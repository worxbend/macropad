"""Builds the unrouted KiCad board from circuit.py. Runs inside the KiCad container (needs pcbnew)."""

from __future__ import annotations

import math
from pathlib import Path

import pcbnew

import circuit
import models
import route
import schematic
import silk
from circuit import BOARD_SPEC, BOTTOM, GND, NO_NET, V1, V3, V5, Part
from router import Rules

STOCK_FOOTPRINTS = Path("/usr/share/kicad/footprints")
PROJECT_FOOTPRINTS = circuit.REPO_ROOT / "pcb" / "lib"
POSITION_TOLERANCE = 0.02
# Passives are too dense for readable silkscreen. Connectors, chips and the other one-of-a-kind parts
# keep their reference; the two buttons are named BOOT and RESET instead (see silk.py).
SILK_LABELLED = {"USBC", "SOCKET5", "EC11", "MX_HOTSWAP", "QFN60", "SOT23-5", "SOT23-6", "F1206"}

# JLCPCB 4-layer capability with margin: 0.09 mm track/space and 0.3 mm drill are their limits.
TRACK_WIDTH = 0.15
CLEARANCE = 0.15
VIA_DIAMETER = 0.6
VIA_DRILL = 0.3
EDGE_CLEARANCE = 0.3
SILK_EDGE_CLEARANCE = 0.2
# The 3.3 V island on the power layer: under the MCU and the display header, with a tongue up to
# the USB connector so the USB pair runs over one unbroken plane.
V3_ISLAND = [(23.0, 8.5, 61.0, 26.5), (37.0, 0.0, 47.5, 9.0)]
# The 1.1 V core island, cut out of the 3.3 V island: a square under the chip, with a lobe out to
# the supply via of each DVDD pin that has its capacitor straight in front of it (pins 6 and 23).
V1_ISLAND = [(38.6, 14.1, 45.4, 20.9), (45.0, 15.9, 47.1, 17.5), (41.2, 20.5, 42.8, 22.6)]
ROUTING_RULES = Rules(track_width=TRACK_WIDTH, clearance=CLEARANCE, via_diameter=VIA_DIAMETER,
                      via_drill=VIA_DRILL, edge_clearance=EDGE_CLEARANCE)


def routing_setup(head_start: tuple[str, ...]) -> route.Setup:
    return route.Setup(ROUTING_RULES, V3_ISLAND, V1_ISLAND, head_start)


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
    footprint.SetFPID(pcbnew.LIB_ID(library, footprint_name))  # with its library, as the schematic names it
    return footprint


def _net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    return _board_net(board, schematic.board_net_name(name))


def _board_net(board: pcbnew.BOARD, board_name: str) -> pcbnew.NETINFO_ITEM:
    existing = board.FindNet(board_name)
    if existing is not None:
        return existing
    net = pcbnew.NETINFO_ITEM(board, board_name)
    board.Add(net)
    return net


def _place(board: pcbnew.BOARD, part: Part, open_pin_nets: dict[str, str]) -> pcbnew.FOOTPRINT:
    footprint = _load_footprint(part.footprint)
    models.attach(part.footprint_key, footprint)
    board.Add(footprint)  # pcbnew crashes when it flips a footprint that has no board
    footprint.SetReference(part.ref)
    footprint.SetPath(pcbnew.KIID_PATH(f"/{schematic.symbol_uuid(part.ref)}"))  # pairs it with its schematic symbol
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
    _remove_silkscreen_off_the_board(footprint)
    footprint.Reference().SetVisible(part.footprint_key in SILK_LABELLED)
    if not part.machine_assembled:
        footprint.SetExcludedFromPosFiles(True)
    _connect(board, footprint, part, open_pin_nets)
    return footprint


def _remove_silkscreen_off_the_board(footprint: pcbnew.FOOTPRINT) -> None:
    """The USB receptacle hangs over the edge and its outline with it; the fab house would clip those lines."""
    spec = BOARD_SPEC["board"]
    for item in list(footprint.GraphicalItems()):
        if item.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        box = item.GetBoundingBox()
        inside = (box.GetLeft() >= mm(SILK_EDGE_CLEARANCE) and box.GetTop() >= mm(SILK_EDGE_CLEARANCE)
                  and box.GetRight() <= mm(spec["width"] - SILK_EDGE_CLEARANCE)
                  and box.GetBottom() <= mm(spec["height"] - SILK_EDGE_CLEARANCE))
        if not inside:
            footprint.Remove(item)


def _connect(board: pcbnew.BOARD, footprint: pcbnew.FOOTPRINT, part: Part, open_pin_nets: dict[str, str]) -> None:
    """Nets from circuit.py. An open pin gets the one-pad net KiCad's netlist names for it, so the board
    carries exactly the nets of the schematic."""
    pad_numbers = {pad.GetNumber() for pad in footprint.Pads()}
    unknown = set(part.nets) - pad_numbers
    assert not unknown, f"{part.ref}: no such pads {sorted(unknown)}"
    for pad in footprint.Pads():
        net_name = part.nets.get(pad.GetNumber(), NO_NET)
        open_net = open_pin_nets.get(f"{part.ref}.{pad.GetNumber()}")
        if net_name != NO_NET:
            pad.SetNet(_net(board, net_name))
        elif open_net is not None:
            pad.SetNet(_board_net(board, open_net))


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


