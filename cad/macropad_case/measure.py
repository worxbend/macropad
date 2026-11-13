"""Checks that measure the finished solids instead of trusting how they were built.

Each function returns rows of `{"name", "value", "limit", "kind", "unit", "ok"}`; `kind` says whether
the limit is a minimum or a maximum.
"""

from math import cos, pi, sin

import numpy as np
import trimesh
from build123d import GeomType, Part, Plane, Pos, Vector, section
from scipy.ndimage import binary_dilation, binary_opening, grey_closing

from .components import pcb
from .parts import lap_ridges
from .raster import DEPTH_MAP_SIZE, mesh_of, Material, rasterise
from .solids import overlap_volume
from .spec import BOARD, CASE, LEVELS, mounting_holes

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


def boss_wall(part: Part, hole_diameter: float, z: float) -> float:
    """Thinnest wall around a screw hole, measured on the horizontal cut at height `z`:
    the distance from each hole's edge to the nearest other edge of the cut."""
    edges = section(part, section_by=Plane.XY.offset(z)).edges()
    thinnest = np.inf
    for x, y in mounting_holes():
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
    """Push the left diffuser 0.6 mm each way out of its seat and see what stops it."""
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
    under_the_pcb = (LEVELS.boss_root_top + LEVELS.pcb_bottom) / 2
    in_the_root = (LEVELS.floor_top + LEVELS.boss_root_top) / 2
    in_the_top = CASE.pilot_depth / 2
    clearance_hole = BOARD.mounting.hole_diameter
    return [
        row("base_boss_wall_under_pcb", boss_wall(base, clearance_hole, under_the_pcb), 1.2),
        row("base_boss_wall_at_floor", boss_wall(base, clearance_hole, in_the_root), 2.0),
        row("top_boss_wall", boss_wall(top, CASE.pilot_diameter, in_the_top), 1.2),
    ]
