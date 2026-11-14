"""Checks that measure the finished solids instead of trusting how they were built.

Each function returns rows of `{"name", "value", "limit", "kind", "unit", "ok"}`; `kind` says whether
the limit is a minimum or a maximum.
"""

from math import cos, pi, sin

import numpy as np
import trimesh
from build123d import Axis, Edge, GeomType, Part, Plane, Pos, Sketch, Vector, mirror, section
from scipy.ndimage import binary_dilation, binary_opening, grey_closing

from .components import pcb
from .parts import lap_ridges
from .raster import DEPTH_MAP_SIZE, mesh_of, Material, rasterise
from .solids import box, cylinder, overlap_volume, rectangle
from .spec import BOARD, CASE, LEVELS, case_bounds, corner_holes, led_slot_span, mounting_holes

WALL_SAMPLES = 3000  # surface points probed per part
WALL_MESH_TOLERANCE = 0.1
FACING_COSINE = -0.9  # two faces count as one wall when they are within about 25 degrees of parallel
RAYS_PER_BATCH = 200
RAY_START = 1e-4  # mm below the surface, so a ray does not hit the face it starts on
PROBE = 0.02  # mm; how far from an edge or a face the corner probes sit
PROBES_PER_EDGE = 8
RETENTION_PUSH = 0.6  # mm; the diffuser must hit something before it has moved this far
RETENTION_VOLUME = 0.05  # mm^3
LAP_PUSH = 0.5  # mm; the top must hit a ridge of the base before it has slid this far
LAP_MIN_GAP = 0.1  # mm between a ridge and its groove; the 45 degree flanks sit 0.7 of `lap_fit` apart
REACH_STEP = 0.25  # mm; how far off a face the tool-access probe sits
REACH_TOLERANCE = 0.05
UNDERCUT_NOISE = 5.0  # mm^2; slivers along edges that the 0.09 mm cells of the height map cannot resolve
TOOL_CELL = 0.1  # mm; grid of the height map the tool is run over
TOOL_GRID_SLACK = 1  # cells taken off the tool radius, so a pocket corner of exactly that radius passes
UNCUT_HEIGHT = 0.1  # mm of material left standing before a cell counts as not cut
UNCUT_NOISE = 0.3  # mm^2; one sharp corner in a 3 mm pocket already leaves 0.48
SLOPED = (0.05, 0.995)  # |normal Z| of a face a flat end mill does not cut: chamfers and tapers
ANY_MATERIAL = Material((0.5, 0.5, 0.5))
MAX_JOIN_CURVATURE = 0.01  # per mm, where a corner curve meets a straight side
CURVE_SAMPLES = 40  # places along a corner curve where its radius is taken
SAME_POINT = 1e-6  # mm
COVER_SLICE = 0.1  # mm; thickness of the disc that stands for a counterbore mouth
SEAT_PROBE = 0.01  # mm; the two shells are cut this far from the plane they meet on
FAR = 500.0
SIGHT_STEP = 0.05  # mm between the rays that look into the gap
SIGHT_START = 5.0  # mm outside the case
PORT_BOX = (6.0, 6.0)  # mm; how far the symmetry check reaches beside the USB plug and into the case
LAYER = 0.2  # mm; the layer height the printed parts are drawn for
LAYER_TOLERANCE = 0.02
FRAME_SAMPLES = 400  # points along the rim of the key dish where the frame's width is taken
OUTER_FACE_DEPTH = 0.6  # mm; a face this close to the outline, and facing out, is part of the outside
FACING_OUT = 0.5  # cosine between a face's normal and the outline's outward normal, in plan
SUPPORT_REACH = 0.5  # mm; a chair, or the bed, this close under an overhanging face carries it
INSERT_STEP = 0.5  # mm between the heights a part is tried at while it is lowered into place
SEAT_RESOLUTION = 0.01  # mm; how closely the height a part stops at is found
HOLE_WALL_REACH = 5.0  # mm round a blind hole within which its thinnest wall is looked for


