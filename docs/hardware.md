# Hardware notes

What the board and the case are, in one place. Nothing here has been built or measured.
Values tagged `MEASURE` come from community footprints, not from a caliper.

Related pages: [parts](parts.md), [ordering](ordering.md), [assembly](assembly.md),
[PCB details](../pcb/README.md), [case details](../cad/README.md).

## How it compares to macropad-nyxilab

| | nyxilab | this board |
|---|---|---|
| Size | 159 x 98 mm | 90.0 x 90.0 mm |
| Wiring | Hand-wired matrix with diodes | 4-layer PCB, one GPIO per key |
| Brain | Pico 2 board | Bare RP2354A on the PCB |
| Keys | 12 MX | 12 MX, hot-swap |
| Centre control | Thumbstick or one knob | Two knobs |
| Screens | Two colour ST7789 | One nice!view (monochrome, always-on, sunlight readable) |
| Light | 16 LEDs on the base | 8 side-emitting LEDs behind two light bars in the case sides |
| Firmware | C++ / PlatformIO | Rust / embassy |

## Layout

Top view, USB at the back:

```
+---------------------------------------------+
|  (knob)   [   nice!view    ]      (knob)    |   back zone, 22 mm deep
|  [K0]     [K1]     [K2]     [K3]            |
|  [K4]     [K5]     [K6]     [K7]            |   19.05 mm pitch
|  [K8]     [K9]     [K10]    [K11]           |
+---------------------------------------------+
   LEDs on both side edges, four per side
```

<img src="images/pcb/assembly-top.svg" alt="Assembly drawing, top face" width="48%"> <img src="images/pcb/assembly-bottom.svg" alt="Assembly drawing, bottom face" width="48%">

- **Top face:** the two encoders and the 5-pin display header. These three are soldered by hand.
  The switches plug into their sockets through the board.
- **Bottom face:** everything else. The MCU, USB-C port, regulator, crystal and both buttons sit
  under the display. The hot-swap sockets sit under the keys. The LEDs sit on the left and right
  edges and shine outward.

Positions are in `board.toml`. The origin is the top-left corner of the PCB seen from the key side.
X grows to the right, Y toward the front.

## Circuit, in words

<a href="images/pcb/schematic.pdf"><img src="images/pcb/schematic.svg" alt="Schematic" width="100%"></a>

The schematic is generated from `pcb/gen/circuit.py` and checked against it pin by pin.
The KiCad file is `pcb/kicad/macropad.kicad_sch`.

- **USB-C.** 5.1 kΩ on both CC pins, USBLC6 ESD diodes, 27 Ω series resistors (R7, R8) right at the
  MCU pins, 500 mA resettable fuse. From the resistors to the chip the pair runs on the bottom layer
  with no via: D+ 14.93 mm and D- 14.08 mm from connector to MCU. No impedance was calculated.
- **Power.** VBUS through the fuse is the 5 V rail (LEDs, level shifter). An AP2112K makes 3.3 V.
  The RP2354A makes its own 1.1 V core supply with the on-chip switching regulator and L1, laid out
  in Raspberry Pi's reference pattern (input and output capacitors side by side at the pins, the
  inductor beyond them, no copper under the inductor on the other layers).
  About 7.5 µF sits on the 5 V rail; USB 2.0 allows 10 µF at plug-in.
  C13, a second 4.7 µF footprint on the 1.1 V output track, is **not fitted**: datasheet 6.3.8 wants
  4.7 µF ±20 % there, and C13 would double it. Its pads stay, marked DNP.
- **Clock.** 12 MHz crystal with a 1 kΩ series resistor on XOUT and 15 pF load capacitors.
  The crystal is Raspberry Pi's reference part, the ABM8-272-T3; see [parts](parts.md).
- **Flashing.** BOOT pulls QSPI_SS low through 1 kΩ, which starts the ROM USB bootloader.
  RESET pulls RUN low. Both buttons are on the bottom face and reached through holes in the case floor.
- **Keys and knobs.** Each switch connects one GPIO to ground. The firmware turns on the internal
  pull-ups. No matrix, no diodes, no ghosting.
- **Knob pull-ups.** R10-R13, 3.3 kΩ 0402, pull the four encoder contacts A and B to 3.3 V, 2.4 mm
  from each encoder pin on the bottom face. A closed contact then carries 1 mA, the minimum Alps
  gives for its EC11 contacts; the chip's internal pull-ups alone give about 0.05 mA. The EC11E18244AU's
  own sheet was not read for this figure. The internal pull-ups stay on in parallel; they do no harm.
  The push switches keep the internal pull-up only.
- **Knobs.** Alps EC11E18244AU: 36 detents and 18 pulses per turn, so one click is half a quadrature
  cycle. The firmware counts one click per debounced edge of contact A and reads the direction from
  contact B (`Detents::PerEdgeOfA`). The detent count is read from the Alps product page, not from a
  part on a desk.
