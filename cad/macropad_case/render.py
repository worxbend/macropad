"""Headless pictures of the case, drawn by the software renderer in `raster.py`."""

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from math import cos, radians, sin
from pathlib import Path

import numpy as np
from build123d import Box, Part, Pos, Rot
from PIL import Image, ImageDraw, ImageFont

from .checks import PRINT_POSES
from .components import DISPLAY_ACTIVE_AREA, drawn_components
from .raster import Camera, Decal, Lighting, Material, Mesh, Scene, mesh_of, render
from .small_parts import case_parts, lens_drawn, tilt_strip
from .solids import LEGEND_FONT
from .spec import BOARD, CASE, CNC, FRONT_ROW, LEVELS, PRINT, case_bounds, encoder_centres, foot_thickness, screw_rows

IMAGE_SIZE = (1600, 1100)
TILE_SIZE = (IMAGE_SIZE[0] // 2, IMAGE_SIZE[1] // 2)
WORKERS = 4  # each view holds about 1 GB of buffers while it renders

GRAPHITE = Material((0.16, 0.17, 0.19), gloss=0.08)
GRAPHITE_KNOB = replace(GRAPHITE, gloss=0.3)  # a little shine, so the grooves catch the light
MATERIALS = {
    "base": GRAPHITE, "top": Material((0.80, 0.79, 0.76), gloss=0.08), "tilt_bar": GRAPHITE, "knob": GRAPHITE_KNOB,
    "diffuser": Material((0.11, 0.11, 0.12), gloss=0.3),  # smoke-grey: unlit, it disappears in the gap
    "keycap": Material((0.93, 0.92, 0.90), gloss=0.12),
    "lens": Material((0.03, 0.03, 0.04), gloss=0.9),
    "foot_strip": Material((0.06, 0.06, 0.06), gloss=0.05),
    "centre_pad": Material((0.06, 0.06, 0.06), gloss=0.05),
    "tilt_strip": Material((0.06, 0.06, 0.06), gloss=0.05),
    "switch": Material((0.16, 0.16, 0.17), gloss=0.3),
    "socket": Material((0.30, 0.31, 0.33)),
    "pcb": Material((0.08, 0.42, 0.30), gloss=0.3),
    "display_glass": Material((0.42, 0.45, 0.47), gloss=0.9),
    "display_pixels": Material((0.66, 0.71, 0.63), gloss=0.9),
    "display": Material((0.10, 0.16, 0.30)),
    "encoder": Material((0.70, 0.71, 0.73), gloss=0.6),
    "usb_receptacle": Material((0.78, 0.79, 0.81), gloss=0.7),
    "usb_plug": Material((0.12, 0.12, 0.13), gloss=0.25),
    "led": Material((1.0, 0.96, 0.80)),
    "button": Material((0.25, 0.25, 0.27)),
    "screw": Material((0.72, 0.73, 0.76), gloss=0.8),
}
GLOWING_DIFFUSER = Material((0.98, 0.93, 0.82), glow=2.2)  # a guess: warm white; the LEDs are RGB


def _anodised(colour: tuple[float, float, float]) -> Material:
    return Material(colour, gloss=0.45, metal=0.6)


def _two_tone(top: Material, base: Material, knob: Material, keycap: tuple[float, float, float]) -> dict[str, Material]:
    return {"top": top, "base": base, "tilt_bar": base, "knob": knob, "keycap": Material(keycap, gloss=0.12)}


SILVER, SPACE_GREY = _anodised((0.77, 0.78, 0.80)), _anodised((0.33, 0.34, 0.36))
# Each colourway: the scene it is drawn from and the materials it changes. Chalk is `MATERIALS` as it stands.
ASSEMBLY, MILLED, CUT_ALONG, CUT_ACROSS, SHELLS, BED = "assembly", "milled", "cut_along", "cut_across", "shells", "bed"
COLOURWAYS = {
    "Chalk, printed": (ASSEMBLY, {}),
    "Graphite, printed": (ASSEMBLY, _two_tone(
        Material((0.17, 0.18, 0.20), gloss=0.08), Material((0.09, 0.09, 0.10), gloss=0.08), GRAPHITE_KNOB,
        (0.22, 0.22, 0.24))),
    "Silver, milled": (MILLED, _two_tone(SILVER, SILVER, SILVER, (0.14, 0.14, 0.15))),
    "Space grey, milled": (MILLED, _two_tone(SPACE_GREY, SPACE_GREY, SPACE_GREY, (0.10, 0.10, 0.11))),
}
FROM_BELOW = Lighting(key_direction=(-0.45, -0.35, -0.82), key=1.15, ambient=0.6, fill=0.35)
FROM_BEHIND = Lighting(key_direction=(-0.45, 0.6, 0.66))  # the default light only grazes the back wall
RAKING = Lighting(key_direction=(-0.85, -0.3, 0.45), key=1.25, ambient=0.36, fill=0.3)  # low: for the knob grooves
NIGHT = Lighting(key=0.22, fill=0.06, ambient=0.10, background_top=(0.05, 0.05, 0.07),
                 background_bottom=(0.09, 0.09, 0.12), bloom=0.55, edge_ink=0.25)

CENTRE = (BOARD.board.width / 2, -BOARD.board.height / 2, 3.0)
FRONT_STRIP_LINE = screw_rows()[FRONT_ROW][0][1]
FEET_BOTTOM = LEVELS.foot_recess_roof - foot_thickness(FRONT_ROW)
EXPLODED_LIFT = {"base": -34.0, "diffuser": -16.0, "screw": -58.0, "foot_strip": -84.0, "centre_pad": -84.0,
                 "top": 62.0, "lens": 74.0, "switch": 100.0, "keycap": 130.0, "knob": 152.0}
SECTION_X = BOARD.usb.x  # the cut passes through the USB port, the lens, the display and the two centre screws
SECTION_Y = BOARD.leds.left_y[1]  # a second cut, across the pad through one LED on each side
PLUG_PULLED_OUT = 14.0
# The firmware simulator's picture of the display. Without it the display is drawn blank.
DISPLAY_PICTURE = Path(__file__).resolve().parents[2] / "docs" / "images" / "ui" / "media.png"
DISPLAY_PICTURE_SIZE = (320, 136)  # two texels per display pixel: enough for these views, and it does not shimmer
CUT_FACE_TINT = 0.45  # how far a cut face is lightened toward white
CUT_HATCH = {"base": 1.1, "top": -1.1}  # mm between hatch lines on the two shells, leaning opposite ways
CAP_TOLERANCE = 1e-3
SHELLS_GAP = 10.0
BED_GAP = 8.0
LONG_PART = 2.0  # on the bed, a part this many times longer than wide is turned to lie across the row
TILE_LABEL = (22, (18, 16), (0.25, 0.27, 0.30))  # font size in pixels, position from the top-left corner, colour
# For each cut scene: the model axis the cut plane is normal to, where it lies, and which side stays.
CUTS = {CUT_ALONG: (0, SECTION_X, -1), CUT_ACROSS: (1, -SECTION_Y, 1)}


@dataclass
class View:
    name: str
    camera: Camera
    lighting: Lighting = Lighting()
    scene: str = ASSEMBLY
    hidden: tuple[str, ...] = ("usb_plug",)
    lift: dict[str, float] = field(default_factory=dict)
    tilted: bool = False
    ground: float | None = FEET_BOTTOM
    overrides: dict[str, Material] = field(default_factory=dict)
    size: tuple[int, int] = IMAGE_SIZE


def _camera(offset: tuple[float, float, float], target: tuple[float, float, float] = CENTRE, **options) -> Camera:
    return Camera(tuple(np.add(target, offset)), target, **options)


HERO_CAMERA = _camera((-95, -170, 250), target=(CENTRE[0], CENTRE[1] - 2, 4.0), field_of_view=21)
LEFT_KNOB = (encoder_centres()[0][0], -encoder_centres()[0][1], (LEVELS.knob_bottom + LEVELS.knob_top) / 2)
BACK_FACE = -case_bounds()[1][0]  # model Y of the back of the case


def _colourway(name: str, picture: str, size: tuple[int, int] = IMAGE_SIZE) -> View:
    scene, materials = COLOURWAYS[name]
    return View(picture, HERO_CAMERA, scene=scene, overrides=materials, size=size)


VIEWS = [
    _colourway("Chalk, printed", "hero"),
    _colourway("Silver, milled", "hero_aluminium"),
    View("top_plan", _camera((0, 0, 420), target=(CENTRE[0], CENTRE[1], 0.0), field_of_view=17, up=(0.0, 1.0, 0.0))),
    View("side_profile", _camera((-420, 0, 22), target=(0.0, CENTRE[1], 5.0), field_of_view=11.5)),
    View("exploded", _camera((-250, -430, 290), target=(CENTRE[0], CENTRE[1], 40.0), field_of_view=33),
         lift=EXPLODED_LIFT, ground=None, size=(1300, 1700)),
    View("section_usb_display", _camera((330, -70, 95), target=(SECTION_X, CENTRE[1] + 4, 4.0), field_of_view=14),
         scene=CUT_ALONG, hidden=("tilt_bar",)),
    View("section_light_line", _camera((-40, -200, 46), target=(17.0, -SECTION_Y, 4.5), field_of_view=12),
         scene=CUT_ACROSS, hidden=("tilt_bar", "usb_plug"), ground=None),
    View("back_usb", _camera((70, 250, 80), target=(CENTRE[0], -20.0, 2.0), field_of_view=19), lighting=FROM_BEHIND,
         hidden=()),
    View("usb_detail", _camera((26, 120, 24), target=(BOARD.usb.x, BACK_FACE, -2.0), field_of_view=13),
         lighting=FROM_BEHIND),
    View("underside", _camera((-70, -150, -250), field_of_view=22, up=(0.0, 1.0, 0.0)), lighting=FROM_BELOW,
         ground=None),
    View("underside_aluminium", _camera((-70, -150, -250), field_of_view=22, up=(0.0, 1.0, 0.0)), lighting=FROM_BELOW,
         scene=MILLED, ground=None, overrides=COLOURWAYS["Silver, milled"][1]),
    View("light_line", _camera((-150, -130, 22), target=(4.0, -50.0, -1.0), field_of_view=17), lighting=NIGHT,
         overrides={"diffuser": GLOWING_DIFFUSER}),
    View("deck_detail", _camera((-60, -105, 95), target=(36.0, -13.0, 9.0), field_of_view=20)),
    View("knob_detail", _camera((-46, -62, 44), target=LEFT_KNOB, field_of_view=14), lighting=RAKING, scene=MILLED,
         overrides=COLOURWAYS["Silver, milled"][1]),  # on the dark knob of the other colourways the grooves hardly show
    View("tilt", _camera((-330, -45, 35), target=(0.0, CENTRE[1], 4.0), field_of_view=12),
         hidden=("usb_plug", "foot_strip_back"), tilted=True),
    View("shells_inside", _camera((-60, -260, 300), target=(BOARD.board.width + SHELLS_GAP / 2 + 3, CENTRE[1], 0.0),
                                  field_of_view=27), scene=SHELLS, hidden=(), ground=LEVELS.floor_bottom),
    View("print_plate", _camera((170, -330, 250), target=(100.0, -44.0, 12.0), field_of_view=30), scene=BED,
         hidden=(), ground=0.0),
]
COLOURWAY_TILES = [_colourway(name, name, TILE_SIZE) for name in COLOURWAYS]


def render_all(images: Path) -> int:
    images.mkdir(parents=True, exist_ok=True)
    scenes = _scene_meshes()
    with ProcessPoolExecutor(WORKERS) as pool:
        jobs = {view.name: pool.submit(_render_view, view, scenes[view.scene]) for view in VIEWS + COLOURWAY_TILES}
        for view in VIEWS:
            _save(jobs[view.name].result(), images / f"{view.name}.png")
        _save(_tiled({tile.name: jobs[tile.name].result() for tile in COLOURWAY_TILES}), images / "colourways.png")
    return 0


def _save(picture: np.ndarray, path: Path) -> None:
    Image.fromarray(picture).save(path, optimize=True)
    print(f"rendered {path.name}")


def _tiled(tiles: dict[str, np.ndarray]) -> np.ndarray:
    """Four pictures in two rows of two, each with its name in the top-left corner."""
    font_size, position, colour = TILE_LABEL
    font = ImageFont.truetype(str(LEGEND_FONT), font_size)
    labelled = []
    for name, picture in tiles.items():
        tile = Image.fromarray(picture)
        ImageDraw.Draw(tile).text(position, name, font=font, fill=tuple(int(channel * 255) for channel in colour))
        labelled.append(np.asarray(tile))
    return np.vstack([np.hstack(labelled[:2]), np.hstack(labelled[2:])])


def _scene_meshes() -> dict[str, dict[str, Mesh]]:
    printed, milled = case_parts(PRINT), case_parts(CNC)
    assembly = printed | drawn_components() | tilt_strip()
    scenes = {
        ASSEMBLY: _meshes(assembly | {"lens": lens_drawn()}),
        SHELLS: _meshes(_shells_side_by_side(printed)),
        BED: _meshes(_parts_on_the_bed(printed)),
    }
    # The milled build differs from the printed one in its two shells only.
    scenes[MILLED] = scenes[ASSEMBLY] | _meshes({name: milled[name] for name in ("base", "top")})
    # The cuts show the whole lens: a cut through its window would leave only the two borders.
    for name, (axis, position, keep) in CUTS.items():
        scenes[name] = _with_cut_faces(_meshes(_cut_open(assembly, axis, position, keep)), axis, position)
    return scenes


def _meshes(solids: dict[str, Part]) -> dict[str, Mesh]:
    meshes = {name: mesh_of(solid, material_of(name)) for name, solid in solids.items()}
    if "display_pixels" in meshes and DISPLAY_PICTURE.exists():
        meshes["display_pixels"].decal = _display_decal()
    return meshes


def _display_decal() -> Decal:
    """The simulator's picture, laid on the lit area of the display as the user reads it."""
    picture = Image.open(DISPLAY_PICTURE).convert("RGB").resize(DISPLAY_PICTURE_SIZE, Image.Resampling.BOX)
    width, height = DISPLAY_ACTIVE_AREA
    left = BOARD.display.window_x - width / 2
    back = -BOARD.display.window_y + height / 2
    origin = np.array((left, back, BOARD.stack.display_glass_top))
    return Decal(np.asarray(picture) / 255.0, origin, np.array((width, 0.0, 0.0)), np.array((0.0, -height, 0.0)))


def material_of(name: str) -> Material:
    """The material of the longest key that starts the part's name."""
    return MATERIALS[max((key for key in MATERIALS if name.startswith(key)), key=len)]


def _cut_open(solids: dict[str, Part], axis: int, position: float, keep: int) -> dict[str, Part]:
    """Everything on one side of a cut plane, so the camera on the other side looks into the cut."""
    centre = [0.0, 0.0, 0.0]
    centre[axis] = position + keep * 250
    kept_space = Pos(*centre) * Box(500, 500, 500)
    found = {}
    for name, solid in solids.items():
        kept = solid & kept_space
        if kept is not None and kept.solids():
            found[name] = kept
    return found


def _with_cut_faces(meshes: dict[str, Mesh], axis: int, position: float) -> dict[str, Mesh]:
    """Split off the triangles that lie in the cut plane and give them a lighter, hatched material."""
    found = {}
    for name, mesh in meshes.items():
        in_the_cut = (np.abs(mesh.triangles[..., axis] - position) < CAP_TOLERANCE).all(axis=1)
        tint = tuple(channel + (1 - channel) * CUT_FACE_TINT for channel in mesh.material.colour)
        hatch = next((spacing for key, spacing in CUT_HATCH.items() if name.startswith(key)), 0.0)
        found[name] = mesh.only(~in_the_cut, mesh.material)
        if in_the_cut.any():
            found[f"{name}:cut"] = mesh.only(in_the_cut, Material(tint, gloss=0.0, hatch=hatch))
    return found


def _shells_side_by_side(parts: dict[str, Part]) -> dict[str, Part]:
    """The base as it lies on the desk and, to its right, the top turned over, both seen from inside."""
    turned = Rot(0, 180, 0) * parts["top"]
    box = turned.bounding_box()
    beside = case_bounds()[0][1] + SHELLS_GAP - box.min.X
    return {"base": parts["base"], "top": Pos(beside, 0, LEVELS.floor_bottom - box.min.Z) * turned}


def _parts_on_the_bed(parts: dict[str, Part]) -> dict[str, Part]:
    """Each printed part the way it prints, in a row on a bed at Z = 0. Long parts lie across the row."""
    found, cursor = {}, 0.0
    for name, pose in PRINT_POSES.items():
        posed = pose * parts[name]
        if posed.bounding_box().size.X > LONG_PART * posed.bounding_box().size.Y:
            posed = Rot(0, 0, 90) * posed
        box = posed.bounding_box()
        found[name] = Pos(cursor - box.min.X, -box.max.Y, -box.min.Z) * posed
        cursor += box.size.X + BED_GAP
    return found


def _render_view(view: View, meshes: dict[str, Mesh]) -> np.ndarray:
    scene = Scene(ground_z=view.ground)
    for name, mesh in meshes.items():
        if name.startswith(view.hidden) or (name.startswith("tilt_") and not view.tilted and view.scene != BED):
            continue
        override = next((material for key, material in view.overrides.items() if name.startswith(key)), None)
        mesh = replace(mesh, material=override) if override else mesh
        scene.meshes.append(_placed(mesh, name, view))
    return render(scene, view.camera, view.size, view.lighting)


def _placed(mesh: Mesh, name: str, view: View) -> Mesh:
    identity = np.eye(3)
    if name == "usb_plug" and view.scene in (ASSEMBLY, MILLED):
        mesh = mesh.moved(identity, np.array((0.0, PLUG_PULLED_OUT, 0.0)))
    lift = next((height for key, height in view.lift.items() if name.startswith(key)), 0.0)
    if lift:
        mesh = mesh.moved(identity, np.array((0.0, 0.0, lift)))
    return _tilted(mesh) if view.tilted else mesh


def _tilted(mesh: Mesh) -> Mesh:
    """The whole pad turned about its front strip, so the desk stays level in the picture."""
    angle = radians(CASE.tilt_angle)
    pivot = np.array((0.0, -FRONT_STRIP_LINE, FEET_BOTTOM))
    about_x = np.array(((1, 0, 0), (0, cos(angle), -sin(angle)), (0, sin(angle), cos(angle))))
    return mesh.moved(about_x, pivot - about_x @ pivot)