def row(name: str, value: float, limit: float, kind: str = "min", unit: str = "mm") -> dict:
    ok = value >= limit - 1e-6 if kind == "min" else value <= limit + 1e-6
    return {"name": name, "value": round(float(value), 3), "limit": limit, "kind": kind, "unit": unit, "ok": bool(ok)}


def thinnest_wall(part: Part) -> float:
    """Smallest distance through the material between two roughly parallel faces, from `WALL_SAMPLES`
    surface points chosen by area with a fixed seed. A sample can miss a very small thin spot."""
    vertices, triangles = part.tessellate(WALL_MESH_TOLERANCE, 0.3)
    mesh = trimesh.Trimesh([tuple(vertex) for vertex in vertices], triangles, process=False)
    points, source = trimesh.sample.sample_surface(mesh, WALL_SAMPLES, seed=0)
    inward = -mesh.face_normals[source]
    thinnest = np.inf
    for start in range(0, len(points), RAYS_PER_BATCH):
        chosen = slice(start, start + RAYS_PER_BATCH)
        distance, struck = _first_hit(points[chosen] + inward[chosen] * RAY_START, inward[chosen], mesh.triangles)
        found = np.isfinite(distance)
        facing = (mesh.face_normals[struck] * inward[chosen]).sum(axis=1) > -FACING_COSINE
        thinnest = min(thinnest, distance[found & facing].min(initial=np.inf) + RAY_START)
    return float(thinnest)


