# macropad

A 12-key macropad on its own 4-layer PCB. Two rotary encoders, an always-on memory display,
light bars in the case sides, one USB-C port. Board, case and firmware are all generated from
code in this repository and checked against one shared file, [`board.toml`](board.toml).

It is the small, PCB-based sibling of [macropad-nyxilab](https://github.com/worxbend/macropad-nyxilab):
90 x 90 mm instead of 159 x 98 mm, and no hand wiring.

<img src="docs/images/cad/hero.png" alt="Render of the case: a square slab with a light top and a dark base, twelve keys in a dish, a flush black lens over the display between two knobs" width="100%">

<img src="docs/images/ui/demo.gif" alt="Simulator: the pad from above, its display, its LEDs and the USB reports the host receives" width="100%">

*Top: a render of the case model, not a photo. Bottom: the firmware running in its simulator, not a
recording of a device. The display in the render shows the simulator's own picture.*

> **Status: design files only. Nothing has been built.**
> No board has been ordered. No case has been printed or milled. The firmware has never run on a chip.
> Every claim below is what the design files and their automatic checks say. Read
> [Before you order](#before-you-order) first.

## Contents

1. [Status](#status)
2. [What it is](#what-it-is)
3. [Gallery](#gallery)
4. [Build one](#build-one)
5. [Stock keymap](#stock-keymap)
6. [Work on the design](#work-on-the-design)
7. [What is checked](#what-is-checked)
8. [Where things are](#where-things-are)
9. [Before you order](#before-you-order)
10. [License](#license)

## Status

Checked on 2026-11-14 by running the commands in the last column on this repository.

| Part | State | How it was checked |
|---|---|---|
| Circuit | Done. 52 nets, 75 machine-placed parts, 1 left unpopulated (C13). | `make pcb-test`: netlist self-check, 37 unit tests pass |
| Schematic | Done. Generated KiCad 9 sheet. ERC: 0 errors, 0 warnings. | `make pcb-place` (report in `pcb/.build/erc.rpt`) |
| PCB layout | **Fully routed.** 827 tracks, 164 vias, 0 unrouted pads. DRC: 0 violations, 0 unconnected, 0 differences from the schematic. | `make pcb-check` |
| Order files | Written: 11 Gerbers, 2 drill files, a BOM and a placement file each for PCBWay and JLCPCB. They agree with the board and with each other. | `make pcb-fab`, `make pcb-test` |
| Case | Done. 659 part pairs per variant, 0 clashes. Every named clearance and measurement inside its limit. Printed and milled variant. | `make test` |
| Firmware | Builds. 248 tests pass. UF2 in `firmware/dist/`. | `make test`, `make firmware` |
| Real hardware | **None.** No board, no print, no flash. | - |

One accepted DRC warning remains: the USB-C footprint differs from its library copy, because its
silkscreen is cut at the board edge. It is named in `pcb/gen/build.py` and explained in
[pcb/README.md](pcb/README.md).

A clean DRC does not make a working board. The list of things a person still has to look at is in
[Before you order](#before-you-order).

## What it is

| | |
|---|---|
| MCU | RP2354A: the Pico 2 chip (RP2350) with 2 MB flash inside the package |
| Keys | 12 x MX, HanElectricity hot-swap sockets (Kailh CPG151101S11 compatible), one GPIO per key (no matrix, no diodes) |
| Knobs | 2 x Alps EC11E18244AU with push switch, 36 clicks per turn. 3.3 kΩ pull-ups on the A and B contacts give each contact 1 mA |
| Display | nice!view (Sharp memory LCD, 160 x 68, monochrome, readable in sunlight), soldered on a 5-pin male header |
| Light | 8 x SK6812 SIDE-A side-emitting RGB LEDs on the PCB edges, behind two light bars that show as a line in the gap round the case |
| USB | One USB-C port for power, data and flashing. ESD diodes, 500 mA resettable fuse |
| Debug | Six test pads on the bottom face: SWCLK, SWDIO, GND, 5V, 3V3, 1V1. BOOT and RESET buttons reached through the case floor |
| PCB | 84 x 82.5 mm, 4 layers, 1.6 mm. Every machine-placed part is on the bottom face, next to the ground plane on In2 |
| Case | Base and top with a lap joint and a shadow gap between them, flush lens over the display, 2 light bars, 2 knobs, 2 foot strips and a centre pad that hide the screws, optional 6° tilt bar. 3D-print or CNC variant. The aluminium case is bonded to GND at one screw (H1) |
| Size | 90.0 x 90.0 x 17.5 mm, 35.5 mm from the underside to the top of the knobs. The foot strips add 1.2 mm |
| Firmware | Rust ([embassy](https://embassy.dev)). 4 layers, macros, tap-hold keys, per-layer knob functions, animated display, reactive lighting |
| Host | Shows up as a USB keyboard plus media keys. No driver, no host software |

How the pieces connect:

```mermaid
flowchart LR
    usb[USB-C] -->|5 V through fuse| reg[AP2112K 3.3 V]
    usb <-->|D+ D- through ESD diodes| mcu[RP2354A]
    reg --> mcu
    keys[12 MX keys] -->|12 GPIO| mcu
    knobs[2 encoders with push] -->|6 GPIO| mcu
    mcu -->|SPI0| lcd[nice!view]
    mcu -->|GPIO9| shift[74LVC1T45 to 5 V]
    shift --> leds[8 x SK6812 SIDE-A]
    usb -->|5 V| leds
```

More detail: [docs/hardware.md](docs/hardware.md).

## Gallery

Every picture is generated by the code in this repository. None is a photo.

### Case

<img src="docs/images/cad/hero_aluminium.png" alt="The milled variant drawn as silver anodised aluminium" width="48%"> <img src="docs/images/cad/colourways.png" alt="Four colourways: Chalk and Graphite printed, Silver and Space grey milled" width="48%">

<img src="docs/images/cad/exploded.png" alt="Exploded view: knobs, keycaps, switches, lens, top, PCB, light bars, base, screws, foot strips and centre pad" width="48%"> <img src="docs/images/cad/light_line.png" alt="The left light line drawn glowing in the gap" width="48%">

<img src="docs/images/cad/side_profile.png" alt="From the left: light top, dark base, the gap between them" width="48%"> <img src="docs/images/cad/underside.png" alt="Underside: two foot strips, the centre pad, the mark, BOOT and RESET holes. No screw shows" width="48%">

<img src="docs/images/cad/section_usb_display.png" alt="Cut through the USB port, the lens and the display" width="48%"> <img src="docs/images/cad/section_light_line.png" alt="Cut across the pad through one LED and its light bar" width="48%">

<img src="docs/images/cad/back_usb.png" alt="Back of the case with the USB-C opening" width="48%"> <img src="docs/images/cad/tilt.png" alt="The optional tilt bar under the back of the base" width="48%">

The case is a 90 mm square slab with one flat top face. The printed variant has R 7.0 arc corners; the
milled variant has continuous-curvature corners. The gap between the two shells runs all round, but it
lights only along two 46.5 mm stretches, one per side. The glow colour and the brightness in the
light-line picture are guesses: no optical simulation was done. The colours are proposals.
More views, the print orientation and the design notes: [cad/README.md](cad/README.md).

### PCB

<img src="docs/images/pcb/render-top.png" alt="Bare board, top face" width="48%"> <img src="docs/images/pcb/render-bottom.png" alt="Bare board, bottom face with all machine-placed parts" width="48%">

<img src="docs/images/pcb/assembled-angle.png" alt="Populated board, key side" width="48%"> <img src="docs/images/pcb/assembled-underside.png" alt="Populated board, underside" width="48%">

The parts on the populated board are block models with nominal heights. They show where things
are. They are not the makers' 3D models.

<a href="docs/images/pcb/schematic.pdf"><img src="docs/images/pcb/schematic.svg" alt="Schematic, one A3 sheet" width="100%"></a>

Schematic as [PDF](docs/images/pcb/schematic.pdf). Copper layers:
[top](docs/images/pcb/copper-top.svg), [ground](docs/images/pcb/copper-ground.svg),
[power](docs/images/pcb/copper-power.svg), [bottom](docs/images/pcb/copper-bottom.svg).
Assembly drawings: [top](docs/images/pcb/assembly-top.svg), [bottom](docs/images/pcb/assembly-bottom.svg).
Routing notes and the full check list: [pcb/README.md](pcb/README.md).

### Display and lighting

<img src="docs/images/ui/screens.png" alt="All display screens: splash, four layers, layer banner, knob overlay, system, idle, flash mode" width="60%">

<img src="docs/images/ui/led_timeline.png" alt="Colours of the 8 LEDs over the demo session" width="100%">

The 8 LEDs over the demo session, one row per LED. Colours are brightened for the screen.
Screens, controls and timing: [firmware/README.md](firmware/README.md).

### Drawings

<img src="docs/images/cad/general_arrangement.png" alt="General arrangement drawing with dimensions" width="100%">

<img src="docs/images/cad/drawing_base.png" alt="Machine-shop sheet for the CNC base" width="48%"> <img src="docs/images/cad/drawing_top.png" alt="Machine-shop sheet for the CNC top" width="48%">

The sheets are in `cad/exports/drawings/` as SVG and PDF. Dimension texts are computed from the model.
The two CNC sheets carry part numbers, revision A, one finish (bead blast and clear anodise), ISO
2768-m with the critical fits toleranced, the M2 thread callouts, the anodise masks for the case
ground at S1, a USB opening detail and, on the base, the laser-mark note. `make cad` reads every exported STEP and STL back: one closed solid per part, no
free edges, volumes within 0.1 %.

## Build one

Nobody has done this yet. The guides are written from the design files. Expect to find mistakes,
and please report them.

The plan for the first prototype, step by step with a pass test for each, is
[docs/prototype.md](docs/prototype.md): measure the parts, order the board, print coupons and a case,
bring the board up, and only then pay for a milled case.

1. **Read [Before you order](#before-you-order).** Decide whether you accept the open points.
2. **Order the board.** [docs/ordering.md](docs/ordering.md): PCBWay step by step, 5 bare boards
   with 2 assembled on the bottom face, with the files in `pcb/fab/`. JLCPCB is the alternative on
   the same page. Buy the parts the board house does not place: [docs/parts.md](docs/parts.md).
3. **Make the case.** Print the coupons first, then the case. Mill it only after a printed case
   closes on measured parts. Orientation, settings and CNC notes are in
   [cad/README.md](cad/README.md#printing).
4. **Assemble.** [docs/assembly.md](docs/assembly.md): bring up the bare board from a current-limited
   supply, run the hardware test, solder the two encoders and the display, then close the case with
   six screws.
5. **Flash.** [docs/flashing.md](docs/flashing.md): hold BOOT, plug in, copy
   `firmware/dist/macropad.uf2` to the `RP2350` drive. The same page lists what to check first when
   something does not work.

To change what the keys do: [docs/keymap.md](docs/keymap.md).

## Stock keymap

Four layers. Tap the left knob for the next layer. The display always shows the active layer's labels.

| Layer | Keys, row by row | Left knob | Right knob | Right knob press |
|---|---|---|---|---|
| MEDIA | PREV PLAY NEXT STOP / F13 F14 F15 F16 / F17 F18 F19 F20 | Volume | Screen brightness | Mute |
| EDIT | UNDO REDO CUT COPY / PASTE ALL SAVE FIND / ESC TAB-or-Shift DEL LINE | Undo, redo | Cursor left, right | Enter |
| NAV | HOME UP END PGUP / LEFT DOWN RIGHT PGDN / TAB- TAB+ BACK FWD | Up, down arrow | Previous, next tab | Enter |
| NUM | 7 8 9 BKSP / 4 5 6 ENTER / 1 2 3 0 | Volume | Minus, plus | Period |

| Gesture | Does |
|---|---|
| Hold the left knob + a top-row key | Jump to layer 1, 2, 3 or 4 |
| Hold the left knob + turn the right knob | LED brightness, 8 steps down to off |
| Hold both knobs for 1 s | Restart as a USB drive for a new firmware file |

## Work on the design

### Tools

| For | You need |
|---|---|
| Firmware | Rust (stable) with `rustup target add thumbv8m.main-none-eabihf`, Python 3.11 or newer, `make` |
| Simulator pictures | The above plus ImageMagick (`magick`) |
| Case | Python 3.12 and a virtual environment in `cad/.venv` (set-up in [cad/README.md](cad/README.md#build)). `rsvg-convert` for the PDF and PNG drawings |
| PCB | Docker. All KiCad work runs in the pinned image `kicad/kicad:9.0.9` through `pcb/kicad.sh` |

### Commands

Run `make help` for this list.

| Command | Does | Needs | Time |
|---|---|---|---|
| `make test` | Everything that can be checked without Docker or hardware | Rust, `cad/.venv` | about 3 minutes |
| `make firmware` | Tests, lints, board and HID checks, `firmware/dist/macropad.uf2` | Rust | under 1 minute |
| `make ui-images` | Redraws `docs/images/ui/` and the demo GIF from the simulator | Rust, ImageMagick | about 1 minute |
| `make cad` | Case self-test, checks, STEP/STL exports, renders, drawings | `cad/.venv` | about 3 minutes |
| `make pcb` | `pcb-place`, `pcb-check`, `pcb-fab` in order | Docker | about 2 minutes |
| `make pcb-place` | Schematic, placed and routed board, 3D models, pictures | Docker | about 1 minute |
| `make pcb-check` | KiCad design-rule check, board against schematic | Docker | seconds |
| `make pcb-fab` | Gerbers, drill files, BOM, placement list into `pcb/fab/` | Docker | seconds |
| `make pcb-test` | Netlist self-check and the PCB generator's unit tests | Python | seconds |
| `make docs-check` | Every file and picture named in a Markdown file exists | Python | seconds |

### One file drives three builds

`board.toml` holds the positions and the GPIO numbers. The PCB generator, the case model and the
firmware's board check all read it.

1. Change a position or a pin in `board.toml`.
2. Run `make pcb cad firmware`.
3. If parts or pins moved on the PCB, the routing order may need a new search:
   `pcb/kicad.sh python3 pcb/gen/build.py order` (about 10 minutes; it can fail).

Nothing in `pcb/kicad/` is drawn by hand. Hand edits are lost on the next `make pcb-place`.
Change `pcb/gen/circuit.py` or `pcb/gen/route.py` instead.

## What is checked

No check here replaces a prototype. They catch the mistakes a computer can catch.

| Area | Check | Result on 2026-11-14 |
|---|---|---|
| PCB | Netlist self-check in `circuit.py` | 52 nets, passes |
| PCB | Router, schematic-writer and order-file unit tests (15, 19, 3) | 37 pass |
| PCB | `circuit.py` pins against KiCad's own RP2354A, regulator, ESD and level-shifter symbols | match |
| PCB | Schematic ERC, every severity | 0 errors, 0 warnings |
| PCB | DRC with board-against-schematic compare | 0 violations, 0 unconnected, 0 parity issues |
| PCB | Length limits on the USB pair, crystal and regulator nets; no via on the sensitive ones | pass (D+ 14.93 mm, D- 14.08 mm) |
| PCB | Order files agree: Gerbers newer than the board, one drill hit per via, both BOMs = both placement files = circuit, C13 in none of them | 75 parts, 1 do-not-populate, pass |
| PCB | Committed order files belong to the committed board: board hash, `unrouted pads 0` | pass |
| PCB | Case ground ring at H1 on GND and bare; encoder pull-ups beside their pins; no solder paste within 0.15 mm of a via hole; the design rules reach KiCad's DRC | pass |
| Case | Self-test: the measuring checks must catch 33 known-bad and sound shapes | 33 of 33 |
| Case | Interference, every part against every other, both variants | 659 pairs each, 0 clashes |
| Case | Every part one sound solid; wall thickness, screw bosses, light bar retention and insertion, lap joint, lens seat and stiffness, key and knob travel, knob seat on its shaft, square outline, corner curvature, frame swell, foot bearing, shell seat, text strokes, USB symmetry | all inside limits |
| Case | CNC: 3 mm tool reaches every pocket within 3 diameters, no sharp internal corner, no undercut beyond the USB opening's rounds | pass |
| Case | Exports read back: 11 STEP files, each part file one closed valid solid and the assembly 81, 0 free edges, volume within 0.1 % of the model and of its STL; no sliver faces in the CNC parts; 9 print coupons, each one watertight body | 11 of 11 STEP, 9 of 9 coupons |
| Case | Print: layer-by-layer bridge and overhang check for every printed part, faces on the 0.2 mm layer grid, show faces of the top at 45° or less, engraving on the bed 0.7 mm wide | pass |
| Firmware | Unit tests: `core` 192, `sim` 38, `uf2` 18 | 248 pass |
| Firmware | `tools/check_pins.py`: GPIOs, knob type, knob debounce longer than the encoder's 3 ms chatter, key grid, LED and simulator positions against `board.toml` | match |
| Firmware | `tools/check_hid.py`: the USB report descriptors, parsed as a host would | match |
| Firmware | UF2 converter refuses an image the chip could not boot | current image passes |
| Docs | `make docs-check`: files and pictures named in Markdown exist | pass |

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the checks that need neither Docker
nor a long case build: `make pcb-test`, `make docs-check` and the firmware tests with both board
checks. The workflow has not run on GitHub yet.

## Where things are

| Path | What |
|---|---|
| [`board.toml`](board.toml) | Positions and GPIOs. The single source of truth for PCB, case and firmware. |
| [`pcb/`](pcb/README.md) | The board. `gen/` is the generator (`circuit.py` is the circuit), `kicad/` the generated KiCad 9 project, `fab/` the order files, `lib/` footprints and block models. |
| [`cad/`](cad/README.md) | Parametric case (build123d). `macropad_case/` is the model and its checks, `exports/` holds STEP, STL, drawings and `checks.json`. |
| [`firmware/`](firmware/README.md) | Rust workspace: `core` logic, `fw` binary, `sim` simulator, `uf2` converter. `dist/macropad.uf2` is the built image. [`KEYMAP.md`](firmware/KEYMAP.md) is the keymap reference. |
| `tools/` | `check_pins.py` and `check_hid.py`: firmware against `board.toml` and against the HID rules. |
| [`docs/hardware.md`](docs/hardware.md) | Circuit in words, pin map, layer stack, test pads, mechanical stack. |
| [`docs/parts.md`](docs/parts.md) | Every part, its JLCPCB number, what to buy elsewhere, substitutions, a shopping list for the prototype. |
| [`docs/prototype.md`](docs/prototype.md) | The staged plan for the first prototype, with a pass test per step. |
| [`docs/ordering.md`](docs/ordering.md) | Ordering the assembled board from PCBWay, step by step; JLCPCB as the alternative. |
| [`docs/assembly.md`](docs/assembly.md) | Bring-up of a bare board, soldering, case assembly. |
| [`docs/flashing.md`](docs/flashing.md) | First flash, updates, troubleshooting. |
| [`docs/keymap.md`](docs/keymap.md) | Changing what the keys, knobs and lights do. |
| `docs/images/` | Generated pictures: `cad/`, `pcb/`, `ui/`. |

## Before you order

These are open. None is hidden by a green check.

**Electrical**

- **Crystal.** Raspberry Pi's reference part, the Abracon ABM8-272-T3, with the reference 15 pF
  capacitors and 1 kΩ. Not measured. If USB does not enumerate, look here first.
  See [docs/parts.md](docs/parts.md).
- **USB pair.** Two short tracks, 14.9 and 14.1 mm, not a tuned differential pair. No impedance was
  calculated. Normal for full-speed USB over this length; nobody measured it.
- **Regulator inductor dot.** The two papers disagree. Raspberry Pi's datasheet and reference
  layout put the dot on +1V1; Abracon's drawing labels the dot "+". The board follows Raspberry Pi:
  dot on the +1V1 pad, next to the silkscreen dot. Mounting on the bottom face changes nothing here:
  the regulator reads as Raspberry Pi's Fig. 26 seen from the bottom. Not verified on a part.
- **Placement rotations.** `pcb/fab/centroid-pcbway.csv` and `pcb/fab/cpl-jlcpcb.csv` carry KiCad's
  angles, also for the bottom-side parts. Whether the assembler wants those or (180 - r) is not
  settled. Check every part in their placement photos or preview before you pay;
  [docs/ordering.md](docs/ordering.md) has the checklist.
- **Suspend current.** The 8 LEDs draw about 4.8 mA even when dark, over the 2.5 mA a suspended USB
  device may draw, and the MCU keeps running too. Accepted for the prototype. The fix is a load
  switch on the LED supply: a board change.
- **C13 is left unpopulated.** Its 4.7 µF would double the 1.1 V regulator's output capacitor.
  The footprint stays; its two pads get solder paste and no part.
- **Hot-swap socket footprint.** The board uses HanElectricity's CPG151101S11-2. The footprint was
  drawn from Kailh's CPG151101S11 dimensions. HanElectricity's drawing gives the same main sizes, but
  nobody has checked the footprint against it pad by pad.

Settled since the last revision: the nice!view header order (MOSI, SCK, VCC, GND, CS) matches the
pinout on nicekeyboards.com, and the SK6812 SIDE-A pad order matches the OPSCO datasheet by function.
Both stay tagged `MEASURE` until someone checks a real module and LED.

**Mechanical**

- **`MEASURE` dimensions.** The nice!view's pixel window, its height on a plain male header (glass 4.4 mm
  above the PCB) and its header position, and the encoder heights (shaft end 24.5 mm, from the Alps
  drawing), come from drawings and community footprints, not from a caliper. The full table is in
  [cad/README.md](cad/README.md#assumptions-to-measure). Measure before you order the board:
  `display.header_x` moves J2 on the PCB.
- **Fits are guesses.** Lap joint 0.2 mm, deepest unsupported ledge 1.5 mm, sag of a printed bridge
  0.2 mm, printed screw holes 0.15 mm small, lens 1.0 mm cover glass on 0.13 mm tape. Print the nine
  coupons in `cad/exports/print/coupons/`, then one case, and measure before paying for machining.
- **The light line is a guess.** The LEDs shine into a bar that shows only through a 1.4 mm slit in the
  gap. How bright and how even that is has not been simulated or tried.
- **The top prints standing on its side wall**, 10.6 times taller than its footprint is wide. Tipping
  and warping are not modelled.

**Firmware**

- **Display orientation, knob direction, LED colour order** are one-line settings and are guesses
  until a board exists. [docs/flashing.md](docs/flashing.md) says where each one is.
- **USB IDs** are the pid.codes test pair `1209:0001`. Get your own before you give boards to others.
- Settings are not stored: brightness and layer reset at power-on.

**Review**

- The schematic and the layout are generated and machine-checked. No engineer has reviewed them.

## License

No license file yet. Until one is added, nobody else has the right to reuse this.
The side-LED footprint comes from another project under the MIT License; see `pcb/lib/SOURCES.txt`.
