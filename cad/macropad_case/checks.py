"""Fit checks: interference between every part and component, named clearances, measurements on the
finished solids, and printability. `run_all` gathers them; `failures` lists what did not pass."""

from itertools import combinations
from math import pi, sqrt

import numpy as np
import trimesh
from build123d import Box, Part, Pos, Rot

from . import measure, printsim, selftest, signature
from .components import MX_FLANGE, at, components, display_room, encoder, keycap, led, pcb, worst_keycap_skirt
from .parts import base_body, drill_point_height, printed_text, socket_post_top, switch_cutout_length, top_chairs
from .parts import underside_mark, usb_cutout
from .small_parts import BAR_TO_TOP, case_parts, desk_plane_drop, knob_crush_ribs, knob_pointer_outline, lens_outline
from .small_parts import tilt_bar_body
from .solids import case_outline, overlap_volume, rectangle, slab, stadium
from .spec import BACK_ROW, BOARD, CASE, CNC, FRONT_ROW, LEVELS, PRINT, VARIANTS, buttons, bushing_hole, case_bounds
from .spec import dish_rim, encoder_centres, foot_span, grown, key_centres, knob_well_diameter, label_field
from .spec import lens_opening, lens_recess, lens_span, screw_length, screw_seat

CLASH_VOLUME = 0.05  # mm^3; below this two solids only touch
OVERHANG_COSINE = 0.72  # faces steeper than about 46 degrees from vertical need something under them
BED_TOLERANCE = 0.05
MIN_BED_CONTACT = 100.0  # mm^2 of first layer, so the part stays on the bed
# The tilt bar's tongue takes the back strip's recess, so that strip moves onto the bar.
ALTERNATIVES = {frozenset(("tilt_bar", "foot_strip_back"))}
# Pairs that are meant to overlap: each knob's crush ribs press into its encoder's shaft. Only the ribs
# may overlap it, by the volume they have inside the shaft; any other overlap is a clash.
PRESS_FITS = {frozenset((f"knob_{side}", f"encoder_{side}")): index for index, side in enumerate(("left", "right"))}
# Printed parts whose horizontal faces must lie on the 0.2 mm layer grid. The top is not one: it prints
# standing, so its faces across the layers sit at the board's key and encoder positions.
LAYERED_PARTS = ("base", "diffuser_left", "knob_left", "foot_strip_back", "centre_pad", "tilt_bar")
LENS_PUSH = 0.3  # mm; the lens must hit its ledges before it has moved this far down
# A height at which each shell's outline has its full size: above the underside chamfer, and in the plate.
OUTLINE_HEIGHTS = {"base": LEVELS.floor_bottom + CASE.underside_chamfer + 0.5, "top": LEVELS.plate_bottom + 0.5}
MIN_CORNER_RADIUS = 5.1  # mm; the corner curve is drawn for 5.15
M2_THREAD = 2.0  # mm, major diameter
MIN_PRINTED_PILOT = 1.6  # mm; in a smaller hole the M2 screw splits the boss
MAX_PRINTED_PILOT = 1.75  # mm; in a larger hole the thread has too little to cut into
PCB_THICKNESS_TOLERANCE = 0.1  # share of the nominal thickness, as the board houses state it
MAX_GAP_GROWTH = 0.2  # mm the gap may open before it reads as a fault
LENS_SHEET_TOLERANCE = 0.1  # mm; guess: how much thicker than nominal a 1.0 mm sheet may be
CHAMFER_CUTTER = (8.0, 0.5)  # mm; a common 90 degree chamfer mill and the flat its tip may have
MIN_STROKE = 0.45  # mm; one line of a 0.4 mm nozzle
# mm; engraved into the face on the bed, a slot loses about 0.2 mm to the squeezed first layer and to
# elephant's foot compensation, and must still be wider than one line.
MIN_BED_ENGRAVING = 0.7
MAX_ASPECT = 11.0  # a part taller than this many times its narrow side tips over while it prints
BRIM_ASPECT = 6.0  # above this, print with a brim
MAX_SHOW_FACE_OVERHANG = 45.0  # degrees from vertical, on the outside of the printed top
MAX_LENS_REVEAL_SPREAD = 0.05  # mm between the widest and the narrowest reveal round the printed lens
MAX_TOOL_DEPTH_RATIO = 3.0  # deepest pocket over the 3 mm end mill's diameter: a stock cutter has 9 mm of flute
FOAM_SOLID_SHARE = 0.2  # guess: a foam ring squeezed to this share of its free thickness is solid
# mm the frame round the key dish may widen at its corners. Not zero: the dish rim cannot be made
# concentric with the outline while the foot strips cover the corner screws (see cad/README.md).
FRAME_SWELL_LIMITS = {"print": 0.65, "cnc": 1.2}
MIN_TAPE_AREA = 30.0  # mm^2 of tape under the lens
MIN_BEARING_SHARE = 0.8  # of a foot's face must lie on the base
MIN_SEAT_AREA = (150.0, 5.0)  # mm^2 the top rests on in all, and at least on each of the four sides

