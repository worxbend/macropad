"""Where everything sits on the schematic sheet. Data only; schematic.py draws it.

Units are grid steps of 1.27 mm. Inside a block, positions count from the block's top-left corner,
X to the right and Y down. A point is either a pin ("R7.1") or a position (x, y).

What is not listed here is drawn by rule (see schematic.py): a pin on a supply net gets a short
wire and the supply symbol, a pin on a signal net gets a short wire and the net's label, an open
pin gets a no-connect mark.
"""

from __future__ import annotations

from dataclasses import dataclass

import circuit
from circuit import GND, V1, V3, V5, VBUS


@dataclass(frozen=True)
class Place:
    ref: str
    x: int
    y: int
    rotation: int = 0  # degrees counter-clockwise


@dataclass(frozen=True)
class Wire:
    """A chain of straight wires through the points. Every pin on it must be on this net in circuit.py."""
    net: str
    points: tuple
    label: tuple | None = None  # (x, y) on the wire, text to the right; (x, y, "left") for text to the left


@dataclass(frozen=True)
class Rail:
    """A supply symbol at this point."""
    net: str
    point: tuple[int, int]


@dataclass(frozen=True)
class Flag:
    """KiCad's PWR_FLAG: tells the rule check that this net is driven from outside the sheet's symbols
    (through the fuse, an inductor or a resistor)."""
    point: tuple[int, int]


@dataclass(frozen=True)
class Note:
    text: str
    x: int
    y: int


@dataclass(frozen=True)
class Block:
    title: str
    x: int
    y: int
    width: int
    height: int
    places: tuple[Place, ...]
    wires: tuple[Wire, ...] = ()
    rails: tuple[Rail, ...] = ()
    flags: tuple[Flag, ...] = ()
    notes: tuple[Note, ...] = ()


PAPER = "A3"
SHEET_WIDTH, SHEET_HEIGHT = 330, 233  # A3 landscape in grid steps

_USB = Block(
    "USB-C input, ESD protection, fuse", 6, 10, 72, 56,
    places=(Place("J1", 12, 24), Place("F1", 42, 12, 90), Place("R6", 58, 21), Place("R5", 66, 19),
            Place("R7", 43, 22, 90), Place("R8", 43, 26, 90), Place("U3", 48, 40)),
    wires=(
        Wire(VBUS, ("J1.A4", (27, 12), (34, 12), "F1.1")),
        Wire(V5, ("F1.2", (54, 12))),
        Wire("CC1", ("J1.A5", "R5.1"), label=(25, 16)),
        Wire("CC2", ("J1.B5", "R6.1"), label=(25, 18)),
        Wire("USB_D_N", ("J1.A7", (28, 22), "R7.1"), label=(31, 22)),
        Wire("USB_D_N", ("J1.B7", (28, 24), (28, 22))),
        Wire("USB_D_P", ("J1.A6", (30, 26), "R8.1"), label=(31, 26)),
        Wire("USB_D_P", ("J1.B6", (30, 28), (30, 26))),
    ),
    rails=(Rail(VBUS, (27, 12)), Rail(V5, (54, 12))),
    flags=(Flag((34, 12)),),
    notes=(Note("5.1 k on each CC line: the host sees a device and switches 5 V on.", 2, 53),),
)

_REGULATOR_3V3 = Block(
    "3.3 V regulator", 6, 70, 72, 28,
    places=(Place("U2", 22, 12), Place("C17", 8, 13), Place("C18", 34, 13), Place("TP5", 46, 10),
            Place("TP4", 68, 10)),
    wires=(
        Wire(V5, ((3, 10), "C17.1", (14, 10), "U2.1")),
        Wire(V5, ("U2.3", (14, 12), (14, 10))),
        Wire(V3, ("U2.5", "C18.1", (40, 10), "TP5.1")),
        Wire(V5, ((52, 10), (60, 10), "TP4.1")),
    ),
    rails=(Rail(V5, (3, 10)), Rail(V3, (40, 10)), Rail(V5, (52, 10)), Rail(GND, (56, 20))),
    flags=(Flag((60, 10)), Flag((56, 20))),
    notes=(Note("TP4, TP5: probe pads.", 44, 26),),
)

