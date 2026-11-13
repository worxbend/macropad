"""A dimensioned general-arrangement drawing as SVG: top, front and right views with hidden lines
removed, and a section through the USB port and the display. Two more sheets are for the machine
shop. Every dimension text is computed from the model, never typed in."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from build123d import Box, Compound, ExportDXF, GeomType, Part, Plane, Pos, Unit, section

from .components import drawn_components
from .parts import drill_point_height, underside_artwork
from .small_parts import case_parts, lens_mask_outline, lens_outline
from .spec import BOARD, CASE, CNC, LEVELS, PRINT, Span, buttons, case_bounds, dish_rim, encoder_centres, foot_span
from .spec import grown, key_centres, knob_well_diameter, led_slot_span, lens_opening, lens_recess, lens_span
from .spec import mounting_holes, screw_rows, screw_seat

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
TABLE_AT = (312.0, 30.0)
TABLE_LINE = 5.2
NOTES_AT = 255.0  # sheet Y of the first line of notes on a part sheet
NOTE_LINE = 4.1
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
    outlines = {"engraving_underside": underside_artwork(), "lens": lens_outline(), "lens_mask": lens_mask_outline()}
    for name, artwork in outlines.items():
        exporter = ExportDXF(unit=Unit.MM)
        exporter.add_shape(artwork)
        exporter.write(str(folder / f"{name}.dxf"))
        print(f"drew {folder / f'{name}.dxf'}")


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
    return (f'<path class="centre" d="M{x:.2f},{top:.2f} V{bottom:.2f}"/>'
            f'<text class="title" x="{x + 2:.2f}" y="{top + 5:.2f}">{letter}</text>'
            f'<text class="title" x="{x + 2:.2f}" y="{bottom - 1.5:.2f}">{letter}</text>')


@dataclass(frozen=True)
class PartSheet:
    name: str  # which case part
    title: str
    fill: str
    detail_height: float  # model Z at the middle of the lap detail
    notes: tuple[str, ...]


CORNER_NOTE = (
    f"Outline corners: one quintic Bezier each, control points {_mm(CASE.corner_setback)}, "
    f"{_mm(CASE.corner_setback * CASE.corner_handles[0])} and {_mm(CASE.corner_setback * CASE.corner_handles[1])} mm "
    "from the box corner on both sides. Take the curve from the STEP file."
)
BASE_SHEET = PartSheet(
    "base", "macropad case: base, CNC variant", "url(#hatch)", -1.5,
    (
        "3-axis, two setups: inside up, then underside up.",
        f"Every pocket corner is R{_mm(CASE.cnc_corner_radius)} or larger: "
        f"a {_mm(2 * CASE.cnc_corner_radius)} mm end mill reaches them all.",
        f"45 degree chamfers: {_mm(CASE.underside_chamfer)} on the underside rim, "
        f"{_mm(CASE.seam_chamfer)} on the outer skin's top edge at the gap, "
        "the flank and ends of the lap ridges, the USB lead-in. The rim inside the gap stays sharp: the top seats on it.",
        f"The rim steps in {_mm(CASE.gap_depth)} mm over the top {_mm(CASE.gap_height)} mm, all round: that is the gap. "
        "Cut it with the side of the end mill in setup 1.",
        f"Screw holes go straight through: M2 x {_mm(CASE.cnc_screw_length)} socket head from below.",
        CORNER_NOTE,
        "General tolerance: ISO 2768-m is a proposal. Nothing has been made or measured.",
    ),
)
TOP_SHEET = PartSheet(
    "top", "macropad case: top, CNC variant", "url(#hatch-back)", 1.5,
    (
        "3-axis, two setups: underside up, then top side up.",
        f"Every pocket corner is R{_mm(CASE.cnc_corner_radius)} or larger; "
        "the switch cut-outs have corner reliefs of that radius.",
        f"Switch cut-outs {_mm(BOARD.stack.switch_cutout)} square in a {_mm(BOARD.stack.plate_thickness)} mm plate. "
        "Take their tolerance from the Cherry MX datasheet.",
        f"Key dish: flat floor on the plate, walls at 45 degrees, {_mm(LEVELS.deck_top - LEVELS.plate_top)} deep. "
        "A 90 degree chamfer mill of 8 mm or more cuts the walls.",
        f"Screw holes: drill {_mm(CASE.cnc_tap_drill[0])} to {_mm(CASE.cnc_tap_drill[1])} at full diameter, "
        f"tap M2 with a bottoming tap to {_mm(CASE.cnc_full_thread)} full thread or more, "
        f"for M2 x {_mm(CASE.cnc_screw_length)}.",
        "Setup 2 (top side up): hold the part on a fixture plate through the six M2 holes, or in soft jaws cut to "
        "the outline. The skirts are too thin for vise pressure.",
        CORNER_NOTE,
        "General tolerance: ISO 2768-m is a proposal. Nothing has been made or measured.",
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
        _cut_line(PLAN_ABOVE, "B"),
        *dimensions, *_feature_tags(features), _feature_table(features), *_part_labels(sheet),
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
        f"{_mm(seat)} from below"
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
        f"\u2300{_mm(drill)} x {_mm(depth)} from below (point to {_mm(depth + drill_point_height())}), "
        f"tap M2 to {_mm(CASE.cnc_full_thread)} full thread"
    )
    pilots = [(f"S{index + 1}", hole, tapped) for index, hole in enumerate(mounting_holes())]
    bushing = BOARD.stack.encoder_bushing_diameter + CASE.bushing_clearance
    through = (
        f"\u2300{_mm(bushing)} through; well \u2300{_mm(knob_well_diameter())} x "
        f"{_mm(CASE.knob_well_depth)} deep from above"
    )
    encoders = [(f"E{index + 1}", centre, through) for index, centre in enumerate(encoder_centres())]
    cutout = (
        f"{_mm(BOARD.stack.switch_cutout)} square through, first of {len(key_centres())} "
        f"on a {_mm(BOARD.keys.pitch)} grid"
    )
    lens_text = (
        f"lens recess {_span_size(lens_recess(CNC))}, R{_mm(CASE.lens_corner_radius + CASE.lens_fit)}, "
        f"{_mm(CASE.lens_recess_depth)} deep from above\nopening {_span_size(lens_opening(CNC))} through, in its middle"
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
            _dimension(frame, (inner, 0), (inner, CASE.lap_height), 9, _mm(CASE.lap_height)),
            _dimension(frame, (crest_outer, CASE.lap_height), (inner, CASE.lap_height), -6, _mm(CASE.lap_crest)),
            _dimension(frame, (outer, LEVELS.gap_bottom), (outer, 0), -5, f"{_mm(CASE.gap_height)} gap"),
            _dimension(frame, (outer, 0), (outer + CASE.gap_depth, 0), -6, _mm(CASE.gap_depth)),
            _dimension(frame, (outer, -4), (inner, -4), 6, _mm(CASE.front_wall, 3)),
        ]
    else:
        depth = CASE.lap_height + CASE.lap_fit
        land = CASE.front_wall - CASE.lap_crest - depth
        dimensions = [
            _dimension(frame, (inner, 0), (inner, depth), 9, _mm(depth)),
            _dimension(frame, (outer, 0), (outer + land, 0), 7, _mm(land, 3)),
            _dimension(frame, (outer, LEVELS.plate_top), (inner, LEVELS.plate_top), -6, _mm(CASE.front_wall, 3)),
        ]
    return _cut_view({sheet.name: part & window}, frame) + "".join(dimensions)


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
            (LEVELS.plate_bottom, LEVELS.plate_top, f"{_mm(BOARD.stack.plate_thickness)} plate"),
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
    detail_x, detail_y = DETAIL_AT
    return [
        f'<text class="title" x="{TABLE_AT[0]}" y="16">{escape(sheet.title)}</text>',
        title(PLAN_ABOVE, plan_left, plan_back + 15, "FROM ABOVE"),
        title(PLAN_BELOW, plan_left, plan_back + 15, "FROM BELOW (mirrored left to right)"),
        title(PART_CUT, _side_point(FRONT_SIDE, 0)[0], 14, "SECTION B-B"),
        f'<text class="title" x="{detail_x - 34:.1f}" y="{detail_y - 44:.1f}">'
        f"GAP AND LAP JOINT, front wall, {DETAIL_SCALE:g}:1</text>",
        datum, block,
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
