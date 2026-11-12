"""JLCPCB assembly files from the routed board: bill of materials and component placement list.

Gerbers and drill files come from kicad-cli (see the Makefile). Runs inside the KiCad container.
"""

from __future__ import annotations

import csv
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


def write_assembly_files(board_path: Path) -> None:
    FAB_DIR.mkdir(exist_ok=True)
    parts = circuit.all_parts()
    board = pcbnew.LoadBoard(str(board_path))
    write_bom(parts, FAB_DIR / "bom-jlcpcb.csv")
    write_placement(board, parts, FAB_DIR / "cpl-jlcpcb.csv")
    assembled = sum(part.machine_assembled for part in parts)
    print(f"assembly files: {assembled} machine-placed parts")
