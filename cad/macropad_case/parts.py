"""The case body, base and top, each in its assembled position.

Both are built the way a mill would cut them: an outline slab with chamfered edges, then pockets
level by level. The print variant adds what only a printer can make (45 degree fillers, engraved text).
"""

from math import radians, sqrt, tan

from build123d import Align, Axis, Circle, Cone, Part, Plane, Polygon, Pos, Rectangle, RectangleRounded, Sketch
from build123d import extrude, fillet, offset

from . import signature
from .solids import CUT_OVERSHOOT, box, case_outline, chamfered_slab, cylinder, discs, legend, millable, pcb_outline
from .solids import rectangle, rounded_rectangle, slab, stadium
from .spec import BOARD, CASE, CENTRE_ROW, CNC, LEVELS, PRINT, buttons, bushing_hole, case_bounds, deck_pocket_front
from .spec import dish_floor, dish_floor_radius, encoder_centres, foot_span, grown, key_centres, knob_well_diameter
from .spec import label_field, lap_runs, led_slot_span, lens_opening, lens_recess, lens_rib_spans, mounting_holes
from .spec import rib_lines, screw_rows, screw_seat, skin_chamfer, socket_posts, top_boss_diameters, usb_opening_size
from .spec import usb_pad_span

FAR = 500.0
WIDTH = BOARD.board.width
HEIGHT = BOARD.board.height
# The text is engraved into the face that lies on the bed, where the first layer is squeezed into
# every slot. Each glyph is drawn bolder by `*_GROW` on every side, so its thinnest stroke is at least
# 0.7 mm (checked). OCCT fails to offset some glyph outlines by other amounts close to these.
LEGEND_SIZE = 4.4
LEGEND_GROW = 0.05
UNDERSIDE_MARK = "worxbend / macropad"
UNDERSIDE_MARK_SIZE = 5.1
UNDERSIDE_MARK_GROW = 0.145


def base(variant: str) -> Part:
    """The base. The print variant has its text engraved into the face that lies on the bed, and a
    skin across each screw hole; the CNC variant stays plain, to be laser-marked."""
    body = base_body(variant)
    if variant == PRINT:
        engraved = (LEVELS.floor_bottom - CUT_OVERSHOOT, LEVELS.floor_bottom + CASE.engraving_depth)
        body = body + screw_skins() - slab(button_legends() + underside_mark(), engraved)
    return body


def screw_skins() -> list[Part]:
    """Print only: one layer that closes each counterbore at the roof of its foot recess. A hole in
    that roof would be a hole in a bridge. The builder cuts the six skins out, so they are not a wall
    of the finished base."""
    skin = (LEVELS.foot_recess_roof, LEVELS.foot_recess_roof + CASE.screw_skin)
    into_the_wall = CASE.counterbore_diameter + 2 * CUT_OVERSHOOT  # so each skin joins the base, not just touches it
    return [cylinder(hole, into_the_wall, skin) for hole in mounting_holes()]


def base_body(variant: str) -> Part:
    """The finished base before any text is engraved, with its screw holes open."""
    body = _base_blank(variant)
    cavity = pcb_outline(CASE.pcb_gap)
    bosses = cavity - discs(mounting_holes(), CASE.base_boss_diameter)
    posts = socket_post_outlines()
    post_top = socket_post_top()
    pockets = [
        (cavity, (LEVELS.base_boss_top, CUT_OVERSHOOT)),
        (bosses, (post_top, LEVELS.base_boss_top)),
        (bosses - posts, (LEVELS.boss_root_top, post_top)),
        (cavity - discs(mounting_holes(), CASE.boss_root_diameter) - posts, (LEVELS.floor_top, LEVELS.boss_root_top)),
    ]
    # One boolean for every pocket: cut one at a time, the 0.01 mm overlaps between levels upset OCCT.
    body -= [slab(millable(pocket, variant), (bottom, top + CUT_OVERSHOOT)) for pocket, (bottom, top) in pockets]
    return body + lap_ridges() - _base_cuts(variant)


def socket_post_outlines() -> Sketch:
    """The posts under the hot-swap sockets, seen from above."""
    return Sketch() + [
        rounded_rectangle(_centred_span((x, y), CASE.socket_post), 1.0)
        for x, y in socket_posts()
    ]


def _centred_span(centre: tuple[float, float], size: tuple[float, float]) -> tuple[tuple, tuple]:
    return (centre[0] - size[0] / 2, centre[0] + size[0] / 2), (centre[1] - size[1] / 2, centre[1] + size[1] / 2)