_MCU_X, _MCU_Y = 34, 54
_MCU = Block(
    "MCU: RP2354A (RP2350 with 2 MB flash inside)", 82, 10, 72, 101,
    places=(Place("U1", _MCU_X, _MCU_Y),),
    wires=(
        Wire(V3, ("U1.53", (24, 16), (26, 16), (30, 16), (32, 16), (36, 16), "U1.49")),
        Wire(V3, ("U1.44", (26, 16))),
        Wire(V3, ("U1.54", (30, 16))),
        Wire(V3, ("U1.1", (32, 16))),
        Wire(V1, ("U1.50", (40, 16), (42, 16), (44, 16), "U1.6")),
        Wire(GND, ("U1.47", (32, 92), (34, 92), "U1.61")),
    ),
    rails=(Rail(V3, (30, 16)), Rail(V1, (42, 16)), Rail(GND, (34, 92))),
    notes=(Note("QSPI_SCLK, QSPI_SD0-3: the flash is inside the package. Leave open.", 2, 99),),
)

_DECOUPLING_PITCH = 7
_DECOUPLING_PINS = circuit.DECOUPLING_CAPS | circuit.SECOND_SUPPLY_CAPS
_DECOUPLING = Block(
    "MCU decoupling: 100 nF for each supply pin, 4.7 uF at pin 23", 82, 114, 88, 30,
    places=tuple(Place(ref, 6 + _DECOUPLING_PITCH * n, 14) for n, ref in enumerate(_DECOUPLING_PINS)),
    notes=tuple(Note(f"pin {pin}", 4 + _DECOUPLING_PITCH * n, 27) for n, pin in enumerate(_DECOUPLING_PINS.values())),
)

_CORE_REGULATOR = Block(
    "1.1 V core supply: the switching regulator inside U1", 6, 134, 72, 52,
    places=(Place("L1", 16, 12, 270), Place("C12", 24, 15), Place("C13", 30, 15), Place("TP6", 52, 12),
            Place("R1", 16, 32, 270), Place("C14", 24, 35), Place("C11", 50, 35)),
    wires=(
        Wire(V1, ("L1.1", "C12.1", "C13.1", (36, 12), (44, 12), "TP6.1")),
        Wire(V3, ((8, 32), "R1.2")),
        Wire("VREG_AVDD", ("R1.1", "C14.1", (36, 32)), label=(26, 32)),
    ),
    rails=(Rail(V1, (36, 12)), Rail(V3, (8, 32))),
    flags=(Flag((44, 12)), Flag((36, 32))),
    notes=(Note("C11: at VREG_VIN (pin 49)", 44, 24),
           Note("C13: do not populate. COUT (C12) is the one 4.7 uF.", 2, 46),
           Note("L1: dot on pad 1, the +1V1 end. Not verified on a part.", 2, 50)),
)

_CLOCK = Block(
    "12 MHz crystal", 6, 102, 72, 28,
    places=(Place("Y1", 22, 12), Place("C15", 13, 15), Place("C16", 31, 15), Place("R2", 39, 12, 270)),
    wires=(
        Wire("XIN", ((5, 12), "C15.1", "Y1.1"), label=(5, 12)),
        Wire("XTAL_DRIVE", ("Y1.3", "C16.1", "R2.2"), label=(26, 12)),
    ),
    notes=(Note("Load capacitors are a guess until measured.", 2, 26),),
)

_RESET_BOOT_DEBUG = Block(
    "Reset, boot select, debug pads", 82, 147, 100, 30,
    places=(Place("R3", 12, 15), Place("SW14", 22, 22), Place("R4", 45, 22, 90), Place("SW13", 58, 22),
            Place("TP1", 76, 14), Place("TP2", 84, 14), Place("TP3", 92, 14)),
    wires=(
        Wire("RUN", ((5, 22), (12, 22), "SW14.1"), label=(5, 22)),
        Wire("RUN", ("R3.2", (12, 22))),
        Wire("BOOT", ("R4.2", "SW13.1"), label=(49, 22)),
    ),
    notes=(Note("Hold BOOT while plugging in: USB drive for the UF2 file.", 34, 28),),
)

