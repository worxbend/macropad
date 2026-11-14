"""The small made parts, each in its assembled position: light bars, knobs, lens, foot strips, centre
pad and the optional tilt bar."""

from math import cos, radians, tan

from build123d import Axis, Box, Location, Part, Plane, Polygon, Pos, Rectangle, Rot, Sketch, chamfer, fillet, mirror

from .parts import FAR, WIDTH, base, top
from .solids import CUT_OVERSHOOT, box, case_outline, centred_rectangle, cylinder, d_profile, rectangle
from .solids import rounded_rectangle, slab, stadium
from .spec import BACK_ROW, BOARD, CASE, CENTRE_ROW, FRONT_ROW, LEVELS, PRINT, Span, case_bounds, encoder_centres
from .spec import foot_span, foot_thickness, grown, led_slot_span, lens_span, screw_rows

BAR_TO_TOP = 0.1  # the light bar ends this far under the top shell
# The end of the knob's bore sits on the end of the shaft: that sets the knob's height.
BORE_END = BOARD.stack.encoder_shaft_top
GROOVE_CUTTER_PAST = 0.2  # the V profile that cuts a knob groove runs this far past the knob's surface


def diffuser_left() -> Part:
    """Light bar for the left wall: a plain bar that stands in the base's channel, behind the outer
    skin of the wall. Only the top of its outer face shows, at the back of the gap. Below the gap its
    ends are rounded like the channel; in the gap they are square like the slot through the rim, so
    the bar fills that slot from end to end. A lip beside the PCB edge stops it from falling inward
    once the PCB is in."""
    fit = CASE.diffuser_fit
    slot_start, slot_end = led_slot_span()
    along = (slot_start + fit, slot_end - fit)
    inner_face = -(CASE.diffuser_to_pcb + CASE.light_bar_lip)
    x_range = (-(CASE.pcb_gap + CASE.light_channel_reach) + CASE.light_bar_skin_fit, inner_face)
    in_the_gap = LEVELS.gap_bottom + fit  # the square part clears the floor of the slot by the fit
    in_the_channel = box(x_range, along, (LEVELS.led_slot_bottom + fit, in_the_gap))
    outer_ends = in_the_channel.edges().filter_by(Axis.Z).group_by(Axis.X)[0]
    shown = box(x_range, along, (in_the_gap, -BAR_TO_TOP))
    lip = box((inner_face, -CASE.diffuser_to_pcb), along, (LEVELS.pcb_bottom, -BAR_TO_TOP))
    return fillet(outer_ends, CASE.light_channel_radius - CASE.light_bar_skin_fit) + shown + lip


def diffuser_right() -> Part:
    return mirror(diffuser_left(), Plane.YZ.offset(WIDTH / 2))


def knob() -> Part:
    """One knob at the origin in X and Y, at its assembled height: a plain cylinder with fine straight
    grooves round the middle, a flat top, and a radial pointer line on the same side as the flat of the
    D-shaft (toward the back of the board). The end of its bore sits on the end of the shaft, and its
    foot stands in a well in the top face."""
    blank = cylinder((0, 0), CASE.knob_diameter, (LEVELS.knob_bottom, LEVELS.knob_top))
    body = chamfer(blank.edges().group_by(Axis.Z)[-1], CASE.chamfer)
    body = chamfer(body.edges().group_by(Axis.Z)[0], CASE.chamfer)
    bushing_pocket_diameter = BOARD.stack.encoder_bushing_diameter + 1.0
    bushing_pocket = cylinder((0, 0), bushing_pocket_diameter, (LEVELS.knob_bottom - CUT_OVERSHOOT, LEVELS.knob_bushing_roof))
    clearance = CASE.knob_bore_clearance
    d_bore = d_profile(CASE.shaft_diameter + clearance, CASE.shaft_flat + clearance)
    bore = slab(d_bore, (LEVELS.knob_bottom, BORE_END))
    return body - bushing_pocket - bore - _knob_grooves() - _knob_pointer() + knob_crush_ribs()


