//! The everyday screen: layer tab, lock states, typing rate, knob functions, key legends.

use super::{invert_rounded, outline_rounded, UiState};
use crate::font::{text_width, GLYPH_HEIGHT};
use crate::framebuffer::{Framebuffer, Rect, Sprite, HEIGHT, WIDTH};
use crate::keymap::{Layer, KEY_COUNT, LAYER_COUNT};
use crate::kps::HISTORY_BUCKETS;

const MARGIN: usize = 2;
const STATUS_TEXT_Y: usize = 1;
const TAB_PADDING: usize = 3;
const PIP_GAP_AFTER_TAB: usize = 4;
const PIP_Y: usize = 3;
const PIP_SIZE: usize = 3;
const PIP_PITCH: usize = 5;
const CAPS_X: usize = 68;
const NUM_X: usize = 92;
const SPARKLINE_X: usize = WIDTH - MARGIN - HISTORY_BUCKETS;
const SPARKLINE_BOTTOM_Y: usize = 8;
const SPARKLINE_MAX_HEIGHT: usize = 8;
const STATUS_RULE_Y: usize = 10;
const KNOB_TEXT_Y: usize = 12;
const KNOB_RULE_Y: usize = 20;
const ICON_SIZE: usize = 7;
const ICON_GAP: usize = 2;
const GRID_Y: usize = 21;
const GRID_COLUMNS: usize = 4;
const CELL_WIDTH: usize = WIDTH / GRID_COLUMNS;
const CELL_HEIGHT: usize = 15;
const GRID_ROWS: usize = KEY_COUNT / GRID_COLUMNS;
/// A key keeps an outline this long after it went down, so even a quick tap is seen.
const KEY_GLOW_MS: u16 = 300;
const _: () = assert!(
    GRID_Y + GRID_ROWS * CELL_HEIGHT <= HEIGHT,
    "the key grid must end inside the panel"
);
const _: () = assert!(
    super::MAX_LABEL_CHARS * 6 + 2 * TAB_PADDING + PIP_GAP_AFTER_TAB + LAYER_COUNT * PIP_PITCH < CAPS_X,
    "the longest layer tab and its pips must end before the lock badges"
);

/// A knob seen from above, with its pointer mark: this function is on a turn.
const TURN_ICON: Sprite<ICON_SIZE> = [
    0b0011_1000,
    0b0101_0100,
    0b1001_0010,
    0b1000_0010,
    0b1000_0010,
    0b0100_0100,
    0b0011_1000,
];
/// A solid button: this function is on a knob press.
const PRESS_ICON: Sprite<ICON_SIZE> = [
    0b0011_1000,
    0b0111_1100,
    0b1111_1110,
    0b1111_1110,
    0b1111_1110,
    0b0111_1100,
    0b0011_1000,
];

pub(super) fn draw(frame: &mut Framebuffer, state: &UiState) {
    draw_status_bar(frame, state);
    draw_knob_row(frame, state.view.layer());
    draw_key_grid(frame, state);
}

fn draw_status_bar(frame: &mut Framebuffer, state: &UiState) {
    let pips_x = draw_layer_tab(frame, state.view.layer().name) + PIP_GAP_AFTER_TAB;
    draw_layer_pips(frame, pips_x, state.view.activity.layer_index);
    if state.host.caps_lock {
        draw_badge(frame, CAPS_X, "CAP");
    }
    if state.host.num_lock {
        draw_badge(frame, NUM_X, "NUM");
    }
    for (bucket, &presses) in state.view.kps_history.iter().enumerate() {
        frame.bar(
            SPARKLINE_X + bucket,
            SPARKLINE_BOTTOM_Y,
            usize::from(presses).min(SPARKLINE_MAX_HEIGHT),
        );
    }
    frame.horizontal_line(STATUS_RULE_Y);
}

/// Light layer name on a dark tab that stands on the status rule. Returns the tab's width.
fn draw_layer_tab(frame: &mut Framebuffer, name: &str) -> usize {
    let tab_width = text_width(name) + 2 * TAB_PADDING;
    frame.text(TAB_PADDING, STATUS_TEXT_Y, name);
    frame.invert(Rect {
        x: 0,
        y: 0,
        width: tab_width,
        height: STATUS_RULE_Y,
    });
    tab_width
}

/// One mark per layer: a square for the active one, a dot for the others.
fn draw_layer_pips(frame: &mut Framebuffer, x: usize, active_layer: usize) {
    for layer in 0..LAYER_COUNT {
        let pip_x = x + layer * PIP_PITCH;
        if layer == active_layer {
            frame.fill(Rect {
                x: pip_x,
                y: PIP_Y,
                width: PIP_SIZE,
                height: PIP_SIZE,
            });
        } else {
            frame.ink(pip_x + PIP_SIZE / 2, PIP_Y + PIP_SIZE / 2);
        }
    }
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
    let press = layer.right_knob_press.label;
    let right = layer.right_knob.label;
    draw_function(frame, MARGIN, &TURN_ICON, layer.left_knob.label);
    draw_function(frame, (WIDTH - function_width(press)) / 2, &PRESS_ICON, press);
    draw_function(frame, WIDTH - MARGIN - function_width(right), &TURN_ICON, right);
    frame.horizontal_line(KNOB_RULE_Y);
}

/// An icon and the label of what it does, starting at `x`.
fn draw_function(frame: &mut Framebuffer, x: usize, icon: &Sprite<ICON_SIZE>, label: &str) {
    frame.sprite(x, KNOB_TEXT_Y, icon);
    frame.text(x + ICON_SIZE + ICON_GAP, KNOB_TEXT_Y, label);
}

