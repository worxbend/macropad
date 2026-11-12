"""Headless pictures: a hero view, an exploded view and a section through the USB port and the display."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from build123d import Part, Plane, Pos, section  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from .components import components  # noqa: E402
from .parts import case_parts  # noqa: E402
from .spec import BOARD, PRINT  # noqa: E402

PART_COLOURS = {
    "base": "#2b2d42", "top": "#2b2d42", "diffuser_left": "#f1e9da", "diffuser_right": "#f1e9da",
    "knob_left": "#ef8354", "knob_right": "#ef8354",
}
COMPONENT_COLOURS = {
    "pcb": "#2d6a4f", "switch": "#d9d9d9", "socket": "#6c757d", "encoder": "#adb5bd", "display": "#8ecae6",
    "usb": "#ced4da", "led": "#ffd166", "button": "#495057",
}
# How far each part lifts in the exploded view.
EXPLODED_LIFT = {"base": -30.0, "pcb": 0.0, "top": 30.0, "knob_left": 50.0, "knob_right": 50.0}
HIDDEN_IN_VIEWS = ("usb_plug",)
# Inside the closed case. Left out of the hero view because matplotlib sorts whole triangles by depth
# and lets large hidden faces bleed through.
INSIDE_THE_CASE = ("pcb", "socket", "led", "button", "usb")


def render_all(images: Path) -> int:
    images.mkdir(parents=True, exist_ok=True)
    solids = {name: solid for name, solid in _coloured_solids().items() if name not in HIDDEN_IN_VIEWS}
    outside = {name: solid for name, solid in solids.items() if not name.startswith(INSIDE_THE_CASE)}
    _render_view(outside, images / "hero.png", lift={})
    _render_view(solids, images / "exploded.png", lift=EXPLODED_LIFT)
    _render_section(_coloured_solids(), images / "section_usb_display.png")
    print(f"rendered to {images}")
    return 0


def _coloured_solids() -> dict[str, tuple[Part, str]]:
    parts = {name: (solid, PART_COLOURS[name]) for name, solid in case_parts(PRINT).items()}
    bought = {name: (solid, _component_colour(name)) for name, solid in components().items()}
    return bought | parts


def _component_colour(name: str) -> str:
    return next(colour for prefix, colour in COMPONENT_COLOURS.items() if name.startswith(prefix))


def _render_view(solids: dict, path: Path, lift: dict[str, float]) -> None:
    """One collection for the whole scene, so matplotlib depth-sorts triangle by triangle."""
    scene_triangles, scene_colours = [], []
    for name, (solid, colour) in solids.items():
        vertices, triangles = (Pos(0, 0, _lift_of(name, lift)) * solid).tessellate(0.1)
        points = np.array([tuple(vertex) for vertex in vertices])
        scene_triangles.append(points[np.array(triangles)])
        scene_colours += [colour] * len(triangles)
    figure = plt.figure(figsize=(10, 8), dpi=150)
    axes = figure.add_subplot(projection="3d")
    axes.add_collection3d(Poly3DCollection(np.concatenate(scene_triangles), facecolors=scene_colours, linewidths=0,
                                           shade=True))
    span = max(BOARD.board.width, BOARD.board.height) / 2 + 8
    centre_x, centre_y = BOARD.board.width / 2, -BOARD.board.height / 2
    axes.set_xlim(centre_x - span, centre_x + span)
    axes.set_ylim(centre_y - span, centre_y + span)
    axes.set_zlim(-span + 10, span + 10)
    axes.set_box_aspect((1, 1, 1))
    axes.view_init(elev=38, azim=-58)
    axes.set_axis_off()
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)


def _lift_of(name: str, lift: dict[str, float]) -> float:
    if not lift:
        return 0.0
    if name in lift:
        return lift[name]
    # Diffusers ride with the base; everything else you buy rides with the PCB.
    return lift["base"] if name.startswith("diffuser") else lift["pcb"]


def _render_section(solids: dict, path: Path) -> None:
    """Cut along the board's centre line: USB port, display window and the centre screws lie on it."""
    cut_plane = Plane.YZ.offset(BOARD.usb.x)
    figure, axes = plt.subplots(figsize=(14, 5), dpi=150)
    for solid, colour in solids.values():
        triangles = _section_triangles(solid, cut_plane)
        if len(triangles):
            axes.add_collection(PolyCollection(triangles, facecolor=colour, edgecolor=colour, linewidth=0.3))
    axes.set_xlim(-10, BOARD.board.height + 6)
    axes.set_ylim(-11, 24)
    axes.set_aspect("equal")
    axes.set_xlabel("board Y, mm (back edge with the USB port on the left)")
    axes.set_ylabel("Z above the PCB top, mm")
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)


def _section_triangles(solid: Part, cut_plane: Plane) -> np.ndarray:
    """Triangles of the cut face as (board Y, Z) pairs."""
    cut = section(solid, section_by=cut_plane)
    found = []
    for face in cut.faces():
        vertices, triangles = face.tessellate(0.05)
        points = np.array([(-vertex.Y, vertex.Z) for vertex in vertices])
        found.extend(points[list(triangle)] for triangle in triangles)
    return np.array(found)
