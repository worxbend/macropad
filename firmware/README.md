# Firmware

Custom Rust firmware for the macropad (RP2354A, [embassy](https://embassy.dev)).

**Nothing here has run on real hardware yet.** The logic is unit-tested on a PC and the image
builds, but no board exists to flash it on. See [Untested](#untested) before you trust it.

## What it does

- 12 keys and two knobs become a USB keyboard plus media keys. No driver needed.
- Four layers: MEDIA, EDIT, NAV, NUM. Press the left knob to go to the next one.
- Each layer gives both knobs their own function. Pressing the right knob is a bindable key.
- The display shows the layer, every key's label, both knob functions, caps/num lock and a
  typing-rate graph. Keys you hold are drawn inverted.
- The side LEDs glow in the layer's colour (solid, breathing or rainbow). Their current is capped
  at 200 mA.

## Build

```sh
rustup target add thumbv8m.main-none-eabihf
make            # tests, lint, and dist/macropad.uf2
```

Single steps: `make test`, `make lint`, `make uf2`, `make ui-images` (renders the display UI to
`../docs/images/ui/`).

## Flash

Both ways go through the one USB-C port. The pad shows up as a USB drive; copy
`dist/macropad.uf2` onto it and it restarts with the new firmware.

1. **First flash, or a bricked pad:** hold the BOOT button (through the hole in the case floor)
   while you plug in the cable.
2. **Later:** hold both knobs down for one second.

## Change the keymap

Edit `LAYERS` in [`core/src/keymap.rs`](core/src/keymap.rs), then `make`. Labels may be up to six
characters; a test fails if one is longer. Key and media codes are in
[`core/src/hid.rs`](core/src/hid.rs).

## Layout

| Crate | Runs on | Contents |
| --- | --- | --- |
| `core` | PC and pad | Debounce, knob decoder, keymap engine, LED effects, display UI, LCD wire format |
| `fw` | pad | Pins, USB, SPI, LED output, the 1 kHz scan loop |
| `sim` | PC | Renders the real UI to PNG |
| `uf2` | PC | ELF to UF2 with the RP2350 family id |

Pins live in [`fw/src/board.rs`](fw/src/board.rs) and must match `../board.toml`;
`make lint` checks that.

## Untested

These are assumptions until a board is built:

- **Display orientation and pixel polarity.** Upside down: set `DISPLAY_ORIENTATION` to
  `Rotated180` in `fw/src/board.rs`.
- **Knob direction.** Assumes contact A leads on a clockwise turn. Wrong way: swap `a` and `b` in
  `KnobScanner::rotation` in `fw/src/inputs.rs`.
- **LED colour order** (assumed green-red-blue, the SK6812 default) and **LED order** along the
  chain.
- **LED current.** The cap assumes at most 20 mA per colour channel.
- **USB enumeration**, the lock-LED report, and the bootloader reboot.
- **UF2 on older chips.** The file has no RP2350-E10 workaround block. RP2354A does not need it;
  an early RP2350 A2 chip might.
- The USB IDs (`1209:0001`) are the pid.codes test pair. Get a real PID before you give boards
  to other people.
