# Assembly

From an assembled board out of the factory to a closed pad.

**Nobody has built one yet.** These steps are written from the design files. The order is chosen so
that each step can be tested before the next one hides it. If a step does not work as described,
stop and look at [flashing.md](flashing.md#troubleshooting).

## What you need

Parts: see [parts.md](parts.md).

| Tool | For |
|---|---|
| Soldering iron and solder | 2 encoders, 1 socket, the display's header |
| Multimeter | Short-circuit and voltage checks |
| Metal tweezers | Testing the key sockets |
| 1.5 mm hex key | The six M2 socket-head screws |
| Flush cutters | Pins that stand too far out |
| USB-C cable with data lines | Power, flashing, use |

## What is already on the board

JLCPCB places all 71 parts on the bottom face. You solder three parts on the top face. The top
silkscreen says so: `hand-solder on this side: ENC1, ENC2, J2`.

<img src="images/pcb/assembled-top.png" alt="Populated board, top face" width="48%"> <img src="images/pcb/assembled-bottom.png" alt="Populated board, bottom face" width="48%">

The pictures show block models of the parts, not photos.

## 1. Check the bare board

Do this before you plug anything in.

1. Look at the bottom face. Compare with the picture above. Look for a part that is turned,
   missing or lifted, mainly U1 to U4, the LEDs and the USB-C port.
2. Set the multimeter to resistance. Measure between the `GND` test pad and each of `5V`, `3V3`
   and `1V1`. All six test pads are named in the bottom silkscreen; their positions are in
   [hardware.md](hardware.md#test-pads).
3. None of the three may read close to 0 Ω. A short here means: do not plug in. Look for a solder
   bridge. A low but non-zero reading that climbs is a capacitor charging; that is fine.

## 2. First power, first flash

Do this before you solder. A fault is easier to find on a bare board.

1. Plug the board into a computer. Do not hold a button.
2. Expected: a USB drive named `RP2350` appears. A chip with empty flash starts its built-in USB
   bootloader by itself. If no drive appears, hold BOOT (silkscreen `BOOT`, bottom face), tap RESET,
   release BOOT.
3. Measure against the `GND` pad: `5V` about 5 V, `3V3` about 3.3 V, `1V1` about 1.1 V.
4. Copy `firmware/dist/macropad.uf2` to the drive. The board restarts.
5. Expected: the eight side LEDs come on one after another, then breathe in purple.
   The computer sees a new keyboard named `macropad`.

No drive, wrong voltage, no LEDs: go to [flashing.md](flashing.md#troubleshooting).

## 3. Test the key sockets

1. Open a key tester or a text editor on the computer.
2. With the tweezers, bridge the two contacts of each hot-swap socket, one socket after another.
3. Expected on the stock MEDIA layer: the back row sends media keys (previous, play, next, stop),
   the other eight send F13 to F20. A text editor shows nothing for these; a key tester does.
4. Every bridge also starts a white ripple on the side LEDs. That is the quickest sign that a socket works.

## 4. Solder the encoders

Unplug the board first.

1. Put ENC1 and ENC2 into the top face. Each has five pins and two mounting lugs.
2. Press the body flat onto the board. The case assumes the body top 6.5 mm above the board.
3. Solder one pin, check that the encoder still sits flat and square, then solder the rest and
   both lugs.
4. Cut any pin that stands more than 3 mm out of the bottom face. The case floor is 5 mm below.
5. Plug in and test: turning the left knob changes the volume, pressing it changes the layer
   (the LED colour changes). Turning the right knob changes the screen brightness on hosts that
   support it; pressing it mutes.

A knob that works backwards is a firmware setting, not a soldering fault. See
[flashing.md](flashing.md#troubleshooting).

## 5. Solder the display socket and fit the display

Unplug the board first.

1. Solder the 5-pin socket J2 on the top face. Keep it square to the board.
2. If your nice!view came with a loose pin header, solder the header to the module. Guess: most
   shops ship it loose. Follow the shop's instructions for the low-profile pins.
3. Check the pin order before you plug the display in. The board expects, from the back edge to the
   front: MOSI, SCK, 3V3, GND, CS. This order is a `MEASURE` value from a community footprint.
   Compare it with the labels on your module. A module with another order must not be plugged in.
4. Plug the display in. The silkscreen under it says `glass this side up`. The module lies between
   the knobs and reaches from the socket toward the right knob.
5. Plug in the USB cable. Expected: a splash screen with the firmware version, then the MEDIA
   layer with its key labels.

The display is held only by its header. If its free end rattles, put a thin foam pad under it.
The case leaves 0.4 mm between the glass and the deck, on the assumption that the glass is 7.0 mm
above the board.

## 6. Prepare the case parts

Print or mill the parts first: [cad/README.md](../cad/README.md#printing).

<img src="images/cad/exploded.png" alt="Exploded view of the whole pad" width="60%">

1. Clean the six screw holes in the top and the slots in the base of strings and burrs.
2. Try the top on the base without the board. The lap ridges on the base rim must enter the grooves
   in the top without force. The 0.2 mm fit is a guess; a tight printer may need a light pass with
   a file on the ridges.
3. Try a diffuser in its slot. It must drop in from inside, flange behind the wall.
4. Try a switch in one plate cut-out. It must clip in.

## 7. Close the case

<img src="images/cad/section_light_strip.png" alt="Cut through one LED, the PCB edge and the diffuser" width="48%"> <img src="images/cad/shells_inside.png" alt="Both shells from inside" width="48%">

1. Drop one diffuser into each side slot of the base, flange inside.
2. Lower the board onto the six bosses, USB port toward the opening at the back. The board edges
   now hold the diffusers in.
3. Check through the base holes that the BOOT and RESET buttons sit behind their holes.
4. Put the top on. The lap ridges centre it. The knob shafts and the display must pass through
   their openings without touching.
5. Turn the pad over. Fit the six M2 x 10 screws from below: four in the corners, two in the middle.
6. Tighten each screw until the head is seated, no further. In a printed top the screws cut their
   own thread in 1.7 mm holes and strip easily.

## 8. Switches, keycaps, knobs, feet

1. Check each switch for bent pins. Straighten them first; a bent pin folds under the switch.
2. Press each switch through the plate into its socket. Press straight down, near the middle of the
   board first. The board rests on six bosses only, so do not use force.
3. Fit the keycaps.
4. Push the knobs onto the shafts. The pointer groove goes on the side of the shaft's flat.
   A pressed knob stops 0.5 mm above its well floor.
5. Stick the four feet into the recesses on the underside.

<img src="images/cad/underside.png" alt="Underside with screws, feet and the BOOT and RESET holes" width="60%">

Optional tilt bar: leave the two back feet off, glue or tape the bar's pegs into the back recesses,
and stick those two feet onto the bar. Details in [cad/README.md](../cad/README.md#tilt-bar).

## 9. Final test

1. Plug in. Splash screen, then the MEDIA layer. LEDs wipe on, then breathe.
2. Press every key. Its label on the display fills while the key is down.
3. Turn and press both knobs.
4. Hold both knobs for one second. The display shows `FLASH MODE` and the `RP2350` drive appears.
   Unplug and plug in again to return to normal.

## To open it again

1. Pull the knobs and the keycaps.
2. Pull the switches with a switch puller.
3. Remove the six screws and lift the top.

Next: [flashing.md](flashing.md) and [keymap.md](keymap.md).
