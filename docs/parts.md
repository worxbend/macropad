# Parts and sourcing

Everything needed for one pad: the parts JLCPCB places, the parts you solder, and the case hardware.
How to place the order is in [ordering.md](ordering.md).

Stock and library type come from the JLCPCB parts search on 2026-11-12. They were not looked up again
since. Stock moves fast: check again before ordering.
"Basic" parts have no setup fee at JLCPCB. "Extended" parts cost a one-time fee per distinct part.
This board has 10 extended parts. The fee and the prices are not listed here, because they change.

## Machine-placed (JLCPCB assembly, bottom face)

71 parts in 22 BOM lines. The table matches `pcb/fab/bom-jlcpcb.csv`, which `make pcb-fab` checks
against the circuit.

| Part | Value | Qty | JLCPCB # | Type | Stock | Why this one |
|---|---|---|---|---|---|---|
| MCU | RP2354A, QFN-60 | 1 | C41378174 | Extended | 1 448 | RP2350 with flash inside: no flash chip, no QSPI routing |
| Regulator inductor | AOTA-B201610S3R3-101-T, 3.3 µH | 1 | C42411119 | Extended | 810 | The part Raspberry Pi specifies for the on-chip 1.1 V regulator |
| Crystal | X322512MMB4SI, 12 MHz, 10 pF, 3225 | 1 | C50430 | Extended | 9 762 | See the crystal note below |
| 3.3 V regulator | AP2112K-3.3, SOT-23-5 | 1 | C51118 | Extended | 5 795 | 600 mA, stable with small ceramic capacitors |
| USB ESD | USBLC6-2SC6 | 1 | C7519 | Extended | 45 001 | |
| Level shifter | 74LVC1T45, SOT-26 | 1 | C168856 | Extended | 45 825 | 3.3 V data to the 5 V LEDs |
| USB-C | TYPE-C-31-M-12, 16 pin | 1 | C165948 | Extended | 544 338 | |
| Fuse | nSMD050, 1206, 500 mA | 1 | C69688 | Extended | 20 188 | Resettable |
| Buttons | TS-1187A | 2 | C318884 | Basic | 828 738 | BOOT and RESET |
| RGB LED | SK6812SIDE-A, 4 x 1.6 mm | 8 | C5378721 | Extended | 111 190 | Side-emitting: shines out of the PCB edge |
| Hot-swap socket | Kailh CPG151101S11-2 | 12 | C49352235 | Extended | 29 766 | |
| Capacitor | 100 nF 0402 | 22 | C1525 | Basic | 33 M | |
| Capacitor | 1 µF 0402 | 1 | C52923 | Basic | 10 M | |
| Capacitor | 4.7 µF 0402 | 4 | C23733 | Basic | 717 287 | |
| Capacitor | 2.2 µF 0603 | 3 | C23630 | Basic | 3.1 M | 5 V rail: regulator input and one per LED row |
| Capacitor | 10 µF 0603 | 1 | C19702 | Basic | 9.8 M | 3.3 V regulator output |
| Capacitor | 15 pF C0G 0402 | 2 | C1548 | Basic | 1 M | |
| Resistor | 1 kΩ 0402 | 2 | C11702 | Basic | 32 M | |
| Resistor | 10 kΩ 0402 | 1 | C25744 | Basic | 22 M | |
| Resistor | 5.1 kΩ 0402 | 2 | C25905 | Basic | 4 M | USB-C CC pull-downs |
| Resistor | 27 Ω 0402 | 2 | C25100 | Extended | 665 508 | USB series resistors |
| Resistor | 33 Ω 0402 | 1 | C25105 | Basic | 3.5 M | |

## Hand-soldered (through-hole, top face)

These are not in the BOM file. The board's top silkscreen names them: `ENC1`, `ENC2`, `J2`.

| Part | Ref | Qty | JLCPCB # | Note |
|---|---|---|---|---|
| Alps EC11E18244AU encoder | ENC1, ENC2 | 2 | C202365 | 20 mm D-shaft, push switch, 36 detents and 18 pulses per turn. 2 553 in stock. The firmware's knob decoder is set for this detent count; another EC11 variant needs `KNOB_DETENTS` changed in `firmware/fw/src/board.rs`. |
| 1 x 5 socket, 2.54 mm | J2 | 1 | C50950 | For the nice!view. Use the low-profile sockets that ship with the display if you have them: the case assumes the glass 7.0 mm above the PCB (`MEASURE`). |

## Plugged in, no solder

| Part | Qty | Where to buy | Note |
|---|---|---|---|
| nice!view | 1 | Keyboard shops (Typeractive, splitkb, and others) | Sharp LS011B7DH03 on a small board, 36 x 14 mm, 5 pins |
| MX-style switches | 12 | Any keyboard shop | 3-pin or 5-pin. They clip into the 1.5 mm plate and plug into the sockets. The renders show dark housings in every colourway: 2.5 mm of housing shows under each keycap, and a dark one makes the keys read as standing on a shaded bed. |
| Keycaps, 1u | 12 | Any keyboard shop | The renders show DSA. The case check assumes the skirt stays 2.0 mm above the plate when pressed (`MEASURE`), and that it is no wider than 18.3 mm with corners of 0.3 mm or more. |