# How each part lies on the print bed: a rotation that brings its bed face to the lowest Z.
PRINT_POSES = {
    "base": Rot(0, 0, 0),
    "top": Rot(0, -90, 0),  # standing on its left side wall
    "diffuser_left": Rot(0, -90, 0),  # outer face down
    "knob_left": Rot(180, 0, 0),  # top face down, so it takes the finish of the bed and every cavity opens upward
    "foot_strip_back": Rot(0, 0, 0),
    "centre_pad": Rot(0, 0, 0),
    "tilt_bar": Rot(CASE.tilt_angle, 0, 0),  # sloped underside down
}


def interference(variant: str) -> dict:
    parts = case_parts(variant)
    bought = components(variant)
    pairs = [(part, component) for part in parts for component in bought] + list(combinations(parts, 2))
    pairs = [pair for pair in pairs if frozenset(pair) not in ALTERNATIVES]
    solids = parts | bought
    clashes = []
    for first, second in pairs:
        volume = overlap_volume(solids[first], solids[second])
        if frozenset((first, second)) in PRESS_FITS:
            shaft = solids[first if first.startswith("encoder") else second]
            volume -= overlap_volume(_placed_ribs(PRESS_FITS[frozenset((first, second))]), shaft)
        if volume > CLASH_VOLUME:
            clashes.append({"first": first, "second": second, "volume_mm3": round(volume, 3)})
    return {"variant": variant, "pairs": len(pairs), "clashes": clashes}


def _placed_ribs(knob_index: int) -> Part:
    x, y = encoder_centres()[knob_index]
    return Pos(x, -y, 0) * (Part() + knob_crush_ribs())


def clearances() -> list[dict]:
    """Named gaps in millimetres, each with the minimum it must keep. These come from the dimensions."""
    stack = BOARD.stack
    display = BOARD.display
    led_height = CASE.led_body[2]
    window_margin = min(
        display.length / 2 - abs(display.window_x - display.x) - display.window_length / 2,
        display.width / 2 - abs(display.window_y - display.y) - display.window_width / 2,
    )
    measured = [
        ("usb_plug_to_opening", _usb_opening_margin(), 0.4),
        ("keycap_to_deck", BOARD.keys.first_y - CASE.keycap_width / 2 - dish_rim()[1][0], 0.4),
        ("display_glass_under_deck", LEVELS.lens_bottom - stack.display_glass_top, 0.2),
        ("display_window_inside_module", window_margin, 0.5),
        ("encoder_body_under_deck", LEVELS.deck_bottom - stack.encoder_body_top, 0.3),
        *_screw_margins(),
        ("knob_to_well_floor_when_pressed", LEVELS.knob_bottom - LEVELS.knob_well_floor - CASE.encoder_press_travel, 0.3),
        *_knob_seat_margins(),
        ("skin_under_knob_well", LEVELS.knob_well_floor - LEVELS.deck_bottom, CASE.min_wall),
        ("lens_ledge_thickness", LEVELS.lens_seat - LEVELS.lens_rib_bottom, CASE.min_wall),
        ("rib_to_switch_cutout", (BOARD.keys.pitch - stack.switch_cutout - CASE.rib_width) / 2, 1.0),
        ("skirt_beside_lap_groove", CASE.wall - CASE.lap_crest - CASE.lap_height - CASE.lap_fit, CASE.min_wall),
        ("lap_groove_under_ribs", LEVELS.rib_bottom - CASE.lap_height - CASE.lap_fit, 0.0),
        ("floor_under_engraving", CASE.floor - CASE.engraving_depth, CASE.min_wall),
        ("plate_under_engraving", stack.plate_thickness - CASE.engraving_depth, CASE.min_wall),
        ("socket_to_floor", stack.underside_clearance - stack.socket_depth, 1.0),
        ("usb_body_to_floor", stack.underside_clearance - BOARD.usb.body_height, 0.5),
        ("led_inside_slot_height", LEVELS.pcb_bottom - led_height - LEVELS.led_slot_bottom, 0.5),
        ("foot_below_underside", CASE.foot_strip[1] - CASE.foot_recess_depth, 0.5),
        *_board_support_margins(),
        *_tilt_bar_margins(), *_top_face_margins(), *_lens_margins(), *_light_line_margins(), *_underside_margins(),
    ]
    return [
        {"name": name, "value_mm": round(value, 3), "minimum_mm": minimum, "ok": value >= minimum - 1e-9}
        for name, value, minimum in measured
    ]


def _knob_seat_margins() -> list[tuple[str, float, float]]:
    """The knob seats on the end of its shaft. A shaft up to `shaft_length_tolerance` short lets it sit
    that much lower; pressed, it must still clear its well and the bushing inside it."""
    press, short = CASE.encoder_press_travel, CASE.shaft_length_tolerance
    well_floor_pressed = LEVELS.knob_bottom - LEVELS.knob_well_floor - press
    over_bushing_pressed = LEVELS.knob_bushing_roof - LEVELS.bushing_top - press
    interference = CASE.knob_rib_interference
    return [
        ("knob_to_well_floor_short_shaft", well_floor_pressed - short, 0.0),
        ("knob_pocket_to_bushing_when_pressed", over_bushing_pressed, 0.3),
        ("knob_pocket_to_bushing_short_shaft", over_bushing_pressed - short, 0.3),
        ("knob_rib_interference", interference, 0.08),
        ("knob_rib_interference_headroom", 0.2 - interference, 0.0),
        ("bushing_to_hole_after_shrink",
         (bushing_hole(PRINT) - CASE.print_hole_shrink - BOARD.stack.encoder_bushing_diameter) / 2, 0.2),
        ("cnc_bushing_to_hole", (bushing_hole(CNC) - BOARD.stack.encoder_bushing_diameter) / 2, 0.2),
    ]


