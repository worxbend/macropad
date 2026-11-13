//! The whole pad seen from above, to scale, beside a readout of what is done to it and what it
//! sends to the host. One such picture per demo frame makes the film.

use macropad_core::framebuffer::{HEIGHT, WIDTH};
use macropad_core::geometry::{KEY_COLUMNS, KEY_FIRST_X_UM, KEY_FIRST_Y_UM, KEY_PITCH_UM, LED_POSITIONS_UM};
use macropad_core::keymap::{KEY_COUNT, LAYERS, LAYER_COUNT};
use macropad_core::led::{LedFrame, Rgb, MAX_LEVEL};

use crate::board::{
    BOARD_HEIGHT_UM, BOARD_WIDTH_UM, DISPLAY_WINDOW_UM, KEYCAP_UM, KNOB_CAP_DIAMETER_UM, KNOB_DETENTS_PER_TURN,
    LEFT_KNOB_UM, RIGHT_KNOB_UM,
};
use crate::canvas::{led_on_screen, Canvas, Color, BACKDROP, CAPTION};
use crate::host_text::{describe, hex};
use crate::session::{HostEvent, Shot};

/// At 6 pixels per millimetre the 160 pixel display is 26.7 mm wide, the size of its real glass.
const PX_PER_MM: i32 = 6;
/// Space around the pad for the glow of the side LEDs.
const MARGIN: i32 = 30;
/// Case wall around the PCB; the diffuser strips sit in it.
const WALL: i32 = 9;
const GLOW_REACH: i32 = 26;
const STRIP_WIDTH: i32 = 5;
/// The strips run this far past the first and the last LED of a side.
const STRIP_OVERHANG_UM: i32 = 6_750;
const DECK_BOTTOM_UM: i32 = 21_000;
const USB_WIDTH_UM: i32 = 9_000;
const READOUT_WIDTH: i32 = WIDTH as i32 * READOUT_DISPLAY_SCALE as i32 + 2 * BEZEL;
const READOUT_DISPLAY_SCALE: usize = 3;
const BEZEL: i32 = 6;
const LOG_LINES: usize = 7;
const LINE: i32 = 12;
const READOUT_CHARS: usize = 40;

const CASE: Color = [0x24, 0x26, 0x2C];
const DECK: Color = [0x30, 0x33, 0x3A];
const GLASS_EDGE: Color = [0x0A, 0x0A, 0x0C];
const STRIP_UNLIT: Color = [0x34, 0x37, 0x3D];
const CAP_EDGE: Color = [0x2E, 0x31, 0x38];
const CAP_FACE: Color = [0x46, 0x4A, 0x54];
const CAP_DOWN: Color = [0xE6, 0xE8, 0xEC];
const LEGEND: Color = [0xB8, 0xBC, 0xC4];
const LEGEND_DOWN: Color = [0x1C, 0x20, 0x1A];
const KNOB_EDGE: Color = [0x50, 0x54, 0x5C];
const KNOB_TOP: Color = [0x6A, 0x6F, 0x78];
const DIM: Color = [0x8A, 0x90, 0x9A];

fn px(um: i32) -> i32 {
    (um * PX_PER_MM + 500) / 1000
}

/// A point on the PCB, in canvas pixels, for a pad whose PCB corner is at `origin`.
fn on_pad(origin: (i32, i32), um: (i32, i32)) -> (i32, i32) {
    (origin.0 + px(um.0), origin.1 + px(um.1))
}

pub fn key_centre_um(key: usize) -> (i32, i32) {
    let (column, row) = ((key % KEY_COLUMNS) as i32, (key / KEY_COLUMNS) as i32);
    (
        KEY_FIRST_X_UM + column * KEY_PITCH_UM,
        KEY_FIRST_Y_UM + row * KEY_PITCH_UM,
    )
}

/// The LEDs of one side of the pad, back to front, with their distance from the back edge.
fn side_leds(leds: &LedFrame, right_side: bool) -> Vec<(i32, Rgb)> {
    let mut side: Vec<(i32, Rgb)> = LED_POSITIONS_UM
        .iter()
        .zip(leds)
        .filter(|((x, _), _)| (*x > BOARD_WIDTH_UM / 2) == right_side)
        .map(|((_, y), led)| (*y, *led))
        .collect();
    side.sort_by_key(|(y, _)| *y);
    side
}

