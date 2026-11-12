"""Builds the unrouted KiCad board from circuit.py. Runs inside the KiCad container (needs pcbnew)."""

from __future__ import annotations

import math
from pathlib import Path

import pcbnew

import circuit
from circuit import BOARD_SPEC, BOTTOM, GND, NO_NET, V3, V5, Part

STOCK_FOOTPRINTS = Path("/usr/share/kicad/footprints")
PROJECT_FOOTPRINTS = circuit.REPO_ROOT / "pcb" / "lib"
POSITION_TOLERANCE = 0.02
# Passives are too dense for readable silkscreen; only connectors and controls keep their reference.
SILK_LABELLED = {"USBC", "SOCKET5", "EC11", "TACT", "MX_HOTSWAP", "QFN60"}

# JLCPCB 4-layer capability with margin: 0.09 mm track/space and 0.3 mm drill are their limits.
TRACK_WIDTH = 0.15
CLEARANCE = 0.15
VIA_DIAMETER = 0.6
VIA_DRILL = 0.3
EDGE_CLEARANCE = 0.3
# The 3.3 V island on the power layer: under the MCU and the display header.
V3_ISLAND = (23.0, 8.5, 61.0, 26.5)


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def pad_xy(pad: pcbnew.PAD) -> tuple[float, float]:
    position = pad.GetPosition()
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def _load_footprint(name: str) -> pcbnew.FOOTPRINT:
    library, footprint_name = name.split(":")
    root = PROJECT_FOOTPRINTS if library == "macropad" else STOCK_FOOTPRINTS
    footprint = pcbnew.FootprintLoad(str(root / f"{library}.pretty"), footprint_name)
    assert footprint is not None, f"footprint not found: {name}"
    return footprint


def _net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    existing = board.FindNet(name)
    if existing is not None:
        return existing
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def _place(board: pcbnew.BOARD, part: Part) -> pcbnew.FOOTPRINT:
    footprint = _load_footprint(part.footprint)
    board.Add(footprint)  # pcbnew crashes when it flips a footprint that has no board
    footprint.SetReference(part.ref)
    footprint.SetValue(part.value)
    footprint.SetPosition(point(part.x, part.y))
    if part.side == BOTTOM:
        # A top-bottom flip mirrors Y; the extra half turn makes it the X mirror you see from the top.
        footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        footprint.SetOrientationDegrees(part.rotation + 180)
    else:
        footprint.SetOrientationDegrees(part.rotation)
    if part.lcsc:
        footprint.SetField("LCSC", part.lcsc)
        footprint.GetFieldByName("LCSC").SetVisible(False)
    footprint.Value().SetVisible(False)
    footprint.Reference().SetVisible(part.footprint_key in SILK_LABELLED)
    if not part.machine_assembled:
        footprint.SetExcludedFromPosFiles(True)
    _connect(board, footprint, part)
    return footprint


def _connect(board: pcbnew.BOARD, footprint: pcbnew.FOOTPRINT, part: Part) -> None:
    pad_numbers = {pad.GetNumber() for pad in footprint.Pads()}
    unknown = set(part.nets) - pad_numbers
    assert not unknown, f"{part.ref}: no such pads {sorted(unknown)}"
    for pad in footprint.Pads():
        net_name = part.nets.get(pad.GetNumber(), NO_NET)
        if net_name != NO_NET:
            pad.SetNet(_net(board, net_name))


def _outline(board: pcbnew.BOARD) -> None:
    spec = BOARD_SPEC["board"]
    width, height, radius = spec["width"], spec["height"], spec["corner_radius"]
    corners = [(radius, radius, 180), (width - radius, radius, 270),
               (width - radius, height - radius, 0), (radius, height - radius, 90)]
    arc_ends = []
    for centre_x, centre_y, start_angle in corners:
        start, mid, end = (
            (centre_x + radius * math.cos(math.radians(a)), centre_y + radius * math.sin(math.radians(a)))
            for a in (start_angle, start_angle + 45, start_angle + 90)
        )
        arc = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        arc.SetArcGeometry(point(*start), point(*mid), point(*end))
        _add_edge(board, arc)
        arc_ends.append((start, end))
    for (_, line_start), (line_end, _) in zip(arc_ends, arc_ends[1:] + arc_ends[:1]):
        line = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(point(*line_start))
        line.SetEnd(point(*line_end))
        _add_edge(board, line)


def _add_edge(board: pcbnew.BOARD, shape: pcbnew.PCB_SHAPE) -> None:
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetWidth(mm(0.1))
    board.Add(shape)


def _zone(board: pcbnew.BOARD, net_name: str, layer: int, rectangle: tuple, priority: int = 0) -> None:
    left, top, right, bottom = rectangle
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(_net(board, net_name))
    zone.SetAssignedPriority(priority)
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetMinThickness(mm(0.2))
    zone.SetLocalClearance(mm(0.2))
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
        outline.Append(mm(x), mm(y))
    board.Add(zone)


