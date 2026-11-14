"""Builds the unrouted KiCad board from circuit.py. Runs inside the KiCad container (needs pcbnew)."""

from __future__ import annotations

import json
import math
import re
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
# Top-view position of a reference that would sit on other parts' pads at its library spot. J1's lands on
# the USB series resistors, so it moves beside the connector's right shell leg.
REFERENCE_POSITION = {"J1": (49.6, 8.9)}

# JLCPCB 4-layer capability with margin: 0.09 mm track/space and 0.3 mm drill are their limits.
TRACK_WIDTH = 0.15
CLEARANCE = 0.15
VIA_DIAMETER = 0.6
VIA_DRILL = 0.3
EDGE_CLEARANCE = 0.3
SILK_EDGE_CLEARANCE = 0.2
# Copper layer of each plane. Ground sits next to the bottom face, which carries every machine-placed part and
# most of the tracks; the 5 V plane with its 3.3 V and 1.1 V islands sits next to the top face.
GROUND_LAYER = pcbnew.In2_Cu
POWER_LAYER = pcbnew.In1_Cu
# The 3.3 V island on the power layer: under the MCU and the display header, with a tongue up to
# the USB connector, and one out to the left encoder's pull-ups (circuit.ENCODER_PULL_UPS). The right
# encoder's pull-ups sit at the island's right edge.
V3_ISLAND = [(23.0, 8.5, 61.0, 26.5), (37.0, 0.0, 47.5, 9.0), (8.0, 7.4, 23.5, 14.6)]
# The 1.1 V core island, cut out of the 3.3 V island: a square under the chip, with a lobe out to
# the supply via of each DVDD pin that has its capacitor straight in front of it (pins 6 and 23), and a
# notch inside the pad ring where the 3.3 V via of VREG_VIN (pin 49) reaches the 3.3 V island.
V1_ISLAND = [(38.6, 15.8, 45.4, 20.9), (38.6, 14.1, 39.8, 15.8), (41.0, 14.1, 45.4, 15.8),
             (45.0, 15.9, 47.1, 17.5), (41.2, 20.5, 42.8, 22.6)]
ROUTING_RULES = Rules(track_width=TRACK_WIDTH, clearance=CLEARANCE, via_diameter=VIA_DIAMETER,
                      via_drill=VIA_DRILL, edge_clearance=EDGE_CLEARANCE)
# The board-wide limits kicad-cli's DRC checks against, as they are written into macropad.kicad_pro.
# KiCad 9 keeps the design rules in the project file, not in the board file.
DRC_RULES = {
    "min_track_width": 0.127,
    "min_clearance": 0.127,
    "min_via_diameter": 0.45,
    "min_through_hole_diameter": 0.3,
    "min_copper_edge_clearance": EDGE_CLEARANCE,
    "min_hole_clearance": 0.2,
    "min_hole_to_hole": 0.25,
}
DEFAULT_NET_CLASS = {"track_width": TRACK_WIDTH, "clearance": CLEARANCE, "via_diameter": VIA_DIAMETER,
                     "via_drill": VIA_DRILL}
# Solder paste on the MCU's exposed pad: windows (x, y, width, height) in footprint coordinates, with the four
# ground vias (route._EXPOSED_PAD_VIA_OFFSETS) between them. A centre square, four arms between the vias and
# four small corner squares. Each window keeps EP_PASTE_VIA_GAP from every via's copper ring, so paste does not
# wick into the holes. About 50 % of the 3.4 mm pad.
EP_PASTE_WINDOWS = ((0.0, 0.0, 1.1, 1.1),
                    (1.175, 0.0, 0.95, 1.1), (-1.175, 0.0, 0.95, 1.1),
                    (0.0, 1.175, 1.1, 0.95), (0.0, -1.175, 1.1, 0.95),
                    (1.485, 1.485, 0.33, 0.33), (-1.485, 1.485, 0.33, 0.33), (1.485, -1.485, 0.33, 0.33),
                    (-1.485, -1.485, 0.33, 0.33))
