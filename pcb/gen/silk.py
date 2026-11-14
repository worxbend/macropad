"""Silkscreen: what a person needs to read off the bare board. Needs pcbnew.

Top face (keys, knobs, display): key numbers with their GPIO, the display outline and its pin
names, the encoder pin names, the board name. Bottom face (all machine-placed parts): button
names, debug pad names, LED chain order, revision.
"""

from __future__ import annotations

import pcbnew

import circuit
from circuit import BOARD_SPEC

REVISION = "A"
# JLCPCB's legibility minimums: 1.0 mm text height, 0.15 mm line and stroke width.
_LINE_WIDTH = 0.15
_TEXT_SIZE = 1.0
_STROKE_RATIO = 0.15  # stroke width over text height
# How far the display outline runs down its socket side before it stops short of the socket outline.
_MODULE_CORNER_RETURN = 2.6
# The free band between the first two key rows, on the bottom face.
_BOTTOM_BAND_Y = 38.6
_DEBUG_PAD_NAMES = {"TP1": "CLK", "TP2": "DIO", "TP3": "GND"}
# Supply probe pads: name, and where the name sits from the pad centre (x, y).
_SUPPLY_PAD_NAMES = {"TP4": ("5V", 0.0, 1.6), "TP5": ("3V3", 0.0, 1.6), "TP6": ("1V1", 0.0, 1.6)}
# The display pin names sit between the socket outline and the glass window, which leaves room for
# narrower letters only. The height stays at the minimum.
_NARROW_TEXT_WIDTH = 0.8


def _mm(value: float) -> int:
    return pcbnew.FromMM(value)


def _text(board: pcbnew.BOARD, text: str, x: float, y: float, layer: int, size: float = _TEXT_SIZE,
          width: float | None = None) -> None:
    """Text of the given height; letter width equals the height unless set narrower."""
    assert size >= _TEXT_SIZE, f"silkscreen text {text!r} is {size} mm high, below the {_TEXT_SIZE} mm minimum"
    label = pcbnew.PCB_TEXT(board)
    label.SetText(text)
    label.SetPosition(pcbnew.VECTOR2I(_mm(x), _mm(y)))
    label.SetLayer(layer)
    label.SetTextSize(pcbnew.VECTOR2I(_mm(width or size), _mm(size)))
    label.SetTextThickness(_mm(size * _STROKE_RATIO))
    label.SetMirrored(layer == pcbnew.B_SilkS)
    board.Add(label)


def _rectangle(board: pcbnew.BOARD, centre: tuple[float, float], length: float, width: float) -> None:
    shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    shape.SetStart(pcbnew.VECTOR2I(_mm(centre[0] - length / 2), _mm(centre[1] - width / 2)))
    shape.SetEnd(pcbnew.VECTOR2I(_mm(centre[0] + length / 2), _mm(centre[1] + width / 2)))
    shape.SetLayer(pcbnew.F_SilkS)
    shape.SetWidth(_mm(_LINE_WIDTH))
    board.Add(shape)


def _line(board: pcbnew.BOARD, start: tuple[float, float], end: tuple[float, float]) -> None:
    shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    shape.SetStart(pcbnew.VECTOR2I(_mm(start[0]), _mm(start[1])))
    shape.SetEnd(pcbnew.VECTOR2I(_mm(end[0]), _mm(end[1])))
    shape.SetLayer(pcbnew.F_SilkS)
    shape.SetWidth(_mm(_LINE_WIDTH))
    board.Add(shape)


def _module_outline(board: pcbnew.BOARD, display: dict) -> None:
    """The display module's edge. Open along the socket, whose own outline runs on the same line there."""
    left, right = display["x"] - display["length"] / 2, display["x"] + display["length"] / 2
    top, bottom = display["y"] - display["width"] / 2, display["y"] + display["width"] / 2
    corners = [(left, top + _MODULE_CORNER_RETURN), (left, top), (right, top), (right, bottom), (left, bottom)]
    for start, end in zip(corners, corners[1:]):
        _line(board, start, end)


def _keys(board: pcbnew.BOARD) -> None:
    """Under each switch, between its centre post and its front edge: key number and GPIO."""
    for index, gpio in enumerate(BOARD_SPEC["keys"]["gpio"]):
        x, y = circuit.key_centre(index)
        _text(board, f"K{index} GP{gpio}", x, y + 4.6, pcbnew.F_SilkS)


