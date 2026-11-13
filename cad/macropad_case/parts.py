"""The case body, base and top, each in its assembled position.

Both are built the way a mill would cut them: an outline slab with chamfered edges, then pockets
level by level. The print variant adds what only a printer can make (45 degree fillers, engraved text).
"""

from math import sqrt

from build123d import Circle, Part, Plane, Polygon, Pos, Rectangle, RectangleRounded, Sketch, extrude

from .solids import CUT_OVERSHOOT, box, centred_rectangle, chamfered_slab, cylinder, discs, flared_cut, legend
from .solids import millable, pcb_outline, rectangle, slab
from .spec import BOARD, CASE, CNC, LEVELS, PRINT, buttons, deck_front, encoder_centres, foot_centres
from .spec import key_centres, lap_runs, led_slot_span, mounting_holes, rib_lines

OUTER = CASE.wall + CASE.pcb_gap
FAR = 500.0
WIDTH = BOARD.board.width
HEIGHT = BOARD.board.height
WORDMARK = "macropad"
WORDMARK_SIZE = 3.6
LEGEND_SIZE = 3.4
UNDERSIDE_MARK = "worxbend / macropad"
UNDERSIDE_MARK_SIZE = 4.2


def base(variant: str) -> Part:
    body = base_body(variant)
    if variant == PRINT:
        body -= slab(underside_artwork(), (LEVELS.floor_bottom - CUT_OVERSHOOT, LEVELS.floor_bottom + CASE.engraving_depth))
    return body


def base_body(variant: str) -> Part:
    """The base before any text is engraved."""
    body = chamfered_slab(pcb_outline(OUTER), (LEVELS.floor_bottom, 0), bottom=CASE.chamfer, top=CASE.seam_chamfer)
    cavity = pcb_outline(CASE.pcb_gap)
    pockets = [
        (cavity, (LEVELS.pcb_bottom, CUT_OVERSHOOT)),
        (cavity - discs(mounting_holes(), CASE.base_boss_diameter), (LEVELS.boss_root_top, LEVELS.pcb_bottom)),
        (cavity - discs(mounting_holes(), CASE.boss_root_diameter), (LEVELS.floor_top, LEVELS.boss_root_top)),
    ]
    # One boolean for every pocket: cut one at a time, the 0.01 mm overlaps between levels upset OCCT.
    body -= [slab(millable(pocket, variant), (bottom, top + CUT_OVERSHOOT)) for pocket, (bottom, top) in pockets]
    return body + lap_ridges() - _base_cuts()


def lap_ridges() -> Part:
    """The ridges on the base rim. Each one's inner face continues the cavity wall; its outer flank
    and its two ends fall at 45 degrees."""
    reach = CASE.lap_crest + CASE.lap_height
    wedges = [
        extrude(rectangle(*_lap_footprint(run, outward=reach, along=0.0)), CASE.lap_height, taper=45)
        for run in lap_runs()
    ]
    return Part() + wedges - slab(pcb_outline(CASE.pcb_gap), (-1, CASE.lap_height + 1))


def lap_grooves() -> list[Part]:
    """What the ridges enter in the top's skirt: pockets with a 45 degree outer wall (a chamfer mill
    cuts it), open toward the cavity so a flat end mill clears the rest."""
    depth = CASE.lap_height + CASE.lap_fit
    reach = CASE.lap_crest + depth
    radius = CASE.cnc_corner_radius + depth  # the taper takes `depth` off it again at the groove's roof
    grooves = []
    for run in lap_runs():
        (x_low, x_high), (y_low, y_high) = _lap_footprint(run, outward=reach, along=CASE.lap_end_room)
        footprint = Pos((x_low + x_high) / 2, -(y_low + y_high) / 2) * RectangleRounded(
            x_high - x_low, y_high - y_low, radius
        )
        grooves.append(Pos(0, 0, -CUT_OVERSHOOT) * extrude(footprint, depth + CUT_OVERSHOOT, taper=45))
    return grooves


