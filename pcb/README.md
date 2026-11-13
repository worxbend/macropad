# PCB

The board is generated. Nothing in `pcb/kicad/` is drawn by hand: `make pcb-place` writes the
schematic, the placed and routed board, and the pictures in `docs/images/pcb/` from two inputs,
`board.toml` (positions, GPIOs) and `pcb/gen/circuit.py` (parts and nets).

**Not built.** No board has been ordered, assembled or powered. Everything below is what the design
files say and what the automatic checks confirm, nothing more.

<img src="../docs/images/pcb/render-top.png" alt="top face, bare board" width="48%"> <img src="../docs/images/pcb/render-bottom.png" alt="bottom face, bare board" width="48%">

Bare-board renders (KiCad 9). Left: top face with the keys, knobs and display socket. Right: bottom
face with every machine-placed part.

<img src="../docs/images/pcb/assembled-angle.png" alt="populated board, key side" width="48%"> <img src="../docs/images/pcb/assembled-underside.png" alt="populated board, underside" width="48%">

The same board with its parts. The parts are block models: boxes and cylinders that `gen/models.py`
draws from each footprint's outline, with nominal heights. They show where things are and which face
they are on. They are not the manufacturers' models. Straight-on views:
[top](../docs/images/pcb/assembled-top.png), [bottom](../docs/images/pcb/assembled-bottom.png).

## Commands

| Command | What it does |
|---|---|
| `make pcb-place` | Place, route, pour, write the schematic, check it, export the pictures. About 1 minute. |
| `make pcb-check` | KiCad design-rule check of the routed board. Fails on any error or unconnected item. |
| `make pcb-fab` | Gerbers, drill files, JLCPCB BOM and placement list into `pcb/fab/`, then a check that they agree. |
| `python3 -m unittest discover -s pcb/gen -p 'test_*.py'` | Router and schematic-writer tests (34). Plain Python, no KiCad needed. |
| `pcb/kicad.sh python3 pcb/gen/build.py order` | Search for a routing order again. Needed after moving parts or pins. About 10 minutes. |

All KiCad work runs in the pinned container `kicad/kicad:9.0.9` through `pcb/kicad.sh`.

## Files

| Path | What |
|---|---|
| `gen/circuit.py` | The circuit: every part, its JLCPCB number, position, rotation and nets. Pure Python. |
| `gen/layout.py` | Footprints, board outline, planes, design rules, placement self-checks. |
| `gen/router.py` | Two-layer grid router. Pure Python, tested in `gen/test_router.py`. |
| `gen/route.py` | The routing plan: what is routed in which order, and the hand-placed vias. |
| `gen/route_order.txt` | MCU nets that are routed before the others. Written by `build.py order`. |
| `gen/silk.py` | Silkscreen text. |
| `gen/models.py` | Block 3D models of the parts, written to `lib/3d/`. |
| `gen/schematic.py` | Writes the KiCad schematic from `circuit.py`, with KiCad's library symbols. |
| `gen/sheet_layout.py` | Where each part sits on the schematic sheet and which wires are drawn. Data only. |
| `gen/symlib.py`, `gen/sexpr.py` | Read KiCad symbol libraries; draw the two symbols KiCad has none for. |
| `gen/test_schematic.py` | Tests of the schematic writer. |
| `gen/fab.py` | JLCPCB BOM and placement list. |
| `kicad/` | Generated KiCad 9 project: board, schematic, symbol library, library tables. |
| `routing.txt` | Generated report: track length and via count per net. |
| `netlist.txt` | Generated netlist: `python3 pcb/gen/circuit.py > pcb/netlist.txt`. |
| `lib/` | The three project footprints and where they come from. `lib/3d/` holds the generated block models. |
| `fab/` | Generated order files: `macropad-gerbers.zip`, `bom-jlcpcb.csv`, `cpl-jlcpcb.csv`. |

## Schematic

<a href="../docs/images/pcb/schematic.pdf"><img src="../docs/images/pcb/schematic.svg" alt="schematic, one A3 sheet"></a>

`kicad/macropad.kicad_sch` opens in KiCad 9. One A3 sheet, thirteen blocks.
[PDF](../docs/images/pcb/schematic.pdf), [SVG](../docs/images/pcb/schematic.svg).

It is a drawing of `circuit.py`, not a second source of truth:

- **Symbols come from KiCad's own libraries** (`Device:R`, `MCU_RaspberryPi:RP2354A`,
  `Regulator_Linear:AP2112K-3.3`, `Power_Protection:USBLC6-2SC6`, `Logic_LevelTranslator:SN74LVC1T45DBV`,
  `Connector:USB_C_Receptacle_USB2.0_16P` and so on). Pin numbers, pin names and pin types are
  therefore KiCad's, not typed here. Two parts have no KiCad symbol and are drawn as boxes: the
  side LED and the display socket.