/// Light in the diffuser `y_um` from the back edge: the two nearest LEDs, mixed by distance.
fn strip_light(side: &[(i32, Rgb)], y_um: i32) -> Rgb {
    let after = side.partition_point(|(led_y, _)| *led_y <= y_um);
    match (after.checked_sub(1).map(|before| side[before]), side.get(after)) {
        (Some((before_y, before)), Some(&(after_y, next))) => {
            before.mixed(next, ((y_um - before_y) * 255 / (after_y - before_y)) as u8)
        }
        (Some((_, only)), None) | (None, Some(&(_, only))) => only,
        (None, None) => Rgb::BLACK,
    }
}

/// The light of one side's strip, row by row: (pixels from the back edge, colour to paint).
fn strip_rows(side: &[(i32, Rgb)]) -> impl Iterator<Item = (i32, Color)> + '_ {
    let ends = side.first().zip(side.last());
    let rows = ends.map_or(0..0, |(first, last)| {
        px(first.0 - STRIP_OVERHANG_UM)..px(last.0 + STRIP_OVERHANG_UM)
    });
    rows.map(|row| (row, led_on_screen(strip_light(side, row * 1000 / PX_PER_MM))))
}

/// Left edge of a side's strip. `outward` is -1 for the left side, 1 for the right.
fn strip_x(origin: (i32, i32), outward: i32) -> i32 {
    if outward > 0 {
        origin.0 + px(BOARD_WIDTH_UM) + WALL - STRIP_WIDTH
    } else {
        origin.0 - WALL
    }
}

/// Light spilling from a strip onto the desk. Drawn before the case.
fn draw_glow(canvas: &mut Canvas, origin: (i32, i32), side: &[(i32, Rgb)], outward: i32) {
    let edge_x = strip_x(origin, outward) + if outward > 0 { STRIP_WIDTH } else { -1 };
    for (row, light) in strip_rows(side) {
        for reach in 0..GLOW_REACH {
            let nearness = 1.0 - reach as f32 / GLOW_REACH as f32;
            canvas.add_light(
                edge_x + outward * reach,
                origin.1 + row,
                light,
                0.6 * nearness * nearness,
            );
        }
    }
}

/// The strip itself, set into the case wall. Drawn after the case.
fn draw_strip(canvas: &mut Canvas, origin: (i32, i32), side: &[(i32, Rgb)], outward: i32) {
    for (row, light) in strip_rows(side) {
        let lit = [0, 1, 2].map(|channel| light[channel].max(STRIP_UNLIT[channel]));
        canvas.fill(
            strip_x(origin, outward) as usize,
            (origin.1 + row) as usize,
            STRIP_WIDTH as usize,
            1,
            lit,
        );
    }
}

fn draw_case(canvas: &mut Canvas, origin: (i32, i32)) {
    let half = (px(BOARD_WIDTH_UM) / 2 + WALL, px(BOARD_HEIGHT_UM) / 2 + WALL);
    let centre = on_pad(origin, (BOARD_WIDTH_UM / 2, BOARD_HEIGHT_UM / 2));
    canvas.rounded(centre, half, 16, CASE);
    let deck_centre = on_pad(origin, (BOARD_WIDTH_UM / 2, DECK_BOTTOM_UM / 2));
    canvas.rounded(
        deck_centre,
        (px(BOARD_WIDTH_UM) / 2, px(DECK_BOTTOM_UM) / 2 - 3),
        10,
        DECK,
    );
    let usb_x = origin.0 + px(BOARD_WIDTH_UM / 2 - USB_WIDTH_UM / 2);
    canvas.fill(
        usb_x as usize,
        (origin.1 - WALL) as usize,
        px(USB_WIDTH_UM) as usize,
        4,
        GLASS_EDGE,
    );
}

/// The display at one picture pixel per display pixel, which is its real size at this scale.
fn draw_display(canvas: &mut Canvas, origin: (i32, i32), shot: &Shot) {
    let centre = on_pad(origin, DISPLAY_WINDOW_UM);
    let (half_width, half_height) = (WIDTH as i32 / 2, HEIGHT as i32 / 2);
    canvas.rounded(centre, (half_width + 4, half_height + 4), 3, GLASS_EDGE);
    canvas.display(
        (centre.0 - half_width) as usize,
        (centre.1 - half_height) as usize,
        &shot.display,
        1,
    );
}

