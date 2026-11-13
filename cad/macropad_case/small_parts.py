"""The small printed parts: light strips, knobs and the optional tilt bar, each in its assembled position."""

from math import cos, radians, tan

from build123d import Axis, Box, Cylinder, Location, Part, Plane, Pos, Rectangle, chamfer, extrude, mirror

from .components import bumper
from .parts import OUTER, WIDTH, base, top
from .solids import CUT_OVERSHOOT, box, cylinder, d_profile, slab
from .spec import BOARD, CASE, LEVELS, encoder_centres, foot_centres, led_slot_span

POINTER_INNER_RADIUS = 2.5
KNOB_TOP_CHAMFER = 1.0
KNOB_BOTTOM_CHAMFER = 0.4


def diffuser_left() -> Part:
    """Translucent strip for the left wall. Its flange sits behind the wall under the slot, a lip beside
    the PCB edge stops it from falling inward once the PCB is in, and its face stands out of the wall."""
    fit = CASE.diffuser_fit
    slot_start, slot_end = led_slot_span()
    stem_y = (slot_start + fit, slot_end - fit)
    stem_z = (LEVELS.led_slot_bottom + fit, -0.1)
    flange_y = (slot_start - CASE.diffuser_flange_overlap, slot_end + CASE.diffuser_flange_overlap)
    inner_face = -CASE.pcb_gap + 0.1
    stem = box((-OUTER, inner_face), stem_y, stem_z)
    lip = box((inner_face, -CASE.diffuser_to_pcb), stem_y, (LEVELS.pcb_bottom, -0.1))
    flange_top = LEVELS.pcb_bottom - CASE.diffuser_flange_top_below_pcb
    flange = box((inner_face, inner_face + CASE.diffuser_flange), flange_y, (LEVELS.floor_top + CASE.diffuser_flange_to_floor, flange_top))
    return stem + lip + flange + _proud_face(stem_y, stem_z)


def _proud_face(y_range: tuple[float, float], z_range: tuple[float, float]) -> Part:
    """The part of the strip outside the left wall, narrowing at 45 degrees."""
    face = Rectangle(y_range[1] - y_range[0], z_range[1] - z_range[0])
    wall_plane = Plane.YZ.offset(-OUTER).reverse()  # its normal points out of the left wall
    centre = Pos(0, -(y_range[0] + y_range[1]) / 2, (z_range[0] + z_range[1]) / 2)
    return centre * extrude(wall_plane * face, CASE.diffuser_proud, taper=45)


def diffuser_right() -> Part:
    return mirror(diffuser_left(), Plane.YZ.offset(WIDTH / 2))


def knob() -> Part:
    """One knob at the origin in X and Y, at its assembled height: fluted grip, a plain band under it,
    and a pointer groove on the same side as the flat of the D-shaft (toward the back of the board)."""
    blank = cylinder((0, 0), CASE.knob_diameter, (LEVELS.knob_bottom, LEVELS.knob_top))
    rims = blank.edges().group_by(Axis.Z)
    body = chamfer(rims[-1], KNOB_TOP_CHAMFER)
    body = chamfer(body.edges().group_by(Axis.Z)[0], KNOB_BOTTOM_CHAMFER)
    bushing_pocket_diameter = BOARD.stack.encoder_bushing_diameter + 1.0
    bushing_pocket = cylinder(
        (0, 0), bushing_pocket_diameter, (LEVELS.knob_bottom - CUT_OVERSHOOT, LEVELS.bushing_top + 0.5)
    )
    clearance = CASE.knob_bore_clearance
    d_bore = d_profile(CASE.shaft_diameter + clearance, CASE.shaft_flat + clearance)
    bore = slab(d_bore, (LEVELS.knob_bottom, BOARD.stack.encoder_shaft_top + 0.3))
    return body - bushing_pocket - bore - _knob_flutes() - _knob_pointer()


