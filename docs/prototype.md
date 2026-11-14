# Prototype plan

The staged plan for the first prototype. Each step has a pass test. Do not start a phase before the
one above it passes.

**Nothing in this plan has been done yet.** No part has been measured, no board ordered, no case
printed or milled, no firmware run on a chip. Tick the boxes as you go, and put every number you
measure in an issue or a pull request.

| Phase | What | Pays for |
|---|---|---|
| A | Buy the parts and measure them | Parts only |
| B | Order the PCB from PCBWay | 5 boards, 2 assembled |
| C | Print coupons, then a case | Filament |
| D | Bring up the board | Nothing |
| E | Gate before the milled case | Nothing |
| F | Optional look improvements | Optional |

The shopping list with spares is in [parts.md](parts.md#buy-for-the-prototype).

## Phase A: order parts and measure

Measure before the PCB order. `display.header_x` moves J2 on the board, so a wrong value cannot be
fixed after the boards arrive.

1. [ ] Buy the parts on the [prototype list](parts.md#buy-for-the-prototype): at least the
   encoders, a nice!view, the header strip, the switches and the keycaps.
   **Pass:** the parts are on the desk.
2. [ ] Measure every row of the
   [measurement checklist](../cad/README.md#measurement-checklist), two samples where you have
   them, the worse one counts. **Pass:** each row below has a measured number.

   | Key | Now | Measure on |
   |---|---|---|
   | `stack.display_glass_top` | 4.4 mm | nice!view on the C2337 header on a bare board: PCB top to glass top. Needs a bare board from phase B; until then, measure header body plus module |
   | `display.header_x` | 25.27 mm | nice!view: header pin row centre to the module's short edge |
   | `display.header_pins` | MOSI, SCK, 3V3, GND, CS | nice!view pin labels, back edge to front |
   | `display.window_*` | 27 x 12 mm | nice!view visible glass outline |
   | `display.mask_window_*` | 26 mm long | nice!view lit pixel area, full white frame |
   | `stack.encoder_body_top` | 4.5 mm | EC11E18244AU: mounting face to bushing shoulder |
   | `stack.encoder_shaft_top` | 24.5 mm | EC11E18244AU: mounting face to shaft end |
   | `shaft_flat_length` | 10.0 mm | EC11E18244AU: shaft end to the step where the flat starts |
   | `shaft_flat` | 4.5 mm | EC11E D-shaft across the flat |
   | `encoder_body` | 12.4 x 13.4 mm | EC11E body |
   | `bushing_length` | 7.0 mm | EC11E threaded bushing above the body |
   | `components.ENCODER_PINS` | KiCad footprint | EC11E terminal positions against its drawing |
   | `display_thickness` | 1.9 mm | nice!view: module board bottom to glass top |
   | `display_underside` | 1.0 mm | nice!view: tallest part under the module board |
   | `display_glass` | 30 x 13.6 mm | nice!view LCD glass |
   | `display_board_thickness` | 1.0 mm | nice!view module PCB |
   | `led_body` | 4.0 x 1.6 x 2.0 mm | SK6812SIDE-A, from a spare or the assembled board |
   | `keycap_pressed_bottom`, `keycap_top` | 2.0 mm, 14.5 mm | Your switch and keycap on a plate |
   | `components.MX_*` | 15.6 mm rim, 6.6 mm, 10.2 mm | One MX switch |
   | `components.USB_PLUG_TIP` | 8.25 x 2.4 x 6.5 mm | The cable you will use: metal tip |
   | `usb_plug` | 12.5 x 6.5 mm | The cable you will use: overmould |
   | `components.DISPLAY_ACTIVE_AREA` | 25.2 x 10.71 mm | nice!view lit area (pictures only) |

3. [ ] Put each number in `board.toml` (keys that start with `stack.` or `display.`) or in
   `cad/macropad_case/spec.py` and `components.py`. Replace the `MEASURE` tag with a note of what
   was measured and how. **Pass:** no changed value still carries `MEASURE`.
4. [ ] Rebuild all three: `make pcb cad firmware`. If parts or pins moved on the PCB, also run
   `pcb/kicad.sh python3 pcb/gen/build.py order`. **Pass:** `make pcb-check` reports 0 violations,
   0 unconnected items and 0 schematic parity issues; `make cad` and `make firmware` exit 0. A check
   that fails after a real measurement is a finding: fix the design, do not loosen the check.
5. [ ] Update the status numbers in `README.md` from the check output, then run `make docs-check`.
   **Pass:** `make test` passes.

## Phase B: order the PCB

1. [ ] Order from PCBWay as in [ordering.md](ordering.md): 4 layers, 1.6 mm, green, ENIG, 5 boards,
   2 with turnkey assembly of the bottom face, the notes pasted into the order.
   **Pass:** every row of the checklist in [ordering.md](ordering.md#7-before-you-pay) is ticked.
2. [ ] Read PCBWay's engineering questions and the parts quote. **Pass:** no substitute for U1, L1
   or Y1; every question answered.
3. [ ] Check their placement photos or preview against
   [the bottom assembly drawing](images/pcb/assembly-bottom.svg).
   **Pass:** every row of the table in [ordering.md](ordering.md#6-check-every-part-before-reflow)
   is right, above all L1's dot, Y1's pin 1, the SOT-23 parts and the LED direction.

## Phase C: print

Print with the case's settings ([cad/README.md](../cad/README.md#printing)). Coupons first: an hour
each instead of a day for the whole case.

1. [ ] Print the nine coupons in `cad/exports/print/coupons/`, a brim on `lap_groove` and `usb_top`.

   | Coupon | Pass |
   |---|---|
   | `pilot_holes` | An M2 x 10 starts by hand in the best of the 1.7, 1.8 and 1.9 mm holes, cuts its thread, holds on the second drive, and the boss shows no crack. Set `pilot_diameter` to that size |
   | `mx_cutout` | An MX switch clips in with a click, sits flat, does not rock, and comes out only with a switch puller |
   | `lap_ridge` + `lap_groove` | The groove goes on the ridge by hand, the outer faces stay in line within 0.1 mm, no rocking |
   | `light_channel` | A printed light bar drops in without force, rests on the slot floor, shows 1.25 mm back in the gap, and stays when shaken upside down |
   | `knob_bore` | It stops on the shaft end with its foot 8.9 mm (±0.2) above the PCB top, grips, and does not turn on the flat |
   | `usb_base` + `usb_top` | Held together, the cable's plug goes in and out without touching the edges |
   | `lens_recess_end` | A lens corner on the ledge with tape lies under flush, with an even reveal of 0.1 to 0.2 mm |

   **Pass:** every row passes. A fail names the value to change in the coupon table of
   [cad/README.md](../cad/README.md#print-coupons); change it, run `make cad`, print that coupon again.
2. [ ] Print the base, floor down, in a dark filament. **Pass:** the six counterbore skins cut out
   cleanly; the light bars drop in.
3. [ ] Print the top lying on its skirt (joint face on the bed, supports allowed) as a quick fit
   test. Rotate it in the slicer; the layer checks do not cover this pose. **Pass:** it goes on the
   base by hand, the screws start, the switches clip in.
4. [ ] Print the top standing on its left side wall, as exported, with `top_chairs.stl` and an
   8 mm brim. **Pass:** no failed layer, the chairs snap off, the top face and the dish are clean.
5. [ ] Print the foot strips and the centre pad in TPU. **Pass:** each lies flat in its recess.
6. [ ] Cut a stand-in lens from 1.0 mm clear acrylic to `cad/exports/drawings/lens.dxf` and mask it
   with black paint or vinyl as in `lens_mask.dxf`. **Pass:** it lies under flush on its tape.

## Phase D: bring up the board

Follow [assembly.md](assembly.md#bring-up-order) and [flashing.md](flashing.md).

1. [ ] Look at both assembled boards. **Pass:** no part turned, missing or bridged.
2. [ ] Resistance from `GND` to `5V`, `3V3` and `1V1`. **Pass:** none near 0 Ω.
3. [ ] First power from a 5 V bench supply limited to 150 mA (a guess). **Pass:** the supply stays
   under its limit.
4. [ ] The three rails. **Pass:** about 5 V, 3.3 V and 1.1 V, each within 5 % (a guess for a pass
   line). If you have a scope, write down the 1.1 V ripple.
5. [ ] Plug into a computer, flash `firmware/dist/macropad.uf2`. **Pass:** the `RP2350` drive
   appears, the copy works, the pad restarts as a keyboard named `macropad`.
6. [ ] Hardware test mode (hold K0 while plugging in). **Pass:** every socket closes its own key and
   no other; each LED shows red, green, blue in the named order.
7. [ ] Solder the encoders. **Pass:** in hardware test mode `A` changes once per click, `B` between
   clicks, `SW` fills on a press; in normal mode both knobs turn the right way.
8. [ ] Solder the display. **Pass:** splash with `RESET: POWER-ON`, then the MEDIA layer.
9. [ ] Close the printed case on the board. **Pass:** the final test in
   [assembly.md](assembly.md#13-final-test) passes in the case.

## Phase E: gate before paying for CNC

A milled case costs many times a printed one. Pay for it only when every box here is ticked.

1. [ ] The printed case closes on the measured parts without filing, cutting or force.
2. [ ] Every `MEASURE` value in `board.toml` and `cad/` is replaced by a measured one, and
   `make cad` passes with them.
3. [ ] The machine shop's design-for-manufacture report is read and answered, including the 1.0 mm
   light-channel skin, the USB opening's rounds and the flat-bottom centre holes S3 and S4.
4. [ ] The CNC sheets (`cad/exports/drawings/top.pdf`, `base.pdf`) carry the case-ground masks at S1
   and the anodise masks for the tapped holes, and the shop has confirmed them.

**Pass:** all four ticked. Then order as in [ordering.md](ordering.md#8-order-the-rest), item 6.

## Phase F: optional look improvements

Optional. None is needed for a working pad, and none is designed yet. Each one changes the model and
needs `make cad` and a new coupon or print.

1. A tighter inner USB aperture round the plug.
2. A lens window centred over the display, on a full ledge all round.
3. A light line centred along each side.
4. Metal knobs, or lower knobs. A metal knob needs a round bore, a grub screw and grooves a cutter
   can run out of.
5. Lighter laser type for the underside mark.