def _first_hit(origins: np.ndarray, directions: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Moller-Trumbore for every ray against every triangle: distance to the first hit and its triangle."""
    corner = triangles[None, :, 0]
    edge_1 = triangles[None, :, 1] - corner
    edge_2 = triangles[None, :, 2] - corner
    ray = directions[:, None, :]
    p_vector = np.cross(ray, edge_2)
    determinant = (edge_1 * p_vector).sum(axis=2)
    with np.errstate(divide="ignore", invalid="ignore"):
        inverse = 1.0 / determinant
        t_vector = origins[:, None, :] - corner
        u = (t_vector * p_vector).sum(axis=2) * inverse
        q_vector = np.cross(t_vector, edge_1)
        v = (ray * q_vector).sum(axis=2) * inverse
        distance = (edge_2 * q_vector).sum(axis=2) * inverse
        hit = (np.abs(determinant) > 1e-12) & (u >= 0) & (v >= 0) & (u + v <= 1) & (distance > 1e-3)
    distance = np.where(hit, distance, np.inf)
    nearest = distance.argmin(axis=1)
    return distance[np.arange(len(origins)), nearest], nearest


def soundness_faults(part: Part) -> int:
    """How many things are wrong with a part as one body: every solid besides the one expected,
    an invalid shape, no volume. A boolean that went wrong shows up as one of these."""
    return abs(len(part.solids()) - 1) + (not part.is_valid) + (part.volume <= 0)


def outline_corners(part: Part, z: float) -> tuple[float, float]:
    """At the four corners of the part's outer outline at height `z`: the largest curvature (1/mm) at a place where a
    curved edge meets a straight one, and the smallest radius (mm) along the curved edges. An arc
    meets a straight side with a curvature of 1/radius; a continuous-curvature corner meets it with zero."""
    cut = section(part, section_by=Plane.XY.offset(z))
    outline = max(cut.faces(), key=lambda face: face.area).outer_wire().edges()
    straight_ends = [edge @ end for edge in outline.filter_by(GeomType.LINE) for end in (0, 1)]
    # Only the four corners count: an opening in a side wall (the USB port) has its own milled radii.
    box = cut.bounding_box()
    corners = [Vector(x, y, z) for x in (box.min.X, box.max.X) for y in (box.min.Y, box.max.Y)]
    curved = [
        edge for edge in outline if edge.geom_type != GeomType.LINE
        and min((edge.center() - corner).length for corner in corners) < CASE.corner_setback
    ]
    at_joins = [
        _curvature(edge, end) for edge in curved for end in (0.0, 1.0)
        if any((edge @ end - point).length < SAME_POINT for point in straight_ends)
    ]
    along_the_curves = [step / CURVE_SAMPLES for step in range(CURVE_SAMPLES + 1)]
    tightest = max(_curvature(edge, at) for edge in curved for at in along_the_curves)
    return max(at_joins, default=0.0), 1 / tightest


def _curvature(edge: Edge, at: float) -> float:
    first, second = edge.derivative_at(at, 1), edge.derivative_at(at, 2)
    return first.cross(second).length / first.length ** 3


def misaligned_faces(posed: Part) -> int:
    """How many horizontal faces of a part in its bed pose lie off the 0.2 mm layer grid, counted from
    the bed. A face off the grid is rounded by the slicer, and a feature thinner than a layer is lost."""
    bed = posed.bounding_box().min.Z
    off_grid = 0
    for face in posed.faces().filter_by(GeomType.PLANE):
        if abs(face.normal_at().Z) < 0.999:
            continue
        height = face.center().Z - bed
        off_grid += abs(height - round(height / LAYER) * LAYER) > LAYER_TOLERANCE + 1e-6
    return off_grid


def frame_swell(top: Part) -> float:
    """How much wider the flat frame round the key dish is at its widest than at its narrowest: zero
    when the dish rim runs concentric with the outline. Taken from points along the front half of the
    rim to the outer edge of the top face; behind the keys the frame is the deck, wide on purpose."""
    top_face = max(top.faces().group_by(Axis.Z)[-1], key=lambda face: face.area)
    rim = max(top_face.inner_wires(), key=lambda wire: wire.bounding_box().diagonal)
    outer = top_face.outer_wire()
    middle = rim.bounding_box().center().Y
    points = [rim.position_at(step / FRAME_SAMPLES) for step in range(FRAME_SAMPLES)]
    widths = [outer.distance_to(point) for point in points if point.Y < middle]  # model Y runs toward the back
    return max(widths) - min(widths)


def steepest_unsupported_outer_face(posed: Part, chairs: Part, outward_in_plan) -> float:
    """Largest angle from vertical, in degrees, of a downward face on the outside of a part in its bed
    pose that neither a chair nor the bed carries: either must lie `SUPPORT_REACH` or less under it.
    `outward_in_plan(triangle centres)` gives, in the bed frame, the outline's outward normal and how
    deep inside the outline each centre lies; faces deeper than `OUTER_FACE_DEPTH`, or not facing out,
    belong to the inside and are left out."""
    mesh = mesh_of(posed, ANY_MATERIAL)
    triangles = mesh.triangles
    normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area = np.linalg.norm(normal, axis=1)
    normal = normal / np.where(area == 0, 1.0, area)[:, None]
    centres = triangles.mean(axis=1)
    outward, depth = outward_in_plan(centres)
    off_the_bed = centres[:, 2] > posed.bounding_box().min.Z + SUPPORT_REACH
    on_the_outside = (depth < OUTER_FACE_DEPTH) & ((normal * outward).sum(axis=1) > FACING_OUT) & (area > 1e-9)
    on_the_outside &= off_the_bed
    downward = on_the_outside & (normal[:, 2] < -1e-6)
    if not downward.any():
        return 0.0
    chosen = np.flatnonzero(downward)
    chair_triangles = mesh_of(chairs, ANY_MATERIAL).triangles
    down = np.broadcast_to((0.0, 0.0, -1.0), (len(chosen), 3))
    carried = np.zeros(len(chosen), dtype=bool)
    for start in range(0, len(chosen), RAYS_PER_BATCH):
        batch = slice(start, start + RAYS_PER_BATCH)
        distance, _ = _first_hit(centres[chosen[batch]], down[batch], chair_triangles)
        carried[batch] = distance <= SUPPORT_REACH
    # The angle from the CAD face itself: on a curved face a flat triangle tilts off the true surface.
    faces = posed.faces()
    exact = np.array([
        tuple(faces[int(mesh.face_ids[index])].normal_at(Vector(*centres[index]))) for index in chosen[~carried]
    ]).reshape(-1, 3)
    angles = np.degrees(np.arcsin(np.clip(-exact[:, 2], 0, 1)))
    return float(angles.max(initial=0.0))


def insertion_clearance(part: Part, height: float, obstacles: list[Part]) -> float:
    """Smallest gap in mm between a part and the obstacles while it is lowered straight down from
    `height` above its place, tried every `INSERT_STEP`, its seated place left out."""
    steps = np.arange(INSERT_STEP, height + INSERT_STEP / 2, INSERT_STEP)
    return float(min(
        (Pos(0, 0, lift) * part).distance_to(obstacle) for lift in steps for obstacle in obstacles
    ))


def frame_widths(top: Part) -> dict[str, float]:
    """Width of the flat top face to the left of, to the right of and in front of the key dish.
    The dish rim is the largest opening in the top face."""
    top_face = max(top.faces().group_by(Axis.Z)[-1], key=lambda face: face.area)  # not the island inside a letter
    rim = max(top_face.inner_wires(), key=lambda wire: wire.bounding_box().diagonal).bounding_box()
    outside = top.bounding_box()
    # Model Y runs toward the back, so the front of the case is at the low end.
    return {"left": rim.min.X - outside.min.X, "right": outside.max.X - rim.max.X, "front": rim.min.Y - outside.min.Y}


def uncovered_screw_area(feet: list[Part]) -> float:
    """Area in mm^2 of the six counterbore mouths that no foot strip or pad lies over."""
    roof = LEVELS.foot_recess_roof
    mouths = [cylinder(hole, CASE.counterbore_diameter, (roof - COVER_SLICE, roof)) for hole in mounting_holes()]
    uncovered = sum(mouth.volume - sum(overlap_volume(mouth, foot) for foot in feet) for mouth in mouths)
    return uncovered / COVER_SLICE


def bearing_share(foot: Part, base: Part) -> float:
    """Share of a foot's face that lies on the base, not over a hole: the foot is pushed a little
    way into the roof of its recess, and what it then shares with the base is compared with all of it."""
    size = foot.bounding_box().size
    pushed_in = overlap_volume(Pos(0, 0, COVER_SLICE) * foot, base)
    return pushed_in / (foot.volume / size.Z * COVER_SLICE)


def stroke_width(artwork: Sketch) -> float:
    """Mean stroke width in mm of the thinnest glyph: twice a glyph's area over the length of its
    outline. A dot would read as half its diameter; the engraved texts have none."""
    def outline_length(face) -> float:
        return sum(wire.length for wire in (face.outer_wire(), *face.inner_wires()))

    return min(2 * face.area / outline_length(face) for face in artwork.faces())


def seat_areas(base: Part, top: Part) -> dict[str, float]:
    """Area in mm^2 on which the top rests on the base, in all and at each of the four sides of the
    PCB. A corner counts for both sides it belongs to."""
    seat = Pos(0, 0, SEAT_PROBE) * section(base, section_by=Plane.XY.offset(-SEAT_PROBE)) & (
        Pos(0, 0, -SEAT_PROBE) * section(top, section_by=Plane.XY.offset(SEAT_PROBE))
    )
    width, height = BOARD.board.width, BOARD.board.height
    sides = {
        "left": ((-FAR, 0), (-FAR, FAR)), "right": ((width, FAR), (-FAR, FAR)),
        "back": ((-FAR, FAR), (-FAR, 0)), "front": ((-FAR, FAR), (height, FAR)),
    }
    return {"all": seat.area} | {side: (seat & rectangle(*span)).area for side, span in sides.items()}


def pcb_seen_through_gap(in_the_way: list[Part], board: Part) -> float:
    """Longest stretch in mm of the left side along which the PCB edge shows through the gap. Rays go
    square into the side at half the gap's height; a ray counts when the PCB is the first thing it hits."""
    height = LEVELS.gap_bottom / 2
    (left, _), _ = case_bounds()
    looked_at = box((left - 1, 1), (0, BOARD.board.height), (height - 0.5, height + 0.5))
    # A part that does not reach this height (the top) has nothing to draw; the board always does.
    near = [piece for piece in (part & looked_at for part in in_the_way) if piece.solids()] + [board & looked_at]
    meshes = [mesh_of(piece, ANY_MATERIAL).triangles for piece in near]
    triangles = np.concatenate(meshes)
    first_of_board = len(triangles) - len(meshes[-1])
    along = np.arange(0, BOARD.board.height, SIGHT_STEP) + SIGHT_STEP / 2
    origins = np.stack([np.full_like(along, left - SIGHT_START), -along, np.full_like(along, height)], axis=1)
    inward = np.broadcast_to((1.0, 0.0, 0.0), origins.shape)
    sees_board = np.zeros(len(along), dtype=bool)
    for start in range(0, len(along), RAYS_PER_BATCH):
        chosen = slice(start, start + RAYS_PER_BATCH)
        distance, struck = _first_hit(origins[chosen], inward[chosen], triangles)
        sees_board[chosen] = np.isfinite(distance) & (struck >= first_of_board)
    return _longest_run(sees_board) * SIGHT_STEP


def _longest_run(flags: np.ndarray) -> int:
    longest = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return longest


def bar_end_gap(bar: Part) -> float:
    """Gap in mm between an end of the left light bar's visible face and the end of its slot, at half
    the gap's height. The larger of the two ends."""
    outline = section(bar, section_by=Plane.XY.offset(LEVELS.gap_bottom / 2)).vertices()
    outer_face = min(vertex.X for vertex in outline)
    along = [-vertex.Y for vertex in outline if vertex.X < outer_face + PROBE]
    slot_start, slot_end = led_slot_span()
    return max(min(along) - slot_start, slot_end - max(along))


def asymmetry_at_usb(shell: Part) -> float:
    """Volume in mm^3 by which a shell differs from its own mirror image round the USB opening."""
    beside, inward = PORT_BOX
    half_width = CASE.usb_plug[0] / 2 + beside
    back_face = case_bounds()[1][0]
    around_the_port = box(
        (BOARD.usb.x - half_width, BOARD.usb.x + half_width), (back_face - 1, inward), (LEVELS.floor_bottom, LEVELS.plate_top)
    )
    as_built = shell & around_the_port
    mirrored = mirror(as_built, Plane.YZ.offset(BOARD.usb.x))
    return sum(solid.volume for difference in (as_built - mirrored, mirrored - as_built) for solid in difference.solids())


def boss_wall(part: Part, hole_diameter: float, z: float, holes: list[tuple[float, float]] | None = None) -> float:
    """Thinnest wall around a screw hole, measured on the horizontal cut at height `z`:
    the distance from each hole's edge to the nearest other edge of the cut."""
    edges = section(part, section_by=Plane.XY.offset(z)).edges()
    thinnest = np.inf
    for x, y in holes or mounting_holes():
        centre = Vector(x, -y, z)
        around_hole = [edge for edge in edges if _is_circle_at(edge, centre, hole_diameter / 2)]
        if not around_hole:
            raise ValueError(f"no {hole_diameter} mm hole found at ({x}, {y}) on z = {z}")
        near = [edge for edge in edges if edge.distance_to(centre) < 10 and not _is_circle_at(edge, centre, hole_diameter / 2)]
        thinnest = min([thinnest] + [around_hole[0].distance_to(edge) for edge in near])
    return float(thinnest)


def _is_circle_at(edge, centre: Vector, radius: float) -> bool:
    if edge.geom_type != GeomType.CIRCLE or abs(edge.radius - radius) > 1e-3:
        return False
    return (edge.arc_center - centre).length < 1e-3


def diffuser_retention(diffuser: Part, base: Part, top: Part) -> list[dict]:
    """Push the left light bar 0.6 mm each way out of its seat and see what stops it."""
    stops = {
        "outward": (Pos(-RETENTION_PUSH, 0, 0), base),
        "inward": (Pos(RETENTION_PUSH, 0, 0), pcb()),
        "upward": (Pos(0, 0, RETENTION_PUSH), top),
        "downward": (Pos(0, 0, -RETENTION_PUSH), base),
        "to_the_back": (Pos(0, RETENTION_PUSH, 0), base),
        "to_the_front": (Pos(0, -RETENTION_PUSH, 0), base),
    }
    return [
        row(f"diffuser_stopped_{direction}", overlap_volume(push * diffuser, stop), RETENTION_VOLUME, unit="mm^3")
        for direction, (push, stop) in stops.items()
    ]


def lap_joint(base: Part, top: Part) -> list[dict]:
    """The ridges must clear their grooves, and must stop the top from sliding any of four ways."""
    pushes = {"left": (-LAP_PUSH, 0), "right": (LAP_PUSH, 0), "back": (0, LAP_PUSH), "front": (0, -LAP_PUSH)}
    stopped = [
        row(f"lap_stops_top_sliding_{direction}", overlap_volume(base, Pos(x, y, 0) * top), RETENTION_VOLUME, unit="mm^3")
        for direction, (x, y) in pushes.items()
    ]
    return [row("lap_ridge_to_groove", lap_ridges().distance_to(top), LAP_MIN_GAP), *stopped]


def sharp_internal_corners(part: Part) -> int:
    """Vertical edges where two pocket walls meet without a radius: a round tool cannot cut them.
    Probe points on a small circle around each vertical edge; in an internal corner most are in material."""
    sharp = 0
    for edge in part.edges().filter_by(GeomType.LINE):
        start, end = edge.position_at(0), edge.position_at(1)
        if edge.length < 0.05 or abs(start.X - end.X) > 1e-6 or abs(start.Y - end.Y) > 1e-6:
            continue
        middle = edge.position_at(0.5)
        in_material = sum(
            part.is_inside(middle + Vector(PROBE * cos(angle), PROBE * sin(angle), 0))
            for angle in (2 * pi * (step + 0.5) / PROBES_PER_EDGE for step in range(PROBES_PER_EDGE))
        )
        sharp += in_material > PROBES_PER_EDGE * 0.6
    return sharp


def smallest_pocket_radius(part: Part) -> tuple[float, int]:
    """Smallest radius of a concave vertical wall that is not a full hole, and how many full holes
    (drilled, not milled) were left out."""
    smallest, drilled = np.inf, 0
    for face in part.faces().filter_by(GeomType.CYLINDER):
        axis = face.axis_of_rotation
        if abs(axis.direction.Z) < 0.999:
            continue
        on_face = face.position_at(0.5, 0.5)
        toward_axis = Vector(axis.position.X - on_face.X, axis.position.Y - on_face.Y, 0).normalized()
        if part.is_inside(on_face + toward_axis * PROBE):
            continue  # material on the axis side: an outside corner
        if _is_full_turn(face):
            drilled += 1
        else:
            smallest = min(smallest, face.radius)
    return float(smallest), drilled


def _is_full_turn(face) -> bool:
    return abs(face.area - 2 * pi * face.radius * face.bounding_box().size.Z) < 1e-3 * face.area


def unreachable_area(part: Part) -> float:
    """Area in mm^2 that a tool coming straight down or straight up cannot see: an undercut.
    A point just off each face is tested against the height of the material above and below it."""
    mesh = mesh_of(part, ANY_MATERIAL)
    triangles = mesh.triangles
    flat_normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area = np.linalg.norm(flat_normal, axis=1) / 2
    probe = triangles.mean(axis=1) + flat_normal / (2 * area[:, None]) * REACH_STEP
    low = triangles.reshape(-1, 3).min(axis=0)[:2] - 1.0
    cells_per_mm = (DEPTH_MAP_SIZE - 1) / (triangles.reshape(-1, 3).max(axis=0)[:2] + 1.0 - low).max()
    size = (DEPTH_MAP_SIZE, DEPTH_MAP_SIZE)
    cells = (triangles[..., :2] - low) * cells_per_mm
    _, _, top_height = rasterise(cells, triangles[..., 2], size, cull_back_faces=False)
    _, _, bottom_depth = rasterise(cells, -triangles[..., 2], size, cull_back_faces=False)
    column, row_number = np.clip(np.rint((probe[:, :2] - low) * cells_per_mm).astype(int), 0, DEPTH_MAP_SIZE - 1).T
    open_above = top_height[row_number, column] <= probe[:, 2] + REACH_TOLERANCE
    open_below = -bottom_depth[row_number, column] >= probe[:, 2] - REACH_TOLERANCE
    return float(area[~open_above & ~open_below].sum())


def uncut_area(part: Part, tool_diameter: float) -> dict[str, float]:
    """Area in mm^2 a flat end mill of `tool_diameter` cannot cut, coming straight down ("above") and
    straight up ("below"). The tool is lowered over a height map of the part: wherever it stops more
    than `UNCUT_HEIGHT` short of the surface, a corner is too tight or a slot too narrow. Sloped faces
    are left out (a chamfer mill cuts them), and so are round holes smaller than the tool (drilled)."""
    triangles = mesh_of(part, ANY_MATERIAL).triangles
    flat_normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    steepness = np.abs(flat_normal[:, 2]) / np.maximum(np.linalg.norm(flat_normal, axis=1), 1e-12)
    is_sloped = (steepness > SLOPED[0]) & (steepness < SLOPED[1])
    border = tool_diameter / 2 + 1.0
    low = triangles.reshape(-1, 3).min(axis=0)[:2] - border
    columns, rows = np.ceil((triangles.reshape(-1, 3).max(axis=0)[:2] + border - low) / TOOL_CELL).astype(int)
    cells = (triangles[..., :2] - low) / TOOL_CELL
    radius = round(tool_diameter / 2 / TOOL_CELL) - TOOL_GRID_SLACK
    across = np.arange(-radius, radius + 1)
    tool = across[:, None] ** 2 + across[None, :] ** 2 <= radius ** 2
    drilled = _drilled_cells(part, tool_diameter, low, (rows, columns))
    found = {}
    for side, toward_tool in (("above", 1.0), ("below", -1.0)):
        nearest, _, height = rasterise(cells, toward_tool * triangles[..., 2], (int(columns), int(rows)), cull_back_faces=False)
        has_material = nearest >= 0
        height = np.where(has_material, height, height[has_material].min() - 1.0)  # the tool may pass beside the part
        left_standing = grey_closing(height, footprint=tool) - height > UNCUT_HEIGHT
        chamfered = binary_dilation(has_material & is_sloped[np.where(has_material, nearest, 0)], iterations=2)
        # Opening drops the lines one or two cells wide that the grid leaves along edges; a real fault is wider.
        faults = binary_opening(left_standing & ~chamfered & ~drilled, structure=np.ones((3, 3), dtype=bool))
        found[side] = float(faults.sum() * TOOL_CELL ** 2)
    return found


def _drilled_cells(part: Part, tool_diameter: float, low: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Cells inside vertical round holes smaller than the tool: those are drilled, not milled."""
    row, column = np.indices(shape)
    x, y = low[0] + (column + 0.5) * TOOL_CELL, low[1] + (row + 0.5) * TOOL_CELL
    drilled = np.zeros(shape, dtype=bool)
    for face in part.faces().filter_by(GeomType.CYLINDER):
        axis = face.axis_of_rotation
        if abs(axis.direction.Z) > 0.999 and face.radius < tool_diameter / 2 and _is_full_turn(face):
            drilled |= (x - axis.position.X) ** 2 + (y - axis.position.Y) ** 2 <= (face.radius + 2 * TOOL_CELL) ** 2
    return drilled


def machinability(name: str, part: Part) -> list[dict]:
    radius, drilled = smallest_pocket_radius(part)
    radius_row = row(f"cnc_{name}_smallest_pocket_radius", radius, CASE.cnc_corner_radius)
    return [
        row(f"cnc_{name}_sharp_internal_corners", sharp_internal_corners(part), 0, kind="max", unit="edges"),
        radius_row | {"note": f"{drilled} full round holes left out: they are drilled"},
        row(f"cnc_{name}_undercut_area", unreachable_area(part), UNDERCUT_NOISE, kind="max", unit="mm^2"),
        *[
            row(f"cnc_{name}_not_cut_from_{side}", area, UNCUT_NOISE, kind="max", unit="mm^2")
            for side, area in uncut_area(part, 2 * CASE.cnc_corner_radius).items()
        ],
    ]


def boss_walls(base: Part, top: Part) -> list[dict]:
    under_the_pcb = (LEVELS.boss_root_top + LEVELS.base_boss_top) / 2
    in_the_root = (LEVELS.floor_top + LEVELS.boss_root_top) / 2
    in_the_top = CASE.pilot_depth / 2
    clearance_hole = BOARD.mounting.hole_diameter
    return [
        row("base_boss_wall_under_pcb", boss_wall(base, clearance_hole, under_the_pcb), 1.2),
        row("base_boss_wall_at_floor", boss_wall(base, clearance_hole, in_the_root), 2.0),
        row("top_boss_wall", boss_wall(top, CASE.pilot_diameter, in_the_top), 1.2),
        # The corner bosses print with their hole along the layers, where a thread-cutting screw splits them.
        row("top_corner_boss_wall", boss_wall(top, CASE.pilot_diameter, in_the_top, corner_holes()), 1.5),
    ]


def seat_lift(part: Part, obstacle: Part, reach: float) -> float:
    """How far `part` must be lifted straight up from where it is drawn before it no longer overlaps
    `obstacle`: zero for a part that seats where it is drawn, `reach` or more for one that never clears."""
    def clashes(lift: float) -> bool:
        return overlap_volume(Pos(0, 0, lift) * part, obstacle) > RETENTION_VOLUME

    if not clashes(0.0):
        return 0.0
    if clashes(reach):
        return reach
    low, high = 0.0, reach
    while high - low > SEAT_RESOLUTION:
        middle = (low + high) / 2
        low, high = (middle, high) if clashes(middle) else (low, middle)
    return high


def wall_round_blind_hole(part: Part, hole: Part, mouth_z: float) -> float:
    """Thinnest material between a blind hole opened from below and any other air of the part, more
    than 1 mm above the hole's mouth: the skin over its end, or the boss round its side. `hole` is
    the shape that was cut; it may be drawn deeper than the hole in `part`, to judge a deeper drill."""
    centre = hole.bounding_box().center()
    reach = HOLE_WALL_REACH
    near = box((centre.X - reach, centre.X + reach), (-centre.Y - reach, -centre.Y + reach), (mouth_z + 1, FAR))
    air = near - ((part & near) + hole)
    return float(hole.distance_to(air))


def section_above(part: Part, z: float) -> Sketch:
    """The part cut just above height `z`, moved down to Z 0: where it rests on a plane at `z`, when
    nothing of it reaches below `z` there."""
    return Pos(0, 0, -z - SEAT_PROBE) * section(part, section_by=Plane.XY.offset(z + SEAT_PROBE))
