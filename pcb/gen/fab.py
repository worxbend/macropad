"""Assembly files from the routed board: JLCPCB bill of materials and component placement list, PCBWay bill of
materials with manufacturer part numbers and PCBWay centroid file.

Gerbers and drill files come from kicad-cli (see the Makefile). Runs inside the KiCad container.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path

import pcbnew

import circuit

FAB_DIR = Path(__file__).resolve().parents[1] / "fab"
# The board's SHA-256 when the order files were last written. make pcb-test compares it with the board.
BOARD_HASH_PATH = FAB_DIR / "board-sha256.txt"

PCBWAY_BOM_COLUMNS = ["Item #", "Designator", "Qty", "Value", "Package", "Manufacturer", "Mfg Part #", "LCSC Part #"]
# PCBWay's assembly file page asks for designator, X, Y, rotation and side (Top or Bottom). Column names follow
# the sample centroid file linked there, with the side spelled out.
PCBWAY_CENTROID_COLUMNS = ["Designator", "Footprint", "Mid X", "Mid Y", "Layer", "Rotation", "Comment"]
# Do-not-populate parts: footprint on the board, left off by the assembler. Must match circuit.py exactly, and none
# may appear in a BOM or a placement file. C13: COUT is the one 4.7 uF (RP2350 datasheet 6.3.8).
DNP_PARTS = ("C13",)


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


def _placed_footprints(board: pcbnew.BOARD, parts: list[circuit.Part]) -> list[pcbnew.FOOTPRINT]:
    machine_assembled = {part.ref for part in parts if part.machine_assembled}
    return sorted((fp for fp in board.GetFootprints() if fp.GetReference() in machine_assembled),
                  key=lambda fp: fp.GetReference())


def _side(footprint: pcbnew.FOOTPRINT) -> str:
    return "Bottom" if footprint.IsFlipped() else "Top"


def _rotation(footprint: pcbnew.FOOTPRINT) -> str:
    """KiCad's rotation, unchanged on both faces. Check it in the assembler's preview (pcb/README.md)."""
    return f"{footprint.GetOrientationDegrees() % 360:.0f}"


def write_placement(board: pcbnew.BOARD, parts: list[circuit.Part], path: Path) -> None:
    rows = []
    for footprint in _placed_footprints(board, parts):
        x, y = _body_centre(footprint)
        # KiCad's Y axis points down; JLCPCB's placement file wants Y up.
        rows.append([footprint.GetReference(), f"{x:.3f}mm", f"{-y:.3f}mm", _side(footprint), _rotation(footprint)])
    with path.open("w", newline="") as placement_file:
        writer = csv.writer(placement_file)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        writer.writerows(rows)


def write_pcbway_centroid(board: pcbnew.BOARD, parts: list[circuit.Part], path: Path) -> None:
    """PCBWay centroid file: millimetres from the board's lower left corner, Y up, positions seen from the top."""
    value = {part.ref: part.value for part in parts}
    height = circuit.BOARD_SPEC["board"]["height"]
    with path.open("w", newline="") as centroid_file:
        writer = csv.writer(centroid_file)
        writer.writerow(PCBWAY_CENTROID_COLUMNS)
        for footprint in _placed_footprints(board, parts):
            x, y = _body_centre(footprint)
            ref = footprint.GetReference()
            writer.writerow([ref, str(footprint.GetFPID().GetLibItemName()), f"{x:.3f}mm", f"{height - y:.3f}mm",
                             _side(footprint), _rotation(footprint), value[ref]])


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
    bom_rows = _read_csv("bom-jlcpcb.csv")
    pcbway_rows = _read_csv("bom-pcbway.csv")
    placement_rows = _read_csv("cpl-jlcpcb.csv")
    centroid_rows = _read_csv("centroid-pcbway.csv")
    with (FAB_DIR / "centroid-pcbway.csv").open() as centroid_file:
        assert next(csv.reader(centroid_file)) == PCBWAY_CENTROID_COLUMNS, "PCBWay centroid file has other columns"
    placed = [row["Designator"] for row in placement_rows]
    centroid = [row["Designator"] for row in centroid_rows]
    listed = [ref for row in bom_rows for ref in row["Designator"].split(",")]
    pcbway_listed = [ref for row in pcbway_rows for ref in row["Designator"].split(",")]
    _check_dnp(board, parts, listed + pcbway_listed + placed + centroid)
    assert sorted(listed) == sorted(placed) == sorted(pcbway_listed) == sorted(centroid) == sorted(machine_assembled), \
        "BOMs, placement lists and circuit.py differ"
    assert {row["Layer"] for row in placement_rows + centroid_rows} <= {"Top", "Bottom"}, "side is not Top or Bottom"
    unnumbered = [row["Comment"] for row in bom_rows if not re.fullmatch(r"C\d+", row["LCSC Part #"])]
    assert not unnumbered, f"no JLCPCB part number for {unnumbered}"
    no_mpn = [row["Value"] for row in pcbway_rows if not (row["Manufacturer"] and row["Mfg Part #"])]
    assert not no_mpn, f"no manufacturer part number for {no_mpn}"
    miscounted = [row["Value"] for row in pcbway_rows if int(row["Qty"]) != len(row["Designator"].split(","))]
    assert not miscounted, f"PCBWay quantity does not match the designators for {miscounted}"
    height = circuit.BOARD_SPEC["board"]["height"]
    _check_placement_on_parts(board, placement_rows, lambda y: -y)
    _check_placement_on_parts(board, centroid_rows, lambda y: height - y)
    for row in placement_rows + centroid_rows:
        footprint = board.FindFootprintByReference(row["Designator"])
        assert row["Layer"] == _side(footprint) and row["Rotation"] == _rotation(footprint), \
            f"{row['Designator']}: side or rotation differs from the board"


