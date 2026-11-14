# Parts and sourcing

Everything needed for one pad: the parts the board house places, the parts you solder, and the case
hardware. How to place the order is in [ordering.md](ordering.md). What to buy for the first
prototype, with spares, is at the end: [Buy for the prototype](#buy-for-the-prototype).

Stock and library type come from the JLCPCB parts search on 2026-11-14. Stock moves fast: check again
before ordering.
"Basic" parts have no setup fee at JLCPCB. "Extended" parts cost a one-time fee per distinct part.
This board has 11 extended parts, not counting the 3.3 kΩ resistor, whose library type JLCPCB's part
page did not show. The fee and the prices are not listed here, because they change.

## Machine-placed (bottom face)

75 parts in 25 BOM lines. The table matches `pcb/fab/bom-jlcpcb.csv` and `pcb/fab/bom-pcbway.csv`,
which `make pcb-fab` checks against the circuit. One footprint more, C13, is left empty: see the
4.7 µF row.

| Part | Value | Qty | JLCPCB # | Type | Stock | Why this one |
|---|---|---|---|---|---|---|
| MCU | RP2354A, QFN-60 | 1 | C41378174 | Extended | 582 | RP2350 with flash inside: no flash chip, no QSPI routing |
| Regulator inductor | AOTA-B201610S3R3-101-T, 3.3 µH | 1 | C42411119 | Extended | 9 | The part Raspberry Pi specifies for the on-chip 1.1 V regulator |
| Crystal | ABM8-272-T3, 12 MHz, 10 pF, 50 Ω, 3225 | 1 | C20625731 | Extended | 724 | See the crystal note below |
| 3.3 V regulator | AP2112K-3.3, SOT-23-5 | 1 | C51118 | Extended | 30 775 | 600 mA, stable with small ceramic capacitors |
| USB ESD | USBLC6-2SC6 | 1 | C7519 | Extended | 42 515 | |
| Level shifter | 74LVC1T45, SOT-26 | 1 | C168856 | Extended | 45 934 | 3.3 V data to the 5 V LEDs |
| USB-C | TYPE-C-31-M-12, 16 pin | 1 | C165948 | Extended | 536 859 | |
| Fuse | nSMD050, 1206, 500 mA | 1 | C69688 | Extended | 20 075 | Resettable |
| Buttons | TS-1187A | 2 | C318884 | Basic | 814 103 | BOOT and RESET |
| RGB LED | SK6812SIDE-A, 4 x 1.6 mm | 8 | C5378721 | Extended | 110 485 | Side-emitting: shines out of the PCB edge |
| Hot-swap socket | HanElectricity CPG151101S11-2 | 12 | C49352235 | Extended | 29 503 | |
| Capacitor | 100 nF 0402 | 21 | C1525 | Basic | 32 M | |
| Capacitor | 1 µF 0402 | 1 | C52923 | Basic | 10 M | |
| Capacitor | 4.7 µF 0402 | 4 | C23733 | Basic | 631 376 | C5 at DVDD pin 23 on the standard footprint; C11, C12, C14 on the wide one. **C13 is not fitted** (do not populate): it would double the 1.1 V regulator's output capacitor. Its footprint stays and is marked DNP; it is in no BOM and no placement file |
| Capacitor | 2.2 µF 0603 | 3 | C23630 | Basic | 3.1 M | 5 V rail: regulator input and one per LED row |
| Capacitor | 10 µF 0603 | 1 | C19702 | Basic | 12 M | 3.3 V regulator output |
| Capacitor | 15 pF C0G 0402 | 2 | C1548 | Basic | 984 188 | |
| Resistor | 1 kΩ 0402 | 2 | C11702 | Basic | 32 M | |
| Resistor | 10 kΩ 0402 | 1 | C25744 | Basic | 21 M | |
| Resistor | 3.3 kΩ 0402, UNI-ROYAL 0402WGF3301TCE | 4 | C25890 | not shown | not looked up | R10-R13: pull-ups on the encoder A and B contacts, 1 mA per closed contact. Alps EC11 sheets give 1 mA as the minimum; the EC11E18244AU's own sheet was not read for this |
| Resistor | 5.1 kΩ 0402 | 2 | C25905 | Basic | 4 M | USB-C CC pull-downs |
| Resistor | 27 Ω 0402 | 2 | C25100 | Extended | 652 465 | USB series resistors |
| Resistor | 33 Ω 0402 | 1 | C25105 | Basic | 3.5 M | |
| Resistor | 330 Ω 0402 | 1 | C25104 | Basic | 1.5 M | R9, in series with the LED data at the level shifter's output |

## Hand-soldered (through-hole, top face)

These are not in the BOM file. The board's top silkscreen names them: `ENC1`, `ENC2`, `J2`.

| Part | Ref | Qty | JLCPCB # | Note |
|---|---|---|---|---|
| Alps EC11E18244AU encoder | ENC1, ENC2 | 2 | C202365 | 20 mm D-shaft (its end is 24.5 mm above the PCB, Alps drawing No. 2), push switch, 36 detents and 18 pulses per turn. 2 544 in stock. The firmware counts one click per debounced edge of contact A (`KNOB_DETENTS = Detents::PerEdgeOfA` in `firmware/fw/src/board.rs`), set for this detent count. Another EC11 variant needs that setting and the part table in `tools/check_pins.py` changed. |
| 1 x 5 male header, 2.54 mm | J2 | 1 | C2337 | BOOMELE 2.54-1*40P: break five pins off the strip. 2.5 mm plastic body, 3 mm tail, 6 mm mating pin. The nice!view is soldered straight onto it, resting on the body, so the glass is 4.4 mm above the PCB (`MEASURE`). Do not use a socket: the listed C50950 (8.5 mm) and the sockets that ship with the nice!view ("adding up to a height of 7mm") hold the glass above the underside of the top, and the case cannot close. See note 6. |

## Plugged in, no solder

| Part | Qty | Where to buy | Note |
|---|---|---|---|
| nice!view | 1 | Keyboard shops (Typeractive, splitkb, and others) | Sharp LS011B7DH03 on a small board, 36 x 14 mm, 5 pins. Soldered to J2, not plugged in: leave its kit sockets out. |
| MX-style switches | 12 | Any keyboard shop | 3-pin or 5-pin. They clip into the 1.5 mm plate and plug into the sockets. The renders show dark housings in every colourway: 2.5 mm of housing shows under each keycap, and a dark one makes the keys read as standing on a shaded bed. |
| Keycaps, 1u | 12 | Any keyboard shop | The renders show DSA. The case check assumes the skirt stays 2.0 mm above the plate when pressed (`MEASURE`), and that it is no wider than 18.3 mm with corners of 0.3 mm or more. |

## Case hardware

| Part | Qty | Note |
|---|---|---|
| M2 socket-head cap screw, ISO 4762 | 6 | 3.8 mm head. Printed case: M2 x 10 only, never M2 x 12; they cut their own thread in the printed top. Milled case: M2 x 8 in all six tapped holes. S1, S2, S5, S6 (corners): `M2x0.4-6H, 3.5 min full thread, drill ⌀1.6 x 4.7, point to 5.18, do not exceed 4.8`. S3, S4 (centre): `M2x0.4-6H, 3.0 min full thread, drill ⌀1.6 x 4.2, flat bottom, do not exceed 4.3`. See the top drawing. |
| Printed or milled base and top | 1 each | `cad/exports/print/` or `cad/exports/cnc/`. 90.0 x 90.0 x 17.5 mm closed, 35.5 mm to the knob tops. Printed corners are R 7.0 arcs; milled corners have continuous curvature. Print the base dark. Print the top with `top_chairs.stl`. A milled pair: 6061-T6, bead blast, clear Type II anodise (natural silver), part numbers MP-CASE-BASE-CNC and MP-CASE-TOP-CNC rev A; see the CNC sheets. |
| Printed light bar | 2 | Natural (clear or milky) translucent PETG, 100 % infill (the material is a guess). `cad/exports/diffuser.stl`. The gap round the case lights only along the two 46.5 mm bars. |
| Printed knob | 2 | `cad/exports/knob.stl`, in both builds. For a 6 mm D-shaft. 14.4 mm wide, 36 grooves, seats on the end of the shaft. |
| Lens | 1 | Cover glass, soda-lime or chemically strengthened, 39.0 x 14.6 x 1.0 mm, corners R 2.5, cut to `cad/exports/drawings/lens.dxf`. Black mask screen-printed on the underside as in `lens_mask.dxf`. The thickness is a guess. Acrylic of the same size bends onto the display under a light press; use it only with the foam pad and a light touch. A 1.0 mm acrylic lens is fine as a stand-in on the printed prototype. |
| Double-sided tape, 0.13 mm or 0.2 mm | 2 pieces of about 1.3 x 14.6 mm | Holds the lens on its two ledges. Measure the lens, then pick the tape that leaves it just under the top face (the thicknesses are guesses). |
| Open-cell foam pad | 1, 10 x 10 x 2.5 mm | Under the display's free end, on the PCB, squeezed to 1.5 mm under the module's parts. Holds the display level under the lens (a guess). |
| Closed-cell foam ring | 6, 0.8 mm thick, 5 mm across, 2.4 mm hole | One on each base boss, under the PCB. Holds a board of any thickness within tolerance against the top (a guess; punch them from foam tape). |
| Printed foot strip | 2 | TPU, or cut from 1.6 mm sheet (a guess). `cad/exports/foot_strip.stl`. They cover the four corner screws. |
| Printed centre pad | 1 | As the strips, 1.4 mm thick. `cad/exports/centre_pad.stl`. It covers the two centre screws. |
| Printed tilt bar (optional) | 1 | `cad/exports/tilt_bar.stl` |
| Thin double-sided tape or glue | a little | For the foot strips and the centre pad. |

Nothing in this table has been printed, milled or cut yet.

The M7 nuts and washers that come with the encoders are not used. The PCB holds the encoders.

## Substitutions I made, and what to check

1. **Crystal.** The board uses Raspberry Pi's reference crystal, the Abracon ABM8-272-T3 (C20625731, 50 Ω
   maximum series resistance), with the reference 15 pF load capacitors and 1 kΩ series resistor.
   An earlier revision used the YXC X322512MMB4SI (C50430, 80 Ω), because JLCPCB then listed almost no
   ABM8-272-T3; the 1 kΩ and 15 pF were tuned for a 50 Ω part. JLCPCB's minimum buy is 23 pieces.
   Nobody has measured the oscillator. If USB does not enumerate on the first boards, look here first.
   The firmware side of the same question: embassy-rp waits for the crystal with a startup delay
   multiplier of 128 (the Pico SDK uses 64 for the reference crystal). It is set through the clock
   settings of `embassy_rp::config::Config`.
