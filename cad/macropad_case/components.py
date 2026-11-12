"""Reference solids for the parts you buy. Simple envelopes, only as exact as the fit checks need."""

from build123d import Part, Pos

from .solids import box, centred_box, cylinder, d_profile, pcb_outline, slab
from .spec import BOARD, CASE, LEVELS, encoder_centres, key_centres, mounting_holes

# MEASURE: EC11E terminals and mounting tabs, from the KiCad footprint, relative to the encoder centre.
ENCODER_PINS = [(-7.5, -2.5), (-7.5, 0.0), (-7.5, 2.5), (7.0, -2.5), (7.0, 2.5)]
ENCODER_TABS = [(0.0, -5.6), (0.0, 5.6)]
SOLDER_TAIL = 2.0  # through-hole pins below the PCB bottom face


def pcb() -> Part:
    board = slab(pcb_outline(), (LEVELS.pcb_bottom, 0))
    return board - [cylinder(hole, BOARD.mounting.hole_diameter, (LEVELS.pcb_bottom - 1, 1)) for hole in mounting_holes()]


def switch(centre: tuple[float, float]) -> Part:
    """MX switch with its keycap swept through the full travel."""
    body = centred_box(centre, (CASE.switch_body, CASE.switch_body), (0, LEVELS.plate_top))
    upper_housing = centred_box(centre, (15.6, 15.6), (LEVELS.plate_top, LEVELS.plate_top + 6.6))
    keycap_z = (LEVELS.plate_top + CASE.keycap_pressed_bottom, LEVELS.plate_top + CASE.keycap_top)
    keycap = centred_box(centre, (CASE.keycap_width, CASE.keycap_width), keycap_z)
    post_diameter, post_length = CASE.switch_post
    post = cylinder(centre, post_diameter, (-post_length, 0))
    return body + upper_housing + keycap + post


def socket(centre: tuple[float, float]) -> Part:
    x0, x1, y0, y1 = CASE.socket_box
    z_range = (LEVELS.pcb_bottom - BOARD.stack.socket_depth, LEVELS.pcb_bottom)
    return box((centre[0] + x0, centre[0] + x1), (centre[1] + y0, centre[1] + y1), z_range)


def encoder(centre: tuple[float, float]) -> Part:
    stack = BOARD.stack
    body = centred_box(centre, CASE.encoder_body, (0, stack.encoder_body_top))
    bushing = cylinder(centre, stack.encoder_bushing_diameter, (stack.encoder_body_top, LEVELS.bushing_top))
    d_shaft = Pos(centre[0], -centre[1]) * d_profile(CASE.shaft_diameter, CASE.shaft_flat)
    shaft = slab(d_shaft, (LEVELS.bushing_top, stack.encoder_shaft_top))
    tail_z = (LEVELS.pcb_bottom - SOLDER_TAIL, LEVELS.pcb_bottom)
    pins = [cylinder((centre[0] + dx, centre[1] + dy), 1.2, tail_z) for dx, dy in ENCODER_PINS]
    tabs = [centred_box((centre[0] + dx, centre[1] + dy), (3.0, 1.2), tail_z) for dx, dy in ENCODER_TABS]
    return body + bushing + shaft + pins + tabs


def display() -> Part:
    """nice!view on its socket strip: the module, the socket under its header end, the solder tails."""
    module = BOARD.display
    glass_top = BOARD.stack.display_glass_top
    module_bottom = glass_top - CASE.display_thickness
    board = centred_box((module.x, module.y), (module.length, module.width), (module_bottom, glass_top))
    header_length = module.header_pitch * len(module.header_pins)
    header_centre = (module.header_x, module.y)
    socket_strip = centred_box(header_centre, (module.header_pitch, header_length), (0, module_bottom))
    tails = centred_box(header_centre, (1.2, header_length), (LEVELS.pcb_bottom - SOLDER_TAIL, LEVELS.pcb_bottom))
    return board + socket_strip + tails


def usb_receptacle() -> Part:
    width, depth = CASE.usb_body
    mouth = -BOARD.usb.mouth_overhang
    z_range = (LEVELS.pcb_bottom - BOARD.usb.body_height, LEVELS.pcb_bottom)
    return box((BOARD.usb.x - width / 2, BOARD.usb.x + width / 2), (mouth, mouth + depth), z_range)


def usb_plug() -> Part:
    """The cable's overmould, seated against the receptacle mouth and running out of the back."""
    width, height = CASE.usb_plug
    mouth = -BOARD.usb.mouth_overhang
    z_range = (LEVELS.usb_centre - height / 2, LEVELS.usb_centre + height / 2)
    return box((BOARD.usb.x - width / 2, BOARD.usb.x + width / 2), (mouth - 25.0, mouth), z_range)


def led(edge_x: float, inward: int, y: float) -> Part:
    along_edge, depth, height = CASE.led_body
    x_range = sorted((edge_x, edge_x + inward * depth))
    return box(tuple(x_range), (y - along_edge / 2, y + along_edge / 2), (LEVELS.pcb_bottom - height, LEVELS.pcb_bottom))


def button(centre: tuple[float, float]) -> Part:
    width, height = CASE.button_body
    return centred_box(centre, (width, width), (LEVELS.pcb_bottom - height, LEVELS.pcb_bottom))


def components() -> dict[str, Part]:
    """Every bought part by name, in assembled position."""
    found = {"pcb": pcb(), "display": display(), "usb_receptacle": usb_receptacle(), "usb_plug": usb_plug()}
    for index, centre in enumerate(key_centres()):
        found[f"switch_{index}"] = switch(centre)
        found[f"socket_{index}"] = socket(centre)
    for side, centre in zip(("left", "right"), encoder_centres()):
        found[f"encoder_{side}"] = encoder(centre)
    for index, y in enumerate(BOARD.leds.left_y):
        found[f"led_left_{index}"] = led(0.0, 1, y)
    for index, y in enumerate(BOARD.leds.right_y):
        found[f"led_right_{index}"] = led(BOARD.board.width, -1, y)
    found["button_boot"] = button((BOARD.buttons.boot.x, BOARD.buttons.boot.y))
    found["button_reset"] = button((BOARD.buttons.reset.x, BOARD.buttons.reset.y))
    return found
