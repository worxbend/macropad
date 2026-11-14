"""Routes the placed board with router.py and writes the tracks and vias. Needs pcbnew.

Order: the 1.1 V regulator and the other sensitive connections first, while the board is empty and
they can take the shortest way; then one via to the plane for every power and ground pad; then the
ordinary signals, shortest first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pcbnew

import circuit
import schematic
from circuit import BOARD_SPEC, GND, V1, V3, V5, VBUS
from router import BACK, BOTH_LAYERS, FRONT, Pad, Router, Rules, Track, Via

PLANE_NETS = (GND, V1, V3, V5)
# The USB lines from pins 51 and 52 squeeze past the regulator to their series resistors. They go straight
# after it, before the decoupling vias of pins 53 and 54 take their lanes. D+ first: it has to lean right
# to its resistor, and D- then fits on the inside.
REGULATOR_NEIGHBOURS = ("USB_DP", "USB_DM")
# Routed after the MCU supply, in this order. Limits are track lengths in mm that fail the build.
SENSITIVE_NETS = ("USB_D_P", "USB_D_N", "XIN", "XOUT", "XTAL_DRIVE", "VREG_AVDD")
# MCU nets whose other pads are right next to the chip. Routed whole, straight after the sensitive ones.
LOCAL_NETS = ("QSPI_SS", "BOOT")
# RUN goes first of all signals: its pull-up and the reset button are on the far side of the SWD pins.
# SWCLK and SWDIO sit between the DVDD capacitor and the crystal pins. They get their way out of the
# chip before the crystal nets, which otherwise cross the only spot where SWCLK can change layer.
EARLY_ESCAPES = ("U1.24", "U1.25")
# Every other MCU signal first gets a track out of this square around the chip, one pin at a time.
# Without it the early nets wall in the pins of the late ones.
ESCAPE_DISTANCE = 8.0
# XOUT is the long one on purpose: it is driven by the chip and ends in the 1 k resistor next to the
# crystal, so the crystal's own two nodes (XIN, XTAL_DRIVE) stay short.
LENGTH_LIMIT = {"VREG_LX": 4.0, "USB_DM": 3.5, "USB_DP": 3.5, "XIN": 9.0, "XTAL_DRIVE": 9.0, "XOUT": 16.0,
                "VREG_AVDD": 8.0}
# VREG_FB is fed from COUT (RP2350 datasheet 6.3.8.1): one short track from pin 50 to the COUT pad.
FEEDBACK_LENGTH_LIMIT = 3.0
# It runs straight up from pin 50, past CIN's 3.3 V pad, to this point, offset (x, y) from the pin, and
# then turns to COUT. USB D- and D+ run straight up beside it from pins 51 and 52.
FEEDBACK_WAYPOINT = (0.0, -1.55)
# VREG_AVDD is noise sensitive and VREG_LX is the switching node: their tracks stay this far apart,
# centre to centre. The two pins are 0.8 mm apart, so this allows only the stubs at the pins.
AVDD_TO_LX_MIN_DISTANCE = 0.75
# How far the copper keepout reaches beyond the inductor's pads and the VREG_LX copper.
REGULATOR_KEEPOUT_MARGIN = 0.2
# Layers that must have no copper under the inductor and the VREG_LX node; the bottom layer carries them.
REGULATOR_KEEPOUT_LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu)
USB_PAIR_MISMATCH_LIMIT = 2.0  # mm; full-speed USB tolerates far more, this only catches a detour
# Nets that must stay on the bottom layer, over the unbroken ground plane on In2.Cu, from pad to pad.
NO_VIA_NETS = ("VREG_LX", "USB_DM", "USB_DP", "USB_D_P")
_PLANE_EDGE_MARGIN = 0.55  # a via this close to the edge of its plane island might miss it
_KICAD_LAYER = {FRONT: pcbnew.F_Cu, BACK: pcbnew.B_Cu}
# Ground vias in the MCU's exposed pad: the chip's ground return and its heat path.
# The exposed pad's paste windows leave room for them (layout.EP_PASTE_WINDOWS).
EXPOSED_PAD_VIA_OFFSETS = ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0))
# Hand-placed regulator vias: net and offset (x, y) from the VREG_LX pin (48). Two ground vias beside the
# joined ground pads of CIN and COUT; the 3.3 V via that feeds VREG_VIN from inside the pad ring, in a
# notch of the 1.1 V island (layout.V1_ISLAND); the two ends of the wide 1.1 V link from the inductor's
# +1V1 pad, over the chip on the top layer, into the core island.
REGULATOR_VIAS = {
    "ground_cin": (GND, circuit.CAPACITOR_SHIFT - 1.2, -circuit.CIN_DISTANCE),
    "ground_cout": (GND, circuit.CAPACITOR_SHIFT - 1.2, -circuit.COUT_DISTANCE),
    "vin": (V3, 0.4, 0.95),
    "core_out": (V1, 0.6, -5.25),
    "core_in": (V1, 1.6, 0.95),
}


@dataclass(frozen=True)
class Setup:
    rules: Rules
    v3_island: list[tuple]  # rectangles (left, top, right, bottom) of the 3.3 V island on the power layer
    v1_island: list[tuple]  # the 1.1 V island inside it
    # MCU nets that go before the others, from route_order.txt (see build.py order).
    head_start: tuple[str, ...] = ()


@dataclass
class RoutingResult:
    router: Router
    unrouted: list[str] = field(default_factory=list)  # "NET: pad" for every pad left unconnected
    feedback_length: float = 0.0  # VREG_FB, pin 50 to the COUT pad
    switch_node_keepouts: list[tuple] = field(default_factory=list)  # see switch_node_keepouts()

    def report_lines(self) -> list[str]:
        router = self.router
        nets = sorted({track.net for track in router.tracks})
        lines = [
            f"tracks {len(router.tracks)}  vias {len(router.vias)}  "
            f"length {sum(t.length for t in router.tracks):.1f} mm  unrouted pads {len(self.unrouted)}",
            f"USB pair, connector to MCU: D+ {usb_path_length(router, 'P'):.2f} mm, "
            f"D- {usb_path_length(router, 'N'):.2f} mm",
            f"VREG_FB, pin 50 to COUT: {self.feedback_length:.2f} mm",
            "",
            f"{'net':14} {'mm':>7} {'vias':>4}",
        ]
        for net in nets:
            vias = sum(via.net == net for via in router.vias)
            lines.append(f"{net:14} {router.net_length(net):7.2f} {vias:4}")
        lines += ["", "unrouted:"] + (self.unrouted or ["none"])
        return lines


def usb_path_length(router: Router, polarity: str) -> float:
    """Copper from the connector to the MCU pin of one USB line, both sides of the series resistor."""
    mcu_side = {"P": "USB_DP", "N": "USB_DM"}[polarity]
    return router.net_length(f"USB_D_{polarity}") + router.net_length(mcu_side)


def box_mm(box: pcbnew.BOX2I) -> tuple[float, float, float, float]:
    return tuple(pcbnew.ToMM(v) for v in (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom()))


def _hole_rect(pad: pcbnew.PAD) -> tuple[float, float, float, float]:
    x, y = pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)
    radius = max(pcbnew.ToMM(pad.GetDrillSize().x), pcbnew.ToMM(pad.GetDrillSize().y)) / 2
    return x - radius, y - radius, x + radius, y + radius


def _load_obstacles(board: pcbnew.BOARD, router: Router) -> dict[str, list[Pad]]:
    """Feeds every pad and hole to the router. Returns the pads by name ("U1.5"); a name can repeat."""
    pads: dict[str, list[Pad]] = {}
    for footprint in sorted(board.GetFootprints(), key=lambda fp: fp.GetReference()):
        for kicad_pad in footprint.Pads():
            if kicad_pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                router.add_hole(_hole_rect(kicad_pad))
                continue
            layers = tuple(layer for layer in BOTH_LAYERS if kicad_pad.IsOnLayer(_KICAD_LAYER[layer]))
            name = f"{footprint.GetReference()}.{kicad_pad.GetNumber()}"
            net = schematic.circuit_net_name(kicad_pad.GetNetname())
            pad = Pad(name, net, box_mm(kicad_pad.GetBoundingBox()), layers)
            router.add_pad(pad)
            pads.setdefault(name, []).append(pad)
    mask_radius = circuit.FIDUCIAL_MASK_DIAMETER / 2
    for x, y in circuit.FIDUCIALS:
        router.add_keepout((x - mask_radius, y - mask_radius, x + mask_radius, y + mask_radius), (BACK,))
    _keep_top_layer_clear(router, inductor_keepout(board))
    return pads


def _keep_top_layer_clear(router: Router, rect: tuple) -> None:
    grow = router.rules.via_diameter / 2  # the keepout holds the centres; the copper keeps out of the area
    router.add_keepout(_grown(rect, grow), (FRONT,))


def _grown(rect: tuple, margin: float) -> tuple:
    left, top, right, bottom = rect
    return left - margin, top - margin, right + margin, bottom + margin


def _in_any(rectangles: list[tuple], x: float, y: float, grow: float) -> bool:
    return any(left - grow <= x <= right + grow and top - grow <= y <= bottom + grow
               for left, top, right, bottom in rectangles)


def _plane_tests(v3_island: list[tuple], v1_island: list[tuple]) -> dict:
    """Per plane net: is that net's plane under this point? Ground is everywhere on its own layer."""
    margin = _PLANE_EDGE_MARGIN
    return {
        GND: lambda x, y: True,
        V1: lambda x, y: _in_any(v1_island, x, y, -margin),
        V3: lambda x, y: _in_any(v3_island, x, y, -margin) and not _in_any(v1_island, x, y, margin),
        V5: lambda x, y: not _in_any(v3_island, x, y, margin),
    }


