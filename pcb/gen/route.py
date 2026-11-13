"""Routes the placed board with router.py and writes the tracks and vias. Needs pcbnew.

Order: the sensitive connections first, while the board is empty and they can take the shortest
way; then one via to the plane for every power and ground pad; then the ordinary signals,
shortest first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pcbnew

import circuit
import schematic
from circuit import BOARD_SPEC, GND, V1, V3, V5, VBUS
from router import BACK, BOTH_LAYERS, FRONT, Pad, Router, Rules, Via

PLANE_NETS = (GND, V1, V3, V5)
# Routed before anything else, in this order. Limits are track lengths in mm that fail the build.
SENSITIVE_NETS = ("VREG_LX", "USB_DM", "USB_DP", "USB_D_P", "USB_D_N", "XIN", "XOUT", "XTAL_DRIVE", "VREG_AVDD")
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
USB_PAIR_MISMATCH_LIMIT = 2.0  # mm; full-speed USB tolerates far more, this only catches a detour
# Nets that must stay on the bottom layer, over the unbroken ground plane, from pad to pad.
NO_VIA_NETS = ("VREG_LX", "USB_DM", "USB_DP", "USB_D_P")
_PLANE_EDGE_MARGIN = 0.55  # a via this close to the edge of its plane island might miss it
_KICAD_LAYER = {FRONT: pcbnew.F_Cu, BACK: pcbnew.B_Cu}
# Ground vias in the MCU's exposed pad: the chip's ground return and its heat path.
_EXPOSED_PAD_VIA_OFFSETS = ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0))


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

    def report_lines(self) -> list[str]:
        router = self.router
        nets = sorted({track.net for track in router.tracks})
        lines = [
            f"tracks {len(router.tracks)}  vias {len(router.vias)}  "
            f"length {sum(t.length for t in router.tracks):.1f} mm  unrouted pads {len(self.unrouted)}",
            f"USB pair, connector to MCU: D+ {usb_path_length(router, 'P'):.2f} mm, "
            f"D- {usb_path_length(router, 'N'):.2f} mm",
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


def _rect(box: pcbnew.BOX2I) -> tuple[float, float, float, float]:
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
            pad = Pad(name, net, _rect(kicad_pad.GetBoundingBox()), layers)
            router.add_pad(pad)
            pads.setdefault(name, []).append(pad)
    mask_radius = circuit.FIDUCIAL_MASK_DIAMETER / 2
    for x, y in circuit.FIDUCIALS:
        router.add_keepout((x - mask_radius, y - mask_radius, x + mask_radius, y + mask_radius), (BACK,))
    return pads


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
        for dx, dy in _EXPOSED_PAD_VIA_OFFSETS:
            self.router.add_via_in_pad(GND, circuit.MCU_X + dx, circuit.MCU_Y + dy)

    def pair(self, net: str, first: str, second: str) -> None:
        if not self.router.route_pair(net, self.pad(first), self.pad(second)):
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
        for number, pin in enumerate(circuit.DECOUPLED_PINS, start=1):
            self._decouple(number, pin)
        self.pair(V3, "U1.44", "U1.45")
        self.pair(V3, "U1.54", "U1.53")
        self.pair(V3, "U1.49", "C11.1")
        self.pair(GND, "U1.47", "U1.61")
        self.fan_out(self.pad("U1.50"))  # VREG_FB senses the core voltage at the island

    def _decouple(self, number: int, pin: int) -> None:
        """Supply via, capacitor, ground via on one line pointing away from the chip.

        Hand-placed: left to the search, these vias land beside the capacitor, in the lanes the
        neighbouring pins need. Where the supply via has no room or no plane under it, the search
        takes over; a DVDD pin then drops its via into the 1.1 V island just inside the pad ring.
        """
        net = circuit.MCU_POWER_PINS[pin]
        out_x, out_y = circuit.outward(pin)
        supply_pad, ground_pad = self.pad(f"C{number}.1"), self.pad(f"C{number}.2")
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

    def regulator_output(self) -> None:
        """Inductor to its two capacitors and the probe pad, then to the via at VREG_FB that enters the 1.1 V island.

        Wide all the way: the link to the island runs on the top layer, under the chip.
        """
        output = [self.pad("L1.2"), self.pad("C12.1"), self.pad("C13.1"), self.pad(f"{circuit.CORE_TEST_PAD}.1")]
        failed = self.router.route_net(V1, output, wide=True)
        self.unrouted += [f"{V1}: {name}" for name in failed]
        feedback_pin = self.pad("U1.50").centre
        island_via = min((via for via in self.router.vias if via.net == V1),
                         key=lambda via: math.dist((via.x, via.y), feedback_pin))
        if not self.router.route_to_via(V1, output, island_via, wide=True):
            self.unrouted.append(f"{V1}: regulator output to the island")
        self.on_plane.update(output)

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
    plan.mcu_supply()
    plan.regulator_output()
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
    return RoutingResult(router, plan.unrouted)


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


def check_sensitive_lengths(router: Router) -> None:
    for net, limit in LENGTH_LIMIT.items():
        length = router.net_length(net)
        assert 0 < length <= limit, f"{net} is {length:.2f} mm long, limit {limit} mm"
    for net in NO_VIA_NETS:
        vias = sum(via.net == net for via in router.vias)
        assert vias == 0, f"{net} changes layer {vias} times"
    mismatch = abs(usb_path_length(router, "P") - usb_path_length(router, "N"))
    assert mismatch <= USB_PAIR_MISMATCH_LIMIT, f"USB D+ and D- differ by {mismatch:.2f} mm"