- **`sheet_layout.py` places the parts and lists the drawn wires.** Every other pin gets its supply
  symbol or its net label by rule. A drawn wire names its net, and the build refuses a wire that
  touches a pin of another net.

Checks on every `make pcb-place`:

1. `circuit.py` against KiCad's RP2354A symbol: each GPIO on its pin, each supply pin on its rail,
   the five pins of the flash inside the package open. Each chip's footprint against the footprint
   KiCad's symbol names.
2. `kicad-cli sch erc` at every severity: no error, no warning. That includes KiCad comparing each
   symbol on the sheet with its library.
3. KiCad exports the schematic's netlist; every pin's net is compared with `circuit.py`.
4. `kicad-cli pcb drc --schematic-parity`: every footprint, value and pad net on the board equals
   the schematic.

What this does not prove: KiCad's RP2354A symbol is itself someone's reading of the datasheet. It
is an independent one, and it agrees with `circuit.py` on all 61 pins. The SK6812 SIDE-A and
nice!view pin orders are still `MEASURE` items; no library covers them.

## Layers

| Layer | Use |
|---|---|
| F.Cu | Signals that cross the chip area, ground pour |
| In1.Cu | Ground plane, unbroken |
| In2.Cu | 5 V plane. Inside it a 3.3 V island under the MCU, the display socket and the USB pair. Inside that a 1.1 V island under the chip |
| B.Cu | All machine-placed parts, most signals, ground pour |

Drawings of each layer: [top](../docs/images/pcb/copper-top.svg),
[ground](../docs/images/pcb/copper-ground.svg), [power](../docs/images/pcb/copper-power.svg),
[bottom](../docs/images/pcb/copper-bottom.svg). Assembly drawings:
[top](../docs/images/pcb/assembly-top.svg), [bottom, mirrored](../docs/images/pcb/assembly-bottom.svg).

## Design rules

| Rule | Value | Note |
|---|---|---|
| Track width | 0.15 mm signals, 0.3 mm supply where it fits | |
| Clearance | 0.15 mm | The router keeps 0.17 mm to allow for its 0.1 mm grid |
| Via | 0.6 mm pad, 0.3 mm drill | No vias in pads, except four in the MCU's exposed pad |
| Copper to board edge | 0.3 mm | |
| Copper to hole | 0.25 mm | |

These are inside JLCPCB's published 4-layer limits as the previous author recorded them in
`layout.py`. Check them against the JLCPCB capability page on the day you order.

## How the routing works

There is no autorouter program. `router.py` is a small grid router and `route.py` tells it what to
do, in this order:

1. **Four ground vias** in the MCU's exposed pad.
2. **MCU supply pins.** Each pin runs to its own 100 nF capacitor. The supply via sits between the
   pin and the capacitor, the ground via behind the capacitor, all on one line pointing away from
   the chip. These vias are placed by hand-computed geometry (`circuit.py`: `DECOUPLING_DISTANCE`,
   `SUPPLY_VIA_DISTANCE`, `GROUND_VIA_DISTANCE`), so they stay out of the lanes the neighbouring
   signal pins need.
3. **1.1 V regulator.** Inductor to its two output capacitors with a 0.3 mm track, then on to the
   via at VREG_FB that enters the 1.1 V island.
4. **Crystal ground vias**, then **SWCLK and SWDIO** out of the chip.
5. **Sensitive nets**, while the board is still empty: VREG_LX, the USB pair, the crystal nets,
   VREG_AVDD. Then QSPI_SS, RUN, BOOT and VBUS.
6. **One via to the plane** for every remaining supply and ground pad.
7. **MCU signals**, one pin at a time: first a track out of the 16 mm square around the chip, then
   the rest of the net. Pins next to a capacitor go first. `route_order.txt` moves some nets to the
   front.
8. **Everything else**, shortest net first.

The router has no rip-up. When a net ends up walled in, `build.py order` routes the whole board
again with that net moved to the front, until every net connects. The order it finds is stored in
`route_order.txt`, so `make pcb-place` is one deterministic pass.

## Checks