def socket_post_top() -> float:
    """Z of the top of the posts: a little under the bottom of the sockets."""
    return LEVELS.pcb_bottom - BOARD.stack.socket_depth - CASE.socket_post_gap


def _base_blank(variant: str) -> Part:
    """The outside of the base: the full outline up to the gap, then a rim set back by the gap depth.
    The two shells meet at the back of that gap, so the joint is a shadow line and not a seam.
    Round the USB opening the rim runs out flush to the outline instead, so the opening sits in a
    plain pad. The rim's top edge stays sharp: it is the seat of the top, and nobody sees it."""
    chamfer_at_gap = skin_chamfer(variant)
    skin = chamfered_slab(
        case_outline(variant), (LEVELS.floor_bottom, LEVELS.gap_bottom), bottom=CASE.underside_chamfer,
        top=chamfer_at_gap,
    )
    back = case_bounds()[1][0]
    pad = rectangle(usb_pad_span(), (back - FAR, back + CASE.gap_depth + 1.0))
    # The step that makes the gap, as a pocket open to the outside: a mill leaves its tool radius
    # where the step ends against the pad.
    step = case_outline(variant, 5.0) - case_outline(variant, -CASE.gap_depth) - pad
    rim = slab(case_outline(variant) - millable(step, variant), (LEVELS.gap_bottom, 0))
    body = skin + rim
    if chamfer_at_gap:
        # The skin's chamfer stops at the pad, which runs on flush.
        body += slab(case_outline(variant) & pad, (LEVELS.gap_bottom - chamfer_at_gap, LEVELS.gap_bottom))
    return body


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


def _base_cuts(variant: str) -> list[Part]:
    under = LEVELS.floor_bottom - CUT_OVERSHOOT
    screw_holes = [cylinder(hole, BOARD.mounting.hole_diameter, (under, 0)) for hole in mounting_holes()]
    counterbores = [cylinder(hole, CASE.counterbore_diameter, (under, screw_seat(variant))) for hole in mounting_holes()]
    button_holes = [
        cylinder(centre, CASE.button_hole_diameter, (under, LEVELS.floor_top + CUT_OVERSHOOT))
        for centre in buttons().values()
    ]
    foot_recesses = [
        slab(stadium(grown(foot_span(row), CASE.foot_recess_fit)), (under, LEVELS.foot_recess_roof)) for row in screw_rows()
    ]
    light_channels = [_light_channel(left=True), _light_channel(left=False)]
    return [usb_cutout()] + light_channels + screw_holes + counterbores + button_holes + foot_recesses


def button_legends() -> Sketch:
    """A name beside each button hole, drawn as seen from above. The legends, the mark and the centre
    pad stand on one line with equal gaps between them, so the legends' height follows from the other two."""
    mark_back, mark_front = _board_y_range(underside_mark())
    pad_back = foot_span(CENTRE_ROW)[1][0]
    gap = pad_back - mark_front
    labels = []
    for name, (x, _) in buttons().items():
        label = _bolder(legend(name.upper(), LEGEND_SIZE, (x, 0.0), read_from_below=True), LEGEND_GROW)
        label_back, label_front = _board_y_range(label)
        labels.append(Pos(0, -(mark_back - gap - label_front)) * label)
    return Sketch() + labels


def _board_y_range(artwork: Sketch) -> tuple[float, float]:
    box = artwork.bounding_box()
    return -box.max.Y, -box.min.Y  # sketch Y is board Y negated


def _bolder(artwork: Sketch, grow: float) -> Sketch:
    return offset(artwork, amount=grow)


def underside_mark() -> Sketch:
    """The mark in the middle of the label field, drawn as seen from above."""
    (x_low, x_high), (y_low, y_high) = label_field()
    mark = legend(UNDERSIDE_MARK, UNDERSIDE_MARK_SIZE, ((x_low + x_high) / 2, (y_low + y_high) / 2), read_from_below=True)
    return _bolder(mark, UNDERSIDE_MARK_GROW)


def underside_artwork() -> Sketch:
    """Everything marked on the underside. The signature is laser-marked only: it is not in the solids."""
    return button_legends() + underside_mark() + signature.artwork()


def printed_text() -> dict[str, Sketch]:
    """Each piece of text that is engraved into the print variant, by name."""
    return {"legend": button_legends(), "underside_mark": underside_mark()}


