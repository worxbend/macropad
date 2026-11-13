"""Reference solids for the parts you buy, each in its assembled position.

`components()` is what the fit checks use: every keycap is a block that covers its whole travel.
`drawn_components()` is what the pictures and drawings use: the same parts with a real keycap shape.
Dimensions marked MEASURE in `spec.py` and here are from datasheets and footprints, not from a caliper.
"""

from build123d import Axis, Box, Cylinder, Part, Pos, Rectangle, RectangleRounded, Sphere, chamfer, extrude, fillet
from build123d import loft

from .solids import box, centred_box, cylinder, d_profile, pcb_outline, slab
from .spec import BOARD, CASE, LEVELS, buttons, encoder_centres, key_centres, mounting_holes, screw_length, screw_seat

# MEASURE: EC11E terminals and mounting tabs, from the KiCad footprint, relative to the encoder centre.
ENCODER_PINS = [(-7.5, -2.5), (-7.5, 0.0), (-7.5, 2.5), (7.0, -2.5), (7.0, 2.5)]
ENCODER_TABS = [(0.0, -5.6), (0.0, 5.6)]
SOLDER_TAIL = 2.0  # through-hole pins below the PCB bottom face

# MX switch, heights above the plate top. MEASURE: from the Cherry MX drawing.
MX_FLANGE = (15.6, 1.0)  # width, height of the square rim that rests on the plate
MX_HOUSING_TOP = (11.6, 12.6, 6.6)  # X, Y of the housing's top face, its height above the plate
MX_STEM_TOP = 10.2
MX_STEM_BLOCK = (7.2, 5.6, 0.6)
MX_STEM_CROSS = (4.0, 1.3)

KEYCAP_WALL = 1.4
KEYCAP_DISH_RADIUS = 30.0
KEYCAP_STEM_SOCKET = (5.6, 4.0)  # diameter, length
USB_SHELL_RADIUS = 1.2
USB_PLUG_TIP = (8.25, 2.4, 6.5)  # MEASURE: the plug's metal tip, width, height, length
USB_CABLE = (4.0, 12.0)
USB_SOCKET_PLAY = 0.08  # gap between the plug tip and the receptacle shell
USB_OVERMOULD_LENGTH = 20.0
# MEASURE: lit area of the LS011B7DH03 (160 x 68 pixels), from its datasheet as remembered. Pictures only.
DISPLAY_ACTIVE_AREA = (25.2, 10.71)


def at(centre: tuple[float, float], shape: Part) -> Part:
    return Pos(centre[0], -centre[1], 0) * shape


def pcb() -> Part:
    board = slab(pcb_outline(), (LEVELS.pcb_bottom, 0))
    return board - [cylinder(hole, BOARD.mounting.hole_diameter, (LEVELS.pcb_bottom - 1, 1)) for hole in mounting_holes()]


def switch_housing() -> Part:
    """MX switch at the origin, without a keycap, stem up (not pressed)."""
    plate = LEVELS.plate_top
    flange_width, flange_height = MX_FLANGE
    top_x, top_y, housing_height = MX_HOUSING_TOP
    lower = centred_box((0, 0), (CASE.switch_body, CASE.switch_body), (0, plate))
    flange = centred_box((0, 0), (flange_width, flange_width), (plate, plate + flange_height))
    upper = loft([
        Pos(0, 0, plate + flange_height) * Rectangle(flange_width, flange_width),
        Pos(0, 0, plate + housing_height) * Rectangle(top_x, top_y),
    ])
    block_x, block_y, block_height = MX_STEM_BLOCK
    stem_block = centred_box((0, 0), (block_x, block_y), (plate + housing_height, plate + housing_height + block_height))
    cross_length, cross_width = MX_STEM_CROSS
    cross_z = (plate + housing_height, plate + MX_STEM_TOP)
    cross = centred_box((0, 0), (cross_length, cross_width), cross_z) + centred_box(
        (0, 0), (cross_width, cross_length), cross_z
    )
    post_diameter, post_length = CASE.switch_post
    post = cylinder((0, 0), post_diameter, (-post_length, 0))
    return lower + flange + upper + stem_block + cross + post


