"""Writes the KiCad schematic from circuit.py. Pure Python, but it reads KiCad's symbol libraries.

The schematic is a drawing of the netlist, not a second source of truth. Parts use KiCad's own
library symbols, so their pin numbers, pin names and pin types come from a maintained library and
not from this repository. sheet_layout.py says where each part sits and which wires are drawn;
every other pin gets its supply symbol or its net label by rule. build.py then lets KiCad export
the netlist of the result and compares it with circuit.py pin by pin.

Sheet positions are grid steps of 1.27 mm, Y down.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import circuit
import sexpr
import sheet_layout
from circuit import GND, NO_NET, V1, V3, V5, VBUS, Part
from sheet_layout import Block, Place
from symlib import GRID, BoxPin, LibPin, LibSymbol, SymbolLibrary, box_symbol

KICAD_SYMBOLS = Path("/usr/share/kicad/symbols")
STUB = 2  # grid steps of wire between a pin and its label or supply symbol
_UUID_NAMESPACE = uuid.UUID("6f1c2b0e-7d5a-4c1e-9b7e-3a2f0c9d4e11")
_POWER_SYMBOL = {GND: "power:GND", V3: "power:+3V3", V5: "power:+5V", V1: "power:+1V1", VBUS: "power:VBUS"}
_FLAG_SYMBOL = "power:PWR_FLAG"



def board_net_name(net: str) -> str:
    """The name KiCad gives this net on the board: a supply symbol names its net as it is, a label on
    the root sheet gets a leading slash. With the same names the board can be checked against the schematic."""
    return net if net in _POWER_SYMBOL else "/" + net


OPEN_PIN_NET_PREFIX = "unconnected-"  # KiCad's netlist names the net of every open pin like this


def circuit_net_name(board_net: str) -> str:
    return NO_NET if board_net.startswith(OPEN_PIN_NET_PREFIX) else board_net.removeprefix("/")


# KiCad library symbol per footprint. A part value can name a more exact symbol.
_SYMBOL_BY_FOOTPRINT = {
    "C0402": "Device:C", "C0402W": "Device:C", "C0603": "Device:C", "R0402": "Device:R", "L2016": "Device:L", "F1206": "Device:Polyfuse",
    "XTAL3225": "Device:Crystal_GND24", "TACT": "Switch:SW_Push", "MX_HOTSWAP": "Switch:SW_Push",
    "USBC": "Connector:USB_C_Receptacle_USB2.0_16P", "EC11": "Device:RotaryEncoder_Switch_MP",
    "TESTPAD": "Connector:TestPoint", "HOLE_M2": "Mechanical:MountingHole", "FIDUCIAL": "Mechanical:Fiducial",
}
_SYMBOL_BY_VALUE = {
    "RP2354A": "MCU_RaspberryPi:RP2354A", "AP2112K-3.3": "Regulator_Linear:AP2112K-3.3",
    "USBLC6-2SC6": "Power_Protection:USBLC6-2SC6", "74LVC1T45": "Logic_LevelTranslator:SN74LVC1T45DBV",
}
# The RP2354A's flash is inside the package, on these pins. Nothing may be connected outside.
MCU_INTERNAL_FLASH_PINS = ("QSPI_SD3", "QSPI_SCLK", "QSPI_SD0", "QSPI_SD2", "QSPI_SD1")
# Where the library's default text position runs into a pin or a wire of this sheet: (x, y) grid steps.
_VALUE_OFFSET = {"Device:RotaryEncoder_Switch_MP": (-8, 5), "Switch:SW_Push": (-1, 2.2)}


def _led_symbol() -> LibSymbol:
    """SK6812 SIDE-A. Pin order from the footprint in pcb/lib (MEASURE: check against the part)."""
    return box_symbol("macropad:SK6812_SIDE-A", "SK6812SIDE-A", (6, 4), (
        BoxPin("1", "DIN", "input", "left", 0), BoxPin("2", "VDD", "power_in", "top", 0),
        BoxPin("3", "DOUT", "output", "right", 0), BoxPin("4", "GND", "power_in", "bottom", 0)))


def _display_socket_symbol() -> LibSymbol:
    names = circuit.BOARD_SPEC["display"]["header_pins"]
    pins = tuple(BoxPin(str(n), name, "passive", "right", 2 * (n - 1) - (len(names) - 1))
                 for n, name in enumerate(names, start=1))
    return box_symbol("macropad:nice_view_socket", "1x5 socket", (5, 6), pins)


_PROJECT_SYMBOLS = {"LED_SIDE": _led_symbol, "SOCKET5": _display_socket_symbol}


def symbol_for(part: Part, library: SymbolLibrary) -> LibSymbol:
    if part.footprint_key in _PROJECT_SYMBOLS:
        return _PROJECT_SYMBOLS[part.footprint_key]()
    return library.get(_SYMBOL_BY_VALUE.get(part.value) or _SYMBOL_BY_FOOTPRINT[part.footprint_key])


def check_part_against_symbol(part: Part, symbol: LibSymbol) -> None:
    """circuit.py may only name pins the symbol has, and must use the footprint the symbol was drawn for."""
    unknown = set(part.nets) - {pin.number for pin in symbol.pins}
    assert not unknown, f"{part.ref}: {symbol.lib_id} has no pins {sorted(unknown)}"
    library_footprint = symbol.property_value("Footprint")
    assert library_footprint in ("", part.footprint), (
        f"{part.ref}: {symbol.lib_id} is drawn for {library_footprint}, circuit.py uses {part.footprint}")


def _plain_pin_name(name: str) -> str:
    """"~{QSPI_SS}" -> "QSPI_SS", "GPIO26/ADC0" -> "GPIO26"."""
    return name.replace("~{", "").replace("}", "").split("/")[0]


def check_mcu_pins(part: Part, symbol: LibSymbol) -> None:
    """circuit.py's pin numbers against the pin names of KiCad's RP2354A symbol."""
    name_of = {int(pin.number): _plain_pin_name(pin.name) for pin in symbol.pins}
    assert len(name_of) == 61, f"{symbol.lib_id} has {len(name_of)} pins, a QFN-60 with exposed pad has 61"
    for gpio in range(30):
        pin = circuit.gpio_pin(gpio)
        assert name_of[pin] == f"GPIO{gpio}", f"GPIO{gpio} is not on pin {pin}"
    expected_supply = {"IOVDD": V3, "ADC_AVDD": V3, "USB_OTP_VDD": V3, "QSPI_IOVDD": V3, "VREG_VIN": V3,
                       "DVDD": V1, "VREG_FB": V1, "VREG_PGND": GND, "GND": GND}
    own_net = ("XIN", "XOUT", "SWCLK", "SWDIO", "RUN", "USB_DM", "USB_DP", "QSPI_SS", "VREG_LX", "VREG_AVDD")
    for number, name in sorted(name_of.items()):
        net = part.nets.get(str(number), NO_NET)
        if name in expected_supply:
            assert net == expected_supply[name], f"U1 pin {number} ({name}) is on {net or 'nothing'}"
        if name in own_net:
            assert net == name, f"U1 pin {number} ({name}) is on {net or 'nothing'}"
        if name in MCU_INTERNAL_FLASH_PINS:
            assert net == NO_NET, f"U1 pin {number} ({name}) belongs to the flash inside the package"


# --- small s-expression helpers ---------------------------------------------------------------

def _uuid(key: str) -> str:
    return str(uuid.uuid5(_UUID_NAMESPACE, key))


def symbol_uuid(ref: str) -> str:
    """The schematic symbol's id. layout.py gives the footprint the same one, so KiCad can pair them."""
    return _uuid(ref)


