"""The parts you print or mill, each in its assembled position."""

from math import sqrt

from build123d import Axis, Circle, Part, Plane, Polygon, Pos, Rectangle, Sketch, chamfer, extrude, mirror

from .solids import CUT_OVERSHOOT, box, centred_rectangle, cylinder, d_profile, discs, millable, pcb_outline
from .solids import rectangle, slab
from .spec import BOARD, CASE, CNC, LEVELS, PRINT, deck_front, encoder_centres, key_centres, led_slot_span
from .spec import mounting_holes

OUTER = CASE.wall + CASE.pcb_gap
FAR = 500.0
WIDTH = BOARD.board.width
HEIGHT = BOARD.board.height


def base(variant: str) -> Part:
    blank = slab(pcb_outline(OUTER), (LEVELS.floor_bottom, 0))
    body = chamfer(blank.edges().group_by(Axis.Z)[0], CASE.chamfer)
    cavity = pcb_outline(CASE.pcb_gap)
    bosses = discs(mounting_holes(), CASE.base_boss_diameter)
    body -= slab(millable(cavity, variant), (LEVELS.pcb_bottom, CUT_OVERSHOOT))
    body -= slab(millable(cavity - bosses, variant), (LEVELS.floor_top, LEVELS.pcb_bottom + CUT_OVERSHOOT))
    return body - _base_cuts()


def _base_cuts() -> list[Part]:
    under = LEVELS.floor_bottom - CUT_OVERSHOOT
    screw_holes = [cylinder(hole, BOARD.mounting.hole_diameter, (under, 0)) for hole in mounting_holes()]
    counterbores = [
        cylinder(hole, CASE.counterbore_diameter, (under, LEVELS.floor_bottom + CASE.counterbore_depth))
        for hole in mounting_holes()
    ]
    buttons = [BOARD.buttons.boot, BOARD.buttons.reset]
    button_holes = [
        cylinder((button.x, button.y), CASE.button_hole_diameter, (under, LEVELS.floor_top + CUT_OVERSHOOT))
        for button in buttons
    ]
    feet = [
        cylinder(centre, CASE.foot_diameter, (under, LEVELS.floor_bottom + CASE.foot_depth))
        for centre in _foot_centres()
    ]
    return [usb_cutout(), _led_slot(left=True), _led_slot(left=False)] + screw_holes + counterbores + button_holes + feet


def _foot_centres() -> list[tuple[float, float]]:
    inset = CASE.foot_inset
    return [(x, y) for x in (inset, WIDTH - inset) for y in (inset, HEIGHT - inset)]


def usb_cutout() -> Part:
    """Opening for the plug overmould. It is taller than the base wall above the receptacle,
    so the base and the top both take a bite of it."""
    width = CASE.usb_plug[0] + 2 * CASE.usb_margin
    height = CASE.usb_plug[1] + 2 * CASE.usb_margin
    return box(
        (BOARD.usb.x - width / 2, BOARD.usb.x + width / 2),
        (-OUTER - 1, 0),
        (LEVELS.usb_centre - height / 2, LEVELS.usb_centre + height / 2),
    )


def _led_slot(left: bool) -> Part:
    """Open-topped slot through a side wall: the top's skirt closes it, so it prints without a bridge."""
    x_range = (-OUTER - 1, 0) if left else (WIDTH, WIDTH + OUTER + 1)
    return box(x_range, led_slot_span(), (LEVELS.led_slot_bottom, CUT_OVERSHOOT))


def top(variant: str) -> Part:
    body = _top_blank()
    cavity = pcb_outline(CASE.pcb_gap)
    bosses = discs(mounting_holes(), CASE.top_boss_diameter)
    deck_zone = rectangle((-FAR, FAR), (-FAR, deck_front() - CASE.deck_front_wall))
    pockets = [
        (cavity - bosses, (-CUT_OVERSHOOT, LEVELS.plate_bottom)),
        ((cavity & deck_zone) - bosses, (LEVELS.plate_bottom - CUT_OVERSHOOT, LEVELS.deck_bottom)),
        (_display_relief(), (LEVELS.deck_bottom - CUT_OVERSHOOT, LEVELS.deck_bottom + CASE.display_relief)),
        (_switch_cutouts(variant), (LEVELS.plate_bottom - CUT_OVERSHOOT, LEVELS.plate_top + CUT_OVERSHOOT)),
        (_deck_openings(), (LEVELS.deck_bottom - CUT_OVERSHOOT, LEVELS.deck_top + CUT_OVERSHOOT)),
    ]
    for pocket, z_range in pockets:
        body -= slab(millable(pocket, variant), z_range)
    if variant == PRINT:
        body += _print_gussets()
    pilot_holes = [
        cylinder(hole, CASE.pilot_diameter, (-CUT_OVERSHOOT, CASE.pilot_depth)) for hole in mounting_holes()
    ]
    return body - pilot_holes - usb_cutout()