/// A knob cap with a dot that shows how far it has been turned. A pressed knob is drawn light.
fn draw_knob(canvas: &mut Canvas, centre: (i32, i32), clicks: i32, down: bool) {
    let radius = px(KNOB_CAP_DIAMETER_UM / 2);
    let (top, dot) = if down {
        (CAP_DOWN, LEGEND_DOWN)
    } else {
        (KNOB_TOP, CAP_DOWN)
    };
    canvas.disc(centre, radius, KNOB_EDGE);
    canvas.disc(centre, radius - 6, top);
    let angle = clicks as f32 * std::f32::consts::TAU / KNOB_DETENTS_PER_TURN as f32;
    let reach = (radius - 15) as f32;
    let dot_centre = (
        centre.0 + (angle.sin() * reach).round() as i32,
        centre.1 - (angle.cos() * reach).round() as i32,
    );
    canvas.disc(dot_centre, 4, dot);
}

fn draw_key(canvas: &mut Canvas, centre: (i32, i32), legend: &str, down: bool) {
    let half = px(KEYCAP_UM / 2);
    let (face, ink) = if down {
        (CAP_DOWN, LEGEND_DOWN)
    } else {
        (CAP_FACE, LEGEND)
    };
    canvas.rounded(centre, (half, half), 8, CAP_EDGE);
    canvas.rounded(centre, (half - 9, half - 9), 6, face);
    let scale = 2;
    let width = (macropad_core::font::text_width(legend) * scale) as i32;
    canvas.text(
        (centre.0 - width / 2) as usize,
        (centre.1 - 7) as usize,
        legend,
        scale,
        ink,
    );
}

/// The pad from above with its PCB corner at `origin`: case, glowing strips, display, knobs, keys.
pub fn draw_pad(canvas: &mut Canvas, origin: (i32, i32), shot: &Shot) {
    let sides = [(side_leds(&shot.leds, false), -1), (side_leds(&shot.leds, true), 1)];
    for (side, outward) in &sides {
        draw_glow(canvas, origin, side, *outward);
    }
    draw_case(canvas, origin);
    for (side, outward) in &sides {
        draw_strip(canvas, origin, side, *outward);
    }
    draw_display(canvas, origin, shot);
    let inputs = &shot.inputs;
    draw_knob(
        canvas,
        on_pad(origin, LEFT_KNOB_UM),
        shot.knob_clicks[0],
        inputs.left_switch,
    );
    draw_knob(
        canvas,
        on_pad(origin, RIGHT_KNOB_UM),
        shot.knob_clicks[1],
        inputs.right_switch,
    );
    let layer = &LAYERS[shot.layer_index];
    for key in 0..KEY_COUNT {
        let down = inputs.keys & (1 << key) != 0;
        draw_key(canvas, on_pad(origin, key_centre_um(key)), layer.keys[key].label, down);
    }
}

fn pressed_legends(shot: &Shot) -> String {
    let layer = &LAYERS[shot.layer_index];
    let legends: Vec<&str> = (0..KEY_COUNT)
        .filter(|key| shot.inputs.keys & (1 << key) != 0)
        .map(|key| layer.keys[key].label)
        .collect();
    if legends.is_empty() {
        "KEYS  -".to_owned()
    } else {
        format!("KEYS  {}", legends.join(" + "))
    }
}

fn knob_line(shot: &Shot) -> String {
    let state = |down: bool| if down { "DOWN" } else { "UP" };
    format!(
        "KNOBS L {:+} {}, R {:+} {}",
        shot.knob_clicks[0],
        state(shot.inputs.left_switch),
        shot.knob_clicks[1],
        state(shot.inputs.right_switch)
    )
}

fn clipped(text: &str) -> &str {
    &text[..text.len().min(READOUT_CHARS)]
}

/// Text lines under each other; `y` is where the next one goes.
struct Column<'a> {
    canvas: &'a mut Canvas,
    x: i32,
    y: i32,
}

