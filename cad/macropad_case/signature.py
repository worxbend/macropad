"""The owner's signature, laser-marked on the underside of the base: one flowing line and a caption.

Flat artwork only. A laser mark is a few hundredths of a millimetre deep, so nothing is cut into
the solids; the artwork goes out as DXF with the drawings, at its place on the underside.
"""

from functools import cache
from math import atan2, ceil, degrees, dist

from build123d import Plane, Pos, Rot, Sketch, SlotOverall, mirror

from .solids import legend
from .spec import BOARD, CENTRE_ROW, FRONT_ROW, Span, foot_span, label_field

LINE_WIDTH = 0.3
MIN_LASER_LINE = 0.18  # thinner lines may break up, from JLCCNC's laser-marking guide (0.5 pt)
SCALE = 0.37  # mm per drawing unit: the line comes out 34 mm wide and 19 mm tall
CAPTION = "Signature Edition"
CAPTION_SIZE = 2.6
CAPTION_GAP = 2.4  # under the lowest point of the line
MARGIN = 1.5  # around the artwork, to the feet, the label field and the wall
SEGMENT_LENGTH = 0.3  # mm of line per straight piece: the facets are far below what a laser resolves

# Cubic Bezier chains in drawing units, x to the right and y down, as read: start point, then three
# points per curve. A large "O", then "leksandr" in one joined stroke that runs on into a "B" whose
# upper lobe runs long.
_LETTER_O = [
    (21, 29), (20, 23), (12, 22), (7, 29), (2, 37), (5, 47), (14, 47), (22, 47), (27, 41), (25, 37), (23,
    34), (18, 35), (17, 38),
]
_LEKSANDR_B = [
    (24, 40), (26, 36), (29, 26), (28, 22), (27.5, 19), (25.5, 22), (26, 30), (26.2, 35), (26.5, 39), (28,
    40), (29.5, 40.5), (31, 37), (30, 35.5), (29, 34), (27.8, 37), (29, 39.5), (30, 41), (32, 40), (33,
    38), (34, 34), (35.5, 26), (35, 22), (34.5, 19), (33, 23), (33.5, 31), (33.7, 36), (33.8, 39), (34,
    40), (34.5, 36), (37, 34.5), (37, 36.5), (37, 38), (35, 37.5), (35, 37.5), (36.5, 38), (37.5, 40),
    (39, 40), (40, 39), (40.5, 36), (41, 35), (41.5, 37), (43, 39), (41.5, 40), (40.5, 40.5), (43, 40),
    (44, 38.5), (44.5, 36), (46, 34), (47.5, 35), (46, 34.5), (44.5, 38), (45.5, 39.8), (46.5, 41), (47.5,
    37), (47.8, 35), (47.8, 38), (48, 40), (49.5, 39.5), (50, 38), (50, 36), (50.5, 35), (50.5, 37),
    (50.5, 39), (50.5, 40), (51, 36), (53, 34), (53.5, 36), (53.8, 38), (53.8, 39.5), (55, 39.5), (54.5,
    36), (56, 34), (57.5, 35), (56, 34.5), (54.8, 38), (55.8, 39.8), (57, 41), (58, 36), (58.3, 30),
    (58.5, 26), (58.5, 23), (58.3, 21), (58, 28), (58, 37), (59.5, 40), (60.5, 38), (60.5, 36), (61, 35),
    (61.5, 36), (63, 35.5), (63.5, 36.5), (64.5, 40), (64, 44), (65, 48), (66.5, 54), (72, 56), (78, 55),
    (86, 54), (89, 46), (87, 40), (86, 36), (83, 34), (80, 35), (77, 36), (78, 38.5), (81, 38), (85, 37),
    (89, 33), (92, 27), (96, 19), (97, 11), (92, 8), (87, 5), (82, 10), (78, 17), (74, 24), (71, 28), (62,
    30),
]
_STROKES = (_LETTER_O, _LEKSANDR_B)


def _points(chain: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The chain as a polyline in drawing units, in pieces about SEGMENT_LENGTH long."""
    points = [chain[0]]
    for first in range(0, len(chain) - 1, 3):
        start, pull_start, pull_end, end = chain[first:first + 4]
        # The control polygon is never shorter than the curve.
        control_length = (dist(start, pull_start) + dist(pull_start, pull_end) + dist(pull_end, end)) * SCALE
        steps = max(4, ceil(control_length / SEGMENT_LENGTH))
        for step in range(1, steps + 1):
            t = step / steps
            weights = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3)
            points.append(tuple(
                sum(weight * point[axis] for weight, point in zip(weights, (start, pull_start, pull_end, end)))
                for axis in (0, 1)
            ))
    return points


@cache
def _line() -> Sketch:
    """The line as read, in millimetres, centred on the origin, y up."""
    polylines = [[(x * SCALE, -y * SCALE) for x, y in _points(chain)] for chain in _STROKES]
    # One rounded slot per segment. A swept curve is not used: the scribble has cusps, which sweep
    # into an invalid face.
    slots = [
        Pos((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) * Rot(0, 0, degrees(atan2(b[1] - a[1], b[0] - a[0])))
        * SlotOverall(dist(a, b) + LINE_WIDTH, LINE_WIDTH)
        for polyline in polylines for a, b in zip(polyline, polyline[1:])
    ]
    line = Sketch() + slots
    box = line.bounding_box()
    return Pos(-(box.min.X + box.max.X) / 2, -(box.min.Y + box.max.Y) / 2) * line


def free_field() -> Span:
    """Where the signature goes, in board coordinates: beside the centre pad, between the label
    field and the front foot, inside the board outline."""
    (_, pad_right), _ = foot_span(CENTRE_ROW)
    _, (_, label_bottom) = label_field()
    _, (front_foot_top, _) = foot_span(FRONT_ROW)
    return (pad_right, BOARD.board.width), (label_bottom, front_foot_top)


def line_height() -> float:
    box = _line().bounding_box()
    return box.max.Y - box.min.Y


def _block_height() -> float:
    return line_height() + CAPTION_GAP + CAPTION_SIZE


def _centre() -> tuple[float, float]:
    """Board position of the middle of the line; the caption hangs below it."""
    (x_low, x_high), (y_low, y_high) = free_field()
    block_top = (y_low + y_high) / 2 - _block_height() / 2
    return (x_low + x_high) / 2, block_top + line_height() / 2


def line() -> Sketch:
    """The signature line at its place on the underside, drawn as seen from above (mirrored: it is
    read from below)."""
    x, y = _centre()
    return Pos(x, -y) * mirror(_line(), Plane.YZ)


def caption() -> Sketch:
    x, y = _centre()
    return legend(CAPTION, CAPTION_SIZE, (x, y + line_height() / 2 + CAPTION_GAP + CAPTION_SIZE / 2), read_from_below=True)


def artwork() -> Sketch:
    return line() + caption()


def margin_in_field() -> float:
    """Smallest distance from the artwork to the edge of its free field. Negative: it does not fit."""
    box = artwork().bounding_box()
    (x_low, x_high), (y_low, y_high) = free_field()
    # Sketch Y is board Y negated.
    return min(box.min.X - x_low, x_high - box.max.X, -box.max.Y - y_low, y_high + box.min.Y)
