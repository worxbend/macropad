"""Print coupons: small pieces cut from the printed parts with boxes, to test one fit each before the
whole case is printed. Each coupon is the real part inside its box, turned the way that part prints,
and lowered onto the bed. Two add something the part does not have, kept apart in the checks: the
pilot-hole coupon ties its three bosses together on the bed, and the light channel gets a block where
the PCB edge would be."""

from dataclasses import dataclass, field
from math import cos, radians

from build123d import Location, Part, Plane, Pos, section

from .small_parts import BORE_END, PRINT_POSES, case_parts
from .solids import box, cylinder, overlap_volume
from .spec import BACK_ROW, BOARD, CASE, FRONT_ROW, LEVELS, PRINT, case_bounds, corner_holes, encoder_centres
from .spec import foot_span, grown, key_centres, led_slot_span, lens_recess

(LEFT, _), (BACK, FRONT_SIDE) = case_bounds()
PILOT_SIZES = (1.7, 1.8, 1.9)  # mm; the drawn pilot is 1.8
PILOT_GAP = 2.0  # mm between two bosses of the pilot-hole coupon
# The tie under the three pilot bosses reaches as high off the bed as the break-away chair would: the
# corner arc's 45 degree point. Without it the bosses are three loose pieces and the arc hangs in the air.
PILOT_TIE = CASE.print_corner_radius * (1 - cos(radians(45)))
LAP_COUPON = (27.0, 57.0)  # board X of the 30 mm of front wall the lap coupons are cut from
STAND_IN_WIDTH = 3.0  # mm of PCB-edge stand-in beside the light channel


@dataclass(frozen=True)
class Cut:
    """One box cut from a printed part, in the part's own frame. `shift` then moves the piece within
    the coupon, before the coupon is turned to its print pose. `pilot` replaces the pilot hole."""

    parent: str
    window: Part
    shift: Location = field(default_factory=Location)
    pilot: float | None = None


@dataclass(frozen=True)
class Coupon:
    name: str
    pose_of: str  # the part whose print pose the coupon takes
    cuts: tuple[Cut, ...]
    added: Part | None = None  # what the coupon has that its parent does not, in the coupon's own frame


def coupons() -> list[Coupon]:
    return [
        _pilot_holes(), _mx_cutout(), *_lap_pair(), _light_channel(), _knob_bore(), *_usb_pair(), _lens_recess_end(),
    ]


def _pilot_holes() -> Coupon:
    """The back-left corner boss three times, with a 1.7, 1.8 and 1.9 mm pilot hole, side by side on
    the bed. The holes lie along the layers, as in the top."""
    hole = min(corner_holes())
    window_y = (BACK, hole[1] + CASE.corner_boss_diameter / 2 + 1.0)
    window = box((LEFT, hole[0] + CASE.corner_boss_diameter / 2 + 0.8), window_y, (0, CASE.pilot_depth + 0.8))
    pitch = window_y[1] - window_y[0] + PILOT_GAP
    cuts = tuple(Cut("top", window, Pos(0, -index * pitch, 0), pilot) for index, pilot in enumerate(PILOT_SIZES))
    tie_y = (window_y[0], window_y[1] + (len(PILOT_SIZES) - 1) * pitch)
    tie = box((LEFT, LEFT + PILOT_TIE), tie_y, (0, CASE.pilot_depth + 0.8))
    return Coupon("pilot_holes", "top", cuts, tie)


def _mx_cutout() -> Coupon:
    """The first key of the middle row, with its 1.5 mm plate, the dish wall and the left frame."""
    x, y = key_centres()[BOARD.keys.columns]
    reach = (BOARD.keys.pitch - CASE.rib_width) / 2 - 0.1  # stops short of the ribs on either side
    window = box((LEFT, x + reach), (y - reach, y + reach), (0, LEVELS.deck_top))
    return Coupon("mx_cutout", "top", (Cut("top", window),))


def _lap_pair() -> list[Coupon]:
    """30 mm of the front lap ridge on the base and of its groove in the top."""
    inside = BOARD.board.height + CASE.pcb_gap - CASE.lap_groove_reach - 0.5
    # The base's box takes the whole foot strip recess under the wall: cut across, its roof would hang.
    ridge = box(LAP_COUPON, (_past_foot_recess(FRONT_ROW, -1), FRONT_SIDE + 1),
                (LEVELS.floor_bottom - 1, CASE.lap_height + 1))
    groove = box(LAP_COUPON, (inside, FRONT_SIDE + 1), (-1, LEVELS.plate_top))
    return [
        Coupon("lap_ridge", "base", (Cut("base", ridge),)),
        Coupon("lap_groove", "top", (Cut("top", groove),)),
    ]


def _light_channel() -> Coupon:
    """10 mm across the left light channel, with a block standing where the PCB edge is."""
    start, end = led_slot_span()
    middle = (start + end) / 2
    along = (middle - 5.0, middle + 5.0)
    window = box((LEFT - 1, STAND_IN_WIDTH), along, (LEVELS.floor_bottom - 1, 1))
    stand_in = box((0, STAND_IN_WIDTH), along, (LEVELS.floor_top, 0))
    return Coupon("light_channel", "base", (Cut("base", window),), stand_in)