def _via_pad(via: Via) -> Pad:
    """A via as a pad on both layers, so a route can start from it."""
    return Pad(f"via at ({via.x:.1f}, {via.y:.1f})", via.net, (via.x, via.y) * 2, BOTH_LAYERS)


def _pin_number(pad: Pad) -> int:
    return int(pad.name.split(".")[1])


class _Plan:
    """The routing order. One method per stage; each appends what it could not connect."""

    def __init__(self, router: Router, pads: dict[str, list[Pad]], setup: Setup) -> None:
        self.router = router
        self.pads = pads
        self.plane_here = _plane_tests(setup.v3_island, setup.v1_island)
        self.head_start = setup.head_start
        self.unrouted: list[str] = []
        self.feedback_length = 0.0
        self.switch_node_keepouts: list[tuple] = []
        self.routed_nets: set[str] = set(PLANE_NETS)
        self.on_plane: set[Pad] = set()  # plane-net pads that already reach their plane
        self.by_net: dict[str, list[Pad]] = {}
        for name in sorted(pads):
            for pad in pads[name]:
                if pad.net:
                    self.by_net.setdefault(pad.net, []).append(pad)

    def pad(self, name: str) -> Pad:
        return self.pads[name][0]

    def exposed_pad_vias(self) -> None:
        for dx, dy in EXPOSED_PAD_VIA_OFFSETS:
            self.router.add_via_in_pad(GND, circuit.MCU_X + dx, circuit.MCU_Y + dy)

    def pair(self, net: str, first: str, second: str, wide: bool = False) -> None:
        if not self.router.route_pair(net, self.pad(first), self.pad(second), wide):
            self.unrouted.append(f"{net}: {first} to {second}")

    def fan_out(self, pad: Pad) -> None:
        """A wide stub if it fits, a normal one if not."""
        self.on_plane.add(pad)
        plane_here = self.plane_here[pad.net]
        if not (self.router.fan_out(pad.net, pad, plane_here, wide=True)
                or self.router.fan_out(pad.net, pad, plane_here)):
            self.unrouted.append(f"{pad.net}: {pad.name} (no via to its plane)")

    def mcu_supply(self) -> None:
        """Every MCU supply pin with its capacitor, and the vias to the planes."""
        for ref, pin in circuit.DECOUPLING_CAPS.items():
            self._decouple(ref, pin)
        self.pair(V3, "C33.1", "C10.1")
        for pad in ("C32.1", "C32.2", "C33.2"):  # no pin in front of it: straight into the planes
            self.fan_out(self.pad(pad))
        self.pair(V3, "U1.44", "U1.45")
        self.pair(V3, "U1.54", "U1.53")

    def _decouple(self, ref: str, pin: int) -> None:
        """Supply via, capacitor, ground via on one line pointing away from the chip.

        Hand-placed: left to the search, these vias land beside the capacitor, in the lanes the
        neighbouring pins need. Where the supply via has no room or no plane under it, the search
        takes over; a DVDD pin then drops its via into the 1.1 V island just inside the pad ring.
        """
        net = circuit.MCU_POWER_PINS[pin]
        out_x, out_y = circuit.outward(pin)
        supply_pad, ground_pad = self.pad(f"{ref}.1"), self.pad(f"{ref}.2")
        centre_x = (supply_pad.centre[0] + ground_pad.centre[0]) / 2
        centre_y = (supply_pad.centre[1] + ground_pad.centre[1]) / 2
        to_supply_via = circuit.DECOUPLING_DISTANCE - circuit.SUPPLY_VIA_DISTANCE
        to_ground_via = circuit.GROUND_VIA_DISTANCE
        supply_via = self.router.snapped(centre_x - out_x * to_supply_via, centre_y - out_y * to_supply_via)
        ground_via = self.router.snapped(centre_x + out_x * to_ground_via, centre_y + out_y * to_ground_via)

        pin_pad = self.pad(f"U1.{pin}")
        if self.plane_here[net](*supply_via) and self.router.via_fits(net, *supply_via):
            self.router.add_via(net, *supply_via)
            for pad in (pin_pad, supply_pad):
                if not self.router.route_to_via(net, [pad], Via(net, *supply_via)):
                    self.unrouted.append(f"{net}: {pad.name}")
        else:
            self.pair(net, pin_pad.name, supply_pad.name)
            self.fan_out(pin_pad if net == V1 else supply_pad)
        self.on_plane.add(supply_pad)

        if self.router.via_fits(GND, *ground_via):
            self.router.add_via(GND, *ground_via)
            if not self.router.route_to_via(GND, [ground_pad], Via(GND, *ground_via), wide=True):
                self.unrouted.append(f"{GND}: {ground_pad.name}")
            self.on_plane.add(ground_pad)
        else:
            self.fan_out(ground_pad)

    def core_regulator(self) -> None:
        """The 1.1 V switching regulator, before anything else (RP2350 datasheet 6.3.8).

        VREG_LX runs from its pin between the pads of CIN and COUT to the inductor. CIN joins VREG_VIN to
        PGND, COUT sits right behind it, and their ground pads share two vias. VREG_VIN takes 3.3 V from a
        via inside the pad ring. VREG_FB senses COUT. A separate wide link carries the output from the
        inductor's +1V1 pad into the core island.
        """
        lx_x, lx_y = circuit.mcu_pin_xy(48)
        via = {name: self.hand_via(net, lx_x + dx, lx_y + dy) for name, (net, dx, dy) in REGULATOR_VIAS.items()}
        switch_pad = next(pad for pad, net in circuit.INDUCTOR_PADS.items() if net == "VREG_LX")
        self.pair("VREG_LX", "U1.48", f"L1.{switch_pad}")  # from the pin: no copper drawn inside the inductor pad
        self.routed_nets.add("VREG_LX")
        self.switch_node_keepouts = switch_node_keepouts(self.router, self.pad("U1.48"))
        for rect in self.switch_node_keepouts:
            _keep_top_layer_clear(self.router, rect)
        self.pair(V3, "U1.49", "C11.1")
        self.to_via(self.pad("U1.49"), via["vin"])
        self.pair(GND, "U1.47", "C11.2")
        self.pair(GND, "C11.2", "C12.2", wide=True)
        self.to_via(self.pad("C11.2"), via["ground_cin"], wide=True)
        self.to_via(self.pad("C12.2"), via["ground_cout"], wide=True)
        tracks_before = len(self.router.tracks)
        feedback_x, feedback_y = circuit.mcu_pin_xy(50)
        waypoint = self.router.snapped(feedback_x + FEEDBACK_WAYPOINT[0], feedback_y + FEEDBACK_WAYPOINT[1])
        bend = Pad("VREG_FB bend", V1, waypoint * 2, (BACK,))
        if not (self.router.route_pair(V1, self.pad("U1.50"), bend)
                and self.router.route_pair(V1, bend, self.pad("C12.1"))):
            self.unrouted.append(f"{V1}: U1.50 (VREG_FB) to C12.1")
        self.feedback_length = sum(track.length for track in self.router.tracks[tracks_before:])
        inductor_output = next(pad for pad, net in circuit.INDUCTOR_PADS.items() if net == V1)
        output = [self.pad("C12.1"), self.pad(f"L1.{inductor_output}"), self.pad("C13.1"),
                  self.pad(f"{circuit.CORE_TEST_PAD}.1")]
        failed = self.router.route_net(V1, output, wide=True)
        self.unrouted += [f"{V1}: {name}" for name in failed]
        self.to_via(self.pad(f"L1.{inductor_output}"), via["core_out"], wide=True)
        self.to_via(_via_pad(via["core_out"]), via["core_in"], wide=True)
        self.on_plane.update(output + [self.pad(name) for name in ("C11.1", "C11.2", "C12.2")])

    def hand_via(self, net: str, x: float, y: float) -> Via:
        snapped = self.router.snapped(x, y)
        self.router.add_via(net, *snapped)
        return Via(net, *snapped)

    def to_via(self, pad: Pad, via: Via, wide: bool = False) -> None:
        if not self.router.route_to_via(via.net, [pad], via, wide):
            self.unrouted.append(f"{via.net}: {pad.name} to the via at ({via.x:.1f}, {via.y:.1f})")

    def net(self, net: str, wide: bool = False) -> None:
        failed = self.router.route_net(net, self.by_net[net], wide)
        if wide and failed:  # a wide track does not fit between fine-pitch pads
            failed = self.router.route_net(net, [pad for pad in self.by_net[net] if pad.name in failed])
        self.unrouted += [f"{net}: {name}" for name in failed]
        self.routed_nets.add(net)

    def mcu_escapes(self) -> None:
        """Each remaining MCU signal: first a track out of the crowd around the chip, then the rest of the net.

        The pin next to a decoupling capacitor goes first, then its neighbour, and so on outward:
        each track can then lean against the one before it, like the teeth of a comb.
        """
        def pins_to_capacitor(pad: Pad) -> int:
            return min(abs(_pin_number(pad) - pin) for pin in circuit.DECOUPLED_PINS)

        def turn(pad: Pad) -> tuple:
            first = self.head_start
            head_start = first.index(pad.net) if pad.net in first else len(first)
            return head_start, pins_to_capacitor(pad), _pin_number(pad)

        mcu_pads = [pad for net in sorted(self.by_net) for pad in self.by_net[net]
                    if pad.name.startswith("U1.") and net not in self.routed_nets]
        for pad in sorted(mcu_pads, key=turn):
            if self.router.has_escaped(pad) or self.escape(pad):
                self.net(pad.net)

    def escape(self, pad: Pad) -> bool:
        escaped = self.router.escape(pad.net, pad, (circuit.MCU_X, circuit.MCU_Y), ESCAPE_DISTANCE)
        if not escaped:
            self.unrouted.append(f"{pad.net}: {pad.name} (no way out from the MCU)")
        return escaped

    def crystal_ground(self) -> None:
        """Ground vias of the crystal and its load capacitors, before any track can take their place."""
        for name in ("Y1.2", "Y1.4", "C15.2", "C16.2"):
            self.fan_out(self.pad(name))

    def plane_fan_out(self) -> None:
        """Every surface pad of a plane net that has no via yet. Through-hole pads touch the planes directly."""
        for net in PLANE_NETS:
            for pad in self.by_net[net]:
                if len(pad.layers) == 1 and not pad.name.startswith("U1.") and pad not in self.on_plane:
                    self.fan_out(pad)

    def signals(self) -> None:
        remaining = [net for net in self.by_net if net not in self.routed_nets]
        for net in sorted(remaining, key=lambda name: (_spread(self.by_net[name]), name)):
            self.net(net)


