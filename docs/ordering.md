# Ordering the board

How to order the board with the files in `pcb/fab/`. The main walk-through is PCBWay: 5 bare boards,
2 of them with turnkey assembly of the bottom face. JLCPCB is the alternative at the end.

**Nobody has placed this order yet.** The steps follow the files in this repository and the board
houses' order forms as read in November 2026. Menu names on their sites may differ. The first order is
a prototype run: order the smallest quantity.

Why assembled: the 0.4 mm pitch QFN-60 and the side-emitting LEDs are poor parts to solder by hand.
Three bare boards are spares, and a board to measure on.

Read [Before you order](../README.md#before-you-order) first. Parts and stock: [parts.md](parts.md).
The whole prototype plan: [prototype.md](prototype.md).

## What you send

| File | What it is |
|---|---|
| `pcb/fab/macropad-gerbers.zip` | 11 Gerber layers and 2 drill files |
| `pcb/fab/centroid-pcbway.csv` | Centroid file: position, side and rotation of the 75 machine-placed parts. Columns `Designator, Footprint, Mid X, Mid Y, Layer, Rotation, Comment`, in mm from the board's lower-left corner |
| `pcb/fab/bom-pcbway.csv` | Bill of materials: 25 lines, 75 parts, each with quantity, value, package, manufacturer, manufacturer part number and the LCSC number |
| `docs/images/pcb/assembly-bottom.svg` | Polarity drawing of the bottom face |

C13 is in neither file: it is not fitted (see [parts.md](parts.md#machine-placed-bottom-face)). The
two encoders and the display header on the top face are not in the files either; you solder them.

The files in the repository belong to the board in `pcb/kicad/`. `make pcb-fab` checks that: every
Gerber is newer than the board file, the drill file has one hole per via, both BOMs, both placement
files and the circuit name the same parts, C13 is in none of them, every line has a manufacturer part
number, and every placement point lies on its own part. `make pcb-test` checks that the order files
were written from the committed board (its SHA-256 is in `pcb/fab/board-sha256.txt`).

## 1. Check the files (optional, needs Docker)

Skip this if you did not change anything.

1. Run `make pcb-check`. It must end with `Found 0 violations` and `Found 0 unconnected items`.
2. Run `make pcb-fab`. It must end with `assembly files: 75 machine-placed parts, 1 do-not-populate;
   Gerbers, drill file, both BOMs and both placement files agree`.
3. Run `make pcb-test`. It must end with `OK`.
4. Open `pcb/kicad/macropad.kicad_pcb` in KiCad 9 and look at it. A person's eyes are a check too.

## 2. Upload the Gerbers

1. Go to PCBWay's PCB quote page and upload `macropad-gerbers.zip`.
2. Check what the site detected: **4 layers, 84 x 82.5 mm**. If it shows something else, stop.
3. Look at the preview of both faces. Compare with these pictures.

<img src="images/pcb/render-top.png" alt="Bare board, top face" width="48%"> <img src="images/pcb/render-bottom.png" alt="Bare board, bottom face" width="48%">

## 3. Board options

| Option | Choose | Why |
|---|---|---|
| Layers | 4 | Detected from the files |
| Quantity | 5 | 2 assembled, 3 bare |
| Thickness | 1.6 mm | The case model assumes it (`board.thickness` in `board.toml`) |
| Solder mask | Green | The solder mask dams between the QFN-60 pads and at the USB-C are about 0.20 mm. Black mask risks losing them. The PCB edge then shows green inside the case's USB opening; the case pictures draw it black. |
| Silkscreen | White | |
| Surface finish | ENIG | Flat pads for the 0.4 mm pitch QFN-60 |
| Copper weight | 1 oz outer, default inner | No high-current track |
| Min track and gap | 0.15 mm (6 mil) | The board's smallest |
| Min hole | 0.3 mm | The via drill |
| Impedance control | No | Full-speed USB over 15 mm. No impedance was calculated for this board. |
| Product number | "Specify a location" | The bottom silkscreen carries `WayWayWay` for it. PCBWay's help page "Notes of Product No on Your PCB" says to choose this option. Without it the number may go elsewhere and `WayWayWay` stays on the board. |
| Everything else | Default | |

The board's 0.6 mm vias with 0.3 mm drills have a 0.15 mm ring, exactly PCBWay's standard minimum
(capability page, read 2026-11-14). Check their page on the day you order.

## 4. Assembly options

1. Switch on **PCB Assembly**, turnkey: PCBWay buys the parts.
2. Side: **bottom only**. Every machine-placed part is on the bottom face.
3. Quantity assembled: **2** of the 5 boards.
4. Upload `bom-pcbway.csv` as the BOM. Open it in a spreadsheet and save it as `.xlsx` if the form
   asks for that.
5. Upload `centroid-pcbway.csv` as the centroid file, and `assembly-bottom.svg` as the assembly
   drawing.
6. Paste the notes in step 5 into the order's remark field.
7. PCBWay quotes the parts after a review. Read every substitution they propose. U1, L1 and Y1 must
   be the exact parts; passives may be generic.

## 5. Notes to paste into the order

```
Turnkey assembly, bottom side only, on 2 of the 5 boards.

1. Please confirm that solder mask dams stay between the QFN-60 pads (U1, 0.4 mm pitch)
   and at the USB-C receptacle J1. The dams are about 0.20 mm.
2. Please add 5 mm rails on the top and bottom edges only. No breakaway tab between
   X 37 and X 47 mm on the top edge: the USB-C receptacle J1 overhangs that edge by 0.5 mm.
   The LED bodies sit flush with the left and right edges: no rail or tab there.
3. The USB-C shell slots and the encoder slots have 0.20 mm copper rings. Please accept
   these, or tell us before production.
4. L1 (inductor): the part's dot goes on the +1V1 pad, the pad with the silkscreen dot.
5. Y1 (crystal): pin 1 on XIN, pad 1, the marked corner.
6. LED1 to LED8: the light-emitting side faces out of the board edge.
7. No substitutes for U1 (RP2354A), L1 (Abracon AOTA-B201610S3R3-101-T) or
   Y1 (Abracon ABM8-272-T3). Passives may be generic parts of the same value,
   size, voltage rating and dielectric.
8. C13 is not fitted (do not populate). It is not in the BOM or the centroid file.
9. ENC1, ENC2 and J2 on the top side are not fitted. We solder them.
10. The rotations in the centroid file are KiCad's angles, also for the bottom side.
    Please send placement photos or a preview before reflow, so we can check each
    part against assembly-bottom.svg.
11. Please print the PCBWay product number on the "WayWayWay" text on the bottom silkscreen.
```

## 6. Check every part before reflow

This step matters most. Nobody has seen this board in an assembler's preview yet.

**Position.** Each placement point is the centre of the part body, read from the footprint's
fabrication outline. For J1 that is the centre of the receptacle, not of its SMD pad row (4 mm
behind it); for the LEDs it is the centre of the LED body, not of its pads (0.525 mm to the side).
`make pcb-fab` checks that every point lies inside its part's courtyard.

**Rotation.** The centroid file carries KiCad's rotation of each footprint, unchanged, also for the
bottom-side parts. That is a choice, not a proven convention. Community exporters write (180 - r) for
bottom-side parts and disagree with each other on the extra turn per package. So expect some parts to
show up turned by 90° or 180° in the photos or the preview. The table is the checklist: tick every row
before you approve.

Compare with the bottom assembly drawing:

<img src="images/pcb/assembly-bottom.svg" alt="Assembly drawing, bottom face" width="70%">

| Part | What must be right |
|---|---|
| U1 (RP2354A) | Pin 1 dot on the board's pin 1 mark |
| U2 (AP2112K), U3 (USBLC6), U4 (74LVC1T45) | Pin 1. A SOT-23 turned by 180° still fits its pads and is wrong. |
| LED1 to LED8 | The light-emitting side faces out of the board edge |
| L1 (inductor) | The part's dot sits on the +1V1 pad (pad 1), next to the silkscreen dot, at the end toward R7. This follows Raspberry Pi's datasheet (Figs. 25, 26, 28) and its Minimal board; Abracon's drawing labels the dot "+". No substitute. |
| J1 (USB-C) | Mouth at the board edge, shell pins in their slots. Body over its pads, not shifted along the board. |
| Y1 (crystal) | Pin-1 corner on the XIN pad (pad 1). Pads 1 and 3 on the crystal nets, 2 and 4 on ground. A 90° turn puts the crystal across the ground pads and stops the clock. |
| R10 to R13 (3.3 kΩ) | Next to the encoder pins at both back corners |
| C13 | Empty. Its pads may carry a little solder. |
| SW1 to SW12 (hot-swap sockets) | The two contacts on their two large pads, the body between the holes |
| SW13, SW14 (buttons) | All four legs on their pads, as in the drawing |

Write down every rotation the assembler had to fix and open an issue: the lasting fix belongs in
`pcb/gen/fab.py`, not in a hand-edited CSV. The CSV is generated.

## 7. Before you pay

1. The layer count, the size, the mask colour and the quantities (5 boards, 2 assembled) are right.
2. Assembly side is bottom only.
3. All 25 BOM lines are quoted with the right part, and no substitute for U1, L1 or Y1.
4. The notes from step 5 are in the order.
5. You accept that this is an untested design.

## 8. Order the rest

The board house does not place these. Buy them yourself. Numbers, notes and a shopping list with
spares are in [parts.md](parts.md).

1. 2 x Alps EC11E18244AU encoder.
2. 1 x 2.54 mm male header strip (C2337) for the display: five pins of it. Not a socket, and not the
   sockets that come with the nice!view: both are too tall for the case (see parts.md, note 6).
3. 1 x nice!view.
4. 12 x MX-style switches and 12 x 1u keycaps.
5. 6 x M2 socket-head cap screws (M2 x 10 for a printed case, never 12; M2 x 8 for a milled one), a
   1.0 mm cover glass lens with a printed black mask, thin double-sided tape, a 2.5 mm foam pad and six
   0.8 mm foam rings. The feet are printed.
6. A milled case, only after a printed one closes on measured parts ([prototype.md](prototype.md)):
   send `cad/exports/cnc/top.step`, `cad/exports/cnc/base.step`, `cad/exports/drawings/top.pdf`,
   `cad/exports/drawings/base.pdf` and `cad/exports/drawings/engraving_underside.dxf` for the laser
   mark. Do not send the STL files. Part numbers MP-CASE-TOP-CNC and MP-CASE-BASE-CNC, revision A, one
   of each per pad. The STEP files are the master; the sheets carry the tolerances. Material and finish
   are on the sheets: 6061-T6, bead blast, clear anodise to MIL-A-8625 Type II Class 1 (natural
   silver), the six tapped M2 holes masked or chased after anodising, the S1 boss face (top) and the S1
   counterbore seat (base) masked for the case ground, ISO 2768-m with the critical fits toleranced.
   Ask the shop to confirm in its quote: the 1.0 mm light-channel skin, the USB opening's rounds (they
   need a ball-nose or bull-nose cutter), laser marking after anodise, and the two centre tapped holes
   S3 and S4 (⌀1.6 x 4.2 mm, flat bottom, 3.0 mm full thread, 0.8 mm skin under the dish floor).
   `make cad` reads every exported STEP back and fails unless each is one closed solid. That read-back
   uses OCCT, the same kernel that wrote the files; no other CAD or CAM program has opened them here.
   The shop's CAM and design-for-manufacture review is the real check: ask for its findings and read
   them before you pay. Nothing has been milled yet.

## JLCPCB, the alternative

JLCPCB takes the same Gerbers. Its assembly uses its own parts library, so it has its own BOM and
placement file. Nobody has tried this order either.

| File | What it is |
|---|---|
| `pcb/fab/macropad-gerbers.zip` | The same Gerbers |
| `pcb/fab/bom-jlcpcb.csv` | 25 lines, 75 parts, columns `Comment, Designator, Footprint, LCSC Part #` |
| `pcb/fab/cpl-jlcpcb.csv` | Placement list, columns `Designator, Mid X, Mid Y, Layer, Rotation` |

1. **Order number.** The board carries PCBWay's `WayWayWay`. JLCPCB's marker is `JLCJLCJLCJLC`. Set
   `PCBWAY_NUMBER_MARKER` in `pcb/gen/silk.py` to that text and run `make pcb`, or let JLCPCB print
   its number where it likes.
2. **Board.** As in step 3: 4 layers, 1.6 mm, green, ENIG, 5 boards. Order number mark "Specify a
   location" only if you changed the marker.
3. **Assembly.** Bottom side, 2 boards. Let JLCPCB add tooling holes; the board has three fiducials
   on the bottom face. Pick the assembly type that accepts all parts. Guess: the QFN-60, the USB-C
   receptacle and the hot-swap sockets may need the standard type, not the economic one.
4. **Parts.** Upload the BOM and the placement list. Every one of the 25 lines must be matched and in
   stock. The inductor (C42411119) was short on 2026-11-14 (9 in stock, minimum buy 27): see
   [parts.md](parts.md#substitutions-i-made-and-what-to-check). Do not let the site pick a
   replacement on its own. Three parts have no drop-in replacement: the RP2354A, the SK6812 SIDE-A
   and the hot-swap socket.
5. **Preview.** Check every row of the table in step 6 in JLCPCB's placement preview. Drag J1, the
   LEDs and the hot-swap sockets onto their pads if they sit off: whether JLCPCB's library models have
   their origin at the body centre is not known.

JLCPCB can also solder the encoders and the header as through-hole parts. They sit on the top face,
so that makes it a two-sided assembly order. The placement files do not include them.

Next: [assembly.md](assembly.md).
