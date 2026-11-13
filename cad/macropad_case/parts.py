"""The case body, base and top, each in its assembled position.

Both are built the way a mill would cut them: an outline slab with chamfered edges, then pockets
level by level. The print variant adds what only a printer can make (45 degree fillers, engraved text).
"""

from math import sqrt

from build123d import Align, Circle, Cone, Part, Plane, Polygon, Pos, Rectangle, RectangleRounded, Sketch, extrude

from . import signature
from .solids import CUT_OVERSHOOT, box, case_outline, chamfered_slab, cylinder, discs, legend, millable, pcb_outline
from .solids import rectangle, rounded_rectangle, slab, stadium
from .spec import BOARD, CASE, CNC, LEVELS, PRINT, buttons, case_bounds, deck_pocket_front, dish_floor
from .spec import encoder_centres, foot_span, grown, key_centres, label_field, lap_runs, led_slot_span, lens_opening
from .spec import lens_recess, lens_rib_spans, mounting_holes, rib_lines, screw_rows

FAR = 500.0
WIDTH = BOARD.board.width
HEIGHT = BOARD.board.height
WORDMARK = "macropad"
WORDMARK_SIZE = 2.6
LEGEND_SIZE = 3.4
UNDERSIDE_MARK = "worxbend / macropad"
UNDERSIDE_MARK_SIZE = 3.6


def base(variant: str) -> Part:
    body = base_body(variant)
    if variant == CNC:
        # Milled only. Printed underside down, the groove's roof is one winding overhang that the
        # printability check counts as a 24 mm span.
        under_signature = (LEVELS.floor_bottom - CUT_OVERSHOOT, LEVELS.floor_bottom + signature.GROOVE_DEPTH)
        body -= slab(signature.artwork(), under_signature)
    if variant == PRINT:
        under = LEVELS.floor_bottom - CUT_OVERSHOOT
        body -= slab(button_legends(), (under, LEVELS.floor_bottom + CASE.engraving_depth))
        # The mark stands in its field, flush with the underside. Sunk into the field's roof it would
        # be holes in a bridge, which do not print.
        body += slab(underside_mark(), (LEVELS.floor_bottom, LEVELS.floor_bottom + CASE.label_field_depth + CUT_OVERSHOOT))
    return body


def base_body(variant: str) -> Part:
    """The base before any text is engraved."""
    body = _base_blank(variant)
    cavity = pcb_outline(CASE.pcb_gap)
    pockets = [
        (cavity, (LEVELS.pcb_bottom, CUT_OVERSHOOT)),
        (cavity - discs(mounting_holes(), CASE.base_boss_diameter), (LEVELS.boss_root_top, LEVELS.pcb_bottom)),
        (cavity - discs(mounting_holes(), CASE.boss_root_diameter), (LEVELS.floor_top, LEVELS.boss_root_top)),
    ]
    # One boolean for every pocket: cut one at a time, the 0.01 mm overlaps between levels upset OCCT.
    body -= [slab(millable(pocket, variant), (bottom, top + CUT_OVERSHOOT)) for pocket, (bottom, top) in pockets]
    return body + lap_ridges() - _base_cuts()


def _base_blank(variant: str) -> Part:
    """The outside of the base: the full outline up to the gap, then a rim set back by the gap depth.
    The two shells meet at the back of that gap, so the joint is a shadow line and not a seam."""
    skin = chamfered_slab(
        case_outline(variant), (LEVELS.floor_bottom, LEVELS.gap_bottom), bottom=CASE.underside_chamfer,
        top=CASE.seam_chamfer,
    )
    rim = chamfered_slab(case_outline(variant, -CASE.gap_depth), (LEVELS.gap_bottom, 0), bottom=0, top=CASE.seam_chamfer)
    return skin + rim


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
        cylinder(hole, CASE.counterbore_diameter, (under, LEVELS.counterbore_top)) for hole in mounting_holes()
    ]
    button_holes = [
        cylinder(centre, CASE.button_hole_diameter, (under, LEVELS.floor_top + CUT_OVERSHOOT))
        for centre in buttons().values()
    ]
    foot_recesses = [
        slab(stadium(grown(foot_span(row), CASE.foot_recess_fit)), (under, LEVELS.foot_recess_roof)) for row in screw_rows()
    ]
    field = slab(label_field_outline(), (under, LEVELS.floor_bottom + CASE.label_field_depth))
    light_channels = [_light_channel(left=True), _light_channel(left=False)]
    return [usb_cutout(), field] + light_channels + screw_holes + counterbores + _screw_cones() + button_holes + foot_recesses