ROOT_UUID = _uuid("root")


def _mm(steps: float) -> str:
    return f"{steps * GRID:.4f}".rstrip("0").rstrip(".")


def _at(point: tuple[float, float], angle: int = 0) -> str:
    return f"(at {_mm(point[0])} {_mm(point[1])} {angle})"


_FONT = "(effects (font (size 1.27 1.27)))"
_HIDDEN = "(effects (font (size 1.27 1.27)) (hide yes))"


# --- one block --------------------------------------------------------------------------------

@dataclass(frozen=True)
class PlacedPin:
    name: str                 # "R7.1"
    net: str
    point: tuple[int, int]    # on the sheet
    outward: tuple[int, int]
    pin: LibPin


@dataclass
class Drawing:
    """What has been drawn so far: KiCad items as text, and the wire ends for the junction dots."""
    items: list[str] = field(default_factory=list)
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = field(default_factory=list)
    net_at: dict[tuple[int, int], str] = field(default_factory=dict)  # every connection point and its net
    pin_points: list[tuple[int, int]] = field(default_factory=list)
    power_count: int = 0
    lib_symbols: dict[str, LibSymbol] = field(default_factory=dict)

    def claim(self, point: tuple[int, int], net: str) -> None:
        other = self.net_at.setdefault(point, net)
        assert other == net, f"{net} and {other} meet at {point}"

    def wire(self, net: str, start: tuple[int, int], end: tuple[int, int]) -> None:
        assert start != end and (start[0] == end[0] or start[1] == end[1]), f"{net}: wire {start} to {end} is not straight"
        self.claim(start, net)
        self.claim(end, net)
        self.segments.append((start, end))

    def label(self, net: str, point: tuple[int, int], direction: tuple[int, int]) -> None:
        angle, justify = {(1, 0): (0, "left"), (-1, 0): (180, "right"), (0, -1): (90, "left"),
                          (0, 1): (270, "right")}[direction]
        self.claim(point, net)
        self.items.append(
            f'(label "{net}" {_at(point, angle)} (effects (font (size 1.27 1.27)) (justify {justify} bottom)) '
            f'(uuid "{_uuid(f"label/{net}/{point}")}"))')

    def power(self, lib_symbol: LibSymbol, net: str, point: tuple[int, int]) -> None:
        """A supply symbol or a power flag with its one pin at the point."""
        self.power_count += 1
        self.lib_symbols[lib_symbol.lib_id] = lib_symbol
        self.claim(point, net)
        self.pin_points.append(point)
        is_flag = lib_symbol.lib_id == _FLAG_SYMBOL
        ref = f"#FLG{self.power_count:03}" if is_flag else f"#PWR{self.power_count:03}"
        value_x, value_y, _, value_style = lib_symbol.property_at("Value")
        value_at = (point[0] + value_x / GRID, point[1] + value_y / GRID)
        self.items.append("\n".join([
            f'(symbol (lib_id "{lib_symbol.lib_id}") {_at(point)} (unit 1) (exclude_from_sim no) (in_bom yes) '
            f'(on_board yes) (dnp no) (uuid "{_uuid(ref)}")',
            f'(property "Reference" "{ref}" {_at(point)} {_HIDDEN})',
            f'(property "Value" "{lib_symbol.name}" {_at(value_at)} {sexpr.dump(value_style)})',
            f'(property "Footprint" "" {_at(point)} {_HIDDEN})',
            f'(property "Datasheet" "" {_at(point)} {_HIDDEN})',
            f'(property "Description" "" {_at(point)} {_HIDDEN})',
            f'(pin "1" (uuid "{_uuid(ref + "/1")}"))',
            f'(instances (project "macropad" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1)))))',
        ]))