def _knob_bore() -> Coupon:
    """The knob cut to a 10 mm square round its bore, from its foot to 1 mm over the end of the bore."""
    x, y = encoder_centres()[0]
    window = box((x - 5, x + 5), (y - 5, y + 5), (LEVELS.knob_bottom - 1, BORE_END + 1.0))
    return Coupon("knob_bore", "knob_left", (Cut("knob_left", window),))


def _usb_pair() -> list[Coupon]:
    """The USB opening's bite from each shell, 20 mm wide."""
    half = 10.0
    x_range = (BOARD.usb.x - half, BOARD.usb.x + half)
    y_range = (BACK - 1, BACK + 6.0)
    base_y_range = (BACK - 1, _past_foot_recess(BACK_ROW, 1))
    return [
        Coupon("usb_base", "base", (Cut("base", box(x_range, base_y_range, (LEVELS.floor_bottom - 1, 1))),)),
        Coupon("usb_top", "top", (Cut("top", box(x_range, y_range, (-1, LEVELS.deck_top + 1))),)),
    ]


def _lens_recess_end() -> Coupon:
    """The high-X end of the lens recess, the whole width of it: that end is a bridge while the top
    prints, and a box across only one corner would turn the bridge into a ledge."""
    (_, recess_end), (_, recess_front) = lens_recess(PRINT)
    window = box((recess_end - 6.0, recess_end + 3.0), (BACK, recess_front + 3.0), (0, LEVELS.deck_top + 1))
    return Coupon("lens_recess_end", "top", (Cut("top", window),))


def _past_foot_recess(row: str, side: int) -> float:
    """Board Y 1 mm past the foot strip recess under one row of screws, on the side `side` points to."""
    _, (back, front) = grown(foot_span(row), CASE.foot_recess_fit)
    return front + 1.0 if side > 0 else back - 1.0


def parent_piece(cut: Cut, parts: dict[str, Part]) -> Part:
    """What the parent part holds inside the cut's box, in the parent's frame, with the corner pilot
    hole changed to the cut's size when it asks for one."""
    piece = parts[cut.parent] & cut.window
    if cut.pilot is None:
        return piece
    hole = min(corner_holes())
    drilled = (-1, CASE.pilot_depth)
    filled = piece + (cylinder(hole, CASE.pilot_diameter, drilled) & cut.window)
    return filled - cylinder(hole, cut.pilot, drilled)


def assembled(coupon: Coupon, parts: dict[str, Part]) -> Part:
    """The coupon in its parent's frame, before it is turned to its print pose."""
    whole = Part() + [cut.shift * parent_piece(cut, parts) for cut in coupon.cuts]
    return whole + coupon.added if coupon.added is not None else whole


def placement(coupon: Coupon, solid: Part) -> Location:
    """Turns the coupon to its parent's print pose, centres it over the origin and lowers it onto the bed."""
    pose = PRINT_POSES[coupon.pose_of]
    bounds = (pose * solid).bounding_box()
    return Pos(-bounds.center().X, -bounds.center().Y, -bounds.min.Z) * pose


def on_the_bed(coupon: Coupon, solid: Part) -> Part:
    return placement(coupon, solid) * solid


def difference_from_parent(coupon: Coupon, parts: dict[str, Part], exported: Part, whole: Part) -> float:
    """Volume in mm^3 by which the coupon as exported differs from its parent inside each box,
    after it is turned back from the bed. What the coupon adds on purpose is left out of both."""
    back_home = placement(coupon, whole).inverse() * exported
    worst = 0.0
    for cut in coupon.cuts:
        mine = cut.shift.inverse() * back_home & cut.window
        theirs = parent_piece(cut, parts)
        if coupon.added is not None:
            kept_out = cut.shift.inverse() * coupon.added
            mine, theirs = mine - kept_out, theirs - kept_out
        shared = overlap_volume(mine, theirs)
        worst = max(worst, _volume(mine) + _volume(theirs) - 2 * shared)
    return worst


def _volume(part: Part) -> float:
    return sum(solid.volume for solid in part.solids())


def built(parts: dict[str, Part] | None = None) -> dict[str, Part]:
    """Every coupon as it is exported, by name."""
    parts = parts or case_parts(PRINT)
    return {coupon.name: on_the_bed(coupon, assembled(coupon, parts)) for coupon in coupons()}


def pilot_hole_sizes(solid: Part) -> list[float]:
    """Diameters of the pilot holes in the pilot-hole coupon as it lies on the bed, cut half-way
    down the holes. The bosses and the corner arcs are larger circles and are left out."""
    cut = section(solid, section_by=Plane.YZ.offset(solid.bounding_box().center().X))
    circles = [edge for edge in cut.edges() if edge.geom_type.name == "CIRCLE" and edge.radius < 1.2]
    return sorted({round(2 * edge.radius, 3) for edge in circles})
