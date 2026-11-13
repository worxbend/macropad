"""The checks, checked: each one is run on a small solid with a known fault and must report it, and on
a sound solid and must stay quiet. A check that cannot fail proves nothing about the case."""

from math import radians, tan

from build123d import Axis, Box, Cylinder, Part, Plane, Polygon, Pos, extrude, fillet

from . import measure, printsim
from .solids import case_outline, overlap_volume, slab
from .spec import CASE, CNC, PRINT

BLOCK = (30.0, 30.0, 10.0)
POCKET = (10.0, 10.0, 6.0)  # open at the top of the block
OUTLINE_SLAB = (0.0, 2.0)
LEDGE_SPAN = 58.0  # about the length of the key dish's wall


def _block() -> Part:
    return Pos(0, 0, BLOCK[2] / 2) * Box(*BLOCK)


def _pocket(corner_radius: float) -> Part:
    pocket = Pos(0, 0, BLOCK[2] - POCKET[2] / 2 + 1) * Box(POCKET[0], POCKET[1], POCKET[2] + 2)
    return fillet(pocket.edges().filter_by(Axis.Z), corner_radius) if corner_radius else pocket


def _triangles(part: Part):
    return measure.mesh_of(part, measure.ANY_MATERIAL).triangles


def run() -> list[dict]:
    tool = 2 * CASE.cnc_corner_radius
    sound = _block() - _pocket(CASE.cnc_corner_radius)
    sharp = _block() - _pocket(0)
    tight = _block() - _pocket(CASE.cnc_corner_radius - 0.5)
    slotted = _block() - Pos(0, 0, BLOCK[2]) * Box(20, tool - 1.0, 8)
    undercut = _block() - Pos(BLOCK[0] / 2, 0, BLOCK[2] / 2) * Box(10, 10, 3)  # a groove in the side
    sheet = Box(20, 20, CASE.min_wall - 0.3)
    table = Pos(0, 0, 5) * Box(24, 20, 2) + Pos(-11, 0, 2) * Box(2, 20, 4) + Pos(11, 0, 2) * Box(2, 20, 4)
    table_print = printsim.simulate(_triangles(table))
    shelf = Pos(0, 0, 5) * Box(4, 4, 10) + Pos(4, 0, 9) * Box(4, 4, 2)
    ramp_60 = _leaning_wall(60)
    ramp_45 = _leaning_wall(45)
    arc_corners, smooth_corners = slab(case_outline(PRINT), OUTLINE_SLAB), slab(case_outline(CNC), OUTLINE_SLAB)
    outline_height = sum(OUTLINE_SLAB) / 2
    loose = Box(5, 5, 5) + Pos(10, 0, 0) * Box(5, 5, 5)
    cases = [
        ("overlap_found", overlap_volume(_block(), Pos(1, 0, 0) * _block()), "more than", 0.05),
        ("thin_wall_found", measure.thinnest_wall(sheet), "less than", CASE.min_wall),
        ("sharp_corners_found", measure.sharp_internal_corners(sharp), "equal to", 4),
        ("sound_pocket_has_no_sharp_corner", measure.sharp_internal_corners(sound), "equal to", 0),
        ("tight_radius_found", measure.smallest_pocket_radius(tight)[0], "less than", CASE.cnc_corner_radius),
        ("undercut_found", measure.unreachable_area(undercut), "more than", measure.UNDERCUT_NOISE),
        ("sound_pocket_has_no_undercut", measure.unreachable_area(sound), "less than", measure.UNDERCUT_NOISE),
        ("sharp_corner_not_cut", measure.uncut_area(sharp, tool)["above"], "more than", measure.UNCUT_NOISE),
        ("narrow_slot_not_cut", measure.uncut_area(slotted, tool)["above"], "more than", measure.UNCUT_NOISE),
        ("sound_pocket_is_cut", measure.uncut_area(sound, tool)["above"], "less than", measure.UNCUT_NOISE),
        ("long_bridge_found", table_print.longest_bridge, "more than", CASE.max_bridge),
        ("bridge_is_no_cantilever", table_print.deepest_cantilever, "less than", 0.5),
        ("cantilever_found", printsim.simulate(_triangles(shelf)).deepest_cantilever, "more than", CASE.max_cantilever),
        ("flat_slope_found", printsim.simulate(_triangles(ramp_60)).deepest_cantilever, "more than", CASE.max_cantilever),
        ("slope_of_45_degrees_prints", printsim.simulate(_triangles(ramp_45)).deepest_cantilever, "less than", 0.5),
        ("arc_corner_found", measure.outline_corners(arc_corners, outline_height)[0], "more than",
         measure.MAX_JOIN_CURVATURE),
        ("smooth_corner_has_no_curvature_step", measure.outline_corners(smooth_corners, outline_height)[0], "less than",
         measure.MAX_JOIN_CURVATURE),
        ("loose_pieces_found", measure.soundness_faults(loose), "more than", 0),
        ("one_box_is_sound", measure.soundness_faults(Box(5, 5, 5)), "equal to", 0),
        ("hole_in_recess_roof_found", _longest_bridge(_recessed_block(skin=0.0)), "more than", CASE.max_bridge),
        ("skinned_hole_in_recess_roof_prints", _longest_bridge(_recessed_block(CASE.screw_skin)), "less than",
         CASE.max_bridge),
        ("thin_stroke_found", measure.stroke_width(_bar_glyph(0.3)), "less than", 0.45),
        ("wide_stroke_passes", measure.stroke_width(_bar_glyph(0.6)), "more than", 0.45),
        ("foot_over_a_hole_found", measure.bearing_share(*_foot_on_a_block(hole=6.0)), "less than", 0.8),
        ("foot_on_a_flat_bears", measure.bearing_share(*_foot_on_a_block(hole=0.0)), "more than", 0.99),
        ("ledge_between_walls_found", _longest_bridge(_ledged_wall(sloped=False)), "more than", CASE.max_bridge),
        ("sloped_ledge_prints", _longest_bridge(_ledged_wall(sloped=True)), "less than", CASE.max_bridge),
    ]
    return [_verdict(*case) for case in cases]


