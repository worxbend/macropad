"""A small software renderer in numpy: a z-buffer rasteriser, a shadow map and deferred shading.

It exists so the pictures need no GPU, no window system and no extra dependency. Hidden surfaces are
removed per pixel, curved faces are shaded smoothly, and edges are inked where two faces meet at an angle.
"""

from dataclasses import dataclass, field

import numpy as np
from build123d import Part
from scipy.ndimage import gaussian_filter, maximum_filter

SUPERSAMPLE = 2
LARGEST_PIECE = 16  # pixels; anything wider is cut in two before it is drawn
CANDIDATE_BUDGET = 2_000_000  # pixels tested per batch of triangles; bounds the memory of one batch
FRONT_FACE_SIGN = -1  # screen Y points down, so a face seen from outside runs clockwise
DEGENERATE_AREA = 1e-5  # square pixels; a triangle seen edge-on covers nothing
INSIDE_TOLERANCE = -1e-4  # barycentric slack, so no pixel falls through the crack between two triangles
DEPTH_MAP_SIZE = 1024  # cells across the shadow map and the contact-shadow map
DEPTH_MAP_MARGIN = 12.0  # mm of empty border around the model in those maps
CONTACT_HEIGHT = 5.0  # mm; surfaces higher than a few of these no longer darken the ground
CONTACT_SPREAD = 4.0  # mm; how far the contact shadow spills past the model
CONTACT_STRENGTH = 0.6
SHADOW_BIAS = 0.15  # mm; lifts the lookup point off its own surface
CREASE_COSINE = 0.82  # faces meeting at more than about 35 degrees get an inked edge
MESH_TOLERANCE = 0.03
HATCH_LINE = 0.28  # share of the hatch spacing that a line takes
HATCH_SHADE = 0.55  # how dark a hatch line is
# What a metal surface mirrors, by the height (Z of the unit vector) its reflected ray points to: a
# sky three times brighter at the horizon than at the zenith, a darker floor that lightens toward the
# horizon, and a bright band of soft boxes low on the walls. A 45 degree chamfer seen from above
# mirrors that band, so it is the brightest line on the part; a vertical flank mirrors the floor.
STUDIO_HORIZON = 1.2
STUDIO_ZENITH = 0.4
STUDIO_NADIR = 0.3
STUDIO_FLOOR_AT_HORIZON = 0.7
STUDIO_BAND = (0.9, 0.4, 0.2)  # extra brightness, the height it is centred on, its spread
STUDIO_KEY_SHARE = 0.6  # how much of the key light counts toward the brightness of the studio
# A glossy sheet mirrors one window as a soft band across it. The band runs along this direction in
# plan, lies off the middle of the sheet by a share of its half-length, and is that wide.
SHEEN_ACROSS = (0.8, 0.6, 0.0)
SHEEN_PLACE = (-0.3, 0.3)
MESH_ANGLE = 0.15


@dataclass(frozen=True)
class Material:
    colour: tuple[float, float, float]  # sRGB, 0..1
    gloss: float = 0.15  # strength of the highlight
    glow: float = 0.0  # light the surface gives off, as a multiple of its colour
    hatch: float = 0.0  # mm between hatch lines on a cut face; negative leans them the other way
    metal: float = 0.0  # share of the surface's light that is a mirror image of the studio, not diffuse
    sheen: float = 0.0  # brightness of the window a glossy sheet mirrors, as a band across the mesh
    glow_fade: float = 0.0  # mm; the glow fades out over this length at both ends of the mesh's longest side


