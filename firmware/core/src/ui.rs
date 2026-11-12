//! The screen: layer name, lock states, typing rate, knob functions and the key legend grid.

use crate::font::{text_width, GLYPH_HEIGHT};
use crate::framebuffer::{Framebuffer, Rect, HEIGHT, WIDTH};
use crate::keymap::{Layer, KEY_COUNT};
use crate::kps::HISTORY_BUCKETS;

/// Longest label that fits a key cell.
pub const MAX_LABEL_CHARS: usize = 6;

const MARGIN: usize = 2;
const STATUS_TEXT_Y: usize = 1;
const CAPS_X: usize = 62;
const NUM_X: usize = 88;
const SPARKLINE_X: usize = WIDTH - MARGIN - HISTORY_BUCKETS;
const SPARKLINE_BOTTOM_Y: usize = 8;
const SPARKLINE_MAX_HEIGHT: usize = 8;
const STATUS_RULE_Y: usize = 10;
const KNOB_TEXT_Y: usize = 12;
const KNOB_RULE_Y: usize = 20;
const GRID_Y: usize = 21;
const GRID_COLUMNS: usize = 4;
const CELL_WIDTH: usize = WIDTH / GRID_COLUMNS;
const CELL_HEIGHT: usize = 15;
const GRID_ROWS: usize = KEY_COUNT / GRID_COLUMNS;
const _: () = assert!(
    GRID_Y + GRID_ROWS * CELL_HEIGHT <= HEIGHT,
    "the key grid must end inside the panel"
);

/// Everything the screen shows.
pub struct UiState<'a> {
    pub layer: &'a Layer,
    /// Bit `n` is set while key `n` is down.
    pub pressed_keys: u16,
    pub kps_history: [u8; HISTORY_BUCKETS],
    pub caps_lock: bool,
    pub num_lock: bool,
}

pub fn draw(state: &UiState) -> Framebuffer {
    let mut frame = Framebuffer::default();
    draw_status_bar(&mut frame, state);
    draw_knob_row(&mut frame, state.layer);
    draw_key_grid(&mut frame, state);
    frame
}

fn draw_status_bar(frame: &mut Framebuffer, state: &UiState) {
    frame.text(MARGIN, STATUS_TEXT_Y, state.layer.name);
    if state.caps_lock {
        draw_badge(frame, CAPS_X, "CAP");
    }
    if state.num_lock {
        draw_badge(frame, NUM_X, "NUM");
    }
    for (bucket, &presses) in state.kps_history.iter().enumerate() {
        frame.bar(
            SPARKLINE_X + bucket,
            SPARKLINE_BOTTOM_Y,
            usize::from(presses).min(SPARKLINE_MAX_HEIGHT),
        );
    }
    frame.horizontal_line(STATUS_RULE_Y);
}

/// Light text on a dark box.
fn draw_badge(frame: &mut Framebuffer, x: usize, text: &str) {
    frame.text(x, STATUS_TEXT_Y, text);
    let box_around_text = Rect {
        x: x - 1,
        y: 0,
        width: text_width(text) + 2,
        height: GLYPH_HEIGHT + 2,
    };
    frame.invert(box_around_text);
}

fn draw_knob_row(frame: &mut Framebuffer, layer: &Layer) {
    let left = layer.left_knob.label;
    let press = layer.right_knob_press.label;
    let right = layer.right_knob.label;
    frame.text(MARGIN, KNOB_TEXT_Y, left);
    frame.text((WIDTH - text_width(press)) / 2, KNOB_TEXT_Y, press);
    frame.text(WIDTH - MARGIN - text_width(right), KNOB_TEXT_Y, right);
    frame.horizontal_line(KNOB_RULE_Y);
}