def keycap() -> Part:
    """A DSA-profile keycap at the origin, not pressed: tapered sides, a spherical dish, hollow underneath."""
    top_width, height, dish = CASE.keycap_profile
    bottom = LEVELS.plate_top + CASE.keycap_pressed_bottom + CASE.key_travel
    shell = _tapered_block(CASE.keycap_width, top_width, (bottom, bottom + height), corner_radii=(1.2, 2.0))
    shell -= Pos(0, 0, bottom + height + KEYCAP_DISH_RADIUS - dish) * Sphere(KEYCAP_DISH_RADIUS)
    roof = bottom + height - dish - KEYCAP_WALL
    inside = _tapered_block(
        CASE.keycap_width - 2 * KEYCAP_WALL, top_width - 2 * KEYCAP_WALL, (bottom - 0.01, roof), corner_radii=(0.6, 1.0)
    )
    socket_diameter, socket_length = KEYCAP_STEM_SOCKET
    stem_socket = cylinder((0, 0), socket_diameter, (roof - socket_length, roof + 0.1))
    cross_length, cross_width = MX_STEM_CROSS
    cross_z = (roof - socket_length - 0.01, roof)
    cross = centred_box((0, 0), (cross_length + 0.1, cross_width + 0.1), cross_z) + centred_box(
        (0, 0), (cross_width + 0.1, cross_length + 0.1), cross_z
    )
    return shell - inside + (stem_socket - cross)


def _tapered_block(bottom_width: float, top_width: float, z: tuple[float, float], corner_radii: tuple[float, float]) -> Part:
    return loft([
        Pos(0, 0, z[0]) * RectangleRounded(bottom_width, bottom_width, corner_radii[0]),
        Pos(0, 0, z[1]) * RectangleRounded(top_width, top_width, corner_radii[1]),
    ])


def worst_keycap_skirt() -> Part:
    """The lower edge of the widest, sharpest-cornered keycap the dish must clear, at the origin and
    pressed all the way down. A slab, not a keycap: only its outline matters."""
    width, corner_radius = CASE.keycap_worst_skirt
    bottom = LEVELS.plate_top + CASE.keycap_pressed_bottom
    return Pos(0, 0, bottom) * extrude(RectangleRounded(width, width, corner_radius), 1.0)


def keycap_sweep() -> Part:
    """Everything a keycap can touch on its way down: full width, from pressed bottom to rest top."""
    z_range = (LEVELS.plate_top + CASE.keycap_pressed_bottom, LEVELS.plate_top + CASE.keycap_top)
    return centred_box((0, 0), (CASE.keycap_width, CASE.keycap_width), z_range)


def socket(centre: tuple[float, float]) -> Part:
    x0, x1, y0, y1 = CASE.socket_box
    z_range = (LEVELS.pcb_bottom - BOARD.stack.socket_depth, LEVELS.pcb_bottom)
    return box((centre[0] + x0, centre[0] + x1), (centre[1] + y0, centre[1] + y1), z_range)


def encoder(centre: tuple[float, float]) -> Part:
    stack = BOARD.stack
    body = centred_box(centre, CASE.encoder_body, (0, stack.encoder_body_top))
    bushing = cylinder(centre, stack.encoder_bushing_diameter, (stack.encoder_body_top, LEVELS.bushing_top))
    bushing = chamfer(bushing.edges().group_by(Axis.Z)[-1], 0.4)
    d_shaft = Pos(centre[0], -centre[1]) * d_profile(CASE.shaft_diameter, CASE.shaft_flat)
    shaft = slab(d_shaft, (LEVELS.bushing_top, stack.encoder_shaft_top))
    tail_z = (LEVELS.pcb_bottom - SOLDER_TAIL, LEVELS.pcb_bottom)
    pins = [cylinder((centre[0] + dx, centre[1] + dy), 1.2, tail_z) for dx, dy in ENCODER_PINS]
    tabs = [centred_box((centre[0] + dx, centre[1] + dy), (3.0, 1.2), tail_z) for dx, dy in ENCODER_TABS]
    return body + bushing + shaft + pins + tabs


