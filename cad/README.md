# Case

Parametric case for the macropad, written with [build123d](https://build123d.readthedocs.io).
Board dimensions come from [`board.toml`](../board.toml); the case-only dimensions are in
[`macropad_case/spec.py`](macropad_case/spec.py).

**Nothing here has been printed or milled yet.** The model passes its own fit checks, and that is all.
Print one copy and measure before you order a batch or pay for machining.

![hero](../docs/images/cad/hero.png)

The keycaps in the pictures are blocks that cover the full key travel, not real keycap shapes.
The pictures are rough previews drawn with matplotlib; open `exports/assembly.step` for the real thing.

![section](../docs/images/cad/section_usb_display.png)

## Parts

| Part | Count | Material | Files |
| --- | --- | --- | --- |
| `base` | 1 | PLA, PETG or aluminium | `exports/print/base.*`, `exports/cnc/base.*` |
| `top` (switch plate, deck and skirt in one piece) | 1 | PLA, PETG or aluminium | `exports/print/top.*`, `exports/cnc/top.*` |
| `diffuser` | 2 | clear or natural PETG | `exports/diffuser.*` |
| `knob` | 2 | any | `exports/knob.*` |

Outer size: 89.6 x 88.1 mm, 13.6 mm tall at the keys, 17.1 mm at the deck, 30.6 mm to the top of the knobs.

The left and right diffuser are the same part, turned around.

Hardware:

- 6 x M2 x 10 screw, cap or pan head, head no wider than 4 mm
- 4 x stick-on foot, 8 mm
- 2 x M7 nut and washer for the encoders are **not** used: the encoders are held by the PCB

## Build

```bash
cd cad
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .
.venv/bin/python build.py all       # check, then export, then render
.venv/bin/python build.py check     # fit checks only; exits non-zero on any failure
```

`check` writes `exports/checks.json`. It runs three things:

1. **Interference.** Every part against every bought component and every other part, for both variants.
   Any shared volume over 0.05 mm³ fails.
2. **Named clearances.** USB plug to its opening, keycap to deck, display glass under the deck,
   screw engagement, and a few more. Each has a minimum.
3. **Printability.** Each printed part in its bed orientation. Overhanging faces are grouped into
   patches. A patch passes if it is 15 mm or narrower in one direction, so it prints as a bridge.
   This does not tell a bridge from a cantilever; the short cantilevers on the diffuser pass as bridges.

## Printing

The STL files already lie the way they print. No supports.

| Part | Orientation | Notes |
| --- | --- | --- |
| `base` | floor down | The screw counterbores and the foot recesses are short bridges. |
| `top` | standing on its **left side wall** | Use an 8 mm brim: the part is 90 mm tall on a 9 mm wide footprint. |
| `diffuser` | outer face down | The face on the bed is the one you see. |
| `knob` | open end down | |

The top stands on its side because the deck and the key plate are at different heights, so neither face
can lie flat on the bed without supports. Standing up, the plate and the deck print as vertical walls
and the switch cut-outs are 14 mm bridges. The print variant has 45° fillers under both side walls so
the upper wall does not start in mid-air. The lower rounded corners touch the bed on a curve and may
look rough; the brim helps.

Settings: 0.2 mm layers, 3 walls, 0.4 mm nozzle. Print the diffusers with 100 % infill.

The screws cut their own thread in the 1.7 mm holes of the top. Do not overtighten.

## CNC

`exports/cnc/base.step` and `exports/cnc/top.step` are for 3-axis milling, two setups each.

- Every pocket is opened with a 1.5 mm radius, so a 3 mm end mill reaches every internal corner.
  Gaps narrower than 3 mm are left solid: the corner bosses are joined to the walls.
- The switch cut-outs have dog-bone reliefs in the corners. The 14.0 mm square is still clear.
- No undercuts. The print variant's 45° fillers are not in the CNC variant.
- Top, setup 1 (underside up): the two cavity levels, the display relief, all through cuts, the six
  screw holes. Setup 2 (top side up): the step from the deck down to the key plate, the chamfer.
- Base, setup 1 (inside up): the cavity, the USB opening, the diffuser slots, the through holes.
  Setup 2: counterbores, foot recesses, chamfer.
- The screw holes in the top are 1.7 mm for plastic. For aluminium drill 1.6 mm and tap M2.
- The plate is 1.5 mm thick, which MX switches need to clip in.

The diffusers and the knobs stay printed.

## Assembly

1. Drop a diffuser into each side slot of the base, flange inside, behind the wall.
2. Lower the assembled PCB onto the six bosses. Its edges now hold the diffusers in.
3. Put the top on. Fit the six screws from below.
4. Press the switches into the plate, then the keycaps and the knobs.

The nice!view is held only by its header. Put a foam pad under its free end if it rattles.

## Assumptions to measure

These came from datasheets, footprints and photos, not from parts on a desk. Each is one number in
`board.toml` (first three) or in `macropad_case/spec.py`.

| What | Value | Where |
| --- | --- | --- |
| nice!view glass top above the PCB | 7.0 mm | `stack.display_glass_top` |
| nice!view header position and pin order | 1.27 mm from the short edge | `display.header_x` |
| Visible glass area and its offset | 27 x 12 mm, 1.5 mm off centre | `display.window_*` |
| nice!view module thickness | 2.9 mm | `display_thickness` |
| Encoder body footprint | 12.4 x 13.4 mm | `encoder_body` |
| Encoder threaded bushing length | 7.0 mm | `bushing_length` |
| Encoder D-shaft, across the flat | 4.5 mm | `shaft_flat` |
| Encoder terminal positions | from the KiCad EC11E footprint | `components.ENCODER_PINS` |
| Side LED body | 4.0 x 1.6 x 1.6 mm | `led_body` |
| Keycap: skirt above the plate when pressed, top above the plate | 2.0 mm, 14.5 mm | `keycap_*` |
| USB-C plug overmould | 12.5 x 6.5 mm | `usb_plug` |

Not modelled: the MCU and the small parts on the PCB bottom (all under 1 mm, with 5 mm of room), cables,
the screws themselves.
