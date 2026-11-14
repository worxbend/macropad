# Assembly

From an assembled board out of the factory to a closed pad: bring-up first, then soldering, then
the case.

**Nobody has built one yet.** These steps are written from the design files. The order is chosen so
that each step can be tested before the next one hides it, starting with a bare board on a
current-limited supply. If a step does not work as described,
stop and look at [flashing.md](flashing.md#troubleshooting).

## What you need

Parts: see [parts.md](parts.md).

| Tool | For |
|---|---|
| Soldering iron and solder | 2 encoders, the display's header (both ends) |
| Multimeter | Resistance and voltage checks |
| Bench supply with a current limit | First power-on at 5 V |
| USB-C plug breakout (VBUS and GND to terminals) | Feeding the bench supply into the USB-C port |
| Oscilloscope (optional) | Ripple on the 1.1 V rail |
| Metal tweezers | Testing the key sockets |
| 1.5 mm hex key | The six M2 socket-head screws |
| Flush cutters | Pins that stand too far out |
| USB-C cable with data lines | Power, flashing, use |

## What is already on the board

The board house places all 75 parts on the bottom face. C13's footprint stays empty on purpose: it is
not fitted. You solder three parts on the top face. The top silkscreen says so:
`hand-solder on this side: ENC1, ENC2, J2`.

<img src="images/pcb/assembled-top.png" alt="Populated board, top face" width="48%"> <img src="images/pcb/assembled-bottom.png" alt="Populated board, bottom face" width="48%">

The pictures show block models of the parts, not photos.

## Bring-up order

Each step needs the one before it to pass. Stop at the first failure and look at
[flashing.md](flashing.md#troubleshooting).

1. Look at the board.
2. Measure resistance between the rails.
3. First power from a current-limited 5 V supply.
4. Measure the three rails. Scope the 1.1 V ripple if you can.
5. Plug into a computer: the RP2350 boot drive.
6. Flash.
7. Hardware test mode: key sockets and LEDs.
8. Solder the encoders, then test them in hardware test mode.
9. Solder the display.
10. The case.

## 1. Look at the bare board

1. Look at the bottom face. Compare with the picture above and with
   [the assembly drawing](images/pcb/assembly-bottom.svg). Look for a part that is turned, missing or
   lifted, mainly U1 to U4, L1, Y1, the LEDs and the USB-C port.
2. Check the polarity marks: L1's dot on the pad with the silkscreen dot, Y1's pin 1 on XIN, each
   LED's light side facing out of the edge.
3. Look along the QFN-60's pins with a loupe for solder bridges.

## 2. Measure resistance

Do this before you power anything.

1. Set the multimeter to resistance. Measure between the `GND` test pad and each of `5V`, `3V3`
   and `1V1`. All six test pads are named in the bottom silkscreen; their positions are in
   [hardware.md](hardware.md#test-pads).
2. None of the three may read close to 0 Ω. A short here means: do not power it. Look for a solder
   bridge. A low but non-zero reading that climbs is a capacitor charging; that is fine.

## 3. First power from a current-limited supply

1. Set the bench supply to 5.0 V with a current limit of 150 mA. The limit is a guess: high enough for
   the chip in its boot ROM with the LEDs dark, low enough to spare a part with a short.
2. Connect it to the USB-C port through the plug breakout: VBUS to +, GND to -. No computer yet.
3. Switch on. Watch the current. If the supply sits at its limit, switch off at once: something is
   shorted or turned. Go back to section 1.
4. Write down the current. It is the first real number for this board; put it in an issue.

## 4. Measure the three rails

With the bench supply still on, measure against the `GND` pad:

| Pad | Expected | If not |
|---|---|---|
| `5V` | about 5 V | The fuse F1, the USB-C port's solder joints |
| `3V3` | about 3.3 V | The regulator U2 and its rotation |
| `1V1` | about 1.1 V | The inductor L1, its polarity, and the capacitors C11 and C12 |

If you have a scope, look at the `1V1` pad with a short ground spring to the `GND` pad. Write down the
ripple, peak to peak. Nobody has measured it; there is no number to compare it with yet.

Switch the supply off.

## 5. Plug into a computer

1. Plug the board into a computer with a data cable. Do not hold a button.
2. Expected: a USB drive named `RP2350` appears. A chip with empty flash starts its built-in USB
   bootloader by itself. If no drive appears, hold BOOT (silkscreen `BOOT`, bottom face), tap RESET,
   release BOOT.
3. No drive with the rails right: the crystal and the USB data path, see
   [flashing.md](flashing.md#power-and-usb).

## 6. Flash

1. Copy `firmware/dist/macropad.uf2` to the drive. The board restarts. Details and the picotool way:
   [flashing.md](flashing.md#first-flash).
2. Expected: the eight side LEDs come on one after another, then breathe in purple.
   The computer sees a new keyboard named `macropad`.

## 7. Hardware test mode: key sockets and LEDs

The test mode is in the firmware. It shows raw contacts and steps through the LEDs, and it sends
nothing to the computer. [flashing.md](flashing.md#check-a-new-board-hardware-test-mode) describes the
screen; until the display is fitted, use the LEDs and a multimeter.

1. Unplug. Bridge the two contacts of K0's socket (top left seen from the key side) with the tweezers
   and plug in while you hold them. Let go after a second.
2. **LEDs.** One LED lights at a time: red, green, blue, half a second each, then the next one. LED1
   is the back LED on the right side; the chain runs clockwise seen from above. A wrong colour means
   the colour order is wrong; a wrong LED means the chain order is; a dark chain from some LED on means
   that LED or the one before it.
3. **Sockets.** Unplug, plug in normally (no tweezers), and bridge the two contacts of each socket in
   turn. Every bridge starts a white ripple on the side LEDs, and a key tester on the computer shows
   the key: on the MEDIA layer the back row sends previous, play, next, stop; the other eight send
   F13 to F20. With the display fitted later, the test mode shows the same in its key grid.

## 8. Solder the encoders

Unplug the board first.

1. Put ENC1 and ENC2 into the top face. Each has five pins and two mounting lugs.
2. Press the body flat onto the board. The case assumes the body top 4.5 mm above the board and the shaft end 24.5 mm (Alps drawing).
3. Solder one pin, check that the encoder still sits flat and square, then solder the rest and
   both lugs.
4. Cut any pin that stands more than 3 mm out of the bottom face. The case floor is 5 mm below.
5. Plug in and test: turning the left knob changes the volume, pressing it changes the layer
   (the LED colour changes). Turning the right knob changes the screen brightness on hosts that
   support it; pressing it mutes.
6. Once the display is on, check the raw contacts in hardware test mode: turn slowly, `A` changes once
   per click, `B` between clicks; pressing fills `SW`.

A knob that works backwards is a firmware setting, not a soldering fault. See
[flashing.md](flashing.md#troubleshooting).

## 9. Solder the display header and the display

Unplug the board first. The display is soldered on, not plugged in: the case has room for a plain
male header only (see [parts.md](parts.md)). The sockets that come with the nice!view are too tall;
do not use them. Desoldering five pins is the only way to take the display off again.

1. Check the pin order first. The board expects, from the back edge to the front: MOSI, SCK, 3V3,
   GND, CS. It matches the pinout on nicekeyboards.com, but stays a `MEASURE` value until a module is
   checked. Compare it with the labels on your module. A module with another order must not be fitted.
2. Break five pins off the 2.54 mm male header strip (C2337). Push the short ends through J2 from the
   top face, plastic body flat on the board. Solder one pin from the bottom, check that the header
   stands square, then solder the other four.
3. Lay the nice!view on the long pins, glass up, its board resting flat on the header's plastic body.
   The silkscreen under it says `glass this side up`. The module lies between the knobs and reaches
   from the header toward the right knob. Solder the five pins on top of the module.
4. Trim the pins to 1.5 mm above the module's board. The glass is then 4.4 mm above the PCB and the
   lens lies 2.38 mm above the trimmed pins (both `MEASURE` values from the drawings).
5. Plug in the USB cable. Expected: a splash screen with the firmware version and `RESET: POWER-ON`,
   then the MEDIA layer with its key labels. Now run the hardware test mode once more with the screen
   (hold K0 while plugging in) and check the key grid and both knobs.

The display is held only by its header. Stick an open-cell foam pad, 10 x 10 mm and 2.5 mm thick (a
guess), on the PCB under the display's free end, between X 48 and 58 mm. The parts under the module
squeeze it to 1.5 mm. It is not optional: without it one degree of tilt lifts the free end 0.6 mm,
and the module's solder joints carry every knock.

## 10. Prepare the case parts

Print or mill the parts first: [cad/README.md](../cad/README.md#printing). For the first case,
print the coupons before the shells; [prototype.md](prototype.md) has the order and the pass tests.

<img src="images/cad/exploded.png" alt="Exploded view of the whole pad" width="60%">

1. Clean the six screw holes in the top and the two light channels in the base of strings and burrs.
   Printed base: cut the one-layer skin out of each of the six counterbores (a 2 mm drill by hand, or
   a knife). Printed top: a screw must start in each hole by hand; if one does not, run a 1.7 mm drill
   4.2 mm deep through all six. A milled top has tapped M2 holes.
2. Try the top on the base without the board. The lap ridges on the base rim must enter the grooves
   in the top without force. The 0.2 mm fit is a guess; a tight printer may need a light pass with
   a file on the ridges.
3. Try a light bar in its channel. It must drop in from above, lip up and toward the inside.
   Punch six foam rings, 5 mm across with a 2.4 mm hole, from 0.8 mm closed-cell foam tape (a guess).
4. Try a switch in one plate cut-out. It must clip in.
5. Try the lens in its recess. It must drop in and lie just under the top face. The lens is 1.0 mm
   cover glass cut to `cad/exports/drawings/lens.dxf`, with the black mask of `lens_mask.dxf`
   screen-printed on its underside. Measure its thickness: up to 1.1 mm still ends under flush with
   0.13 mm tape. A thinner sheet may take 0.2 mm tape.

## 11. Close the case

<img src="images/cad/section_light_line.png" alt="Cut through one LED, the PCB edge and the light bar" width="48%"> <img src="images/cad/shells_inside.png" alt="Both shells from inside" width="48%">

1. Put a foam ring on each of the six base bosses.
2. Lower the board onto the rings, USB port toward the opening at the back.
3. Drop one light bar into each side channel, between the board edge and the outer skin, lip up and
   toward the inside. It passes the board's edge with 0.15 mm to spare; the edge then holds it in.
4. Check through the base holes that the BOOT and RESET buttons sit behind their holes.
5. Stick a piece of thin double-sided tape (0.13 mm, a guess) on each of the two lens ledges in the
   top. Press the lens in, mask down, window toward the right knob.
6. Put the top on. The lap ridges centre it. The knob shafts must pass through their holes without
   touching, and the display must sit under the lens.
7. Turn the pad over. Fit the six screws from below: four in the corners, two in the middle. Printed
   case: **M2 x 10 only, never M2 x 12**: a 12 mm screw comes through the skin under the dish floor.
   Milled case: M2 x 8; a 10 mm screw bottoms in its tapped hole.
8. Tighten each screw until the head is seated, no further. The top seats on the base rim and the
   rings press the board up against it. In a printed top the screws cut their own thread in 1.8 mm
   holes and strip easily.

## 12. Switches, keycaps, knobs, feet

1. Check each switch for bent pins. Straighten them first; a bent pin folds under the switch.
2. Press each switch through the plate into its socket. Press straight down, near the middle of the
   board first. A post under each socket carries the board, 0.15 mm under it; still, do not use force.
3. Fit the keycaps.
4. Push the knobs onto the shafts until each stops on the end of its shaft. The pointer line goes on
   the side of the shaft's flat. Three ribs in the bore press on the shaft; they need a firm push. A
   pressed knob stops 0.6 mm above the floor of its well.
5. Run the final test below before the next step.
6. Stick the two foot strips and the centre pad into their recesses on the underside, last. They
   cover all six screws.

<img src="images/cad/underside.png" alt="Underside with the two foot strips, the centre pad, the mark and the BOOT and RESET holes" width="60%">

Optional tilt bar: leave the back foot strip off, glue or tape the bar's tongue into the back recess,
and stick that strip onto the bar. Details in [cad/README.md](../cad/README.md#tilt-bar).

## 13. Final test

1. Plug in. Splash screen, then the MEDIA layer. LEDs wipe on, then breathe.
2. Press every key. Its label on the display fills while the key is down.
3. Turn and press both knobs.
4. Hold both knobs for one second. The display shows `FLASH MODE` and the `RP2350` drive appears.
   Unplug and plug in again to return to normal.

## To open it again

1. Pull the knobs and the keycaps.
2. Pull the switches with a switch puller.
3. Peel the two foot strips and the centre pad off the underside. Keep them flat; fresh tape holds
   them again.
4. Remove the six screws and lift the top.

Next: [flashing.md](flashing.md) and [keymap.md](keymap.md).