def _spread(pads: list[Pad]) -> float:
    """Half the perimeter of the box around the pads: a quick guess of the track length."""
    xs = [pad.centre[0] for pad in pads]
    ys = [pad.centre[1] for pad in pads]
    return max(xs) - min(xs) + max(ys) - min(ys)


def route(board: pcbnew.BOARD, setup: Setup) -> RoutingResult:
    """Plans every track and via. Nothing is written to the board; see write_copper."""
    spec = BOARD_SPEC["board"]
    router = Router(spec["width"], spec["height"], spec["corner_radius"], setup.rules)
    plan = _Plan(router, _load_obstacles(board, router), setup)
    plan.exposed_pad_vias()
    plan.core_regulator()
    for net in REGULATOR_NEIGHBOURS:
        plan.net(net)
    plan.mcu_supply()
    plan.crystal_ground()
    plan.net("RUN")
    for name in EARLY_ESCAPES:
        plan.escape(plan.pad(name))
    for net in SENSITIVE_NETS + LOCAL_NETS:
        plan.net(net)
    plan.net(VBUS, wide=True)
    plan.plane_fan_out()
    plan.mcu_escapes()
    plan.signals()
    return RoutingResult(router, plan.unrouted, plan.feedback_length, plan.switch_node_keepouts)