fn draw_key_grid(frame: &mut Framebuffer, state: &UiState) {
    for (key, binding) in state.layer.keys.iter().enumerate() {
        let cell = Rect {
            x: key % GRID_COLUMNS * CELL_WIDTH,
            y: GRID_Y + key / GRID_COLUMNS * CELL_HEIGHT,
            width: CELL_WIDTH,
            height: CELL_HEIGHT,
        };
        let text_x = cell.x + (CELL_WIDTH - text_width(binding.label)) / 2;
        frame.text(text_x, cell.y + (CELL_HEIGHT - GLYPH_HEIGHT) / 2, binding.label);
        if state.pressed_keys & (1 << key) != 0 {
            frame.invert(Rect {
                x: cell.x + 1,
                y: cell.y + 1,
                width: CELL_WIDTH - 2,
                height: CELL_HEIGHT - 2,
            });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::keymap::LAYERS;

    fn idle(layer: &Layer) -> UiState<'_> {
        UiState {
            layer,
            pressed_keys: 0,
            kps_history: [0; HISTORY_BUCKETS],
            caps_lock: false,
            num_lock: false,
        }
    }

    fn ink_in(frame: &Framebuffer, area: Rect) -> usize {
        let xs = area.x..area.x + area.width;
        (area.y..area.y + area.height)
            .flat_map(|y| xs.clone().map(move |x| (x, y)))
            .filter(|&(x, y)| frame.has_ink(x, y))
            .count()
    }

    fn cell(key: usize) -> Rect {
        Rect {
            x: key % 4 * CELL_WIDTH,
            y: GRID_Y + key / 4 * CELL_HEIGHT,
            width: CELL_WIDTH,
            height: CELL_HEIGHT,
        }
    }

    #[test]
    fn every_layer_draws_a_legend_in_every_cell() {
        for layer in &LAYERS {
            let frame = draw(&idle(layer));
            assert!((0..12).all(|key| ink_in(&frame, cell(key)) > 0), "{}", layer.name);
        }
    }

    #[test]
    fn a_pressed_key_inverts_only_its_own_cell() {
        let released = draw(&idle(&LAYERS[0]));
        let pressed = draw(&UiState {
            pressed_keys: 1 << 5,
            ..idle(&LAYERS[0])
        });
        let cell_area = CELL_WIDTH * CELL_HEIGHT;
        assert!(ink_in(&pressed, cell(5)) > cell_area / 2);
        assert_eq!(ink_in(&pressed, cell(4)), ink_in(&released, cell(4)));
        assert_eq!(ink_in(&pressed, cell(6)), ink_in(&released, cell(6)));
    }

    #[test]
    fn lock_badges_appear_only_when_the_lock_is_on() {
        let status_bar = Rect {
            x: CAPS_X - 1,
            y: 0,
            width: 50,
            height: 9,
        };
        let off = draw(&idle(&LAYERS[0]));
        let on = draw(&UiState {
            caps_lock: true,
            num_lock: true,
            ..idle(&LAYERS[0])
        });
        assert_eq!(ink_in(&off, status_bar), 0);
        assert!(ink_in(&on, status_bar) > 0);
    }

    #[test]
    fn sparkline_bars_follow_the_history_and_are_capped() {
        let mut history = [0; HISTORY_BUCKETS];
        history[0] = 3;
        history[HISTORY_BUCKETS - 1] = 200;
        let frame = draw(&UiState {
            kps_history: history,
            ..idle(&LAYERS[0])
        });
        let column = |x| Rect {
            x,
            y: 0,
            width: 1,
            height: STATUS_RULE_Y,
        };
        assert_eq!(ink_in(&frame, column(SPARKLINE_X)), 3);
        assert_eq!(ink_in(&frame, column(WIDTH - MARGIN - 1)), SPARKLINE_MAX_HEIGHT);
    }

    #[test]
    fn right_knob_label_ends_at_the_right_margin() {
        let frame = draw(&idle(&LAYERS[0]));
        let margin = Rect {
            x: WIDTH - MARGIN,
            y: KNOB_TEXT_Y,
            width: MARGIN,
            height: GLYPH_HEIGHT,
        };
        let last_glyph = Rect {
            x: WIDTH - MARGIN - 5,
            y: KNOB_TEXT_Y,
            width: 5,
            height: GLYPH_HEIGHT,
        };
        assert_eq!(ink_in(&frame, margin), 0);
        assert!(ink_in(&frame, last_glyph) > 0);
    }
}