2. **RP2354A instead of RP2350A plus flash.** Stock was 1 448 against 5 840 for the RP2350A (C42411118).
   If the RP2354A runs out, the RP2350A needs an external flash chip and a board change.
3. **Hot-swap socket.** The Kailh CPG151101S11 (C2803348) had zero stock. C49352235 is HanElectricity's
   CPG151101S11-2, a different maker's socket. Its drawing has the same dimensions (3.0 mm holes 6.35 mm
   apart, 2.55 x 2.5 mm pads, 1.85 mm high), so the footprint fits. Not tried with a switch.
4. **Inductor polarity.** The AOTA inductor has a dot on one end. The dot goes on the +1V1 pad (L1 pad 1),
   next to the silkscreen dot. Raspberry Pi's datasheet (6.3.8.2, Figs. 25, 26 and 28) and its RP2350A
   Minimal board put the dot on the +1V1 end. Abracon's own drawing labels the dot end "+". The two
   papers disagree; the board follows Raspberry Pi. Mounting on the bottom face does not change the
   rule: the regulator reads as Raspberry Pi's Fig. 26 seen from the bottom. Check in the assembler's
   photos or preview that the part's dot sits on the +1V1 pad. Not verified on a part.
5. **Inductor stock.** JLCPCB had 9 of the AOTA inductor on 2026-11-14, with a minimum buy of 27. Buy the
   27 when you order, or wait for stock. Do not accept an automatic substitute: the 1.1 V regulator
   needs this part.
