"""The committed board and order files belong together. Plain Python, no KiCad.

    python3 -m unittest discover -s pcb/gen -p 'test_*.py'

Fails when the routing report shows an unrouted pad, or when the board changed after the order files in
pcb/fab/ were written: by its hash (recorded by `make pcb-fab`), and by file times where they mean something.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

PCB_DIR = Path(__file__).resolve().parents[1]
BOARD_PATH = PCB_DIR / "kicad" / "macropad.kicad_pcb"
GERBER_DIR = PCB_DIR / "fab" / "gerbers"
BOARD_HASH_PATH = PCB_DIR / "fab" / "board-sha256.txt"
ROUTING_REPORT_PATH = PCB_DIR / "routing.txt"
# A fresh checkout writes every file within a moment, in path order, so pcb/fab/ lands a little before
# pcb/kicad/. A board rebuilt after the order files is minutes newer.
CHECKOUT_SLACK_SECONDS = 10.0


class OrderFilesTest(unittest.TestCase):
    def test_every_pad_is_routed(self) -> None:
        first_line = ROUTING_REPORT_PATH.read_text().splitlines()[0]
        self.assertTrue(first_line.endswith("unrouted pads 0"), f"routing.txt: {first_line}")

    def test_order_files_were_written_from_this_board(self) -> None:
        recorded = BOARD_HASH_PATH.read_text().split()[0]
        actual = hashlib.sha256(BOARD_PATH.read_bytes()).hexdigest()
        self.assertEqual(recorded, actual, "the board changed after `make pcb-fab`; run it again")

    def test_no_gerber_is_older_than_the_board(self) -> None:
        board_time = BOARD_PATH.stat().st_mtime
        gerbers = sorted(GERBER_DIR.glob("macropad-*"))
        self.assertTrue(gerbers, f"no Gerbers in {GERBER_DIR}")
        stale = [gerber.name for gerber in gerbers if gerber.stat().st_mtime < board_time - CHECKOUT_SLACK_SECONDS]
        self.assertEqual(stale, [], "Gerbers older than the board; run `make pcb-fab`")


if __name__ == "__main__":
    unittest.main()
