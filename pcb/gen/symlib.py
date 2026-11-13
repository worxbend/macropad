"""Schematic symbols: read from KiCad's symbol libraries, or drawn here for the two parts KiCad has none for.

Pure Python. The library files only exist inside the KiCad container, so the caller passes their folder.

Coordinates are counted in schematic grid steps of 1.27 mm. Inside a symbol Y points up, on the
sheet Y points down; `sheet_offset` converts.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

import sexpr

GRID = 1.27
ROTATIONS = (0, 90, 180, 270)


def to_grid(millimetres: float) -> int:
    steps = round(millimetres / GRID)
    assert abs(steps * GRID - millimetres) < 1e-6, f"{millimetres} mm is off the {GRID} mm grid"
    return steps


def sheet_offset(x: int, y: int, rotation: int) -> tuple[int, int]:
    """A point of a symbol (Y up) as an offset on the sheet (Y down), for a symbol turned counter-clockwise."""
    assert rotation in ROTATIONS, f"rotation {rotation}"
    for _ in range(rotation // 90):
        x, y = -y, x
    return x, -y


@dataclass(frozen=True)
class LibPin:
    number: str
    name: str
    kind: str  # KiCad's electrical type: passive, power_in, power_out, input, output, bidirectional, no_connect
    x: int     # the end a wire connects to
    y: int
    angle: int  # direction from that end into the body: 0 right, 90 up, 180 left, 270 down
    hidden: bool

    def at(self, rotation: int) -> tuple[int, int]:
        return sheet_offset(self.x, self.y, rotation)

    def outward(self, rotation: int) -> tuple[int, int]:
        """Unit step on the sheet from the pin's end away from the body."""
        into_body = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[self.angle]
        return sheet_offset(-into_body[0], -into_body[1], rotation)


@dataclass(frozen=True)
class LibSymbol:
    lib_id: str             # "Device:R"
    node: tuple             # the symbol as KiCad wants it inside a schematic's lib_symbols, frozen
    pins: tuple[LibPin, ...]

    @property
    def name(self) -> str:
        return self.lib_id.split(":")[1]

    def property_value(self, name: str) -> str:
        for prop in sexpr.children(_thaw(self.node), "property"):
            if sexpr.unquoted(prop[1]) == name:
                return sexpr.unquoted(prop[2])
        return ""

    def property_at(self, name: str) -> tuple[float, float, int, list]:
        """A text field: offset from the symbol origin in millimetres (sheet directions), angle, text style."""
        for prop in sexpr.children(_thaw(self.node), "property"):
            if sexpr.unquoted(prop[1]) == name:
                at = sexpr.child(prop, "at")
                return float(at[1]), -float(at[2]), int(at[3]), sexpr.child(prop, "effects")
        raise KeyError(f"{self.lib_id} has no field {name}")

    def embedded(self, lib_id: str | None = None) -> str:
        """Text for lib_symbols (name with its library) or for a symbol library file (bare name)."""
        node = _thaw(self.node)
        node[1] = sexpr.quoted(self.lib_id if lib_id is None else lib_id)
        return sexpr.dump(node)


def _freeze(node):
    return tuple(_freeze(child) for child in node) if isinstance(node, list) else node


def _thaw(node):
    return [_thaw(child) for child in node] if isinstance(node, tuple) else node


def _pins(symbol_node: list) -> tuple[LibPin, ...]:
    pins = []
    for unit in sexpr.children(symbol_node, "symbol"):
        for pin in sexpr.children(unit, "pin"):
            at = sexpr.child(pin, "at")
            pins.append(LibPin(
                number=sexpr.unquoted(sexpr.child(pin, "number")[1]),
                name=sexpr.unquoted(sexpr.child(pin, "name")[1]),
                kind=pin[1],
                x=to_grid(float(at[1])), y=to_grid(float(at[2])), angle=int(at[3]),
                hidden=sexpr.child(pin, "hide") is not None,
            ))
    numbers = [pin.number for pin in pins]
    assert len(numbers) == len(set(numbers)), f"{symbol_node[1]}: a pin number repeats"
    return tuple(pins)


