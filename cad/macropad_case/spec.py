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
    """Case-only dimensions in millimetres. MEASURE = taken from datasheets or photos, not a caliper.
    "guess" = chosen without a part or a print to check it against."""

    wall: float = 2.7  # the two side walls, and what the lap joint is sized from
    back_wall: float = 3.175  # with `front_wall`, makes the case as deep as it is wide
    front_wall: float = 3.725  # and the flat frame in front of the key dish as wide as beside it
    pcb_gap: float = 0.3
    floor: float = 2.4
    chamfer: float = 0.5  # top rim, knob rims, USB lead-in
    underside_chamfer: float = 1.5  # makes the dark base recede
    seam_chamfer: float = 0.3  # the three edges at the base/top joint
    gap_height: float = 1.2  # the line round the case: the base rim steps in under the top
    gap_depth: float = 1.0
    corner_setback: float = 10.0  # CNC: where a corner curve leaves the straight side
    corner_handles: tuple[float, float] = (0.6, 0.2)  # CNC: inner control points of the curve, as shares of the setback
    print_corner_radius: float = 6.4  # same apex as the CNC corner; the top prints standing, so it must be an arc
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
    counterbore_depth: float = 2.9  # from the underside; the head ends up above the foot recess
    screw_cone: tuple[float, float] = (7.0, 5.0)  # 45 degree cone from the foot recess up to the counterbore
    pilot_diameter: float = 1.7  # self-tapping in plastic; tap drill for M2 in aluminium is 1.6
    pilot_depth: float = 4.2
    min_screw_engagement: float = 3.0
    screw_head: tuple[float, float] = (3.8, 2.0)  # ISO 4762 M2 cap head: diameter, height
    screw_thread_core: float = 1.6  # thread minor diameter, drawn inside the self-tapped hole

    rib_width: float = 2.0  # plate ribs between the key rows
    rib_to_pcb: float = 1.0  # above the lap grooves, so the ribs do not close them

    keycap_width: float = 18.1
    keycap_pressed_bottom: float = 2.0  # MEASURE: keycap skirt above the plate at full travel
    keycap_top: float = 14.5  # MEASURE: tallest common keycap above the plate
    key_travel: float = 4.0
    keycap_profile: tuple[float, float, float] = (12.7, 7.4, 0.6)  # DSA: top width, height, dish depth
    switch_body: float = 13.95
    dish_floor_margin: float = 8.15  # outer key centres to the foot of the dish wall: the MX rim (7.8) and 0.35
    dish_floor_radius: float = 1.5
    deck_front_wall: float = 1.85  # between the dish wall and the pocket under the deck, level with the deck skin

    encoder_body: tuple[float, float] = (12.4, 13.4)  # MEASURE: X, Y
    bushing_length: float = 7.0  # MEASURE: threaded bushing above the encoder body
    bushing_clearance: float = 0.4
    shaft_diameter: float = 6.0
    shaft_flat: float = 4.5  # MEASURE: D-shaft thickness across the flat

    knob_diameter: float = 16.0
    knob_to_deck: float = 1.0  # knob underside above the deck
    knob_well_depth: float = 0.0  # the knobs stand on the plain deck
    knob_grooves: int = 36  # guess: the land between two grooves is still one 0.4 mm line wide
    knob_groove_depth: float = 0.45  # a 90 degree V, so twice as wide as deep
    knob_plain_band: float = 1.5  # smooth band under and over the grooves
    knob_pointer: tuple[float, float, float] = (1.2, 0.4, 5.5)  # dimple diameter, depth, distance from the axis
    knob_cap: float = 2.0
    knob_bore_clearance: float = 0.2
    encoder_press_travel: float = 0.5

    display_thickness: float = 2.9  # MEASURE: nice!view module, PCB bottom to glass top
    display_glass: tuple[float, float] = (30.0, 13.6)  # MEASURE: LCD glass on the module, length and width
    display_board_thickness: float = 1.0  # MEASURE: the module's own PCB
    lens: tuple[float, float, float] = (39.0, 14.6, 1.0)  # guess: clear cast acrylic, length, width, thickness
    lens_corner_radius: float = 2.0
    lens_fit: float = 0.1  # the recess is this much larger than the lens on every side
    lens_tape: float = 0.13  # guess: double-sided tape between the lens and its two ledges
    lens_recess_depth: float = 1.15  # leaves the lens 0.02 under the top face
    lens_opening_length: float = 37.0  # through opening over the whole display module, between the two ledges
    lens_rib: tuple[float, float] = (3.6, 0.65)  # width, height of the rib under each ledge
    lens_rib_past_recess: float = 1.0  # how far a rib reaches beyond the end of the recess

    usb_body: tuple[float, float] = (8.94, 7.35)  # receptacle width, depth
    usb_plug: tuple[float, float] = (12.5, 6.5)  # plug overmould width, height
    usb_margin: float = 0.25
    usb_mouth_chamfer: float = 0.5

    button_hole_diameter: float = 2.5
    button_body: tuple[float, float] = (5.1, 1.5)  # tact switch width, height
    foot_strip: tuple[float, float] = (7.0, 1.6)  # guess: printed TPU or cut from sheet; width, thickness
    centre_pad_thickness: float = 1.4  # lower than the strips, so the pad never makes the case rock
    foot_recess_depth: float = 0.6
    foot_recess_fit: float = 0.2  # a recess is this much larger than its strip on every side
    label_field: tuple[float, float, float] = (60.0, 8.0, 3.0)  # length, width, corner radius
    label_field_centre: float = 32.4  # board Y: between the button legends and the centre pad
    label_field_depth: float = 0.4
    engraving_depth: float = 0.4
    tilt_angle: float = 6.0  # degrees, with the optional tilt bar in the back strip recess
    tilt_bar_front: float = 8.7  # board Y of the bar's front face
    tilt_hole_diameter: float = 5.6  # through the bar, over each back corner screw
    # The bar's tongue in the base's back strip recess: play per side, height, and how far it stays
    # from the cone mouth of each corner screw (a tongue round the holes would be a 0.75 mm ring).
    tilt_tongue: tuple[float, float, float] = (0.15, 0.5, 1.0)

    led_body: tuple[float, float, float] = (4.0, 1.6, 1.6)  # MEASURE: along the edge, depth, height
    led_window_margin: float = 1.0
    led_sill: float = 1.0  # floor of the light channel above the cavity floor
    light_channel_reach: float = 1.7  # from the cavity wall into the side wall; the rest is the outer skin
    light_channel_radius: float = 1.5  # outer plan corners of the channel and of the light bar
    diffuser_fit: float = 0.15
    diffuser_inner_face: float = 0.1  # the bar ends this far inside the cavity wall, in front of the LEDs
    diffuser_to_pcb: float = 0.05

    socket_box: tuple[float, float, float, float] = (-8.4, 7.2, -6.9, -0.5)  # hot-swap socket, from key centre
    switch_post: tuple[float, float] = (4.0, 3.3)  # MX centre post diameter, length below the PCB top

    max_bridge: float = 15.0  # longest unsupported span accepted by the printability check
    max_cantilever: float = 1.5  # deepest ledge that may hang from one side. A guess: about three 0.45 mm lines

    @property
    def side_wall(self) -> float:
        return self.wall


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
    gap_bottom: float
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
    counterbore_top: float
    foot_recess_roof: float
    lens_seat: float
    lens_bottom: float
    lens_top: float
    lens_rib_bottom: float


