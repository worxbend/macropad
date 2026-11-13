"""Fit checks: interference between every part and component, named clearances, measurements on the
finished solids, and printability. `run_all` gathers them; `failures` lists what did not pass."""

from itertools import combinations

import numpy as np
import trimesh
from build123d import Box, Part, Pos, Rot

from . import measure, printsim, selftest
from .components import at, components, keycap
from .parts import base_body, top_body, usb_cutout
from .small_parts import case_parts, desk_plane_drop
from .solids import overlap_volume
from .spec import BOARD, CASE, CNC, LEVELS, PRINT, VARIANTS, buttons, deck_front, foot_centres, key_centres
from .spec import mounting_holes

CLASH_VOLUME = 0.05  # mm^3; below this two solids only touch
OVERHANG_COSINE = 0.72  # faces steeper than about 46 degrees from vertical need something under them
BED_TOLERANCE = 0.05
MIN_BED_CONTACT = 100.0  # mm^2 of first layer, so the part stays on the bed
# The tilt bar takes over the two back foot recesses, so the back feet move onto it.
ALTERNATIVES = {("tilt_bar", "foot_0"), ("tilt_bar", "foot_1")}

# How each part lies on the print bed: a rotation that brings its bed face to the lowest Z.
PRINT_POSES = {
    "base": Rot(0, 0, 0),
    "top": Rot(0, -90, 0),  # standing on its left side wall
    "diffuser_left": Rot(0, -90, 0),  # outer face down
    "knob_left": Rot(0, 0, 0),
    "tilt_bar": Rot(CASE.tilt_angle, 0, 0),  # sloped underside down
}


def interference(variant: str) -> dict:
    parts = case_parts(variant)
    bought = components()
    pairs = [(part, component) for part in parts for component in bought] + list(combinations(parts, 2))
    pairs = [pair for pair in pairs if pair not in ALTERNATIVES]
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
    deck_skin = stack.plate_thickness - CASE.display_relief
    measured = [
        ("usb_plug_to_opening", _usb_opening_margin(), 0.2),
        ("keycap_to_deck", BOARD.keys.first_y - CASE.keycap_width / 2 - deck_front(), 0.4),
        ("display_glass_under_deck", LEVELS.deck_bottom + CASE.display_relief - stack.display_glass_top, 0.2),
        ("display_window_inside_module", window_margin, 0.5),
        ("encoder_body_under_deck", LEVELS.deck_bottom - stack.encoder_body_top, 0.3),
        ("screw_engagement", engagement, CASE.min_screw_engagement),
        ("screw_tip_to_hole_end", CASE.pilot_depth - engagement, 0.2),
        ("skin_over_screw_hole", LEVELS.plate_top - CASE.pilot_depth, CASE.min_wall),
        ("screw_head_below_underside", CASE.counterbore_depth - CASE.screw_head[1], 0.2),
        ("screw_head_in_counterbore", (CASE.counterbore_diameter - CASE.screw_head[0]) / 2, 0.2),
        ("knob_to_well_floor_when_pressed", LEVELS.knob_bottom - LEVELS.knob_well_floor - CASE.encoder_press_travel, 0.3),
        ("skin_under_knob_well", LEVELS.knob_well_floor - LEVELS.deck_bottom, CASE.min_wall),
        ("bezel_land_under_chamfer", deck_skin - CASE.bezel_chamfer, 0.2),
        ("rib_to_switch_cutout", (BOARD.keys.pitch - stack.switch_cutout - CASE.rib_width) / 2, 1.0),
        ("skirt_beside_lap_groove", CASE.wall - CASE.lap_crest - CASE.lap_height - CASE.lap_fit, CASE.min_wall),
        ("lap_groove_under_ribs", LEVELS.rib_bottom - CASE.lap_height - CASE.lap_fit, 0.0),
        ("floor_under_engraving", CASE.floor - CASE.engraving_depth, CASE.min_wall),
        ("plate_under_engraving", stack.plate_thickness - CASE.engraving_depth, CASE.min_wall),
        ("socket_to_floor", stack.underside_clearance - stack.socket_depth, 1.0),
        ("usb_body_to_floor", stack.underside_clearance - BOARD.usb.body_height, 0.5),
        ("led_inside_slot_height", LEVELS.pcb_bottom - led_height - LEVELS.led_slot_bottom, 0.5),
        ("foot_below_underside", CASE.foot[1] - CASE.foot_depth, 0.5),
        *_tilt_bar_margins(),
    ]
    return [
        {"name": name, "value_mm": round(value, 3), "minimum_mm": minimum, "ok": value >= minimum - 1e-9}
        for name, value, minimum in measured
    ]


def _tilt_bar_margins() -> list[tuple[str, float, float]]:
    """The tilt bar must leave the back screws and the two button holes uncovered."""
    back_feet_y = foot_centres()[0][1]
    bar_back, bar_front = back_feet_y - CASE.tilt_bar_depth / 2, back_feet_y + CASE.tilt_bar_depth / 2
    back_screws_y = min(y for _, y in mounting_holes())
    button_y = min(y for _, y in buttons().values())
    return [
        ("tilt_bar_to_screw_counterbore", bar_back - back_screws_y - CASE.counterbore_diameter / 2, 0.5),
        ("tilt_bar_to_button_hole", button_y - CASE.button_hole_diameter / 2 - bar_front, 0.5),
        ("tilt_bar_thinnest", desk_plane_drop(bar_front), 3.0),
    ]


def _usb_opening_margin() -> float:
    """Smallest gap between the plug overmould and the opening, across the width and the height."""
    width, height = CASE.usb_plug
    opening = usb_cutout() & Pos(BOARD.usb.x, CASE.wall / 2 + CASE.pcb_gap, LEVELS.usb_centre) * _slice_of_wall()
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
    bodies = {
        "print_base": base_body(PRINT), "print_top": top_body(PRINT), "cnc_base": milled["base"],
        "cnc_top": milled["top"], "diffuser": printed["diffuser_left"], "knob": printed["knob_left"],
        "tilt_bar": printed["tilt_bar"],
    }
    rows = [measure.row(f"thinnest_wall_{name}", measure.thinnest_wall(body), CASE.min_wall) for name, body in bodies.items()]
    rows += measure.boss_walls(printed["base"], printed["top"])
    rows += measure.diffuser_retention(printed["diffuser_left"], printed["base"], printed["top"])
    rows += measure.lap_joint(printed["base"], printed["top"])
    rows += [dict(found, name=f"cnc_{found['name']}") for found in measure.lap_joint(milled["base"], milled["top"])]
    rows += moving_parts(printed)
    for name in ("base", "top"):
        rows += measure.machinability(name, milled[name])
    return rows


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
