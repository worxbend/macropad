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
| From above: a 90 mm square, the same 4.275 mm frame left, right and in front of the keys. No text on the top face. | From the left: light top over a dark base that recedes under its 2.0 mm chamfer, the gap between them, the strips that lift the body 1.2 mm. |
| ![deck](../docs/images/cad/deck_detail.png) | ![knob](../docs/images/cad/knob_detail.png) |
| The lens lies 0.12 mm under the top face between the two knobs; each knob stands in a shallow well. | A knob in a low raking light: 30 grooves that run out at 45° at both ends, plain bands, flat top, one 0.8 mm dimple. |
| ![light line at night](../docs/images/cad/light_line.png) | ![cut through a light bar](../docs/images/cad/section_light_line.png) |
| The left light line, drawn glowing and fading out at its ends. Its colour and brightness are guesses; the LEDs are RGB. | Cut across the pad through one LED: the bar stands in the wall behind the outer skin and shows in the gap. |
| ![back](../docs/images/cad/back_usb.png) | ![USB opening](../docs/images/cad/usb_detail.png) |
| Back, with the plug drawn pulled out. | The USB-C opening, 13.5 x 7.5 mm with a 0.5 mm lead-in, seen square on. The gap runs into it on both sides. |
| ![underside](../docs/images/cad/underside.png) | ![shells from inside](../docs/images/cad/shells_inside.png) |
| Underside: two foot strips, the centre pad, the mark, BOOT and RESET. No screw shows. | Both shells from inside: lap ridges and light channels in the base, ribs and screw bosses under the plate. |
| ![milled underside](../docs/images/cad/underside_aluminium.png) | |
| Underside of the milled base, with the laser-marked signature beside the centre pad. | |

The pictures come from the same solids as the exports. The display shows `docs/images/ui/media.png`,
the firmware simulator's own picture, laid on the lit area of the glass (25.2 x 10.7 mm, a datasheet value
to measure). The renderer has no clear material, so only the masked part of the lens is drawn and the
display shows through its window; the two cut views draw the whole lens. The band of light on the lens
is a drawn reflection, not a computed one. Product pictures have no edge lines; the cut views, the
exploded view and the print bed keep them. Cut faces are lighter, and hatched on the two shells.
Colours and finishes are proposals. The PCB is drawn with a black solder mask, an order option (the
default is green, and a green edge then shows in the USB opening). Chalk is drawn with light switch
housings. Keycaps, switches, encoders, the display, the USB parts and the screws are reference shapes
drawn from datasheets, not vendor models.

## What the design is

- **One slab with one line round it.** 90.0 x 90.0 mm, 17.5 mm tall, one flat top face with no text on
  it. The base rim steps in 1.0 mm over its top 1.5 mm, so a shadow gap runs all round the case at the
  joint. The two shells meet at the back of that gap; nothing is left to line up on the outside. The top
  rests on 256 mm² of rim (252 mm² milled), on all four sides.
- **Corners.** The CNC outline has one quintic Bezier per corner (control points 10, 6 and 2 mm from the
  box corner on both sides): curvature is zero where the curve meets the straight side, and the
  smallest radius is 4.71 mm. The print outline has plain R 6.4 arcs through the same apex, **not
  continuous curvature**: the top prints standing on a side wall, and the Bezier corner starts so flat
  that it would hang 2.7 mm over the bed (the limit is 1.5; the arc hangs 1.1).
- **Edges.** 45° only. 0.5 mm on the top rim, the knob rims and the USB lead-in. 2.0 mm on the underside,
  so the base recedes: its straight flank is 5.2 mm tall against the top's 7.7 mm. Not 2.5 mm: that leaves no flat
  between the chamfer and the ends of the foot strip recesses. 0.3 mm on the two outer edges at the gap;
  the rim inside the gap stays sharp, because the top seats on it. Chamfers print without supports in
  any orientation and a mill cuts them with one tool; fillets do neither.
