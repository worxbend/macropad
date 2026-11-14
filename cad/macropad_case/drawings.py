"""A dimensioned general-arrangement drawing as SVG: top, front and right views with hidden lines
removed, and a section through the USB port and the display. Two more sheets are for the machine
shop. Every dimension text is computed from the model, never typed in."""

import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from build123d import Box, Compound, ExportDXF, GeomType, Part, Plane, Pos, Sketch, Unit, mirror, section

from .components import drawn_components
from .parts import drill_point_height, underside_artwork, usb_opening_profile
from .small_parts import case_parts, lens_mask_outline, lens_outline
from .solids import case_outline, discs, offset_sketch, stadium
from .spec import BOARD, CASE, CNC, CNC_PART_NUMBERS, LEVELS, PRINT, REVISION, Span, buttons, case_bounds, dish_rim
from .spec import encoder_centres, foot_span, grown, key_centres, knob_well_diameter, led_slot_span, lens_opening
from .spec import lens_recess, lens_span, mounting_holes, screw_rows, screw_seat, usb_corner_radii, usb_opening_size

SHEET = (420.0, 297.0)  # A3 landscape, mm
SCALE = 1.6
SECTION_X = BOARD.usb.x
CENTRE = (BOARD.board.width / 2, -BOARD.board.height / 2)  # model X, Y that every view looks at
(LEFT, RIGHT_SIDE), (BACK, FRONT_SIDE) = case_bounds()  # board coordinates of the four faces of the case
NOT_DRAWN = ("tilt_", "usb_plug")
CURVE_STEP = 0.6  # mm between points when a curved edge is drawn as a polyline
FAR = 500.0
LETTER_WIDTH = 1.9  # sheet mm per character of dimension text, on average
FONT = "DejaVu Sans, Arial, sans-serif"
SECTION_FILLS = {
    "base": "url(#hatch)", "top": "url(#hatch-back)", "knob": "#9a9fa8", "diffuser": "#8d8f94", "pcb": "#9cc5a9",
    "keycap": "#e8e5dd", "switch": "#b9b9bd", "display_glass": "#c9d6dc", "display": "#9fb1d1", "usb": "#d5d7db",
    "screw": "#c3c6cc", "foot_strip": "#6d6d6d", "centre_pad": "#6d6d6d", "lens": "#3d4046", "socket": "#a7a9ad",
    "encoder": "#c7cacf",
}


@dataclass(frozen=True)
class Frame:
    """Where a view sits on the sheet: sheet position of the view's own origin, in mm."""

    x: float
    y: float
    scale: float = SCALE

    def place(self, across: float, up: float) -> tuple[float, float]:
        return self.x + self.scale * across, self.y - self.scale * up


TOP = Frame(114.0, 112.0)
FRONT = Frame(114.0, 258.0)
RIGHT = Frame(310.0, 258.0)
CUT = Frame(310.0, 150.0)
# Part sheets: two plans, a section through the centre screws and an enlarged detail of the lap joint.
PLAN_ABOVE = Frame(86.0, 104.0, 1.5)
PLAN_BELOW = Frame(232.0, 104.0, 1.5)
PART_CUT = Frame(134.0, 230.0, 2.0)
DETAIL_SCALE = 8.0
DETAIL_AT = (272.0, 250.0)  # sheet position of the detail's centre
DETAIL_SIZE = (7.0, 8.0)  # model mm shown, across and up
TITLE_BLOCK_AT = (312.0, 9.0)  # top-left corner of the title block on a part sheet
TITLE_BLOCK_SIZE = (101.0, 4.4)  # width, row height
TABLE_AT = (312.0, 58.0)
TABLE_LINE = 4.8
NOTES_AT = 255.0  # sheet Y of the first line of notes on a part sheet
NOTE_LINE = 3.5
# The second column of notes on a part sheet, under the feature table: finish, tolerances, workholding.
SIDE_NOTES_AT = (312.0, 156.0)
SIDE_NOTE_WIDTH = 62  # characters per line
LAST_LINE = SHEET[1] - 8.0  # no text below this, inside the sheet frame
# The USB opening seen from behind, between the plan from below and the lap detail.
USB_DETAIL = Frame(190.0, 192.0, 3.0)
USB_NOTES_AT = (226.0, 179.0)
USB_NOTE_WIDTH = 44
# Tolerances on the critical fits, all after anodise. ISO 2768-m holds everywhere else.
POSITION_TOLERANCE = 0.05  # screw holes from datum A
PLATE_TOLERANCE = 0.05
LAP_TOLERANCE = 0.03  # lap ridge and groove
CUTOUT_PLUS = 0.05  # switch cut-outs: +0.05 / 0
LENS_DEPTH_TOLERANCE = 0.05
USB_TOLERANCE = 0.1
CUT_LETTER_ASIDE = 6.0  # sheet mm left of the cut line, so a letter clears dimension text centred on it
# The back letter sits just inside the back face: above it run the dimension lines of the lens and the knobs.
CUT_LETTER_INSIDE = 6.0
PREVIEW_NAMES = {"general_arrangement": "general_arrangement", "base": "drawing_base", "top": "drawing_top"}


def write_drawings(folder: Path, images: Path) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    milled = case_parts(CNC)
    sheets = {
        "general_arrangement": general_arrangement(),
        "base": part_sheet(BASE_SHEET, milled["base"]),
        "top": part_sheet(TOP_SHEET, milled["top"]),
    }
    converter = shutil.which("rsvg-convert")
    for name, content in sheets.items():
        drawing = folder / f"{name}.svg"
        drawing.write_text(content)
        print(f"drew {drawing}")
        if converter is None:
            continue
        subprocess.run([converter, "-f", "pdf", "-o", str(drawing.with_suffix(".pdf")), str(drawing)], check=True)
        preview = images / f"{PREVIEW_NAMES[name]}.png"
        subprocess.run([converter, "-w", "2400", "-b", "white", "-o", str(preview), str(drawing)], check=True)
        print(f"drew {drawing.with_suffix('.pdf')} and {preview}")
    if converter is None:
        print("rsvg-convert not found: no PDF and no PNG of the drawings were written")
    write_outlines(folder)
    return 0


