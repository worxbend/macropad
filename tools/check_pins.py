#!/usr/bin/env python3
"""Fail when the firmware pin map disagrees with board.toml.

board.toml is the source of truth for the PCB; firmware/fw/src/board.rs must name the same GPIOs.
"""

import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOARD_TOML = REPO / "board.toml"
BOARD_RS = REPO / "firmware" / "fw" / "src" / "board.rs"

GPIO = r"PIN_(\d+)"


def expected_pins(board: dict) -> dict[str, list[int]]:
    """GPIO numbers from board.toml, keyed by the board.rs field that must carry them."""
    left, right = board["encoders"]["left"], board["encoders"]["right"]
    display = board["display"]
    return {
        "keys": board["keys"]["gpio"],
        "left_knob": [left["gpio_a"], left["gpio_b"], left["gpio_sw"]],
        "right_knob": [right["gpio_a"], right["gpio_b"], right["gpio_sw"]],
        "display": [display["gpio_sck"], display["gpio_mosi"], display["gpio_cs"]],
        "leds": [board["leds"]["gpio_data"]],
    }


def firmware_pins(board_rs: str) -> dict[str, list[int]]:
    """GPIO numbers that `Board::take` assigns to each field, in source order."""
    take_body = board_rs.split("pub fn take", 1)[1]
    key_list = re.search(r"keys:\s*\[(.*?)\]", take_body, re.DOTALL)
    if key_list is None:
        raise ValueError("no `keys: [...]` list in Board::take")
    pins = {"keys": [int(gpio) for gpio in re.findall(GPIO, key_list.group(1))]}
    for field in ("left_knob", "right_knob", "display", "leds"):
        initializer = re.search(rf"{field}:\s*\w+\s*\{{(.*?)\}}", take_body, re.DOTALL)
        if initializer is None:
            raise ValueError(f"no `{field}: ... {{ }}` initializer in Board::take")
        pins[field] = [int(gpio) for gpio in re.findall(GPIO, initializer.group(1))]
    return pins


def mismatches(expected: dict[str, list[int]], actual: dict[str, list[int]]) -> list[str]:
    return [
        f"{field}: board.toml says GPIO {expected[field]}, board.rs uses {actual[field]}"
        for field in expected
        if expected[field] != actual[field]
    ]


def main() -> int:
    expected = expected_pins(tomllib.loads(BOARD_TOML.read_text()))
    try:
        actual = firmware_pins(BOARD_RS.read_text())
    except (ValueError, IndexError) as error:
        print(f"check_pins: cannot read the pin map from {BOARD_RS}: {error}", file=sys.stderr)
        return 2
    problems = mismatches(expected, actual)
    for problem in problems:
        print(f"check_pins: {problem}", file=sys.stderr)
    if not problems:
        print(f"check_pins: {sum(map(len, expected.values()))} GPIOs match board.toml")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