6. **Display height.** The top's deck leaves room for the nice!view only on a plain male header. Its
   2.5 mm body (LCSC C2337 page) stands on the PCB, the module's 1.0 mm board rests on it and 0.9 mm of
   LCD lies on that (nice!view drawing), so the glass is 4.4 mm up and 2.98 mm under the lens. Sockets
   do not fit: C50950 is 8.5 mm tall (its drawing: 8.5 ± 0.3), and the nice!view's kit sockets add up
   to 7 mm (nicekeyboards.com), which puts the glass at about 10.4 or 8.9 mm, above the deck's 7.0 mm
   underside. For a removable display, the Mill-Max 315-43-105-41-004000 socket with the
   335-10-105-00-160000 header gives 3.94 mm between the boards (Mill-Max PR685, 2.11 mm socket above
   the board). A search on 2026-11-14 found no LCSC stock of the series; Mill-Max's own distributors
   carry it. With that pair set `display_glass_top = 5.84` in
   `board.toml` and run `make cad`; the checks then size the foam pad. J2's footprint (1.0 mm holes,
   1.7 mm pads) takes either. All heights are `MEASURE` values until a module is fitted.

## PCBWay

PCBWay is the main route for the prototype: 5 bare boards, 2 with turnkey assembly of the bottom face.
PCBWay has no fixed parts library. Their turnkey assembly buys from distributors, so every part above can
be sourced. Send the Gerbers, `pcb/fab/centroid-pcbway.csv` and `pcb/fab/bom-pcbway.csv`, which names each
part by manufacturer and manufacturer part number (the `MPN` table in `pcb/gen/circuit.py`); they quote
parts per order. Ask for no substitute for U1, L1 and Y1; passives may be generic. C13 is not fitted, and
ENC1, ENC2 and J2 are yours to solder. It usually costs more than JLCPCB for a board this small and takes
longer. The steps and the notes to paste into the order are in [ordering.md](ordering.md).