EP_SIZE = 3.4
EP_PASTE_COVERAGE = (0.5, 0.7)
EP_PASTE_VIA_GAP = 0.15
# No paste aperture anywhere comes closer than this to a via's drilled hole.
PASTE_TO_VIA_DRILL = 0.15


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
    if part.footprint_key == "HOLE_M2_GND":
        _size_ground_bond(footprint)
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
    if part.ref in REFERENCE_POSITION:
        footprint.Reference().SetPosition(point(*REFERENCE_POSITION[part.ref]))
    silk.fit_footprint_silk(footprint)
    if not part.machine_assembled:
        footprint.SetExcludedFromPosFiles(True)
    footprint.SetDNP(part.dnp)
    _connect(board, footprint, part, open_pin_nets)
    return footprint


def _size_ground_bond(footprint: pcbnew.FOOTPRINT) -> None:
    """The case ground ring and its hole, from board.toml. The library copy must agree, or DRC reports it."""
    mounting = BOARD_SPEC["mounting"]
    (pad,) = footprint.Pads()
    pad.SetSize(pcbnew.VECTOR2I(mm(mounting["ground_bond_pad_diameter"]), mm(mounting["ground_bond_pad_diameter"])))
    pad.SetDrillSize(pcbnew.VECTOR2I(mm(mounting["hole_diameter"]), mm(mounting["hole_diameter"])))


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


def add_inductor_keepouts(board: pcbnew.BOARD) -> None:
    """No copper under the regulator inductor on the other layers, and no bottom-layer pour between its pads
    (RP2350 datasheet 6.3.8)."""
    add_keepouts_above_bottom(board, [route.inductor_keepout(board)])
    _rule_area(board, pcbnew.B_Cu, route.inductor_gap(board), tracks_and_vias=False)


def add_keepouts_above_bottom(board: pcbnew.BOARD, rects: list[tuple]) -> None:
    """Rule areas with no copper on the top and the two inner layers. The VREG_LX keepouts come from the routed
    track (route.switch_node_keepouts), so they are added after routing."""
    for layer in route.REGULATOR_KEEPOUT_LAYERS:
        for rect in rects:
            _rule_area(board, layer, rect, tracks_and_vias=True)


def _rule_area(board: pcbnew.BOARD, layer: int, rect: tuple, tracks_and_vias: bool) -> None:
    area = pcbnew.ZONE(board)
    area.SetIsRuleArea(True)
    area.SetLayer(layer)
    area.SetDoNotAllowCopperPour(True)
    area.SetDoNotAllowTracks(tracks_and_vias)
    area.SetDoNotAllowVias(tracks_and_vias)
    area.SetDoNotAllowPads(False)
    area.SetDoNotAllowFootprints(False)
    left, top, right, bottom = rect
    outline = area.Outline()
    outline.NewOutline()
    for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
        outline.Append(mm(x), mm(y))
    board.Add(area)


def _whole_board() -> list[tuple]:
    return [(0.0, 0.0, BOARD_SPEC["board"]["width"], BOARD_SPEC["board"]["height"])]


def add_inner_planes(board: pcbnew.BOARD) -> None:
    _zone(board, GND, GROUND_LAYER, _whole_board())
    _zone(board, V5, POWER_LAYER, _whole_board())
    _zone(board, V3, POWER_LAYER, V3_ISLAND, priority=1)
    _zone(board, V1, POWER_LAYER, V1_ISLAND, priority=2)


def add_outer_ground_pours(board: pcbnew.BOARD) -> None:
    _zone(board, GND, pcbnew.F_Cu, _whole_board())
    _zone(board, GND, pcbnew.B_Cu, _whole_board())


