"""The board contract (`board.toml`) and the dimensions that belong to the case alone.

Frames: `board.toml` uses X right, Y toward the front, origin at the PCB's back-left corner.
The model keeps X, flips Y (model Y = -board Y, so the frame stays right-handed) and puts Z = 0
on the PCB top face. Every helper in `solids.py` takes board coordinates.
"""

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import tomllib

BOARD_TOML = Path(__file__).resolve().parents[2] / "board.toml"

PRINT = "print"
CNC = "cnc"
VARIANTS = (PRINT, CNC)


def _namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _namespace(item) for key, item in value.items()})
    return value


def load_board() -> SimpleNamespace:
    with BOARD_TOML.open("rb") as toml_file:
        return _namespace(tomllib.load(toml_file))


@dataclass(frozen=True)
class Case:
    """Case-only dimensions in millimetres. MEASURE = taken from datasheets or photos, not a caliper."""

    wall: float = 2.5
    pcb_gap: float = 0.3
    floor: float = 2.0
    chamfer: float = 0.6
    cnc_corner_radius: float = 1.5  # a 3 mm end mill

    base_boss_diameter: float = 5.5
    top_boss_diameter: float = 4.5
    screw_length: float = 10.0  # M2 x 10
    counterbore_diameter: float = 4.4
    counterbore_depth: float = 2.4
    pilot_diameter: float = 1.7  # self-tapping in plastic; tap drill for M2 in aluminium is 1.6
    pilot_depth: float = 4.2
    min_screw_engagement: float = 3.0

    keycap_width: float = 18.1
    keycap_to_deck: float = 0.5
    keycap_pressed_bottom: float = 2.0  # MEASURE: keycap skirt above the plate at full travel
    keycap_top: float = 14.5  # MEASURE: tallest common keycap above the plate
    switch_body: float = 13.95
    deck_front_wall: float = 1.5

    encoder_body: tuple[float, float] = (12.4, 13.4)  # MEASURE: X, Y
    bushing_length: float = 7.0  # MEASURE: threaded bushing above the encoder body
    bushing_clearance: float = 0.4
    shaft_diameter: float = 6.0
    shaft_flat: float = 4.5  # MEASURE: D-shaft thickness across the flat

    knob_diameter: float = 16.0
    knob_to_deck: float = 1.0
    knob_cap: float = 2.0
    knob_bore_clearance: float = 0.2
    encoder_press_travel: float = 0.5

    display_thickness: float = 2.9  # MEASURE: nice!view module, PCB bottom to glass top
    display_relief: float = 0.4  # pocket under the deck so the glass never carries the deck
    display_relief_margin: float = 1.0

    usb_body: tuple[float, float] = (8.94, 7.35)  # receptacle width, depth
    usb_plug: tuple[float, float] = (12.5, 6.5)  # plug overmould width, height
    usb_margin: float = 0.25

    button_hole_diameter: float = 2.5
    button_body: tuple[float, float] = (5.1, 1.5)  # tact switch width, height
    foot_diameter: float = 8.4  # recess for an 8 mm stick-on foot
    foot_depth: float = 0.6
    foot_inset: float = 12.0

    led_body: tuple[float, float, float] = (4.0, 1.6, 1.6)  # MEASURE: along the edge, depth, height
    led_window_margin: float = 1.0
    led_sill: float = 1.0  # wall left under the diffuser slot
    diffuser_fit: float = 0.15
    diffuser_flange: float = 1.2
    diffuser_flange_overlap: float = 1.5
    diffuser_flange_top_below_pcb: float = 2.0  # keeps the flange under the LEDs
    diffuser_to_pcb: float = 0.05

    socket_box: tuple[float, float, float, float] = (-8.4, 7.2, -6.9, -0.5)  # hot-swap socket, from key centre
    switch_post: tuple[float, float] = (4.0, 3.3)  # MX centre post diameter, length below the PCB top

    max_bridge: float = 15.0  # longest unsupported span accepted by the printability check


CASE = Case()
BOARD = load_board()


def key_centres() -> list[tuple[float, float]]:
    keys = BOARD.keys
    return [
        (keys.first_x + column * keys.pitch, keys.first_y + row * keys.pitch)
        for row in range(keys.rows)
        for column in range(keys.columns)
    ]


def encoder_centres() -> list[tuple[float, float]]:
    return [(BOARD.encoders.left.x, BOARD.encoders.left.y), (BOARD.encoders.right.x, BOARD.encoders.right.y)]


def mounting_holes() -> list[tuple[float, float]]:
    return [tuple(hole) for hole in BOARD.mounting.holes]


@dataclass(frozen=True)
class Levels:
    """Z heights, PCB top face = 0."""

    pcb_bottom: float
    floor_top: float
    floor_bottom: float
    plate_top: float
    plate_bottom: float
    deck_top: float
    deck_bottom: float
    usb_centre: float
    led_slot_bottom: float
    knob_bottom: float
    knob_top: float
    bushing_top: float


def levels() -> Levels:
    stack = BOARD.stack
    pcb_bottom = -BOARD.board.thickness
    floor_top = pcb_bottom - stack.underside_clearance
    bushing_top = stack.encoder_body_top + CASE.bushing_length
    return Levels(
        pcb_bottom=pcb_bottom,
        floor_top=floor_top,
        floor_bottom=floor_top - CASE.floor,
        plate_top=stack.plate_top,
        plate_bottom=stack.plate_top - stack.plate_thickness,
        deck_top=stack.deck_top,
        deck_bottom=stack.deck_top - stack.plate_thickness,
        usb_centre=pcb_bottom - BOARD.usb.body_height / 2,
        led_slot_bottom=floor_top + CASE.led_sill,
        knob_bottom=stack.deck_top + CASE.knob_to_deck,
        knob_top=stack.encoder_shaft_top + CASE.knob_cap,
        bushing_top=bushing_top,
    )


LEVELS = levels()


def deck_front() -> float:
    """Board Y of the deck's front face: just behind the row-0 keycaps."""
    return BOARD.keys.first_y - CASE.keycap_width / 2 - CASE.keycap_to_deck


def led_slot_span() -> tuple[float, float]:
    """Board Y range of the diffuser slot: every LED body plus a margin."""
    led_centres = BOARD.leds.left_y + BOARD.leds.right_y
    half_led = CASE.led_body[0] / 2
    return (min(led_centres) - half_led - CASE.led_window_margin, max(led_centres) + half_led + CASE.led_window_margin)