def _leaning_wall(degrees_from_vertical: float) -> Part:
    """A 3 mm wall, 12 mm tall, leaning over by the given angle."""
    lean = 12 * tan(radians(degrees_from_vertical))
    profile = Plane.XZ * Polygon((0, 0), (3, 0), (3 + lean, 12), (lean, 12), align=None)
    return extrude(profile, 10)


def _longest_bridge(part: Part) -> float:
    return printsim.simulate(_triangles(part)).longest_bridge


def _recessed_block(skin: float) -> Part:
    """A block on the bed with a foot recess under it and a screw counterbore above that recess.
    `skin` is how much of the recess roof is left under the counterbore: none, or the one layer the base has."""
    recess_width = CASE.foot_strip[0] + 2 * CASE.foot_recess_fit
    depth = CASE.foot_recess_depth
    block = Pos(0, 0, 3) * Box(40, 14, 6)
    recess = Pos(0, 0, depth / 2 - 1) * Box(30, recess_width, depth + 2)
    counterbore = Pos(0, 0, depth + skin + 2 - 0.01) * Cylinder(CASE.counterbore_diameter / 2, 4)
    return block - recess - counterbore


def _bar_glyph(stroke: float) -> Part:
    """A stand-in for a letter: one bar 3 mm long."""
    return Plane.XY * Polygon((0, 0), (3, 0), (3, stroke), (0, stroke), align=None)


def _foot_on_a_block(hole: float) -> tuple[Part, Part]:
    """A foot 10 x 10 x 1 under a block, and the block, with a round hole of the given diameter over the foot."""
    foot = Pos(0, 0, -0.5) * Box(10, 10, 1)
    block = Pos(0, 0, 3) * Box(20, 20, 6)
    return foot, block - Cylinder(hole / 2, 20) if hole else block


def _ledged_wall(sloped: bool) -> Part:
    """A wall between two posts with a ledge 1 mm deep along it, 6 mm up: the foot of a vertical dish
    wall while the top prints standing. `sloped` gives the ledge a 45 degree underside instead."""
    posts = [Pos(side * (LEDGE_SPAN / 2 + 1), 0, 5) * Box(2, 6, 10) for side in (-1, 1)]
    wall = Pos(0, 2, 5) * Box(LEDGE_SPAN, 2, 10)
    underside = (1, 5) if sloped else (0, 6)
    profile = Plane.YZ * Polygon((1, 7), (0, 7), (0, 6), underside, align=None)
    ledge = Pos(-LEDGE_SPAN / 2, 0, 0) * extrude(profile, LEDGE_SPAN)
    return wall + posts + ledge


def _verdict(name: str, found: float, relation: str, limit: float) -> dict:
    ok = {"more than": found > limit, "less than": found < limit, "equal to": found == limit}[relation]
    return {"name": name, "found": round(float(found), 3), "expected": f"{relation} {limit}", "ok": bool(ok)}