def display_parts() -> dict[str, Part]:
    """nice!view on its socket strip, in three solids so the pictures can colour them: the module
    board with its socket, its header pins trimmed short and its solder tails, the LCD glass, and the
    visible pixel area."""
    module = BOARD.display
    glass_top = BOARD.stack.display_glass_top
    module_bottom = glass_top - CASE.display_thickness
    board_top = module_bottom + CASE.display_board_thickness
    board = centred_box((module.x, module.y), (module.length, module.width), (module_bottom, board_top))
    header_length = module.header_pitch * len(module.header_pins)
    header_centre = (module.header_x, module.y)
    socket_strip = centred_box(header_centre, (module.header_pitch, header_length), (0, module_bottom))
    tails = centred_box(header_centre, (1.2, header_length), (LEVELS.pcb_bottom - SOLDER_TAIL, LEVELS.pcb_bottom))
    pins = centred_box(header_centre, (1.2, header_length), (board_top, board_top + CASE.header_pin_height))
    window_centre = (module.window_x, module.window_y)
    pixels = centred_box(window_centre, (module.window_length, module.window_width), (glass_top - 0.1, glass_top))
    glass = centred_box(window_centre, CASE.display_glass, (board_top, glass_top)) - pixels
    return {"display": board + socket_strip + tails + pins, "display_glass": glass, "display_pixels": pixels}


def usb_receptacle() -> Part:
    width, depth = CASE.usb_body
    mouth = -BOARD.usb.mouth_overhang
    z_range = (LEVELS.pcb_bottom - BOARD.usb.body_height, LEVELS.pcb_bottom)
    shell = box((BOARD.usb.x - width / 2, BOARD.usb.x + width / 2), (mouth, mouth + depth), z_range)
    return fillet(shell.edges().filter_by(Axis.Y), USB_SHELL_RADIUS) - _usb_tip(USB_SOCKET_PLAY)


def _usb_tip(grow: float) -> Part:
    """The plug's metal tip in its seated position, made `grow` larger all round."""
    tip_width, tip_height, tip_length = (size + 2 * grow for size in USB_PLUG_TIP)
    mouth = -BOARD.usb.mouth_overhang - grow
    tip = Pos(BOARD.usb.x, -(mouth + tip_length / 2), LEVELS.usb_centre) * Box(tip_width, tip_length, tip_height)
    return fillet(tip.edges().filter_by(Axis.Y), tip_height / 2 - 0.05)


def usb_plug() -> Part:
    """The cable end: the overmould seated against the receptacle mouth, its metal tip inside the
    receptacle, and a stub of cable. Only the overmould matters for the opening in the case."""
    width, height = CASE.usb_plug
    mouth = -BOARD.usb.mouth_overhang
    overmould_z = (LEVELS.usb_centre - height / 2, LEVELS.usb_centre + height / 2)
    overmould = box((BOARD.usb.x - width / 2, BOARD.usb.x + width / 2), (mouth - USB_OVERMOULD_LENGTH, mouth), overmould_z)
    overmould = fillet(overmould.edges().filter_by(Axis.Y), 2.0)
    cable_diameter, cable_length = USB_CABLE
    cable_centre_y = mouth - USB_OVERMOULD_LENGTH - cable_length / 2
    cable = Pos(BOARD.usb.x, -cable_centre_y, LEVELS.usb_centre) * (
        Cylinder(cable_diameter / 2, cable_length, rotation=(90, 0, 0))
    )
    return overmould + _usb_tip(0.0) + cable


