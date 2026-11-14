"""Assembly files from the routed board: JLCPCB bill of materials, component placement list, and a
PCBWay bill of materials with manufacturer part numbers.

Gerbers and drill files come from kicad-cli (see the Makefile). Runs inside the KiCad container.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import pcbnew

import circuit

FAB_DIR = Path(__file__).resolve().parents[1] / "fab"


PCBWAY_BOM_COLUMNS = ["Item #", "Designator", "Qty", "Value", "Package", "Manufacturer", "Mfg Part #", "LCSC Part #"]


def _bom_lines(parts: list[circuit.Part]) -> list[tuple[circuit.Part, list[str]]]:
    """One line per distinct machine-placed part: a sample part and every reference that uses it.
    Hand-soldered parts are listed in docs/parts.md, not here."""
    refs_by_part: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    sample: dict[tuple[str, str, str], circuit.Part] = {}
    for part in parts:
        if part.machine_assembled:
            key = (part.value, _package(part), part.lcsc)
            refs_by_part[key].append(part.ref)
            sample.setdefault(key, part)
    return [(sample[key], refs_by_part[key]) for key in sorted(refs_by_part)]


def _package(part: circuit.Part) -> str:
    return part.footprint.split(":")[1]


def write_bom(parts: list[circuit.Part], path: Path) -> None:
    with path.open("w", newline="") as bom_file:
        writer = csv.writer(bom_file)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for part, refs in _bom_lines(parts):
            writer.writerow([part.value, ",".join(refs), _package(part), part.lcsc])


def write_pcbway_bom(parts: list[circuit.Part], path: Path) -> None:
    """The columns PCBWay's turnkey assembly asks for. The LCSC number goes along as the distributor part number."""
    with path.open("w", newline="") as bom_file:
        writer = csv.writer(bom_file)
        writer.writerow(PCBWAY_BOM_COLUMNS)
        for item, (part, refs) in enumerate(_bom_lines(parts), start=1):
            manufacturer, mpn = part.manufacturer_part
            writer.writerow([item, ",".join(refs), len(refs), part.value, _package(part), manufacturer, mpn, part.lcsc])


def _body_centre(footprint: pcbnew.FOOTPRINT) -> tuple[float, float]:
    """Centre of the part body, drawn on the fabrication layer: where the pick-and-place nozzle holds the part.

    Not the centre of the SMD pads: J1's SMD pads are one row 4 mm behind the receptacle body, and an LED's
    pads sit 0.525 mm to the side of its body. Not the footprint origin either: the hot-swap socket's origin
    is the switch centre. A footprint with no body outline falls back to the centre of its pads.
    """
    fab_layers = (pcbnew.F_Fab, pcbnew.B_Fab)
    boxes = [item.GetBoundingBox() for item in footprint.GraphicalItems()
             if item.GetLayer() in fab_layers and item.GetClass() == "PCB_SHAPE"]
    if not boxes:
        boxes = [pad.GetBoundingBox() for pad in footprint.Pads()]
    left = min(pcbnew.ToMM(box.GetLeft()) for box in boxes)
    right = max(pcbnew.ToMM(box.GetRight()) for box in boxes)
    top = min(pcbnew.ToMM(box.GetTop()) for box in boxes)
    bottom = max(pcbnew.ToMM(box.GetBottom()) for box in boxes)
    return (left + right) / 2, (top + bottom) / 2


def write_placement(board: pcbnew.BOARD, parts: list[circuit.Part], path: Path) -> None:
    machine_assembled = {part.ref for part in parts if part.machine_assembled}
    rows = []
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if ref not in machine_assembled:
            continue
        x, y = _body_centre(footprint)
        layer = "Bottom" if footprint.IsFlipped() else "Top"
        # KiCad's Y axis points down; JLCPCB's placement file wants Y up.
        rows.append([ref, f"{x:.3f}mm", f"{-y:.3f}mm", layer, f"{footprint.GetOrientationDegrees() % 360:.0f}"])
    with path.open("w", newline="") as placement_file:
        writer = csv.writer(placement_file)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        writer.writerows(sorted(rows))


GERBER_SUFFIXES = ("F_Cu.gtl", "In1_Cu.g1", "In2_Cu.g2", "B_Cu.gbl", "F_Paste.gtp", "B_Paste.gbp",
                   "F_Silkscreen.gto", "B_Silkscreen.gbo", "F_Mask.gts", "B_Mask.gbs", "Edge_Cuts.gm1")


