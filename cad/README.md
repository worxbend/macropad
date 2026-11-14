# Case

Parametric case for the macropad, written with [build123d](https://build123d.readthedocs.io).
Board dimensions come from [`board.toml`](../board.toml); the case-only dimensions are in
[`macropad_case/spec.py`](macropad_case/spec.py).

**Nothing here has been printed or milled yet.** The model passes its own checks, and that is all.
Print one copy and measure before you order a batch or pay for machining.

![hero](../docs/images/cad/hero.png)

| | |
| --- | --- |
| ![milled, silver](../docs/images/cad/hero_aluminium.png) | ![four colourways](../docs/images/cad/colourways.png) |
| The CNC variant, drawn as silver anodised aluminium with printed graphite knobs. Its corners have continuous curvature. | Chalk and Graphite are the printed variant. Silver and Space grey are the milled one. |
| ![from above](../docs/images/cad/top_plan.png) | ![from the left](../docs/images/cad/side_profile.png) |
| From above: a 90 mm square, the same 4.275 mm frame left, right and in front of the keys. No text on the top face. | From the left: light top over a dark base that recedes under its 1.7 mm chamfer, the gap between them, the strips that lift the body 1.2 mm. |
| ![deck](../docs/images/cad/deck_detail.png) | ![knob](../docs/images/cad/knob_detail.png) |
| The lens lies 0.12 mm under the top face between the two knobs; each knob stands in a shallow well. | A knob in a low raking light: 36 grooves in one band that ends square, plain bands above and below, flat top with a radial pointer line. |
| ![light line at night](../docs/images/cad/light_line.png) | ![cut through a light bar](../docs/images/cad/section_light_line.png) |
| The left light line, drawn glowing and fading out at its ends. Its colour and brightness are guesses; the LEDs are RGB. | Cut across the pad through one LED: the bar stands in the wall behind the outer skin and shows in the gap. |
| ![back](../docs/images/cad/back_usb.png) | ![USB opening](../docs/images/cad/usb_detail.png) |
| Back, with the plug drawn pulled out. | The USB-C opening, 13.5 x 7.5 mm with rounded corners and a 0.3 mm lead-in, seen 20° off square. The gap stops 2 mm short of it on both sides, so it sits in a flush pad. |
| ![underside](../docs/images/cad/underside.png) | ![shells from inside](../docs/images/cad/shells_inside.png) |
| Underside: two foot strips, the centre pad, the mark, BOOT and RESET. No screw shows. | Both shells from inside: lap ridges and light channels in the base, ribs and screw bosses under the plate. |
| ![milled underside](../docs/images/cad/underside_aluminium.png) | |
| Underside of the milled base: BOOT, RESET, the mark and the signature, laser-marked. | |

The pictures come from the same solids as the exports. The display shows `docs/images/ui/media.png`,
the firmware simulator's own picture, laid on the lit area of the glass (25.2 x 10.7 mm, a datasheet value
to measure). The renderer has no clear material, so only the masked part of the lens is drawn and the
display shows through its window; the two cut views draw the whole lens. The band of light on the lens
is a drawn reflection, not a computed one. Product pictures have no edge lines; the cut views, the
exploded view and the print bed keep them. Cut faces are lighter, and hatched on the two shells.
Colours and finishes are proposals. The PCB is drawn with a black solder mask, an order option (the
default is green, and a green edge then shows in the USB opening). Every colourway is drawn with dark
switch housings. The unlit light bar is drawn darker than its colour, because most of the light that
falls on a translucent part passes into it; how it really looks in the gap is a guess. Keycaps,
switches, encoders, the display, the USB parts and the screws are reference shapes drawn from
datasheets, not vendor models.

## What the design is

- **One slab with one line round it.** 90.0 x 90.0 mm, 17.5 mm tall, one flat top face with no text on
  it. The base rim steps in 1.0 mm over its top 1.6 mm, so a shadow gap runs all round the case at the
  joint. The two shells meet at the back of that gap; nothing is left to line up on the outside. At the
  back the gap stops 2.0 mm short of each side of the USB opening: from X 32.95 to 51.05 the base runs
  up flush to the top, so the opening sits in a plain pad and the gap does not jog into it. The top
  rests on 254 mm² of rim (250 mm² milled), on all four sides.
- **Corners.** The CNC outline has one quintic Bezier per corner (control points 10.935, 6.561 and
  2.187 mm from the box corner on both sides): curvature is zero where the curve meets the straight
  side, and the smallest radius is 5.16 mm. The print outline has plain R 7.0 arcs through the same
  apex, **not continuous curvature**: the top prints standing on a side wall, and the Bezier corner
  starts so flat that it would hang more than the 1.5 mm limit over the bed (the arc hangs 1.2).
- **Corners and the key dish.** The corners are as large as the parts round them allow, and the dish
  rim is still not quite concentric with them: the frame round the dish is 0.40 mm wider at its
  corners than at its sides in print, and 0.90 mm when milled (both checked). Truly concentric needs an
  outer corner of about R 9.8. That leaves under 0.8 mm of rim wall at the corners inside the gap, and
  under 0.6 mm of flat between the underside chamfer and the foot strips, which must cover the corner
  screws. The printed dish floor has nearly sharp corners (R 0.2), which brings its rim closer to
  concentric; a mill leaves R 1.5 there.
- **Edges.** 45° only. 0.5 mm on the top rim and the knob rims, 0.3 mm on the USB lead-in, where it
  reads as a fine line. 1.7 mm on the underside, so the base recedes: its straight flank is 5.4 mm tall
  (5.7 mm milled) against the top's 7.7 mm. Not larger: on the corner curves 2.0 mm left under 0.6 mm
  of flat between the chamfer and the ends of the foot strip recesses. 0.3 mm on the lower outer edge
  of the top in both variants. The upper edge of the base's skin at the gap has 0.3 mm in print and is
  left sharp when milled, so on anodised metal only two bright lines run round the case, with the gap
  between them. The milled top keeps its 0.3 mm: with a sharp edge only 0.4 mm of the light bar would
  show from 45° above, under the 0.6 mm the check asks for. The rim inside the gap stays sharp,
  because the top seats on it. Chamfers print without supports in any orientation and a mill cuts
  them with one tool; fillets do neither.
- **Key dish.** The keys stand in a dish: flat floor on the plate, 8.65 mm outside the outer key centres,
  and 45° walls up to the top face. The flat frame around it is 4.275 mm wide on the left, the right and
  in front. The dish is sized for the widest, sharpest keycap skirt it must clear, 18.3 mm with 0.3 mm
  corners (0.94 mm when pressed), not only for the DSA caps in the pictures. A vertical wall with a foot
  was tried first and does not print: the foot is a 55 mm bridge.
