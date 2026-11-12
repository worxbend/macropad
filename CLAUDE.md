# CLAUDE.md

Guidance for Claude Code in this repository.

## Git commits and pull requests

Do not add Claude or AI attribution to commits or PRs. No `Co-Authored-By` trailer, no "Generated with" line.

## What this is

A 12-key macropad on a custom PCB: RP2354A (RP2350 core, flash in package), two EC11 encoders,
a nice!view display, 8 side-emitting RGB LEDs, one USB-C port. Smaller sibling of `worxbend/macropad-nyxilab`.

- `board.toml` is the single source of truth for positions and GPIOs. PCB, case and firmware pin check read it.
- `pcb/gen/` generates the KiCad board. There is no hand-drawn schematic: `circuit.py` is the circuit.
- `cad/` is the build123d case (FDM and CNC variants).
- `firmware/` is the Rust (embassy) firmware: `core` logic, `fw` binary, `sim` UI renderer, `uf2` converter.

## Commands

```bash
make pcb        # place, autoroute, DRC, fab files (needs Docker)
make cad        # case checks and exports (needs cad/.venv)
make firmware   # tests, clippy, pin check, UF2
make test       # everything checkable without hardware
```

## Rules of the road

- Change a position or a pin in `board.toml`, then rebuild all three: `make pcb cad firmware`.
- `pcb/kicad/macropad.kicad_pcb` is generated. Hand edits are lost on the next `make pcb`; change `pcb/gen/circuit.py`.
- `pcb/gen/layout.py:check_placement` guards flips and rotations. Keep it passing; do not delete an assert to get a build.
- `make pcb-check` must report zero errors before fab files are committed.
- Nothing here has been fabricated or run on hardware yet. Keep `MEASURE` tags until someone measures.