- **Key dish.** The keys stand in a dish: flat floor on the plate, 8.65 mm outside the outer key centres,
  and 45° walls up to the top face. The flat frame around it is 4.275 mm wide on the left, the right and
  in front. The dish is sized for the widest, sharpest keycap skirt it must clear, 18.3 mm with 0.3 mm
  corners (0.56 mm when pressed), not only for the DSA caps in the pictures. A vertical wall with a foot
  was tried first and does not print: the foot is a 55 mm bridge.
- **Lens.** A 39.0 x 14.6 x 1.0 mm cover glass (soda-lime or chemically strengthened, black mask
  screen-printed on its underside) lies in a recess in the top face, 0.12 mm under flush, taped on two
  end ledges. A sheet 0.1 mm too thick still ends under flush. Its corners are R 2.5, its recess R 2.6.
  The mask leaves a 27 x 12 mm window over the visible glass, 1.5 mm off the lens centre as the glass
  is: the board fixes the display, and the opening under the lens must cover the whole module, so the
  lens cannot move to centre the window. A 5 N press in the middle bends glass 0.06 mm onto a 0.38 mm
  air gap. Clear cast acrylic of the same size bends 1.4 mm and touches the display: it is a fallback
  only with a foam pad under the display and a light touch, and the check fails for it.
- **Light line.** Each side wall of the base has a channel behind a 1.0 mm outer skin. A light bar stands
  in it, in front of the four side LEDs. In the gap the rim is cut away along the channel, so the top
  1.4 mm of the bar shows there, 1.0 mm back, 46.2 mm long. From 45° above, 0.7 mm of it is still in
  sight. In the gap the bar's ends are square and fill the slot to 0.15 mm; below, they are rounded like
  the channel. Its lip runs its whole length, so the PCB edge does not show past it. The gap runs all
  round, but it lights only along these two 46.5 mm stretches. The light reaches the slit indirectly:
  brightness and evenness are guesses. A printed base must be dark, or the 1.0 mm skin glows too.
- **Knobs.** 14.4 mm, 13.4 mm tall, standing in a 15.5 mm well 0.7 mm deep, so no bushing shows under
  them; the reveal round each knob is 0.55 mm. 30 straight V grooves, 0.45 mm deep, that run out at 45°
  into two plain bands; flat top; a 0.8 mm pointer dimple on the side of the D-shaft's flat. Three low
  ribs in the bore grip the shaft (a guess). The knobs are printed in both builds: they are not designed
  for turning in aluminium.
- **Underside.** All six screws are hidden. Two foot strips, 84.6 x 7.0 mm with ends concentric to the
  corner screws, lie in 0.4 mm recesses and stand 1.2 mm proud. A centre pad covers the two centre
  screws and stands 1.0 mm proud, so the case never rocks on it. `worxbend / macropad` is engraved
  0.4 mm into the flat face in the print variant, in a 66 x 8 mm area kept free for it; BOOT and RESET
  sit behind it. The print variant closes each counterbore with one 0.2 mm layer at the roof of its foot
  recess (the builder cuts it out): a hole in that roof would be a hole in a bridge.
- **Lap joint.** Ridges 0.6 mm tall stand on the base rim, inside the wall, along the back, the front and
  the first part of each side. They enter grooves in the top's skirt. The joint centres the top on the base
  and closes the straight path for light through the joint. The ridges stop 10 mm short of the corners
  (where the screw bosses join the walls), at the USB opening and at the light channels. Flank and ends
  are 45°, so they print without support and a chamfer mill cuts them.
- **Structure.** Two ribs run under the plate between the key rows and pass through the two centre screw
  bosses. They start 1.0 mm above the PCB, above the lap grooves. In the print variant each corner boss has
  a web to the back or front wall with a 45° underside, and each centre boss has a small fin: without them
  a boss is a cylinder sticking out sideways while the top prints on its side. Each base boss is 5.5 mm
  wide next to the hot-swap sockets and 8 mm wide where it joins the floor.
- **Legends.** `BOOT`, `RESET` and `worxbend / macropad` on the underside, engraved in the print variant
  only: the CNC base stays plain, to be laser-marked or left blank. The top face carries no text.
  Text sizes are set so the thinnest stroke is wider than one 0.4 mm line (checked: 0.48 mm).
