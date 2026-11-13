"""Small build123d helpers that take board coordinates (X right, Y toward the front, Z up from the PCB top)."""

from pathlib import Path

import matplotlib
from build123d import Axis, Box, Circle, Cylinder, Kind, Part, Plane, Pos, Rectangle, RectangleRounded, Sketch, Text
from build123d import chamfer, extrude, loft, mirror, offset

from .spec import BOARD, CASE, CNC

CUT_OVERSHOOT = 0.01  # cuts run past the face they open so no zero-thickness skin is left
# DejaVu Sans Bold ships inside matplotlib, so the engraved text is the same on every machine.
LEGEND_FONT = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"


def box(x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Part:
    size = (x[1] - x[0], y[1] - y[0], z[1] - z[0])
    return Pos((x[0] + x[1]) / 2, -(y[0] + y[1]) / 2, (z[0] + z[1]) / 2) * Box(*size)


def centred_box(centre: tuple[float, float], size: tuple[float, float], z: tuple[float, float]) -> Part:
    half_x, half_y = size[0] / 2, size[1] / 2
    return box((centre[0] - half_x, centre[0] + half_x), (centre[1] - half_y, centre[1] + half_y), z)


def cylinder(centre: tuple[float, float], diameter: float, z: tuple[float, float]) -> Part:
    return Pos(centre[0], -centre[1], (z[0] + z[1]) / 2) * Cylinder(diameter / 2, z[1] - z[0])


def rectangle(x: tuple[float, float], y: tuple[float, float]) -> Sketch:
    return Pos((x[0] + x[1]) / 2, -(y[0] + y[1]) / 2) * Rectangle(x[1] - x[0], y[1] - y[0])


def centred_rectangle(centre: tuple[float, float], size: tuple[float, float]) -> Sketch:
    return Pos(centre[0], -centre[1]) * Rectangle(*size)


def disc(centre: tuple[float, float], diameter: float) -> Sketch:
    return Pos(centre[0], -centre[1]) * Circle(diameter / 2)


def discs(centres: list[tuple[float, float]], diameter: float) -> Sketch:
    return Sketch() + [disc(centre, diameter) for centre in centres]


def d_profile(diameter: float, across_flat: float) -> Sketch:
    """A D-shaft cross-section at the origin, flat toward the back of the board."""
    radius = diameter / 2
    flat_offset = across_flat - radius
    keep = Pos(0, (flat_offset - radius) / 2) * Rectangle(diameter, flat_offset + radius)
    return Circle(radius) & keep


def pcb_outline(grow: float = 0.0) -> Sketch:
    """The PCB outline grown outward by `grow` (the corner radius grows with it)."""
    board = BOARD.board
    grown = RectangleRounded(board.width + 2 * grow, board.height + 2 * grow, board.corner_radius + grow)
    return Pos(board.width / 2, -board.height / 2) * grown


def slab(profile: Sketch, z: tuple[float, float]) -> Part:
    return Pos(0, 0, z[0]) * extrude(profile, z[1] - z[0])


def chamfered_slab(profile: Sketch, z: tuple[float, float], bottom: float, top: float) -> Part:
    """A slab with its bottom and top outlines cut back at 45 degrees. A zero leaves that outline sharp."""
    body = slab(profile, z)
    if bottom:
        body = chamfer(body.edges().group_by(Axis.Z)[0], bottom)
    if top:
        body = chamfer(body.edges().group_by(Axis.Z)[-1], top)
    return body


def flared_cut(opening: Sketch, top: float, depth: float) -> Part:
    """A 45 degree lead-in around `opening`: `depth` deep, widest at the face z = `top`."""
    narrow = Pos(0, 0, top - depth) * opening
    wide = Pos(0, 0, top + CUT_OVERSHOOT) * offset(opening, amount=depth + CUT_OVERSHOOT, kind=Kind.INTERSECTION)
    return loft([narrow.face(), wide.face()], ruled=True)


def legend(text: str, size: float, centre: tuple[float, float], read_from_below: bool = False) -> Sketch:
    """Engraving artwork at a board position. Text read from below is mirrored left to right."""
    artwork = Text(text, size, font_path=str(LEGEND_FONT))
    if read_from_below:
        artwork = mirror(artwork, Plane.YZ)
    return Pos(centre[0], -centre[1]) * artwork


def millable(pocket: Sketch, variant: str) -> Sketch:
    """A pocket a 3-axis mill can cut: for CNC every corner of the pocket gets the tool radius
    and any gap the tool cannot enter stays solid (a morphological opening)."""
    if variant != CNC:
        return pocket
    radius = CASE.cnc_corner_radius
    return offset(offset(pocket, amount=-radius), amount=radius)


def overlap_volume(first: Part, second: Part) -> float:
    if not _boxes_overlap(first.bounding_box(), second.bounding_box()):
        return 0.0
    common = first & second
    return 0.0 if common is None else sum(solid.volume for solid in common.solids())


def _boxes_overlap(first, second) -> bool:
    return all(
        low_a < high_b and low_b < high_a
        for low_a, high_a, low_b, high_b in zip(first.min, first.max, second.min, second.max)
    )