def write_copper(board: pcbnew.BOARD, router: Router) -> None:
    for track in router.tracks:
        segment = pcbnew.PCB_TRACK(board)
        segment.SetStart(_point(*track.start))
        segment.SetEnd(_point(*track.end))
        segment.SetWidth(pcbnew.FromMM(track.width))
        segment.SetLayer(_KICAD_LAYER[track.layer])
        segment.SetNet(board.FindNet(schematic.board_net_name(track.net)))
        board.Add(segment)
    for via in router.vias:
        barrel = pcbnew.PCB_VIA(board)
        barrel.SetViaType(pcbnew.VIATYPE_THROUGH)
        barrel.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        barrel.SetPosition(_point(via.x, via.y))
        barrel.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(router.rules.via_diameter))
        barrel.SetDrill(pcbnew.FromMM(router.rules.via_drill))
        barrel.SetNet(board.FindNet(schematic.board_net_name(via.net)))
        board.Add(barrel)


def _point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def check_sensitive_lengths(result: RoutingResult) -> None:
    router = result.router
    for net, limit in LENGTH_LIMIT.items():
        length = router.net_length(net)
        assert 0 < length <= limit, f"{net} is {length:.2f} mm long, limit {limit} mm"
    assert 0 < result.feedback_length <= FEEDBACK_LENGTH_LIMIT, \
        f"VREG_FB to COUT is {result.feedback_length:.2f} mm, limit {FEEDBACK_LENGTH_LIMIT} mm"
    for net in NO_VIA_NETS:
        vias = sum(via.net == net for via in router.vias)
        assert vias == 0, f"{net} changes layer {vias} times"
    mismatch = abs(usb_path_length(router, "P") - usb_path_length(router, "N"))
    assert mismatch <= USB_PAIR_MISMATCH_LIMIT, f"USB D+ and D- differ by {mismatch:.2f} mm"
    gap = min(_segment_distance(a, b) for a in router.tracks if a.net == "VREG_AVDD"
              for b in router.tracks if b.net == "VREG_LX")
    assert gap >= AVDD_TO_LX_MIN_DISTANCE, f"VREG_AVDD runs {gap:.2f} mm from VREG_LX, limit {AVDD_TO_LX_MIN_DISTANCE} mm"