- **Signature.** A single-line signature reading "Oleksandr B" (34 x 19 mm, line 0.3 mm) and the caption `Signature Edition`
  are laser-marked on the underside of the base, beside the centre pad (`macropad_case/signature.py`).
  It is flat artwork, not geometry: the solids and the STEP/STL files do not contain it. Send
  `exports/drawings/engraving_underside.dxf` to the laser shop; it holds the signature at its place,
  drawn as seen from above (mirrored, because it is read from below). Two clearance rows check that
  it stays clear of the feet and the label field and that the line is wide enough for a laser.
- **USB-C.** The opening is 13.5 x 7.5 mm, 0.5 mm round a 12.5 x 6.5 mm overmould, so a plug up to
  13.0 x 7.0 mm still enters. It is the same on both sides of its centre line (checked).
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
and recesses from datum A. The tolerance note on them (ISO 2768-m) is a proposal, not a tested requirement.

| | |
| --- | --- |
| ![base sheet](../docs/images/cad/drawing_base.png) | ![top sheet](../docs/images/cad/drawing_top.png) |

`exports/drawings/` also holds three DXF outlines. `engraving_underside.dxf` is the underside text and
the signature, for laser-marking the milled base, drawn as seen from above (mirrored). `lens.dxf` is the
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

Size: 90.0 x 90.0 mm, 17.5 mm tall, 31.0 mm from the underside to the top of the knobs. The foot strips
add 1.2 mm.

The left and right light bar are the same part, turned around. The two foot strips are identical.

The light bar is natural, not smoke-grey: the light reaches the slit indirectly, and a tinted bar takes
away more of it. By day it sits 1.0 mm back in the shadow of the gap. How it looks is a guess until one
is printed.

Hardware:

- Print variant: 6 x M2 x 10 socket-head cap screw (ISO 4762, 3.8 mm head). CNC variant: 6 x M2 x 8.
- Double-sided tape for the lens: two pieces of about 1.3 x 14.6 mm, 30 mm² in all. Measure the glass,
  then pick 0.13 mm or 0.2 mm tape so the lens ends just under the top face (the thickness is a guess).
- A foam pad about 8 x 10 mm and 4 mm thick, under the free end of the display (a guess)
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

0. **Self-test.** Before the case is judged, the measuring checks are run on 27 small solids: a sheet
   thinner than the minimum wall, a pocket with sharp corners, a pocket with too small a radius, a slot
   narrower than the tool, a groove in a side wall, a bridge that is too long, a shelf, a wall leaning 60°,
   an outline with arc corners, two loose boxes, a foot recess with an open screw hole in its roof, a
   1 mm ledge 58 mm long between two posts, a letter stroke 0.3 mm wide, a foot over a hole, and sound
   versions of each. A check that misses its fault, or flags a sound shape, fails the run.
1. **Interference.** Every part against every bought component and every other part, for both variants:
   582 pairs each. Any shared volume over 0.05 mm³ fails. Keycaps are blocks that cover the whole key travel.
   The tilt bar against the back foot strip is skipped, because the bar takes that strip's recess.
2. **Named clearances.** 68 gaps computed from the dimensions: USB plug to its opening, keycap to the
   dish rim, lens to the glass and how far a 5 N press bends it, screw engagement and thread for both
   screws, the tap drill's point under the dish floor, switch cut-outs and the lens recess after a
   printed bridge sags, the gap and the lap joint on a PCB 10 % too thick, floor under each recess and
   each engraving, and more.
3. **Measurements on the finished solids.** These do not trust how the model was built.
   - Every part is one valid solid with a volume. A boolean that went wrong shows up here first.
   - Thinnest wall of every part: 3000 surface points per part, a ray through the material from each.
     Minimum 0.8 mm. A sample can miss a very small thin spot. The printed base and tilt bar are measured
     finished: without their engraving and without the 0.2 mm skins the builder cuts out. The layer
     check below sees them with skins.
   - Engraved text: the mean stroke of the thinnest letter (twice its area over its outline) must be
     0.45 mm or more.
   - Silhouette: width equals depth, and the frame beside the key dish equals the frame in front of it,
     both within 0.01 mm. On the CNC shells the curvature where a corner curve meets a straight side
     must stay under 0.01 per mm, and the smallest corner radius must be 4.66 mm or more. Only the four
     corners count: the USB opening cuts the base outline and has its own milled radii.
   - Wall around every screw hole, measured on a horizontal cut.
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
     pressed knob to the top, as distances between solids.
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
- The underside mark at 4.6 mm had a 0.42 mm stroke. It is 5.2 mm now (0.48 mm).