def _field_positions(place: Place, symbol: LibSymbol, origin: tuple[int, int]) -> dict[str, str]:
    """Reference and Value: the library's own spots, or on one line above a part that lies on its side."""
    if place.rotation in (90, 270):
        # A text field turns with its symbol, so 90 here reads horizontally on the sheet.
        # A quarter turn one way also swaps what KiCad calls left and right.
        before, after = ("left", "right") if place.rotation == 90 else ("right", "left")
        line_y = origin[1] - 1.8
        style = "(effects (font (size 1.27 1.27)) (justify {}))"
        return {"Reference": f"{_at((origin[0] - 0.5, line_y), 90)} {style.format(before)}",
                "Value": f"{_at((origin[0] + 0.5, line_y), 90)} {style.format(after)}"}
    assert place.rotation == 0, f"{place.ref}: only two-pin parts are drawn turned"
    positions = {}
    for name in ("Reference", "Value"):
        x, y, angle, style = symbol.property_at(name)
        if name == "Value" and symbol.lib_id in _VALUE_OFFSET:
            x, y = (step * GRID for step in _VALUE_OFFSET[symbol.lib_id])
        positions[name] = f"{_at((origin[0] + x / GRID, origin[1] + y / GRID), angle)} {sexpr.dump(style)}"
    return positions