def _lap_footprint(run: tuple[str, float, float], outward: float, along: float) -> tuple[tuple, tuple]:
    """Board X and Y range of one lap run: `outward` past the cavity wall into the case wall, the
    groove reach into the cavity, and `along` past each end."""
    wall, start, end = run
    gap, inward = CASE.pcb_gap, CASE.lap_groove_reach
    span = (start - along, end + along)
    across = {
        "back": (-gap - outward, -gap + inward), "front": (HEIGHT + gap - inward, HEIGHT + gap + outward),
        "left": (-gap - outward, -gap + inward), "right": (WIDTH + gap - inward, WIDTH + gap + outward),
    }[wall]
    return (span, across) if wall in ("back", "front") else (across, span)


def _base_cuts() -> list[Part]:
    under = LEVELS.floor_bottom - CUT_OVERSHOOT
    screw_holes = [cylinder(hole, BOARD.mounting.hole_diameter, (under, 0)) for hole in mounting_holes()]
    counterbores = [
        cylinder(hole, CASE.counterbore_diameter, (under, LEVELS.floor_bottom + CASE.counterbore_depth))
        for hole in mounting_holes()
    ]
    button_holes = [
        cylinder(centre, CASE.button_hole_diameter, (under, LEVELS.floor_top + CUT_OVERSHOOT))
        for centre in buttons().values()
    ]
    feet = [
        cylinder(centre, CASE.foot_diameter, (under, LEVELS.floor_bottom + CASE.foot_depth))
        for centre in foot_centres()
    ]
    return [usb_cutout(), _led_slot(left=True), _led_slot(left=False)] + screw_holes + counterbores + button_holes + feet


def underside_artwork() -> Sketch:
    """What is engraved in the floor, drawn as seen from above: a name for each button hole and the mark."""
    label_offset = CASE.button_hole_diameter / 2 + LEGEND_SIZE / 2 + 1.2
    labels = [
        legend(name.upper(), LEGEND_SIZE, (x, y + label_offset), read_from_below=True)
        for name, (x, y) in buttons().items()
    ]
    first_rib, second_rib = rib_lines()[:2]
    mark = legend(UNDERSIDE_MARK, UNDERSIDE_MARK_SIZE, (WIDTH / 2, (first_rib + second_rib) / 2), read_from_below=True)
    return Sketch() + labels + mark


def usb_cutout() -> Part:
    """Opening for the plug overmould, with a 45 degree lead-in on the outside. It is taller than
    the base wall above the receptacle, so the base and the top both take a bite of it."""
    width = CASE.usb_plug[0] + 2 * CASE.usb_margin
    height = CASE.usb_plug[1] + 2 * CASE.usb_margin
    # The tunnel floor is a little lower than the case floor. Its inner end is rounded like a milled
    # pocket, so that shallow step has no sharp corner; the rounding starts past the plug.
    radius = CASE.cnc_corner_radius
    plan = rectangle((BOARD.usb.x - width / 2, BOARD.usb.x + width / 2), (-OUTER - 2 * radius, radius))
    tunnel = slab(millable(plan, CNC), (LEVELS.usb_centre - height / 2, LEVELS.usb_centre + height / 2))
    flare = CASE.usb_mouth_chamfer
    outer_wall_face = Plane.XZ.offset(-OUTER - CUT_OVERSHOOT)  # its normal points into the case
    mouth = Pos(BOARD.usb.x, 0, LEVELS.usb_centre) * outer_wall_face * Rectangle(width + 2 * flare, height + 2 * flare)
    return tunnel + extrude(mouth, flare, taper=45)


def _led_slot(left: bool) -> Part:
    """Open-topped slot through a side wall: the top's skirt closes it, so it prints without a bridge."""
    x_range = (-OUTER - 1, 0) if left else (WIDTH, WIDTH + OUTER + 1)
    return box(x_range, led_slot_span(), (LEVELS.led_slot_bottom, CUT_OVERSHOOT))


