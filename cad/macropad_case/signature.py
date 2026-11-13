"""The owner's signature, milled or printed into the underside: one flowing line and a caption.

The line is a single-stroke path, so a mill cuts it in one pass along the centre line with a cutter
as wide as the groove. Sizes follow the published limits for milled text in aluminium: groove at
least 0.46 mm wide, about 0.3 mm deep, at least 0.5 mm of metal between neighbouring strokes.
"""

from math import atan2, degrees, dist

from build123d import Plane, Pos, Rot, Sketch, SlotOverall, mirror

from .solids import legend
from .spec import BOARD, CENTRE_ROW, FRONT_ROW, Span, foot_span, label_field

GROOVE_WIDTH = 0.6  # one pass of a 0.6 mm end mill
GROOVE_DEPTH = 0.3
MIN_MILLED_GROOVE = 0.46  # narrowest milled stroke in soft metal, from Protolabs' milling guidelines
SCALE = 0.5  # mm per drawing unit: the line comes out 34 mm wide and 24 mm tall
CAPTION = "Signature Edition"
CAPTION_SIZE = 2.6  # too fine for the 0.6 mm cutter: an engraving cutter or a laser in the CNC variant
CAPTION_GAP = 2.4  # under the lowest point of the line
MARGIN = 1.5  # around the artwork, to the feet, the label field and the wall
_SEGMENTS_PER_CURVE = 8

# Cubic Bezier chains in drawing units, x to the right and y down, as read: start point, then three
# points per curve. An "O", a scribble, and a "B" whose upper lobe runs long.
_LETTER_O = [
    (21, 27), (20, 21), (12, 20), (7, 27), (2, 35), (5, 45), (14, 45), (22, 45), (27, 39), (25, 35),
    (23, 32), (18, 33), (17, 36),
]
_SCRIBBLE_AND_B = [
    (24, 38), (25, 34), (28, 33), (27, 38), (28, 35), (30, 34), (30, 38), (31, 35), (33, 34), (33, 38),
    (34, 35), (37, 35), (38, 38), (39, 41), (40, 43), (41, 40), (41, 46), (43, 52), (51, 52), (60, 52),
    (64, 45), (62, 38), (61, 34), (58, 32), (55, 32.5), (50.5, 33.5), (51.5, 37.5), (56.5, 36.2),
    (60, 35), (64, 31), (67, 25), (71, 17), (72, 9), (67, 6), (62, 3), (57, 8), (53, 15), (49, 22),
    (46, 26), (37, 28),
]
_STROKES = (_LETTER_O, _SCRIBBLE_AND_B)


def _points(chain: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The chain as a polyline, a fixed number of points per curve."""
    points = [chain[0]]
    for first in range(0, len(chain) - 1, 3):
        start, pull_start, pull_end, end = chain[first:first + 4]
        for step in range(1, _SEGMENTS_PER_CURVE + 1):
            t = step / _SEGMENTS_PER_CURVE
            weights = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3)
            points.append(tuple(
                sum(weight * point[axis] for weight, point in zip(weights, (start, pull_start, pull_end, end)))
                for axis in (0, 1)
            ))
    return points


def _line() -> Sketch:
    """The groove as read, in millimetres, centred on the origin, y up."""
    polylines = [[(x * SCALE, -y * SCALE) for x, y in _points(chain)] for chain in _STROKES]
    # One rounded slot per segment. A swept curve is not used: the scribble has cusps, which sweep
    # into an invalid face.
    slots = [
        Pos((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) * Rot(0, 0, degrees(atan2(b[1] - a[1], b[0] - a[0])))
        * SlotOverall(dist(a, b) + GROOVE_WIDTH, GROOVE_WIDTH)
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
    """The signature groove at its place in the floor, drawn as seen from above (mirrored: it is
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