def write_outlines(folder: Path) -> None:
    """Flat artwork as DXF: the marks on the underside, for laser-marking the milled base, and the
    lens with its mask, for whoever cuts and prints it. The top face carries no mark."""
    underside = folder / "engraving_underside.dxf"
    write_underside_marks(underside)
    print(f"drew {underside}")
    for name, artwork in {"lens": lens_outline(), "lens_mask": lens_mask_outline()}.items():
        exporter = ExportDXF(unit=Unit.MM)
        exporter.add_shape(artwork)
        exporter.write(str(folder / f"{name}.dxf"))
        print(f"drew {folder / f'{name}.dxf'}")


def write_underside_marks(path: Path) -> None:
    """The underside marks as the laser sees them: from below, not mirrored, origin at datum A.
    The model draws them as seen from above (mirrored). Mirroring X about datum A turns them the
    right way round, with the back edge at the top, so a point at (X, Y) from datum A in the hole
    table lands at (-X, -Y). Layer MARK is marked; layer REF holds the outline and the holes, to
    register the part, and is not marked."""
    marks = from_below(underside_artwork())
    reference = [from_below(sketch) for sketch in underside_reference()]
    outline_box, mark_box = reference[0].bounding_box(), marks.bounding_box()
    assert abs(outline_box.max.X) < 1e-6 and abs(outline_box.max.Y) < 1e-6, "datum A is not the outline's corner"
    assert outline_box.min.X < mark_box.min.X and mark_box.max.X < outline_box.max.X, "the marks run past the outline"
    assert outline_box.min.Y < mark_box.min.Y and mark_box.max.Y < outline_box.max.Y, "the marks run past the outline"
    exporter = ExportDXF(unit=Unit.MM)
    exporter.add_layer("MARK")
    exporter.add_layer("REF")
    exporter.add_shape(marks, layer="MARK")
    exporter.add_shape(reference, layer="REF")
    exporter.write(str(path))


def underside_reference() -> list[Sketch]:
    """What a laser operator registers on, drawn as seen from above: the outline first, then the
    screw counterbores, the BOOT and RESET holes and the foot slots."""
    return [
        case_outline(CNC),
        discs(mounting_holes(), CASE.counterbore_diameter),
        discs(list(buttons().values()), CASE.button_hole_diameter),
        *[stadium(grown(foot_span(row), CASE.foot_recess_fit)) for row in screw_rows()],
    ]


def from_below(artwork: Sketch) -> Sketch:
    """Sketch coordinates (board X, minus board Y) to the underside DXF frame."""
    return Pos(LEFT, BACK) * mirror(artwork, Plane.YZ)


def general_arrangement() -> str:
    solids = {
        name: solid for name, solid in (case_parts(PRINT) | drawn_components(PRINT)).items()
        if not name.startswith(NOT_DRAWN)
    }
    assembly = Compound(children=list(solids.values()))
    eye_height = (*CENTRE, FAR)
    views = [
        _outline(assembly, eye_height, (0, 1, 0), TOP),
        _outline(assembly, (CENTRE[0], -FAR, 0), (0, 0, 1), FRONT),
        _outline(assembly, (FAR, CENTRE[1], 0), (0, 0, 1), RIGHT),
        _cut_view(solids, CUT),
    ]
    body = [_sheet_frame(), *views, *_top_dimensions(), *_front_dimensions(), *_right_dimensions(), *_cut_dimensions(),
            *_labels()]
    return _svg(body)


def _outline(assembly: Compound, eye: tuple[float, float, float], up: tuple[float, float, float], frame: Frame) -> str:
    """Visible edges of the whole pad from one side."""
    visible, _hidden = assembly.project_to_viewport(eye, up, look_at=(*CENTRE, 0))
    paths = [_polyline([frame.place(x, y) for x, y in _points_along(edge)]) for edge in visible]
    return f'<path class="visible" d="{" ".join(paths)}"/>'


def _points_along(edge) -> list[tuple[float, float]]:
    steps = 1 if edge.geom_type == GeomType.LINE else max(4, int(edge.length / CURVE_STEP))
    return [(point.X, point.Y) for point in (edge.position_at(step / steps) for step in range(steps + 1))]


