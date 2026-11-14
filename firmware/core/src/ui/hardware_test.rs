//! The hardware test screen: every contact as the pins read it, and which LED should be lit.
//! A filled box is a closed contact (pin low), an empty one an open contact.

use core::fmt::Write;

use super::screens::draw_title_tab;
use super::Line;
use crate::font::{text_width, GLYPH_HEIGHT};
use crate::framebuffer::{Framebuffer, Rect, HEIGHT, WIDTH};
use crate::geometry::KEY_COLUMNS;
use crate::hardware_test::{KnobContacts, TestView};
use crate::keymap::KEY_COUNT;

const MARGIN: usize = 2;
const BOX: usize = 10;
const PITCH: usize = 13;
const TOP_Y: usize = 13;
/// Text inside a box-high row starts this far down.
const TEXT_DROP: usize = (BOX - GLYPH_HEIGHT) / 2 + 1;

const KEYS_X: usize = MARGIN;
const KEY_ROWS: usize = KEY_COUNT / KEY_COLUMNS;
const KEYS_BITMAP_Y: usize = TOP_Y + KEY_ROWS * PITCH + 1;

const KNOB_LABEL_X: usize = 70;
const KNOB_HEADER_Y: usize = TOP_Y;
const KNOB_ROWS_Y: usize = TOP_Y + GLYPH_HEIGHT + 3;
const LEFT_KNOB_X: usize = 100;
const RIGHT_KNOB_X: usize = 135;
const HINT_Y: usize = HEIGHT - GLYPH_HEIGHT;

pub fn draw(frame: &mut Framebuffer, view: &TestView) {
    draw_title_tab(frame, "HW TEST");
    draw_led_step(frame, view);
    draw_keys(frame, view.raw.keys);
    draw_knobs(frame, view.raw.left, view.raw.right);
    frame.text(KEYS_X, HINT_Y, "UNPLUG TO LEAVE");
}

fn draw_led_step(frame: &mut Framebuffer, view: &TestView) {
    let step = view.led_step();
    let mut text: Line<12> = Line::new();
    // `Line::write_str` never fails. LED1 is the first LED of the chain.
    let _ = write!(text, "LED{} {}", step.led + 1, step.colour_name());
    frame.text(WIDTH - MARGIN - text_width(text.as_str()), 1, text.as_str());
}

/// The twelve keys as they sit on the pad, and the same bitmap in hexadecimal.
fn draw_keys(frame: &mut Framebuffer, keys: u16) {
    for key in 0..KEY_COUNT {
        let (column, row) = (key % KEY_COLUMNS, key / KEY_COLUMNS);
        contact_box(
            frame,
            KEYS_X + column * PITCH,
            TOP_Y + row * PITCH,
            keys & 1 << key != 0,
        );
    }
    let mut bitmap: Line<12> = Line::new();
    let _ = write!(bitmap, "KEYS {keys:03X}");
    frame.text(KEYS_X, KEYS_BITMAP_Y, bitmap.as_str());
}

fn draw_knobs(frame: &mut Framebuffer, left: KnobContacts, right: KnobContacts) {
    frame.text(LEFT_KNOB_X + BOX / 2 - text_width("LEFT") / 2, KNOB_HEADER_Y, "LEFT");
    frame.text(RIGHT_KNOB_X + BOX / 2 - text_width("RIGHT") / 2, KNOB_HEADER_Y, "RIGHT");
    let rows = [
        ("A", left.a, right.a),
        ("B", left.b, right.b),
        ("SW", left.switch, right.switch),
    ];
    for (index, (label, left_closed, right_closed)) in rows.into_iter().enumerate() {
        let y = KNOB_ROWS_Y + index * PITCH;
        frame.text(KNOB_LABEL_X, y + TEXT_DROP, label);
        contact_box(frame, LEFT_KNOB_X, y, left_closed);
        contact_box(frame, RIGHT_KNOB_X, y, right_closed);
    }
}

fn contact_box(frame: &mut Framebuffer, x: usize, y: usize, closed: bool) {
    let area = Rect {
        x,
        y,
        width: BOX,
        height: BOX,
    };
    if closed {
        frame.fill(area);
    } else {
        frame.outline(area);
    }
}

const _: () = assert!(
    KEYS_X + KEY_COLUMNS * PITCH <= KNOB_LABEL_X,
    "the key grid must end left of the knob table"
);
const _: () = assert!(
    KEYS_BITMAP_Y + GLYPH_HEIGHT < HINT_Y,
    "the key bitmap line must end above the hint"
);
const _: () = assert!(
    KNOB_ROWS_Y + 2 * PITCH + BOX < HINT_Y,
    "the knob table must end above the hint"
);
const _: () = assert!(
    RIGHT_KNOB_X + BOX <= WIDTH - MARGIN,
    "the knob table must fit the panel"
);

#[cfg(test)]
mod tests {
    use super::super::test_support::ink_in;
    use super::*;
    use crate::hardware_test::{RawInputs, LED_STEP_MS};

    fn screen(raw: RawInputs, uptime_ms: u64) -> Framebuffer {
        TestView { raw, uptime_ms }.screen()
    }

    fn inside(x: usize, y: usize) -> Rect {
        Rect {
            x,
            y,
            width: BOX,
            height: BOX,
        }
        .inset(2)
    }

    fn key_inside(key: usize) -> Rect {
        inside(KEYS_X + key % KEY_COLUMNS * PITCH, TOP_Y + key / KEY_COLUMNS * PITCH)
    }

    #[test]
    fn a_closed_key_fills_its_own_box_only() {
        let frame = screen(
            RawInputs {
                keys: 1 << 6,
                ..RawInputs::default()
            },
            0,
        );
        for key in 0..KEY_COUNT {
            let filled = ink_in(&frame, key_inside(key)) > 0;
            assert_eq!(filled, key == 6, "key {key}");
        }
    }

    #[test]
    fn the_key_bitmap_is_also_written_in_hexadecimal() {
        let bitmap_line = Rect {
            x: KEYS_X + text_width("KEYS "),
            y: KEYS_BITMAP_Y,
            width: text_width("000"),
            height: GLYPH_HEIGHT,
        };
        let none = screen(RawInputs::default(), 0);
        let all = screen(
            RawInputs {
                keys: 0xFFF,
                ..RawInputs::default()
            },
            0,
        );
        assert_ne!(ink_in(&none, bitmap_line), ink_in(&all, bitmap_line));
    }

    #[test]
    fn each_knob_contact_fills_its_own_box() {
        let closed = KnobContacts {
            a: false,
            b: true,
            switch: false,
        };
        let frame = screen(
            RawInputs {
                right: closed,
                ..RawInputs::default()
            },
            0,
        );
        for row in 0..3 {
            let y = KNOB_ROWS_Y + row * PITCH;
            assert_eq!(ink_in(&frame, inside(LEFT_KNOB_X, y)), 0, "left row {row}");
            assert_eq!(ink_in(&frame, inside(RIGHT_KNOB_X, y)) > 0, row == 1, "right row {row}");
        }
    }

    #[test]
    fn the_led_line_follows_the_lit_led() {
        let corner = Rect {
            x: WIDTH / 2,
            y: 0,
            width: WIDTH / 2,
            height: GLYPH_HEIGHT + 2,
        };
        let first = screen(RawInputs::default(), 0);
        let next = screen(RawInputs::default(), LED_STEP_MS);
        assert!(ink_in(&first, corner) > 0);
        assert!(first != next);
    }
}