def _drill_hits_by_diameter(drill_path: Path) -> dict[str, int]:
    """Excellon file -> hole count per tool diameter ("0.300")."""
    diameter_of_tool: dict[str, str] = {}
    hits: dict[str, int] = defaultdict(int)
    current = ""
    for line in drill_path.read_text().splitlines():
        tool = re.fullmatch(r"(T\d+)(?:C([\d.]+))?", line)
        if tool and tool.group(2):
            diameter_of_tool[tool.group(1)] = tool.group(2)
        elif tool:
            current = diameter_of_tool[tool.group(1)]
        elif line.startswith("X") and "G85" not in line:
            hits[current] += 1
    return dict(hits)


def check_outputs(board: pcbnew.BOARD, parts: list[circuit.Part]) -> None:
    """The files in pcb/fab/ agree with the board and with each other. Run after the Gerber export."""
    gerber_dir = FAB_DIR / "gerbers"
    for suffix in GERBER_SUFFIXES:
        gerber = gerber_dir / f"macropad-{suffix}"
        assert gerber.is_file() and gerber.stat().st_size > 0, f"missing or empty {gerber}"
        board_written = Path(board.GetFileName()).stat().st_mtime
        assert gerber.stat().st_mtime >= board_written, f"{gerber.name} is older than the board"

    via_drills = {f"{pcbnew.ToMM(track.GetDrillValue()):.3f}" for track in board.GetTracks()
                  if track.GetClass() == "PCB_VIA"}
    assert len(via_drills) == 1, f"vias with different drills: {via_drills}"
    via_count = sum(track.GetClass() == "PCB_VIA" for track in board.GetTracks())
    drilled = _drill_hits_by_diameter(gerber_dir / "macropad-PTH.drl").get(via_drills.pop(), 0)
    assert drilled == via_count, f"{via_count} vias on the board, {drilled} in the drill file"

    machine_assembled = {part.ref for part in parts if part.machine_assembled}
    with (FAB_DIR / "bom-jlcpcb.csv").open() as bom_file:
        bom_rows = list(csv.DictReader(bom_file))
    with (FAB_DIR / "bom-pcbway.csv").open() as bom_file:
        pcbway_rows = list(csv.DictReader(bom_file))
    with (FAB_DIR / "cpl-jlcpcb.csv").open() as placement_file:
        placement_rows = list(csv.DictReader(placement_file))
    placed = [row["Designator"] for row in placement_rows]
    listed = [ref for row in bom_rows for ref in row["Designator"].split(",")]
    pcbway_listed = [ref for row in pcbway_rows for ref in row["Designator"].split(",")]
    assert sorted(listed) == sorted(placed) == sorted(pcbway_listed) == sorted(machine_assembled), \
        "BOMs, placement list and circuit.py differ"
    unnumbered = [row["Comment"] for row in bom_rows if not re.fullmatch(r"C\d+", row["LCSC Part #"])]
    assert not unnumbered, f"no JLCPCB part number for {unnumbered}"
    no_mpn = [row["Value"] for row in pcbway_rows if not (row["Manufacturer"] and row["Mfg Part #"])]
    assert not no_mpn, f"no manufacturer part number for {no_mpn}"
    miscounted = [row["Value"] for row in pcbway_rows if int(row["Qty"]) != len(row["Designator"].split(","))]
    assert not miscounted, f"PCBWay quantity does not match the designators for {miscounted}"
    _check_placement_on_parts(board, placement_rows)


def _check_placement_on_parts(board: pcbnew.BOARD, placement_rows: list[dict[str, str]]) -> None:
    """Every placement point lies inside its own part's courtyard, so the nozzle lands on the part."""
    for row in placement_rows:
        footprint = board.FindFootprintByReference(row["Designator"])
        footprint.BuildCourtyardCaches()
        x, y = float(row["Mid X"].removesuffix("mm")), -float(row["Mid Y"].removesuffix("mm"))
        courtyard = footprint.GetCourtyard(pcbnew.B_CrtYd if footprint.IsFlipped() else pcbnew.F_CrtYd)
        assert courtyard.OutlineCount() and courtyard.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))), \
            f"{row['Designator']}: placement point ({x:.3f}, {y:.3f}) is not on the part"


def write_assembly_files(board_path: Path) -> None:
    FAB_DIR.mkdir(exist_ok=True)
    parts = circuit.all_parts()
    board = pcbnew.LoadBoard(str(board_path))
    write_bom(parts, FAB_DIR / "bom-jlcpcb.csv")
    write_pcbway_bom(parts, FAB_DIR / "bom-pcbway.csv")
    write_placement(board, parts, FAB_DIR / "cpl-jlcpcb.csv")
    check_outputs(board, parts)
    assembled = sum(part.machine_assembled for part in parts)
    print(f"assembly files: {assembled} machine-placed parts; Gerbers, drill file, both BOMs and placement list agree")