def _board_support_margins() -> list[tuple[str, float, float]]:
    """What holds the PCB: foam rings on the base bosses press it up against the top's bosses on any
    board within tolerance, and posts under the sockets carry it while switches are pressed in."""
    free, room, _ = CASE.boss_ring
    tolerance = BOARD.board.thickness * PCB_THICKNESS_TOLERANCE
    foam_free, _ = CASE.display_foam
    socket_bottom = LEVELS.pcb_bottom - BOARD.stack.socket_depth
    return [
        ("pcb_clamped_thin_pcb", free - (room + tolerance), 0.0),
        ("boss_ring_not_solid_thick_pcb", room - tolerance, FOAM_SOLID_SHARE * free),
        ("display_foam_compression", foam_free - display_room(), 0.5),
        # A guess: squeezed to less than half, open-cell foam takes a set and stops holding the module up.
        ("display_foam_squeezed_under_half", display_room() - foam_free / 2, 0.0),
        ("socket_post_to_socket", socket_bottom - socket_post_top(), 0.05),
        ("socket_post_gap_headroom", 0.2 - (socket_bottom - socket_post_top()), 0.0),
    ]


def _tilt_bar_margins() -> list[tuple[str, float, float]]:
    """The tilt bar must leave the back screws and the two button holes reachable."""
    button_y = min(y for _, y in buttons().values())
    hole_around_counterbore = (CASE.tilt_hole_diameter - CASE.counterbore_diameter) / 2
    return [
        ("tilt_bar_to_screw_counterbore", hole_around_counterbore, 0.5),
        ("tilt_bar_to_button_hole", button_y - CASE.button_hole_diameter / 2 - CASE.tilt_bar_front, 0.5),
        ("tilt_bar_thinnest", desk_plane_drop(CASE.tilt_bar_front), 3.0),
    ]


def _screw_engagement(variant: str) -> float:
    """Length of screw inside the top: what is left of it above the PCB."""
    under_head = LEVELS.pcb_bottom - screw_seat(variant)
    return screw_length(variant) - under_head - BOARD.board.thickness


def _screw_margins() -> list[tuple[str, float, float]]:
    """Print: an M2 x 10 cuts its thread in a printed pilot hole. CNC: an M2 x 8 in a tapped blind
    hole, where the full thread ends before the hole does and the drill point comes on top."""
    engagement, cnc_engagement = _screw_engagement(PRINT), _screw_engagement(CNC)
    head_diameter, head_height = CASE.screw_head
    printed_pilot = CASE.pilot_diameter - CASE.print_hole_shrink
    drill_end = CASE.cnc_tap_drill[1] + drill_point_height()
    return [
        ("screw_engagement", engagement, CASE.min_screw_engagement),
        ("screw_tip_to_hole_end", CASE.pilot_depth - engagement, 0.6),
        ("skin_over_screw_hole", LEVELS.plate_top - CASE.pilot_depth, CASE.min_wall),
        ("screw_head_below_underside", CASE.counterbore_depth - head_height, 0.2),
        ("screw_head_in_counterbore", (CASE.counterbore_diameter - head_diameter) / 2, 0.2),
        ("print_pilot_after_shrink", printed_pilot, MIN_PRINTED_PILOT),
        ("print_pilot_thread_bite", (M2_THREAD - printed_pilot) / 2, (M2_THREAD - MAX_PRINTED_PILOT) / 2),
        ("cnc_screw_engagement", cnc_engagement, CASE.cnc_min_screw_engagement),
        ("cnc_full_thread_past_screw_tip", CASE.cnc_full_thread - cnc_engagement, 0.5),
        ("cnc_skin_over_drill_point", LEVELS.plate_top - drill_end, CASE.min_wall),
        # At the drawing's depth limit the skin under the dish floor is thinner than the wall rule; the
        # limit only bounds a drill that runs 0.1 deep, so it is held to 0.7 here.
        ("cnc_skin_over_deepest_drill_point", LEVELS.plate_top - CASE.cnc_tap_drill_limit - drill_point_height(), 0.7),
        ("cnc_screw_head_below_underside", CASE.cnc_counterbore_depth - head_height, 0.2),
    ]


