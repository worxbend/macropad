"""The checks, checked: each one is run on a small solid with a known fault and must report it, and on
a sound solid and must stay quiet. A check that cannot fail proves nothing about the case."""

from math import radians, tan

from build123d import Axis, Box, Part, Plane, Polygon, Pos, extrude, fillet

from . import measure, printsim
from .solids import overlap_volume
from .spec import CASE

BLOCK = (30.0, 30.0, 10.0)
POCKET = (10.0, 10.0, 6.0)  # open at the top of the block


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
    ]
    return [_verdict(*case) for case in cases]


def _leaning_wall(degrees_from_vertical: float) -> Part:
    """A 3 mm wall, 12 mm tall, leaning over by the given angle."""
    lean = 12 * tan(radians(degrees_from_vertical))
    profile = Plane.XZ * Polygon((0, 0), (3, 0), (3 + lean, 12), (lean, 12), align=None)
    return extrude(profile, 10)


def _verdict(name: str, found: float, relation: str, limit: float) -> dict:
    ok = {"more than": found > limit, "less than": found < limit, "equal to": found == limit}[relation]
    return {"name": name, "found": round(float(found), 3), "expected": f"{relation} {limit}", "ok": bool(ok)}