- **Display.** SPI0 (SCK GPIO22, MOSI GPIO23), chip select GPIO24, active high. Header order
  from the back edge to the front: MOSI, SCK, 3V3, GND, CS. It matches the pinout on
  nicekeyboards.com (MOSI, SCK, VCC, GND, CS). Still `MEASURE` until a module is checked.
- **LEDs.** GPIO9, through a 74LVC1T45 to 5 V logic and a 330 Ω series resistor (R9), then eight
  SK6812 SIDE-A in a chain: right side
  back to front, then left side front to back. The firmware caps total LED current at about 200 mA
  and turns the LEDs off when the host sleeps. Dark, the eight still draw about 4.8 mA, over the
  2.5 mA a suspended USB device may draw. Accepted for the prototype; the fix is a load switch on
  the LED supply, a board change.
- **Case ground.** H1, the back-left mounting hole at (3.2, 3.2), is plated, 2.2 mm, with a bare
  5.4 mm GND ring on both faces (`mounting.ground_bond_hole` and `ground_bond_pad_diameter` in
  `board.toml`). The milled top's 5.0 mm corner boss rests on the top ring, its face masked from
  anodise, and the S1 screw joins base, top and GND. The other five holes are unplated. A printed
  case insulates and is not grounded. Nobody has measured the bond.

The full netlist is `pcb/netlist.txt` (`python3 pcb/gen/circuit.py > pcb/netlist.txt` writes it).
Track length and via count per net are in `pcb/routing.txt`.

## Pin map

`board.toml` is the source of truth. `tools/check_pins.py` fails when the firmware disagrees with it.

| Function | GPIO |
|---|---|
| Keys K0 to K3 (back row) | 21, 20, 4, 3 |
| Keys K4 to K7 | 19, 18, 6, 5 |
| Keys K8 to K11 (front row) | 17, 16, 8, 7 |
| Left knob A, B, push | 27, 28, 29 |
| Right knob A, B, push | 0, 1, 2 |
| Display SCK, MOSI, CS | 22, 23, 24 |
| LED data | 9 |
| Spare, no pads | 10 to 15, 25, 26 |

The spare pins end at the chip. Adding a header means a board change.

## Test pads

Six round 1 mm pads on the bottom face, each named in silkscreen. Positions in board coordinates (mm).

| Pad | Net | X, Y | Where |
|---|---|---|---|
| TP1 | SWCLK | 39.0, 36.5 | Between the first two key rows |
| TP2 | SWDIO | 42.0, 36.5 | Next to TP1 |
| TP3 | GND | 45.0, 36.5 | Next to TP2 |
| TP4 | 5V | 50.0, 38.5 | Next to the debug pads |
| TP5 | 3V3 | 24.5, 23.0 | Beside the BOOT button |
| TP6 | 1V1 | 36.0, 11.0 | Beside the inductor, on the regulator output track |