### Checks that changed their meaning

These checks from the earlier case measure something else now, because the part they were about is
gone or changed. Their limits are the same or stricter.

| Check | Measures now | Value, minimum |
| --- | --- | --- |
| `keycap_to_deck` | back edge of the back keycaps to the rim of the key dish | 3.1, 0.4 |
| `display_glass_under_deck` | display glass to the underside of the lens | 0.38, 0.2 |
| `bezel_land_under_chamfer`, now `lens_ledge_thickness` | thickness of the two ledges that carry the lens | 0.9, 0.8 (was 0.2) |
| `tilt_bar_to_screw_counterbore` | wall of the bar's 5.6 mm hole around the 4.4 mm counterbore under it | 0.6, 0.5 |
| `cone_inside_floor`, now `screw_skin_inside_floor` | floor left above the print skin that closes each counterbore (the cones are gone) | 1.8, 0.5 |
| `pressed_keycap_to_top` | an 18.3 mm skirt with 0.3 mm corners, pressed, instead of the DSA cap | 0.56, 0.4 |
| `screw_tip_to_hole_end` | as before | 0.6, 0.6 (was 0.2) |
| `usb_plug_to_opening` | as before | 0.5, 0.4 (was 0.2) |

`foot_below_underside` is how far a foot strip stands proud (1.2 mm). `knob_to_well_floor_when_pressed`
and `skin_under_knob_well` read the knob wells again. `floor_under_label_engraving` is the floor under
the engraved mark: there is no label pocket any more. `thinnest_wall_print_base` and
`thinnest_wall_tilt_bar` measure the finished parts, without the 0.2 mm skins; the layer check sees the
skins.

## Printing

The STL files already lie the way they print. No supports.

| Part | Orientation | Notes |
| --- | --- | --- |
| `base` | floor down | Print it dark. The foot recesses are short bridges; one 0.2 mm layer closes each counterbore at the recess roof. Cut the six skins out with a 2 mm drill or a knife before assembly. |
| `top` | standing on its **left side wall** | Use an 8 mm brim: the part is 10.6 times taller than its footprint is wide. |
| `diffuser` | outer face down | The face on the bed is the one you see in the gap. 100 % infill. |
| `knob` | top face down | The top takes the finish of the bed; the 0.5 mm chamfer takes the elephant's foot. The grooves are vertical; the land between two is 0.6 mm (a guess for a 0.4 mm nozzle). |
| `foot_strip`, `centre_pad` | flat | TPU. Or cut them from sheet. |
| `tilt_bar` | sloped face down | The top comes out 6° off level and shows layer steps; it is hidden under the base. Cut the two skins out of its holes. |

![parts on the bed](../docs/images/cad/print_plate.png)

The top stands on its side so that the top face and the walls of the key dish print as walls, not as
a first layer or a ceiling. The ribs print as vertical walls too, the switch cut-outs are 14 mm bridges
and the lens recess is a 15.0 mm one. The print variant has 45° fillers under both side walls so the
upper wall does not start in mid-air, webs under the screw bosses, and a filler beside each lens rib,
all for the same reason.

A bridge sags. The high-X edge of every opening in the top is a bridge in this pose, so the print's
switch cut-outs are 14.2 mm long in X (the extra 0.2 mm on that side), and its lens recess has 0.2 mm
of fit all round and 0.1 mm more at that end. The 0.2 mm sag is a guess.

Standing on one side means the two sides do not match. How each face of the top prints:

| Face | How it prints |
| --- | --- |
| Top face, walls of the dish on the left, the back and the front, back and front faces | Vertical walls: the best finish on the part |
| Left side face | On the bed: bed texture |
| Right side face | Last layers: top-layer infill |
| Left corners | Leave the bed on a curve, 1.1 mm overhang: may look rough; the brim helps |
| Right corners | Close as a dome: the first step below the right face is 1.6 mm wide at 0.2 mm layers, so layer steps show |
| Dish wall on the right | A 54 mm long 45° overhang on the show face |
| Dish floor | Vertical: as the top face |

