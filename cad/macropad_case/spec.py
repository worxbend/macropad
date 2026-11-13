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
    chamfer: float = 0.8  # every outer top and bottom edge
    seam_chamfer: float = 0.3  # on both sides of the base/top joint: a V groove that hides a small mismatch
    min_wall: float = 0.8  # two passes of a 0.4 mm nozzle; nothing thinner is allowed
    # Lap joint: ridges on the base rim, inside the wall, that enter grooves in the top's skirt. They
    # centre the two shells on each other and close the straight path for light through the seam.
    lap_height: float = 0.6
    lap_crest: float = 0.8  # flat top of a ridge; its outer flank and its ends fall at 45 degrees
    lap_fit: float = 0.2  # a ridge is this much smaller than its groove; the 45 degree flanks end up 0.14 apart
    lap_corner_inset: float = 10.0  # ridges stop short of the corners, where the screw bosses join the walls
    lap_end_room: float = 3.0  # a groove is this much longer than its ridge at each end
    lap_groove_reach: float = 3.5  # how far a groove opens into the cavity, so an end mill can clear it
    cnc_corner_radius: float = 1.5  # a 3 mm end mill

    base_boss_diameter: float = 5.5  # as wide as the hot-swap sockets next to the centre bosses allow
    boss_root_diameter: float = 8.0  # the boss is wider below the sockets, where it joins the floor
    boss_root_height: float = 2.4
    top_boss_diameter: float = 4.5
    screw_length: float = 10.0  # M2 x 10
    counterbore_diameter: float = 4.4
    counterbore_depth: float = 2.4
    pilot_diameter: float = 1.7  # self-tapping in plastic; tap drill for M2 in aluminium is 1.6
    pilot_depth: float = 4.2
    min_screw_engagement: float = 3.0
    screw_head: tuple[float, float] = (3.8, 2.0)  # ISO 4762 M2 cap head: diameter, height
    screw_thread_core: float = 1.6  # thread minor diameter, drawn inside the self-tapped hole

    rib_width: float = 2.0  # plate ribs between the key rows
    rib_to_pcb: float = 1.0  # above the lap grooves, so the ribs do not close them

    keycap_width: float = 18.1
    keycap_to_deck: float = 0.5
    keycap_pressed_bottom: float = 2.0  # MEASURE: keycap skirt above the plate at full travel
    keycap_top: float = 14.5  # MEASURE: tallest common keycap above the plate
    key_travel: float = 4.0
    keycap_profile: tuple[float, float, float] = (12.7, 7.4, 0.6)  # DSA: top width, height, dish depth
    switch_body: float = 13.95
    deck_front_wall: float = 1.5

    encoder_body: tuple[float, float] = (12.4, 13.4)  # MEASURE: X, Y
    bushing_length: float = 7.0  # MEASURE: threaded bushing above the encoder body
    bushing_clearance: float = 0.4
    shaft_diameter: float = 6.0
    shaft_flat: float = 4.5  # MEASURE: D-shaft thickness across the flat

    knob_diameter: float = 16.0
    knob_to_deck: float = 1.0  # knob underside to the floor of its well
    knob_well_margin: float = 1.0  # radial gap between the knob and the wall of its well
    knob_well_depth: float = 0.5
    knob_flutes: int = 20
    knob_flute_radius: float = 1.0
    knob_flute_depth: float = 0.5
    knob_plain_band: float = 2.0  # smooth band under the flutes
    knob_pointer: tuple[float, float] = (1.2, 0.5)  # groove width, depth
    knob_cap: float = 2.0
    knob_bore_clearance: float = 0.2
    encoder_press_travel: float = 0.5

    display_thickness: float = 2.9  # MEASURE: nice!view module, PCB bottom to glass top
    display_relief: float = 0.4  # pocket under the deck so the glass never carries the deck
    display_relief_margin: float = 0.5  # keeps the pocket's roof a 15 mm bridge when the top prints on its side
    bezel_chamfer: float = 0.8  # 45 degree lead-in around the display window
    display_glass: tuple[float, float] = (30.0, 13.6)  # MEASURE: LCD glass on the module, length and width
    display_board_thickness: float = 1.0  # MEASURE: the module's own PCB

    usb_body: tuple[float, float] = (8.94, 7.35)  # receptacle width, depth
    usb_plug: tuple[float, float] = (12.5, 6.5)  # plug overmould width, height
    usb_margin: float = 0.25
    usb_mouth_chamfer: float = 0.6

    button_hole_diameter: float = 2.5
    button_body: tuple[float, float] = (5.1, 1.5)  # tact switch width, height
    foot_diameter: float = 8.4  # recess for an 8 mm stick-on foot
    foot_depth: float = 0.6
    foot_inset: float = 12.0
    foot: tuple[float, float] = (8.0, 1.6)  # MEASURE: stick-on bumper diameter, height
    engraving_depth: float = 0.4
    tilt_angle: float = 6.0  # degrees, with the optional tilt bar under the back feet
    tilt_bar_depth: float = 11.0  # front to back, centred on the back feet
    tilt_bar_overhang: float = 6.0  # past each back foot centre, left and right
    tilt_peg_clearance: float = 0.3  # the pegs that sit in the base's back foot recesses

    led_body: tuple[float, float, float] = (4.0, 1.6, 1.6)  # MEASURE: along the edge, depth, height
    led_window_margin: float = 1.0
    led_sill: float = 1.0  # wall left under the diffuser slot
    diffuser_fit: float = 0.15
    diffuser_flange: float = 1.2
    diffuser_flange_overlap: float = 1.0  # a ledge this deep still prints without support
    diffuser_flange_to_floor: float = 0.2
    diffuser_flange_top_below_pcb: float = 2.0  # keeps the flange under the LEDs
    diffuser_to_pcb: float = 0.05
    diffuser_proud: float = 0.5  # the strip stands out of the wall, with its edges cut back at 45 degrees

    socket_box: tuple[float, float, float, float] = (-8.4, 7.2, -6.9, -0.5)  # hot-swap socket, from key centre
    switch_post: tuple[float, float] = (4.0, 3.3)  # MX centre post diameter, length below the PCB top

    max_bridge: float = 15.0  # longest unsupported span accepted by the printability check
    max_cantilever: float = 1.5  # deepest ledge that may hang from one side. A guess: about three 0.45 mm lines


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
    boss_root_top: float
    rib_bottom: float
    knob_well_floor: float
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
        boss_root_top=floor_top + CASE.boss_root_height,
        rib_bottom=CASE.rib_to_pcb,
        knob_well_floor=stack.deck_top - CASE.knob_well_depth,
        knob_bottom=stack.deck_top - CASE.knob_well_depth + CASE.knob_to_deck,
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