def flatten(library: dict[str, list], name: str) -> list:
    """The symbol with everything it inherits written out, the way a schematic file stores it."""
    node = copy.deepcopy(library[name])
    extends = sexpr.child(node, "extends")
    if extends is None:
        return node
    parent_name = sexpr.unquoted(extends[1])
    parent = flatten(library, parent_name)
    own_properties = {sexpr.unquoted(prop[1]) for prop in sexpr.children(node, "property")}
    merged = ["symbol", sexpr.quoted(name)]
    for item in parent[2:]:
        if item[0] == "property":
            if sexpr.unquoted(item[1]) not in own_properties:
                merged.append(item)
        elif item[0] == "symbol":
            unit_name = sexpr.unquoted(item[1])
            assert unit_name.startswith(parent_name + "_"), unit_name
            merged.append(["symbol", sexpr.quoted(name + unit_name[len(parent_name):]), *item[2:]])
        else:
            merged.append(item)
    first_unit = next(i for i, item in enumerate(merged) if isinstance(item, list) and item[0] == "symbol")
    merged[first_unit:first_unit] = sexpr.children(node, "property")
    return merged


class SymbolLibrary:
    """KiCad's symbol libraries in one folder, read on demand."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._files: dict[str, dict[str, list]] = {}
        self._symbols: dict[str, LibSymbol] = {}

    def get(self, lib_id: str) -> LibSymbol:
        if lib_id not in self._symbols:
            library_name, name = lib_id.split(":")
            if library_name not in self._files:
                tree = sexpr.parse((self._directory / f"{library_name}.kicad_sym").read_text())
                self._files[library_name] = {sexpr.unquoted(s[1]): s for s in sexpr.children(tree, "symbol")}
            node = flatten(self._files[library_name], name)
            self._symbols[lib_id] = LibSymbol(lib_id, _freeze(node), _pins(node))
        return self._symbols[lib_id]


# --- symbols drawn here -----------------------------------------------------------------------

_PIN_LENGTH = 2  # grid steps
_SIDE_ANGLE = {"left": 0, "right": 180, "top": 270, "bottom": 90}
_FONT = "(effects (font (size 1.27 1.27)))"


@dataclass(frozen=True)
class BoxPin:
    number: str
    name: str
    kind: str
    side: str      # left, right, top, bottom
    offset: int    # along that side, from the middle: down for left/right, right for top/bottom


def box_symbol(lib_id: str, value: str, half_size: tuple[int, int], pins: tuple[BoxPin, ...]) -> LibSymbol:
    """A plain rectangle with named, typed pins. For parts KiCad's libraries do not have."""
    half_width, half_height = half_size
    name = lib_id.split(":")[1]
    pin_texts = []
    for pin in pins:
        reach_x, reach_y = half_width + _PIN_LENGTH, half_height + _PIN_LENGTH
        x, y = {"left": (-reach_x, -pin.offset), "right": (reach_x, -pin.offset),
                "top": (pin.offset, reach_y), "bottom": (pin.offset, -reach_y)}[pin.side]
        pin_texts.append(
            f'(pin {pin.kind} line (at {x * GRID:.2f} {y * GRID:.2f} {_SIDE_ANGLE[pin.side]}) '
            f'(length {_PIN_LENGTH * GRID}) (name "{pin.name}" {_FONT}) (number "{pin.number}" {_FONT}))')
    text = "\n".join([
        f'(symbol "{name}" (pin_names (offset 0.762)) (exclude_from_sim no) (in_bom yes) (on_board yes)',
        f'(property "Reference" "U" (at {-half_width * GRID:.2f} {(half_height + 1) * GRID:.2f} 0) '
        f'(effects (font (size 1.27 1.27)) (justify left)))',
        f'(property "Value" "{value}" (at {GRID:.2f} {(half_height + 1) * GRID:.2f} 0) '
        f'(effects (font (size 1.27 1.27)) (justify left)))',
        '(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        '(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        '(property "Description" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        f'(symbol "{name}_0_1" (rectangle (start {-half_width * GRID:.2f} {half_height * GRID:.2f}) '
        f'(end {half_width * GRID:.2f} {-half_height * GRID:.2f}) (stroke (width 0.254) (type default)) '
        f'(fill (type background))))',
        f'(symbol "{name}_1_1"', *pin_texts, "))",
    ])
    node = sexpr.parse(text)
    return LibSymbol(lib_id, _freeze(node), _pins(node))
