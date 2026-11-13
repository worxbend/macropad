"""The macropad circuit: every part, its JLCPCB part number, its place on the board and its nets.

Pure Python, no KiCad import, so the netlist can be checked anywhere.
Positions are top-view board coordinates in millimetres (see board.toml).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOARD_SPEC = tomllib.loads((REPO_ROOT / "board.toml").read_text())

TOP = "top"
BOTTOM = "bottom"

GND = "GND"
VBUS = "VBUS"
V5 = "+5V"
V3 = "+3V3"
V1 = "+1V1"
NO_NET = ""

# JLCPCB part numbers, checked against the JLCPCB parts search on 2026-11-12.
LCSC = {
    "RP2354A": "C41378174",
    "AP2112K-3.3": "C51118",
    "USBLC6-2SC6": "C7519",
    "74LVC1T45": "C168856",
    "12MHz": "C50430",  # X322512MMB4SI, 10 pF load: the load the 15 pF capacitors and 1 k are sized for
    "3.3uH": "C42411119",
    "USB-C": "C165948",
    "nSMD050": "C69688",
    "TS-1187A": "C318884",
    "SK6812SIDE-A": "C5378721",
    "MX hot-swap": "C49352235",
    "EC11E18244AU": "C202365",
    "1x5 socket": "C50950",
    "100nF": "C1525",
    "1uF": "C52923",
    "4.7uF": "C23733",
    "2.2uF": "C23630",
    "10uF": "C19702",
    "15pF": "C1548",
    "1k": "C11702",
    "10k": "C25744",
    "5.1k": "C25905",
    "27R": "C25100",
    "33R": "C25105",
}

FOOTPRINT = {
    "C0402": "Capacitor_SMD:C_0402_1005Metric",
    "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "R0402": "Resistor_SMD:R_0402_1005Metric",
    "QFN60": "Package_DFN_QFN:QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm",
    "SOT23-5": "Package_TO_SOT_SMD:SOT-23-5",
    "SOT23-6": "Package_TO_SOT_SMD:SOT-23-6",
    "XTAL3225": "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    "L2016": "Inductor_SMD:L_Murata_DFE201610P",
    "F1206": "Fuse:Fuse_1206_3216Metric",
    "TACT": "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
    "USBC": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
    "SOCKET5": "Connector_PinSocket_2.54mm:PinSocket_1x05_P2.54mm_Vertical",
    "EC11": "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm",
    "TESTPAD": "TestPoint:TestPoint_Pad_D1.0mm",
    "FIDUCIAL": "Fiducial:Fiducial_1mm_Mask2mm",
    "HOLE_M2": "macropad:Hole_M2",
    "LED_SIDE": "macropad:SK6812-side-a",
    "MX_HOTSWAP": "macropad:MX_Hotswap",
}

HAND_SOLDERED = {"EC11", "SOCKET5"}
NOT_A_PART = {"TESTPAD", "HOLE_M2", "FIDUCIAL"}


@dataclass(frozen=True)
class Part:
    ref: str
    value: str
    footprint_key: str
    x: float
    y: float
    rotation: float = 0.0
    side: str = BOTTOM
    nets: dict[str, str] = field(default_factory=dict)

    @property
    def footprint(self) -> str:
        return FOOTPRINT[self.footprint_key]

    @property
    def lcsc(self) -> str:
        return "" if self.footprint_key in NOT_A_PART else LCSC[self.value]

    @property
    def machine_assembled(self) -> bool:
        return self.footprint_key not in HAND_SOLDERED | NOT_A_PART


# --- MCU geometry -----------------------------------------------------------------------------

MCU_X, MCU_Y = 42.0, 17.5
_PAD_ROW_OFFSET = 3.45  # QFN-60 pad centre to package centre
_PIN_PITCH = 0.4
_FIRST_PIN_OFFSET = 2.8


def mcu_pin_xy(pin: int) -> tuple[float, float]:
    """Top-view position of an MCU pad. The chip is on the bottom face, so it appears mirrored."""
    side, index = divmod(pin - 1, 15)
    along = -_FIRST_PIN_OFFSET + index * _PIN_PITCH
    if side == 0:
        return MCU_X + _PAD_ROW_OFFSET, MCU_Y + along
    if side == 1:
        return MCU_X - along, MCU_Y + _PAD_ROW_OFFSET
    if side == 2:
        return MCU_X - _PAD_ROW_OFFSET, MCU_Y - along
    return MCU_X + along, MCU_Y - _PAD_ROW_OFFSET


def _mcu_side(pin: int) -> int:
    return (pin - 1) // 15


def gpio_pin(gpio: int) -> int:
    """QFN-60 pin number of a GPIO (RP2350 datasheet, QFN-60 pinout)."""
    gpio_pins = [2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19,
                 27, 28, 29, 31, 32, 33, 34, 35, 36, 37, 40, 41, 42, 43]
    return gpio_pins[gpio]


MCU_POWER_PINS = {
    1: V3, 11: V3, 20: V3, 30: V3, 38: V3, 45: V3,   # IOVDD
    6: V1, 23: V1, 39: V1,                           # DVDD
    44: V3,                                          # ADC_AVDD
    46: "VREG_AVDD", 47: GND, 48: "VREG_LX", 49: V3, 50: V1,
    53: V3,                                          # USB_OTP_VDD
    54: V3,                                          # QSPI_IOVDD (flash is inside the RP2354A)
    61: GND,
}
MCU_FIXED_SIGNALS = {
    21: "XIN", 22: "XOUT", 24: "SWCLK", 25: "SWDIO", 26: "RUN",
    51: "USB_DM", 52: "USB_DP", 60: "QSPI_SS",
}
# One 100 nF in front of each of these supply pins: capacitor -> MCU pin.
DECOUPLING_CAPS = {"C1": 1, "C2": 6, "C3": 11, "C4": 20, "C5": 23, "C6": 30, "C7": 38, "C8": 39, "C9": 45,
                   "C10": 53}
DECOUPLED_PINS = list(DECOUPLING_CAPS.values())
# ADC_AVDD (44) and QSPI_IOVDD (54) are each tied to the 3.3 V pin beside them (45, 53) and reach that
# pin's capacitor. Their own 100 nF has no room in front of the pin, where signals leave the chip. It
# sits as near as it fits: capacitor -> MCU pin.
SECOND_SUPPLY_CAPS = {"C32": 44, "C33": 54}
# Sideways shift (x, y) of a capacitor away from the spot straight in front of its pin. Some would
# sit on a neighbour there. Pins 1 and 11 move theirs outward along the row instead, to open a fifth
# track lane for the four signal pins between two capacitors (2-5 and 7-10).
DECOUPLING_SHIFT = {1: (0.0, -0.4), 11: (0.0, 0.4), 20: (0.9, 0.0), 30: (-1.4, 0.0), 38: (0.0, 0.2),
                    39: (0.0, -0.4), 53: (1.7, 0.0)}


def key_net(index: int) -> str:
    return f"KEY{index}"


def _gpio_nets() -> dict[int, str]:
    spec = BOARD_SPEC
    nets = {gpio: key_net(i) for i, gpio in enumerate(spec["keys"]["gpio"])}
    for name, side in (("ENC_L", "left"), ("ENC_R", "right")):
        encoder = spec["encoders"][side]
        nets[encoder["gpio_a"]] = f"{name}_A"
        nets[encoder["gpio_b"]] = f"{name}_B"
        nets[encoder["gpio_sw"]] = f"{name}_SW"
    display = spec["display"]
    nets[display["gpio_sck"]] = "DISP_SCK"
    nets[display["gpio_mosi"]] = "DISP_MOSI"
    nets[display["gpio_cs"]] = "DISP_CS"
    nets[spec["leds"]["gpio_data"]] = "LED_DATA_3V3"
    return nets


def _mcu() -> Part:
    nets = {str(pin): net for pin, net in (MCU_POWER_PINS | MCU_FIXED_SIGNALS).items()}
    gpio_nets = _gpio_nets()
    assert len(gpio_nets) == 22, "two functions share a GPIO in board.toml"
    for gpio, net in gpio_nets.items():
        nets[str(gpio_pin(gpio))] = net
    return Part("U1", "RP2354A", "QFN60", MCU_X, MCU_Y, nets=nets)


# --- parts around the MCU ---------------------------------------------------------------------

_RADIAL_ROTATION = {0: 180.0, 1: 90.0, 2: 0.0, 3: 270.0}  # pad 1 toward the chip
_OUTWARD = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
# MCU pad centre to capacitor centre. Far enough for a via between the pin and the capacitor, in
# line with both, so the tracks of the neighbouring pins keep their way out.
DECOUPLING_DISTANCE = 2.0
# Along the same line: MCU pad centre to the supply via, and capacitor centre to its ground via.
SUPPLY_VIA_DISTANCE = 0.85
GROUND_VIA_DISTANCE = 1.45


def outward(pin: int) -> tuple[int, int]:
    """Unit step away from the chip, for the side this pin is on."""
    return _OUTWARD[_mcu_side(pin)]


def _decoupling_caps() -> list[Part]:
    caps = []
    for ref, pin in DECOUPLING_CAPS.items():
        pad_x, pad_y = mcu_pin_xy(pin)
        out_x, out_y = _OUTWARD[_mcu_side(pin)]
        shift_x, shift_y = DECOUPLING_SHIFT.get(pin, (0.0, 0.0))
        caps.append(Part(
            ref, "100nF", "C0402",
            pad_x + out_x * DECOUPLING_DISTANCE + shift_x, pad_y + out_y * DECOUPLING_DISTANCE + shift_y,
            rotation=_RADIAL_ROTATION[_mcu_side(pin)],
            nets={"1": MCU_POWER_PINS[pin], "2": GND},
        ))
    # C32 behind C9, on the 3.3 V plane. C33 beside C10, between the USB protection and the chip.
    caps.append(Part("C32", "100nF", "C0402", 34.65, 14.7, 0, nets={"1": V3, "2": GND}))
    caps.append(Part("C33", "100nF", "C0402", 45.2, 12.9, 180, nets={"1": V3, "2": GND}))
    return caps


CORE_TEST_PAD = "TP6"


def _core_regulator() -> list[Part]:
    """On-chip 1.1 V switching regulator, values from "Hardware design with RP2350".

    The input capacitor sits right at VREG_VIN, the inductor right at VREG_LX.
    """
    return [
        Part("C11", "4.7uF", "C0402", 40.3, 12.3, 270, nets={"1": V3, "2": GND}),
        Part("L1", "3.3uH", "L2016", 38.6, 11.9, 270, nets={"1": "VREG_LX", "2": V1}),
        Part("C12", "4.7uF", "C0402", 38.2, 9.6, 270, nets={"1": V1, "2": GND}),
        Part("C13", "4.7uF", "C0402", 39.3, 9.6, 270, nets={"1": V1, "2": GND}),
        Part("C14", "4.7uF", "C0402", 37.0, 13.7, 0, nets={"1": "VREG_AVDD", "2": GND}),
        Part("R1", "33R", "R0402", 35.0, 13.7, 0, nets={"1": "VREG_AVDD", "2": V3}),
        # Probe pad on the regulator output, beside the inductor. Routed with the output capacitors.
        Part(CORE_TEST_PAD, V1, "TESTPAD", 36.0, 11.0, nets={"1": V1}),
    ]


def _clock_and_reset() -> list[Part]:
    spec = BOARD_SPEC["buttons"]
    return [
        # The crystal sits as close below XIN/XOUT (MCU pins 21 and 22) as the two hot-swap sockets
        # allow. XIN runs down its right side to pad 1, with its load capacitor right there.
        Part("Y1", "12MHz", "XTAL3225", 41.9, 26.2, 0,
             nets={"1": "XIN", "2": GND, "3": "XTAL_DRIVE", "4": GND}),
        Part("C15", "15pF", "C0402", 44.7, 26.7, 270, nets={"1": "XIN", "2": GND}),
        Part("C16", "15pF", "C0402", 42.05, 28.9, 180, nets={"1": "XTAL_DRIVE", "2": GND}),
        Part("R2", "1k", "R0402", 40.1, 28.9, 0, nets={"1": "XOUT", "2": "XTAL_DRIVE"}),
        Part("R3", "10k", "R0402", 47.6, 22.6, 90, nets={"1": V3, "2": "RUN"}),
        Part("SW14", "TS-1187A", "TACT", spec["reset"]["x"], spec["reset"]["y"], 0,
             nets={"1": "RUN", "2": GND}),
        # Next to the BOOT button, so the long track across the board is the one behind the resistor.
        Part("R4", "1k", "R0402", 35.6, 22.3, 90, nets={"1": "QSPI_SS", "2": "BOOT"}),
        Part("SW13", "TS-1187A", "TACT", spec["boot"]["x"], spec["boot"]["y"], 0,
             nets={"1": "BOOT", "2": GND}),
        # Debug pads in a row between the first two key rows, where nothing else needs the space.
        Part("TP1", "SWCLK", "TESTPAD", 39.0, 36.5, nets={"1": "SWCLK"}),
        Part("TP2", "SWDIO", "TESTPAD", 42.0, 36.5, nets={"1": "SWDIO"}),
        Part("TP3", "GND", "TESTPAD", 45.0, 36.5, nets={"1": GND}),
    ]


def _usb_and_power() -> list[Part]:
    usb = BOARD_SPEC["usb"]
    connector_nets = {pad: GND for pad in ("A1", "A12", "B1", "B12", "S1")}
    connector_nets |= {pad: VBUS for pad in ("A4", "A9", "B4", "B9")}
    connector_nets |= {"A5": "CC1", "B5": "CC2", "A6": "USB_D_P", "B6": "USB_D_P",
                       "A7": "USB_D_N", "B7": "USB_D_N", "A8": NO_NET, "B8": NO_NET}
    receptacle_half_depth = 3.65
    return [
        Part("J1", "USB-C", "USBC", usb["x"], receptacle_half_depth - usb["mouth_overhang"], 180,
             nets=connector_nets),
        Part("R5", "5.1k", "R0402", 36.0, 6.6, 90, nets={"1": "CC1", "2": GND}),
        Part("R6", "5.1k", "R0402", 48.0, 6.6, 90, nets={"1": "CC2", "2": GND}),
        Part("U3", "USBLC6-2SC6", "SOT23-6", 46.8, 10.4, 0,
             nets={"1": "USB_D_N", "6": "USB_D_N", "3": "USB_D_P", "4": "USB_D_P", "2": GND, "5": VBUS}),
        # Each series resistor sits straight above its MCU pin (51 at x 41.2, 52 at x 41.6) or to the
        # right of it, so D- runs straight and D+ leans away from it: both stay on the bottom layer.
        Part("R7", "27R", "R0402", 41.25, 11.0, 90, nets={"1": "USB_D_N", "2": "USB_DM"}),
        Part("R8", "27R", "R0402", 42.25, 11.0, 90, nets={"1": "USB_D_P", "2": "USB_DP"}),
        Part("F1", "nSMD050", "F1206", 33.0, 3.4, 90, nets={"1": VBUS, "2": V5}),
        Part("U2", "AP2112K-3.3", "SOT23-5", 31.0, 9.4, 90,
             nets={"1": V5, "2": GND, "3": V5, "4": NO_NET, "5": V3}),
        # 5 V rail: 2.2 uF here and at each LED row, plus nine 100 nF, is 7.5 uF behind the fuse.
        # USB 2.0 allows a device 10 uF at plug-in.
        Part("C17", "2.2uF", "C0603", 29.0, 5.6, 0, nets={"1": V5, "2": GND}),
        Part("C18", "10uF", "C0603", 31.0, 12.4, 0, nets={"1": V3, "2": GND}),
        # Probe pads for bring-up, each in a free spot over its own plane: 5 V beside the debug pads,
        # 3.3 V at the left end of the 3.3 V island.
        Part("TP4", V5, "TESTPAD", 50.0, 38.5, nets={"1": V5}),
        Part("TP5", V3, "TESTPAD", 24.5, 23.0, nets={"1": V3}),
    ]


# --- inputs, display, lights ------------------------------------------------------------------

def key_centre(index: int) -> tuple[float, float]:
    keys = BOARD_SPEC["keys"]
    row, column = divmod(index, keys["columns"])
    return keys["first_x"] + column * keys["pitch"], keys["first_y"] + row * keys["pitch"]


def _keys() -> list[Part]:
    keys = BOARD_SPEC["keys"]
    count = keys["columns"] * keys["rows"]
    return [
        Part(f"SW{i + 1}", "MX hot-swap", "MX_HOTSWAP", *key_centre(i), nets={"1": key_net(i), "2": GND})
        for i in range(count)
    ]


def _encoders() -> list[Part]:
    # The footprint origin is pad A; the shaft is 7.5 mm right and 2.5 mm below it.
    shaft_dx, shaft_dy = 7.5, 2.5
    parts = []
    for ref, name, side in (("ENC1", "ENC_L", "left"), ("ENC2", "ENC_R", "right")):
        encoder = BOARD_SPEC["encoders"][side]
        parts.append(Part(
            ref, BOARD_SPEC["encoders"]["part"], "EC11", encoder["x"] - shaft_dx, encoder["y"] - shaft_dy,
            side=TOP,
            nets={"A": f"{name}_A", "B": f"{name}_B", "C": GND, "S1": f"{name}_SW", "S2": GND, "MP": GND},
        ))
    return parts


def _display() -> list[Part]:
    display = BOARD_SPEC["display"]
    signal_net = {"MOSI": "DISP_MOSI", "SCK": "DISP_SCK", "3V3": V3, "GND": GND, "CS": "DISP_CS"}
    pins = display["header_pins"]
    first_pin_y = display["y"] - display["header_pitch"] * (len(pins) - 1) / 2
    return [
        Part("J2", "1x5 socket", "SOCKET5", display["header_x"], first_pin_y, side=TOP,
             nets={str(n): signal_net[name] for n, name in enumerate(pins, start=1)}),
        Part("C19", "1uF", "C0402", 27.6, 14.6, 90, nets={"1": V3, "2": GND}),
    ]


def _leds() -> list[Part]:
    leds = BOARD_SPEC["leds"]
    width = BOARD_SPEC["board"]["width"]
    right = [(width - leds["inset"], y, 90.0) for y in leds["right_y"]]
    left = [(leds["inset"], y, 270.0) for y in leds["left_y"]]
    chain = right + left
    parts = [
        Part("U4", "74LVC1T45", "SOT23-6", 55.2, 8.4, 0,
             nets={"1": V3, "2": GND, "3": "LED_DATA_3V3", "4": "LED_D0", "5": V3, "6": V5}),
        Part("C20", "100nF", "C0402", 52.4, 8.4, 90, nets={"1": V3, "2": GND}),
        Part("C21", "100nF", "C0402", 58.0, 8.4, 90, nets={"1": V5, "2": GND}),
        Part("C22", "2.2uF", "C0603", 79.6, 23.4, 0, nets={"1": V5, "2": GND}),
        Part("C23", "2.2uF", "C0603", 4.4, 23.4, 0, nets={"1": V5, "2": GND}),
    ]
    for i, (x, y, rotation) in enumerate(chain):
        is_last = i == len(chain) - 1
        parts.append(Part(
            f"LED{i + 1}", "SK6812SIDE-A", "LED_SIDE", x, y, rotation,
            nets={"1": f"LED_D{i}", "2": V5, "3": NO_NET if is_last else f"LED_D{i + 1}", "4": GND},
        ))
        inboard = 3.4 if x < width / 2 else -3.4
        parts.append(Part(f"C{24 + i}", "100nF", "C0402", x + inboard, y, 90, nets={"1": V5, "2": GND}))
    return parts


def _mounting_holes() -> list[Part]:
    return [
        Part(f"H{i}", "M2", "HOLE_M2", x, y, side=TOP)
        for i, (x, y) in enumerate(BOARD_SPEC["mounting"]["holes"], start=1)
    ]


# Three optical marks for the pick-and-place camera, on the assembly face, in three corners so the
# board cannot be read upside down. 4 mm in from the edge, clear of the conveyor rails.
FIDUCIALS = [(7.5, 4.0), (76.5, 4.0), (7.5, 78.5)]
FIDUCIAL_MASK_DIAMETER = 2.0


def _fiducials() -> list[Part]:
    return [Part(f"FID{i}", "fiducial", "FIDUCIAL", x, y) for i, (x, y) in enumerate(FIDUCIALS, start=1)]


def all_parts() -> list[Part]:
    parts = (
        [_mcu()] + _decoupling_caps() + _core_regulator() + _clock_and_reset() + _usb_and_power()
        + _keys() + _encoders() + _display() + _leds() + _mounting_holes() + _fiducials()
    )
    refs = [part.ref for part in parts]
    assert len(refs) == len(set(refs)), "duplicate reference designator"
    return parts


def nets_to_pads(parts: list[Part]) -> dict[str, list[str]]:
    connections: dict[str, list[str]] = {}
    for part in parts:
        for pad, net in part.nets.items():
            if net != NO_NET:
                connections.setdefault(net, []).append(f"{part.ref}.{pad}")
    return connections


def check_netlist(parts: list[Part]) -> None:
    """Every signal net needs at least two pads; a single-pad net is a wiring mistake."""
    dangling = sorted(net for net, pads in nets_to_pads(parts).items() if len(pads) < 2)
    assert not dangling, f"nets with a single pad: {dangling}"


if __name__ == "__main__":
    circuit = all_parts()
    check_netlist(circuit)
    for net_name, pad_names in sorted(nets_to_pads(circuit).items()):
        print(f"{net_name:14} {' '.join(pad_names)}")