def top(variant: str) -> Part:
    body = top_body(variant)
    if variant == PRINT:
        body -= slab(deck_artwork(), (LEVELS.plate_top - CASE.engraving_depth, LEVELS.plate_top + CUT_OVERSHOOT))
    return body


def top_body(variant: str) -> Part:
    """The top before any text is engraved."""
    body = _top_blank()
    body -= [slab(millable(pocket, variant), z_range) for pocket, z_range in _top_pockets(variant)]
    body -= flared_cut(millable(_display_window(), variant), LEVELS.deck_top, CASE.bezel_chamfer)
    if variant == PRINT:
        body += _print_gussets() + _print_boss_webs()
    pilot_holes = [
        cylinder(hole, CASE.pilot_diameter, (-CUT_OVERSHOOT, CASE.pilot_depth)) for hole in mounting_holes()
    ]
    return body - pilot_holes - usb_cutout() - lap_grooves()


def _top_blank() -> Part:
    """Key plate level all over, plus the raised deck at the back. Each has its own chamfered rim."""
    outline = pcb_outline(OUTER)
    plate_level = chamfered_slab(outline, (0, LEVELS.plate_top), bottom=CASE.seam_chamfer, top=CASE.chamfer)
    behind_the_keys = rectangle((-FAR, FAR), (-FAR, deck_front()))
    deck = chamfered_slab(outline & behind_the_keys, (LEVELS.plate_bottom, LEVELS.deck_top), bottom=0, top=CASE.chamfer)
    return plate_level + deck


def _top_pockets(variant: str) -> list[tuple[Sketch, tuple[float, float]]]:
    """Every pocket of the top as (outline, Z range), lowest first."""
    cavity = pcb_outline(CASE.pcb_gap) - discs(mounting_holes(), CASE.top_boss_diameter)
    deck_zone = rectangle((-FAR, FAR), (-FAR, deck_front() - CASE.deck_front_wall))
    knob_well = CASE.knob_diameter + 2 * CASE.knob_well_margin
    bushing_hole = BOARD.stack.encoder_bushing_diameter + CASE.bushing_clearance
    return [
        (cavity, (-CUT_OVERSHOOT, LEVELS.rib_bottom)),
        (cavity - _ribs(), (LEVELS.rib_bottom - CUT_OVERSHOOT, LEVELS.plate_bottom)),
        (cavity & deck_zone, (LEVELS.plate_bottom - CUT_OVERSHOOT, LEVELS.deck_bottom)),
        (_display_relief(), (LEVELS.deck_bottom - CUT_OVERSHOOT, LEVELS.deck_bottom + CASE.display_relief)),
        (_switch_cutouts(variant), (LEVELS.plate_bottom - CUT_OVERSHOOT, LEVELS.plate_top + CUT_OVERSHOOT)),
        (_display_window(), (LEVELS.deck_bottom - CUT_OVERSHOOT, LEVELS.deck_top + CUT_OVERSHOOT)),
        (discs(encoder_centres(), bushing_hole), (LEVELS.deck_bottom - CUT_OVERSHOOT, LEVELS.deck_top + CUT_OVERSHOOT)),
        (discs(encoder_centres(), knob_well), (LEVELS.knob_well_floor, LEVELS.deck_top + CUT_OVERSHOOT)),
    ]


def _ribs() -> Sketch:
    """Ribs under the plate between the key rows. They run left to right, so they are vertical
    when the top prints standing on its side wall, and they pass through the two centre bosses."""
    half = CASE.rib_width / 2
    return Sketch() + [rectangle((-FAR, FAR), (line - half, line + half)) for line in rib_lines()]


def _display_relief() -> Sketch:
    display = BOARD.display
    margin = 2 * CASE.display_relief_margin
    return centred_rectangle((display.x, display.y), (display.length + margin, display.width + margin))


def _display_window() -> Sketch:
    display = BOARD.display
    return centred_rectangle((display.window_x, display.window_y), (display.window_length, display.window_width))


