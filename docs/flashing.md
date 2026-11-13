# Flashing and troubleshooting

How to put firmware on the pad, how to update it, and what to check when something does not work.

**The firmware has never run on a chip.** The image builds, 220 tests pass on a PC, and the UF2
converter checks that the image is bootable. The troubleshooting list is therefore a list of the
design's known guesses, most likely first. It is not a record of faults somebody has seen.

## The firmware file

`firmware/dist/macropad.uf2` is in the repository, built from the stock keymap.

To build it yourself:

1. Install Rust with [rustup](https://rustup.rs).
2. Add the chip's target: `rustup target add thumbv8m.main-none-eabihf`.
3. Run `make firmware` in the repository root.
4. The last lines must say `bootable RP2350 image` and name `dist/macropad.uf2`.

## First flash

Everything goes through the one USB-C port. No debug probe is needed.

1. Unplug the pad.
2. Hold the BOOT button. On a bare board it is on the bottom face, marked `BOOT`. In the case it is
   behind the hole marked `BOOT` in the floor; use a toothpick, not a metal pin.
3. Plug in the USB cable while holding BOOT. Then release.
4. A USB drive named `RP2350` appears.
5. Copy `macropad.uf2` onto the drive. On Linux: `cp firmware/dist/macropad.uf2 /run/media/$USER/RP2350/`
   (the mount point depends on your desktop).
6. The drive disappears and the pad restarts. Expected: splash screen, LEDs wipe on, a keyboard
   named `macropad` appears on the host.

A factory-fresh chip has empty flash and starts the bootloader without the BOOT button.

Instead of unplugging you can hold BOOT, tap RESET, and release BOOT.

## Later updates

1. Hold both knobs down for one second. The display shows `FLASH MODE` and a bar that fills.
   Let go earlier to cancel.
2. The `RP2350` drive appears. The LEDs are off. The display keeps showing what to do.
3. Copy the new `macropad.uf2` onto the drive.

If the new firmware is broken and the two-knob hold no longer works, use the BOOT button as in the
first flash. The bootloader is in the chip's ROM. A bad firmware file cannot remove it.

## Debug probe (optional)

Three test pads on the bottom face carry SWCLK, SWDIO and GND, marked `CLK`, `DIO`, `GND`. There is
no connector: solder three thin wires or use spring pins. They are reachable only with the board out
of the case. Positions: [hardware.md](hardware.md#test-pads). Nobody has attached a probe yet.

## Troubleshooting

Work from the top. Each row names the guess behind the symptom and where to change it.
After a firmware change run `make firmware` and flash again.

### Power and USB

| Symptom | Check |
|---|---|
| Nothing at all, no drive even with BOOT held | 1. Another cable: many USB-C cables carry power only. 2. Measure the `5V` pad against `GND`. No 5 V: the fuse F1, the USB-C port's solder joints, the CC resistors R5 and R6 (a USB-C to USB-C cable gives no power without them). 3. Measure `3V3`. Missing: the regulator U2 and its rotation. 4. Measure `1V1`. Missing: the inductor L1 and its polarity, see [parts.md](parts.md). |
| 5 V, 3.3 V and 1.1 V are right, still no `RP2350` drive | 1. The crystal. It is not the reference part and its load capacitors are a guess; see [parts.md](parts.md). The bootloader needs it for USB. 2. The USB data path: U3 rotation, R7 and R8, the port's data pins. 3. Hold BOOT and measure QSPI_SS at R4: it must be low. |
| The drive appears, the copy works, then nothing | 1. Was the file built for this chip? `make firmware` prints `bootable RP2350 image`. 2. The crystal again: the firmware waits for it, then starts USB. The startup wait is embassy-rp's clock setting (`delay_multiplier` in `embassy_rp::config::Config`). |
| The host drops the pad at plug-in, or a hub port shuts off | About 31 µF sits on the 5 V rail; USB allows 10 µF. Try a different port or a powered hub. The lasting fix is smaller capacitors at C22 and C23; see [the PCB notes](../pcb/README.md). |
| The pad dies when the computer sleeps | The LEDs go off in suspend but the MCU keeps running, above the 2.5 mA a sleeping device may draw. Not fixed in this firmware. |
| The pad restarts by itself | The watchdog restarts a firmware that hangs for 500 ms. Note what you did just before and open an issue. |

### Display

| Symptom | Check |
|---|---|
| Blank | 1. The module is in its socket the right way: glass up, header on the left seen from the front. 2. The header pin order of your module against the board's: MOSI, SCK, 3V3, GND, CS from back to front (`display.header_pins` in `board.toml`, a `MEASURE` value). A different order needs a board change or an adapter. |
| Upside down | Set `DISPLAY_ORIENTATION` to `Orientation::Rotated180` in `firmware/fw/src/board.rs`. |
| Light and dark swapped | Pixel polarity is an untested assumption. The wire format is in `firmware/core/src/sharp_lcd.rs`. |
| Flicker | The panel's VCOM signal alternates at 15 Hz. Raise `FRAME_PERIOD` in `firmware/fw/src/display.rs`. |
| The picture is cut off by the case | The window position is a `MEASURE` value (`display.window_*` in `board.toml`). Measure your module, change the values, run `make cad`. |

### Knobs and keys

| Symptom | Check |
|---|---|
| A knob works backwards | Swap `a` and `b` in `KnobScanner::rotation` in `firmware/fw/src/inputs.rs`. |
| One click does nothing, the next does two things; or every click counts twice | The detent type. The firmware assumes 36 detents and 18 pulses per turn. Change `KNOB_DETENTS` in `firmware/fw/src/board.rs`, and the part table in `tools/check_pins.py` so the board check agrees. |
| Knob clicks get lost on one computer | A host or hub that polls slowly can miss an 8 ms tap. Raise `TAP_PRESS_MS` and `TAP_GAP_MS` in `firmware/core/src/engine.rs`. |
| One key is dead | 1. A bent switch pin. Pull the switch and look. 2. Bridge the socket contacts with tweezers. Still dead: the socket's solder joints. |
| The tap-hold key feels wrong | `TAP_HOLD_MS` in `firmware/core/src/engine.rs`. 200 ms is a guess. |
| A key types the wrong letter | Key codes name positions on a US layout. See [keymap.md](keymap.md). |

### Lights

| Symptom | Check |
|---|---|
| No LED lights | 1. `5V` pad. 2. The level shifter U4 and its rotation. 3. LED1: the chain starts there, and a dead or turned first LED darkens all eight. |
| The chain stops after some LEDs | The first dark LED or the one before it: solder joints, rotation. |
| Wrong colours (red and green swapped) | The colour order is assumed green-red-blue. It is set where `firmware/fw/src/leds.rs` creates the LED driver. |
| The ripple or the knob dot runs the wrong way | The firmware's LED order follows `board.toml`: right side back to front, then left side front to back. If the board is wired otherwise, `firmware/core/src/geometry.rs` is the place. |
| Dim or uneven through the strips | Print the diffusers in clear or natural PETG with 100 % infill. Ripple speed and idle level are guesses made on a monitor; they are constants in `firmware/core/src/lighting.rs`. |
| Light leaks at the seam | The lap joint blocks the seam only along the ridges. It is open at the corners and next to the strips by design. |

## Report what you find

This design needs its first builder's notes. If you measure a `MEASURE` value or fix a guess, open
an issue or a pull request with the number and how you measured it.
