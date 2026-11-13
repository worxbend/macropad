#!/usr/bin/env python3
"""Fail when the firmware disagrees with board.toml.

board.toml is the source of truth for the PCB. Three things in the firmware repeat it:

- firmware/fw/src/board.rs names the GPIOs,
- firmware/fw/src/board.rs says how the encoder part clicks,
- firmware/core/src/geometry.rs holds the key and LED positions the light effects use,
- firmware/sim/src/board.rs holds the outline, knob and display positions the simulator draws.
"""

import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOARD_TOML = REPO / "board.toml"
BOARD_RS = REPO / "firmware" / "fw" / "src" / "board.rs"
GEOMETRY_RS = REPO / "firmware" / "core" / "src" / "geometry.rs"
SIM_BOARD_RS = REPO / "firmware" / "sim" / "src" / "board.rs"

UM_PER_MM = 1000
# Clicks per electrical cycle of each encoder part the firmware knows, as `quadrature::Detents`.
# EC11E18244AU: 36 detents, 18 pulses per turn (Alps Alpine product page).
ENCODER_DETENTS = {"EC11E18244AU": "PerHalfCycle"}

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


def to_um(millimetres: float) -> int:
    return round(millimetres * UM_PER_MM)


def expected_geometry(board: dict) -> dict[str, object]:
    """Key and LED positions from board.toml in micrometres, keyed by the geometry.rs constant."""
    keys, leds = board["keys"], board["leds"]
    right_x = to_um(board["board"]["width"] - leds["inset"])
    left_x = to_um(leds["inset"])
    return {
        "KEY_COLUMNS": keys["columns"],
        "KEY_FIRST_X_UM": to_um(keys["first_x"]),
        "KEY_FIRST_Y_UM": to_um(keys["first_y"]),
        "KEY_PITCH_UM": to_um(keys["pitch"]),
        "LED_POSITIONS_UM": [(right_x, to_um(y)) for y in leds["right_y"]]
        + [(left_x, to_um(y)) for y in leds["left_y"]],
    }


def integer(literal: str) -> int:
    return int(literal.replace("_", ""))


def firmware_geometry(geometry_rs: str) -> dict[str, object]:
    """The same constants as geometry.rs declares them."""
    geometry: dict[str, object] = {}
    for name in ("KEY_COLUMNS", "KEY_FIRST_X_UM", "KEY_FIRST_Y_UM", "KEY_PITCH_UM"):
        declaration = re.search(rf"pub const {name}: \w+ = ([\d_]+);", geometry_rs)
        if declaration is None:
            raise ValueError(f"no `pub const {name}` in geometry.rs")
        geometry[name] = integer(declaration.group(1))
    positions = re.search(r"pub const LED_POSITIONS_UM:[^=]*=\s*\[(.*?)\];", geometry_rs, re.DOTALL)
    if positions is None:
        raise ValueError("no `pub const LED_POSITIONS_UM` in geometry.rs")
    pairs = re.findall(r"\(\s*([\d_]+)\s*,\s*([\d_]+)\s*\)", positions.group(1))
    geometry["LED_POSITIONS_UM"] = [(integer(x), integer(y)) for x, y in pairs]
    return geometry


def expected_picture(board: dict) -> dict[str, object]:
    """What the simulator draws, from board.toml in micrometres, keyed by the sim board.rs constant."""
    left, right = board["encoders"]["left"], board["encoders"]["right"]
    display = board["display"]
    return {
        "BOARD_WIDTH_UM": to_um(board["board"]["width"]),
        "BOARD_HEIGHT_UM": to_um(board["board"]["height"]),
        "LEFT_KNOB_UM": (to_um(left["x"]), to_um(left["y"])),
        "RIGHT_KNOB_UM": (to_um(right["x"]), to_um(right["y"])),
        "DISPLAY_WINDOW_UM": (to_um(display["window_x"]), to_um(display["window_y"])),
    }


def simulator_picture(sim_board_rs: str) -> dict[str, object]:
    """The same constants as the simulator's board.rs declares them."""
    picture: dict[str, object] = {}
    for name in ("BOARD_WIDTH_UM", "BOARD_HEIGHT_UM"):
        declaration = re.search(rf"pub const {name}: i32 = ([\d_]+);", sim_board_rs)
        if declaration is None:
            raise ValueError(f"no `pub const {name}` in the simulator's board.rs")
        picture[name] = integer(declaration.group(1))
    for name in ("LEFT_KNOB_UM", "RIGHT_KNOB_UM", "DISPLAY_WINDOW_UM"):
        declaration = re.search(rf"pub const {name}: \(i32, i32\) = \(([\d_]+), ([\d_]+)\);", sim_board_rs)
        if declaration is None:
            raise ValueError(f"no `pub const {name}` in the simulator's board.rs")
        picture[name] = (integer(declaration.group(1)), integer(declaration.group(2)))
    return picture


def detent_problems(board: dict, board_rs: str) -> list[str]:
    """board.rs must decode the knobs the way the encoder part in board.toml clicks."""
    part = board["encoders"]["part"]
    if part not in ENCODER_DETENTS:
        return [f"encoder part {part} is not in ENCODER_DETENTS: look up its detents and pulses, then add it"]
    declaration = re.search(r"pub const KNOB_DETENTS: Detents = Detents::(\w+);", board_rs)
    if declaration is None:
        raise ValueError("no `pub const KNOB_DETENTS` in board.rs")
    if declaration.group(1) != ENCODER_DETENTS[part]:
        return [f"KNOB_DETENTS: {part} needs Detents::{ENCODER_DETENTS[part]}, board.rs uses {declaration.group(1)}"]
    return []


def mismatches(expected: dict[str, list[int]], actual: dict[str, list[int]]) -> list[str]:
    return [
        f"{field}: board.toml says {expected[field]}, the firmware uses {actual[field]}"
        for field in expected
        if expected[field] != actual[field]
    ]


def main() -> int:
    board = tomllib.loads(BOARD_TOML.read_text())
    expected = expected_pins(board)
    try:
        board_rs = BOARD_RS.read_text()
        problems = mismatches(expected, firmware_pins(board_rs))
        problems += detent_problems(board, board_rs)
        problems += mismatches(expected_geometry(board), firmware_geometry(GEOMETRY_RS.read_text()))
        problems += mismatches(expected_picture(board), simulator_picture(SIM_BOARD_RS.read_text()))
    except (ValueError, IndexError) as error:
        print(f"check_pins: cannot read the firmware sources: {error}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"check_pins: {problem}", file=sys.stderr)
    if not problems:
        print(f"check_pins: {sum(map(len, expected.values()))} GPIOs match board.toml")
        print("check_pins: knob detents, key grid and 8 LED positions match board.toml")
        print("check_pins: the simulator's outline, knob and display positions match board.toml")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