def _read_csv(name: str) -> list[dict[str, str]]:
    with (FAB_DIR / name).open() as csv_file:
        return list(csv.DictReader(csv_file))


def _check_dnp(board: pcbnew.BOARD, parts: list[circuit.Part], listed: list[str]) -> None:
    """The do-not-populate parts are exactly DNP_PARTS, keep their footprint and pads, carry KiCad's DNP mark,
    and appear in no BOM and no placement file."""
    dnp = sorted(part.ref for part in parts if part.dnp)
    assert dnp == sorted(DNP_PARTS), f"circuit.py marks {dnp} do-not-populate, fab.py expects {sorted(DNP_PARTS)}"
    for ref in DNP_PARTS:
        footprint = board.FindFootprintByReference(ref)
        assert footprint is not None and len(footprint.Pads()) > 0, f"{ref}: footprint or pads missing"
        assert footprint.IsDNP() and footprint.IsExcludedFromPosFiles(), f"{ref} is not marked DNP on the board"
    in_files = sorted(set(listed) & set(DNP_PARTS))
    assert not in_files, f"do-not-populate parts {in_files} are in a BOM or placement file"


def board_hash(board_path: Path) -> str:
    return hashlib.sha256(board_path.read_bytes()).hexdigest()


def _check_placement_on_parts(board: pcbnew.BOARD, placement_rows: list[dict[str, str]], to_kicad_y) -> None:
    """Every placement point lies inside its own part's courtyard, so the nozzle lands on the part."""
    for row in placement_rows:
        footprint = board.FindFootprintByReference(row["Designator"])
        footprint.BuildCourtyardCaches()
        x, y = float(row["Mid X"].removesuffix("mm")), to_kicad_y(float(row["Mid Y"].removesuffix("mm")))
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
    write_pcbway_centroid(board, parts, FAB_DIR / "centroid-pcbway.csv")
    check_outputs(board, parts)
    BOARD_HASH_PATH.write_text(f"{board_hash(board_path)}  {board_path.name}\n")
    assembled = sum(part.machine_assembled for part in parts)
    print(f"assembly files: {assembled} machine-placed parts, {len(DNP_PARTS)} do-not-populate; Gerbers, drill file, "
          "both BOMs and both placement files agree")
