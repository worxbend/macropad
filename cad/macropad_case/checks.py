"""Fit checks: interference between every part and component, named clearances, printability."""

from itertools import combinations

import numpy as np
import trimesh
from build123d import Part, Rot

from .components import components, usb_plug
from .parts import case_parts, usb_cutout
from .solids import overlap_volume
from .spec import BOARD, CASE, LEVELS, PRINT, VARIANTS, deck_front

CLASH_VOLUME = 0.05  # mm^3; below this two solids only touch
OVERHANG_COSINE = 0.72  # faces steeper than about 46 degrees from vertical need something under them
BED_TOLERANCE = 0.05

# How each part lies on the print bed: a rotation that brings its bed face to the lowest Z.
PRINT_POSES = {
    "base": Rot(0, 0, 0),
    "top": Rot(0, -90, 0),  # standing on its left side wall
    "diffuser_left": Rot(0, -90, 0),  # outer face down
    "knob_left": Rot(0, 0, 0),
}


def interference(variant: str) -> dict:
    parts = case_parts(variant)
    bought = components()
    pairs = [(part, component) for part in parts for component in bought] + list(combinations(parts, 2))
    solids = parts | bought
    clashes = []
    for first, second in pairs:
        volume = overlap_volume(solids[first], solids[second])
        if volume > CLASH_VOLUME:
            clashes.append({"first": first, "second": second, "volume_mm3": round(volume, 3)})
    return {"variant": variant, "pairs": len(pairs), "clashes": clashes}


def clearances() -> list[dict]:
    """Named gaps in millimetres, each with the minimum it must keep."""
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
        ("keycap_to_deck", BOARD.keys.first_y - CASE.keycap_width / 2 - deck_front(), 0.4),
        ("display_glass_under_deck", LEVELS.deck_bottom + CASE.display_relief - stack.display_glass_top, 0.2),
        ("display_window_inside_module", window_margin, 0.5),
        ("encoder_body_under_deck", LEVELS.deck_bottom - stack.encoder_body_top, 0.3),
        ("screw_engagement", engagement, CASE.min_screw_engagement),
        ("screw_tip_to_hole_end", CASE.pilot_depth - engagement, 0.2),
        ("skin_over_screw_hole", LEVELS.plate_top - CASE.pilot_depth, 0.6),
        ("knob_to_deck_when_pressed", CASE.knob_to_deck - CASE.encoder_press_travel, 0.3),
        ("socket_to_floor", stack.underside_clearance - stack.socket_depth, 1.0),
        ("usb_body_to_floor", stack.underside_clearance - BOARD.usb.body_height, 0.5),
        ("led_inside_slot_height", LEVELS.pcb_bottom - led_height - LEVELS.led_slot_bottom, 0.5),
    ]
    return [
        {"name": name, "value_mm": round(value, 3), "minimum_mm": minimum, "ok": value >= minimum - 1e-9}
        for name, value, minimum in measured
    ]


def _usb_opening_margin() -> float:
    """Smallest gap between the plug overmould and the opening, across the width and the height."""
    opening = usb_cutout().bounding_box()
    plug = usb_plug().bounding_box()
    gaps = []
    for axis in (0, 2):
        gaps.append(tuple(plug.min)[axis] - tuple(opening.min)[axis])
        gaps.append(tuple(opening.max)[axis] - tuple(plug.max)[axis])
    return min(gaps)


def printability() -> list[dict]:
    """For each printed part in its bed pose: the widest overhang that nothing supports."""
    parts = case_parts(PRINT)
    report = []
    for name, pose in PRINT_POSES.items():
        span = widest_unsupported_span(pose * parts[name])
        report.append({"part": name, "widest_span_mm": round(span, 2), "limit_mm": CASE.max_bridge,
                       "ok": span <= CASE.max_bridge})
    return report


def widest_unsupported_span(posed: Part) -> float:
    """Overhanging faces are grouped into patches; a patch prints as a bridge if it is narrow
    in at least one direction, so the narrow side of the worst patch is the number that matters."""
    mesh = to_mesh(posed)
    bed_level = mesh.vertices[:, 2].min()
    on_bed = mesh.triangles[:, :, 2].max(axis=1) < bed_level + BED_TOLERANCE
    overhanging = (-mesh.face_normals[:, 2] > OVERHANG_COSINE) & ~on_bed
    both_overhang = overhanging[mesh.face_adjacency].all(axis=1)
    patches = trimesh.graph.connected_components(mesh.face_adjacency[both_overhang], nodes=np.flatnonzero(overhanging))
    narrow_sides = [np.ptp(mesh.triangles[patch].reshape(-1, 3)[:, :2], axis=0).min() for patch in patches]
    return float(max(narrow_sides, default=0.0))


def to_mesh(part: Part) -> trimesh.Trimesh:
    vertices, triangles = part.tessellate(0.05)
    return trimesh.Trimesh([tuple(vertex) for vertex in vertices], triangles, process=True)


def run_all() -> dict:
    return {
        "interference": [interference(variant) for variant in VARIANTS],
        "clearances": clearances(),
        "printability": printability(),
    }


def failures(report: dict) -> list[str]:
    found = []
    for result in report["interference"]:
        for clash in result["clashes"]:
            found.append(f"{result['variant']}: {clash['first']} clashes with {clash['second']} "
                         f"({clash['volume_mm3']} mm^3)")
    found += [f"clearance {item['name']}: {item['value_mm']} < {item['minimum_mm']}"
              for item in report["clearances"] if not item["ok"]]
    found += [f"{item['part']} needs supports: {item['widest_span_mm']} mm span"
              for item in report["printability"] if not item["ok"]]
    return found