def usb_cutout() -> Part:
    """Opening for the plug overmould, with a 45 degree lead-in on the outside. It is taller than
    the base wall above the receptacle, so the base and the top both take a bite of it. Seen from
    behind its corners are rounded: the lower pair in the base, the upper pair inside the top's bite."""
    width, height = usb_opening_size()
    back_face = case_bounds()[1][0]
    # The tunnel floor is a little lower than the case floor. Its inner end is rounded like a milled
    # pocket, so that shallow step has no sharp corner; the rounding starts past the plug.
    radius = CASE.cnc_corner_radius
    plan = rectangle((BOARD.usb.x - width / 2, BOARD.usb.x + width / 2), (back_face - 2 * radius, radius))
    z_range = (LEVELS.usb_centre - height / 2, LEVELS.usb_centre + height / 2)
    # On the outer face of the back wall, centred on the receptacle; its normal points into the case.
    # (A `Pos` in front of a plane would move it in the plane's own axes, not the model's.)
    at_the_port = Plane(origin=(BOARD.usb.x, -(back_face - CUT_OVERSHOOT), LEVELS.usb_centre), x_dir=(1, 0, 0),
                        z_dir=(0, -1, 0))
    profile = usb_opening_profile()
    tunnel = extrude(at_the_port * profile, radius - back_face + CUT_OVERSHOOT) & slab(millable(plan, CNC), z_range)
    flare = CASE.usb_mouth_chamfer
    return tunnel + extrude(at_the_port * offset(profile, amount=flare), flare, taper=45)


def usb_opening_profile() -> Sketch:
    """The opening seen from behind, centred on the receptacle: X across, Y up."""
    width, height = usb_opening_size()
    lower, upper = CASE.usb_corner_radii
    outline = Rectangle(width, height)
    outline = fillet(outline.vertices().group_by(Axis.Y)[0], lower)
    return fillet(outline.vertices().group_by(Axis.Y)[-1], upper)


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
    """The top. Its face carries no text in either variant."""
    # The dish goes first and the pockets go in one boolean: in any other order OCCT returns the
    # CNC top in pieces.
    body = _top_blank(variant) - key_dish(variant)
    body -= [slab(millable(pocket, variant), z_range) for pocket, z_range in _top_pockets(variant)]
    if variant == PRINT:
        body += _print_gussets() + _print_boss_webs() + _print_lens_fillers()
    return body - _top_screw_holes(variant) - usb_cutout() - lap_grooves()


def _top_screw_holes(variant: str) -> list[Part]:
    """Print: a pilot hole the screw cuts its own thread in. CNC: the tap drill, with the cone its
    point leaves, because that point is what comes nearest to the dish floor."""
    if variant == PRINT:
        return [cylinder(hole, CASE.pilot_diameter, (-CUT_OVERSHOOT, CASE.pilot_depth)) for hole in mounting_holes()]
    diameter, depth = CASE.cnc_tap_drill
    point = Pos(0, 0, depth) * Cone(diameter / 2, 0, drill_point_height(), align=(Align.CENTER, Align.CENTER, Align.MIN))
    return [cylinder(hole, diameter, (-CUT_OVERSHOOT, depth)) + Pos(hole[0], -hole[1]) * point for hole in mounting_holes()]


def drill_point_height() -> float:
    return CASE.cnc_tap_drill[0] / 2 / tan(radians(CASE.cnc_drill_point_angle / 2))


def _top_blank(variant: str) -> Part:
    """One flat slab from the joint to the top face."""
    return chamfered_slab(case_outline(variant), (0, LEVELS.deck_top), bottom=CASE.seam_chamfer, top=CASE.chamfer)


def key_dish(variant: str) -> Part:
    """What is cut away for the keys: a flat floor on the plate and 45 degree walls up to the top
    face. The walls print without support when the top stands on its side, and a chamfer mill cuts them."""
    floor = rounded_rectangle(dish_floor(), dish_floor_radius(variant))
    depth = LEVELS.deck_top - LEVELS.plate_top
    return Pos(0, 0, LEVELS.plate_top) * extrude(floor, depth + CUT_OVERSHOOT, taper=-45)