def levels() -> Levels:
    stack = BOARD.stack
    pcb_bottom = -BOARD.board.thickness
    floor_top = pcb_bottom - stack.underside_clearance
    floor_bottom = floor_top - CASE.floor
    deck_bottom = stack.deck_top - stack.plate_thickness
    lens_seat = stack.deck_top - CASE.lens_recess_depth
    return Levels(
        pcb_bottom=pcb_bottom,
        floor_top=floor_top,
        floor_bottom=floor_bottom,
        gap_bottom=-CASE.gap_height,
        plate_top=stack.plate_top,
        plate_bottom=stack.plate_top - stack.plate_thickness,
        deck_top=stack.deck_top,
        deck_bottom=deck_bottom,
        usb_centre=pcb_bottom - BOARD.usb.body_height / 2,
        led_slot_bottom=floor_top + CASE.led_sill,
        boss_root_top=floor_top + CASE.boss_root_height,
        rib_bottom=CASE.rib_to_pcb,
        knob_well_floor=stack.deck_top - CASE.knob_well_depth,
        knob_bottom=stack.deck_top - CASE.knob_well_depth + CASE.knob_to_deck,
        knob_top=stack.encoder_shaft_top + CASE.knob_cap,
        bushing_top=stack.encoder_body_top + CASE.bushing_length,
        counterbore_top=floor_bottom + CASE.counterbore_depth,
        foot_recess_roof=floor_bottom + CASE.foot_recess_depth,
        lens_seat=lens_seat,
        lens_bottom=lens_seat + CASE.lens_tape,
        lens_top=lens_seat + CASE.lens_tape + CASE.lens[2],
        lens_rib_bottom=deck_bottom - CASE.lens_rib[1],
    )


LEVELS = levels()
Span = tuple[tuple[float, float], tuple[float, float]]  # board X range, board Y range


def grown(span: Span, amount: float) -> Span:
    (x_low, x_high), (y_low, y_high) = span
    return (x_low - amount, x_high + amount), (y_low - amount, y_high + amount)


