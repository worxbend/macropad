"""PCB build steps. Run inside the KiCad container; see the Makefile.

    build.py place    board.toml + circuit.py -> unrouted board + Specctra DSN for the autorouter
    build.py finish   autorouter session -> routed board with ground pours
    build.py fab      routed board -> JLCPCB bill of materials and placement list
"""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew

import fab
import layout

KICAD_DIR = Path(__file__).resolve().parents[1] / "kicad"
BOARD_PATH = KICAD_DIR / "macropad.kicad_pcb"
BUILD_DIR = Path(__file__).resolve().parents[1] / ".build"
DSN_PATH = BUILD_DIR / "macropad.dsn"
SESSION_PATH = BUILD_DIR / "macropad.ses"


def place() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    KICAD_DIR.mkdir(exist_ok=True)
    board = layout.build_board(BOARD_PATH)
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    assert pcbnew.ExportSpecctraDSN(board, str(DSN_PATH)), "Specctra export failed"
    print(f"placed {len(board.GetFootprints())} footprints, {board.GetNetCount() - 1} nets")


def finish() -> None:
    board = pcbnew.LoadBoard(str(BOARD_PATH))
    assert pcbnew.ImportSpecctraSES(board, str(SESSION_PATH)), "Specctra session import failed"
    layout.add_outer_ground_pours(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print(f"routed: {len(board.GetTracks())} track segments and vias")


STEPS = {"place": place, "finish": finish, "fab": lambda: fab.write_assembly_files(BOARD_PATH)}

if __name__ == "__main__":
    step = STEPS.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if step is None:
        sys.exit(__doc__)
    step()