def _place_part(drawing: Drawing, part: Part, symbol: LibSymbol, place: Place, origin: tuple[int, int]) -> list[PlacedPin]:
    drawing.lib_symbols[symbol.lib_id] = symbol
    fields = _field_positions(place, symbol, origin)
    in_bom = "yes" if part.lcsc else "no"
    lines = [
        f'(symbol (lib_id "{symbol.lib_id}") {_at(origin, place.rotation)} (unit 1) (exclude_from_sim no) '
        f'(in_bom {in_bom}) (on_board yes) (dnp no) (uuid "{symbol_uuid(part.ref)}")',
        f'(property "Reference" "{part.ref}" {fields["Reference"]})',
        f'(property "Value" "{part.value}" {fields["Value"]})',
        f'(property "Footprint" "{part.footprint}" {_at(origin)} {_HIDDEN})',
        f'(property "Datasheet" "" {_at(origin)} {_HIDDEN})',
        f'(property "Description" "" {_at(origin)} {_HIDDEN})',
        f'(property "LCSC" "{part.lcsc}" {_at(origin)} {_HIDDEN})',
    ]
    lines += [f'(pin "{pin.number}" (uuid "{_uuid(f"{part.ref}/{pin.number}")}"))' for pin in symbol.pins]
    lines.append(f'(instances (project "macropad" (path "/{ROOT_UUID}" (reference "{part.ref}") (unit 1)))))')
    drawing.items.append("\n".join(lines))
    placed = []
    for pin in symbol.pins:
        dx, dy = pin.at(place.rotation)
        placed.append(PlacedPin(f"{part.ref}.{pin.number}", part.nets.get(pin.number, NO_NET),
                                (origin[0] + dx, origin[1] + dy), pin.outward(place.rotation), pin))
    return placed


def _draw_wires(drawing: Drawing, block: Block, pins: dict[str, PlacedPin]) -> set[tuple[int, int]]:
    """The wires sheet_layout.py lists. Returns the points they connect."""
    def resolve(wire_net: str, point) -> tuple[int, int]:
        if isinstance(point, str):
            assert pins[point].net == wire_net, f"{point} is on {pins[point].net}, the drawn wire says {wire_net}"
            return pins[point].point
        return block.x + point[0], block.y + point[1]

    wired = set()
    for wire in block.wires:
        points = [resolve(wire.net, point) for point in wire.points]
        for start, end in zip(points, points[1:]):
            drawing.wire(wire.net, start, end)
        wired.update(points)
        if wire.label is not None:
            x, y, *side = wire.label
            drawing.label(wire.net, (block.x + x, block.y + y), (-1, 0) if side == ["left"] else (1, 0))
    return wired


def _connect_by_rule(drawing: Drawing, library: SymbolLibrary, placed: list[PlacedPin], wired: set) -> None:
    """Every pin position no drawn wire reaches: supply symbol, net label or no-connect mark."""
    by_point: dict[tuple[int, int], list[PlacedPin]] = {}
    for pin in placed:
        by_point.setdefault(pin.point, []).append(pin)
    for point, stacked in by_point.items():
        nets = {pin.net for pin in stacked}
        assert len(nets) == 1, f"{[pin.name for pin in stacked]} share one spot on the symbol but not one net"
        net, first = nets.pop(), stacked[0]
        drawing.pin_points.append(point)
        if net == NO_NET:
            if first.pin.kind != "no_connect":
                drawing.items.append(f'(no_connect (at {_mm(point[0])} {_mm(point[1])}) (uuid "{_uuid(first.name + "/nc")}"))')
            continue
        drawing.claim(point, net)
        if point in wired:
            continue
        end = (point[0] + first.outward[0] * STUB, point[1] + first.outward[1] * STUB)
        drawing.wire(net, point, end)
        if net in _POWER_SYMBOL:
            drawing.power(library.get(_POWER_SYMBOL[net]), net, end)
        else:
            drawing.label(net, end, first.outward)