def _rules(board: pcbnew.BOARD) -> None:
    """The same rules on the board in memory, for the DRC runs on boards saved without the project file."""
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = mm(DRC_RULES["min_track_width"])
    settings.m_MinClearance = mm(DRC_RULES["min_clearance"])
    settings.m_ViasMinSize = mm(DRC_RULES["min_via_diameter"])
    settings.m_MinThroughDrill = mm(DRC_RULES["min_through_hole_diameter"])
    settings.m_CopperEdgeClearance = mm(DRC_RULES["min_copper_edge_clearance"])
    settings.m_HoleClearance = mm(DRC_RULES["min_hole_clearance"])
    settings.m_HoleToHoleMin = mm(DRC_RULES["min_hole_to_hole"])
    settings.m_TentViasFront = True  # the vias in the MCU's exposed pad stay covered on the top face
    settings.m_TentViasBack = True
    default_class = settings.m_NetSettings.GetDefaultNetclass()
    default_class.SetTrackWidth(mm(TRACK_WIDTH))
    default_class.SetClearance(mm(CLEARANCE))
    default_class.SetViaDiameter(mm(VIA_DIAMETER))
    default_class.SetViaDrill(mm(VIA_DRILL))


def write_project_rules(project_path: Path, rules: dict[str, float] = DRC_RULES) -> None:
    """Writes the design rules into the KiCad project file, where kicad-cli's DRC reads them. Saving the board
    from Python does not write this file."""
    project = json.loads(project_path.read_text())
    project["board"]["design_settings"]["rules"].update(rules)
    (default_class,) = [c for c in project["net_settings"]["classes"] if c["name"] == "Default"]
    default_class.update(DEFAULT_NET_CLASS)
    project_path.write_text(json.dumps(project, indent=2, sort_keys=True) + "\n")


# --- the MCU footprint with windowed exposed-pad paste -----------------------------------------

def _paste_pad(x: float, y: float, width: float, height: float) -> str:
    return (f'\t(pad "" smd rect\n\t\t(at {x:g} {y:g})\n\t\t(size {width:g} {height:g})\n'
            f'\t\t(layers "F.Paste")\n\t)\n')


def check_paste_windows() -> None:
    """The exposed-pad windows: inside the pad, EP_PASTE_VIA_GAP clear of every via's copper ring, about half
    the pad."""
    half = EP_SIZE / 2
    via_reach = VIA_DIAMETER / 2 + EP_PASTE_VIA_GAP
    for x, y, width, height in EP_PASTE_WINDOWS:
        window = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
        assert -half <= window[0] and window[2] <= half and -half <= window[1] and window[3] <= half, \
            f"paste window at ({x}, {y}) leaves the exposed pad"
        for dx, dy in route.EXPOSED_PAD_VIA_OFFSETS:
            assert not route.circle_meets_rect(dx, dy, via_reach, window), \
                f"paste window at ({x}, {y}) is within {EP_PASTE_VIA_GAP} mm of the via at ({dx}, {dy})"
    coverage = sum(width * height for _, _, width, height in EP_PASTE_WINDOWS) / EP_SIZE ** 2
    low, high = EP_PASTE_COVERAGE
    assert low <= coverage <= high, f"exposed-pad paste covers {coverage:.0%}, wanted {low:.0%} to {high:.0%}"


def write_derived_footprints() -> None:
    """The project copy of the MCU footprint: KiCad's stock QFN-60 with its nine exposed-pad paste squares
    replaced by EP_PASTE_WINDOWS. Everything else is the stock file's text."""
    check_paste_windows()
    project_name = circuit.FOOTPRINT["QFN60"]
    library, stock_name = circuit.DERIVED_FOOTPRINTS[project_name].split(":")
    text = (STOCK_FOOTPRINTS / f"{library}.pretty" / f"{stock_name}.kicad_mod").read_text()
    paste_pad = re.compile(r'\t\(pad "" smd roundrect\n(?:\t\t[^\n]*\n)*?\t\)\n')
    assert len(paste_pad.findall(text)) == 9, "the stock QFN-60 no longer has nine exposed-pad paste squares"
    first = paste_pad.search(text).start()
    text = paste_pad.sub("", text)
    text = text[:first] + "".join(_paste_pad(*window) for window in EP_PASTE_WINDOWS) + text[first:]
    footprint_name = project_name.split(":")[1]
    text = text.replace(f'(footprint "{stock_name}"', f'(footprint "{footprint_name}"', 1)
    text = text.replace(f'(property "Value" "{stock_name}"', f'(property "Value" "{footprint_name}"', 1)
    text = text.replace('(generator "kicad-footprint-generator")',
                        '(generator "macropad")\n\t(generator_version "pcb/gen/layout.py")', 1)
    (PROJECT_FOOTPRINTS / "macropad.pretty" / f"{footprint_name}.kicad_mod").write_text(text)


