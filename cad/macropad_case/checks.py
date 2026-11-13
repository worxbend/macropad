"""Fit checks: interference between every part and component, named clearances, measurements on the
finished solids, and printability. `run_all` gathers them; `failures` lists what did not pass."""

from itertools import combinations
from math import pi, sqrt

import numpy as np
import trimesh
from build123d import Box, Part, Pos, Rot

from . import measure, printsim, selftest, signature
from .components import MX_FLANGE, at, components, keycap
from .parts import base_body, label_field_outline, top_body, underside_mark, usb_cutout
from .small_parts import BAR_TO_TOP, case_parts, desk_plane_drop
from .solids import overlap_volume
from .spec import BOARD, CASE, CNC, LEVELS, PRINT, VARIANTS, buttons, dish_rim, encoder_centres
from .spec import key_centres, lens_opening, lens_recess

CLASH_VOLUME = 0.05  # mm^3; below this two solids only touch
OVERHANG_COSINE = 0.72  # faces steeper than about 46 degrees from vertical need something under them
BED_TOLERANCE = 0.05
MIN_BED_CONTACT = 100.0  # mm^2 of first layer, so the part stays on the bed
# The tilt bar's tongue takes the back strip's recess, so that strip moves onto the bar.
ALTERNATIVES = {frozenset(("tilt_bar", "foot_strip_back"))}
LENS_PUSH = 0.3  # mm; the lens must hit its ledges before it has moved this far down
# A height at which each shell's outline is whole: above the underside chamfer, and in the plate.
OUTLINE_HEIGHTS = {"base": LEVELS.floor_bottom + 2.0, "top": LEVELS.plate_bottom + 0.5}
MIN_CORNER_RADIUS = 4.66  # mm; the corner curve is drawn for 4.71

# How each part lies on the print bed: a rotation that brings its bed face to the lowest Z.
PRINT_POSES = {
    "base": Rot(0, 0, 0),
    "top": Rot(0, -90, 0),  # standing on its left side wall
    "diffuser_left": Rot(0, -90, 0),  # outer face down
    "knob_left": Rot(0, 0, 0),
    "foot_strip_back": Rot(0, 0, 0),
    "centre_pad": Rot(0, 0, 0),
    "tilt_bar": Rot(CASE.tilt_angle, 0, 0),  # sloped underside down
}