## Case hardware

| Part | Qty | Note |
|---|---|---|
| M2 socket-head cap screw, ISO 4762 | 6 | 3.8 mm head. Printed case: M2 x 10 only, never M2 x 12; they cut their own thread in the printed top. Milled case: M2 x 8 in holes drilled 1.6 mm and tapped M2 to 3.0 mm of full thread (see the top drawing). |
| Printed or milled base and top | 1 each | `cad/exports/print/` or `cad/exports/cnc/`. 90.0 x 90.0 x 17.5 mm closed, 31.0 mm to the knob tops. Printed corners are R 7.0 arcs; milled corners have continuous curvature. Print the base dark. Print the top with `top_chairs.stl`. A milled pair: 6061-T6, bead blast, Type II anodise (a proposal; see the CNC sheets). |
| Printed light bar | 2 | Natural (clear or milky) translucent PETG, 100 % infill (the material is a guess). `cad/exports/diffuser.stl`. The gap round the case lights only along the two 46.5 mm bars. |
| Printed knob | 2 | `cad/exports/knob.stl`, in both builds. For a 6 mm D-shaft. 14.4 mm wide, 36 grooves, seats on the end of the shaft. |
| Lens | 1 | Cover glass, soda-lime or chemically strengthened, 39.0 x 14.6 x 1.0 mm, corners R 2.5, cut to `cad/exports/drawings/lens.dxf`. Black mask screen-printed on the underside as in `lens_mask.dxf`. The thickness is a guess. Acrylic of the same size bends onto the display under a light press; use it only with the foam pad and a light touch. |
| Double-sided tape, 0.13 mm or 0.2 mm | 2 pieces of about 1.3 x 14.6 mm | Holds the lens on its two ledges. Measure the lens, then pick the tape that leaves it just under the top face (the thicknesses are guesses). |
| Open-cell foam pad | 1, 10 x 10 x 5 mm | Under the display's free end, on the PCB, squeezed to 4.1 mm. Holds the display level under the lens (a guess). |
| Closed-cell foam ring | 6, 0.8 mm thick, 5 mm across, 2.4 mm hole | One on each base boss, under the PCB. Holds a board of any thickness within tolerance against the top (a guess; punch them from foam tape). |
| Printed foot strip | 2 | TPU, or cut from 1.6 mm sheet (a guess). `cad/exports/foot_strip.stl`. They cover the four corner screws. |
| Printed centre pad | 1 | As the strips, 1.4 mm thick. `cad/exports/centre_pad.stl`. It covers the two centre screws. |
| Printed tilt bar (optional) | 1 | `cad/exports/tilt_bar.stl` |
| Thin double-sided tape or glue | a little | For the foot strips and the centre pad. |

Nothing in this table has been printed, milled or cut yet.

The M7 nuts and washers that come with the encoders are not used. The PCB holds the encoders.

## Substitutions I made, and what to check

1. **Crystal.** Raspberry Pi's design uses the Abracon ABM8-272-T3 (C20625731). JLCPCB had 1 piece.
   The board uses the YXC X322512MMB4SI (C50430, 9 762 in stock on 2026-11-13): same 3225 package and
   the same 10 pF load rating, with the reference 15 pF load capacitors and 1 kΩ series resistor.
   Its series resistance is listed as 80 Ω; the reference part's was not compared. Nobody has measured
   the oscillator. If USB does not enumerate on the first boards, look here first.
   The firmware side of the same question: embassy-rp waits for the crystal with a startup delay
   multiplier of 128 (the Pico SDK uses 64 for the reference crystal). It is set through the clock
   settings of `embassy_rp::config::Config`.
2. **RP2354A instead of RP2350A plus flash.** Stock was 1 448 against 5 840 for the RP2350A (C42411118).
   If the RP2354A runs out, the RP2350A needs an external flash chip and a board change.
3. **Hot-swap socket.** The plain CPG151101S11 (C2803348) had zero stock; the `-2` variant is the same socket.
4. **Inductor polarity.** The AOTA inductor has a marked end. Confirm against "Hardware design with RP2350"
   that the marked end faces VREG_LX, and check its rotation in JLCPCB's preview.

## PCBWay

PCBWay has no fixed parts library. Their turnkey assembly buys from distributors, so every part above can be
sourced, including the ABM8-272-T3 crystal. Send them the same Gerbers, BOM and placement list; they quote
parts per order. It usually costs more than JLCPCB for a board this small and takes longer.

## Board order settings

4 layers, 1.6 mm, any colour (black hides the PCB edge in the case's USB opening), HASL or ENIG (ENIG is kinder to the 0.4 mm pitch QFN).
Assembly on the bottom side only. Minimum track and gap on the board: 0.15 mm. Smallest drill: 0.3 mm.
The full walk-through is in [ordering.md](ordering.md).