def lap_runs() -> list[tuple[str, float, float]]:
    """Where the lap ridges run: (wall, start, end) along that wall in board coordinates. They leave out
    the corners, the USB opening and the light-strip slots."""
    inset = CASE.lap_corner_inset
    width, height = BOARD.board.width, BOARD.board.height
    usb_half = CASE.usb_plug[0] / 2 + CASE.usb_margin + CASE.usb_mouth_chamfer + 1.0
    side_end = led_slot_span()[0] - CASE.diffuser_flange_overlap - CASE.lap_end_room - 0.5
    return [
        ("back", inset, BOARD.usb.x - usb_half), ("back", BOARD.usb.x + usb_half, width - inset),
        ("front", inset, width - inset), ("left", inset, side_end), ("right", inset, side_end),
    ]


def rib_lines() -> list[float]:
    """Board Y of each plate rib: halfway between two key rows."""
    keys = BOARD.keys
    return [keys.first_y + (row + 0.5) * keys.pitch for row in range(keys.rows - 1)]


def foot_centres() -> list[tuple[float, float]]:
    """Back feet first, then front feet."""
    inset = CASE.foot_inset
    width, height = BOARD.board.width, BOARD.board.height
    return [(x, y) for y in (inset, height - inset) for x in (inset, width - inset)]


def buttons() -> dict[str, tuple[float, float]]:
    return {name: (button.x, button.y) for name, button in vars(BOARD.buttons).items()}