def _zone(board: pcbnew.BOARD, net_name: str, layer: int, rectangles: list[tuple], priority: int = 0) -> None:
    """One zone over the union of the rectangles (left, top, right, bottom)."""
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(_net(board, net_name))
    zone.SetAssignedPriority(priority)
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)  # hand-soldered pins must not sink the heat
    zone.SetThermalReliefGap(mm(0.25))
    zone.SetThermalReliefSpokeWidth(mm(0.4))
    zone.SetMinThickness(mm(0.2))
    zone.SetLocalClearance(mm(0.2))
    union = pcbnew.SHAPE_POLY_SET()
    for left, top, right, bottom in rectangles:
        union.NewOutline()
        for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
            union.Append(mm(x), mm(y))
    union.Simplify()
    assert union.OutlineCount() == 1, f"{net_name} zone: the rectangles do not form one piece"
    # Copied point by point: handing the union itself to the zone makes pcbnew free it twice.
    merged = union.Outline(0)
    outline = zone.Outline()
    outline.NewOutline()
    for index in range(merged.PointCount()):
        corner = merged.CPoint(index)
        outline.Append(corner.x, corner.y)
    board.Add(zone)


def add_fiducial_keepouts(board: pcbnew.BOARD) -> None:
    """Bare board inside each fiducial's solder-mask opening: no pour, no track, no via."""
    radius = circuit.FIDUCIAL_MASK_DIAMETER / 2 + 0.1
    for x, y in circuit.FIDUCIALS:
        area = pcbnew.ZONE(board)
        area.SetIsRuleArea(True)
        area.SetLayer(pcbnew.B_Cu)
        area.SetDoNotAllowCopperPour(True)
        area.SetDoNotAllowTracks(True)
        area.SetDoNotAllowVias(True)
        area.SetDoNotAllowPads(False)
        area.SetDoNotAllowFootprints(False)
        outline = area.Outline()
        outline.NewOutline()
        for step in range(16):
            angle = math.radians(step * 22.5)
            outline.Append(mm(x + radius * math.cos(angle)), mm(y + radius * math.sin(angle)))
        board.Add(area)


def _whole_board() -> list[tuple]:
    return [(0.0, 0.0, BOARD_SPEC["board"]["width"], BOARD_SPEC["board"]["height"])]


def add_inner_planes(board: pcbnew.BOARD) -> None:
    _zone(board, GND, pcbnew.In1_Cu, _whole_board())
    _zone(board, V5, pcbnew.In2_Cu, _whole_board())
    _zone(board, V3, pcbnew.In2_Cu, V3_ISLAND, priority=1)
    _zone(board, V1, pcbnew.In2_Cu, V1_ISLAND, priority=2)


def add_outer_ground_pours(board: pcbnew.BOARD) -> None:
    _zone(board, GND, pcbnew.F_Cu, _whole_board())
    _zone(board, GND, pcbnew.B_Cu, _whole_board())


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

    for ref, pin in (circuit.DECOUPLING_CAPS | circuit.SECOND_SUPPLY_CAPS).items():
        cap = placed[ref]
        pin_xy = circuit.mcu_pin_xy(pin)
        near, far = _pads(cap, "1")[0], _pads(cap, "2")[0]
        assert math.dist(near, pin_xy) < math.dist(far, pin_xy), f"{ref} is reversed"

    # The crystal's load capacitors: the signal pad faces the crystal pad it loads.
    for cap_ref, crystal_pad in (("C15", "1"), ("C16", "3")):
        signal, ground = _pads(placed[cap_ref], "1")[0], _pads(placed[cap_ref], "2")[0]
        crystal_xy = _pads(placed["Y1"], crystal_pad)[0]
        assert math.dist(signal, crystal_xy) < math.dist(ground, crystal_xy), f"{cap_ref} is reversed"
    mcu_xin = circuit.mcu_pin_xy(21)
    xin_pad, drive_pad = _pads(placed["Y1"], "1")[0], _pads(placed["Y1"], "3")[0]
    assert math.dist(xin_pad, mcu_xin) < 8.0 and math.dist(drive_pad, mcu_xin) < 8.0, "the crystal is far from XIN"

    for ref, footprint in placed.items():
        if ref.startswith("FID"):
            assert footprint.IsFlipped(), f"{ref} is not on the assembly face"


def write_models() -> None:
    """One model file per footprint type, and two sanity checks on them."""
    real_parts = [part for part in circuit.all_parts() if part.footprint_key not in circuit.NOT_A_PART]
    missing = sorted({part.footprint_key for part in real_parts} - models.MODELLED)
    assert not missing, f"no 3D model for {missing}"
    floor_gap = BOARD_SPEC["stack"]["underside_clearance"]
    for key in sorted(models.MODELLED):
        footprint = _load_footprint(circuit.FOOTPRINT[key])
        models.write_model(key, footprint)
        on_bottom = any(part.footprint_key == key and part.side == BOTTOM for part in real_parts)
        height = max(solid.z_top for solid in models.solids(key, footprint))
        assert not on_bottom or height < floor_gap, f"{key} is {height} mm tall, the case floor is {floor_gap} mm away"


def build_board(board_path: Path, open_pin_nets: dict[str, str]) -> pcbnew.BOARD:
    """open_pin_nets: "U1.14" -> the net name KiCad's schematic netlist gives that unconnected pin."""
    parts = circuit.all_parts()
    circuit.check_netlist(parts)
    board = pcbnew.NewBoard(str(board_path))
    board.SetCopperLayerCount(4)
    _rules(board)
    _outline(board)
    placed = {part.ref: _place(board, part, open_pin_nets) for part in parts}
    check_placement(placed)
    silk.add_labels(board)
    add_inner_planes(board)
    add_fiducial_keepouts(board)
    return board
