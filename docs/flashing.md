# Flashing and troubleshooting

How to put firmware on the pad, how to update it, and what to check when something does not work.

**The firmware has never run on a chip.** The image builds, 248 tests pass on a PC, and the UF2
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

Everything goes through the one USB-C port. No debug probe is needed. On a new board, do the
bring-up in [assembly.md](assembly.md#bring-up-order) first: look, measure resistance, power it from
a current-limited supply and check the three rails.

1. Unplug the pad.
2. Hold the BOOT button. On a bare board it is on the bottom face, marked `BOOT`. In the case it is
   behind the hole marked `BOOT` in the floor; use a toothpick, not a metal pin.
3. Plug in the USB cable while holding BOOT. Then release.
4. A USB drive named `RP2350` appears.
5. Copy `macropad.uf2` onto the drive. On Linux: `cp firmware/dist/macropad.uf2 /run/media/$USER/RP2350/`
   (the mount point depends on your desktop).
6. The drive disappears and the pad restarts. Expected: splash screen, LEDs wipe on, a keyboard
   named `macropad` appears on the host.

The splash screen's `RESET:` line, under the firmware version, names why the chip started:

| Text | Means |
|---|---|
| `RESET: POWER-ON` | Plugged in (or the supply dipped). |
| `RESET: RESET PIN` | RESET was pressed. |
| `RESET: DEBUGGER` | A debug probe reset the chip. |
| `RESET: WATCHDOG` | The firmware hung or panicked and the watchdog restarted it. |
| `RESET: RESTART` | A deliberate restart. Probably what you see right after a flash, a guess until tried. |
| `RESET: UNKNOWN` | No reset flag was set. Note it in an issue. |

`WATCHDOG` on every start is a reboot loop: see [Troubleshooting](#power-and-usb).

A factory-fresh chip has empty flash and starts the bootloader without the BOOT button.

Instead of unplugging you can hold BOOT, tap RESET, and release BOOT.

## Later updates

1. Hold both knobs down for one second. The display shows `FLASH MODE` and a bar that fills.
   Let go earlier to cancel.
2. The `RP2350` drive appears. The LEDs are off. The display keeps showing what to do.
3. Copy the new `macropad.uf2` onto the drive.

If the new firmware is broken and the two-knob hold no longer works, use the BOOT button as in the
first flash. The bootloader is in the chip's ROM. A bad firmware file cannot remove it.

## Check a new board: hardware test mode

1. Hold key K0 (top left). Plug in the cable. Let go once the screen says `HW TEST`.
2. **Keys.** Press each key. Its box in the 3 x 4 grid fills while it is down; `KEYS` shows the
   same as a hexadecimal number. A box that never fills is a dead key; one that is always filled
   is a short.
3. **Knobs.** The `A`, `B` and `SW` boxes of each knob show the raw contacts, not debounced. Turn
   slowly: `A` changes once per click and stays put between clicks. `B` changes between clicks
   and may rest either way. Press the knob: `SW` fills.
4. **LEDs.** One LED lights at a time: red, green, blue, half a second each, then the next LED.
   The top right corner says which, `LED1 RED` first. LED1 is the back LED on the right side; the
   chain runs clockwise seen from above. A colour other than the one named: the colour order is
   wrong. Another LED: the chain order differs from `firmware/core/src/geometry.rs`.
5. Unplug to leave. The pad sends nothing to the host in this mode, and the two-knob flash hold
   does not work.

## Check a flash with picotool

Optional. Raspberry Pi's `picotool` talks to the boot ROM over USB. It is not installed by this
repository.

- **Install.** Pre-built executables are in Raspberry Pi's
  [pico-sdk-tools releases](https://github.com/raspberrypi/pico-sdk-tools/releases). To build it,
  follow [picotool's BUILDING.md](https://github.com/raspberrypi/picotool/blob/master/BUILDING.md)
  (CMake, the Pico SDK and libusb-1.0). On Linux, its `udev/60-picotool.rules` lets you run it
  without `sudo`.
- **Flash and verify.** Put the pad in drive mode (BOOT button or the two-knob hold), then:

  ```sh
  picotool load -v -x firmware/dist/macropad.uf2
  ```

  `-v` reads the flash back and compares it, `-x` starts the firmware afterwards.
- **Cross-check the UF2 converter once.** `firmware/uf2` is this repository's own converter. Build
  a second UF2 from the same ELF with picotool and compare:

  ```sh
  make firmware
  picotool uf2 convert firmware/target/thumbv8m.main-none-eabihf/release/macropad -t elf \
      /tmp/picotool.uf2 --family rp2350-arm-s
  cmp /tmp/picotool.uf2 firmware/dist/macropad.uf2 && echo identical
  ```

  Identical files settle it. If they differ, compare `picotool info -a` of both files and open an
  issue with the output. Nobody has run this comparison yet.

## Debug probe (optional)

Three test pads on the bottom face carry SWCLK, SWDIO and GND, marked `CLK`, `DIO`, `GND`. There is
no connector: solder three thin wires or use spring pins. They are reachable only with the board out
of the case. Positions: [hardware.md](hardware.md#test-pads). Nobody has attached a probe yet.

**Wiring.** Probe SWCLK to `CLK`, probe SWDIO to `DIO`, probe ground to `GND`. Power the pad from
its USB cable; do not feed power from the probe. Any SWD probe that probe-rs supports should do,
for example Raspberry Pi's Debug Probe (untried here).

**Install probe-rs.** From [probe.rs](https://probe.rs/docs/getting-started/installation/): the
install script, `brew install probe-rs` after `brew tap probe-rs/probe-rs`, `cargo binstall
probe-rs-tools`, or from source with `cargo install probe-rs-tools --locked`. On Linux, add
probe-rs's udev rules as its probe setup page describes. This repository does not install it.

**Run the probe build.**

```sh
cd firmware/fw
cargo run --release --features probe
```

This flashes over SWD with `probe-rs run --chip RP235x` and prints the log: start, reset cause,
test mode, USB state changes, the first display frame and the first LED frame. A panic prints its
message instead of halting quietly. `make -C firmware probe` only builds. The UF2 never contains
the probe build. The watchdog pauses while the probe halts the chip.

## Troubleshooting

Work from the top. Each row names the guess behind the symptom and where to change it.
After a firmware change run `make firmware` and flash again.

### Power and USB

| Symptom | Check |
|---|---|
| Nothing at all, no drive even with BOOT held | 1. Another cable: many USB-C cables carry power only. 2. Measure the `5V` pad against `GND`. No 5 V: the fuse F1, the USB-C port's solder joints, the CC resistors R5 and R6 (a USB-C to USB-C cable gives no power without them). 3. Measure `3V3`. Missing: the regulator U2 and its rotation. 4. Measure `1V1`. Missing: the inductor L1 and its polarity, see [parts.md](parts.md). |
| 5 V, 3.3 V and 1.1 V are right, still no `RP2350` drive | 1. The crystal Y1: its rotation (pin 1 on XIN) and its solder joints. It is Raspberry Pi's reference part with the reference 15 pF and 1 kΩ, but the oscillator is not measured; see [parts.md](parts.md). The bootloader needs it for USB. 2. The USB data path: U3 rotation, R7 and R8, the port's data pins. 3. Hold BOOT and measure QSPI_SS at R4: it must be low. |
| The drive appears, the copy works, then nothing | 1. Was the file built for this chip? `make firmware` prints `bootable RP2350 image`. 2. The crystal again: the firmware waits for it, then starts USB. The startup wait is embassy-rp's clock setting (`delay_multiplier` in `embassy_rp::config::Config`). |
| The host drops the pad at plug-in, or a hub port shuts off | About 7.5 µF sits on the 5 V rail, inside the 10 µF USB allows. Try a different port or cable, then look for a short on the 5 V pad. |
| The pad dies when the computer sleeps | The LEDs go off in suspend, but the eight still draw about 4.8 mA dark and the MCU keeps running: over the 2.5 mA a sleeping device may draw. Accepted for the prototype. The fix is a load switch on the LED supply, a board change. |
| The pad restarts by itself | The watchdog restarts a firmware that hangs for 500 ms. The splash then says `RESET: WATCHDOG`. Note what you did just before and open an issue. A probe build prints the panic message, if it was one. |
| The pad drops back to the `RP2350` drive after every flash | Both knob switches read pressed for 1 s, which is the flash gesture. A short from both `SW` lines to ground, or two stuck switches. Hardware test mode shows it: both `SW` boxes filled without a press. |

### Display

| Symptom | Check |
|---|---|
| Blank | 1. The module is soldered the right way: glass up, header on the left seen from the front. 2. The header pin order of your module against the board's: MOSI, SCK, 3V3, GND, CS from back to front (`display.header_pins` in `board.toml`, a `MEASURE` value). A different order needs a board change or an adapter. |
| Upside down | Set `DISPLAY_ORIENTATION` to `Orientation::Rotated180` in `firmware/fw/src/board.rs`. |
| Light and dark swapped | Pixel polarity is an untested assumption. The wire format is in `firmware/core/src/sharp_lcd.rs`. |
| Flicker | The panel's VCOM signal alternates at 15 Hz. Raise `FRAME_PERIOD` in `firmware/fw/src/display.rs`. |
| The picture is cut off by the case | The window position is a `MEASURE` value (`display.window_*` in `board.toml`). Measure your module, change the values, run `make cad`. |

### Knobs and keys

| Symptom | Check |
|---|---|
| A knob works backwards | Swap `a` and `b` in `KnobScanner::rotation` in `firmware/fw/src/inputs.rs`. |
| One click does nothing, the next does two things; or every click counts twice | The detent type. The firmware assumes 36 detents and 18 pulses per turn and counts each edge of contact A (`Detents::PerEdgeOfA`). Check in hardware test mode that `A` changes once per click. Change `KNOB_DETENTS` in `firmware/fw/src/board.rs`, and the part table in `tools/check_pins.py` so the board check agrees. |
| Clicks get lost when the knob spins fast | Contact A must hold each level for the 5 ms debounce, so about 200 clicks per second is the limit. `DEBOUNCE_SAMPLES` in `firmware/core/src/debounce.rs` sets it, for the keys too. It must stay above Alps' 3 ms chatter; the board check enforces that. |
| Knob clicks get lost on one computer | A host or hub that polls slowly can miss an 8 ms tap. Raise `TAP_PRESS_MS` and `TAP_GAP_MS` in `firmware/core/src/engine.rs`. |
| One key is dead | 1. A bent switch pin. Pull the switch and look. 2. Bridge the socket contacts with tweezers. Still dead: the socket's solder joints. |
| The tap-hold key feels wrong | `TAP_HOLD_MS` in `firmware/core/src/engine.rs`. 200 ms is a guess. |
| A key types the wrong letter | Key codes name positions on a US layout. See [keymap.md](keymap.md). |

### Lights

| Symptom | Check |
|---|---|
| No LED lights | 1. `5V` pad. 2. The level shifter U4 and its rotation. 3. LED1: the chain starts there, and a dead or turned first LED darkens all eight. |
| The chain stops after some LEDs | The first dark LED or the one before it: solder joints, rotation. |
| Wrong colours (red and green swapped) | The colour order is assumed green-red-blue. It is set where `firmware/fw/src/leds.rs` creates the LED driver. Hardware test mode names the colour each LED should show. |
| The ripple or the knob dot runs the wrong way | The firmware's LED order follows `board.toml`: right side back to front, then left side front to back. If the board is wired otherwise, `firmware/core/src/geometry.rs` is the place. |
| Dim or uneven through the strips | Print the diffusers in clear or natural PETG with 100 % infill. Ripple speed and idle level are guesses made on a monitor; they are constants in `firmware/core/src/lighting.rs`. |
| Light leaks in the gap away from the two light lines | The lap joint blocks the joint only along the ridges. It is open at the corners and next to the light bars by design. A light-coloured printed base also glows through its 1.0 mm skin: print the base dark. |

## Report what you find

This design needs its first builder's notes. If you measure a `MEASURE` value or fix a guess, open
an issue or a pull request with the number and how you measured it.