def add_inner_planes(board: pcbnew.BOARD) -> None:
    whole_board = (0.0, 0.0, BOARD_SPEC["board"]["width"], BOARD_SPEC["board"]["height"])
    _zone(board, GND, pcbnew.In1_Cu, whole_board)
    _zone(board, V5, pcbnew.In2_Cu, whole_board)
    _zone(board, V3, pcbnew.In2_Cu, V3_ISLAND, priority=1)


def add_outer_ground_pours(board: pcbnew.BOARD) -> None:
    whole_board = (0.0, 0.0, BOARD_SPEC["board"]["width"], BOARD_SPEC["board"]["height"])
    _zone(board, GND, pcbnew.F_Cu, whole_board)
    _zone(board, GND, pcbnew.B_Cu, whole_board)


def _silk_text(board: pcbnew.BOARD, text: str, x: float, y: float, layer: int, size: float = 1.0) -> None:
    label = pcbnew.PCB_TEXT(board)
    label.SetText(text)
    label.SetPosition(point(x, y))
    label.SetLayer(layer)
    label.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    label.SetTextThickness(mm(size * 0.15))
    label.SetMirrored(layer == pcbnew.B_SilkS)
    board.Add(label)


def _labels(board: pcbnew.BOARD) -> None:
    buttons = BOARD_SPEC["buttons"]
    _silk_text(board, "BOOT", buttons["boot"]["x"], buttons["boot"]["y"] - 3.6, pcbnew.B_SilkS, 0.8)
    _silk_text(board, "RESET", buttons["reset"]["x"], buttons["reset"]["y"] - 3.6, pcbnew.B_SilkS, 0.8)
    _silk_text(board, "macropad rev A", 42.0, 46.0, pcbnew.B_SilkS)
    _silk_text(board, "JLCJLCJLCJLC", 42.0, 48.0, pcbnew.B_SilkS, 0.8)
    display = BOARD_SPEC["display"]
    _silk_text(board, "nice!view", display["x"] + 4, display["y"], pcbnew.F_SilkS)


def _rules(board: pcbnew.BOARD) -> None:
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = mm(0.127)
    settings.m_MinClearance = mm(0.127)
    settings.m_ViasMinSize = mm(0.45)
    settings.m_MinThroughDrill = mm(0.3)
    settings.m_CopperEdgeClearance = mm(EDGE_CLEARANCE)
    settings.m_HoleClearance = mm(0.2)
    default_class = settings.m_NetSettings.GetDefaultNetclass()
    default_class.SetTrackWidth(mm(TRACK_WIDTH))
    default_class.SetClearance(mm(CLEARANCE))
    default_class.SetViaDiameter(mm(VIA_DIAMETER))
    default_class.SetViaDrill(mm(VIA_DRILL))


# --- placement self-checks: flipping and rotating are easy to get backwards -------------------

def _close(actual: tuple[float, float], expected: tuple[float, float]) -> bool:
    return math.dist(actual, expected) < POSITION_TOLERANCE


def _pads(footprint: pcbnew.FOOTPRINT, number: str) -> list[tuple[float, float]]:
    return [pad_xy(pad) for pad in footprint.Pads() if pad.GetNumber() == number]


def check_placement(placed: dict[str, pcbnew.FOOTPRINT]) -> None:
    mcu = placed["U1"]
    for pin in (1, 15, 16, 31, 46, 60):
        assert _close(_pads(mcu, str(pin))[0], circuit.mcu_pin_xy(pin)), f"MCU pin {pin} is not where circuit.py says"

    key_x, key_y = circuit.key_centre(0)
    assert _close(_pads(placed["SW1"], "1")[0], (key_x - 7.085, key_y - 2.54)), "hot-swap socket is mirrored"

    usb_pad_y = _pads(placed["J1"], "A6")[0][1]
    assert usb_pad_y > placed["J1"].GetPosition().y / 1e6, "USB-C receptacle faces into the board"

    width = BOARD_SPEC["board"]["width"]
    for ref, footprint in placed.items():
        if ref.startswith("LED"):
            body_x = pcbnew.ToMM(footprint.GetPosition().x)
            pad_x = _pads(footprint, "2")[0][0]
            # The pads are at the back of a side-emitter, so they must sit inboard of the body.
            assert abs(pad_x - width / 2) < abs(body_x - width / 2), f"{ref} shines into the board"

    for number, pin in enumerate(circuit.DECOUPLED_PINS, start=1):
        cap = placed[f"C{number}"]
        pin_xy = circuit.mcu_pin_xy(pin)
        near, far = _pads(cap, "1")[0], _pads(cap, "2")[0]
        assert math.dist(near, pin_xy) < math.dist(far, pin_xy), f"C{number} is reversed"


def build_board(board_path: Path) -> pcbnew.BOARD:
    parts = circuit.all_parts()
    circuit.check_netlist(parts)
    board = pcbnew.NewBoard(str(board_path))
    board.SetCopperLayerCount(4)
    _rules(board)
    _outline(board)
    placed = {part.ref: _place(board, part) for part in parts}
    check_placement(placed)
    _labels(board)
    add_inner_planes(board)
    return board