def _top_face_margins() -> list[tuple[str, float, float]]:
    """The key dish, and the knobs in their wells."""
    widest_hole = max(bushing_hole(variant) for variant in VARIANTS)
    grooved_radius = CASE.knob_diameter / 2 - CASE.knob_groove_depth
    groove_pitch = pi * CASE.knob_diameter / CASE.knob_grooves
    (left_x, knob_y), (right_x, _) = encoder_centres()
    well_radius = knob_well_diameter() / 2
    well_to_recess = min(
        min(lens_recess(variant)[0][0] - (left_x + well_radius), (right_x - well_radius) - lens_recess(variant)[0][1])
        for variant in VARIANTS
    )
    dish_depth = LEVELS.deck_top - LEVELS.plate_top
    cutter_diameter, tip_flat = CHAMFER_CUTTER
    return [
        ("switch_flange_to_dish_floor", CASE.dish_floor_margin - MX_FLANGE[0] / 2, 0.25),
        ("deck_wall_under_dish", CASE.deck_front_wall / sqrt(2), CASE.min_wall),
        ("knob_covers_bushing_hole", grooved_radius - widest_hole / 2, 3.0),
        ("knob_groove_land", groove_pitch - 2 * CASE.knob_groove_depth, 0.45),
        ("knob_well_to_lens_recess", well_to_recess, 1.0),
        ("knob_well_to_dish_rim", dish_rim()[1][0] - (knob_y + well_radius), 1.0),
        ("print_switch_cutout_after_sag", switch_cutout_length(PRINT) - CASE.print_bridge_sag, BOARD.stack.switch_cutout),
        ("cnc_dish_wall_inside_8mm_chamfer_cutter", cutter_diameter - tip_flat - 2 * dish_depth, 0.0),
    ]


def _lens_margins() -> list[tuple[str, float, float]]:
    """Each row is the smaller of the two variants: the print's recess is the looser one."""
    display = BOARD.display
    half_length, half_width = display.length / 2, display.width / 2
    module = (display.x - half_length, display.x + half_length), (display.y - half_width, display.y + half_width)
    (lens_start, _), _ = lens_span()
    (_, _), (print_back, print_front) = lens_recess(PRINT)
    knob_edge = encoder_centres()[0][0] + CASE.knob_diameter / 2
    air_gap = LEVELS.lens_bottom - BOARD.stack.display_glass_top
    pin_tops = BOARD.stack.display_glass_top - CASE.display_thickness + CASE.display_board_thickness + CASE.header_pin_height
    glass_length, glass_width = CASE.display_glass
    return [
        ("display_module_inside_opening", min(_inside(module, lens_opening(variant)) for variant in VARIANTS), 0.3),
        ("lens_below_flush", LEVELS.deck_top - LEVELS.lens_top, 0.0),
        ("lens_not_proud_thick_sheet", LEVELS.deck_top - LEVELS.lens_top - LENS_SHEET_TOLERANCE, 0.0),
        ("lens_end_ledge", min(_end_ledge(variant) for variant in VARIANTS), 1.0),
        ("lens_to_knob", lens_start - knob_edge, 1.0),
        ("lens_to_dish_rim", dish_rim()[1][0] - print_front, 1.0),
        ("lens_recess_bridge_margin", CASE.max_bridge - (print_front - print_back), 0.0),
        ("print_lens_fit_after_bridge_sag", CASE.print_lens_fit + CASE.print_lens_end_room - CASE.print_bridge_sag, 0.0),
        ("lens_to_glass_under_press", air_gap - _lens_sag(), 0.2),
        ("header_pins_under_lens", LEVELS.lens_bottom - pin_tops, 0.5),
        ("lens_mask_window_inside_glass",
         min(glass_length - display.mask_window_length, glass_width - display.window_width) / 2, 0.5),
        ("lens_mask_window_inside_module", _mask_window_margin(), 0.5),
    ]


def _mask_window_margin() -> float:
    """Smallest distance from the lens mask's window to the ends of the display module, along it."""
    display = BOARD.display
    half_window = display.mask_window_length / 2
    module_start, module_end = display.x - display.length / 2, display.x + display.length / 2
    return min(display.mask_window_x - half_window - module_start, module_end - display.mask_window_x - half_window)


def _inside(inner: tuple, outer: tuple) -> float:
    """Smallest distance from the `inner` span to the edge of the `outer` one, on the four sides."""
    return min(
        low_or_high for (inner_low, inner_high), (outer_low, outer_high) in zip(inner, outer)
        for low_or_high in (inner_low - outer_low, outer_high - inner_high)
    )


def _end_ledge(variant: str) -> float:
    """Width of the narrower of the two ledges the lens rests on."""
    (recess_start, recess_end), _ = lens_recess(variant)
    (opening_start, opening_end), _ = lens_opening(variant)
    return min(opening_start - recess_start, recess_end - opening_end)


def _lens_sag() -> float:
    """How far the middle of the lens moves down under `lens_press_load`, as a beam that lies loose
    on its two ledges across the opening. The tape clamps the ends a little, so the real figure is smaller."""
    _, width, thickness = CASE.lens
    second_moment = width * thickness ** 3 / 12
    return CASE.lens_press_load * CASE.lens_opening_length ** 3 / (48 * CASE.lens_modulus * second_moment)