def _draw_block(drawing: Drawing, block: Block, parts: dict[str, Part], library: SymbolLibrary) -> None:
    placed: list[PlacedPin] = []
    for place in block.places:
        part = parts[place.ref]
        symbol = symbol_for(part, library)
        check_part_against_symbol(part, symbol)
        placed += _place_part(drawing, part, symbol, place, (block.x + place.x, block.y + place.y))
    wired = _draw_wires(drawing, block, {pin.name: pin for pin in placed})
    for rail in block.rails:
        drawing.power(library.get(_POWER_SYMBOL[rail.net]), rail.net, (block.x + rail.point[0], block.y + rail.point[1]))
    for flag in block.flags:
        point = (block.x + flag.point[0], block.y + flag.point[1])
        assert point in drawing.net_at, f"{block.title}: power flag at {flag.point} touches nothing"
        drawing.power(library.get(_FLAG_SYMBOL), drawing.net_at[point], point)
    _connect_by_rule(drawing, library, placed, wired)
    drawing.items.append(_text(block.title, block.x + 1, block.y + 3, 2.0, bold=True))
    drawing.items += [_text(note.text, block.x + note.x, block.y + note.y, 1.27) for note in block.notes]
    drawing.items.append(
        f'(rectangle (start {_mm(block.x)} {_mm(block.y)}) (end {_mm(block.x + block.width)} {_mm(block.y + block.height)}) '
        f'(stroke (width 0.15) (type dash)) (fill (type none)) (uuid "{_uuid("frame/" + block.title)}"))')


def _text(text: str, x: float, y: float, size: float, bold: bool = False) -> str:
    weight = " (bold yes)" if bold else ""
    return (f'(text "{text}" (exclude_from_sim no) {_at((x, y))} '
            f'(effects (font (size {size} {size}){weight}) (justify left bottom)) (uuid "{_uuid("text/" + text)}"))')


# --- wires: split where another wire or a pin ends on them, dot where three meet --------------

def _strictly_inside(point: tuple[int, int], start: tuple[int, int], end: tuple[int, int]) -> bool:
    (x, y), (x1, y1), (x2, y2) = point, start, end
    if x1 == x2 == x:
        return min(y1, y2) < y < max(y1, y2)
    if y1 == y2 == y:
        return min(x1, x2) < x < max(x1, x2)
    return False


def split_segments(segments: list, ends: set) -> list:
    """Cuts every wire at each point where something ends on it. KiCad joins wires at their ends."""
    pieces = []
    for start, end in segments:
        cuts = sorted(point for point in ends if _strictly_inside(point, start, end))
        if start > end:
            cuts.reverse()
        chain = [start, *cuts, end]
        pieces += list(zip(chain, chain[1:]))
    return pieces


def junctions(pieces: list, pin_points: list) -> list:
    """Points where three or more wire ends and pins meet."""
    count: dict[tuple[int, int], int] = {}
    for point in [end for piece in pieces for end in piece] + list(pin_points):
        count[point] = count.get(point, 0) + 1
    return sorted(point for point, meeting in count.items() if meeting >= 3)


def _wire_items(drawing: Drawing) -> list[str]:
    ends = {end for segment in drawing.segments for end in segment} | set(drawing.pin_points)
    pieces = split_segments(drawing.segments, ends)
    items = [
        f'(wire (pts (xy {_mm(start[0])} {_mm(start[1])}) (xy {_mm(end[0])} {_mm(end[1])})) '
        f'(stroke (width 0) (type default)) (uuid "{_uuid(f"wire/{start}/{end}")}"))'
        for start, end in pieces]
    items += [f'(junction (at {_mm(x)} {_mm(y)}) (diameter 0) (color 0 0 0 0) (uuid "{_uuid(f"junction/{x}/{y}")}"))'
              for x, y in junctions(pieces, drawing.pin_points)]
    return items


# --- the sheet --------------------------------------------------------------------------------