def inductor_keepout(board: pcbnew.BOARD) -> tuple:
    """No copper on the top and the two inner layers under the regulator inductor (RP2350 datasheet 6.3.8.1)."""
    inductor = _rect_around([box_mm(pad.GetBoundingBox()) for pad in board.FindFootprintByReference("L1").Pads()])
    return _grown(inductor, REGULATOR_KEEPOUT_MARGIN)


def switch_node_keepouts(router: Router, lx_pin: Pad) -> list[tuple]:
    """No copper on the top and the two inner layers under the VREG_LX node (RP2350 datasheet 6.3.8.1): one
    rectangle around the pin and around each routed VREG_LX segment. Built from the routed copper, so the
    keepout follows the track wherever the router put it."""
    copper = [lx_pin.rect] + [_track_box(track) for track in router.tracks if track.net == "VREG_LX"]
    return [_grown(rect, REGULATOR_KEEPOUT_MARGIN) for rect in copper]


def _track_box(track: Track) -> tuple:
    half_width = track.width / 2
    (x1, y1), (x2, y2) = track.start, track.end
    return min(x1, x2) - half_width, min(y1, y2) - half_width, max(x1, x2) + half_width, max(y1, y2) + half_width


def inductor_gap(board: pcbnew.BOARD) -> tuple:
    """The space between the inductor's two pads, where the bottom-layer ground pour must not run."""
    pads = sorted((box_mm(pad.GetBoundingBox()) for pad in board.FindFootprintByReference("L1").Pads()))
    (_, top, first_right, bottom), (second_left, second_top, _, _) = pads
    assert second_left > first_right and abs(second_top - top) < 0.01, "L1 is expected with its pads side by side in x"
    return first_right, top, second_left, bottom


