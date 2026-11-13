//! The LED timeline: the colour of each LED over the demo film, with the screens and the
//! film time marked, so a glance shows what the lighting does when.

use macropad_core::geometry::LED_POSITIONS_UM;
use macropad_core::led::LED_COUNT;
use macropad_core::ui::Screen;

use crate::board::BOARD_WIDTH_UM;
use crate::canvas::{led_on_screen, Canvas, BACKDROP, CAPTION};
use crate::session::{Shot, FRAME_MS};

/// One column of this width per demo frame, one row of this height per LED.
const COLUMN: usize = 3;
const ROW: usize = 14;
const ROW_GAP: usize = 2;
/// Room for the row labels on the left, the screen names above and the time scale below.
const LABELS_WIDTH: usize = 86;
const HEADER_HEIGHT: usize = 24;
const FOOTER_HEIGHT: usize = 24;
const RIGHT_MARGIN: usize = 30;
const TICK: usize = 4;
const FRAMES_PER_SECOND: usize = 1000 / FRAME_MS as usize;

/// "LED 0 RIGHT" and so on: the chain index and the side of the pad the LED is on.
pub fn led_label(led: usize) -> String {
    let side = if LED_POSITIONS_UM[led].0 > BOARD_WIDTH_UM / 2 {
        "RIGHT"
    } else {
        "LEFT"
    };
    format!("LED {led} {side}")
}

/// The frames at which a different screen comes up, with that screen.
fn screen_changes(frames: &[Shot]) -> Vec<(usize, Screen)> {
    let mut changes: Vec<(usize, Screen)> = Vec::new();
    for (index, frame) in frames.iter().enumerate() {
        if changes.last().is_none_or(|(_, screen)| *screen != frame.screen) {
            changes.push((index, frame.screen));
        }
    }
    changes
}

fn draw_header(timeline: &mut Canvas, frames: &[Shot]) {
    for (frame, screen) in screen_changes(frames) {
        let x = LABELS_WIDTH + frame * COLUMN;
        timeline.fill(x, 0, 1, HEADER_HEIGHT - 2, CAPTION);
        timeline.text(x + 3, 2, &format!("{screen:?}").to_uppercase(), 1, CAPTION);
    }
}

fn draw_time_scale(timeline: &mut Canvas, frames: usize, y: usize) {
    for second in 0..=frames / FRAMES_PER_SECOND {
        let x = LABELS_WIDTH + second * FRAMES_PER_SECOND * COLUMN;
        timeline.fill(x, y, 1, TICK, CAPTION);
        if second % 2 == 0 {
            timeline.text(x.saturating_sub(2), y + TICK + 2, &second.to_string(), 1, CAPTION);
        }
    }
    timeline.text(2, y + TICK + 2, "FILM TIME, S", 1, CAPTION);
}

/// LED colours over the demo: time runs left to right, the chain top to bottom.
pub fn led_timeline(frames: &[Shot]) -> Canvas {
    let rows_height = LED_COUNT * ROW;
    let mut timeline = Canvas::new(
        LABELS_WIDTH + frames.len() * COLUMN + RIGHT_MARGIN,
        HEADER_HEIGHT + rows_height + FOOTER_HEIGHT,
        BACKDROP,
    );
    draw_header(&mut timeline, frames);
    for led in 0..LED_COUNT {
        let y = HEADER_HEIGHT + led * ROW;
        timeline.text(2, y + 2, &led_label(led), 1, CAPTION);
        for (column, frame) in frames.iter().enumerate() {
            let x = LABELS_WIDTH + column * COLUMN;
            timeline.fill(x, y, COLUMN, ROW - ROW_GAP, led_on_screen(frame.leds[led]));
        }
    }
    draw_time_scale(&mut timeline, frames.len(), HEADER_HEIGHT + rows_height);
    timeline
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::session::Session;
    use macropad_core::led::Rgb;

    fn film(ms: u32) -> Vec<Shot> {
        let mut session = Session::new();
        session.start_recording();
        session.wait(ms);
        session.into_film().frames
    }

    #[test]
    fn the_first_four_leds_are_labelled_right_and_the_rest_left() {
        assert_eq!(led_label(0), "LED 0 RIGHT");
        assert_eq!(led_label(3), "LED 3 RIGHT");
        assert_eq!(led_label(4), "LED 4 LEFT");
        assert_eq!(led_label(7), "LED 7 LEFT");
    }

    #[test]
    fn a_screen_is_named_once_where_it_comes_up() {
        let changes = screen_changes(&film(3000));
        assert_eq!(changes.len(), 2);
        assert_eq!(changes[0], (0, Screen::Splash));
        assert_eq!(changes[1].1, Screen::Main);
    }

    #[test]
    fn each_led_gets_its_row_and_each_frame_its_column() {
        let mut frames = film(200);
        frames[1].leds = [Rgb::BLACK; LED_COUNT];
        frames[1].leds[2] = Rgb::new(255, 0, 0);
        let timeline = led_timeline(&frames);
        let cell = |frame: usize, led: usize| timeline.pixel(LABELS_WIDTH + frame * COLUMN, HEADER_HEIGHT + led * ROW);
        assert_eq!(cell(1, 2), [255, 0, 0]);
        assert_eq!(cell(1, 3), [0, 0, 0]);
        assert_eq!(timeline.width, LABELS_WIDTH + frames.len() * COLUMN + RIGHT_MARGIN);
    }
}