The case floor has no probe holes. Use the pads before the board goes into the case. TP1 to TP3
take a debug probe ([flashing.md](flashing.md#debug-probe-optional)); TP4 to TP6 are the rail checks
in [assembly.md](assembly.md).
The pad positions were picked by a free-space search on the copper and are not checked against the
case model; the pads are flat copper, so nothing can collide.

## Layer stack

| Layer | Use |
|---|---|
| F.Cu | Signals, ground pour, the bare case ground ring at H1 |
| In1.Cu | 5 V plane, with a 3.3 V island under the MCU, the display header and the USB pair (a tongue reaches the left encoder's pull-ups), and a 1.1 V island under the chip |
| In2.Cu | Ground plane, next to the parts on the bottom face |
| B.Cu | Parts, most signals (1067 of 1308 mm of track), ground pour |

The ground plane sits on In2, next to B.Cu, because every part and most of the track are on the
bottom face. Each bottom signal then has its return path one layer away.

Design rules: 0.15 mm track and gap, 0.6 mm via with a 0.3 mm drill, 0.3 mm copper to board edge.
Pictures of each layer: [top](images/pcb/copper-top.svg), [ground](images/pcb/copper-ground.svg),
[power](images/pcb/copper-power.svg), [bottom](images/pcb/copper-bottom.svg).

Routing: 827 tracks, 164 vias, 1307.7 mm of track, 0 unrouted pads. The router is a small grid
router in `pcb/gen/router.py`; the routing plan is `pcb/gen/route.py`. No third-party autorouter is used.

## Mechanical stack

Heights from `board.toml`, measured from the PCB top face.

| What | Height |
|---|---|
| Case floor (inside) | 5.0 mm below the PCB bottom face |
| Hot-swap socket | 1.85 mm below the PCB bottom face |
| USB-C body | 3.26 mm below the PCB bottom face |
| PCB | 1.6 mm thick |
| Switch plate top | 5.0 mm (plate 1.5 mm thick, 14.0 mm cut-outs) |
| Encoder body top | 4.5 mm (`MEASURE`: Alps drawing No. 2) |
| Display glass top | 4.4 mm (`MEASURE`: nice!view soldered on a plain male header with a 2.5 mm body) |
| Top face of the case | 8.5 mm |
| Lens underside | 7.38 mm (2.98 mm above the glass) |
| Encoder shaft top | 24.5 mm (`MEASURE`: Alps EC11E18244AU drawing No. 2) |

<img src="images/cad/section_usb_display.png" alt="Cut through the USB port, the lens, the display and the centre screws" width="48%"> <img src="images/cad/section_light_line.png" alt="Cut through one LED, the PCB edge and the light bar" width="48%">

## Case

Nothing below has been printed or milled. The model passes its own checks, and that is all.

<img src="images/cad/hero.png" alt="The printed variant: light top, dark base" width="48%"> <img src="images/cad/hero_aluminium.png" alt="The milled variant, drawn as silver aluminium" width="48%">

- **Shape.** A 90.0 x 90.0 mm slab, 17.5 mm tall, with one flat top face and no text on it. The base
  rim steps in under the top, so a 1.6 mm shadow gap runs all round the case where the two shells meet.
  Round the USB opening the base runs up flush, so the opening sits in a plain pad. A 1.7 mm chamfer
  under the dark base makes it recede.
- **Two shells.** The base holds the PCB on six bosses. A milled case is bonded to GND at S1, over
  the board's H1 ring. The top is the switch plate, the deck and the
  skirt in one piece. Six M2 screws go in from below and are hidden under the feet: M2 x 10 cutting
  their own thread in a printed top (never M2 x 12: it comes through the skin under the dish floor),
  M2 x 8 in tapped holes in a milled one (3.0 mm of thread at the corners, 2.5 mm at the centre).
  Posts under the hot-swap sockets carry the board while the switches are pressed in.
- **PCB thickness.** The board is ordered 1.6 mm thick; board houses allow about 10 %. On a 1.76 mm
  board the top rides 0.16 mm higher, the gap reads 1.66 mm and the lap joint still overlaps 0.44 mm.
  On a thin board foam rings on the base bosses (a guess) still press the PCB up against the top.
  Both are checked, neither is measured.
- **Corners.** The milled outline has continuous-curvature corners (one quintic Bezier each). The
  printed outline has R 7.0 arcs through the same apex, because the top prints standing on a side wall
  and the flatter curve would hang too far over the bed. Two break-away chairs carry the printed
  corners where they leave the bed.
- **Key dish.** The keys stand in a dish with 45° walls. The flat frame around it is 4.275 mm wide on
  the left, the right and in front.
- **Lens.** A 39.0 x 14.6 x 1.0 mm cover glass with a black mask lies 0.12 mm under the top face over
  the display, taped on two ledges. A 5 N press bends it 0.06 mm; acrylic would bend 1.4 mm onto the
  display. Its thickness, its stiffness and the 0.13 mm tape are guesses. A foam pad holds the display
  level under it.
- **Lap joint.** Ridges 0.6 mm tall on the base rim enter grooves in the top. They centre the top and
  close the straight path for light through the joint. The 0.2 mm fit is a guess until a test print.
- **Light line.** One light bar per side stands in a channel in the base wall, behind a 1.0 mm skin, and
  is held by the PCB edge. It shows only in the gap: a line 1.5 mm tall, 1.25 mm back, 0.65 mm of it
  still in sight from 45° above. The gap runs all round, but it lights only along these two 46.5 mm stretches. How
  bright and how even is a guess.
- **Knobs.** 14.4 mm, 36 fine grooves in one band, flat top with a radial pointer line. Each seats on
  the end of its shaft and stands in a shallow well in the top face, so no bushing shows. Three crush
  ribs grip the shaft (a guess). Printed in both variants.
- **Underside.** Two foot strips and a centre pad cover all six screws. The mark is engraved in the flat
  face of a printed base and laser-marked on a milled one.
- **USB-C.** A 13.5 x 7.5 mm opening with rounded corners and a 0.3 mm lead-in: a plug overmould up to
  13.0 x 7.0 mm fits. The PCB edge shows in it; a black solder mask hides it.
- **Size.** 90.0 x 90.0 x 17.5 mm, 35.5 mm from the underside to the top of the knobs. The foot strips
  add 1.2 mm.
- **Two variants.** `cad/exports/print/` for FDM printing, `cad/exports/cnc/` for 3-axis milling with a
  3 mm end mill and a chamfer mill. Light bars, knobs, foot strips and the tilt bar are always printed;
  the lens is cut from sheet.
- **Tilt.** An optional bar under the back of the base tilts the pad by 6°.

<img src="images/cad/exploded.png" alt="Exploded view" width="48%"> <img src="images/cad/shells_inside.png" alt="Both shells from inside" width="48%">

<img src="images/cad/side_profile.png" alt="From the left: the gap between top and base" width="48%"> <img src="images/cad/light_line.png" alt="The left light line drawn glowing; colour and brightness are guesses" width="48%">

Drawings with dimensions: [general arrangement](images/cad/general_arrangement.png),
[CNC base](images/cad/drawing_base.png), [CNC top](images/cad/drawing_top.png).
Printing and milling notes: [cad/README.md](../cad/README.md#printing).