Settings: 0.2 mm layers, 0.1 mm for X below 3 and above 87 and through X 78.7 to 82.2 (the corners and
the right dish wall; the first corner step drops to 1.13 mm), 3 walls and 4 round the screw bosses,
0.4 mm nozzle, seam on the joint face (the skirt's underside at Z = 0), elephant's foot compensation
0.15 mm, ironing off. If both sides must match, sand and paint: there is no print orientation that
gives one finish all round.

The engraved text is 0.4 mm deep, on the face that lies on the bed. Its thinnest strokes are 0.48 mm
(measured on the artwork): a little more than one line of a 0.4 mm nozzle.

The screws cut their own thread in the 1.8 mm holes of the top. A hole printed lying down comes out about
0.15 mm small (a guess), so expect 1.65 mm; a hole under 1.6 mm splits the boss. If a screw will not start,
run a 1.7 mm drill 4.2 mm deep through the six holes first. Do not overtighten.

## CNC

`exports/cnc/base.step` and `exports/cnc/top.step` are for 3-axis milling, two setups each.

- The outline corners are free curves, not arcs. Take them from the STEP file.
- Every pocket is opened with a 1.5 mm radius, so a 3 mm end mill reaches every internal corner.
  Gaps narrower than 3 mm are left solid: the corner bosses are joined to the walls.
- The switch cut-outs have dog-bone reliefs in the corners. The 14.0 mm square is still clear.
- No undercuts. The print variant's 45° fillers, boss webs and text are not in the CNC variant.
- The lap grooves in the top open toward the cavity. A flat end mill clears them; a chamfer mill cuts the
  45° outer wall and leaves the conical ends drawn in the model.
- A 90° chamfer mill cuts everything that is at 45°: the rims, the edges at the gap, the walls of the
  key dish and the USB lead-in. The dish walls are 3.5 mm deep: they need a cutter of 8 mm or more with
  a tip flat of 0.5 mm or less (checked), in several passes. Where two faces of the dish or of a lead-in
  meet, the tool leaves a small radius instead of the sharp mitre in the model.
- Top, setup 1 (underside up): the cavity levels around the ribs and the lens ribs, all through cuts,
  the six screw holes, the lower rim chamfer. Setup 2 (top side up): the key dish, the lens recess, the
  knob wells, the top rim chamfer. Hold the part for setup 2 on a fixture plate through the six M2 holes
  or in soft jaws cut to the outline: the 2.7 mm skirts will not take vise pressure.
- Base, setup 1 (inside up): the cavity in three levels, the USB opening, the light channels, the through
  holes, the rim step that makes the gap and the chamfer on the skin. Setup 2: counterbores, foot
  recesses, underside chamfer. A mill needs no skin over the counterbores.
- Screws: M2 x 8 in tapped blind holes. Drill 1.6 mm to 3.7 mm at full diameter (the 118° point ends at
  4.18 mm, 0.82 mm under the dish floor), tap M2 with a bottoming tap to 3.0 mm of full thread or more.
  The screw takes 1.9 mm of thread (an M2 nut is 1.6 mm tall) and ends 1.1 mm before the full thread
  does. A tap leaving about 0.6 mm of a 3.7 mm hole without full thread is a guess.
- The plate is 1.5 mm thick, which MX switches need to clip in.

The light bars, the knobs, the foot strips and the tilt bar stay printed, in both builds. The knobs are
not designed for turning: a metal knob needs a round bore, a grub screw and grooves a cutter can run out
of, and none of that is drawn. The pictures of the milled variant show graphite printed knobs.

## Assembly

1. Print variant: cut the six skins out of the counterbores in the base.
2. Stand a light bar in each side channel of the base, lip up and toward the inside. Hold each bar
   against the outer skin with a strip of tape over the gap until the top is on: until the PCB is in,
   nothing stops a bar tipping inward.
3. Trim the display's header pins to 1.5 mm above its board. Stick the foam pad on the PCB under the
   display's free end, then plug the display in.
4. Lower the assembled PCB onto the six bosses. Its edges now hold the bars in.
5. Stick the two tape pieces on the lens ledges of the top and press the lens in, mask down, window
   toward the right knob.
6. Put the top on. The lap ridges find their grooves and centre it. Peel off the tape over the gap. Fit
   the six screws from below.
7. Press the switches into the plate, then the keycaps and the knobs. The pointer dimple goes on the
   side of the shaft's flat.
8. Stick the two foot strips and the centre pad into their recesses, last. They cover the screws.
   To open the case again, peel them off first.

The nice!view is held only by its header. The foam pad under its free end is not optional: it keeps
the display from tilting up to the lens.

### Tilt bar

![tilt](../docs/images/cad/tilt.png)

Cut the two skins out of the bar's holes. Leave the back foot strip off the base. Glue or tape the
bar's tongue into the empty back recess, then stick that strip into the recess on the bar.
The two holes in the bar keep the back corner screws reachable once the strip is peeled off, and the
bar leaves the BOOT and RESET holes free. The pad then rests on its front strip and on the bar.

## Assumptions to measure

These came from datasheets, footprints and photos, not from parts on a desk. Each is one number in
`board.toml` (first three), in `macropad_case/spec.py`, in `macropad_case/components.py` or, for the
picture colours, in `macropad_case/render.py`.

| What | Value | Where |
| --- | --- | --- |
| nice!view glass top above the PCB | 7.0 mm | `stack.display_glass_top` |
| nice!view header position and pin order | 1.27 mm from the short edge | `display.header_x` |
| Visible glass area and its offset | 27 x 12 mm, 1.5 mm off centre | `display.window_*` |
| nice!view module thickness | 2.9 mm | `display_thickness` |
| nice!view glass outline and board thickness (pictures only) | 30 x 13.6 mm, 1.0 mm | `display_glass`, `display_board_thickness` |
| Encoder body footprint | 12.4 x 13.4 mm | `encoder_body` |
| Encoder threaded bushing length | 7.0 mm | `bushing_length` |
| Encoder D-shaft, across the flat | 4.5 mm | `shaft_flat` |
| Encoder terminal positions | from the KiCad EC11E footprint | `components.ENCODER_PINS` |
| Side LED body | 4.0 x 1.6 x 1.6 mm | `led_body` |
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
| Foam pad under the display (a guess) | about 8 x 10 x 4 mm | assembly above |
| Widest keycap skirt the dish must clear | 18.3 mm, 0.3 mm corners | `keycap_worst_skirt` |
| Foot strips and centre pad (a guess) | TPU, 1.6 mm and 1.4 mm thick | `foot_strip`, `centre_pad_thickness` |
| Knob grooves (a guess for a 0.4 mm nozzle) | 30 grooves, 0.45 mm deep, 0.6 mm land | `knob_grooves`, `knob_groove_depth` |
| Crush ribs in the knob bore (a guess) | three, 1.0 mm wide, 6 mm long, 0.1 mm high | `knob_crush_rib` |
| Light bar material (a guess) | natural translucent PETG | parts table above |
| Light through the slit (a guess, nothing was simulated) | enough to read as a line | `gap_height`, `light_channel_reach` |
| Glow colour and brightness in `light_line.png` (a guess) | warm white | `render.GLOWING_DIFFUSER` |
| Colours and finishes in the pictures (proposals) | Chalk, Graphite, Silver, Space grey | `render.COLOURWAYS` |

A pressed keycap with an 18.3 mm skirt and 0.3 mm corners keeps 0.56 mm to the dish wall at the four
dish corners. Wider or squarer skirts: check your keycaps.

The PCB may be up to 10 % thicker or thinner than 1.6 mm. On a 1.76 mm board the top rides 0.16 mm
higher: the gap reads 1.66 mm and the lap ridges still overlap their grooves by 0.44 mm (both checked).
On a thin board the PCB is loose until the screws pull it down.

Not modelled: the MCU and the small parts on the PCB bottom (all under 1 mm, with 5 mm of room), cables,
the two pieces of lens tape, the foam pad and the mask on the lens.