def _light_line_margins() -> list[tuple[str, float, float]]:
    """The gap round the case and the light bar behind it."""
    rim_wall = CASE.wall - CASE.gap_depth
    slit = CASE.gap_height - BAR_TO_TOP
    thicker_pcb = BOARD.board.thickness * PCB_THICKNESS_TOLERANCE  # the top then rides this much higher
    # The bar's visible face lies this far behind the outer face of the case.
    set_back = CASE.wall - CASE.light_channel_reach + CASE.light_bar_skin_fit
    return [
        ("gap_land_beside_lap_ridge", rim_wall - CASE.lap_crest - CASE.lap_height, 0.2),
        ("light_skin", CASE.wall - CASE.light_channel_reach, CASE.min_wall),
        ("light_slit_height", slit, 0.8),
        # Seen from 45 degrees above, past the chamfered lower edge of the top, the top hides the gap
        # down to as far as the bar is set back behind that edge.
        ("light_line_visible_at_45deg", min(slit, CASE.gap_height - (set_back - CASE.seam_chamfer)), 0.6),
        ("led_to_light_bar", CASE.diffuser_to_pcb + CASE.light_bar_lip, 0.1),
        ("pcb_edge_to_light_bar_lip", CASE.diffuser_to_pcb, 0.15),
        ("gap_growth_room_thick_pcb", MAX_GAP_GROWTH - thicker_pcb, 0.0),
        ("lap_overlap_thick_pcb", CASE.lap_height - thicker_pcb, 0.3),
    ]


def _underside_margins() -> list[tuple[str, float, float]]:
    """The foot strips hide the screws; the recesses must leave enough floor and enough flat round them."""
    head_height = CASE.screw_head[1]
    skin_top = LEVELS.foot_recess_roof + CASE.screw_skin
    return [
        ("screw_head_under_strip_recess", screw_seat(PRINT) - head_height - LEVELS.foot_recess_roof, 0.2),
        ("cnc_screw_head_under_strip_recess", screw_seat(CNC) - head_height - LEVELS.foot_recess_roof, 0.2),
        ("strip_covers_counterbore", (CASE.foot_strip[0] - CASE.counterbore_diameter) / 2, 1.0),
        ("floor_under_strip_recess", CASE.floor - CASE.foot_recess_depth, CASE.min_wall),
        ("screw_skin_inside_floor", LEVELS.floor_top - skin_top, 0.5),
        ("pad_lower_than_strips", CASE.foot_strip[1] - CASE.centre_pad_thickness, 0.1),
        ("floor_under_label_engraving", CASE.floor - CASE.engraving_depth, CASE.min_wall),
        # Print: a flat narrower than this lifts at the stadium ends on the first layer.
        ("chamfer_to_strip_recess", _flat_round_strip_recesses(PRINT), 0.6),
        ("cnc_chamfer_to_strip_recess", _flat_round_strip_recesses(CNC), 0.4),
        ("signature_inside_free_field", signature.margin_in_field(), signature.MARGIN),
        ("signature_line_laser_markable", signature.LINE_WIDTH, signature.MIN_LASER_LINE),
    ]


def _flat_round_strip_recesses(variant: str) -> float:
    """Narrowest flat between the underside chamfer and a foot strip recess, measured on the variant's
    own outline, so the corner curves count."""
    chamfer_band = slab(case_outline(variant) - case_outline(variant, -CASE.underside_chamfer), (0, 1))
    return min(
        slab(stadium(grown(foot_span(row), CASE.foot_recess_fit)), (0, 1)).distance_to(chamfer_band)
        for row in (BACK_ROW, FRONT_ROW)
    )


def _usb_opening_margin() -> float:
    """Smallest gap between the plug overmould and the opening, across the width and the height."""
    width, height = CASE.usb_plug
    opening = usb_cutout() & Pos(BOARD.usb.x, CASE.back_wall / 2 + CASE.pcb_gap, LEVELS.usb_centre) * _slice_of_wall()
    box = opening.bounding_box()
    return min((box.size.X - width) / 2, (box.size.Z - height) / 2)


def _slice_of_wall() -> Part:
    """A thin slab in the middle of the back wall, where the opening is at its narrowest."""
    return Box(100, 0.2, 100)


def moving_parts(parts: dict[str, Part]) -> list[dict]:
    """Gaps measured between solids, with the keys and the knobs pushed all the way down."""
    back_left_key, back_right_key = key_centres()[0], key_centres()[BOARD.keys.columns - 1]
    knob_pressed = Pos(0, 0, -CASE.encoder_press_travel) * parts["knob_left"]
    # On a shaft at the short end of its tolerance, pressed.
    knob_low = Pos(0, 0, -CASE.encoder_press_travel - CASE.shaft_length_tolerance) * parts["knob_left"]
    return [
        measure.row("pressed_keycap_to_top", at(back_left_key, worst_keycap_skirt()).distance_to(parts["top"]), 0.4),
        measure.row("keycap_to_knob", at(back_left_key, keycap()).distance_to(parts["knob_left"]), 2.0),
        measure.row("keycap_to_knob_right", at(back_right_key, keycap()).distance_to(parts["knob_right"]), 2.0),
        measure.row("pressed_knob_to_top", knob_pressed.distance_to(parts["top"]), 0.3),
        measure.row("knob_to_top", parts["knob_left"].distance_to(parts["top"]), 0.8),
        measure.row("pressed_knob_to_bushing", knob_low.distance_to(_bushing(encoder_centres()[0])), 0.3),
    ]