def _knob_flutes() -> list[Part]:
    grip_bottom = LEVELS.knob_bottom + CASE.knob_plain_band
    height = LEVELS.knob_top - grip_bottom + CUT_OVERSHOOT
    centre_radius = CASE.knob_diameter / 2 + CASE.knob_flute_radius - CASE.knob_flute_depth
    flute = Pos(centre_radius, 0, grip_bottom + height / 2) * Cylinder(CASE.knob_flute_radius, height)
    step = 360 / CASE.knob_flutes
    # Half a step off, so the flutes sit either side of the pointer groove at 90 degrees.
    return [Location((0, 0, 0), (0, 0, (index + 0.5) * step)) * flute for index in range(CASE.knob_flutes)]


def _knob_pointer() -> Part:
    width, depth = CASE.knob_pointer
    radius = CASE.knob_diameter / 2
    across_top_length = radius - POINTER_INNER_RADIUS + 1
    across_top = Pos(0, POINTER_INNER_RADIUS + across_top_length / 2, LEVELS.knob_top) * Box(
        width, across_top_length, 2 * depth
    )
    grip_bottom = LEVELS.knob_bottom + CASE.knob_plain_band
    down_the_side = Pos(0, radius, (grip_bottom + LEVELS.knob_top) / 2) * Box(
        width, 2 * depth, LEVELS.knob_top - grip_bottom
    )
    return across_top + down_the_side


def knobs() -> list[Part]:
    return [Pos(x, -y, 0) * knob() for x, y in encoder_centres()]


def desk_plane_drop(board_y: float) -> float:
    """How far the tilted desk plane lies below the base underside at `board_y`, measured to the
    underside of the tilt bar. The case pivots on its front feet."""
    front_feet_y = foot_centres()[-1][1]
    return (front_feet_y - board_y) * tan(radians(CASE.tilt_angle))


def _on_the_slope() -> Location:
    """A frame lying on the tilt bar's sloped underside: origin under the front feet, local +Y toward
    the back, local +Z into the bar."""
    front_feet_y = foot_centres()[-1][1]
    return Location((0, -front_feet_y, LEVELS.floor_bottom), (-CASE.tilt_angle, 0, 0))


def _back_feet_on_the_slope() -> list[Pos]:
    """Where the back feet sit in that frame."""
    back_left, back_right = foot_centres()[:2]
    front_feet_y = foot_centres()[-1][1]
    along_slope = (front_feet_y - back_left[1]) / cos(radians(CASE.tilt_angle))
    return [Pos(x, along_slope, 0) for x in (back_left[0], back_right[0])]


def tilt_bar() -> Part:
    """Optional wedge under the back feet. Two pegs sit in the base's back foot recesses, and the
    feet move to the recesses in its own sloped underside."""
    back_left, back_right = foot_centres()[:2]
    half_depth = CASE.tilt_bar_depth / 2
    x_range = (back_left[0] - CASE.tilt_bar_overhang, back_right[0] + CASE.tilt_bar_overhang)
    y_range = (back_left[1] - half_depth, back_left[1] + half_depth)
    block = box(x_range, y_range, (LEVELS.floor_bottom - desk_plane_drop(y_range[0]) - 1, LEVELS.floor_bottom))
    below_the_slope = _on_the_slope() * Pos(0, 0, -50) * Box(1000, 1000, 100)
    recess = Pos(0, 0, CASE.foot_depth / 2 - CUT_OVERSHOOT) * Cylinder(
        CASE.foot_diameter / 2, CASE.foot_depth + 2 * CUT_OVERSHOOT
    )
    recesses = [_on_the_slope() * place * recess for place in _back_feet_on_the_slope()]
    peg_diameter = CASE.foot_diameter - CASE.tilt_peg_clearance
    peg_top = LEVELS.floor_bottom + CASE.foot_depth - 0.1
    pegs = [cylinder(centre, peg_diameter, (LEVELS.floor_bottom, peg_top)) for centre in (back_left, back_right)]
    return block - below_the_slope - recesses + pegs


def tilt_feet() -> dict[str, Part]:
    """The two back feet moved to the tilt bar. They replace `foot_0` and `foot_1`."""
    seat = Pos(0, 0, CASE.foot_depth)
    return {
        f"tilt_foot_{index}": _on_the_slope() * place * seat * bumper()
        for index, place in enumerate(_back_feet_on_the_slope())
    }


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
        "tilt_bar": tilt_bar(),
    }