- **Lens.** A 39.0 x 14.6 x 1.0 mm cover glass (soda-lime or chemically strengthened, black mask
  screen-printed on its underside) lies in a recess in the top face, 0.12 mm under flush, taped on two
  end ledges. A sheet 0.1 mm too thick still ends under flush. Its corners are R 2.5, its recess R 2.6
  (R 2.65 in print, where the recess has 0.15 mm of fit and 0.17 mm more at the end that prints as a
  bridge, so the reveal after the guessed sag is 0.12 to 0.15 mm all round).
  The mask leaves a 26 x 12 mm window over the pixels: the active area of the nice!view drawing (4.6 mm
  in from the module's header end, 25.3 mm long) plus 0.35 mm at each end, 0.75 mm off the lens centre:
  the board fixes the display, the opening under the lens must cover the whole module, and each end
  ledge must stay 1.0 mm or wider, so the lens can neither move nor be shortened to centre the window.
  The glass sits 2.98 mm under the lens on a plain male header (see the display stack below). A 5 N
  press in the middle bends glass 0.06 mm. Clear cast acrylic of the same size bends 1.4 mm under the
  same press; the gap takes that, but acrylic is not the part drawn.
- **Display stack.** The nice!view is soldered straight onto a plain 2.54 mm male header (LCSC C2337,
  BOOMELE 2.54-1*40P: 2.5 mm plastic body, 3 mm tail, 6 mm mating pin). The header's body stands on the
  PCB and the module rests on it, so its board is 2.5 mm up and, with 1.0 mm of board and 0.9 mm of
  LCD from the nice!view drawing, the glass top is 4.4 mm above the PCB (`display_glass_top`,
  `MEASURE`). The case needs no change for it: the glass lies 2.98 mm under the lens and the trimmed
  pins 2.38 mm. The listed C50950 socket (8.5 mm) and the nice!view's own kit sockets ("adding up to
  a height of 7mm") put the glass at about 10.4 and 8.9 mm, above the 7.0 mm underside of the deck,
  so the top would not close over them. A removable option is the Mill-Max 315-43-105-41-004000
  socket with the 335-10-105-00-160000 header, 3.94 mm between the boards (Mill-Max PR685); set
  `display_glass_top` to 5.84 and rebuild, and the checks size the foam pad again.
- **Light line.** Each side wall of the base has a channel behind a 1.0 mm outer skin. A light bar stands
  in it, in front of the four side LEDs. In the gap the rim is cut away along the channel, so the top
  1.5 mm of the bar shows there, 1.25 mm back, 46.2 mm long. From 45° above, 0.65 mm of it is still in
  sight. In the gap the bar's ends are square and fill the slot to 0.15 mm; below, they are rounded like
  the channel. Its 0.2 mm lip runs its whole length, so the PCB edge does not show past it; bar and lip
  are 1.6 mm deep, eight 0.2 mm layers. The bar goes in after the PCB: lowered from above, it passes
  the board, the LEDs and the base with 0.15 mm to spare (checked). The gap runs all round, but it
  lights only along these two 46.5 mm stretches. The light reaches the slit indirectly: brightness and
  evenness are guesses. A printed base must be dark, or the 1.0 mm skin glows too.
  The bar stays natural, not smoked, and 1.25 mm back, not deeper: a tinted bar takes away light that
  only reaches the slit indirectly, and set further back less than 0.6 mm of it shows from 45° above.
- **Knobs.** 14.4 mm, 17.6 mm tall (Z 8.9 to 26.5), standing 1.1 mm above the floor of a 15.5 mm well
  0.7 mm deep, so no bushing shows under them; the reveal round each knob is 0.55 mm. The end of the
  bore sits on the end of the shaft, so the shaft sets the knob's height: the Alps drawing puts the
  shaft end of the EC11E18244AU 24.5 mm above the PCB (`MEASURE`). Pressed 0.5 mm, a knob keeps 0.6 mm
  to its well floor and 0.9 mm over the bushing; on a shaft 0.3 mm short (a guess) it keeps 0.3 and
  0.6 mm. 36 straight 90° V grooves, 0.35 mm deep, in one band that ends square like a turned
  ring, between two plain 1.6 mm bands; flat top; a radial pointer line 0.9 mm wide and 0.4 mm deep,
  from 2 to 6 mm off the axis, on the side of the D-shaft's flat. Three ribs in the bore reach 0.12 mm
  into the shaft (a guess for PETG or PLA), so a bore printed to size still grips. The knob is not
  lower: the shaft fixes its top, and a higher bottom would show the bushing. A builder who wants a
  lower knob shortens both shafts by the same amount and lowers `encoder_shaft_top` to match. The knobs are
  printed in both builds: they are not designed for turning in aluminium.
- **Underside.** All six screws are hidden. Two foot strips, 84.6 x 7.0 mm with ends concentric to the
  corner screws, lie in 0.4 mm recesses and stand 1.2 mm proud. A centre pad covers the two centre
  screws and stands 1.0 mm proud, so the case never rocks on it. The BOOT and RESET legends, the mark
  `worxbend / macropad` and the centre pad stand on the centre line with equal gaps between them. The
  strips stay on the screw centres and 7.0 mm wide: the flat between them and the underside chamfer is
  0.74 mm in print and 0.57 mm on the milled corner curves, not the same all round, because a narrower
  or moved strip no longer covers the corner counterbores by 1.0 mm. The print variant closes each
  counterbore with one 0.2 mm layer at the roof of its foot recess (the builder cuts it out): a hole in
  that roof would be a hole in a bridge.
- **Lap joint.** Ridges 0.6 mm tall stand on the base rim, inside the wall, along the back, the front and
  the first part of each side. They enter grooves in the top's skirt. The joint centres the top on the base
  and closes the straight path for light through the joint. The ridges stop 10 mm short of the corners
  (where the screw bosses join the walls), at the USB opening and at the light channels. Flank and ends
  are 45°, so they print without support and a chamfer mill cuts them.
- **Structure.** Two ribs run under the plate between the key rows and pass through the two centre screw
  bosses. They start 1.0 mm above the PCB, above the lap grooves. In the print variant each corner boss has
  a web to the back or front wall with a 45° underside, and each centre boss has a small fin: without them
  a boss is a cylinder sticking out sideways while the top prints on its side. The top's corner bosses
  are 5.0 mm wide (a 1.6 mm wall), the centre ones 4.5 mm: in the standing print the corner pilot holes
  lie along the layers, where a screw that cuts its own thread splits a thin boss. Each base boss is
  5.5 mm wide next to the hot-swap sockets and 8 mm wide where it joins the floor.
- **Board support.** The base bosses end 0.4 mm under the PCB. A closed-cell foam ring on each (0.8 mm
  free, a guess) presses the board up against the top's bosses, so a board from 1.44 to 1.76 mm thick
  is held without rattling, and the top always seats on the base rim. Under each hot-swap socket a
  4 x 3 mm post rises from the floor to 0.15 mm under the socket: a switch pressed in after the case is
  closed bends the board onto the post, not onto the socket's solder joints.
- **Legends.** `BOOT`, `RESET` and `worxbend / macropad` on the underside: engraved 0.4 mm deep in the
  print variant, laser-marked on the milled base from `engraving_underside.dxf`. The top face carries
  no text. The print engraving lies on the bed, where the first layer is squeezed into every slot, so
  the letters are drawn bolder: the thinnest slot is 0.72 mm (checked against 0.7 mm).
- **Signature.** A single-line signature reading "Oleksandr B" (34 x 19 mm, line 0.3 mm) and the caption `Signature Edition`
  are laser-marked on the underside of the base, beside the centre pad (`macropad_case/signature.py`).
  It is flat artwork, not geometry: the solids and the STEP/STL files do not contain it. Send
  `exports/drawings/engraving_underside.dxf` to the laser shop; it holds the signature at its place,
  drawn as seen from below and not mirrored, with its origin at datum A (see the DXF note below). Two
  clearance rows check that
  it stays clear of the feet and the label field and that the line is wide enough for a laser.
- **USB-C.** The opening is 13.5 x 7.5 mm, 0.5 mm round a 12.5 x 6.5 mm overmould, so a plug up to
  13.0 x 7.0 mm still enters. Seen from behind its lower corners are R 1.0 (in the base) and its upper
  ones R 0.52, the whole of the top's 0.52 mm bite, so the round starts at the seam and leaves no
  sliver face; the lead-in is 0.3 mm. It is not smaller: a 12.0 x 6.5 mm
  opening would stop the plug the case is drawn for. It is the same on both sides of its centre line
  (checked).
- **Tilt.** An optional bar under the back of the base tilts the pad by 6°. It needs no change to the case.
  Its outer top edge is chamfered, so the underside chamfer runs on down the bar.

Walls: 2.7 mm at the sides, 3.175 mm at the back, 3.725 mm at the front. Floor 2.4 mm.

![exploded](../docs/images/cad/exploded.png)

![section](../docs/images/cad/section_usb_display.png)

The cut passes through the USB port, the lens, the display and the two centre screws under the pad.

![general arrangement](../docs/images/cad/general_arrangement.png)

The drawing is also in [`exports/drawings/`](exports/drawings) as SVG and PDF (A3, 1.6:1). Its dimension
texts are computed from the model.

Two more sheets are for the machine shop: the CNC base and the CNC top, each with a plan from above and
from below, section B-B through the centre screws, the gap and the lap joint at 8:1 and a table of holes
and recesses from datum A. Each sheet has a title block (part number `MP-CASE-BASE-CNC` or
`MP-CASE-TOP-CNC`, revision A, quantity, material, finish), one finish (bead blast, then clear Type II
anodise, Class 1: the natural silver of the renders), ISO 2768-m as the general tolerance, tolerances on
the critical fits (switch cut-outs 14.00 +0.05/0 after anodise, plate 1.50 ±0.05, S1-S6 positions ±0.05,
lap ridge and groove ±0.03, lens recess depth 1.25 ±0.05, USB opening ±0.1), the thread callout
`M2x0.4-6H, 2.5 min full thread, drill ⌀1.6 x 3.7, do not exceed 3.8` and a 3:1 detail of the USB
opening with the cutter its rounds need. The base sheet carries the laser-mark note. Nothing has been
made from these sheets; the anodise build-up is a guess.

| | |
| --- | --- |
| ![base sheet](../docs/images/cad/drawing_base.png) | ![top sheet](../docs/images/cad/drawing_top.png) |

`exports/drawings/` also holds three DXF outlines. `engraving_underside.dxf` is the underside text and
the signature, for laser-marking the milled base. It is drawn as seen from below, not mirrored, with its
origin at datum A: seen from below with the USB edge away from you, datum A is the top-right corner of
the outline box, so a point at (X, Y) in the hole table is at (-X, -Y) in the DXF. Layer `MARK` is what
the laser marks; layer `REF` holds the outline, the six counterbores, the BOOT and RESET holes and the
foot slots, for registration only. The model keeps the artwork as seen from above. `lens.dxf` is the
lens and `lens_mask.dxf` its black mask.

## Parts

| Part | Count | Material | Files |
| --- | --- | --- | --- |
| `base` | 1 | PLA, PETG or aluminium | `exports/print/base.*`, `exports/cnc/base.*` |
| `top` (switch plate, deck and skirt in one piece) | 1 | PLA, PETG or aluminium | `exports/print/top.*`, `exports/cnc/top.*` |
| `diffuser` (light bar) | 2 | natural (clear or milky) translucent PETG (a guess) | `exports/diffuser.*` |
| `knob` | 2 | any, printed in both builds | `exports/knob.*` |
| `lens` | 1 | 1.0 mm cover glass, black mask screen-printed on the underside (thickness is a guess) | `exports/lens.step`, `exports/drawings/lens.dxf`, `lens_mask.dxf` |
| `foot_strip` | 2 | TPU, printed or cut from 1.6 mm sheet (a guess) | `exports/foot_strip.*` |
| `centre_pad` | 1 | as the strips, 1.4 mm | `exports/centre_pad.*` |
| `tilt_bar` (optional) | 1 | any | `exports/tilt_bar.*` |

Size: 90.0 x 90.0 mm, 17.5 mm tall, 35.5 mm from the underside to the top of the knobs. The foot strips
add 1.2 mm.

The left and right light bar are the same part, turned around. The two foot strips are identical.

The light bar is natural, not smoke-grey: the light reaches the slit indirectly, and a tinted bar takes
away more of it. By day it sits 1.25 mm back in the shadow of the gap. How it looks is a guess until one
is printed.

Hardware:

- Print variant: 6 x M2 x 10 socket-head cap screw (ISO 4762, 3.8 mm head). CNC variant: 6 x M2 x 8.
  **Never M2 x 12 in the printed top**: its tip would come through the 0.8 mm skin under the dish floor.
- Double-sided tape for the lens: two pieces of about 1.3 x 14.6 mm, 30 mm² in all. Measure the glass,
  then pick 0.13 mm or 0.2 mm tape so the lens ends just under the top face (the thickness is a guess).
- An open-cell foam pad 10 x 10 mm and 2.5 mm thick, squeezed to 1.5 mm under the parts at the free
  end of the display (a guess)
- Six closed-cell foam rings, 0.8 mm thick, 5 mm across with a 2.4 mm hole, one on each base boss
  (a guess: cut them from foam tape with two punches)
- Thin double-sided tape or glue for the foot strips and the centre pad
- The M7 nuts and washers of the encoders are **not** used: the encoders are held by the PCB

## Build

```bash
cd cad
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .
.venv/bin/python build.py all       # check, export, render, draw
.venv/bin/python build.py check     # checks only; exits non-zero on any failure
.venv/bin/python build.py render    # pictures -> docs/images/cad/
.venv/bin/python build.py draw      # three sheets and three DXF -> exports/drawings/ (PDF and PNG need rsvg-convert)
```

| Module | Holds |
| --- | --- |
| `spec.py` | Every dimension, and the heights derived from `board.toml` |
| `solids.py` | Small helpers, and the two outlines of the case |
| `parts.py` | Base and top |
| `signature.py` | The signature laser-marked on the underside: flat artwork, exported as DXF |
| `small_parts.py` | Light bars, knobs, lens, foot strips, centre pad, tilt bar |
| `components.py` | Reference shapes of the bought parts |
| `checks.py`, `measure.py` | The checks below |
| `printsim.py` | The layer-by-layer print check |
| `selftest.py` | Known-bad shapes that every measuring check must catch |
| `raster.py`, `render.py` | A numpy software renderer and its views |
| `drawings.py` | The three drawing sheets and the DXF outlines |

## Checks

`check` writes `exports/checks.json` and runs five groups.

0. **Self-test.** Before the case is judged, the measuring checks are run on 31 small solids: a sheet
   thinner than the minimum wall, a pocket with sharp corners, a pocket with too small a radius, a slot
   narrower than the tool, a groove in a side wall, a bridge that is too long, a shelf, a wall leaning 60°,
   an outline with arc corners, two loose boxes, a foot recess with an open screw hole in its roof, a
   1 mm ledge 58 mm long between two posts, a letter stroke 0.3 mm wide, a foot over a hole, a step
   between two 0.2 mm layers, a rod lying on the bed with no chair under it, and sound versions of
   each. A check that misses its fault, or flags a
   sound shape, fails the run.
1. **Interference.** Every part against every bought component and every other part, for both variants:
   659 pairs each. Any shared volume over 0.05 mm³ fails. Keycaps are blocks that cover the whole key travel.
   The tilt bar against the back foot strip is skipped, because the bar takes that strip's recess. Each
   knob is a press fit on its shaft: only the volume of its crush ribs may overlap the shaft.
2. **Named clearances.** 84 gaps computed from the dimensions: USB plug to its opening, keycap to the
   dish rim, lens to the glass and how far a 5 N press bends it, screw engagement and thread for both
   screws, the tap drill's point under the dish floor, switch cut-outs and the lens recess after a
   printed bridge sags, the gap and the lap joint on a PCB 10 % too thick, the PCB still clamped on a
   board 10 % too thin, the knob pressed on a shaft 0.3 mm short, the crush rib interference (0.08 to
   0.2 mm), the bushing in its hole after a printed hole shrinks, the posts under the sockets, the foam
   under the display, the lens mask's window over the module, the skin over a tap drill at its depth
   limit, floor under each recess and each engraving, and more.
3. **Measurements on the finished solids.** These do not trust how the model was built.
   - Every part is one valid solid with a volume. A boolean that went wrong shows up here first.
   - Thinnest wall of every part: 3000 surface points per part, a ray through the material from each.
     Minimum 0.8 mm. A sample can miss a very small thin spot. The printed base and tilt bar are measured
     finished: without their engraving and without the 0.2 mm skins the builder cuts out. The layer
     check below sees them with skins.
   - Engraved text: the mean stroke of the thinnest letter (twice its area over its outline) must be
     0.45 mm or more. Text and the knob's pointer line on a face that prints on the bed must be 0.7 mm
     or wider: the squeezed first layer and elephant's foot compensation close about 0.2 mm of a slot.
   - Silhouette: width equals depth, and the frame beside the key dish equals the frame in front of it,
     both within 0.01 mm. On the CNC shells the curvature where a corner curve meets a straight side
     must stay under 0.01 per mm, and the smallest corner radius must be 5.1 mm or more. Only the four
     corners count: the USB opening cuts the base outline and has its own milled radii. Frame swell:
     along the front half of the dish rim, the widest frame minus the narrowest must stay under 0.65 mm
     in print and 1.2 mm milled (see "Corners and the key dish" above for why not zero).
   - Wall around every screw hole, measured on a horizontal cut; 1.5 mm or more round the top's corner
     bosses, whose pilot holes lie along the layers in the print.
   - Light bar retention: the bar is pushed 0.6 mm in six directions and must hit the base, the PCB
     or the top each time.
   - Lens: pushed 0.3 mm down it must hit its ledges, its top must not stand above the top face, and
     the tape under it covers 30 mm² or more.
   - Feet: every counterbore mouth lies under a strip or the pad, and at least 80 % of each foot's face
     rests on the base, not over a hole. The mark keeps 1.0 mm to the edge of the area kept for it.
   - Seat: the top rests on the base on 150 mm² or more, and on each of the four sides.
   - Gap: rays look square into the left side at half the gap's height; the PCB edge shows for no more
     than the light bar's 0.15 mm fit. The bar's visible face ends 0.2 mm or less from its slot.
   - USB: each shell, mirrored about the opening's centre line, differs from itself by under 0.5 mm³.
   - Pressed keycap to the top (with the widest, sharpest skirt the dish must clear), keycap to knob,
     pressed knob to the top, and a pressed knob on a short shaft to the bushing alone, as distances
     between solids.
   - Layers: every horizontal face of the base, the light bar, the knob, the strips, the pad and the
     tilt bar lies on the 0.2 mm layer grid of its print pose (within 0.02 mm). The top is left out:
     it prints standing, and its faces across the layers sit where the board puts the keys.
   - Show faces of the printed top: no outer face that leaves the bed is steeper than 45° unless a
     break-away chair, or the bed, lies 0.5 mm or less under it.
   - Lens reveal in print: the widest minus the narrowest reveal round the lens, after the guessed
     bridge sag, is 0.05 mm or less.
   - Light bar after the PCB: lowered from 12 mm above its seat, it keeps 0.1 mm or more from the board,
     the LEDs and the base all the way down.
   - CNC tool reach: the deepest pocket of each milled shell, from the face it is cut from, is no more
     than 3 times the 3 mm end mill's diameter (a stock cutter has about 9 mm of flute).
   - Lap joint: ridge to groove at least 0.1 mm apart, and the top pushed 0.5 mm left, right, back and
     front must hit a ridge each time. Both variants.
   - CNC variant, tool run: a 3 mm flat end mill is lowered over a 0.1 mm height map of each shell, from
     above and from below. Any place where it stops more than 0.1 mm short of the surface is a corner too
     tight or a slot too narrow. Chamfers and holes smaller than the tool are left out (chamfer mill, drill).
     This check made the lap joint what it is: a ridge all the way round needed a 1 mm groove behind every
     rib end and corner boss, which a 3 mm tool cannot cut.
   - CNC variant: no vertical internal edge without a radius (probe points around every vertical edge),
     smallest concave wall radius at least 1.5 mm, and no face hidden from a tool coming straight down
     or straight up (two height maps). Full round holes are left out of the radius check: they are drilled.
4. **Printability.** Each printed part in its bed orientation, two ways.
   - Faces: overhanging faces are grouped into patches; a patch passes if it is 15 mm or narrower in one
     direction. The part must also put at least 100 mm² on the bed. This alone does not tell a bridge
     from a cantilever.
   - Layers: the part is cut into 0.2 mm layers on a 0.1 mm grid. A layer may rest on the one below up to
     0.3 mm past its edge (about 56° from vertical; the 45° faces of the design need 0.2), or bridge in a
     straight line between two places that rest. What is left hangs from one side. The longest bridge
     must stay under 15 mm and the deepest cantilever under 1.5 mm. The 1.5 mm is a guess: about three
     0.45 mm lines.
   - Aspect: a part may stand no more than 11 times taller than its narrow side on the bed. Above 6,
     `checks.json` marks it `brim_required` (the top: 10.6). The top is checked with its two chairs.

Faults these checks found while the case was drawn, all fixed in the model:

- The top's corner screw bosses hung 4.4 mm from the plate. They are webbed to the walls now.
- The USB tunnel cut a 0.13 mm step into the floor with two sharp corners. Its inner end is rounded now.
- A light channel with rounded ends, cut through the rim at the gap, left a feather edge 0.03 mm thick
  on the rim. In the gap the rim is cut straight through now.
- The mark sunk into the roof of a label pocket was a 59 mm bridge with holes in it. The pocket is gone
  now: the mark is engraved straight into the flat face that lies on the bed.
- A tilt bar tongue round the screw holes was a ring 0.75 mm wide. The tongue lies between the screws now.
- The tilt bar's strip recess came within 0.5 mm of its side faces. The bar is 1.0 mm wider now, with its
  outer top edge chamfered.
- The underside mark at 4.6 mm had a 0.42 mm stroke. It is 5.1 mm now, drawn bolder (0.72 mm).
- The front break-away chair under the printed top was drawn clockwise and came out below the part;
  the show-face check found the front-left corner bare. Both chairs are drawn the same way now.
- The flat between the underside chamfer and the back foot strip recess was measured on a square box
  and read 0.5 mm; on the real milled corner curve it was 0.375 mm. It is measured on each variant's own
  outline now, and the chamfer is 1.7 mm.

### Checks that changed their meaning

These checks from the earlier case measure something else now, because the part they were about is
gone or changed. Their limits are the same or stricter.

| Check | Measures now | Value, minimum |
| --- | --- | --- |
| `keycap_to_deck` | back edge of the back keycaps to the rim of the key dish | 3.1, 0.4 |
| `display_glass_under_deck` | display glass to the underside of the lens | 2.98, 0.2 |
| `bezel_land_under_chamfer`, now `lens_ledge_thickness` | thickness of the two ledges that carry the lens | 0.9, 0.8 (was 0.2) |
| `tilt_bar_to_screw_counterbore` | wall of the bar's 5.6 mm hole around the 4.4 mm counterbore under it | 0.6, 0.5 |
| `cone_inside_floor`, now `screw_skin_inside_floor` | floor left above the print skin that closes each counterbore (the cones are gone) | 1.8, 0.5 |
| `pressed_keycap_to_top` | an 18.3 mm skirt with 0.3 mm corners, pressed, instead of the DSA cap | 0.94, 0.4 |
| `chamfer_to_strip_recess` | measured on the print outline itself, not on a square box; the milled outline has its own row, `cnc_chamfer_to_strip_recess` | 0.74, 0.6 (was 0.4); 0.57, 0.4 |
| `knob_to_well_floor_when_pressed` | as before, with the knob seated on the end of its shaft | 0.6, 0.3 |
| `led_to_light_bar` | LED to the bar's inner face, past the lip | 0.35, 0.1 |
| `screw_tip_to_hole_end` | as before | 0.6, 0.6 (was 0.2) |
| `usb_plug_to_opening` | as before | 0.5, 0.4 (was 0.2) |

`foot_below_underside` is how far a foot strip stands proud (1.2 mm). `knob_to_well_floor_when_pressed`
and `skin_under_knob_well` read the knob wells again. `floor_under_label_engraving` is the floor under
the engraved mark: there is no label pocket any more. `thinnest_wall_print_base` and
`thinnest_wall_tilt_bar` measure the finished parts, without the 0.2 mm skins; the layer check sees the
skins.

## Printing

The STL files already lie the way they print. No supports. The top's two break-away chairs are a
file of their own, `exports/print/top_chairs.stl`, in the same pose: load it with `top.stl` as one object
(most slicers offer this for several files at once) and it lands in place. The print checks run with the chairs.

| Part | Orientation | Notes |
| --- | --- | --- |
| `base` | floor down | Print it dark. The foot recesses are short bridges; one 0.2 mm layer closes each counterbore at the recess roof. Cut the six skins out with a 2 mm drill or a knife before assembly. |
| `top` | standing on its **left side wall** | Use an 8 mm brim: the part is 10.6 times taller than its footprint is wide. Add the two break-away chairs under the left corners (see below). |
| `diffuser` | outer face down | The face on the bed is the one you see in the gap. 100 % infill. Bar and lip are 1.6 mm, eight 0.2 mm layers. |
| `knob` | top face down | The top takes the finish of the bed; the 0.5 mm chamfer takes the elephant's foot. The pointer line is 0.9 mm wide, so it stays open on the first layer. The grooves are vertical; the land between two is 0.56 mm (a guess for a 0.4 mm nozzle). |
| `foot_strip`, `centre_pad` | flat | TPU. Or cut them from sheet. |
| `tilt_bar` | sloped face down | The top comes out 6° off level and shows layer steps; it is hidden under the base. Cut the two skins out of its holes. |

![parts on the bed](../docs/images/cad/print_plate.png)

The top stands on its side so that the top face and the walls of the key dish print as walls, not as
a first layer or a ceiling. The ribs print as vertical walls too, the switch cut-outs are 14 mm bridges
and the lens recess is a 14.9 mm one. The print variant has 45° fillers under both side walls so the
upper wall does not start in mid-air, webs under the screw bosses, and a filler beside each lens rib,
all for the same reason.

A bridge sags. The high-X edge of every opening in the top is a bridge in this pose, so the print's
switch cut-outs are 14.2 mm long in X (the extra 0.2 mm on that side), and its lens recess has 0.15 mm
of fit all round and 0.17 mm more at that end. The 0.2 mm sag is a guess. The knob wells are not grown
the same way: the left well would then come within 0.8 mm of the lens recess. Where the top of each
well's arc sags, the reveal round the knob may read about 0.35 mm instead of 0.55 mm (a guess).

Each left corner leaves the bed on its arc, at up to 90° from vertical for the first layers. Two
break-away chairs carry them: each fills the room between the bed, the corner and the corner's
45° tangent, 0.25 mm off the part, the full height of the top. Print them with the part on the same
brim, and snap them off afterwards. The check finds no show face of the top steeper than 45° that
is not on the bed or on a chair.

Standing on one side means the two sides do not match. How each face of the top prints:

| Face | How it prints |
| --- | --- |
| Top face, walls of the dish on the left, the back and the front, back and front faces | Vertical walls: the best finish on the part |
| Left side face | On the bed: bed texture |
| Right side face | Last layers: top-layer infill |
| Left corners | Leave the bed on a curve, carried by the two chairs up to 45°: expect a witness line where each chair breaks off |
| Right corners | Close as a dome: layer steps show; print them at 0.1 mm |
| Dish wall on the right | A 54 mm long 45° overhang on the show face |
| Dish wall on the left | A 45° upskin: 0.2 mm layers step it visibly; print it at 0.1 mm |
| Dish floor | Vertical: as the top face |

Settings: 0.2 mm layers; 0.1 mm layers from board X -3.0 to 5.3 and from X 78.7 to 87.0, that is from
bed height 0 to 8.3 mm and from 81.7 to 90.0 mm (the corners and both dish walls), 3 walls and 4 round the screw bosses,
0.4 mm nozzle, seam on the joint face (the skirt's underside at Z = 0), elephant's foot compensation
0.15 mm, ironing off. If both sides must match, sand and paint: there is no print orientation that
gives one finish all round.

The engraved text is 0.4 mm deep, on the face that lies on the bed. Its letters are drawn bolder than
the font, so the thinnest slot is 0.72 mm (measured on the artwork): the first layer is squeezed into
each slot and closes about 0.2 mm of it (a guess).

The screws cut their own thread in the 1.8 mm holes of the top. A hole printed lying down comes out about
0.15 mm small (a guess), so expect 1.65 mm; a hole under 1.6 mm splits the boss. If a screw will not start,
run a 1.7 mm drill 4.2 mm deep through the six holes first. Do not overtighten. Use M2 x 10 only:
an M2 x 12 screw comes through the 0.8 mm skin under the dish floor.

## CNC

`exports/cnc/base.step` and `exports/cnc/top.step` are for 3-axis milling, two setups each.

- The outline corners are free curves, not arcs. Take them from the STEP file.
- Every pocket is opened with a 1.5 mm radius, so a 3 mm end mill reaches every internal corner.
  Gaps narrower than 3 mm are left solid: the corner bosses are joined to the walls.
- The switch cut-outs have dog-bone reliefs in the corners. The 14.0 mm square is still clear.
- No undercuts, except the USB opening's rounds: their axes run along Y, so they need a ball-nose or
  bull-nose cutter of R 1.0 (base) and R 0.52 or smaller (top) in a 3D finishing pass; the sheets have a
  detail of it. The print variant's 45° fillers, boss webs and text are not in the CNC variant.
- The lap grooves in the top open toward the cavity. A flat end mill clears them; a chamfer mill cuts the
  45° outer wall and leaves the conical ends drawn in the model.
- A 90° chamfer mill cuts everything that is at 45°: the rims, the edges at the gap, the walls of the
  key dish and the USB lead-in. The dish walls are 3.5 mm deep: they need a cutter of 8 mm or more with
  a tip flat of 0.5 mm or less (checked), in several passes. Where two faces of the dish or of a lead-in
  meet, the tool leaves a small radius instead of the sharp mitre in the model.
- Top, setup 1 (underside up): the cavity levels around the ribs and the lens ribs, the through cuts
  for the switches and the bushings, the six screw holes, the lower rim chamfer. Setup 2 (top side up):
  the key dish, the lens recess and then the lens opening with the same 3 mm end mill, down to Z 6.35
  (2.15 mm deep), so the long walls of the recess and the opening come from one setup with no step
  between them; the knob wells; the top rim chamfer. Hold the part for setup 2 on a fixture plate
  through the six M2 holes or in soft jaws cut to the outline: the 2.7 mm skirts will not take vise
  pressure.
- Base, setup 1 (inside up): the cavity in four levels round the bosses and the socket posts, the USB
  opening, the through holes and the rim step that makes the gap. Cut the light channels last, after
  the cavity is roughed: 3 mm 3-flute end mill, 0.2 mm radial steps, full depth in two passes. Each
  channel leaves a free 1.0 mm skin that chatters if it is slotted in one pass. The skin's top edge
  stays sharp. Setup 2 (underside up): counterbores, foot recesses, underside chamfer. Sit the base on
  a plug fixture that fills the cavity, 0.1 mm smaller all round and 4 mm tall, so the plug backs up
  both skins; hold it with an M2 screw through each of the six holes into the fixture, or in soft jaws
  cut to the outline below the gap. A plain vise across X crushes the skins, and the curved outline has
  no parallel flats to clamp. A mill needs no skin over the counterbores.
- The deepest pocket of either shell is 7.0 mm from the face it is cut from, 2.3 times the 3 mm cutter
  (checked against 3.0).
- Material and finish (nothing has been milled): 6061-T6. Bead blast all over (120 to 150 grit glass
  bead), then anodise to MIL-A-8625 Type II, Class 1 (clear, not dyed), 8 to 12 µm: the natural silver
  of the renders. Space grey stays a render colourway only. Mask the six tapped M2 holes, or chase them
  with an M2 6H tap after anodising. Anodise grows each face by about 0.004 to 0.006 mm (a guess: half
  the coating); the toleranced fits on the sheets hold after anodise. Break unmarked edges 0.05 mm. The
  0.3 mm chamfers are cosmetic: measure them after blasting. The same block is on both CNC sheets.
- Screws: M2 x 8 in tapped blind holes, called out as `M2x0.4-6H, 2.5 min full thread, drill ⌀1.6 x
  3.7, do not exceed 3.8`. 2.5 mm of thread plus three pitches (1.2 mm) is the 3.7 mm hole, as PCBWay's
  tapped-hole guide asks. The 118° point ends at 4.18 mm, 0.82 mm under the dish floor; at the 3.8 mm
  limit it leaves 0.72 mm (checked against 0.7). The screw takes 1.9 mm of thread (an M2 nut is 1.6 mm
  tall) and ends 0.6 mm before the full thread does.
- Every exported STEP and STL is read back after `export` (`macropad_case/roundtrip.py`): one valid,
  closed solid per part file and 81 in `assembly.step`, no free edges, volume within 0.1 % of the part
  in memory and of its STL, which must be watertight, and the STEP product named. The milled parts
  must also have no face under 0.05 mm² and no edge under 0.01 mm. The product names are
  `MP-CASE-BASE-CNC rev A` and `MP-CASE-TOP-CNC rev A`.
- Why the check exists: OCCT's STEP writer leaves out, without a warning, every face that touches an
  offset curve. Offsetting the CNC outline's Bezier corners made such curves, and `base.step` came out
  as two open shells without the rim the top seats on. `solids.offset_sketch` now rebuilds those faces
  on B-spline copies of their edges (within 0.00003 mm), so no offset curve reaches a solid.
- The plate is 1.5 mm thick, which MX switches need to clip in.

The light bars, the knobs, the foot strips and the tilt bar stay printed, in both builds. The knobs are
not designed for turning: a metal knob needs a round bore, a grub screw and grooves a cutter can run out
of, and none of that is drawn. The pictures of the milled variant show graphite printed knobs.

## Assembly

1. Print variant: cut the six skins out of the counterbores in the base.
2. Put a foam ring on each of the six base bosses.
3. The display is soldered to its header on the PCB (see `docs/assembly.md`). Stick the foam pad on
   the PCB under the display's free end.
4. Lower the assembled PCB onto the six bosses.
5. Drop a light bar into each side channel, between the PCB edge and the outer skin, lip up and toward
   the inside. The board's edge now holds it in. No tape is needed.
6. Stick the two tape pieces on the lens ledges of the top and press the lens in, mask down, window
   toward the right knob.
7. Put the top on. The lap ridges find their grooves and centre it. Fit the six screws from below.
8. Press the switches into the plate, then the keycaps and the knobs. Push each knob on until it stops
   on the end of its shaft. The pointer line goes on the side of the shaft's flat.
9. Stick the two foot strips and the centre pad into their recesses, last. They cover the screws.
   To open the case again, peel them off first.

The nice!view is held only by its header. The foam pad under its free end is not optional: squeezed
from 2.5 to 1.5 mm under the module's parts, it keeps the display level under the lens.

### Tilt bar

![tilt](../docs/images/cad/tilt.png)

Cut the two skins out of the bar's holes. Leave the back foot strip off the base. Glue or tape the
bar's tongue into the empty back recess, then stick that strip into the recess on the bar.
The two holes in the bar keep the back corner screws reachable once the strip is peeled off, and the
bar leaves the BOOT and RESET holes free. The pad then rests on its front strip and on the bar.

## Assumptions to measure

These came from datasheets, footprints and photos, not from parts on a desk. Each is one number in
`board.toml` (the rows that name `stack.` or `display.`), in `macropad_case/spec.py`, in `macropad_case/components.py` or, for the
picture colours, in `macropad_case/render.py`.

| What | Value | Where |
| --- | --- | --- |
| nice!view glass top above the PCB, on a plain male header | 4.4 mm | `stack.display_glass_top` |
| nice!view header position and pin order | 1.27 mm from the short edge | `display.header_x` |
| Glass frame on the PCB silkscreen and the simulator's screen position | 27 x 12 mm, 1.5 mm off centre | `display.window_*` |
| Lens mask window over the pixels | 26 x 12 mm, 0.75 mm off centre | `display.mask_window_*`, `display.window_width` |
| nice!view module, board bottom to glass top, and parts under the board | 1.9 mm, 1.0 mm | `display_thickness`, `display_underside` |
| Encoder body top and shaft end above the PCB (Alps drawing No. 2) | 4.5 mm, 24.5 mm | `stack.encoder_body_top`, `stack.encoder_shaft_top` |
| nice!view glass outline and board thickness (pictures only) | 30 x 13.6 mm, 1.0 mm | `display_glass`, `display_board_thickness` |
| Encoder body footprint | 12.4 x 13.4 mm | `encoder_body` |
| Encoder threaded bushing length | 7.0 mm; the PCB's block model in `pcb/gen/models.py` draws 5.0 mm. The case takes the larger | `bushing_length` |
| Encoder shaft length tolerance (a guess) | 0.3 mm short | `shaft_length_tolerance` |
| Encoder D-shaft, across the flat | 4.5 mm | `shaft_flat` |
| Encoder terminal positions | from the KiCad EC11E footprint | `components.ENCODER_PINS` |
| Side LED body (Opsco datasheet) | 4.0 x 1.6 x 2.0 mm | `led_body` |
| Keycap: skirt above the plate when pressed, top above the plate | 2.0 mm, 14.5 mm | `keycap_*` |
| Keycap shape in the pictures | DSA: 12.7 mm top, 7.4 mm tall | `keycap_profile` |
| MX switch housing above the plate | 15.6 mm rim, 6.6 mm tall, stem to 10.2 mm | `components.MX_*` |
| MX plate clips clear the 2 mm ribs | 1.5 mm from cut-out to rib | `rib_width` |
| USB-C plug overmould | 12.5 x 6.5 mm | `usb_plug` |
| USB-C plug tip (pictures only) | 8.25 x 2.4 x 6.5 mm | `components.USB_PLUG_TIP` |
| Lit area of the display (pictures only) | 25.2 x 10.71 mm | `components.DISPLAY_ACTIVE_AREA` |
| Deepest ledge that prints without support | 1.5 mm | `max_cantilever` |
| Lap joint fit | 0.2 mm on the size, 0.13 mm between the flanks | `lap_fit` |
| Lens sheet (a guess) | cover glass, 1.0 mm thick, E 70 GPa | `lens`, `lens_modulus` |
| Fingertip load on the lens (a guess) | 5 N in the middle | `lens_press_load` |
| Lens tape (a guess) | 0.13 mm thick | `lens_tape` |
| Sheet thickness tolerance (a guess) | +0.1 mm | `checks.LENS_SHEET_TOLERANCE` |
| Sag of a printed bridge (a guess) | 0.2 mm | `print_bridge_sag` |
| Printed hole lying down comes out small by (a guess) | 0.15 mm | `print_hole_shrink` |
| Full thread a bottoming tap leaves in a 3.7 mm hole (a guess) | 3.0 mm | `cnc_full_thread` |
| Display header pins once trimmed | 1.5 mm above the module board | `header_pin_height` |
| Foam pad under the display (a guess) | 10 x 10 mm, 2.5 mm free, squeezed to 1.5 mm | `display_foam` |
| Foam rings on the base bosses (a guess) | 0.8 mm free, 0.4 mm of room on a 1.6 mm board | `boss_ring` |
| Hot-swap socket body, for the posts under it | from the Kailh footprint | `socket_post_offset` |
| Widest keycap skirt the dish must clear | 18.3 mm, 0.3 mm corners | `keycap_worst_skirt` |
| Foot strips and centre pad (a guess) | TPU, 1.6 mm and 1.4 mm thick | `foot_strip`, `centre_pad_thickness` |
| Knob grooves (a guess for a 0.4 mm nozzle) | 36 grooves, 0.35 mm deep, 0.56 mm land | `knob_grooves`, `knob_groove_depth` |
| Crush ribs in the knob bore (a guess) | three, 1.0 mm wide, 5 mm long, 0.12 mm into the shaft | `knob_crush_rib`, `knob_rib_interference` |
| Engraved slot lost to the first layer (a guess) | about 0.2 mm | `checks.MIN_BED_ENGRAVING` |
| Anodise growth per face (a guess) | 0.01 to 0.02 mm | CNC notes above |
| Light bar material (a guess) | natural translucent PETG | parts table above |
| Light through the slit (a guess, nothing was simulated) | enough to read as a line | `gap_height`, `light_channel_reach` |
| Glow colour and brightness in `light_line.png` (a guess) | warm white | `render.GLOWING_DIFFUSER` |
| Colours and finishes in the pictures (proposals) | Chalk, Graphite, Silver, Space grey | `render.COLOURWAYS` |

A pressed keycap with an 18.3 mm skirt and 0.3 mm corners keeps 0.94 mm to the dish wall at the four
dish corners. Wider or squarer skirts: check your keycaps.

The PCB may be up to 10 % thicker or thinner than 1.6 mm. On a 1.76 mm board the top rides 0.16 mm
higher: the gap reads 1.66 mm and the lap ridges still overlap their grooves by 0.44 mm (both checked).
On a 1.44 mm board the foam rings still press it up against the top's bosses (checked).

Not modelled: the MCU and the small parts on the PCB bottom (all under 1 mm, with 5 mm of room), cables,
the two pieces of lens tape and the mask on the lens. The foam pad and the foam rings are drawn as
the blocks they are squeezed to.

### Measurement checklist

Every value tagged `MEASURE` in `board.toml` and `cad/`, with what to put a tool on. Nothing on this
list has been measured yet. Use a 0.01 mm digital caliper unless the row says otherwise; measure two
samples where you have them and take the worse one.

After a change: in `board.toml`, run `make pcb cad firmware`; in `cad/macropad_case/spec.py` or
`cad/macropad_case/components.py`, run `make cad`. A check that fails after a real measurement is a
finding: fix the design, do not loosen the check. Keep the `MEASURE` tag until the number comes from
a part, then replace it with a note of what was measured and how.

| Key | Now | Measure on | Tool | Update | Drives |
| --- | --- | --- | --- | --- | --- |
| `stack.display_glass_top` | 4.4 mm | nice!view soldered to the C2337 header on a bare board: PCB top face to glass top | Caliper depth rod or height gauge | `board.toml` | `display_glass_under_deck` (0.2), `lens_to_glass_under_press`, `header_pins_under_lens` |
| `display.header_x` | 25.27 mm (1.27 mm in) | nice!view: header pin row centre to the module's short edge | Caliper | `board.toml` | J2 position on the PCB (`make pcb-place`), `display_module_inside_opening`, clash check |
| `display.header_pins` | MOSI, SCK, 3V3, GND, CS | nice!view: pin labels from the back edge to the front | Eyes and a continuity tester against the module's traces | `board.toml` | J2 nets in `pcb/gen/circuit.py`: ERC and schematic parity in `make pcb-place`, silkscreen |
| `display.window_*` | 43.5, 11.0; 27 x 12 mm | nice!view: visible glass outline, relative to the module centre | Caliper | `board.toml` | Silkscreen frame, simulator (`make -C firmware check-pins`), `display_window_inside_module` |
| `display.mask_window_*` | 41.25; 26 mm long | nice!view showing a full white frame: lit pixel area | Caliper, or a photo with a ruler in frame | `board.toml` | `lens_mask.dxf`, `lens_mask_window_inside_glass`, `lens_mask_window_inside_module` |
| `stack.encoder_body_top` | 4.5 mm | EC11E18244AU: mounting face to bushing shoulder | Caliper | `board.toml` | `encoder_body_under_deck` (0.3), clash check |
| `stack.encoder_shaft_top` | 24.5 mm | EC11E18244AU: mounting face to shaft end | Caliper | `board.toml` | `knob_to_well_floor_short_shaft`, `knob_pocket_to_bushing_*`, knob height |
| `encoder_body` | 12.4 x 13.4 mm | EC11E body, X and Y | Caliper | `cad/macropad_case/spec.py` | Clash check (encoder against the top) |
| `bushing_length` | 7.0 mm | EC11E threaded bushing above the body | Caliper | `cad/macropad_case/spec.py` | `knob_pocket_to_bushing_*`, clash check |
| `shaft_flat` | 4.5 mm | EC11E D-shaft across the flat | Caliper or micrometer | `cad/macropad_case/spec.py` | Knob bore and `knob_rib_interference` |
| `display_thickness` | 1.9 mm | nice!view: module board bottom to glass top | Caliper | `cad/macropad_case/spec.py` | `header_pins_under_lens`, clash check |
| `display_underside` | 1.0 mm | nice!view: tallest part or folded flex under the module board | Caliper depth rod | `cad/macropad_case/spec.py` | Clash check (display against the PCB and the foam pad) |
| `display_glass` | 30 x 13.6 mm | nice!view: LCD glass length and width | Caliper | `cad/macropad_case/spec.py` | `lens_mask_window_inside_glass`, pictures |
| `display_board_thickness` | 1.0 mm | nice!view module PCB | Caliper | `cad/macropad_case/spec.py` | `header_pins_under_lens` |
| `led_body` | 4.0 x 1.6 x 2.0 mm | SK6812SIDE-A: along the edge, depth, height | Caliper | `cad/macropad_case/spec.py` | `led_inside_slot_height` (0.5), clash check |
| `keycap_pressed_bottom`, `keycap_top` | 2.0 mm, 14.5 mm | Your switch and keycap on a plate: skirt bottom at full travel, cap top | Caliper depth rod | `cad/macropad_case/spec.py` | Clash check (keycap sweep against the top) |
| `components.ENCODER_PINS` | from the KiCad footprint | EC11E terminal positions against its drawing | Caliper | `cad/macropad_case/components.py` | Clash check (pins and tabs against the base) |
| `components.MX_*` | 15.6 mm rim, 6.6 mm housing, stem 10.2 mm | One MX switch | Caliper | `cad/macropad_case/components.py` | `switch_flange_to_dish_floor` (0.25), clash check |
| `components.USB_PLUG_TIP` | 8.25 x 2.4 x 6.5 mm | The cable you will use: metal tip of the plug | Caliper | `cad/macropad_case/components.py` | Plug in the clash check and the pictures; the opening uses `usb_plug` (`usb_plug_to_opening`) |
| `components.DISPLAY_ACTIVE_AREA` | 25.2 x 10.71 mm | nice!view lit area | Caliper | `cad/macropad_case/components.py` | Pictures only |

The numbers in brackets are each check's minimum in millimetres; `cad/exports/checks.json` lists them
all with their current values.