## Board order settings

4 layers, 1.6 mm, green solder mask (black risks losing the 0.20 mm mask dams at the QFN-60 and the
USB-C), ENIG. 5 boards, 2 assembled, bottom side only. Minimum track and gap on the board: 0.15 mm.
Smallest drill: 0.3 mm. The full walk-through is in [ordering.md](ordering.md).

## Buy for the prototype

One pad, with spares for the parts you measure, wreck or test on coupons. Nothing here has been bought
for this design yet.

| Item | Qty | Why |
|---|---|---|
| Alps EC11E18244AU | 3 | 2 for the board, 1 to measure (shaft, flat, body) and to test the `knob_bore` coupon on |
| nice!view | 1, or 2 if the budget allows | The second one to measure before the PCB order, without a soldered header |
| 2.54 mm male header strip, C2337 | 1 strip | Five pins for J2; the rest are spares |
| MX-style switches | 14 | 12 for the keys, 2 spares; one for the `mx_cutout` coupon |
| Keycaps, 1u | 12 | Check skirt width and corners against the dish (see the keycap row above) |
| M2 x 10 socket-head cap screws, ISO 4762 | 20 | 6 for the printed case, the rest for the `pilot_holes` coupon. Never M2 x 12 |
| M2 x 8 socket-head cap screws, ISO 4762 | 6 | Only for a milled case |
| Acrylic sheet, clear, 1.0 mm | 1 small sheet | A stand-in lens for the printed case, cut to `lens.dxf`; mask it with black paint or vinyl |
| PETG filament, clear or natural | 1 spool | The two light bars |
| TPU filament | 1 spool | Foot strips and centre pad |
| Filament for the case, dark and light | 1 spool each | The base prints dark |
| Double-sided tape, 0.13 mm and 0.2 mm | 1 roll each | Lens on its ledges; pick after measuring the lens |
| Open-cell foam, 2.5 mm | 1 small sheet | Pad under the display |
| Closed-cell foam tape, 0.8 mm | 1 roll | Six rings on the base bosses |
| Raspberry Pi Debug Probe | 1 (optional) | SWD logs with the `probe` firmware build ([flashing.md](flashing.md#debug-probe-optional)) |
| Bench supply with a current limit, and a USB-C plug breakout | 1 | First power-on in [assembly.md](assembly.md) |
| Digital caliper, 0.01 mm | 1 | The measurement checklist in [cad/README.md](../cad/README.md#measurement-checklist) |