fn function_width(label: &str) -> usize {
    ICON_SIZE + ICON_GAP + text_width(label)
}

fn draw_key_grid(frame: &mut Framebuffer, state: &UiState) {
    let view = &state.view;
    for (key, binding) in view.layer().keys.iter().enumerate() {
        let cell = cell(key);
        let text_x = cell.x + (CELL_WIDTH - text_width(binding.label)) / 2;
        frame.text(text_x, cell.y + (CELL_HEIGHT - GLYPH_HEIGHT) / 2, binding.label);
        if view.pressed_keys & (1 << key) != 0 {
            invert_rounded(frame, cell.inset(1));
        } else if view.activity.key_age_ms[key] < KEY_GLOW_MS {
            outline_rounded(frame, cell.inset(1));
        }
    }
}

fn cell(key: usize) -> Rect {
    Rect {
        x: key % GRID_COLUMNS * CELL_WIDTH,
        y: GRID_Y + key / GRID_COLUMNS * CELL_HEIGHT,
        width: CELL_WIDTH,
        height: CELL_HEIGHT,
    }
}

#[cfg(test)]
mod tests {
    use super::super::test_support::*;
    use super::super::{draw, UiState};
    use super::*;
    use crate::keymap::LAYERS;
    use crate::pad::Host;

    fn with_keys_down(state: UiState, pressed_keys: u16) -> UiState {
        let mut state = state;
        state.view.pressed_keys = pressed_keys;
        state
    }

    #[test]
    fn every_layer_draws_a_legend_in_every_cell() {
        for (index, layer) in LAYERS.iter().enumerate() {
            let frame = draw(&settled(index));
            assert!((0..12).all(|key| ink_in(&frame, cell(key)) > 0), "{}", layer.name);
        }
    }

    #[test]
    fn a_pressed_key_inverts_only_its_own_cell() {
        let released = draw(&settled(0));
        let pressed = draw(&with_keys_down(settled(0), 1 << 5));
        let cell_area = CELL_WIDTH * CELL_HEIGHT;
        assert!(ink_in(&pressed, cell(5)) > cell_area / 2);
        assert_eq!(ink_in(&pressed, cell(4)), ink_in(&released, cell(4)));
        assert_eq!(ink_in(&pressed, cell(6)), ink_in(&released, cell(6)));
    }

    #[test]
    fn a_tapped_key_keeps_an_outline_for_a_moment_after_release() {
        let mut pad = pad_on(0);
        let calm = draw(&state_of(&pad));
        run(&mut pad, crate::engine::Inputs { keys: 1 << 5, ..IDLE }, 20);
        run(&mut pad, IDLE, 100);
        let glowing = draw(&state_of(&pad));
        let outline_pixels = 2 * (CELL_WIDTH - 2) + 2 * (CELL_HEIGHT - 4) - 4;
        assert_eq!(ink_in(&glowing, cell(5)), ink_in(&calm, cell(5)) + outline_pixels);
        run(&mut pad, IDLE, u32::from(KEY_GLOW_MS));
        assert_eq!(ink_in(&draw(&state_of(&pad)), cell(5)), ink_in(&calm, cell(5)));
    }

    #[test]
    fn lock_badges_appear_only_when_the_lock_is_on() {
        let status_bar = Rect {
            x: CAPS_X - 1,
            y: 0,
            width: 50,
            height: 9,
        };
        let off = draw(&settled(0));
        let on = draw(&UiState {
            host: Host {
                caps_lock: true,
                num_lock: true,
                asleep: false,
            },
            ..settled(0)
        });
        assert_eq!(ink_in(&off, status_bar), 0);
        assert!(ink_in(&on, status_bar) > 0);
    }

    #[test]
    fn sparkline_bars_follow_the_history_and_are_capped() {
        let mut state = settled(0);
        state.view.kps_history = [0; HISTORY_BUCKETS];
        state.view.kps_history[0] = 3;
        state.view.kps_history[HISTORY_BUCKETS - 1] = 200;
        let frame = draw(&state);
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
        let frame = draw(&settled(0));
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

    #[test]
    fn the_layer_tab_is_dark_and_exactly_one_pip_is_a_square() {
        for (index, layer) in LAYERS.iter().enumerate() {
            let frame = draw(&settled(index));
            let tab_width = text_width(layer.name) + 2 * TAB_PADDING;
            assert!(frame.has_ink(0, 0) && frame.has_ink(tab_width - 1, STATUS_RULE_Y - 1));
            let pips = Rect {
                x: tab_width + PIP_GAP_AFTER_TAB,
                y: PIP_Y,
                width: LAYER_COUNT * PIP_PITCH,
                height: PIP_SIZE,
            };
            let square_and_dots = PIP_SIZE * PIP_SIZE + LAYER_COUNT - 1;
            assert_eq!(ink_in(&frame, pips), square_and_dots, "{}", layer.name);
            assert!(frame.has_ink(pips.x + index * PIP_PITCH, PIP_Y));
        }
    }

    #[test]
    fn the_three_knob_functions_do_not_touch_each_other() {
        // Six characters everywhere is the widest the keymap test allows.
        let widest = function_width("WWWWWW");
        let centre_x = (WIDTH - widest) / 2;
        assert!(MARGIN + widest < centre_x);
        assert!(centre_x + widest < WIDTH - MARGIN - widest);
    }
}
