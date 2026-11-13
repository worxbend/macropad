"""JLCPCB assembly files from the routed board: bill of materials and component placement list.

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


def write_bom(parts: list[circuit.Part], path: Path) -> None:
    """One row per distinct part. Hand-soldered parts are listed in the README, not here."""
    refs_by_part: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for part in parts:
        if part.machine_assembled:
            package = part.footprint.split(":")[1]
            refs_by_part[(part.value, package, part.lcsc)].append(part.ref)
    with path.open("w", newline="") as bom_file:
        writer = csv.writer(bom_file)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (value, package, lcsc), refs in sorted(refs_by_part.items()):
            writer.writerow([value, ",".join(refs), package, lcsc])


def _smd_pad_centre(footprint: pcbnew.FOOTPRINT) -> tuple[float, float]:
    """Centre of the SMD pads: where the pick-and-place nozzle puts the part.

    The hot-swap socket footprint has its origin at the switch centre, not at the socket body.
    """
    pads = [pad.GetPosition() for pad in footprint.Pads() if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    xs = [pcbnew.ToMM(position.x) for position in pads]
    ys = [pcbnew.ToMM(position.y) for position in pads]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def write_placement(board: pcbnew.BOARD, parts: list[circuit.Part], path: Path) -> None:
    machine_assembled = {part.ref for part in parts if part.machine_assembled}
    rows = []
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if ref not in machine_assembled:
            continue
        x, y = _smd_pad_centre(footprint)
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
    with (FAB_DIR / "cpl-jlcpcb.csv").open() as placement_file:
        placed = [row["Designator"] for row in csv.DictReader(placement_file)]
    listed = [ref for row in bom_rows for ref in row["Designator"].split(",")]
    assert sorted(listed) == sorted(placed) == sorted(machine_assembled), "BOM, placement list and circuit.py differ"
    unnumbered = [row["Comment"] for row in bom_rows if not re.fullmatch(r"C\d+", row["LCSC Part #"])]
    assert not unnumbered, f"no JLCPCB part number for {unnumbered}"


def write_assembly_files(board_path: Path) -> None:
    FAB_DIR.mkdir(exist_ok=True)
    parts = circuit.all_parts()
    board = pcbnew.LoadBoard(str(board_path))
    write_bom(parts, FAB_DIR / "bom-jlcpcb.csv")
    write_placement(board, parts, FAB_DIR / "cpl-jlcpcb.csv")
    check_outputs(board, parts)
    assembled = sum(part.machine_assembled for part in parts)
    print(f"assembly files: {assembled} machine-placed parts; Gerbers, drill file, BOM and placement list agree")