def led(edge_x: float, inward: int, y: float) -> Part:
    along_edge, depth, height = CASE.led_body
    x_range = sorted((edge_x, edge_x + inward * depth))
    return box(tuple(x_range), (y - along_edge / 2, y + along_edge / 2), (LEVELS.pcb_bottom - height, LEVELS.pcb_bottom))


def button(centre: tuple[float, float]) -> Part:
    width, height = CASE.button_body
    return centred_box(centre, (width, width), (LEVELS.pcb_bottom - height, LEVELS.pcb_bottom))


def boss_ring(centre: tuple[float, float]) -> Part:
    """Foam ring on a base boss, under the PCB, squeezed to the room left for it on a 1.6 mm board."""
    _, room, diameter = CASE.boss_ring
    z_range = (LEVELS.base_boss_top, LEVELS.base_boss_top + room)
    return cylinder(centre, diameter, z_range) - cylinder(centre, CASE.boss_ring_hole, (z_range[0] - 1, z_range[1] + 1))


def display_foam() -> Part:
    """Foam pad on the PCB under the free end of the display module, squeezed to the room there."""
    module = BOARD.display
    module_bottom = BOARD.stack.display_glass_top - CASE.display_thickness
    _, side = CASE.display_foam
    free_end = module.x + module.length / 2 - side / 2 - 2.0
    return centred_box((free_end, module.y), (side, side), (0, module_bottom))


def screw(centre: tuple[float, float], variant: str) -> Part:
    """M2 socket-head screw of the variant's length, head in the base counterbore. Above the PCB it is
    drawn at the thread's root diameter, because there its thread is inside the wall of the hole."""
    head_diameter, head_height = CASE.screw_head
    seat = screw_seat(variant)
    head = cylinder(centre, head_diameter, (seat - head_height, seat))
    hex_socket = cylinder(centre, 1.7, (seat - head_height - 0.01, seat - head_height + 1.0))
    shank = cylinder(centre, 2.0, (seat, 0))
    core = cylinder(centre, CASE.screw_thread_core, (0, seat + screw_length(variant)))
    return head - hex_socket + shank + core


def components(variant: str) -> dict[str, Part]:
    """Every bought part by name, for the fit checks."""
    return _fixed_components(variant) | _switches(switch_housing() + keycap_sweep(), name="switch")


def drawn_components(variant: str) -> dict[str, Part]:
    """Every bought part by name, for pictures: keycaps are separate and have their real shape."""
    housings, keycaps = _switches(switch_housing(), name="switch"), _switches(keycap(), name="keycap")
    return _fixed_components(variant) | housings | keycaps


def _switches(shape: Part, name: str) -> dict[str, Part]:
    return {f"{name}_{index}": at(centre, shape) for index, centre in enumerate(key_centres())}


def _fixed_components(variant: str) -> dict[str, Part]:
    found = {"pcb": pcb(), **display_parts(), "usb_receptacle": usb_receptacle(), "usb_plug": usb_plug()}
    for index, centre in enumerate(key_centres()):
        found[f"socket_{index}"] = socket(centre)
    for side, centre in zip(("left", "right"), encoder_centres()):
        found[f"encoder_{side}"] = encoder(centre)
    for index, y in enumerate(BOARD.leds.left_y):
        found[f"led_left_{index}"] = led(0.0, 1, y)
    for index, y in enumerate(BOARD.leds.right_y):
        found[f"led_right_{index}"] = led(BOARD.board.width, -1, y)
    for name, centre in buttons().items():
        found[f"button_{name}"] = button(centre)
    for index, centre in enumerate(mounting_holes()):
        found[f"screw_{index}"] = screw(centre, variant)
        found[f"boss_ring_{index}"] = boss_ring(centre)
    found["display_foam"] = display_foam()
    return found
