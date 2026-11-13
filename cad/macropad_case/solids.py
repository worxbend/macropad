"""Small build123d helpers that take board coordinates (X right, Y toward the front, Z up from the PCB top)."""

from pathlib import Path

import matplotlib
from build123d import Axis, Bezier, Box, Circle, Cylinder, Kind, Line, Part, Plane, Pos, Rectangle, RectangleRounded
from build123d import Sketch, Text, Wire, chamfer, extrude, loft, make_face, mirror, offset

from .spec import BOARD, CASE, CNC, PRINT, Span, case_bounds, grown

CUT_OVERSHOOT = 0.01  # cuts run past the face they open so no zero-thickness skin is left
STADIUM_FLAT = 1e-4  # a rounded rectangle needs a side between its corners, however short
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


def rounded_rectangle(span: Span, radius: float) -> Sketch:
    (x_low, x_high), (y_low, y_high) = span
    return Pos((x_low + x_high) / 2, -(y_low + y_high) / 2) * RectangleRounded(x_high - x_low, y_high - y_low, radius)


def stadium(span: Span) -> Sketch:
    """A slot shape: a rectangle whose two short sides are half circles."""
    (x_low, x_high), (y_low, y_high) = span
    return rounded_rectangle(span, min(x_high - x_low, y_high - y_low) / 2 - STADIUM_FLAT)


def case_outline(variant: str, grow: float = 0.0) -> Sketch:
    """The case seen from above, grown outward by `grow`.

    Print: circular corners. The top prints standing on a side wall, and a corner that starts flatter
    than this arc hangs too far over the bed. CNC: each corner is one curve whose curvature is zero
    where it meets the straight sides, so no highlight breaks there. Both corners have the same apex."""
    if variant == PRINT:
        return rounded_rectangle(grown(case_bounds(), grow), CASE.print_corner_radius + grow)
    outline = _continuous_outline(case_bounds())
    return offset(outline, amount=grow) if grow else outline


def _continuous_outline(span: Span) -> Sketch:
    (x_low, x_high), (y_low, y_high) = span
    corners = [(x_low, -y_low), (x_high, -y_low), (x_high, -y_high), (x_low, -y_high)]
    curves = [
        _corner_curve(corners[index - 1], corner, corners[(index + 1) % len(corners)])
        for index, corner in enumerate(corners)
    ]
    sides = [Line(curve @ 1, following @ 0) for curve, following in zip(curves, curves[1:] + curves[:1])]
    return Sketch() + make_face(Wire(curves + sides))


def _corner_curve(before: tuple[float, float], corner: tuple[float, float], after: tuple[float, float]) -> Bezier:
    """A quintic Bezier round `corner`. Three control points lie on each side, which is what makes
    the curvature zero at both ends."""
    def toward(point: tuple[float, float], share: float) -> tuple[float, float]:
        length = abs(point[0] - corner[0]) + abs(point[1] - corner[1])  # the sides are parallel to the axes
        step = CASE.corner_setback * share / length
        return corner[0] + (point[0] - corner[0]) * step, corner[1] + (point[1] - corner[1]) * step

    near, far = CASE.corner_handles[1], CASE.corner_handles[0]
    return Bezier(
        toward(before, 1.0), toward(before, far), toward(before, near),
        toward(after, near), toward(after, far), toward(after, 1.0),
    )


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