def _switch_cutouts(variant: str) -> Sketch:
    side = BOARD.stack.switch_cutout
    cutout = Rectangle(side, side)
    if variant == CNC:
        cutout += _dog_bones(side)
    return Sketch() + [Pos(x, -y) * cutout for x, y in key_centres()]


def _dog_bones(side: float) -> list[Sketch]:
    """Corner reliefs: a round tool cannot cut the square corner an MX switch needs."""
    radius = CASE.cnc_corner_radius
    centre = side / 2 - radius / sqrt(2)
    return [Pos(sign_x * centre, sign_y * centre) * Circle(radius) for sign_x in (-1, 1) for sign_y in (-1, 1)]


def deck_artwork() -> Sketch:
    """The wordmark on the front lip of the plate, in front of the bottom key row."""
    last_row = BOARD.keys.first_y + (BOARD.keys.rows - 1) * BOARD.keys.pitch
    keycap_front = last_row + CASE.keycap_width / 2
    lip_front = HEIGHT + OUTER - CASE.chamfer
    return legend(WORDMARK, WORDMARK_SIZE, (WIDTH / 2, (keycap_front + lip_front) / 2))


def _print_gussets() -> list[Part]:
    """45 degree fillers under the side walls. The top prints standing on one side wall,
    so without them the other side wall would start in mid-air."""
    back, front = -CASE.pcb_gap, HEIGHT + CASE.pcb_gap
    deck_back_of_wall = deck_front() - CASE.deck_front_wall
    gussets = []
    for wall_x, inward in ((-CASE.pcb_gap, 1), (WIDTH + CASE.pcb_gap, -1)):
        gussets.append(_gusset(wall_x, inward * LEVELS.plate_bottom, (back, front)))
        gussets.append(_gusset(wall_x, inward * LEVELS.deck_bottom, (back, deck_back_of_wall)))
    return gussets


def _print_boss_webs() -> list[Part]:
    """What carries the screw bosses while the top prints on its left side wall. Without it each boss
    is a cylinder that sticks out of the plate sideways. A corner boss gets a web to the back or front
    wall with a 45 degree underside; a centre boss stands on a rib and only needs a fin below the rib."""
    radius = CASE.top_boss_diameter / 2
    webs = []
    for x, y in mounting_holes():
        on_a_rib = any(abs(y - line) < CASE.rib_width / 2 for line in rib_lines())
        if on_a_rib:
            fin_y = (y - CASE.rib_width / 2, y + CASE.rib_width / 2)
            webs.append(_gusset(x - radius, -LEVELS.rib_bottom, fin_y))
        else:
            webs.append(_corner_boss_web((x, y), radius))
    return webs


def _corner_boss_web(boss: tuple[float, float], radius: float) -> Part:
    x, y = boss
    at_the_back = y < HEIGHT / 2
    wall_y = -CASE.pcb_gap if at_the_back else HEIGHT + CASE.pcb_gap
    away_from_wall = 1 if at_the_back else -1
    tangent = radius / sqrt(2)  # where the boss's own underside reaches 45 degrees
    touch = (x - tangent, y + away_from_wall * tangent)
    foot = (touch[0] - abs(touch[1] - wall_y), wall_y)
    outline = [foot, touch, (x + radius, y), (x + radius, wall_y)]
    web = Polygon(*[(across, -along) for across, along in outline], align=None) & pcb_outline(CASE.pcb_gap)
    ceiling = LEVELS.deck_bottom if y < deck_front() else LEVELS.plate_bottom
    return extrude(web, ceiling, dir=(0, 0, 1))  # the outline may run either way round; the direction is fixed here


def _gusset(wall_x: float, signed_leg: float, y_range: tuple[float, float]) -> Part:
    leg = abs(signed_leg)
    profile = Plane.XZ * Polygon((wall_x, 0), (wall_x, leg), (wall_x + signed_leg, leg), align=None)
    toward_front = (0, -1, 0)
    return Pos(0, -y_range[0], 0) * extrude(profile, y_range[1] - y_range[0], dir=toward_front)