def _top_blank() -> Part:
    full_height = slab(pcb_outline(OUTER), (0, LEVELS.deck_top))
    above_the_keys = box((-FAR, FAR), (deck_front(), FAR), (LEVELS.plate_top, FAR))
    stepped = full_height - above_the_keys
    return chamfer(stepped.edges().group_by(Axis.Z)[-1], CASE.chamfer)


def _display_relief() -> Sketch:
    display = BOARD.display
    margin = 2 * CASE.display_relief_margin
    return centred_rectangle((display.x, display.y), (display.length + margin, display.width + margin))


def _switch_cutouts(variant: str) -> Sketch:
    side = BOARD.stack.switch_cutout
    cutout = Rectangle(side, side)
    if variant == CNC:
        cutout += _dog_bones(side)
    return Sketch() + [Pos(x, -y) * cutout for x, y in key_centres()]


def _dog_bones(side: float) -> list[Sketch]:
    """Corner reliefs: a round tool cannot cut the square corner an MX switch needs."""
    radius = CASE.cnc_corner_radius
    centre = side / 2 - radius / sqrt(2)
    return [Pos(sign_x * centre, sign_y * centre) * Circle(radius) for sign_x in (-1, 1) for sign_y in (-1, 1)]


def _deck_openings() -> Sketch:
    display = BOARD.display
    bushing_hole = BOARD.stack.encoder_bushing_diameter + CASE.bushing_clearance
    window = centred_rectangle((display.window_x, display.window_y), (display.window_length, display.window_width))
    return window + discs(encoder_centres(), bushing_hole)


def _print_gussets() -> list[Part]:
    """45 degree fillers under the side walls. The top prints standing on one side wall,
    so without them the other side wall would start in mid-air."""
    back, front = -CASE.pcb_gap, HEIGHT + CASE.pcb_gap
    deck_back_of_wall = deck_front() - CASE.deck_front_wall
    gussets = []
    for wall_x, inward in ((-CASE.pcb_gap, 1), (WIDTH + CASE.pcb_gap, -1)):
        gussets.append(_gusset(wall_x, inward * LEVELS.plate_bottom, (back, front)))
        gussets.append(_gusset(wall_x, inward * LEVELS.deck_bottom, (back, deck_back_of_wall)))
    return gussets


def _gusset(wall_x: float, signed_leg: float, y_range: tuple[float, float]) -> Part:
    leg = abs(signed_leg)
    profile = Plane.XZ * Polygon((wall_x, 0), (wall_x, leg), (wall_x + signed_leg, leg), align=None)
    toward_front = (0, -1, 0)
    return Pos(0, -y_range[0], 0) * extrude(profile, y_range[1] - y_range[0], dir=toward_front)


def diffuser_left() -> Part:
    """Translucent strip for the left wall. Its flange sits behind the wall under the slot,
    and a lip beside the PCB edge stops it from falling inward once the PCB is in."""
    fit = CASE.diffuser_fit
    slot_start, slot_end = led_slot_span()
    stem_y = (slot_start + fit, slot_end - fit)
    flange_y = (slot_start - CASE.diffuser_flange_overlap, slot_end + CASE.diffuser_flange_overlap)
    inner_face = -CASE.pcb_gap + 0.1
    stem = box((-OUTER, inner_face), stem_y, (LEVELS.led_slot_bottom + fit, -0.1))
    lip = box((inner_face, -CASE.diffuser_to_pcb), stem_y, (LEVELS.pcb_bottom, -0.1))
    flange_top = LEVELS.pcb_bottom - CASE.diffuser_flange_top_below_pcb
    flange = box((inner_face, inner_face + CASE.diffuser_flange), flange_y, (LEVELS.floor_top + 0.1, flange_top))
    return stem + lip + flange


def diffuser_right() -> Part:
    return mirror(diffuser_left(), Plane.YZ.offset(WIDTH / 2))


def knob() -> Part:
    """One knob at the origin in X and Y, at its assembled height."""
    blank = cylinder((0, 0), CASE.knob_diameter, (LEVELS.knob_bottom, LEVELS.knob_top))
    body = chamfer(blank.edges().group_by(Axis.Z)[-1], 1.0)
    bushing_pocket_diameter = BOARD.stack.encoder_bushing_diameter + 1.0
    bushing_pocket = cylinder(
        (0, 0), bushing_pocket_diameter, (LEVELS.knob_bottom - CUT_OVERSHOOT, LEVELS.bushing_top + 0.5)
    )
    clearance = CASE.knob_bore_clearance
    d_bore = d_profile(CASE.shaft_diameter + clearance, CASE.shaft_flat + clearance)
    bore = slab(d_bore, (LEVELS.knob_bottom, BOARD.stack.encoder_shaft_top + 0.3))
    return body - bushing_pocket - bore


def knobs() -> list[Part]:
    return [Pos(x, -y, 0) * knob() for x, y in encoder_centres()]


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
    }