def _knob_grooves() -> list[Part]:
    """Straight 90 degree V grooves between the two plain bands. Each ends square, as a turned band
    would: the grooved band reads as one ring between two smooth ones."""
    radius, depth, past = CASE.knob_diameter / 2, CASE.knob_groove_depth, GROOVE_CUTTER_PAST
    start, end = LEVELS.knob_bottom + CASE.knob_plain_band, LEVELS.knob_top - CASE.knob_plain_band
    # Counter-clockwise, so the face looks up and `slab` extrudes it upward.
    vee = Polygon((radius - depth, 0), (radius + past, -depth - past), (radius + past, depth + past), align=None)
    groove = slab(vee, (start, end))
    step = 360 / CASE.knob_grooves
    # Half a step off, so a land and not a groove lies in line with the pointer.
    return [Rot(0, 0, (index + 0.5) * step) * groove for index in range(CASE.knob_grooves)]


def knob_crush_ribs() -> list[Part]:
    """Three low ribs on the round side of the bore, at the knob's place over the origin. Each reaches
    `knob_rib_interference` into the shaft, so a bore that prints to size still grips it; a bore that
    prints small crushes them."""
    width, length = CASE.knob_crush_rib
    inner = CASE.shaft_diameter / 2 - CASE.knob_rib_interference
    bore_radius = (CASE.shaft_diameter + CASE.knob_bore_clearance) / 2
    into_the_wall = 0.3  # so the rib and the knob are one body
    rib = Pos((inner + bore_radius + into_the_wall) / 2, 0, BORE_END - length / 2) * Box(
        bore_radius + into_the_wall - inner, width, length
    )
    # The flat of the bore faces +Y; the ribs sit opposite it and 60 degrees to either side.
    return [Rot(0, 0, angle) * rib for angle in (210, 270, 330)]


def knob_pointer_outline() -> Sketch:
    """The pointer line on the knob's top, seen from above."""
    width, _, start, end = CASE.knob_pointer
    return Pos(0, (start + end) / 2) * Rectangle(width, end - start)


def _knob_pointer() -> Part:
    depth = CASE.knob_pointer[1]
    return slab(knob_pointer_outline(), (LEVELS.knob_top - depth, LEVELS.knob_top + CUT_OVERSHOOT))


def knobs() -> list[Part]:
    return [Pos(x, -y, 0) * knob() for x, y in encoder_centres()]


def lens_outline() -> Sketch:
    return rounded_rectangle(lens_span(), CASE.lens_corner_radius)


def lens_mask_outline() -> Sketch:
    """The black print on the underside of the lens: all of it except the window over the pixels."""
    display = BOARD.display
    window = centred_rectangle((display.mask_window_x, display.window_y),
                               (display.mask_window_length, display.window_width))
    return lens_outline() - window


def lens() -> Part:
    """The display lens: a clear sheet taped on the two ledges of its recess."""
    return slab(lens_outline(), (LEVELS.lens_bottom, LEVELS.lens_top))


def lens_drawn() -> Part:
    """The lens for the pictures: the renderer has no clear material, so only the masked part of the
    lens is drawn and the display shows through the window."""
    return slab(lens_mask_outline(), (LEVELS.lens_bottom, LEVELS.lens_top))


def foot_strip(row: str) -> Part:
    """The foot over one row of screws, in its recess under the base. It hides the screw heads."""
    return slab(stadium(foot_span(row)), (LEVELS.foot_recess_roof - foot_thickness(row), LEVELS.foot_recess_roof))


def centre_pad() -> Part:
    return foot_strip(CENTRE_ROW)


def _strip_line(row: str) -> float:
    """Board Y of the screws under one foot strip."""
    return screw_rows()[row][0][1]


def desk_plane_drop(board_y: float) -> float:
    """How far the tilted desk plane lies below the base underside at `board_y`, measured to the
    underside of the tilt bar. The case pivots on its front strip."""
    return (_strip_line(FRONT_ROW) - board_y) * tan(radians(CASE.tilt_angle))


def _on_the_slope() -> Location:
    """A frame lying on the tilt bar's sloped underside, under the back strip's line: local X along
    the strip, local +Y toward the back, local +Z into the bar."""
    under_the_front_strip = Location((0, -_strip_line(FRONT_ROW), LEVELS.floor_bottom), (-CASE.tilt_angle, 0, 0))
    along_slope = (_strip_line(FRONT_ROW) - _strip_line(BACK_ROW)) / cos(radians(CASE.tilt_angle))
    return under_the_front_strip * Pos(0, along_slope, 0)


def _back_strip_at_origin(grow: float) -> Span:
    """The back strip's footprint moved to board Y = 0, made `grow` larger all round."""
    x_range, (y_low, y_high) = grown(foot_span(BACK_ROW), grow)
    half_width = (y_high - y_low) / 2
    return x_range, (-half_width, half_width)