def _copper_pads(footprint: pcbnew.FOOTPRINT) -> list[tuple]:
    return sorted((pad.GetNumber(), pad.GetPosition().x, pad.GetPosition().y, pad.GetSize(pcbnew.F_Cu).x,
                   pad.GetSize(pcbnew.F_Cu).y, pad.GetShape(pcbnew.F_Cu), pad.GetLayerSet().FmtHex())
                  for pad in footprint.Pads() if pad.IsOnCopperLayer())


def check_derived_footprints() -> None:
    """Each project copy of a stock footprint has exactly the stock copper pads: only the paste differs."""
    for project_name, stock_name in circuit.DERIVED_FOOTPRINTS.items():
        project, stock = _load_footprint(project_name), _load_footprint(stock_name)
        assert _copper_pads(project) == _copper_pads(stock), f"{project_name}: copper differs from {stock_name}"


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

    _check_inductor_dot(placed["L1"])
    _check_pull_ups(placed)

    for ref, footprint in placed.items():
        if ref.startswith("FID"):
            assert footprint.IsFlipped(), f"{ref} is not on the assembly face"


def _check_pull_ups(placed: dict[str, pcbnew.FOOTPRINT]) -> None:
    """Each encoder pull-up sits on the bottom face within 3 mm of its encoder pin, its signal pad toward the pin."""
    for ref, net in circuit.ENCODER_PULL_UPS.items():
        side = "left" if net.startswith("ENC_L") else "right"
        pin_xy = circuit.encoder_pin_xy(side, net[-1])
        encoder = placed["ENC1" if side == "left" else "ENC2"]
        assert _close(_pads(encoder, net[-1])[0], pin_xy), f"encoder pin {net[-1]} is not where circuit.py says"
        signal, supply = _pads(placed[ref], "1")[0], _pads(placed[ref], "2")[0]
        assert placed[ref].IsFlipped(), f"{ref} is not on the bottom face"
        assert math.dist(signal, pin_xy) < math.dist(supply, pin_xy) < 3.0, f"{ref} is reversed or far from {net}"


def check_ground_bond(board: pcbnew.BOARD) -> None:
    """The case ground ring: on GND, with board.toml's ring and hole size, at board.toml's spot, and no copper of
    another net within the clearance. Run after placement for pads, and again after routing for tracks and vias."""
    mounting = BOARD_SPEC["mounting"]
    ring_footprint = circuit.FOOTPRINT["HOLE_M2_GND"].split(":")[1]
    rings = [footprint for footprint in board.GetFootprints()
             if str(footprint.GetFPID().GetLibItemName()) == ring_footprint]
    assert len(rings) == 1, f"{len(rings)} ground-bond holes on the board"
    (ring,) = rings[0].Pads()
    centre = pad_xy(ring)
    radius = mounting["ground_bond_pad_diameter"] / 2
    assert ring.GetNetname() == GND, f"the ground-bond ring is on {ring.GetNetname() or 'no net'}"
    assert _close(centre, tuple(mounting["ground_bond_hole"])), f"the ground-bond ring is at {centre}"
    ring_size = ring.GetSize(pcbnew.F_Cu)
    assert ring.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE and all(
        abs(pcbnew.ToMM(size) - 2 * radius) < 1e-3 for size in (ring_size.x, ring_size.y)), \
        "the ground-bond ring does not have board.toml's diameter"
    assert abs(pcbnew.ToMM(ring.GetDrillSize().x) - mounting["hole_diameter"]) < 1e-3, "the ground-bond hole is resized"
    assert ring.IsOnLayer(pcbnew.F_Cu) and ring.IsOnLayer(pcbnew.F_Mask), \
        "the ground-bond ring is not bare on the top face"
    reach = radius + CLEARANCE
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetname() != GND and pad.IsOnCopperLayer():
                assert not route.circle_meets_rect(*centre, reach, route.box_mm(pad.GetBoundingBox())), \
                    f"{footprint.GetReference()} pad {pad.GetNumber()} is within {CLEARANCE} mm of the ground-bond ring"
    for item in board.GetTracks():
        if item.GetNetname() == GND:
            continue
        half_width = pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu) if item.GetClass() == "PCB_VIA" else item.GetWidth()) / 2
        start, end = (pcbnew.ToMM(item.GetStart().x), pcbnew.ToMM(item.GetStart().y)), \
            (pcbnew.ToMM(item.GetEnd().x), pcbnew.ToMM(item.GetEnd().y))
        assert route.point_segment_distance(centre, start, end) >= reach + half_width, \
            f"{item.GetNetname()} copper at {start} is within {CLEARANCE} mm of the ground-bond ring"