def _screw_cones() -> list[Part]:
    """A 45 degree cone from the roof of each foot recess up to the counterbore. Without it the roof is
    a bridge with a hole in it, which does not print; a chamfer mill cuts the cone in the CNC variant."""
    wide, narrow = (diameter / 2 for diameter in CASE.screw_cone)
    cone = Cone(wide, narrow, wide - narrow, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return [Pos(x, -y, LEVELS.foot_recess_roof - CUT_OVERSHOOT) * cone for x, y in mounting_holes()]


def label_field_outline() -> Sketch:
    return rounded_rectangle(label_field(), CASE.label_field[2])


def button_legends() -> Sketch:
    """A name beside each button hole, drawn as seen from above."""
    label_offset = CASE.button_hole_diameter / 2 + LEGEND_SIZE / 2 + 1.2
    labels = [
        legend(name.upper(), LEGEND_SIZE, (x, y + label_offset), read_from_below=True)
        for name, (x, y) in buttons().items()
    ]
    return Sketch() + labels


def underside_mark() -> Sketch:
    """The mark in the middle of the label field, drawn as seen from above."""
    (x_low, x_high), (y_low, y_high) = label_field()
    return legend(UNDERSIDE_MARK, UNDERSIDE_MARK_SIZE, ((x_low + x_high) / 2, (y_low + y_high) / 2), read_from_below=True)


def underside_artwork() -> Sketch:
    """Everything engraved in the floor."""
    return button_legends() + underside_mark() + signature.artwork()


def usb_cutout() -> Part:
    """Opening for the plug overmould, with a 45 degree lead-in on the outside. It is taller than
    the base wall above the receptacle, so the base and the top both take a bite of it."""
    width = CASE.usb_plug[0] + 2 * CASE.usb_margin
    height = CASE.usb_plug[1] + 2 * CASE.usb_margin
    back_face = case_bounds()[1][0]
    # The tunnel floor is a little lower than the case floor. Its inner end is rounded like a milled
    # pocket, so that shallow step has no sharp corner; the rounding starts past the plug.
    radius = CASE.cnc_corner_radius
    plan = rectangle((BOARD.usb.x - width / 2, BOARD.usb.x + width / 2), (back_face - 2 * radius, radius))
    tunnel = slab(millable(plan, CNC), (LEVELS.usb_centre - height / 2, LEVELS.usb_centre + height / 2))
    flare = CASE.usb_mouth_chamfer
    outer_wall_face = Plane.XZ.offset(back_face - CUT_OVERSHOOT)  # its normal points into the case
    mouth = Pos(BOARD.usb.x, 0, LEVELS.usb_centre) * outer_wall_face * Rectangle(width + 2 * flare, height + 2 * flare)
    return tunnel + extrude(mouth, flare, taper=45)


def _light_channel(left: bool) -> Part:
    """Open-topped channel for a light bar, cut into a side wall from the cavity. Below the gap the
    outer skin of the wall stays and the channel is a rounded pocket whose inner corners lie in the
    cavity, so the same shape prints and mills. In the gap the rim is cut straight through: that slot
    is where the bar shows. A rounded end there would leave a feather edge on the rim."""
    outer = CASE.pcb_gap + CASE.light_channel_reach
    inner = CASE.light_channel_radius
    x_range = (-outer, inner) if left else (WIDTH - inner, WIDTH + outer)
    plan = rounded_rectangle((x_range, led_slot_span()), CASE.light_channel_radius)
    pocket = slab(plan, (LEVELS.led_slot_bottom, LEVELS.gap_bottom))
    past_the_rim = CASE.gap_depth + CUT_OVERSHOOT
    slot_x = (x_range[0] - past_the_rim, x_range[1]) if left else (x_range[0], x_range[1] + past_the_rim)
    return pocket + box(slot_x, led_slot_span(), (LEVELS.gap_bottom, CUT_OVERSHOOT))


def top(variant: str) -> Part:
    body = top_body(variant)
    if variant == PRINT:
        body -= slab(deck_artwork(), (LEVELS.deck_top - CASE.engraving_depth, LEVELS.deck_top + CUT_OVERSHOOT))
    return body


def top_body(variant: str) -> Part:
    """The top before any text is engraved."""
    # The dish goes first and the pockets go in one boolean: in any other order OCCT returns the
    # CNC top in pieces.
    body = _top_blank(variant) - key_dish()
    body -= [slab(millable(pocket, variant), z_range) for pocket, z_range in _top_pockets(variant)]
    if variant == PRINT:
        body += _print_gussets() + _print_boss_webs() + _print_lens_fillers()
    pilot_holes = [
        cylinder(hole, CASE.pilot_diameter, (-CUT_OVERSHOOT, CASE.pilot_depth)) for hole in mounting_holes()
    ]
    return body - pilot_holes - usb_cutout() - lap_grooves()


def _top_blank(variant: str) -> Part:
    """One flat slab from the joint to the top face."""
    return chamfered_slab(case_outline(variant), (0, LEVELS.deck_top), bottom=CASE.seam_chamfer, top=CASE.chamfer)


def key_dish() -> Part:
    """What is cut away for the keys: a flat floor on the plate and 45 degree walls up to the top
    face. The walls print without support when the top stands on its side, and a chamfer mill cuts them."""
    floor = rounded_rectangle(dish_floor(), CASE.dish_floor_radius)
    depth = LEVELS.deck_top - LEVELS.plate_top
    return Pos(0, 0, LEVELS.plate_top) * extrude(floor, depth + CUT_OVERSHOOT, taper=-45)


def _top_pockets(variant: str) -> list[tuple[Sketch, tuple[float, float]]]:
    """Every pocket of the top as (outline, Z range), lowest first. Levels that stand on each other
    meet exactly; a pocket runs past a face only where it opens it."""
    cavity = pcb_outline(CASE.pcb_gap) - discs(mounting_holes(), CASE.top_boss_diameter)
    under_the_deck = cavity & rectangle((-FAR, FAR), (-FAR, deck_pocket_front()))
    lens_ribs = Sketch() + [rectangle(span, (-FAR, FAR)) for span in lens_rib_spans()]
    bushing_hole = BOARD.stack.encoder_bushing_diameter + CASE.bushing_clearance
    above = LEVELS.deck_top + CUT_OVERSHOOT
    return [
        (cavity, (-CUT_OVERSHOOT, LEVELS.rib_bottom)),
        (cavity - _ribs(), (LEVELS.rib_bottom, LEVELS.plate_bottom)),
        (under_the_deck, (LEVELS.plate_bottom, LEVELS.lens_rib_bottom)),
        (under_the_deck - lens_ribs, (LEVELS.lens_rib_bottom, LEVELS.deck_bottom)),
        (_switch_cutouts(variant), (LEVELS.plate_bottom, LEVELS.plate_top + CUT_OVERSHOOT)),
        (rectangle(*lens_opening()), (LEVELS.lens_rib_bottom, above)),
        (lens_recess_outline(), (LEVELS.lens_seat, above)),
        (discs(encoder_centres(), bushing_hole), (LEVELS.deck_bottom, above)),
    ]


def lens_recess_outline() -> Sketch:
    return rounded_rectangle(lens_recess(), CASE.lens_corner_radius + CASE.lens_fit)


def _ribs() -> Sketch:
    """Ribs under the plate between the key rows. They run left to right, so they are vertical
    when the top prints standing on its side wall, and they pass through the two centre bosses."""
    half = CASE.rib_width / 2
    return Sketch() + [rectangle((-FAR, FAR), (line - half, line + half)) for line in rib_lines()]


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
    """The wordmark on the top face, between the back edge and the lens."""
    back_edge = case_bounds()[1][0] + CASE.chamfer
    lens_back = lens_recess()[1][0]
    return legend(WORDMARK, WORDMARK_SIZE, (WIDTH / 2, (back_edge + lens_back) / 2))


def _print_gussets() -> list[Part]:
    """45 degree fillers under the side walls. The top prints standing on one side wall,
    so without them the other side wall would start in mid-air."""
    back, front = -CASE.pcb_gap, HEIGHT + CASE.pcb_gap
    gussets = []
    for wall_x, inward in ((-CASE.pcb_gap, 1), (WIDTH + CASE.pcb_gap, -1)):
        gussets.append(_gusset((wall_x, LEVELS.plate_bottom), inward * LEVELS.plate_bottom, (back, front)))
        gussets.append(_gusset((wall_x, LEVELS.deck_bottom), inward * LEVELS.deck_bottom, (back, deck_pocket_front())))
    return gussets


def _print_lens_fillers() -> list[Part]:
    """A 45 degree filler on the side of each lens rib that faces the bed. Without it that side is a
    ledge as long as the deck pocket is deep."""
    height = CASE.lens_rib[1]
    y_range = (-CASE.pcb_gap, deck_pocket_front())
    through = slab(rectangle(*lens_opening()), (LEVELS.lens_rib_bottom - CUT_OVERSHOOT, LEVELS.deck_bottom + CUT_OVERSHOOT))
    return [_gusset((rib_start, LEVELS.deck_bottom), -height, y_range) - through for rib_start, _ in lens_rib_spans()]


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
            webs.append(_gusset((x - radius, LEVELS.rib_bottom), -LEVELS.rib_bottom, fin_y))
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
    ceiling = LEVELS.deck_bottom if y < deck_pocket_front() else LEVELS.plate_bottom
    return extrude(web, ceiling, dir=(0, 0, 1))  # the outline may run either way round; the direction is fixed here


def _gusset(corner: tuple[float, float], signed_leg: float, y_range: tuple[float, float]) -> Part:
    """A triangular filler along Y. `corner` is its right angle as (X, Z): one leg goes straight down
    from there, the other goes level, toward +X or -X by the sign of `signed_leg`."""
    wall_x, ceiling = corner
    profile = Plane.XZ * Polygon(
        (wall_x, ceiling - abs(signed_leg)), (wall_x, ceiling), (wall_x + signed_leg, ceiling), align=None
    )
    toward_front = (0, -1, 0)
    return Pos(0, -y_range[0], 0) * extrude(profile, y_range[1] - y_range[0], dir=toward_front)