def _draw_sheet(library: SymbolLibrary) -> Drawing:
    parts = {part.ref: part for part in circuit.all_parts()}
    circuit.check_netlist(list(parts.values()))
    check_mcu_pins(parts["U1"], symbol_for(parts["U1"], library))
    drawn = [place.ref for block in sheet_layout.BLOCKS for place in block.places]
    assert sorted(drawn) == sorted(parts), f"parts not in exactly one block: {set(drawn) ^ set(parts)}"
    drawing = Drawing()
    for block in sheet_layout.BLOCKS:
        assert block.x + block.width <= sheet_layout.SHEET_WIDTH and block.y + block.height <= sheet_layout.SHEET_HEIGHT, (
            f"{block.title} runs off the sheet")
        _draw_block(drawing, block, parts, library)
    return drawing


def render(drawing: Drawing) -> str:
    lines = [
        f'(kicad_sch (version 20250114) (generator "macropad_gen") (generator_version "9.0") (uuid "{ROOT_UUID}")',
        f'(paper "{sheet_layout.PAPER}")',
        '(title_block (title "macropad") (rev "A") (company "worxbend")',
        '(comment 1 "Generated from pcb/gen/circuit.py. Do not edit: change circuit.py and run make pcb-place.")',
        '(comment 2 "Not built. Nothing on this sheet has been measured on hardware."))',
        "(lib_symbols", *(drawing.lib_symbols[lib_id].embedded() for lib_id in sorted(drawing.lib_symbols)), ")",
        *drawing.items,
        *_wire_items(drawing),
        '(sheet_instances (path "/" (page "1")))',
        "(embedded_fonts no))",
    ]
    return "\n".join(lines) + "\n"


def render_symbol_library() -> str:
    """The project's own symbol library: the two parts KiCad has no symbol for."""
    symbols = [make() for make in _PROJECT_SYMBOLS.values()]
    lines = ['(kicad_symbol_lib (version 20241209) (generator "macropad_gen") (generator_version "9.0")',
             *(symbol.embedded(symbol.name) for symbol in symbols), ")"]
    return "\n".join(lines) + "\n"


def symbol_library_table(lib_ids: list[str]) -> str:
    """The project's own symbols, and the KiCad libraries the sheet uses, so the rule check can compare
    every symbol on the sheet with its library even on a machine where KiCad was never set up."""
    libraries = sorted({lib_id.split(":")[0] for lib_id in lib_ids} - {"macropad"})
    lines = ["(sym_lib_table", "  (version 7)",
             '  (lib (name "macropad")(type "KiCad")(uri "${KIPRJMOD}/macropad.kicad_sym")(options "")'
             '(descr "Generated by pcb/gen/schematic.py"))']
    lines += [f'  (lib (name "{name}")(type "KiCad")(uri "${{KICAD9_SYMBOL_DIR}}/{name}.kicad_sym")(options "")(descr ""))'
              for name in libraries]
    return "\n".join(lines) + "\n)\n"


FOOTPRINT_LIBRARY_TABLE = """\
(fp_lib_table
  (version 7)
  (lib (name "macropad")(type "KiCad")(uri "${KIPRJMOD}/../lib/macropad.pretty")(options "")(descr "Project footprints"))
)
"""


def write(kicad_dir: Path, symbol_dir: Path = KICAD_SYMBOLS) -> None:
    """The schematic, its symbol library and the two library tables KiCad needs to find the project's own parts."""
    drawing = _draw_sheet(SymbolLibrary(symbol_dir))
    (kicad_dir / "macropad.kicad_sch").write_text(render(drawing))
    (kicad_dir / "macropad.kicad_sym").write_text(render_symbol_library())
    (kicad_dir / "sym-lib-table").write_text(symbol_library_table(list(drawing.lib_symbols)))
    (kicad_dir / "fp-lib-table").write_text(FOOTPRINT_LIBRARY_TABLE)


def nets_by_pin() -> dict[str, str]:
    """"U1.5" -> net, for every pin that has a net. What the exported netlist must say."""
    return {f"{part.ref}.{pad}": net for part in circuit.all_parts() for pad, net in part.nets.items() if net != NO_NET}


if __name__ == "__main__":
    write(circuit.REPO_ROOT / "pcb" / "kicad", Path(sys.argv[1]) if len(sys.argv) > 1 else KICAD_SYMBOLS)