def case_bounds() -> Span:
    """The case seen from above, without its rounded corners."""
    side = CASE.side_wall + CASE.pcb_gap
    return (
        (-side, BOARD.board.width + side),
        (-CASE.back_wall - CASE.pcb_gap, BOARD.board.height + CASE.pcb_gap + CASE.front_wall),
    )


def dish_floor() -> Span:
    """The flat floor of the key dish, on the plate: the outer key centres and a margin."""
    xs, ys = zip(*key_centres())
    return grown(((min(xs), max(xs)), (min(ys), max(ys))), CASE.dish_floor_margin)


def dish_rim() -> Span:
    """Where the 45 degree wall of the dish meets the top face."""
    return grown(dish_floor(), LEVELS.deck_top - LEVELS.plate_top)


def deck_pocket_front() -> float:
    """Board Y of the front wall of the pocket under the deck. The dish wall leans back over it."""
    dish_wall_at_deck_skin = dish_floor()[1][0] - (LEVELS.deck_bottom - LEVELS.plate_top)
    return dish_wall_at_deck_skin - CASE.deck_front_wall


def lens_recess() -> Span:
    display = BOARD.display
    half_length, half_width = CASE.lens[0] / 2 + CASE.lens_fit, CASE.lens[1] / 2 + CASE.lens_fit
    return (display.x - half_length, display.x + half_length), (display.y - half_width, display.y + half_width)


def lens_opening() -> Span:
    """The through opening under the lens. It is as wide as the recess, so the lens rests on two end ledges."""
    half_length = CASE.lens_opening_length / 2
    return (BOARD.display.x - half_length, BOARD.display.x + half_length), lens_recess()[1]


def lens_rib_spans() -> list[tuple[float, float]]:
    """Board X range of the rib under each lens ledge, left then right."""
    (recess_start, recess_end), _ = lens_recess()
    width, past = CASE.lens_rib[0], CASE.lens_rib_past_recess
    return [(recess_start - past, recess_start - past + width), (recess_end + past - width, recess_end + past)]


def led_slot_span() -> tuple[float, float]:
    """Board Y range of the light channel: every LED body plus a margin."""
    led_centres = BOARD.leds.left_y + BOARD.leds.right_y
    half_led = CASE.led_body[0] / 2
    return (min(led_centres) - half_led - CASE.led_window_margin, max(led_centres) + half_led + CASE.led_window_margin)


def lap_runs() -> list[tuple[str, float, float]]:
    """Where the lap ridges run: (wall, start, end) along that wall in board coordinates. They leave out
    the corners, the USB opening and the light channels."""
    inset = CASE.lap_corner_inset
    width, height = BOARD.board.width, BOARD.board.height
    usb_half = CASE.usb_plug[0] / 2 + CASE.usb_margin + CASE.usb_mouth_chamfer + 1.0
    side_end = led_slot_span()[0] - CASE.light_channel_radius - CASE.lap_end_room
    return [
        ("back", inset, BOARD.usb.x - usb_half), ("back", BOARD.usb.x + usb_half, width - inset),
        ("front", inset, width - inset), ("left", inset, side_end), ("right", inset, side_end),
    ]


def rib_lines() -> list[float]:
    """Board Y of each plate rib: halfway between two key rows."""
    keys = BOARD.keys
    return [keys.first_y + (row + 0.5) * keys.pitch for row in range(keys.rows - 1)]


BACK_ROW, CENTRE_ROW, FRONT_ROW = "back", "centre", "front"


def screw_rows() -> dict[str, list[tuple[float, float]]]:
    """The screws in the three groups that share a foot: back corners, centre, front corners."""
    holes = mounting_holes()
    back, front = min(y for _, y in holes), max(y for _, y in holes)
    return {
        BACK_ROW: [hole for hole in holes if hole[1] == back],
        CENTRE_ROW: [hole for hole in holes if back < hole[1] < front],
        FRONT_ROW: [hole for hole in holes if hole[1] == front],
    }


def foot_span(row: str) -> Span:
    """Footprint of the foot over one row of screws: a stadium whose ends are concentric with them."""
    xs, ys = zip(*screw_rows()[row])
    return grown(((min(xs), max(xs)), (min(ys), max(ys))), CASE.foot_strip[0] / 2)


def foot_thickness(row: str) -> float:
    return CASE.centre_pad_thickness if row == CENTRE_ROW else CASE.foot_strip[1]


def label_field() -> Span:
    length, width, _ = CASE.label_field
    middle_x, middle_y = BOARD.board.width / 2, CASE.label_field_centre
    return (middle_x - length / 2, middle_x + length / 2), (middle_y - width / 2, middle_y + width / 2)


def buttons() -> dict[str, tuple[float, float]]:
    return {name: (button.x, button.y) for name, button in vars(BOARD.buttons).items()}