def _bushing(centre: tuple[float, float]) -> Part:
    """The encoder's threaded bushing alone: what a knob that sits low must not land on."""
    whole = encoder(centre)
    return whole & Pos(centre[0], -centre[1], (BOARD.stack.encoder_body_top + LEVELS.bushing_top) / 2) * Box(
        20, 20, LEVELS.bushing_top - BOARD.stack.encoder_body_top
    )


def measurements() -> list[dict]:
    """Everything measured on the finished solids rather than computed from the dimensions."""
    printed, milled = case_parts(PRINT), case_parts(CNC)
    shells = {
        "print_base": printed["base"], "print_top": printed["top"], "cnc_base": milled["base"], "cnc_top": milled["top"],
    }
    bodies = {
        "print_base": base_body(PRINT), "print_top": printed["top"], "cnc_base": milled["base"],
        "cnc_top": milled["top"], "diffuser": printed["diffuser_left"], "knob": printed["knob_left"],
        "tilt_bar": tilt_bar_body(), "foot_strip": printed["foot_strip_back"], "centre_pad": printed["centre_pad"],
    }
    rows = [
        measure.row(f"thinnest_wall_{name}", measure.thinnest_wall(body), CASE.min_wall) for name, body in bodies.items()
    ]
    rows += _soundness(printed, milled)
    rows += _silhouette(shells)
    rows += [
        measure.row(f"{variant}_frame_swell_at_dish_corners", measure.frame_swell(shells[f"{variant}_top"]), limit,
                    kind="max")
        for variant, limit in FRAME_SWELL_LIMITS.items()
    ]
    rows += measure.boss_walls(printed["base"], printed["top"])
    rows += measure.diffuser_retention(printed["diffuser_left"], printed["base"], printed["top"])
    rows += measure.lap_joint(printed["base"], printed["top"])
    rows += [dict(found, name=f"cnc_{found['name']}") for found in measure.lap_joint(milled["base"], milled["top"])]
    rows += moving_parts(printed)
    rows += _lens_and_feet(printed, milled["base"])
    rows += _joint_and_port(printed, milled)
    rows += [measure.row(f"{name}_stroke", measure.stroke_width(text), MIN_STROKE) for name, text in printed_text().items()]
    bed_texts = printed_text() | {"knob_pointer": knob_pointer_outline()}
    rows += [
        measure.row(f"{name}_bed_engraving", measure.stroke_width(text), MIN_BED_ENGRAVING) for name, text in bed_texts.items()
    ]
    rows += _print_finish(printed)
    rows += _assembly_order(printed)
    for name in ("base", "top"):
        rows += measure.machinability(name, milled[name])
    rows += _tool_reach()
    return rows


def _print_finish(printed: dict[str, Part]) -> list[dict]:
    """What the slicer does to the printed parts: faces on the layer grid, no show face of the top
    steeper than 45 degrees without a chair under it, and the same reveal all round the lens."""
    rows = [
        measure.row(f"layer_aligned_{name}", measure.misaligned_faces(PRINT_POSES[name] * printed[name]), 0,
                    kind="max", unit="faces")
        for name in LAYERED_PARTS
    ]
    pose = PRINT_POSES["top"]
    steepest = measure.steepest_unsupported_outer_face(pose * printed["top"], pose * top_chairs(), _outward_in_top_bed)
    reveals = [CASE.print_lens_fit, CASE.print_lens_fit + CASE.print_lens_end_room - CASE.print_bridge_sag]
    return rows + [
        measure.row("show_face_overhang_print_top", steepest, MAX_SHOW_FACE_OVERHANG, kind="max", unit="degrees"),
        measure.row("lens_reveal_spread_print", max(reveals) - min(reveals), MAX_LENS_REVEAL_SPREAD, kind="max"),
    ]