impl Column<'_> {
    fn caption(&mut self, text: &str) {
        self.y += LINE;
        self.canvas.text(self.x as usize, self.y as usize, text, 1, DIM);
        self.y += LINE + 2;
    }

    fn big(&mut self, text: &str) {
        self.canvas
            .text(self.x as usize, self.y as usize, clipped(text), 2, CAPTION);
        self.y += 2 * LINE - 4;
    }

    fn small(&mut self, text: &str) {
        self.canvas.text(self.x as usize, self.y as usize, text, 1, CAPTION);
        self.y += LINE;
    }
}

/// The readout beside the pad: the display enlarged, the inputs, the HID reports and their log.
fn draw_readout(canvas: &mut Canvas, corner: (i32, i32), shot: &Shot, host_log: &[HostEvent]) {
    let mut column = Column {
        canvas,
        x: corner.0,
        y: corner.1 - LINE,
    };
    column.caption("DISPLAY  160 X 68 PIXELS, SHOWN 3X");
    let glass = (WIDTH * READOUT_DISPLAY_SCALE, HEIGHT * READOUT_DISPLAY_SCALE);
    column.canvas.fill(
        column.x as usize,
        column.y as usize,
        READOUT_WIDTH as usize,
        glass.1 + 2 * BEZEL as usize,
        GLASS_EDGE,
    );
    column.canvas.display(
        (column.x + BEZEL) as usize,
        (column.y + BEZEL) as usize,
        &shot.display,
        READOUT_DISPLAY_SCALE,
    );
    column.y += glass.1 as i32 + 2 * BEZEL;
    column.caption("INPUT");
    column.big(&pressed_legends(shot));
    column.big(&knob_line(shot));
    column.caption("HOST SEES  USB HID");
    column.big(&describe(&shot.reports));
    column.small(&format!("KEYBOARD REPORT  {}", hex(&shot.reports.keyboard.to_bytes())));
    column.small(&format!(
        "CONSUMER REPORT  {}",
        hex(&shot.reports.consumer.to_le_bytes())
    ));
    column.caption("HOST LOG");
    for event in host_log.iter().rev().take(LOG_LINES).rev() {
        let seconds = event.at_ms as f64 / 1000.0;
        column.small(&format!("{seconds:8.3} S  {}", describe(&event.reports)));
    }
    column.y = corner.1 + px(BOARD_HEIGHT_UM) + WALL - 2 * LINE;
    column.caption(&format!(
        "LAYER {}/{} {}   LIGHT {}/{}   UPTIME {:.1} S",
        shot.layer_index + 1,
        LAYER_COUNT,
        LAYERS[shot.layer_index].name,
        shot.led_level,
        MAX_LEVEL,
        shot.uptime_ms as f64 / 1000.0
    ));
}