def _top_pockets(variant: str) -> list[tuple[Sketch, tuple[float, float]]]:
    """Every pocket of the top as (outline, Z range), lowest first. Levels that stand on each other
    meet exactly; a pocket runs past a face only where it opens it."""
    cavity = pcb_outline(CASE.pcb_gap) - top_bosses()
    under_the_deck = cavity & rectangle((-FAR, FAR), (-FAR, deck_pocket_front()))
    lens_ribs = Sketch() + [rectangle(span, (-FAR, FAR)) for span in lens_rib_spans()]
    above = LEVELS.deck_top + CUT_OVERSHOOT
    opening = rectangle(*lens_opening(variant))
    return [
        (cavity, (-CUT_OVERSHOOT, LEVELS.rib_bottom)),
        (cavity - _ribs(), (LEVELS.rib_bottom, LEVELS.plate_bottom)),
        (under_the_deck, (LEVELS.plate_bottom, LEVELS.lens_rib_bottom)),
        (under_the_deck - lens_ribs, (LEVELS.lens_rib_bottom, LEVELS.deck_bottom)),
        (_switch_cutouts(variant), (LEVELS.plate_bottom, LEVELS.plate_top + CUT_OVERSHOOT)),
        (opening, (LEVELS.lens_rib_bottom, above)),
        (lens_recess_outline(variant), (LEVELS.lens_seat, above)),
        (discs(encoder_centres(), bushing_hole(variant)), (LEVELS.deck_bottom, above)),
        (discs(encoder_centres(), knob_well_diameter()), (LEVELS.knob_well_floor, above)),
    ]


def top_bosses() -> Sketch:
    """The screw bosses of the top, seen from above: wider at the four corners."""
    return Sketch() + [Pos(x, -y) * Circle(diameter / 2) for (x, y), diameter in top_boss_diameters()]


def top_chairs() -> Part:
    """Print only, and not part of the top: two break-away chairs under the corners that leave the bed
    while the top prints standing on its left side. Each fills the room between the bed, the corner
    and the 45 degree tangent of the corner, with `chair_gap` to the part, and is printed with it.
    Without them the first millimetres of each corner start at up to 90 degrees."""
    (left, _), (back, front) = case_bounds()
    reach = CASE.print_corner_radius
    room = [
        Polygon((left, -back), (left, -(back + reach)), (left + reach, -(back + reach)), align=None),
        Polygon((left, -front), (left, -(front - reach)), (left + reach, -(front - reach)), align=None),
    ]
    profile = Sketch() + room - case_outline(PRINT, CASE.chair_gap)
    return slab(profile, (0, LEVELS.deck_top))


def lens_recess_outline(variant: str) -> Sketch:
    fit = CASE.print_lens_fit if variant == PRINT else CASE.lens_fit
    return rounded_rectangle(lens_recess(variant), CASE.lens_corner_radius + fit)


def _ribs() -> Sketch:
    """Ribs under the plate between the key rows. They run left to right, so they are vertical
    when the top prints standing on its side wall, and they pass through the two centre bosses."""
    half = CASE.rib_width / 2
    return Sketch() + [rectangle((-FAR, FAR), (line - half, line + half)) for line in rib_lines()]


def switch_cutout_length(variant: str) -> float:
    """Size of a switch cut-out along X. The high-X edge of each cut-out is a bridge while the top
    prints standing, and a bridge sags: the print's cut-out is longer by that sag, at that edge."""
    return BOARD.stack.switch_cutout + (CASE.print_bridge_sag if variant == PRINT else 0.0)


def _switch_cutouts(variant: str) -> Sketch:
    side, length = BOARD.stack.switch_cutout, switch_cutout_length(variant)
    cutout = Pos((length - side) / 2, 0) * Rectangle(length, side)
    if variant == CNC:
        cutout += _dog_bones(side)
    return Sketch() + [Pos(x, -y) * cutout for x, y in key_centres()]


def _dog_bones(side: float) -> list[Sketch]:
    """Corner reliefs: a round tool cannot cut the square corner an MX switch needs."""
    radius = CASE.cnc_corner_radius
    centre = side / 2 - radius / sqrt(2)
    return [Pos(sign_x * centre, sign_y * centre) * Circle(radius) for sign_x in (-1, 1) for sign_y in (-1, 1)]


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
    opening = rectangle(*lens_opening(PRINT))
    through = slab(opening, (LEVELS.lens_rib_bottom - CUT_OVERSHOOT, LEVELS.deck_bottom + CUT_OVERSHOOT))
    return [_gusset((rib_start, LEVELS.deck_bottom), -height, y_range) - through for rib_start, _ in lens_rib_spans()]


def _print_boss_webs() -> list[Part]:
    """What carries the screw bosses while the top prints on its left side wall. Without it each boss
    is a cylinder that sticks out of the plate sideways. A corner boss gets a web to the back or front
    wall with a 45 degree underside; a centre boss stands on a rib and only needs a fin below the rib."""
    webs = []
    for (x, y), diameter in top_boss_diameters():
        radius = diameter / 2
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
