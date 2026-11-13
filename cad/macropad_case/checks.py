"""Fit checks: interference between every part and component, named clearances, measurements on the
finished solids, and printability. `run_all` gathers them; `failures` lists what did not pass."""

from itertools import combinations
from math import pi, sqrt

import numpy as np
import trimesh
from build123d import Box, Part, Pos, Rot

from . import measure, printsim, selftest, signature
from .components import MX_FLANGE, at, components, keycap, pcb, worst_keycap_skirt
from .parts import base_body, drill_point_height, printed_text, switch_cutout_length, underside_mark, usb_cutout
from .small_parts import BAR_TO_TOP, case_parts, desk_plane_drop, lens_outline, tilt_bar_body
from .solids import overlap_volume, rectangle
from .spec import BACK_ROW, BOARD, CASE, CNC, FRONT_ROW, LEVELS, PRINT, VARIANTS, buttons, case_bounds, dish_rim
from .spec import encoder_centres, foot_span, grown, key_centres, knob_well_diameter, label_field, lens_opening
from .spec import lens_recess, lens_span, screw_length, screw_seat

CLASH_VOLUME = 0.05  # mm^3; below this two solids only touch
OVERHANG_COSINE = 0.72  # faces steeper than about 46 degrees from vertical need something under them
BED_TOLERANCE = 0.05
MIN_BED_CONTACT = 100.0  # mm^2 of first layer, so the part stays on the bed
# The tilt bar's tongue takes the back strip's recess, so that strip moves onto the bar.
ALTERNATIVES = {frozenset(("tilt_bar", "foot_strip_back"))}
LENS_PUSH = 0.3  # mm; the lens must hit its ledges before it has moved this far down
# A height at which each shell's outline has its full size: above the underside chamfer, and in the plate.
OUTLINE_HEIGHTS = {"base": LEVELS.floor_bottom + CASE.underside_chamfer + 0.5, "top": LEVELS.plate_bottom + 0.5}
MIN_CORNER_RADIUS = 4.66  # mm; the corner curve is drawn for 4.71
M2_THREAD = 2.0  # mm, major diameter
MIN_PRINTED_PILOT = 1.6  # mm; in a smaller hole the M2 screw splits the boss
MAX_PRINTED_PILOT = 1.75  # mm; in a larger hole the thread has too little to cut into
PCB_THICKNESS_TOLERANCE = 0.1  # share of the nominal thickness, as the board houses state it
MAX_GAP_GROWTH = 0.2  # mm the gap may open before it reads as a fault
LENS_SHEET_TOLERANCE = 0.1  # mm; guess: how much thicker than nominal a 1.0 mm sheet may be
CHAMFER_CUTTER = (8.0, 0.5)  # mm; a common 90 degree chamfer mill and the flat its tip may have
MIN_STROKE = 0.45  # mm; one line of a 0.4 mm nozzle
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
        if volume > CLASH_VOLUME:
            clashes.append({"first": first, "second": second, "volume_mm3": round(volume, 3)})
    return {"variant": variant, "pairs": len(pairs), "clashes": clashes}


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
        *_tilt_bar_margins(), *_top_face_margins(), *_lens_margins(), *_light_line_margins(), *_underside_margins(),
    ]
    return [
        {"name": name, "value_mm": round(value, 3), "minimum_mm": minimum, "ok": value >= minimum - 1e-9}
        for name, value, minimum in measured
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
        ("cnc_screw_head_below_underside", CASE.cnc_counterbore_depth - head_height, 0.2),
    ]


def _top_face_margins() -> list[tuple[str, float, float]]:
    """The key dish, and the knobs in their wells."""
    bushing_hole = BOARD.stack.encoder_bushing_diameter + CASE.bushing_clearance
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
        ("knob_covers_bushing_hole", grooved_radius - bushing_hole / 2, 3.0),
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
        ("lens_mask_window_inside_glass", min(glass_length - display.window_length, glass_width - display.window_width) / 2, 0.5),
    ]


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
    return [
        ("gap_land_beside_lap_ridge", rim_wall - CASE.lap_crest - CASE.lap_height, 0.2),
        ("light_skin", CASE.wall - CASE.light_channel_reach, CASE.min_wall),
        ("light_slit_height", slit, 0.8),
        # Seen from 45 degrees above, the edge of the top hides as much of the bar as the bar is set back.
        ("light_line_visible_at_45deg", slit - (CASE.gap_depth - CASE.seam_chamfer), 0.6),
        ("led_to_light_bar", CASE.pcb_gap, 0.1),
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
        ("chamfer_to_strip_recess", _flat_round_strip_recesses(), 0.4),
        ("signature_inside_free_field", signature.margin_in_field(), signature.MARGIN),
        ("signature_line_laser_markable", signature.LINE_WIDTH, signature.MIN_LASER_LINE),
    ]


def _flat_round_strip_recesses() -> float:
    """Narrowest flat between the underside chamfer and a foot strip recess, at the sides, back and front."""
    flat = grown(case_bounds(), -CASE.underside_chamfer)
    return min(_inside(grown(foot_span(row), CASE.foot_recess_fit), flat) for row in (BACK_ROW, FRONT_ROW))


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
    return [
        measure.row("pressed_keycap_to_top", at(back_left_key, worst_keycap_skirt()).distance_to(parts["top"]), 0.4),
        measure.row("keycap_to_knob", at(back_left_key, keycap()).distance_to(parts["knob_left"]), 2.0),
        measure.row("keycap_to_knob_right", at(back_right_key, keycap()).distance_to(parts["knob_right"]), 2.0),
        measure.row("pressed_knob_to_top", knob_pressed.distance_to(parts["top"]), 0.3),
        measure.row("knob_to_top", parts["knob_left"].distance_to(parts["top"]), 0.8),
    ]


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
    rows += measure.boss_walls(printed["base"], printed["top"])
    rows += measure.diffuser_retention(printed["diffuser_left"], printed["base"], printed["top"])
    rows += measure.lap_joint(printed["base"], printed["top"])
    rows += [dict(found, name=f"cnc_{found['name']}") for found in measure.lap_joint(milled["base"], milled["top"])]
    rows += moving_parts(printed)
    rows += _lens_and_feet(printed, milled["base"])
    rows += _joint_and_port(printed, milled)
    rows += [measure.row(f"{name}_stroke", measure.stroke_width(text), MIN_STROKE) for name, text in printed_text().items()]
    for name in ("base", "top"):
        rows += measure.machinability(name, milled[name])
    return rows


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
    report = []
    for name, pose in PRINT_POSES.items():
        mesh = to_mesh(pose * parts[name])
        span = widest_unsupported_span(mesh)
        contact = bed_contact_area(mesh)
        size = mesh.bounds[1] - mesh.bounds[0]
        layered = printsim.simulate(mesh.triangles)
        report.append({
            "part": name, "widest_span_mm": round(span, 2), "limit_mm": CASE.max_bridge,
            "bed_contact_mm2": round(contact, 1), "minimum_contact_mm2": MIN_BED_CONTACT,
            "height_over_narrow_side": round(float(size[2] / min(size[0], size[1])), 1),
            "longest_bridge_mm": round(layered.longest_bridge, 2), "bridge_at": layered.bridge_at,
            "deepest_cantilever_mm": round(layered.deepest_cantilever, 2), "cantilever_at": layered.cantilever_at,
            "cantilever_limit_mm": CASE.max_cantilever,
            "ok": (span <= CASE.max_bridge and contact >= MIN_BED_CONTACT
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