/// One frame of the film: the pad on the left, the readout on the right.
pub fn dashboard(shot: &Shot, host_log: &[HostEvent]) -> Canvas {
    let pad_block = 2 * (MARGIN + WALL) + px(BOARD_WIDTH_UM);
    let mut canvas = Canvas::new(
        (pad_block + READOUT_WIDTH + MARGIN) as usize,
        (2 * (MARGIN + WALL) + px(BOARD_HEIGHT_UM)) as usize,
        BACKDROP,
    );
    let origin = (MARGIN + WALL, MARGIN + WALL);
    draw_pad(&mut canvas, origin, shot);
    draw_readout(&mut canvas, (pad_block, MARGIN), shot, host_log);
    canvas
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::session::{Session, IDLE};
    use macropad_core::engine::Inputs;
    use macropad_core::quadrature::Rotation;

    const ORIGIN: (i32, i32) = (MARGIN + WALL, MARGIN + WALL);
    const RED: Rgb = Rgb::new(255, 0, 0);
    const BLUE: Rgb = Rgb::new(0, 0, 255);

    fn pixel_at(canvas: &Canvas, point: (i32, i32)) -> Color {
        canvas.pixel(point.0 as usize, point.1 as usize)
    }

    fn pad_of(shot: &Shot) -> Canvas {
        dashboard(shot, &[])
    }

    #[test]
    fn the_display_on_the_pad_is_as_wide_as_its_real_glass() {
        let glass_width_mm = WIDTH as f32 / PX_PER_MM as f32;
        assert!((glass_width_mm - 27.0).abs() < 0.5, "{glass_width_mm} mm");
    }

    #[test]
    fn a_pressed_key_is_drawn_light_and_the_others_stay_dark() {
        let mut session = Session::settled_on(1);
        session.run(Inputs { keys: 1 << 6, ..IDLE }, 20);
        let picture = pad_of(&session.shot());
        let corner_of = |key| {
            let centre = on_pad(ORIGIN, key_centre_um(key));
            (centre.0 - px(KEYCAP_UM / 2) + 14, centre.1 - px(KEYCAP_UM / 2) + 14)
        };
        assert_eq!(pixel_at(&picture, corner_of(6)), CAP_DOWN);
        assert_eq!(pixel_at(&picture, corner_of(5)), CAP_FACE);
    }

    #[test]
    fn the_knob_dot_starts_at_the_top_and_moves_clockwise_with_the_clicks() {
        let mut session = Session::settled_on(0);
        let centre = on_pad(ORIGIN, RIGHT_KNOB_UM);
        let reach = px(KNOB_CAP_DIAMETER_UM / 2) - 15;
        assert_eq!(
            pixel_at(&pad_of(&session.shot()), (centre.0, centre.1 - reach)),
            CAP_DOWN
        );
        session.turn(crate::session::Knob::Right, Rotation::Clockwise, 9, IDLE);
        let quarter_turn = pad_of(&session.shot());
        assert_eq!(pixel_at(&quarter_turn, (centre.0 + reach, centre.1)), CAP_DOWN);
        assert_eq!(pixel_at(&quarter_turn, (centre.0, centre.1 - reach)), KNOB_TOP);
    }

    #[test]
    fn each_side_lists_its_leds_from_the_back_edge_to_the_front() {
        let mut leds = [Rgb::BLACK; 8];
        leds[0] = RED;
        leds[7] = BLUE;
        let (left, right) = (side_leds(&leds, false), side_leds(&leds, true));
        assert_eq!((left.len(), right.len()), (4, 4));
        assert_eq!((right[0].1, left[0].1), (RED, BLUE));
        assert!(left.windows(2).all(|pair| pair[0].0 < pair[1].0));
    }

    #[test]
    fn strip_light_is_the_led_at_an_led_and_a_mix_between_two() {
        let side = [(30_000, RED), (43_500, BLUE)];
        assert_eq!(strip_light(&side, 30_000), RED);
        assert_eq!(strip_light(&side, 20_000), RED);
        assert_eq!(strip_light(&side, 50_000), BLUE);
        let between = strip_light(&side, 36_000);
        assert!(between.r > 0 && between.b > 0);
    }

    #[test]
    fn the_strips_glow_outward_in_the_colour_of_the_nearest_led() {
        let mut shot = Session::settled_on(1).shot();
        shot.leds = [Rgb::BLACK; 8];
        shot.leds[0] = RED;
        let picture = pad_of(&shot);
        let beside_first_led = |outside_x| (outside_x, ORIGIN.1 + px(LED_POSITIONS_UM[0].1));
        let right_glow = pixel_at(&picture, beside_first_led(ORIGIN.0 + px(BOARD_WIDTH_UM) + WALL + 3));
        let left_glow = pixel_at(&picture, beside_first_led(ORIGIN.0 - WALL - 4));
        assert!(
            right_glow[0] > BACKDROP[0] + 60 && right_glow[1] == BACKDROP[1],
            "{right_glow:?}"
        );
        assert_eq!(left_glow, BACKDROP);
    }

    #[test]
    fn every_readout_line_fits_and_uses_the_font() {
        let mut session = Session::settled_on(1);
        session.run(
            Inputs {
                keys: 0b1111_1111_1111,
                ..IDLE
            },
            20,
        );
        let shot = session.shot();
        for line in [pressed_legends(&shot), knob_line(&shot), describe(&shot.reports)] {
            assert!(line.bytes().all(|byte| (0x20..0x60).contains(&byte)), "{line}");
        }
        assert!(clipped(&pressed_legends(&shot)).len() <= READOUT_CHARS);
        assert!(knob_line(&shot).len() <= READOUT_CHARS);
    }
}