def tilt_bar() -> Part:
    """The tilt bar as it prints: the finished bar with a skin across each hole, where the hole opens
    into the roof of the strip recess. The bar prints with that recess on the bed, and a hole in its
    roof would be a hole in a bridge. The builder cuts the two skins out."""
    skin = CASE.screw_skin
    layer = _on_the_slope() * Pos(0, 0, CASE.foot_recess_depth + skin / 2) * Box(1000, 1000, skin)
    through = (_lowest_point(), LEVELS.floor_bottom)
    into_the_wall = CASE.tilt_hole_diameter + 2 * CUT_OVERSHOOT  # so each skin joins the bar, not just touches it
    return tilt_bar_body() + [cylinder(screw, into_the_wall, through) & layer for screw in screw_rows()[BACK_ROW]]


def _lowest_point() -> float:
    back_edge = case_bounds()[1][0] + CASE.tilt_bar_inset
    return LEVELS.floor_bottom - desk_plane_drop(back_edge) - 1


def tilt_bar_body() -> Part:
    """Optional wedge under the back of the base, finished. A tongue on its top sits in the base's
    back strip recess, and the back strip moves to a recess in its own sloped underside. Two holes keep
    the back corner screws reachable once that strip is peeled off."""
    plan = case_outline(PRINT, -CASE.tilt_bar_inset) & rectangle((-FAR, FAR), (-FAR, CASE.tilt_bar_front))
    lowest = _lowest_point()
    below_the_slope = _on_the_slope() * Pos(0, 0, -50) * Box(1000, 1000, 100)
    block = slab(plan, (lowest, LEVELS.floor_bottom))
    # The bar stands a little wider than the flat of the underside; its outer top edge is cut back at
    # 45 degrees, so the underside chamfer of the base runs on down the bar.
    front = -CASE.tilt_bar_front
    outer = block.edges().group_by(Axis.Z)[-1].filter_by(lambda edge: edge.center().Y > front + CUT_OVERSHOOT)
    block = chamfer(outer, CASE.underside_chamfer - CASE.tilt_bar_inset)
    tongue_height = CASE.tilt_tongue[1]
    tongue = slab(_tilt_tongue_plan(), (LEVELS.floor_bottom, LEVELS.floor_bottom + tongue_height))
    recess = _on_the_slope() * slab(
        stadium(_back_strip_at_origin(CASE.foot_recess_fit)), (-CUT_OVERSHOOT, CASE.foot_recess_depth)
    )
    return block - below_the_slope + tongue - recess - _tilt_holes(lowest)


def _tilt_holes(lowest: float) -> list[Part]:
    """A hole straight up to each back corner screw."""
    through = (lowest, LEVELS.floor_bottom + CASE.tilt_tongue[1] + 1)
    return [cylinder(screw, CASE.tilt_hole_diameter, through) for screw in screw_rows()[BACK_ROW]]


def _tilt_tongue_plan() -> Sketch:
    """The tongue fills the back strip recess between the two corner screws, with a little play."""
    play, _, from_hole = CASE.tilt_tongue
    (x_low, x_high), y_range = grown(foot_span(BACK_ROW), CASE.foot_recess_fit - play)
    left_screw, right_screw = sorted(x for x, _ in screw_rows()[BACK_ROW])
    clear_of_screw = CASE.tilt_hole_diameter / 2 + from_hole
    return stadium(((max(x_low, left_screw + clear_of_screw), min(x_high, right_screw - clear_of_screw)), y_range))


def tilt_strip() -> dict[str, Part]:
    """The back foot strip moved to the tilt bar. It replaces `foot_strip_back`."""
    roof = CASE.foot_recess_depth
    strip = slab(stadium(_back_strip_at_origin(0.0)), (roof - foot_thickness(BACK_ROW), roof))
    return {"tilt_strip": _on_the_slope() * strip}


def case_parts(variant: str) -> dict[str, Part]:
    """Every part of one build, by name, in assembled position."""
    left_knob, right_knob = knobs()
    return {
        "base": base(variant),
        "top": top(variant),
        "diffuser_left": diffuser_left(),
        "diffuser_right": diffuser_right(),
        "knob_left": left_knob,
        "knob_right": right_knob,
        "lens": lens(),
        "foot_strip_back": foot_strip(BACK_ROW),
        "foot_strip_front": foot_strip(FRONT_ROW),
        "centre_pad": centre_pad(),
        "tilt_bar": tilt_bar(),
    }