@dataclass(frozen=True)
class Decal:
    """A picture laid on a mesh: `origin` is the model position of its top-left corner, `across` and
    `down` are the vectors along its top and left edges. It shows on faces that look along their normal."""

    image: np.ndarray  # (rows, columns, 3), sRGB 0..1
    origin: np.ndarray
    across: np.ndarray
    down: np.ndarray

    def moved(self, matrix: np.ndarray, offset: np.ndarray) -> "Decal":
        return Decal(self.image, self.origin @ matrix.T + offset, self.across @ matrix.T, self.down @ matrix.T)

    def paint(self, colour: np.ndarray, position: np.ndarray, normal: np.ndarray, chosen: np.ndarray) -> None:
        """Replace `colour` (linear) with the picture, at the chosen pixels that lie inside it."""
        facing = np.abs(normal @ _unit(np.cross(self.across, self.down))) > 0.7
        relative = position - self.origin
        u = relative @ self.across / (self.across @ self.across)
        v = relative @ self.down / (self.down @ self.down)
        inside = chosen & facing & (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
        rows, columns = self.image.shape[:2]
        row = np.clip((v[inside] * rows).astype(int), 0, rows - 1)
        column = np.clip((u[inside] * columns).astype(int), 0, columns - 1)
        colour[inside] = _to_linear(self.image[row, column])


@dataclass
class Mesh:
    """Triangles with one normal per corner. `face_ids` tells which CAD face each triangle came from."""

    triangles: np.ndarray  # (n, 3, 3)
    normals: np.ndarray  # (n, 3, 3)
    face_ids: np.ndarray  # (n,)
    material: Material
    decal: Decal | None = None

    def moved(self, matrix: np.ndarray, offset: np.ndarray) -> "Mesh":
        decal = self.decal.moved(matrix, offset) if self.decal else None
        return Mesh(self.triangles @ matrix.T + offset, self.normals @ matrix.T, self.face_ids, self.material, decal)

    def only(self, chosen: np.ndarray, material: Material) -> "Mesh":
        """The chosen triangles as a mesh of their own, in another material."""
        return Mesh(self.triangles[chosen], self.normals[chosen], self.face_ids[chosen], material, self.decal)


@dataclass(frozen=True)
class Camera:
    eye: tuple[float, float, float]
    target: tuple[float, float, float]
    field_of_view: float = 22.0  # degrees, vertical
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)

    def axes(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        forward = _unit(np.subtract(self.target, self.eye))
        right = _unit(np.cross(forward, self.up))
        return right, np.cross(right, forward), forward


@dataclass(frozen=True)
class Lighting:
    key_direction: tuple[float, float, float] = (-0.55, 0.30, 0.78)  # toward the light: above, left, a little behind
    key: float = 0.95
    fill: float = 0.25
    ambient: float = 0.42
    background_top: tuple[float, float, float] = (0.93, 0.94, 0.95)
    background_bottom: tuple[float, float, float] = (0.80, 0.82, 0.85)
    shadow_strength: float = 0.55
    bloom: float = 0.0  # how much glowing surfaces spill light around themselves
    edge_ink: float = 0.45


@dataclass
class Scene:
    meshes: list[Mesh] = field(default_factory=list)
    ground_z: float | None = None  # a shadow-catching plane; None for views from below

    def add(self, shape: Part, material: Material) -> None:
        self.meshes.append(mesh_of(shape, material))


def mesh_of(shape: Part, material: Material) -> Mesh:
    """Tessellate face by face: corners are shared inside one CAD face (smooth shading) and split
    between faces (crisp edges)."""
    triangles, normals, face_ids = [], [], []
    for face_number, face in enumerate(shape.faces()):
        vertices, indices = face.tessellate(MESH_TOLERANCE, MESH_ANGLE)
        if not indices:
            continue
        points = np.array([tuple(vertex) for vertex in vertices])
        corners = np.array(indices)
        face_triangles = points[corners]
        flat = np.cross(face_triangles[:, 1] - face_triangles[:, 0], face_triangles[:, 2] - face_triangles[:, 0])
        vertex_normals = np.zeros_like(points)
        for corner in range(3):
            np.add.at(vertex_normals, corners[:, corner], flat)  # area-weighted
        triangles.append(face_triangles)
        normals.append(_unit(vertex_normals)[corners])
        face_ids.append(np.full(len(corners), face_number))
    return Mesh(np.concatenate(triangles), np.concatenate(normals), np.concatenate(face_ids), material)


def _unit(vectors: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(lengths == 0, 1.0, lengths)


def rasterise(corners_xy: np.ndarray, corner_depth: np.ndarray, size: tuple[int, int], cull_back_faces: bool = True):
    """Nearest triangle per pixel.

    `corners_xy` is (n, 3, 2) in pixels, `corner_depth` is (n, 3) and larger means nearer.
    Returns the triangle index (-1 where empty), the barycentric weights and the depth, per pixel.
    Large triangles are first cut into pieces, then all pieces are drawn in batches of similar size,
    so the work stays inside numpy.
    """
    width, height = size
    on_screen = (corners_xy.max(axis=1) >= 0).all(axis=1) & (corners_xy.min(axis=1) <= (width, height)).all(axis=1)
    # Every solid is closed, so the camera never sees a back face. Depth maps keep both sides.
    drawn = on_screen & (_signed_area(corners_xy) * FRONT_FACE_SIGN > 0) if cull_back_faces else on_screen
    buffers = _Buffers(width, height)
    for pieces, lowest, grid in _batches(_Pieces(np.flatnonzero(drawn), corners_xy[drawn], corner_depth[drawn])):
        buffers.draw(pieces, lowest, grid)
    return buffers.result()


def crossings(corners_xy: np.ndarray, corner_depth: np.ndarray, size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Every place a pixel centre lies under a triangle, not only the nearest: the flat pixel index
    and the depth there, one entry per crossing. Triangles seen edge-on give none."""
    found = [
        _samples(pieces, lowest, grid, size, tolerance=0.0)[1:3]
        for pieces, lowest, grid in _batches(_Pieces(np.arange(len(corners_xy)), corners_xy, corner_depth))
    ]
    if not found:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    return np.concatenate([pixel for pixel, _ in found]), np.concatenate([depth for _, depth in found])


def _batches(triangles: "_Pieces"):
    """The triangles cut small, in batches whose pieces need the same number of columns and rows."""
    pieces = triangles.cut_small()
    lowest = np.floor(pieces.corners.min(axis=1)).astype(np.int64)
    extent = np.ceil(pieces.corners.max(axis=1)).astype(np.int64) - lowest + 1
    grid = 2 ** np.ceil(np.log2(extent)).astype(np.int64)  # columns and rows each piece needs, as powers of two
    for columns, rows in np.unique(grid, axis=0):
        in_batch = np.flatnonzero((grid == (columns, rows)).all(axis=1))
        per_batch = max(1, CANDIDATE_BUDGET // (columns * rows))
        for start in range(0, len(in_batch), per_batch):
            chosen = in_batch[start:start + per_batch]
            yield pieces.take(chosen), lowest[chosen], (columns, rows)


def _samples(pieces: "_Pieces", lowest: np.ndarray, grid: tuple[int, int], size: tuple[int, int], tolerance: float):
    """The pixel centres inside each piece: which piece, the flat pixel index, the depth there and
    the weights of the piece's corners."""
    width, height = size
    pixel_x = lowest[:, 0, None, None] + np.arange(grid[0])[None, None, :]
    pixel_y = lowest[:, 1, None, None] + np.arange(grid[1])[None, :, None]
    candidate = _barycentric(pieces.corners, pixel_x + 0.5, pixel_y + 0.5)
    inside = (pixel_x >= 0) & (pixel_x < width) & (pixel_y >= 0) & (pixel_y < height)
    for weight in candidate:
        inside = inside & (weight >= tolerance)
    which, row, column = np.nonzero(inside)
    weights = np.stack([weight[which, row, column] for weight in candidate], axis=1)
    depth = (weights * pieces.depth[which]).sum(axis=1)
    pixel = pixel_y[which, row, 0] * width + pixel_x[which, 0, column]
    return which, pixel, depth, weights


def _signed_area(corners: np.ndarray) -> np.ndarray:
    first, second = corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]
    return first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]


@dataclass
class _Pieces:
    """Triangles on their way to the screen. `weights` holds, for each corner of a piece, its
    barycentric position in the triangle it was cut from."""

    number: np.ndarray  # (n,) index of the original triangle
    corners: np.ndarray  # (n, 3, 2)
    depth: np.ndarray  # (n, 3)
    weights: np.ndarray | None = None  # (n, 3, 3)

    def __post_init__(self) -> None:
        if self.weights is None:
            self.weights = np.broadcast_to(np.eye(3), (len(self.number), 3, 3)).copy()

    def take(self, chosen: np.ndarray) -> "_Pieces":
        return _Pieces(self.number[chosen], self.corners[chosen], self.depth[chosen], self.weights[chosen])

    def cut_small(self) -> "_Pieces":
        """Halve every piece wider than `LARGEST_PIECE` pixels across its longest edge, until none is left."""
        pieces = self
        while True:
            extent = (pieces.corners.max(axis=1) - pieces.corners.min(axis=1)).max(axis=1)
            large = extent > LARGEST_PIECE
            if not large.any():
                return pieces
            halves = pieces.take(np.flatnonzero(large))._halved()
            small = pieces.take(np.flatnonzero(~large))
            pieces = _Pieces(*(np.concatenate([kept, *cut]) for kept, cut in zip(small._arrays(), halves)))

    def _arrays(self) -> tuple[np.ndarray, ...]:
        return self.number, self.corners, self.depth, self.weights

    def _halved(self) -> list[tuple[np.ndarray, np.ndarray]]:
        """Both halves of every piece, as one pair of arrays per field."""
        edges = np.linalg.norm(np.roll(self.corners, -1, axis=1) - self.corners, axis=2)
        rows = np.arange(len(self.number))
        start = edges.argmax(axis=1)
        end, opposite = (start + 1) % 3, (start + 2) % 3
        halves = [(self.number, self.number)]
        for values in (self.corners, self.depth, self.weights):
            first, second, third = values[rows, start], values[rows, end], values[rows, opposite]
            middle = (first + second) / 2
            halves.append((np.stack([first, middle, third], axis=1), np.stack([middle, second, third], axis=1)))
        return halves


class _Buffers:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.depth = np.full(width * height, -np.inf)
        self.triangle = np.full(width * height, -1, dtype=np.int64)
        self.weights = np.zeros((width * height, 3), dtype=np.float32)

    def draw(self, pieces: _Pieces, lowest: np.ndarray, grid: tuple[int, int]) -> None:
        which, pixel, depth, weights = _samples(pieces, lowest, grid, (self.width, self.height), INSIDE_TOLERANCE)
        if not len(which):
            return
        # Far to near: where several candidates land on one pixel, numpy keeps the last one written.
        order = np.argsort(depth, kind="stable")
        pixel, depth, weights, which = pixel[order], depth[order], weights[order], which[order]
        nearer = depth > self.depth[pixel]
        pixel, which = pixel[nearer], which[nearer]
        self.depth[pixel] = depth[nearer]
        self.triangle[pixel] = pieces.number[which]
        self.weights[pixel] = np.einsum("nc,nco->no", weights[nearer], pieces.weights[which])

    def result(self):
        shape = (self.height, self.width)
        return self.triangle.reshape(shape), self.weights.reshape(*shape, 3), self.depth.reshape(shape)


def _barycentric(corners: np.ndarray, x: np.ndarray, y: np.ndarray) -> list[np.ndarray]:
    """The weight of each triangle's three corners at the sample points; three (n, rows, columns) arrays."""
    origin = np.floor(corners.min(axis=1))  # keeps the float32 arithmetic below exact enough
    a, b, c = ((corners[:, index] - origin).astype(np.float32)[:, :, None, None] for index in range(3))
    x = (x - origin[:, 0, None, None]).astype(np.float32)
    y = (y - origin[:, 1, None, None]).astype(np.float32)

    def edge(start, end):
        return (end[:, 0] - start[:, 0]) * (y - start[:, 1]) - (end[:, 1] - start[:, 1]) * (x - start[:, 0])

    area = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    area = np.where(np.abs(area) < DEGENERATE_AREA, np.nan, area)  # NaN weights fail every inside test
    return [edge(b, c) / area, edge(c, a) / area, edge(a, b) / area]


def render(scene: Scene, camera: Camera, size: tuple[int, int], lighting: Lighting = Lighting()) -> np.ndarray:
    """An sRGB image, (height, width, 3) of uint8."""
    width, height = size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE
    geometry = _SceneArrays(scene)
    view = _View(camera, width, height)
    corners_xy, inverse_distance = view.project(geometry.triangles)
    triangle, weights, depth = rasterise(corners_xy, inverse_distance, (width, height))
    hit = triangle >= 0
    surface = _Surface(geometry, view, scene.ground_z, triangle, weights, depth)
    lit = _shade(surface, lighting, geometry.triangles, scene.ground_z)
    image = np.where(surface.covered[..., None], lit, _background(lighting, width, height))
    image = image * (1 - lighting.edge_ink * _edges(surface, hit)[..., None])
    if lighting.bloom:
        image = image + lighting.bloom * _bloom(surface.glow_colour, width)
    image = _to_srgb(np.clip(image, 0, 1))
    image = image.reshape(size[1], SUPERSAMPLE, size[0], SUPERSAMPLE, 3).mean(axis=(1, 3))
    return (image * 255 + 0.5).astype(np.uint8)


class _SceneArrays:
    """All meshes of a scene end to end, with per-triangle lookups."""

    def __init__(self, scene: Scene) -> None:
        self.triangles = np.concatenate([mesh.triangles for mesh in scene.meshes])
        self.normals = np.concatenate([mesh.normals for mesh in scene.meshes])
        counts = [len(mesh.triangles) for mesh in scene.meshes]
        self.mesh_number = np.repeat(np.arange(len(scene.meshes)), counts)
        # A face id that is unique in the whole scene, for edge inking.
        self.face = self.mesh_number * 100_000 + np.concatenate([mesh.face_ids for mesh in scene.meshes])
        self.colour = _to_linear(np.array([mesh.material.colour for mesh in scene.meshes]))
        self.gloss = np.array([mesh.material.gloss for mesh in scene.meshes])
        self.glow = np.array([mesh.material.glow for mesh in scene.meshes])
        self.hatch = np.array([mesh.material.hatch for mesh in scene.meshes])
        self.metal = np.array([mesh.material.metal for mesh in scene.meshes])
        self.sheen = np.array([mesh.material.sheen for mesh in scene.meshes])
        self.glow_fade = np.array([mesh.material.glow_fade for mesh in scene.meshes])
        # Each mesh's extent, for the effects that are laid out along it.
        points = [mesh.triangles.reshape(-1, 3) for mesh in scene.meshes]
        low, high = np.array([each.min(axis=0) for each in points]), np.array([each.max(axis=0) for each in points])
        self.long_axis = (high - low).argmax(axis=1)
        rows = np.arange(len(low))
        self.long_ends = np.stack([low[rows, self.long_axis], high[rows, self.long_axis]], axis=1)
        across = _unit(np.array(SHEEN_ACROSS))
        self.sheen_middle = (low + high) / 2 @ across
        self.sheen_half = np.abs((high - low) / 2) @ np.abs(across)
        self.decals = {number: mesh.decal for number, mesh in enumerate(scene.meshes) if mesh.decal}


class _View:
    def __init__(self, camera: Camera, width: int, height: int) -> None:
        self.eye = np.array(camera.eye, dtype=float)
        self.right, self.up, self.forward = camera.axes()
        self.width, self.height = width, height
        self.focal = height / 2 / np.tan(np.radians(camera.field_of_view) / 2)  # pixels

    def project(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Pixel positions and 1 / distance along the view axis (which is linear on the screen)."""
        relative = points - self.eye
        distance = relative @ self.forward
        x = self.width / 2 + self.focal * (relative @ self.right) / distance
        y = self.height / 2 - self.focal * (relative @ self.up) / distance
        return np.stack([x, y], axis=-1), 1.0 / distance

    def rays(self) -> np.ndarray:
        """For each pixel, the vector that reaches distance 1 along the view axis."""
        x = (np.arange(self.width) + 0.5 - self.width / 2) / self.focal
        y = (self.height / 2 - np.arange(self.height) - 0.5) / self.focal
        return self.forward + x[None, :, None] * self.right + y[:, None, None] * self.up


class _Surface:
    """What each pixel sees: position, normal, material, and whether it is the model or the ground."""

    def __init__(self, geometry: _SceneArrays, view: _View, ground_z, triangle, weights, depth) -> None:
        hit = triangle >= 0
        rays = view.rays()
        distance = np.where(hit, 1.0 / np.where(hit, depth, 1.0), np.inf)
        on_ground = np.zeros_like(hit)
        if ground_z is not None:
            falling = rays[..., 2] < -1e-9
            to_ground = np.where(falling, (ground_z - view.eye[2]) / np.where(falling, rays[..., 2], -1.0), np.inf)
            on_ground = ~hit & np.isfinite(to_ground)
            distance = np.where(on_ground, to_ground, distance)
        self.covered = hit | on_ground
        self.on_ground = on_ground
        self.distance = distance
        self.position = view.eye + rays * np.where(self.covered, distance, 0.0)[..., None]
        self.toward_eye = -_unit(rays)
        safe = np.where(hit, triangle, 0)
        normal = _unit((geometry.normals[safe] * weights[..., None]).sum(axis=2))
        self.normal = np.where(on_ground[..., None], (0.0, 0.0, 1.0), normal)
        mesh = geometry.mesh_number[safe]
        self.colour = geometry.colour[mesh]
        for number, decal in geometry.decals.items():
            decal.paint(self.colour, self.position, self.normal, hit & (mesh == number))
        self.colour = self.colour * _hatching(self.position, np.where(hit, geometry.hatch[mesh], 0.0))[..., None]
        self.gloss = np.where(hit, geometry.gloss[mesh], 0.0)
        self.metal = np.where(hit, geometry.metal[mesh], 0.0)
        glow = geometry.glow[mesh] * _end_fade(geometry, mesh, self.position)
        self.glow_colour = np.where(hit[..., None], geometry.colour[mesh] * glow[..., None], 0.0)
        self.sheen = np.where(hit, geometry.sheen[mesh] * _sheen_band(geometry, mesh, self.position), 0.0)
        self.face = np.where(hit, geometry.face[safe], -1)


def _end_fade(geometry: _SceneArrays, mesh: np.ndarray, position: np.ndarray) -> np.ndarray:
    """1 in the middle of each mesh, falling to 0 toward both ends of its longest side over the
    mesh's `glow_fade`. A lit strip that ends in a hard edge would be brighter than the light allows."""
    fade = geometry.glow_fade[mesh]
    along = np.take_along_axis(position, geometry.long_axis[mesh][..., None], axis=-1)[..., 0]
    start, end = geometry.long_ends[mesh, 0], geometry.long_ends[mesh, 1]
    share = np.minimum(along - start, end - along) / np.where(fade > 0, fade, 1.0)
    return np.where(fade > 0, np.clip(share, 0, 1), 1.0)


def _sheen_band(geometry: _SceneArrays, mesh: np.ndarray, position: np.ndarray) -> np.ndarray:
    """A soft band across each mesh, 0..1: where a window would be mirrored."""
    offset, width = SHEEN_PLACE
    across = (position @ _unit(np.array(SHEEN_ACROSS)) - geometry.sheen_middle[mesh]) / geometry.sheen_half[mesh]
    return np.exp(-(((across - offset) / width) ** 2))


def _hatching(position: np.ndarray, spacing: np.ndarray) -> np.ndarray:
    """1 on plain surfaces; on hatched ones, darker along lines at 45 degrees in the model's Y-Z or X-Z plane."""
    hatched = spacing != 0
    step = np.where(hatched, np.abs(spacing), 1.0)
    along = position[..., 0] + position[..., 1] + np.sign(spacing) * position[..., 2]
    on_a_line = hatched & (np.mod(along / step, 1.0) < HATCH_LINE)
    return np.where(on_a_line, HATCH_SHADE, 1.0)


class _DepthMap:
    """The scene seen from far away along one direction: for each cell, how far toward the viewer
    the nearest surface reaches (-inf where there is none)."""

    def __init__(self, triangles: np.ndarray, toward_viewer: tuple[float, float, float]) -> None:
        self.toward_viewer = _unit(np.array(toward_viewer, dtype=float))
        helper = (0.0, 0.0, 1.0) if abs(self.toward_viewer[2]) < 0.9 else (1.0, 0.0, 0.0)
        self.across = _unit(np.cross(helper, self.toward_viewer))
        self.along = np.cross(self.toward_viewer, self.across)
        flat = np.stack([triangles @ self.across, triangles @ self.along], axis=-1)
        self.origin = flat.reshape(-1, 2).min(axis=0) - DEPTH_MAP_MARGIN
        span = (flat.reshape(-1, 2).max(axis=0) + DEPTH_MAP_MARGIN - self.origin).max()
        self.cells_per_mm = (DEPTH_MAP_SIZE - 1) / span
        _, _, self.reach = rasterise(
            (flat - self.origin) * self.cells_per_mm, triangles @ self.toward_viewer, (DEPTH_MAP_SIZE, DEPTH_MAP_SIZE),
            cull_back_faces=False,
        )

    def cell_of(self, position: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Fractional row and column of each position."""
        column = ((position @ self.across) - self.origin[0]) * self.cells_per_mm
        row = ((position @ self.along) - self.origin[1]) * self.cells_per_mm
        return row, column


def _in_map(cell: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(cell).astype(np.int64), 0, DEPTH_MAP_SIZE - 1)


def _cast_shadow(light_view: _DepthMap, position: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """0 = fully lit, 1 = fully in shadow, from a soft 3 x 3 lookup."""
    lifted = position + (normal + light_view.toward_viewer) * SHADOW_BIAS
    row, column = light_view.cell_of(lifted)
    height = lifted @ light_view.toward_viewer
    shadowed = np.zeros(height.shape)
    for row_step in (-1, 0, 1):
        for column_step in (-1, 0, 1):
            shadowed += light_view.reach[_in_map(row + row_step), _in_map(column + column_step)] > height
    return np.where(_outside_map(row, column), 0.0, shadowed / 9.0)


def _outside_map(row: np.ndarray, column: np.ndarray) -> np.ndarray:
    last = DEPTH_MAP_SIZE - 1
    return (row < 0) | (row > last) | (column < 0) | (column > last)


def _contact_shadow(triangles: np.ndarray, ground_z: float, position: np.ndarray) -> np.ndarray:
    """How much sky the model takes away from each ground point, 0..1: a soft dark patch under and
    around whatever stands close above the ground."""
    from_below = _DepthMap(triangles, (0.0, 0.0, -1.0))
    clearance = -from_below.reach - ground_z  # height of the lowest surface above the ground; inf where empty
    cover = np.exp(-np.clip(clearance, 0, None) / CONTACT_HEIGHT)
    soft = gaussian_filter(cover, CONTACT_SPREAD * from_below.cells_per_mm)
    row, column = from_below.cell_of(position)
    return np.where(_outside_map(row, column), 0.0, soft[_in_map(row), _in_map(column)])


def _shade(surface: _Surface, lighting: Lighting, triangles: np.ndarray, ground_z: float | None) -> np.ndarray:
    normal = surface.normal
    light_view = _DepthMap(triangles, lighting.key_direction)
    key = light_view.toward_viewer
    fill = _unit(np.array((-key[0] * 1.5, -key[1], 0.35)))
    shadow = np.where(surface.covered, _cast_shadow(light_view, surface.position, normal), 0.0)
    shadow = gaussian_filter(shadow, 1.5 * SUPERSAMPLE)
    sky = 0.5 + 0.5 * normal[..., 2]
    occlusion = _crease_occlusion(surface)
    diffuse = (
        lighting.key * np.clip(normal @ key, 0, None) * (1 - shadow)
        + lighting.fill * np.clip(normal @ fill, 0, None)
        + lighting.ambient * (0.55 + 0.45 * sky) * occlusion
    )
    diffuse = diffuse * (1 - surface.metal) + surface.metal * _studio(surface, lighting) * occlusion
    halfway = _unit(surface.toward_eye + key)
    highlight = surface.gloss * np.clip((normal * halfway).sum(axis=-1), 0, None) ** 40 * (1 - shadow)
    window = surface.sheen * (lighting.ambient + STUDIO_KEY_SHARE * lighting.key)
    model = (surface.colour * diffuse[..., None] + (highlight * lighting.key + window)[..., None]
             + surface.glow_colour)
    if ground_z is None:
        return model
    contact = _contact_shadow(triangles, ground_z, surface.position)
    ground_light = (1 - lighting.shadow_strength * shadow) * (1 - CONTACT_STRENGTH * contact)
    ground = _background(lighting, *surface.covered.shape[::-1]) * ground_light[..., None]
    return np.where(surface.on_ground[..., None], ground, model)


def _studio(surface: _Surface, lighting: Lighting) -> np.ndarray:
    """How bright the studio is where each pixel's mirror image comes from."""
    normal, toward_eye = surface.normal, surface.toward_eye
    reflected_z = np.clip(2 * (normal * toward_eye).sum(axis=-1) * normal[..., 2] - toward_eye[..., 2], -1, 1)
    sky = STUDIO_HORIZON + (STUDIO_ZENITH - STUDIO_HORIZON) * np.clip(reflected_z, 0, 1) ** 0.7
    floor = STUDIO_FLOOR_AT_HORIZON + (STUDIO_NADIR - STUDIO_FLOOR_AT_HORIZON) * np.clip(-reflected_z, 0, 1)
    extra, centre, spread = STUDIO_BAND
    band = extra * np.exp(-((reflected_z - centre) / spread) ** 2)
    return (np.where(reflected_z >= 0, sky, floor) + band) * (lighting.ambient + STUDIO_KEY_SHARE * lighting.key)


def _crease_occlusion(surface: _Surface) -> np.ndarray:
    """Darkens creases on the model: a pixel that lies deeper than its neighbourhood gets less sky."""
    farthest = surface.distance[surface.covered].max() if surface.covered.any() else 1.0
    distance = np.where(surface.covered, surface.distance, farthest)
    occlusion = np.zeros_like(distance)
    for radius, reach in ((4 * SUPERSAMPLE, 1.2), (14 * SUPERSAMPLE, 4.0)):
        deeper = distance - gaussian_filter(distance, radius)
        occlusion += np.clip(deeper / reach, 0, 1)
    return 1 - 0.5 * np.clip(occlusion, 0, 1.4) / 1.4


def _edges(surface: _Surface, hit: np.ndarray) -> np.ndarray:
    """1 where an outline or a crease runs: neighbouring pixels on different CAD faces whose normals
    differ, or where the model ends."""
    ink = np.zeros(hit.shape)
    for axis in (0, 1):
        other_face = np.roll(surface.face, 1, axis=axis)
        other_normal = np.roll(surface.normal, 1, axis=axis)
        other_distance = np.roll(surface.distance, 1, axis=axis)
        with np.errstate(invalid="ignore"):
            jump = np.abs(surface.distance - other_distance) > 0.6
        crease = (surface.normal * other_normal).sum(axis=-1) < CREASE_COSINE
        differs = (surface.face != other_face) & (crease | jump) & (hit | np.roll(hit, 1, axis=axis))
        np.moveaxis(differs, axis, 0)[0] = False  # `roll` wraps round: the first row and column have no neighbour
        ink = np.maximum(ink, differs)
    ink = maximum_filter(ink, size=SUPERSAMPLE)
    return gaussian_filter(ink, 0.4 * SUPERSAMPLE)


def _bloom(glow: np.ndarray, width: int) -> np.ndarray:
    near = gaussian_filter(glow, (width / 220, width / 220, 0))
    far = gaussian_filter(glow, (width / 45, width / 45, 0))
    return near + 1.6 * far


def _background(lighting: Lighting, width: int, height: int) -> np.ndarray:
    blend = np.linspace(0, 1, height)[:, None, None]
    top = _to_linear(np.array(lighting.background_top))
    bottom = _to_linear(np.array(lighting.background_bottom))
    return np.broadcast_to(top * (1 - blend) + bottom * blend, (height, width, 3))


def _to_linear(colour: np.ndarray) -> np.ndarray:
    return np.asarray(colour, dtype=float) ** 2.2


def _to_srgb(colour: np.ndarray) -> np.ndarray:
    return colour ** (1 / 2.2)