_KEY_COLUMNS = circuit.BOARD_SPEC["keys"]["columns"]
_KEYS = Block(
    "Keys: one GPIO each, switch to ground, pull-ups inside U1", 158, 10, 108, 46,
    places=tuple(Place(f"SW{i + 1}", 16 + 26 * (i % _KEY_COLUMNS), 14 + 12 * (i // _KEY_COLUMNS))
                 for i in range(len(circuit.BOARD_SPEC["keys"]["gpio"]))),
)

# The four pull-ups in a row under the encoders: x of each resistor, and of its +3V3 symbol a little to the right,
# clear of the value text.
_PULL_UP_X = {ref: 16 + 22 * n for n, ref in enumerate(circuit.ENCODER_PULL_UPS)}
_PULL_UP_Y = 29
_ENCODERS = Block(
    "Rotary encoders with push switch, 3.3 k pull-ups on A and B", 158, 60, 92, 38,
    places=(Place("ENC1", 26, 14), Place("ENC2", 72, 14))
    + tuple(Place(ref, x, _PULL_UP_Y, 90) for ref, x in _PULL_UP_X.items()),
    wires=(Wire(GND, ("ENC1.C", (8, 14))), Wire(GND, ("ENC2.C", (54, 14))))
    + tuple(Wire(V3, (f"{ref}.2", (x + 6, _PULL_UP_Y))) for ref, x in _PULL_UP_X.items()),
    rails=(Rail(GND, (8, 14)), Rail(GND, (54, 14)))
    + tuple(Rail(V3, (x + 6, _PULL_UP_Y)) for x in _PULL_UP_X.values()),
    notes=(Note("Pull-ups: 1 mA through each contact, the minimum Alps gives. SW keeps U1's own pull-up.", 2, 36),),
)

_DISPLAY = Block(
    "Display socket for the nice!view module", 6, 188, 72, 26,
    places=(Place("J2", 10, 14), Place("C19", 54, 15)),
    wires=(Wire(V3, ("J2.3", (34, 14))), Wire(GND, ("J2.4", (42, 16)))),
    rails=(Rail(V3, (34, 14)), Rail(GND, (42, 16))),
)

_LEVEL_SHIFTER = Block(
    "LED data: 3.3 V to 5 V", 254, 60, 68, 36,
    places=(Place("U4", 26, 22), Place("C20", 50, 20), Place("C21", 58, 20), Place("R9", 46, 30, 90)),
    wires=(
        Wire(V3, ("U4.1", (24, 12), (14, 12), (14, 26), "U4.5")),
        Wire(V5, ("U4.6", (28, 12), (32, 12))),
        Wire("LED_DATA_3V3", ("U4.3", (12, 22)), label=(12, 22, "left")),
    ),
    rails=(Rail(V3, (24, 12)), Rail(V5, (32, 12))),
    notes=(Note("DIR high: A drives B.", 2, 34),),
)

_LED_PITCH = 24
_LED_ROWS = ((1, 18, "LED1-4: right side of the board, back to front."),
             (5, 56, "LED5-8: left side of the board, front to back."))


def _led_row(first: int, y: int) -> tuple[list[Place], list[Wire]]:
    places, wires = [], []
    for column in range(4):
        number = first + column
        x = 16 + _LED_PITCH * column
        places.append(Place(f"LED{number}", x, y))
        places.append(Place(f"C{23 + number}", x + 14, y + 14))
        if column < 3:
            wires.append(Wire(f"LED_D{number}", (f"LED{number}.3", f"LED{number + 1}.1"), label=(x + 9, y)))
    return places, wires


def _leds() -> Block:
    places, wires, notes = [Place("C22", 112, 32), Place("C23", 112, 70)], [], []
    for first, y, text in _LED_ROWS:
        row_places, row_wires = _led_row(first, y)
        places += row_places
        wires += row_wires
        notes.append(Note(text, 4, y + 25))
    return Block("LED chain: 8 side-emitting SK6812, one 100 nF each", 188, 100, 120, 86,
                 tuple(places), tuple(wires), notes=tuple(notes))


_MECHANICAL_REFS = [f"H{n}" for n in range(1, 7)] + [f"FID{n}" for n in range(1, 4)]
_MECHANICAL = Block(
    "Mounting holes (M2), case ground at H1, fiducials", 82, 181, 100, 22,
    places=tuple(Place(ref, 8 + 10 * n, 12) for n, ref in enumerate(_MECHANICAL_REFS)),
)

BLOCKS = (_USB, _REGULATOR_3V3, _CLOCK, _CORE_REGULATOR, _DISPLAY, _MCU, _DECOUPLING, _RESET_BOOT_DEBUG,
          _MECHANICAL, _KEYS, _ENCODERS, _LEVEL_SHIFTER, _leds())