def _polyline(points: list[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _cut_view(solids: dict[str, Part], frame: Frame) -> str:
    """Section on the plane X = `SECTION_X`, seen from the right: every solid it cuts, filled."""
    plane = Plane.YZ.offset(SECTION_X)
    shapes = []
    for name, solid in solids.items():
        fill = next((colour for key, colour in SECTION_FILLS.items() if name.startswith(key)), "#dddddd")
        for face in section(solid, section_by=plane).faces():
            loops = [face.outer_wire(), *face.inner_wires()]
            path = " ".join(_polyline(_cut_points(loop, frame)) + " Z" for loop in loops)
            shapes.append(f'<path class="cut" fill="{fill}" fill-rule="evenodd" d="{path}"/>')
    return "\n".join(shapes)


def _cut_points(loop, frame: Frame) -> list[tuple[float, float]]:
    points = []
    for edge in loop.order_edges():
        steps = 1 if edge.geom_type == GeomType.LINE else max(4, int(edge.length / CURVE_STEP))
        points += [edge.position_at(step / steps) for step in range(steps)]
    return [frame.place(point.Y - CENTRE[1], point.Z) for point in points]


# Dimensions. `across` and `up` are view coordinates in mm: across from the view centre, up from Z = 0.

def _dimension(frame: Frame, start: tuple[float, float], end: tuple[float, float], offset: float, text: str,
               along: bool = False) -> str:
    """A dimension between two points that share a row (horizontal) or a column (vertical).
    `offset` moves the dimension line away from the points, in sheet mm. A vertical dimension's text
    runs along the line when it fits or when `along` is set; otherwise it sits level, outside the line."""
    (x1, y1), (x2, y2) = frame.place(*start), frame.place(*end)
    horizontal = abs(y1 - y2) < abs(x1 - x2)
    if horizontal:
        line_y = min(y1, y2) + offset if offset < 0 else max(y1, y2) + offset
        witness = f"M{x1:.2f},{y1:.2f} V{line_y:.2f} M{x2:.2f},{y2:.2f} V{line_y:.2f}"
        line = f"M{x1:.2f},{line_y:.2f} H{x2:.2f}"
        label = f'<text x="{(x1 + x2) / 2:.2f}" y="{line_y - 1.2:.2f}" text-anchor="middle">{escape(text)}</text>'
    else:
        line_x = min(x1, x2) + offset if offset < 0 else max(x1, x2) + offset
        witness = f"M{x1:.2f},{y1:.2f} H{line_x:.2f} M{x2:.2f},{y2:.2f} H{line_x:.2f}"
        line = f"M{line_x:.2f},{y1:.2f} V{y2:.2f}"
        fits = abs(y1 - y2) >= LETTER_WIDTH * len(text)
        label = _upright_label(line_x, (y1 + y2) / 2, text, along or fits, outside=1 if offset > 0 else -1)
    return f'<path class="witness" d="{witness}"/><path class="dimension" d="{line}"/>{label}'


def _upright_label(line_x: float, middle: float, text: str, along: bool, outside: int) -> str:
    """Text for a vertical dimension: along the line, or level on the side away from the view."""
    if along:
        return (f'<text x="{line_x - 1.2:.2f}" y="{middle:.2f}" text-anchor="middle" '
                f'transform="rotate(-90 {line_x - 1.2:.2f} {middle:.2f})">{escape(text)}</text>')
    anchor = "start" if outside > 0 else "end"
    return f'<text x="{line_x + 2 * outside:.2f}" y="{middle + 1.1:.2f}" text-anchor="{anchor}">{escape(text)}</text>'


def _mm(value: float, places: int = 2) -> str:
    return f"{value + 0.0:.{places}f}".rstrip("0").rstrip(".")


def _plan_point(board_x: float, board_y: float) -> tuple[float, float]:
    """Board position as (across, up) of a plan seen from above."""
    return board_x - CENTRE[0], -board_y - CENTRE[1]


def _side_point(board_y: float, z: float) -> tuple[float, float]:
    """Board Y and height as (across, up) of a view or a section seen from the right."""
    return -board_y - CENTRE[1], z


def _top_dimensions() -> list[str]:
    keys = key_centres()
    (left_x, knob_y), (right_x, _) = encoder_centres()
    (lens_start, lens_end), (lens_back, _) = lens_span()
    above_the_case = -(SCALE * (knob_y - BACK) + 11)
    below_the_case = SCALE * (FRONT_SIDE - keys[-1][1]) + 8
    right_of_the_case = SCALE * (RIGHT_SIDE - keys[-1][0]) + 10
    return [
        _dimension(TOP, _plan_point(LEFT, BACK), _plan_point(RIGHT_SIDE, BACK), -22, _mm(RIGHT_SIDE - LEFT)),
        _dimension(TOP, _plan_point(LEFT, BACK), _plan_point(LEFT, FRONT_SIDE), -16, _mm(FRONT_SIDE - BACK)),
        _dimension(TOP, _plan_point(left_x, knob_y), _plan_point(right_x, knob_y), above_the_case, _mm(right_x - left_x)),
        _dimension(TOP, _plan_point(lens_start, lens_back), _plan_point(lens_end, lens_back),
                   -(SCALE * (lens_back - BACK) + 3), f"{_mm(CASE.lens[0])} lens"),
        _dimension(TOP, _plan_point(*keys[-2]), _plan_point(*keys[-1]), below_the_case, _mm(BOARD.keys.pitch)),
        _dimension(TOP, _plan_point(*keys[BOARD.keys.columns - 1]), _plan_point(*keys[2 * BOARD.keys.columns - 1]),
                   right_of_the_case, _mm(BOARD.keys.pitch)),
    ]


def _front_dimensions() -> list[str]:
    left, right = LEFT - CENTRE[0], RIGHT_SIDE - CENTRE[0]
    desk = LEVELS.foot_recess_roof - CASE.foot_strip[1]
    rows = [(LEVELS.plate_top, -10, "dish floor"), (BOARD.stack.deck_top, -18, "top face"), (LEVELS.knob_top, -26, "knobs")]
    heights = [
        _dimension(FRONT, (left, desk), (left, level), offset, f"{_mm(level - desk)} {label}", along=True)
        for level, offset, label in rows
    ]
    return heights + [_dimension(FRONT, (left, desk), (right, desk), 9, _mm(right - left))]


def _right_dimensions() -> list[str]:
    back = _side_point(BACK, 0)[0]
    return [
        _dimension(RIGHT, (back, LEVELS.floor_bottom), (back, 0), 8, f"{_mm(-LEVELS.floor_bottom)} base"),
        _dimension(RIGHT, (back, 0), (back, BOARD.stack.deck_top), 8, f"{_mm(BOARD.stack.deck_top)} top"),
    ]


def _cut_dimensions() -> list[str]:
    front = _side_point(FRONT_SIDE, 0)[0]
    inside_front = front + CASE.front_wall
    return [
        _dimension(CUT, (front, LEVELS.floor_bottom), (front, LEVELS.floor_top), -8, f"{_mm(CASE.floor)} floor"),
        _dimension(CUT, (front, LEVELS.floor_top), (front, LEVELS.pcb_bottom), -8,
                   f"{_mm(BOARD.stack.underside_clearance)} under the PCB"),
        _dimension(CUT, (front, 0), (front, LEVELS.plate_top), -8, f"{_mm(LEVELS.plate_top)} PCB to plate"),
        _dimension(CUT, (front, LEVELS.pcb_bottom), (front, 0), -8, f"{_mm(BOARD.board.thickness)} PCB"),
        _dimension(CUT, (front, LEVELS.floor_bottom), (inside_front, LEVELS.floor_bottom), 8,
                   f"{_mm(CASE.front_wall, 3)} front wall"),
    ]


def _labels() -> list[str]:
    def title(frame: Frame, across: float, up: float, text: str) -> str:
        x, y = frame.place(across, up)
        return f'<text class="title" x="{x:.2f}" y="{y:.2f}">{escape(text)}</text>'

    plan_left, plan_back = _plan_point(LEFT, BACK)
    view_left = _side_point(FRONT_SIDE, 0)[0]
    notes = [
        "macropad case, general arrangement",
        f"Scale {SCALE:g}:1 on A3. Dimensions in mm, computed from board.toml and spec.py.",
        "Third-angle projection. Print variant shown, keys not pressed. Heights in FRONT are from the desk.",
        "Not built or measured yet: values tagged MEASURE in the sources are from datasheets.",
    ]
    block = "".join(
        f'<text class="{"title" if index == 0 else "note"}" x="232" y="{24 + 6.5 * index:.1f}">{escape(note)}</text>'
        for index, note in enumerate(notes)
    )
    return [
        title(TOP, plan_left, plan_back + 16, "TOP"),
        title(FRONT, view_left, LEVELS.knob_top + 7, "FRONT"),
        title(RIGHT, view_left, LEVELS.knob_top + 7, "RIGHT"),
        title(CUT, view_left, LEVELS.knob_top + 7, "SECTION A-A (through the USB port, the lens and two screws)"),
        _cut_line(TOP, "A"), block,
    ]


def _cut_line(frame: Frame, letter: str) -> str:
    """The trace of the section plane on a plan view, with its letter beside both ends."""
    x, top = frame.place(*_plan_point(SECTION_X, BACK - 4.5))
    _, bottom = frame.place(*_plan_point(SECTION_X, FRONT_SIDE + 4.5))
    _, back_face = frame.place(*_plan_point(SECTION_X, BACK))
    letter_x = x - CUT_LETTER_ASIDE
    return (f'<path class="centre" d="M{x:.2f},{top:.2f} V{bottom:.2f}"/>'
            f'<text class="title" x="{letter_x:.2f}" y="{back_face + CUT_LETTER_INSIDE:.2f}">{letter}</text>'
            f'<text class="title" x="{letter_x:.2f}" y="{bottom - 1.5:.2f}">{letter}</text>')


@dataclass(frozen=True)
class PartSheet:
    name: str  # which case part
    title: str
    fill: str
    detail_height: float  # model Z at the middle of the lap detail
    notes: tuple[str, ...]
    side_notes: tuple[str, ...] = ()  # material, finish and workholding, in a column of their own


# One finish for both parts. Nothing has been milled or anodised yet; the coating build-up is a guess.
FINISH = "Bead blast, then clear anodise (natural silver)"
FINISH_NOTES = (
    "MATERIAL AND FINISH",
    "6061-T6 aluminium.",
    "Bead blast all over, 120 to 150 grit glass bead, then anodise to MIL-A-8625 Type II, Class 1 (clear, "
    "not dyed), 8 to 12 um. Colour: natural silver, as in the renders. Cosmetic faces: the outside and the top face.",
    "Anodise grows each face by about 0.004 to 0.006 mm (a guess: half the coating). The tolerances below "
    "hold after anodise.",
    "Break unmarked edges 0.05. The 0.3 chamfers are cosmetic: measure them after blasting.",
)
POSITION_NOTE = f"S1-S6 positions from datum A: \u00b1{_mm(POSITION_TOLERANCE)}, on both parts."
CORNER_NOTE = (
    f"Outline corners: one quintic Bezier each, control points {_mm(CASE.corner_setback)}, "
    f"{_mm(CASE.corner_setback * CASE.corner_handles[0])} and {_mm(CASE.corner_setback * CASE.corner_handles[1])} mm "
    "from the box corner on both sides. Take the curve from the STEP file."
)
THREAD_CALLOUT = (
    f"M2x0.4-6H, {_mm(CASE.cnc_full_thread)} min full thread, drill \u2300{_mm(CASE.cnc_tap_drill[0])} x "
    f"{_mm(CASE.cnc_tap_drill[1])}, do not exceed {_mm(CASE.cnc_tap_drill_limit)}"
)
BASE_SHEET = PartSheet(
    "base", "macropad case: base, CNC variant", "url(#hatch)", -1.5,
    (
        "3-axis, two setups: inside up, then underside up.",
        f"Every vertical pocket corner is R{_mm(CASE.cnc_corner_radius)} or larger: "
        f"a {_mm(2 * CASE.cnc_corner_radius)} mm end mill reaches them all. The USB opening's rounds are not "
        "vertical: see its detail.",
        f"45 degree chamfers: {_mm(CASE.underside_chamfer)} on the underside rim, "
        f"the flank and ends of the lap ridges, {_mm(CASE.usb_mouth_chamfer)} on the USB lead-in.",
        "The outer skin's top edge at the gap stays sharp, and so does the rim inside the gap: the top seats on it.",
        f"The rim steps in {_mm(CASE.gap_depth)} mm over the top {_mm(CASE.gap_height)} mm, all round: that is the gap. "
        "Cut it with the side of the end mill in setup 1.",
        f"Screw holes go straight through: M2 x {_mm(CASE.cnc_screw_length)} socket head from below.",
        CORNER_NOTE,
        "Laser mark on the underside: see LASER MARK and engraving_underside.dxf.",
    ),
    (
        *FINISH_NOTES,
        "TOLERANCES (after anodise)",
        "General: ISO 2768-m.",
        POSITION_NOTE,
        f"Lap ridges: height {_mm(CASE.lap_height)} and crest {_mm(CASE.lap_crest)}, \u00b1{_mm(LAP_TOLERANCE)} "
        "(detail).",
        f"USB opening: \u00b1{_mm(USB_TOLERANCE)} (detail).",
        "WORKHOLDING",
        "Setup 1: cut the light channels last, after the cavity is roughed: 3 mm 3-flute end mill, "
        "0.2 mm radial steps, full depth in two passes. Each channel leaves a free 1.0 mm skin.",
        "Setup 2 (underside up): sit the base on a plug fixture that fills the cavity, 0.1 mm smaller all "
        "round and 4 mm tall, so it backs up both skins. Hold it with an M2 screw through each of the six "
        "holes into the fixture, or in soft jaws cut to the outline below the gap. Never in a plain vise.",
        "LASER MARK",
        "Face: the underside, the flat floor face between the foot slots.",
        "Process: fibre laser, after anodise. Fill every closed contour on layer MARK of engraving_underside.dxf "
        "(hatch about 0.03 mm, a guess); do not mark layer REF. Colour: the light grey, frosted mark a fibre "
        "laser leaves on clear anodise. Mark one sample first.",
        "Position: the DXF is drawn as seen from below, not mirrored, with its origin at datum A. Seen from "
        "below with the USB edge away from you, datum A is the top-right corner of the outline box, so a point "
        "at (X, Y) in the table above is at (-X, -Y) in the DXF. Register on the REF outline and holes.",
    ),
)
TOP_SHEET = PartSheet(
    "top", "macropad case: top, CNC variant", "url(#hatch-back)", 1.5,
    (
        "3-axis, two setups: underside up, then top side up.",
        f"Every vertical pocket corner is R{_mm(CASE.cnc_corner_radius)} or larger; "
        "the switch cut-outs have corner reliefs of that radius. The USB opening's rounds are not vertical: "
        "see its detail.",
        f"Switch cut-outs {BOARD.stack.switch_cutout:.2f} +{_mm(CUTOUT_PLUS)}/0 square, measured after anodise, "
        f"in a {BOARD.stack.plate_thickness:.2f} \u00b1{_mm(PLATE_TOLERANCE)} mm plate.",
        f"Key dish: flat floor on the plate, walls at 45 degrees, {_mm(LEVELS.deck_top - LEVELS.plate_top)} deep. "
        "A 90 degree chamfer mill of 8 mm or more cuts the walls.",
        f"Screw holes S1-S6: {THREAD_CALLOUT}. For M2 x {_mm(CASE.cnc_screw_length)}.",
        "Setup 2 (top side up): hold the part on a fixture plate through the six M2 holes, or in soft jaws cut to "
        "the outline. The skirts are too thin for vise pressure.",
        CORNER_NOTE,
    ),
    (
        *FINISH_NOTES,
        "Mask the six tapped M2 holes before anodising, or chase them with an M2 6H tap after it.",
        "TOLERANCES (after anodise)",
        "General: ISO 2768-m.",
        f"Switch cut-outs {BOARD.stack.switch_cutout:.2f} +{_mm(CUTOUT_PLUS)}/0; plate "
        f"{BOARD.stack.plate_thickness:.2f} \u00b1{_mm(PLATE_TOLERANCE)}.",
        POSITION_NOTE,
        f"Lap grooves: depth {_mm(CASE.lap_height + CASE.lap_fit)} and land, \u00b1{_mm(LAP_TOLERANCE)} (detail).",
        f"Lens recess depth {_mm(CASE.lens_recess_depth)} \u00b1{_mm(LENS_DEPTH_TOLERANCE)}; USB opening "
        f"\u00b1{_mm(USB_TOLERANCE)} (detail).",
        "LENS OPENING",
        f"Cut it in setup 2, after the lens recess, with the same 3 mm end mill, down to Z "
        f"{_mm(LEVELS.lens_rib_bottom)} ({_mm(BOARD.stack.deck_top - LEVELS.lens_rib_bottom)} deep). The "
        "recess and the opening then share their long walls without a step between setups.",
    ),
)


def part_sheet(sheet: PartSheet, part: Part) -> str:
    """One manufacturing sheet: plan from above, plan from below, section B-B, lap detail, feature table."""
    above = (*CENTRE, FAR)
    below = (*CENTRE, -FAR)
    features = _base_features() if sheet.name == "base" else _top_features()
    dimensions = _base_dimensions() if sheet.name == "base" else _top_part_dimensions()
    body = [
        _sheet_frame(),
        _outline(part, above, (0, 1, 0), PLAN_ABOVE),
        _outline(part, below, (0, 1, 0), PLAN_BELOW),
        _cut_view({sheet.name: part}, PART_CUT),
        _lap_detail(sheet, part),
        _usb_detail(),
        _cut_line(PLAN_ABOVE, "B"),
        *dimensions, *_feature_tags(features), _feature_table(features), _title_block(sheet), *_part_labels(sheet),
    ]
    return _svg(body)


def _from_datum(x: float, y: float) -> tuple[float, float]:
    """Board position measured from the back-left corner of the box round the case's outline."""
    return x - LEFT, y - BACK


def _span_centre(span: Span) -> tuple[float, float]:
    (x_low, x_high), (y_low, y_high) = span
    return (x_low + x_high) / 2, (y_low + y_high) / 2


def _span_size(span: Span) -> str:
    (x_low, x_high), (y_low, y_high) = span
    return f"{_mm(x_high - x_low)} x {_mm(y_high - y_low)}"


def _base_features() -> list[tuple[str, tuple[float, float], str]]:
    """(tag, board position, what to make) for every hole and every recess in the underside of the base.
    A line break in the text starts a new line in the table."""
    seat = screw_seat(CNC) - LEVELS.floor_bottom
    screw_text = (
        f"\u2300{_mm(BOARD.mounting.hole_diameter)} through; counterbore \u2300{_mm(CASE.counterbore_diameter)} to "
        f"{_mm(seat)} from below; position \u00b1{_mm(POSITION_TOLERANCE)}"
    )
    screws = [(f"S{index + 1}", hole, screw_text) for index, hole in enumerate(mounting_holes())]
    button_text = f"\u2300{_mm(CASE.button_hole_diameter)} through"
    button_holes = [(name.upper()[:2], centre, f"{button_text} ({name.upper()})") for name, centre in buttons().items()]
    depth = f"{_mm(CASE.foot_recess_depth)} deep from below"
    recesses = [
        (f"R{index + 1}", _span_centre(foot_span(row)),
         f"slot {_span_size(grown(foot_span(row), CASE.foot_recess_fit))}, full-radius ends, {depth}")
        for index, row in enumerate(screw_rows())
    ]
    return screws + button_holes + recesses


def _top_features() -> list[tuple[str, tuple[float, float], str]]:
    drill, depth = CASE.cnc_tap_drill
    tapped = (
        f"M2x0.4-6H, {_mm(CASE.cnc_full_thread)} min full thread, from below; position \u00b1{_mm(POSITION_TOLERANCE)}\n"
        f"drill \u2300{_mm(drill)} x {_mm(depth)}, do not exceed {_mm(CASE.cnc_tap_drill_limit)} "
        f"(point to {_mm(depth + drill_point_height())})"
    )
    pilots = [(f"S{index + 1}", hole, tapped) for index, hole in enumerate(mounting_holes())]
    bushing = BOARD.stack.encoder_bushing_diameter + CASE.bushing_clearance
    through = (
        f"\u2300{_mm(bushing)} through; well \u2300{_mm(knob_well_diameter())} x "
        f"{_mm(CASE.knob_well_depth)} deep from above"
    )
    encoders = [(f"E{index + 1}", centre, through) for index, centre in enumerate(encoder_centres())]
    cutout = (
        f"{BOARD.stack.switch_cutout:.2f} +{_mm(CUTOUT_PLUS)}/0 square through (after anodise), first of "
        f"{len(key_centres())} on a {_mm(BOARD.keys.pitch)} grid"
    )
    lens_text = (
        f"lens recess {_span_size(lens_recess(CNC))}, R{_mm(CASE.lens_corner_radius + CASE.lens_fit)}, "
        f"{_mm(CASE.lens_recess_depth)} \u00b1{_mm(LENS_DEPTH_TOLERANCE)} deep from above\n"
        f"opening {_span_size(lens_opening(CNC))} through, in its middle"
    )
    return pilots + encoders + [("K1", key_centres()[0], cutout), ("LS", _span_centre(lens_recess(CNC)), lens_text)]


def _feature_tags(features: list[tuple[str, tuple[float, float], str]]) -> list[str]:
    tags = []
    for tag, centre, _ in features:
        x, y = PLAN_ABOVE.place(*_plan_point(*centre))
        tags.append(f'<text class="tag" x="{x + 2.2:.2f}" y="{y - 2.2:.2f}">{tag}</text>')
    return tags


def _feature_table(features: list[tuple[str, tuple[float, float], str]]) -> str:
    left, top = TABLE_AT
    lines = [f'<text class="title" x="{left}" y="{top}">Holes and recesses, from datum A</text>',
             f'<text class="note" x="{left}" y="{top + TABLE_LINE}">tag</text>'
             f'<text class="note" x="{left + 22}" y="{top + TABLE_LINE}" text-anchor="end">X</text>'
             f'<text class="note" x="{left + 40}" y="{top + TABLE_LINE}" text-anchor="end">Y</text>']
    line = top + 2 * TABLE_LINE
    previous = None
    for tag, centre, text in features:
        if text != previous:  # the description stands once, above each group of equal features
            for part in text.split("\n"):
                lines.append(f'<text class="small" x="{left}" y="{line:.1f}">{escape(part)}</text>')
                line += TABLE_LINE
            previous = text
        x, y = _from_datum(*centre)
        lines.append(f'<text class="note" x="{left}" y="{line:.1f}">{tag}</text>'
                     f'<text class="note" x="{left + 22}" y="{line:.1f}" text-anchor="end">{_mm(x, 3)}</text>'
                     f'<text class="note" x="{left + 40}" y="{line:.1f}" text-anchor="end">{_mm(y, 3)}</text>')
        line += TABLE_LINE
    assert line <= SIDE_NOTES_AT[1], "the feature table runs into the notes under it"
    return "".join(lines)


def _lap_detail(sheet: PartSheet, part: Part) -> str:
    """Section B-B again, eight times larger, where it crosses the gap and the lap joint in the front wall."""
    wall_middle = -(BOARD.board.height + CASE.pcb_gap + CASE.front_wall / 2)
    across, up = DETAIL_SIZE
    window = Pos(SECTION_X, wall_middle, sheet.detail_height) * Box(2.0, across, up)
    frame = Frame(
        DETAIL_AT[0] - DETAIL_SCALE * (wall_middle - CENTRE[1]), DETAIL_AT[1] + DETAIL_SCALE * sheet.detail_height,
        DETAIL_SCALE,
    )
    outer, inner = _side_point(FRONT_SIDE, 0)[0], _side_point(BOARD.board.height + CASE.pcb_gap, 0)[0]
    if sheet.name == "base":
        crest_outer = inner - CASE.lap_crest
        dimensions = [
            _dimension(frame, (inner, 0), (inner, CASE.lap_height), 3, _fit(CASE.lap_height)),
            _dimension(frame, (crest_outer, CASE.lap_height), (inner, CASE.lap_height), -6, _fit(CASE.lap_crest)),
            _dimension(frame, (outer, LEVELS.gap_bottom), (outer, 0), -5, f"{_mm(CASE.gap_height)} gap"),
            _dimension(frame, (outer, 0), (outer + CASE.gap_depth, 0), -6, _mm(CASE.gap_depth)),
            _dimension(frame, (outer, -4), (inner, -4), 6, _mm(CASE.front_wall, 3)),
        ]
    else:
        depth = CASE.lap_height + CASE.lap_fit
        land = CASE.front_wall - CASE.lap_crest - depth
        dimensions = [
            _dimension(frame, (inner, 0), (inner, depth), 3, _fit(depth)),
            _dimension(frame, (outer, 0), (outer + land, 0), 7, _fit(land)),
            _dimension(frame, (outer, LEVELS.plate_top), (inner, LEVELS.plate_top), -6, _mm(CASE.front_wall, 3)),
        ]
    return _cut_view({sheet.name: part & window}, frame) + "".join(dimensions)


def _fit(value: float) -> str:
    """A lap-joint dimension with its tolerance."""
    return f"{_mm(value, 3)} \u00b1{_mm(LAP_TOLERANCE)}"


def _usb_detail() -> str:
    """The USB opening seen from behind, with its lead-in and the seam where base and top meet. Its
    rounds have their axes along Y, so the note names the cutter they need."""
    width, height = usb_opening_size()
    lower, upper = usb_corner_radii()
    flare = CASE.usb_mouth_chamfer
    profile = usb_opening_profile()
    outlines = [_sketch_path(profile, USB_DETAIL), _sketch_path(offset_sketch(profile, flare), USB_DETAIL)]
    seam = -LEVELS.usb_centre  # Z 0 in the profile's frame
    left, right = -width / 2 - flare - 2.0, width / 2 + flare + 2.0
    (seam_left, seam_y), (seam_right, _) = USB_DETAIL.place(left, seam), USB_DETAIL.place(right, seam)
    tolerance = f" \u00b1{_mm(USB_TOLERANCE)}"
    note = (
        f"Seen from behind. Rounds along Y: R{_mm(lower)} lower (base), R{_mm(upper)} upper (top). Ball-nose or "
        f"bull-nose cutter of that radius or smaller, 3D finish; the {_mm(2 * CASE.cnc_corner_radius)} mm flat end "
        f"mill cannot cut them. {_mm(flare)} x 45 degree lead-in on the outer face."
    )
    note_x, note_y = USB_NOTES_AT
    lines = [f'<text class="title" x="{note_x}" y="{note_y}">USB OPENING, {USB_DETAIL.scale:g}:1</text>']
    lines += [f'<text class="small" x="{note_x}" y="{note_y + NOTE_LINE * (index + 1.5):.1f}">{escape(line)}</text>'
              for index, line in enumerate(textwrap.wrap(note, USB_NOTE_WIDTH))]
    return "".join([
        f'<path class="cut" fill="none" d="{" ".join(outlines)}"/>',
        f'<path class="centre" d="M{seam_left:.2f},{seam_y:.2f} H{seam_right:.2f}"/>',
        _detail_label((left - 0.5, seam - 0.3), "Z 0: top above, base below", "end"),
        _dimension(USB_DETAIL, (-width / 2, -height / 2), (width / 2, -height / 2), 6, _mm(width) + tolerance),
        _dimension(USB_DETAIL, (-width / 2, -height / 2), (-width / 2, height / 2), -8, _mm(height) + tolerance,
                   along=True),
        _detail_label((-width / 2 - 0.6, -height / 2 - 1.0), f"R{_mm(lower)}", "end"),
        _detail_label((width / 2 + 0.6, height / 2 + 0.6), f"R{_mm(upper)}", "start"),
        *lines,
    ])


def _detail_label(at: tuple[float, float], text: str, anchor: str) -> str:
    x, y = USB_DETAIL.place(*at)
    return f'<text class="small" x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}">{escape(text)}</text>'


def _sketch_path(sketch: Sketch, frame: Frame) -> str:
    """Every loop of a flat sketch, seen as it lies (X across, Y up), as closed SVG paths."""
    paths = []
    for face in sketch.faces():
        for loop in [face.outer_wire(), *face.inner_wires()]:
            points = [point for edge in loop.order_edges() for point in _points_along(edge)]
            paths.append(_polyline([frame.place(x, y) for x, y in points]) + " Z")
    return " ".join(paths)


def _title_block(sheet: PartSheet) -> str:
    """Part number, revision, quantity, material, finish and the general tolerance, boxed."""
    left, top = TITLE_BLOCK_AT
    width, row = TITLE_BLOCK_SIZE
    rows = [
        ("PART", sheet.title),
        ("PART NO.", f"{CNC_PART_NUMBERS[sheet.name]}    REV {REVISION}"),
        ("QUANTITY", "1 per macropad (order quantity on the purchase order)"),
        ("MATERIAL", "6061-T6 aluminium"),
        ("FINISH", FINISH),
        ("UNITS", "mm; plans seen from above and from below, as titled"),
        ("TOLERANCE", "ISO 2768-m unless stated; fits as listed below"),
        ("STATUS", "Not made or measured yet: check the first part"),
    ]
    lines = [f'<rect class="block" x="{left}" y="{top}" width="{width}" height="{row * len(rows):.1f}"/>']
    for index, (field, value) in enumerate(rows):
        baseline = top + row * (index + 0.75)
        lines.append(f'<text class="small" x="{left + 1.2}" y="{baseline:.1f}">{field}</text>'
                     f'<text class="small" x="{left + 19}" y="{baseline:.1f}">{escape(value)}</text>')
        if index:
            lines.append(f'<path class="witness" d="M{left},{top + row * index:.1f} H{left + width}"/>')
    return "".join(lines)


def _base_dimensions() -> list[str]:
    slot_start, slot_end = led_slot_span()
    usb_half = CASE.usb_plug[0] / 2 + CASE.usb_margin
    return [
        _dimension(PLAN_ABOVE, _plan_point(LEFT, BACK), _plan_point(RIGHT_SIDE, BACK), -17, _mm(RIGHT_SIDE - LEFT)),
        _dimension(PLAN_ABOVE, _plan_point(RIGHT_SIDE, BACK), _plan_point(RIGHT_SIDE, FRONT_SIDE), 9,
                   _mm(FRONT_SIDE - BACK), along=True),
        _dimension(PLAN_ABOVE, _plan_point(BOARD.usb.x - usb_half, BACK), _plan_point(BOARD.usb.x + usb_half, BACK), -8,
                   f"{_mm(2 * usb_half)} USB"),
        _dimension(PLAN_ABOVE, _plan_point(LEFT, BACK), _plan_point(LEFT, slot_start), -7,
                   _mm(slot_start - BACK, 3), along=True),
        _dimension(PLAN_ABOVE, _plan_point(LEFT, slot_start), _plan_point(LEFT, slot_end), -7,
                   f"{_mm(slot_end - slot_start)} light channel", along=True),
        *_section_heights([
            (LEVELS.floor_bottom, LEVELS.floor_top, f"{_mm(CASE.floor)} floor"),
            (LEVELS.floor_top, LEVELS.pcb_bottom, f"{_mm(BOARD.stack.underside_clearance)} cavity"),
            (LEVELS.pcb_bottom, 0, f"{_mm(BOARD.board.thickness)} PCB"),
        ]),
    ]


def _top_part_dimensions() -> list[str]:
    keys = key_centres()
    (recess_start, recess_end), (recess_back, recess_front) = lens_recess(CNC)
    (_, _), (rim_back, rim_front) = dish_rim()
    return [
        _dimension(PLAN_ABOVE, _plan_point(LEFT, BACK), _plan_point(RIGHT_SIDE, BACK), -17, _mm(RIGHT_SIDE - LEFT)),
        _dimension(PLAN_ABOVE, _plan_point(RIGHT_SIDE, BACK), _plan_point(RIGHT_SIDE, FRONT_SIDE), 9,
                   _mm(FRONT_SIDE - BACK), along=True),
        _dimension(PLAN_ABOVE, _plan_point(LEFT, BACK), _plan_point(LEFT, rim_back), -7,
                   f"{_mm(rim_back - BACK, 3)} to the dish", along=True),
        _dimension(PLAN_ABOVE, _plan_point(LEFT, rim_front), _plan_point(LEFT, FRONT_SIDE), -7,
                   f"{_mm(FRONT_SIDE - rim_front, 3)} frame", along=True),
        _dimension(PLAN_ABOVE, _plan_point(recess_start, recess_back), _plan_point(recess_end, recess_back), -4,
                   _mm(recess_end - recess_start)),
        _dimension(PLAN_ABOVE, _plan_point(recess_end, recess_back), _plan_point(recess_end, recess_front), 4,
                   _mm(recess_front - recess_back)),
        _dimension(PLAN_ABOVE, _plan_point(*keys[-2]), _plan_point(*keys[-1]),
                   PLAN_ABOVE.scale * (FRONT_SIDE - keys[-1][1]) + 6, _mm(BOARD.keys.pitch)),
        *_section_heights([
            (0, LEVELS.plate_bottom, f"{_mm(LEVELS.plate_bottom)} skirt"),
            (LEVELS.plate_bottom, LEVELS.plate_top,
             f"{BOARD.stack.plate_thickness:.2f} \u00b1{_mm(PLATE_TOLERANCE)} plate"),
            (LEVELS.plate_top, LEVELS.deck_top, f"{_mm(LEVELS.deck_top - LEVELS.plate_top)} dish"),
        ]),
    ]


def _section_heights(levels: list[tuple[float, float, str]]) -> list[str]:
    """A chain of height dimensions at the front end of section B-B."""
    front = _side_point(FRONT_SIDE, 0)[0]
    return [_dimension(PART_CUT, (front, low), (front, high), -8, text) for low, high, text in levels]


def _part_labels(sheet: PartSheet) -> list[str]:
    def title(frame: Frame, across: float, up: float, text: str) -> str:
        x, y = frame.place(across, up)
        return f'<text class="title" x="{x:.2f}" y="{y:.2f}">{escape(text)}</text>'

    plan_left, plan_back = _plan_point(LEFT, BACK)
    datum_x, datum_y = PLAN_ABOVE.place(plan_left, plan_back)
    datum = (f'<circle class="datum" cx="{datum_x:.2f}" cy="{datum_y:.2f}" r="1.6"/>'
             f'<text class="title" x="{datum_x - 7:.2f}" y="{datum_y - 2:.2f}">A</text>')
    notes = (
        f"Scale {PLAN_ABOVE.scale:g}:1 plans, {PART_CUT.scale:g}:1 section, {DETAIL_SCALE:g}:1 detail, on A3. "
        "Dimensions in mm, computed from the model.",
        "Datum A: back-left corner of the box round the outline, seen from above. "
        "X to the right, Y toward the front.",
        *sheet.notes,
    )
    block = "".join(
        f'<text class="small" x="20" y="{NOTES_AT + NOTE_LINE * index:.1f}">{escape(note)}</text>'
        for index, note in enumerate(notes)
    )
    side_x, side_y = SIDE_NOTES_AT
    side_lines = [line for note in sheet.side_notes for line in textwrap.wrap(note, SIDE_NOTE_WIDTH)]
    assert side_y + NOTE_LINE * (len(side_lines) - 1) <= LAST_LINE, f"{sheet.name}: side notes run off the sheet"
    assert NOTES_AT + NOTE_LINE * (len(notes) - 1) <= LAST_LINE, f"{sheet.name}: notes run off the sheet"
    side_block = "".join(
        f'<text class="small" x="{side_x}" y="{side_y + NOTE_LINE * index:.1f}">{escape(line)}</text>'
        for index, line in enumerate(side_lines)
    )
    detail_x, detail_y = DETAIL_AT
    return [
        title(PLAN_ABOVE, plan_left, plan_back + 15, "FROM ABOVE"),
        title(PLAN_BELOW, plan_left, plan_back + 15, "FROM BELOW (mirrored left to right)"),
        title(PART_CUT, _side_point(FRONT_SIDE, 0)[0], 14, "SECTION B-B"),
        f'<text class="title" x="{detail_x - 34:.1f}" y="{detail_y - 44:.1f}">'
        f"GAP AND LAP JOINT, {DETAIL_SCALE:g}:1</text>",
        datum, block, side_block,
    ]


def _sheet_frame() -> str:
    width, height = SHEET
    return f'<rect class="sheet" x="5" y="5" width="{width - 10}" height="{height - 10}"/>'


def _svg(body: list[str]) -> str:
    width, height = SHEET
    style = f"""
      text {{ font-family: {FONT}; font-size: 3.2px; fill: #1b1f24; }}
      .title {{ font-size: 4.4px; font-weight: bold; }}
      .note {{ font-size: 3.2px; }}
      .small {{ font-size: 2.7px; }}
      .tag {{ font-size: 3px; font-weight: bold; fill: #b5651d; }}
      .datum {{ fill: none; stroke: #b5651d; stroke-width: 0.4; }}
      .block {{ fill: none; stroke: #1b1f24; stroke-width: 0.3; }}
      .sheet {{ fill: #ffffff; stroke: #1b1f24; stroke-width: 0.5; }}
      .visible {{ fill: none; stroke: #1b1f24; stroke-width: 0.3; stroke-linecap: round; stroke-linejoin: round; }}
      .cut {{ stroke: #1b1f24; stroke-width: 0.3; stroke-linejoin: round; }}
      .witness {{ fill: none; stroke: #2a6f97; stroke-width: 0.13; }}
      .dimension {{ fill: none; stroke: #2a6f97; stroke-width: 0.2; marker-start: url(#arrow); marker-end: url(#arrow); }}
      .centre {{ fill: none; stroke: #b5651d; stroke-width: 0.25; stroke-dasharray: 6 1.5 1 1.5; }}
    """
    definitions = """
      <marker id="arrow" viewBox="0 0 6 4" refX="6" refY="2" markerWidth="6" markerHeight="4" orient="auto-start-reverse">
        <path d="M0,0 L6,2 L0,4 Z" fill="#2a6f97"/>
      </marker>
      <pattern id="hatch" width="1.6" height="1.6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="1.6" height="1.6" fill="#e6e8ec"/><line x1="0" y1="0" x2="0" y2="1.6" stroke="#4a5160" stroke-width="0.25"/>
      </pattern>
      <pattern id="hatch-back" width="1.6" height="1.6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
        <rect width="1.6" height="1.6" fill="#eef0f3"/><line x1="0" y1="0" x2="0" y2="1.6" stroke="#4a5160" stroke-width="0.25"/>
      </pattern>
    """
    lines = "\n".join(body)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}">\n'
            f"<style>{style}</style>\n<defs>{definitions}</defs>\n{lines}\n</svg>\n")
