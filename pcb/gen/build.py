"""PCB build steps. Run inside the KiCad container; see the Makefile.

    build.py place    board.toml + circuit.py -> placed and routed board with filled planes,
                      the schematic (checked against circuit.py), and the pictures in docs/images/pcb
    build.py order    search for a routing order that connects every net; rewrites route_order.txt
    build.py fab      routed board -> JLCPCB bill of materials and placement list
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pcbnew

import fab
import layout
import route
import schematic

PCB_DIR = Path(__file__).resolve().parents[1]
KICAD_DIR = PCB_DIR / "kicad"
BOARD_PATH = KICAD_DIR / "macropad.kicad_pcb"
ROUTING_REPORT_PATH = PCB_DIR / "routing.txt"
ROUTE_ORDER_PATH = Path(__file__).with_name("route_order.txt")
BUILD_DIR = PCB_DIR / ".build"
SCHEMATIC_PATH = KICAD_DIR / "macropad.kicad_sch"
IMAGE_DIR = PCB_DIR.parent / "docs" / "images" / "pcb"
ORDER_SEARCH_ROUNDS = 12
# Camera for the two angled renders, as kicad-cli wants it: degrees about X, Y, Z.
ASSEMBLED_VIEW_ROTATION = "-50,0,25"
UNDERSIDE_VIEW_ROTATION = "-130,0,-25"
# DRC findings that are meant: (kind, item). layout.py cuts the part of J1's silkscreen outline that
# hangs over the board edge with the receptacle, so J1 differs from KiCad's library copy.
ACCEPTED_FINDINGS = {("lib_footprint_mismatch", "Footprint J1")}
_ORDER_HEADER = """\
# MCU nets that are routed before the others, first line first.
# Written by `build.py order`. Run it again after moving parts or pins, when `build.py place`
# reports unrouted pads.
"""


def _read_route_order() -> tuple[str, ...]:
    lines = ROUTE_ORDER_PATH.read_text().splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def _plan(head_start: tuple[str, ...], open_pin_nets: dict[str, str]) -> tuple[pcbnew.BOARD, route.RoutingResult]:
    board = layout.build_board(BOARD_PATH, open_pin_nets)
    return board, route.route(board, layout.routing_setup(head_start))


def place() -> None:
    KICAD_DIR.mkdir(exist_ok=True)
    open_pin_nets = write_schematic()  # first: the board is checked against it below
    layout.write_models()
    board, result = _plan(_read_route_order(), open_pin_nets)
    nets = board.GetNetCount() - 1 - len(open_pin_nets)
    print(f"placed {len(board.GetFootprints())} footprints, {nets} nets, {len(open_pin_nets)} open pins")
    route.write_copper(board, result.router)
    if not result.unrouted:
        _check_connected_without_pours(board)
    layout.add_outer_ground_pours(board)
    _save_filled(board, BOARD_PATH)
    if not result.unrouted:
        _check_no_warnings()
    ROUTING_REPORT_PATH.write_text("\n".join(result.report_lines()) + "\n")
    print(result.report_lines()[0])
    for line in result.unrouted:
        print("UNROUTED", line)
    if not result.unrouted:
        route.check_sensitive_lengths(result.router)
    write_images()


def _kicad_cli(*arguments: str) -> None:
    subprocess.run(["kicad-cli", *arguments], check=True, stdout=subprocess.DEVNULL)


def _schematic_nets() -> dict[str, str]:
    """"U1.5" -> net, read back from the netlist KiCad exports for the schematic."""
    netlist_path = BUILD_DIR / "schematic.net"
    _kicad_cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(netlist_path), str(SCHEMATIC_PATH))
    nets = {}
    for block in netlist_path.read_text().split("(net (code")[1:]:
        name = re.search(r'\(name "/?([^"]*)"\)', block).group(1)
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', block):
            nets[f"{ref}.{pin}"] = name
    return nets


def write_schematic() -> dict[str, str]:
    """Schematic from circuit.py, then KiCad's own view of it: rule check, and the netlist compared pin by pin.

    Returns the nets of the open pins ("U1.14" -> "unconnected-(U1-GPIO10-Pad14)") for the board."""
    BUILD_DIR.mkdir(exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    schematic.write(KICAD_DIR)
    _kicad_cli("sch", "erc", "--severity-all", "--exit-code-violations", "-o", str(BUILD_DIR / "erc.rpt"),
               str(SCHEMATIC_PATH))
    exported, wanted = _schematic_nets(), schematic.nets_by_pin()
    open_pin_nets = {pin: net for pin, net in exported.items() if net.startswith(schematic.OPEN_PIN_NET_PREFIX)}
    drawn = {pin: net for pin, net in exported.items() if pin not in open_pin_nets}
    wrong = sorted(pin for pin in drawn.keys() | wanted.keys() if drawn.get(pin) != wanted.get(pin))
    assert not wrong, f"schematic and circuit.py disagree on {wrong}"
    _kicad_cli("sch", "export", "svg", "--exclude-drawing-sheet", "-o", str(BUILD_DIR), str(SCHEMATIC_PATH))
    (BUILD_DIR / "macropad.svg").replace(IMAGE_DIR / "schematic.svg")
    _kicad_cli("sch", "export", "pdf", "-o", str(IMAGE_DIR / "schematic.pdf"), str(SCHEMATIC_PATH))
    print(f"schematic: ERC clean, {len(drawn)} pins match circuit.py")
    return open_pin_nets


def _render(board_path: Path, name: str, *view: str) -> None:
    _kicad_cli("pcb", "render", *view, "--width", "1600", "--height", "1600", "--quality", "high",
               "--background", "opaque", "-o", str(IMAGE_DIR / f"{name}.png"), str(board_path))


def _write_bare_copy() -> Path:
    """The board without its part models, so the bare-board renders show the silkscreen."""
    board = pcbnew.LoadBoard(str(BOARD_PATH))
    for footprint in board.GetFootprints():
        footprint.Models().clear()
    bare_path = BUILD_DIR / "bare.kicad_pcb"
    pcbnew.SaveBoard(str(bare_path), board)
    return bare_path


def write_images() -> None:
    """Renders of the bare and the populated board, and one drawing per copper layer."""
    bare_path = _write_bare_copy()
    for side in ("top", "bottom"):
        _render(bare_path, f"render-{side}", "--side", side)
        _render(BOARD_PATH, f"assembled-{side}", "--side", side)
    _render(BOARD_PATH, "assembled-angle", "--rotate", ASSEMBLED_VIEW_ROTATION, "--perspective", "--zoom", "0.75")
    _render(BOARD_PATH, "assembled-underside", "--rotate", UNDERSIDE_VIEW_ROTATION, "--perspective", "--zoom", "0.75")
    drawings = {"copper-top": "F.Cu", "copper-ground": "In1.Cu", "copper-power": "In2.Cu", "copper-bottom": "B.Cu",
                "assembly-top": "F.SilkS,F.Mask,F.Fab", "assembly-bottom": "B.SilkS,B.Mask,B.Fab"}
    for name, layers in drawings.items():
        mirror = ["--mirror"] if name == "assembly-bottom" else []
        _kicad_cli("pcb", "export", "svg", "--layers", f"{layers},Edge.Cuts", "--exclude-drawing-sheet",
                   "--page-size-mode", "2", *mirror, "-o", str(IMAGE_DIR / f"{name}.svg"), str(BOARD_PATH))


def _save_filled(board: pcbnew.BOARD, path: Path) -> None:
    pcbnew.SaveBoard(str(path), board)
    # Filled on a freshly loaded board: on the board still in memory the fill ignores the holes.
    reloaded = pcbnew.LoadBoard(str(path))
    pcbnew.ZONE_FILLER(reloaded).Fill(reloaded.Zones())
    pcbnew.SaveBoard(str(path), reloaded)


def _check_connected_without_pours(board: pcbnew.BOARD) -> None:
    """Tracks, vias and the inner planes alone must connect every net. The ground pours on the
    outer layers come later and would hide a ground pad that has no via."""
    BUILD_DIR.mkdir(exist_ok=True)
    bare_path = BUILD_DIR / "without-pours.kicad_pcb"
    _save_filled(board, bare_path)
    _kicad_cli("pcb", "drc", "--severity-error", "--exit-code-violations", "-o",
               str(BUILD_DIR / "without-pours-drc.rpt"), str(bare_path))


def _check_no_warnings() -> None:
    """KiCad's warnings fail the build too: a track end that touches nothing, silkscreen over a pad or off the edge,
    a footprint, value or net that differs from the schematic."""
    report_path = BUILD_DIR / "drc-all.rpt"
    _kicad_cli("pcb", "drc", "--severity-all", "--schematic-parity", "-o", str(report_path), str(BOARD_PATH))
    report = report_path.read_text()
    findings = re.findall(r"^\[(\w+)\][^\n]*\n[^\n]*\n[^\n]*: (.*)$", report, re.MULTILINE)
    unexpected = sorted(set(findings) - ACCEPTED_FINDINGS)
    assert not unexpected, f"DRC warnings {unexpected}; see {report_path}"
    kinds = set(re.findall(r"^\[(\w+)\]", report, re.MULTILINE))
    assert kinds <= {kind for kind, _ in ACCEPTED_FINDINGS}, f"DRC warnings {sorted(kinds)}; see {report_path}"
    for clean in ("unconnected pads", "Footprint errors"):
        assert f"Found 0 {clean}" in report, f"{clean}; see {report_path}"
    assert f"Found {len(findings)} DRC violations" in report, f"not every finding was read; see {report_path}"


def order() -> None:
    """Routes again and again; the nets that ended up walled in go to the front of the next round."""
    head_start: tuple[str, ...] = ()
    open_pin_nets = write_schematic()
    for round_number in range(1, ORDER_SEARCH_ROUNDS + 1):
        _, result = _plan(head_start, open_pin_nets)
        walled_in = list(dict.fromkeys(line.split(":")[0] for line in result.unrouted))
        print(f"round {round_number}: {len(result.unrouted)} unrouted {walled_in}", flush=True)
        if not walled_in:
            ROUTE_ORDER_PATH.write_text(_ORDER_HEADER + "".join(f"{net}\n" for net in head_start))
            return
        head_start = tuple(walled_in) + tuple(net for net in head_start if net not in walled_in)
    sys.exit(f"no complete routing order found in {ORDER_SEARCH_ROUNDS} rounds; route_order.txt is unchanged")


STEPS = {"place": place, "order": order, "fab": lambda: fab.write_assembly_files(BOARD_PATH)}

if __name__ == "__main__":
    step = STEPS.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if step is None:
        sys.exit(__doc__)
    step()