def _rect_around(rects: list[tuple]) -> tuple:
    return (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))


def check_regulator_keepout(router: Router, keepouts: list[tuple]) -> None:
    """No via and no top-layer track inside the keepout under the inductor and VREG_LX (RP2350 datasheet 6.3.8)."""
    for rect in keepouts:
        for via in router.vias:
            assert not circle_meets_rect(via.x, via.y, router.rules.via_diameter / 2, rect), \
                f"{via.net} via at ({via.x:.2f}, {via.y:.2f}) under the regulator inductor or VREG_LX"
        for track in router.tracks:
            if track.layer == FRONT:
                assert not _segment_meets_rect(track, rect), f"{track.net} track under the regulator inductor or VREG_LX"


def check_no_pour_under_regulator(board: pcbnew.BOARD) -> None:
    """On the filled board: no zone copper on the top or inner layers under the VREG_LX tracks, its pin or the
    inductor's pads. The rule areas should keep it out; this catches a rule area that misses its copper."""
    lx_net = schematic.board_net_name("VREG_LX")
    lx_tracks = [track for track in board.GetTracks()
                 if track.GetClass() == "PCB_TRACK" and track.GetNetname() == lx_net]
    assert lx_tracks, "no VREG_LX track on the board"
    lx_pin = next(pad for pad in board.FindFootprintByReference("U1").Pads() if pad.GetNumber() == "48")
    copper = [(track.GetStart(), track.GetEnd(), track.GetWidth() // 2) for track in lx_tracks]
    copper += [_pad_capsule(pad) for pad in [lx_pin, *board.FindFootprintByReference("L1").Pads()]]
    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue
        for layer in REGULATOR_KEEPOUT_LAYERS:
            if not zone.IsOnLayer(layer):
                continue
            fill = zone.GetFilledPolysList(layer)
            for start, end, reach in copper:
                assert not fill.Collide(pcbnew.SEG(start, end), reach), (
                    f"{zone.GetNetname()} pour on {board.GetLayerName(layer)} under the regulator near "
                    f"({pcbnew.ToMM(start.x):.2f}, {pcbnew.ToMM(start.y):.2f})")


def _pad_capsule(pad: pcbnew.PAD) -> tuple[pcbnew.VECTOR2I, pcbnew.VECTOR2I, int]:
    """A rectangular pad as a centre line along its long side and half its short side: (start, end, reach)."""
    box = pad.GetBoundingBox()
    reach = min(box.GetWidth(), box.GetHeight()) // 2
    centre = box.GetCenter()
    if box.GetHeight() > box.GetWidth():
        start, end = pcbnew.VECTOR2I(centre.x, box.GetTop() + reach), pcbnew.VECTOR2I(centre.x, box.GetBottom() - reach)
    else:
        start, end = pcbnew.VECTOR2I(box.GetLeft() + reach, centre.y), pcbnew.VECTOR2I(box.GetRight() - reach, centre.y)
    return start, end, reach


def point_segment_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    t = 0.0 if length_squared == 0 else max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy)
                                                     / length_squared))
    return math.dist(point, (start[0] + t * dx, start[1] + t * dy))


def _cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segment_distance(a, b) -> float:
    """Centre-line distance between two track segments, seen from above: zero where they cross."""
    if (_cross(a.start, a.end, b.start) * _cross(a.start, a.end, b.end) < 0
            and _cross(b.start, b.end, a.start) * _cross(b.start, b.end, a.end) < 0):
        return 0.0
    return min(point_segment_distance(a.start, b.start, b.end), point_segment_distance(a.end, b.start, b.end),
               point_segment_distance(b.start, a.start, a.end), point_segment_distance(b.end, a.start, a.end))


def circle_meets_rect(x: float, y: float, radius: float, rect: tuple) -> bool:
    left, top, right, bottom = rect
    return math.dist((x, y), (min(max(x, left), right), min(max(y, top), bottom))) < radius


def _segment_meets_rect(track, rect: tuple) -> bool:
    """True if the track's copper reaches into the rectangle (sampled every 0.05 mm along its centre line)."""
    steps = max(1, math.ceil(track.length / 0.05))
    return any(circle_meets_rect(track.start[0] + (track.end[0] - track.start[0]) * i / steps,
                                  track.start[1] + (track.end[1] - track.start[1]) * i / steps,
                                  track.width / 2, rect) for i in range(steps + 1))