def _display(board: pcbnew.BOARD) -> None:
    display = BOARD_SPEC["display"]
    _module_outline(board, display)
    _rectangle(board, (display["window_x"], display["window_y"]), display["window_length"], display["window_width"])
    _text(board, "nice!view", display["window_x"], display["window_y"] - 1.2, pcbnew.F_SilkS)
    _text(board, "glass this side up", display["window_x"], display["window_y"] + 1.0, pcbnew.F_SilkS)
    pins = display["header_pins"]
    first_pin_y = display["y"] - display["header_pitch"] * (len(pins) - 1) / 2
    for row, name in enumerate(pins):
        _text(board, name, display["header_x"] + 2.95, first_pin_y + row * display["header_pitch"], pcbnew.F_SilkS,
              width=_NARROW_TEXT_WIDTH)


def _encoders(board: pcbnew.BOARD) -> None:
    for name, side in (("ENC L", "left"), ("ENC R", "right")):
        encoder = BOARD_SPEC["encoders"][side]
        pin_x = encoder["x"] - 7.5 - 1.9  # left of the A/C/B pin row
        for pin_name, dy in (("A", -2.5), ("C", 0.0), ("B", 2.5)):
            _text(board, pin_name, pin_x, encoder["y"] + dy, pcbnew.F_SilkS)
        gpios = f"GP{encoder['gpio_a']}/{encoder['gpio_b']}/{encoder['gpio_sw']}"
        _text(board, f"{name}  A/B/SW {gpios}", encoder["x"], encoder["y"] + 8.2, pcbnew.F_SilkS)


def _top_title(board: pcbnew.BOARD) -> None:
    height = BOARD_SPEC["board"]["height"]
    _text(board, f"macropad rev {REVISION}", 42.0, 20.6, pcbnew.F_SilkS, 1.2)
    _text(board, "github.com/worxbend/macropad", 42.0, 22.5, pcbnew.F_SilkS)
    _text(board, "hand-solder on this side: ENC1, ENC2, J2", 42.0, height - 1.6, pcbnew.F_SilkS)


def _bottom(board: pcbnew.BOARD) -> None:
    buttons = BOARD_SPEC["buttons"]
    _text(board, "BOOT", buttons["boot"]["x"], buttons["boot"]["y"] - 3.6, pcbnew.B_SilkS)
    _text(board, "RESET", buttons["reset"]["x"], buttons["reset"]["y"] - 3.6, pcbnew.B_SilkS)
    _text(board, f"macropad rev {REVISION}", 22.0, _BOTTOM_BAND_Y, pcbnew.B_SilkS)
    _text(board, "JLCJLCJLCJLC", 62.0, _BOTTOM_BAND_Y, pcbnew.B_SilkS)  # JLCPCB prints its order number here
    debug_pads = [part for part in circuit.all_parts() if part.ref in _DEBUG_PAD_NAMES]
    for part in debug_pads:
        _text(board, _DEBUG_PAD_NAMES[part.ref], part.x, part.y + 1.6, pcbnew.B_SilkS)
    _text(board, "SWD", debug_pads[0].x - 2.6, debug_pads[0].y, pcbnew.B_SilkS)
    for part in circuit.all_parts():
        if part.ref in _SUPPLY_PAD_NAMES:
            name, dx, dy = _SUPPLY_PAD_NAMES[part.ref]
            _text(board, name, part.x + dx, part.y + dy, pcbnew.B_SilkS)


def _led_order(board: pcbnew.BOARD) -> None:
    """The chain position next to each LED, on the bottom face. Number 1 gets the data first."""
    width = BOARD_SPEC["board"]["width"]
    leds = [part for part in circuit.all_parts() if part.footprint_key == "LED_SIDE"]
    for number, led in enumerate(leds, start=1):
        inboard = 3.4 if led.x < width / 2 else -3.4
        _text(board, f"L{number}", led.x + inboard, led.y - 1.9, pcbnew.B_SilkS)


def add_labels(board: pcbnew.BOARD) -> None:
    _keys(board)
    _display(board)
    _encoders(board)
    _top_title(board)
    _bottom(board)
    _led_order(board)