def check_paste_clear_of_vias(board: pcbnew.BOARD) -> None:
    """Board-wide: no solder-paste aperture comes within PASTE_TO_VIA_DRILL of a via's hole, and every via is
    covered by solder mask on the top face."""
    vias = [track for track in board.GetTracks() if track.GetClass() == "PCB_VIA"]
    for via in vias:
        assert via.IsTented(pcbnew.F_Mask), f"via at {pad_xy(via)} is not tented on the top face"
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            for layer in (pcbnew.F_Paste, pcbnew.B_Paste):
                if not pad.IsOnLayer(layer):
                    continue
                margin = pad.GetSolderPasteMargin(layer)
                left, top, right, bottom = route.box_mm(pad.GetBoundingBox())
                aperture = (left - pcbnew.ToMM(margin.x), top - pcbnew.ToMM(margin.y),
                            right + pcbnew.ToMM(margin.x), bottom + pcbnew.ToMM(margin.y))
                for via in vias:
                    reach = pcbnew.ToMM(via.GetDrillValue()) / 2 + PASTE_TO_VIA_DRILL
                    assert not route.circle_meets_rect(*pad_xy(via), reach, aperture), (
                        f"{footprint.GetReference()}: paste aperture at {pad_xy(pad)} is within "
                        f"{PASTE_TO_VIA_DRILL} mm "
                        f"of the via hole at {pad_xy(via)}")


def _dots(footprint: pcbnew.FOOTPRINT, layer: int) -> list[tuple[float, float]]:
    """Centres of the filled circles a footprint draws on one layer."""
    return [(pcbnew.ToMM(item.GetCenter().x), pcbnew.ToMM(item.GetCenter().y))
            for item in footprint.GraphicalItems()
            if item.GetLayer() == layer and item.GetClass() == "PCB_SHAPE"
            and item.GetShape() == pcbnew.SHAPE_T_CIRCLE and item.IsFilled()]


def _check_inductor_dot(inductor: pcbnew.FOOTPRINT) -> None:
    """The polarity dot on the silkscreen and on the assembly drawing marks the +1V1 end of L1."""
    pad_of_net = {net: pad for pad, net in circuit.INDUCTOR_PADS.items()}
    output_pad = _pads(inductor, pad_of_net[V1])[0]
    switch_pad = _pads(inductor, pad_of_net["VREG_LX"])[0]
    for layer, name in ((pcbnew.B_SilkS, "B.SilkS"), (pcbnew.B_Fab, "B.Fab")):
        dots = _dots(inductor, layer)
        assert dots, f"L1 has no polarity dot on {name}"
        for dot in dots:
            assert math.dist(dot, output_pad) < math.dist(dot, switch_pad), f"L1 dot on {name} is not at the +1V1 end"


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
    check_ground_bond(board)
    silk.add_labels(board)
    silk.check_minimums(board)
    add_inner_planes(board)
    add_fiducial_keepouts(board)
    add_inductor_keepouts(board)
    return board