| Check | Where | Fails the build |
|---|---|---|
| Every net has at least two pads | `circuit.py` | yes |
| Flips and rotations: MCU pins, hot-swap sockets, USB mouth, LED direction, capacitor orientation, crystal near XIN, fiducials on the assembly face | `layout.py:check_placement` | yes |
| Router: clearance to pads, tracks, vias, holes and the edge; vias; fan-out; escapes; determinism (15 tests) | `test_router.py` | yes, in `make pcb-test` and CI |
| Hand-placed vias have room | `router.py:add_via` | yes |
| Every net connects through tracks, vias and inner planes alone, before the outer ground pours are added | `build.py` | yes |
| Length limits: VREG_LX, USB_DM, USB_DP, XIN, XOUT, VREG_AVDD; USB pair mismatch under 2 mm; no via on VREG_LX, on USB D+ from connector to chip, or on D- after its resistor | `route.py:check_sensitive_lengths` | yes |
| KiCad DRC at every severity: no warning either (loose track end, silkscreen over a pad or the edge). One named exception: J1 differs from its library copy, because its silkscreen is cut at the board edge | `build.py:_check_no_warnings` | yes |
| Every real part has a 3D model; no bottom-side model is taller than the gap to the case floor | `layout.py:write_models` | yes |
| Order files: all 11 Gerbers present and newer than the board, drill file has one hole per via, BOM and placement list name the same 71 parts as `circuit.py`, every BOM line has a JLCPCB number | `fab.py:check_outputs` | yes, in `make pcb-fab` |
| Schematic ERC at every severity, and schematic netlist equals `circuit.py` | `build.py:write_schematic` | yes |
| `circuit.py` pins against KiCad's library symbols; chip footprints against the symbols' footprints | `schematic.py` | yes |
| Board equals schematic: footprints, values, pad nets (`--schematic-parity`) | `build.py:_check_no_warnings` | yes |
| Schematic writer: library reading, pin positions under rotation, wire splitting, junction dots, sheet layout (19 tests) | `test_schematic.py` | yes, in `make pcb-test` and CI |
| KiCad DRC: zero errors, zero unconnected | `make pcb-check` | yes |

## What a person still has to look at

- **USB pair.** Routed as two short tracks, not as a tuned differential pair. Lengths are in
  `routing.txt` (D+ 15.4 mm, D- 14.3 mm). From the series resistors to the chip both run on the
  bottom layer with no via. Near the connector D- changes layer twice: a USB-C receptacle has two
  pads per line and one line has to cross the other. No impedance was calculated. This is normal for
  full-speed USB (12 Mbit/s) over 15 mm; it would not be for high-speed.
- **Capacitance on VBUS.** About 7.5 µF sits behind the fuse on the 5 V rail (three 2.2 µF: C17,
  C22, C23, and nine 100 nF). The USB 2.0 specification allows a device 10 µF at plug-in. The LED
  rows now have 2.2 µF each instead of 10 µF; the firmware caps LED current at about 200 mA.
  Nobody has looked at the 5 V rail with a scope while the LEDs switch.
- **Decoupling.** Each MCU supply pin has its own 100 nF. Ten sit 2 mm in front of their pin.
  Two do not fit there: C33 (QSPI_IOVDD, pin 54) sits beside C10 and is tracked to it; C32
  (ADC_AVDD, pin 44) sits 4 mm away behind C9 and connects through the 3.3 V plane. Pins 44 and 54
  are also tracked to the pin beside them, so each reaches that pin's capacitor.
- **Test pads.** Six 1 mm pads on the bottom face, each named in silkscreen: SWCLK, SWDIO, GND
  (between the first two key rows), 5V (next to them), 3V3 (right of the BOOT button, seen from the
  bottom) and 1V1 (beside the inductor). The 1V1 pad hangs on the regulator output track. Nobody has
  put a probe on them.
- **Regulator loop.** VREG_LX and the output link are short and checked for length, but nobody has
  looked at the loop area by eye in KiCad. The inductor's part number and its polarity mark are not
  verified against Raspberry Pi's hardware design guide.
- **Crystal.** It sits 5 mm below XIN, as close as the two hot-swap sockets allow. The 15 pF load
  capacitors are the reference design's values for the reference crystal. This crystal is a
  different part with the same 10 pF load rating (see `docs/parts.md`). The oscillator is not measured.
- **Thermal reliefs** are on for through-hole pads only (encoders, display socket, USB shell).
- **No teardrops.** KiCad 9's Python interface can switch teardrops on per via, but only the editor
  draws them: tried here, a filled and saved board had none. Open the board in KiCad and run
  Edit > Edit Teardrops if you want them; that is a hand edit the next `make pcb-place` removes.
- **Fiducials.** Three 1 mm marks on the bottom face. JLCPCB adds its own tooling holes; none are
  drawn here.
- **Silkscreen** was checked in the renders above, not on a printed board. KiCad reports no
  silkscreen warning.
- **3D models** are block models with heights typed from memory of the datasheets. Use them to see
  the layout, not to measure. The case model has its own clearance checks.
- **Placement list rotations.** `fab/cpl-jlcpcb.csv` carries KiCad's rotation of each footprint.
  JLCPCB's library often expects another zero angle, most often for bottom-side parts, SOT-23 and
  LEDs. Check every part in JLCPCB's placement preview before paying.
- **Schematic layout.** The sheet is generated. It passes KiCad's checks and was looked at as a
  picture, but nobody has reviewed it as an engineer would review a hand-drawn schematic.
- **Net names.** On the board, signal nets carry KiCad's leading slash (`/KEY3`), supply nets do not
  (`GND`, `+3V3`). Each open pin has KiCad's one-pad net (`unconnected-(U1-GPIO10-Pad14)`). This is
  what KiCad itself writes when it updates a board from a schematic.