def _outward_in_top_bed(centres: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For points of the printed top in its bed pose: the outline's outward normal there, in the bed
    frame, and how deep inside the outline each point lies. The pose maps model (x, y, z) to (-z, y, x)."""
    (x_low, x_high), (y_low, y_high) = case_bounds()
    radius = CASE.print_corner_radius
    board = np.stack([centres[:, 2], -centres[:, 1]], axis=1)
    inner_low, inner_high = np.array((x_low + radius, y_low + radius)), np.array((x_high - radius, y_high - radius))
    nearest = np.clip(board, inner_low, inner_high)
    away = board - nearest
    length = np.linalg.norm(away, axis=1)
    to_sides = np.stack([board[:, 0] - x_low, x_high - board[:, 0], board[:, 1] - y_low, y_high - board[:, 1]], axis=1)
    side_normals = np.array(((-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0)))
    on_a_corner = length > 1e-9
    outward = np.where(on_a_corner[:, None], away / np.where(on_a_corner, length, 1.0)[:, None],
                       side_normals[to_sides.argmin(axis=1)])
    depth = np.where(on_a_corner, radius - length, to_sides.min(axis=1))
    # Board (x, y) is model (x, -y, 0), which the pose turns into bed (0, -y, x).
    in_bed = np.stack([np.zeros(len(board)), -outward[:, 1], outward[:, 0]], axis=1)
    return in_bed, depth


def _assembly_order(printed: dict[str, Part]) -> list[dict]:
    """A light bar must drop into its channel after the PCB is in: lowered from above, it clears the
    board, the LEDs and the base."""
    leds = [led(0.0, 1, y) for y in BOARD.leds.left_y]
    clearance = measure.insertion_clearance(printed["diffuser_left"], 12.0, [pcb(), printed["base"], *leds])
    return [measure.row("bar_insert_after_pcb", clearance, 0.1)]


def _tool_reach() -> list[dict]:
    """Deepest pocket of each milled shell, from the face it is cut from, over the 3 mm end mill's
    diameter. The top: the cavity under the deck from the joint face, the dish and lens from the top face.
    The base: the USB tunnel and the cavity from the rim, the counterbores from the underside."""
    tool = 2 * CASE.cnc_corner_radius
    usb_floor = LEVELS.usb_centre - CASE.usb_plug[1] / 2 - CASE.usb_margin
    depths = {
        "top": max(LEVELS.deck_bottom, BOARD.stack.deck_top - LEVELS.lens_rib_bottom),
        "base": max(-usb_floor, -LEVELS.floor_top, screw_seat(CNC) - LEVELS.floor_bottom),
    }
    return [
        measure.row(f"cnc_{name}_deepest_pocket_over_tool", depth / tool, MAX_TOOL_DEPTH_RATIO, kind="max", unit="of 1")
        for name, depth in depths.items()
    ]


def _soundness(printed: dict[str, Part], milled: dict[str, Part]) -> list[dict]:
    """Every part must be one valid solid. The small parts are the same in both variants."""
    parts = {f"print_{name}": part for name, part in printed.items()}
    parts |= {f"cnc_{name}": milled[name] for name in ("base", "top")}
    return [
        measure.row(f"solid_is_sound_{name}", measure.soundness_faults(part), 0, kind="max", unit="faults")
        for name, part in parts.items()
    ]


def _silhouette(shells: dict[str, Part]) -> list[dict]:
    """The outline is square, the frame round the key dish is even, and the CNC corners are what the
    documents say they are."""
    sizes = [shell.bounding_box().size for shell in shells.values()]
    frame = measure.frame_widths(shells["print_top"])
    corners = [measure.outline_corners(shells[f"cnc_{name}"], height) for name, height in OUTLINE_HEIGHTS.items()]
    out_of_square = max(abs(size.X - size.Y) for size in sizes)
    uneven_frame = max(abs(frame[side] - frame["front"]) for side in ("left", "right"))
    join_curvature = max(join for join, _ in corners)
    return [
        measure.row("case_width_minus_depth", out_of_square, 0.01, kind="max"),
        measure.row("frame_side_minus_front", uneven_frame, 0.01, kind="max"),
        measure.row("cnc_corner_curvature_at_join", join_curvature, measure.MAX_JOIN_CURVATURE, kind="max", unit="1/mm"),
        measure.row("cnc_corner_smallest_radius", min(radius for _, radius in corners), MIN_CORNER_RADIUS),
    ]


def _lens_and_feet(parts: dict[str, Part], milled_base: Part) -> list[dict]:
    """The feet are measured against the milled base: it is the printed one after its skins are cut out."""
    lens, top = parts["lens"], parts["top"]
    feet = {name: parts[name] for name in ("foot_strip_back", "foot_strip_front", "centre_pad")}
    carried = overlap_volume(Pos(0, 0, -LENS_PUSH) * lens, top)
    tape = min((lens_outline() - rectangle(*lens_opening(variant))).area for variant in VARIANTS)
    bearing = [
        measure.row(f"{name}_bearing_share", measure.bearing_share(foot, milled_base), MIN_BEARING_SHARE, unit="of 1")
        for name, foot in feet.items()
    ]
    return [
        measure.row("lens_not_proud", top.bounding_box().max.Z - lens.bounding_box().max.Z, 0.0),
        measure.row("lens_carried_by_ledges", carried, measure.RETENTION_VOLUME, unit="mm^3"),
        measure.row("lens_tape_area", tape, MIN_TAPE_AREA, unit="mm^2"),
        measure.row("strip_covers_screws", measure.uncovered_screw_area(list(feet.values())), 0.01, kind="max", unit="mm^2"),
        *bearing,
        measure.row("label_text_inside_field", _label_margin(), 1.0),
    ]


def _joint_and_port(printed: dict[str, Part], milled: dict[str, Part]) -> list[dict]:
    """Where the top rests on the base, what shows through the gap, and the USB opening."""
    total, per_side = MIN_SEAT_AREA
    rows = []
    for prefix, parts in (("", printed), ("cnc_", milled)):
        seat = measure.seat_areas(parts["base"], parts["top"])
        rows.append(measure.row(f"{prefix}shell_seat_area", seat["all"], total, unit="mm^2"))
        rows += [
            measure.row(f"{prefix}shell_seat_area_{side}", area, per_side, unit="mm^2")
            for side, area in seat.items() if side != "all"
        ]
    seen = measure.pcb_seen_through_gap([printed["base"], printed["top"], printed["diffuser_left"]], pcb())
    rows += [
        measure.row("pcb_seen_through_gap", seen, CASE.diffuser_fit, kind="max"),
        measure.row("light_bar_end_gap_in_slit", measure.bar_end_gap(printed["diffuser_left"]), 0.2, kind="max"),
    ]
    rows += [
        measure.row(f"usb_opening_asymmetry_{name}", measure.asymmetry_at_usb(printed[name]), 0.5, kind="max", unit="mm^3")
        for name in ("base", "top")
    ]
    return rows


def _label_margin() -> float:
    """Smallest distance from the engraved mark to the edge of the area kept free for it, on the four sides."""
    text = underside_mark().bounding_box()
    (x_low, x_high), (y_low, y_high) = label_field()
    # Sketch Y is board Y negated.
    return min(text.min.X - x_low, x_high - text.max.X, -text.max.Y - y_low, y_high + text.min.Y)


def printability() -> list[dict]:
    """For each printed part in its bed pose: the widest overhang that nothing supports, how much of
    it touches the bed, and the longest bridge and deepest cantilever of a layer-by-layer print."""
    parts = case_parts(PRINT)
    parts["top"] = parts["top"] + top_chairs()  # the chairs print with it
    report = []
    for name, pose in PRINT_POSES.items():
        mesh = to_mesh(pose * parts[name])
        span = widest_unsupported_span(mesh)
        contact = bed_contact_area(mesh)
        size = mesh.bounds[1] - mesh.bounds[0]
        aspect = float(size[2] / min(size[0], size[1]))
        layered = printsim.simulate(mesh.triangles)
        report.append({
            "part": name, "widest_span_mm": round(span, 2), "limit_mm": CASE.max_bridge,
            "bed_contact_mm2": round(contact, 1), "minimum_contact_mm2": MIN_BED_CONTACT,
            "height_over_narrow_side": round(aspect, 1), "aspect_limit": MAX_ASPECT,
            "brim_required": aspect > BRIM_ASPECT,
            "longest_bridge_mm": round(layered.longest_bridge, 2), "bridge_at": layered.bridge_at,
            "deepest_cantilever_mm": round(layered.deepest_cantilever, 2), "cantilever_at": layered.cantilever_at,
            "cantilever_limit_mm": CASE.max_cantilever,
            "ok": (span <= CASE.max_bridge and contact >= MIN_BED_CONTACT and aspect <= MAX_ASPECT
                   and layered.longest_bridge <= CASE.max_bridge
                   and layered.deepest_cantilever <= CASE.max_cantilever),
        })
    return report


def widest_unsupported_span(mesh: trimesh.Trimesh) -> float:
    """Overhanging faces are grouped into patches; a patch prints as a bridge if it is narrow
    in at least one direction, so the narrow side of the worst patch is the number that matters."""
    overhanging = (-mesh.face_normals[:, 2] > OVERHANG_COSINE) & ~_on_bed(mesh)
    both_overhang = overhanging[mesh.face_adjacency].all(axis=1)
    patches = trimesh.graph.connected_components(mesh.face_adjacency[both_overhang], nodes=np.flatnonzero(overhanging))
    narrow_sides = [np.ptp(mesh.triangles[patch].reshape(-1, 3)[:, :2], axis=0).min() for patch in patches]
    return float(max(narrow_sides, default=0.0))


def bed_contact_area(mesh: trimesh.Trimesh) -> float:
    return float(mesh.area_faces[_on_bed(mesh)].sum())


def _on_bed(mesh: trimesh.Trimesh) -> np.ndarray:
    bed_level = mesh.vertices[:, 2].min()
    return mesh.triangles[:, :, 2].max(axis=1) < bed_level + BED_TOLERANCE


def to_mesh(part: Part) -> trimesh.Trimesh:
    vertices, triangles = part.tessellate(0.05)
    return trimesh.Trimesh([tuple(vertex) for vertex in vertices], triangles, process=True)


def run_all() -> dict:
    return {
        "self_test": selftest.run(),
        "interference": [interference(variant) for variant in VARIANTS],
        "clearances": clearances(),
        "measurements": measurements(),
        "printability": printability(),
    }


def failures(report: dict) -> list[str]:
    found = [f"self-test {item['name']}: {item['found']}, expected {item['expected']}"
             for item in report["self_test"] if not item["ok"]]
    for result in report["interference"]:
        for clash in result["clashes"]:
            found.append(f"{result['variant']}: {clash['first']} clashes with {clash['second']} "
                         f"({clash['volume_mm3']} mm^3)")
    found += [f"clearance {item['name']}: {item['value_mm']} < {item['minimum_mm']}"
              for item in report["clearances"] if not item["ok"]]
    found += [f"measured {item['name']}: {item['value']} {item['unit']}, {item['kind']} is {item['limit']}"
              for item in report["measurements"] if not item["ok"]]
    found += [f"{item['part']} does not print cleanly: {item['widest_span_mm']} mm span, "
              f"{item['bed_contact_mm2']} mm^2 on the bed, {item['longest_bridge_mm']} mm bridge, "
              f"{item['deepest_cantilever_mm']} mm cantilever at {item['cantilever_at']}"
              for item in report["printability"] if not item["ok"]]
    return found