def interference(variant: str) -> dict:
    parts = case_parts(variant)
    bought = components()
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
    under_head = (LEVELS.pcb_bottom - LEVELS.floor_bottom) - CASE.counterbore_depth
    engagement = CASE.screw_length - under_head - BOARD.board.thickness
    led_height = CASE.led_body[2]
    window_margin = min(
        display.length / 2 - abs(display.window_x - display.x) - display.window_length / 2,
        display.width / 2 - abs(display.window_y - display.y) - display.window_width / 2,
    )
    measured = [
        ("usb_plug_to_opening", _usb_opening_margin(), 0.2),
        ("keycap_to_deck", BOARD.keys.first_y - CASE.keycap_width / 2 - dish_rim()[1][0], 0.4),
        ("display_glass_under_deck", LEVELS.lens_bottom - stack.display_glass_top, 0.2),
        ("display_window_inside_module", window_margin, 0.5),
        ("encoder_body_under_deck", LEVELS.deck_bottom - stack.encoder_body_top, 0.3),
        ("screw_engagement", engagement, CASE.min_screw_engagement),
        ("screw_tip_to_hole_end", CASE.pilot_depth - engagement, 0.2),
        ("skin_over_screw_hole", LEVELS.plate_top - CASE.pilot_depth, CASE.min_wall),
        ("screw_head_below_underside", CASE.counterbore_depth - CASE.screw_head[1], 0.2),
        ("screw_head_in_counterbore", (CASE.counterbore_diameter - CASE.screw_head[0]) / 2, 0.2),
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


def _top_face_margins() -> list[tuple[str, float, float]]:
    """The key dish, and the knobs on the plain deck."""
    bushing_hole = BOARD.stack.encoder_bushing_diameter + CASE.bushing_clearance
    grooved_radius = CASE.knob_diameter / 2 - CASE.knob_groove_depth
    groove_pitch = pi * CASE.knob_diameter / CASE.knob_grooves
    return [
        ("switch_flange_to_dish_floor", CASE.dish_floor_margin - MX_FLANGE[0] / 2, 0.25),
        ("deck_wall_under_dish", CASE.deck_front_wall / sqrt(2), CASE.min_wall),
        ("knob_covers_bushing_hole", grooved_radius - bushing_hole / 2, 3.0),
        ("knob_groove_land", groove_pitch - 2 * CASE.knob_groove_depth, 0.45),
    ]


def _lens_margins() -> list[tuple[str, float, float]]:
    display = BOARD.display
    (recess_start, recess_end), (recess_back, recess_front) = lens_recess()
    (opening_start, opening_end), (opening_back, opening_front) = lens_opening()
    module_in_opening = min(
        display.x - display.length / 2 - opening_start, opening_end - display.x - display.length / 2,
        display.y - display.width / 2 - opening_back, opening_front - display.y - display.width / 2,
    )
    knob_edge = encoder_centres()[0][0] + CASE.knob_diameter / 2
    return [
        ("display_module_inside_opening", module_in_opening, 0.3),
        ("lens_below_flush", LEVELS.deck_top - LEVELS.lens_top, 0.0),
        ("lens_end_ledge", opening_start - recess_start, 1.0),
        ("lens_to_knob", display.x - CASE.lens[0] / 2 - knob_edge, 1.0),
        ("lens_to_dish_rim", dish_rim()[1][0] - recess_front, 1.0),
        ("lens_recess_bridge_margin", CASE.max_bridge - (recess_front - recess_back), 0.0),
    ]


def _light_line_margins() -> list[tuple[str, float, float]]:
    """The gap round the case and the light bar behind it."""
    rim_wall = CASE.wall - CASE.gap_depth
    return [
        ("gap_land_beside_lap_ridge", rim_wall - CASE.lap_crest - CASE.lap_height, 0.2),
        ("light_skin", CASE.wall - CASE.light_channel_reach, CASE.min_wall),
        ("light_slit_height", CASE.gap_height - BAR_TO_TOP, 0.8),
        ("led_to_light_bar", CASE.pcb_gap - CASE.diffuser_inner_face, 0.1),
    ]


def _underside_margins() -> list[tuple[str, float, float]]:
    """The foot strips hide the screws; the recesses and the cones must leave enough floor."""
    head_bottom = LEVELS.counterbore_top - CASE.screw_head[1]
    cone_mouth, cone_end = CASE.screw_cone
    cone_top = LEVELS.foot_recess_roof + (cone_mouth - cone_end) / 2
    return [
        ("screw_head_under_strip_recess", head_bottom - LEVELS.foot_recess_roof, 0.2),
        ("strip_covers_counterbore", (CASE.foot_strip[0] - CASE.counterbore_diameter) / 2, 1.0),
        ("floor_under_strip_recess", CASE.floor - CASE.foot_recess_depth, CASE.min_wall),
        ("cone_inside_floor", LEVELS.floor_top - cone_top, 0.5),
        ("pad_lower_than_strips", CASE.foot_strip[1] - CASE.centre_pad_thickness, 0.1),
        ("floor_under_label_engraving", CASE.floor - CASE.label_field_depth - CASE.engraving_depth, CASE.min_wall),
        ("signature_inside_free_field", signature.margin_in_field(), signature.MARGIN),
        ("signature_line_laser_markable", signature.LINE_WIDTH, signature.MIN_LASER_LINE),
    ]


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
    pressed = Pos(0, 0, -CASE.key_travel) * keycap()
    knob_pressed = Pos(0, 0, -CASE.encoder_press_travel) * parts["knob_left"]
    return [
        measure.row("pressed_keycap_to_top", at(back_left_key, pressed).distance_to(parts["top"]), 0.4),
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
        "print_base": base_body(PRINT), "print_top": top_body(PRINT), "cnc_base": milled["base"],
        "cnc_top": milled["top"], "diffuser": printed["diffuser_left"], "knob": printed["knob_left"],
        "tilt_bar": printed["tilt_bar"], "foot_strip": printed["foot_strip_back"], "centre_pad": printed["centre_pad"],
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
    rows += _lens_and_feet(printed)
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


def _lens_and_feet(parts: dict[str, Part]) -> list[dict]:
    lens, top = parts["lens"], parts["top"]
    feet = [parts["foot_strip_back"], parts["foot_strip_front"], parts["centre_pad"]]
    carried = overlap_volume(Pos(0, 0, -LENS_PUSH) * lens, top)
    return [
        measure.row("lens_not_proud", top.bounding_box().max.Z - lens.bounding_box().max.Z, 0.0),
        measure.row("lens_carried_by_ledges", carried, measure.RETENTION_VOLUME, unit="mm^3"),
        measure.row("strip_covers_screws", measure.uncovered_screw_area(feet), 0.01, kind="max", unit="mm^2"),
        measure.row("label_text_inside_field", _label_margin(), 1.0),
    ]


def _label_margin() -> float:
    """Smallest distance from the engraved mark to the edge of its field, on the four sides."""
    text, field = underside_mark().bounding_box(), label_field_outline().bounding_box()
    return min(text.min.X - field.min.X, field.max.X - text.max.X, text.min.Y - field.min.Y, field.max.Y - text.max.Y)


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
