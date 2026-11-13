# CLAUDE.md

Guidance for Claude Code in this repository.

## Git commits and pull requests

Do not add Claude or AI attribution to commits or PRs. No `Co-Authored-By` trailer, no "Generated with" line.

## What this is

A 12-key macropad on a custom PCB: RP2354A (RP2350 core, flash in package), two EC11 encoders,
a nice!view display, 8 side-emitting RGB LEDs, one USB-C port. Smaller sibling of `worxbend/macropad-nyxilab`.

Nothing has been fabricated, printed or run on hardware. Every document must say so where it matters.

- `board.toml` is the single source of truth for positions and GPIOs. PCB, case and firmware checks read it.
- `pcb/gen/` generates the whole KiCad project. `circuit.py` is the circuit. `route.py` is the routing plan
  (own grid router in `router.py`, no third-party autorouter). `schematic.py` writes a real KiCad schematic
  from `circuit.py`; the build checks the board against it. See `pcb/README.md`.
- `cad/` is the build123d case (FDM and CNC variants), its checks, renders and drawings. See `cad/README.md`.
- `firmware/` is the Rust (embassy) firmware: `core` logic, `fw` binary, `sim` simulator, `uf2` converter.
  See `firmware/README.md` and `firmware/KEYMAP.md`.
- `tools/check_pins.py` and `tools/check_hid.py` tie the firmware to `board.toml` and to the HID descriptors.
- `docs/` holds the builder's guides (`ordering.md`, `assembly.md`, `flashing.md`, `keymap.md`),
  `hardware.md`, `parts.md` and the generated pictures in `docs/images/`.

## Commands

```bash
make help       # list every target
make test       # everything checkable without Docker or hardware (about 2 minutes)
make pcb        # place, route, schematic, DRC, order files (needs Docker, kicad/kicad:9.0.9)
make pcb-test   # netlist self-check and the generator's unit tests (no Docker)
make cad        # case self-test, checks, exports, renders, drawings (needs cad/.venv, about 3 minutes)
make firmware   # tests, fmt, clippy, board and HID checks, UF2
make ui-images  # simulator pictures and demo GIF -> docs/images/ui/ (needs ImageMagick)
make docs-check # every file and picture named in a Markdown file exists
```

`pcb/kicad.sh python3 pcb/gen/build.py order` searches for a new routing order. It takes about
10 minutes and can fail. It is needed only after parts or pins moved.

## Rules of the road

- Change a position or a pin in `board.toml`, then rebuild all three: `make pcb cad firmware`.
- Everything in `pcb/kicad/`, `pcb/fab/`, `pcb/lib/3d/`, `cad/exports/` and `docs/images/` is generated.
  Hand edits are lost on the next build. Change the generator.
- `pcb/gen/layout.py:check_placement` guards flips and rotations. Keep it passing; do not delete an assert to get a build.
- `make pcb-check` must report zero violations, zero unconnected items and zero schematic parity issues
  before order files are committed. `make pcb-place` also fails on any DRC or ERC warning; the one accepted
  finding is named in `pcb/gen/build.py`.
- Never remove or weaken a check or a test to get green. Add a check for what you add.
- Keep `MEASURE` tags until someone measures. Label every guess as a guess.
- `cad/macropad_case/render.py` puts `docs/images/ui/media.png` on the display in the case renders.
  Keep that file's name and its 640 x 272 size.
- `firmware/sim/src/board.rs` mirrors the board outline, knob and display positions; `tools/check_pins.py` guards it.
- Status numbers in `README.md` (tracks, vias, test counts, pairs checked) are copied from check output.
  When a build changes them, update the README in the same change. Run `make docs-check` after moving or renaming a file.
