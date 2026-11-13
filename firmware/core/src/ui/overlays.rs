//! Short-lived pictures on top of the main screen: the layer banner and the knob overlay.

use core::fmt::Write;

use super::Line;
use crate::activity::{KnobTurn, Side, KNOB_OVERLAY_MS};
use crate::font::{big_text_width, GLYPH_HEIGHT};
use crate::framebuffer::{Framebuffer, Rect, HEIGHT, WIDTH};
use crate::keymap::{Layer, LAYER_COUNT};
use crate::pad::View;

/// How long the banner shows after a layer change.
pub(super) const BANNER_MS: u16 = 800;
const BANNER_OPEN_MS: u16 = 90;
const BANNER_CLOSE_MS: u16 = 160;
/// Everything below the status bar: the banner opens from the middle of this area and fills it.
const BELOW_STATUS_BAR: Rect = Rect {
    x: 0,
    y: 12,
    width: WIDTH,
    height: HEIGHT - 12,
};
const BANNER_HEIGHT: usize = BELOW_STATUS_BAR.height;
const BANNER_NAME_Y: usize = 13;
const BANNER_PIPS_Y: usize = 36;
const BANNER_PIP_SIZE: usize = 6;
const BANNER_PIP_PITCH: usize = 12;
const BIG: usize = 2;

const BELOW_KNOB_ROW: Rect = Rect {
    x: 0,
    y: 21,
    width: WIDTH,
    height: HEIGHT - 21,
};
const KNOB_BOX: Rect = Rect {
    x: 16,
    y: 25,
    width: 128,
    height: 40,
};
const KNOB_BOX_PADDING: usize = 8;
const KNOB_LABEL_Y: usize = KNOB_BOX.y + 5;
const POINTER_Y: usize = KNOB_BOX.y + 22;
const POINTER_HEIGHT: usize = 3;
const DIAL_BOTTOM_Y: usize = KNOB_BOX.y + 34;
const DIAL_INSET: usize = 6;
/// The dial has a tick every `TICK_PITCH` pixels and a long one every `LONG_TICK_EVERY` ticks.
/// One knob step moves the dial by one tick.
const TICK_PITCH: i32 = 4;
const LONG_TICK_EVERY: i32 = 4;
const TICK_HEIGHT: usize = 3;
const LONG_TICK_HEIGHT: usize = 6;

pub(super) fn draw(frame: &mut Framebuffer, view: &View) {
    let activity = &view.activity;
    if activity.layer_age_ms < BANNER_MS {
        draw_layer_banner(frame, view.layer(), activity.layer_index, activity.layer_age_ms);
    } else if activity.knob.age_ms < KNOB_OVERLAY_MS {
        draw_knob_overlay(frame, view.layer(), activity.knob);
    }
}

/// A dark band that opens from the middle, shows the new layer's name, and closes again.
fn draw_layer_banner(frame: &mut Framebuffer, layer: &Layer, layer_index: usize, age_ms: u16) {
    let height = banner_height(age_ms);
    let band = Rect {
        y: BELOW_STATUS_BAR.y + (BANNER_HEIGHT - height) / 2,
        height,
        ..BELOW_STATUS_BAR
    };
    // One row of paper above and below keeps the band apart from what it covers.
    frame.clear(Rect {
        y: band.y - 1,
        height: height + 2,
        ..band
    });
    if height == BANNER_HEIGHT {
        let name_x = (WIDTH - big_text_width(layer.name, BIG)) / 2;
        frame.big_text(name_x, band.y + BANNER_NAME_Y, layer.name, BIG);
        draw_banner_pips(frame, band.y + BANNER_PIPS_Y, layer_index);
    }
    frame.invert(band);
}

fn banner_height(age_ms: u16) -> usize {
    let closing_from = BANNER_MS - BANNER_CLOSE_MS;
    let (shown, of) = if age_ms < BANNER_OPEN_MS {
        (age_ms, BANNER_OPEN_MS)
    } else if age_ms > closing_from {
        (BANNER_MS.saturating_sub(age_ms), BANNER_CLOSE_MS)
    } else {
        return BANNER_HEIGHT;
    };
    // Kept even so the band stays centred.
    BANNER_HEIGHT * usize::from(shown) / usize::from(of) / 2 * 2
}

fn draw_banner_pips(frame: &mut Framebuffer, y: usize, active_layer: usize) {
    let row_width = (LAYER_COUNT - 1) * BANNER_PIP_PITCH + BANNER_PIP_SIZE;
    for layer in 0..LAYER_COUNT {
        let pip = Rect {
            x: (WIDTH - row_width) / 2 + layer * BANNER_PIP_PITCH,
            y,
            width: BANNER_PIP_SIZE,
            height: BANNER_PIP_SIZE,
        };
        if layer == active_layer {
            frame.fill(pip);
        } else {
            frame.outline(pip);
        }
    }
}

/// A box with the knob's function, the net steps of this run, and a dial that turns with it.
///
/// The pad cannot know the host's volume or brightness, so it shows what it does know:
/// how far the knob was turned.
fn draw_knob_overlay(frame: &mut Framebuffer, layer: &Layer, turn: KnobTurn) {
    let label = match turn.side {
        Side::Left => layer.left_knob.label,
        Side::Right => layer.right_knob.label,
    };
    let mut steps: Line<6> = Line::new();
    // `Line::write_str` never fails.
    let _ = write!(steps, "{:+}", turn.net_steps);
    // The key legends go: half-covered words around the box would only be noise.
    frame.clear(BELOW_KNOB_ROW);
    frame.outline(KNOB_BOX);
    frame.outline(KNOB_BOX.inset(1));
    frame.big_text(KNOB_BOX.x + KNOB_BOX_PADDING, KNOB_LABEL_Y, label, BIG);
    let steps_right = KNOB_BOX.x + KNOB_BOX.width - KNOB_BOX_PADDING;
    frame.big_text(
        steps_right - big_text_width(steps.as_str(), BIG),
        KNOB_LABEL_Y,
        steps.as_str(),
        BIG,
    );
    draw_pointer(frame);
    draw_dial(frame, turn.net_steps);
}

/// A small triangle that points down at the middle of the dial.
fn draw_pointer(frame: &mut Framebuffer) {
    for row in 0..POINTER_HEIGHT {
        let half_width = POINTER_HEIGHT - 1 - row;
        for x in WIDTH / 2 - half_width..=WIDTH / 2 + half_width {
            frame.ink(x, POINTER_Y + row);
        }
    }
}

/// Ruler ticks that shift left as the knob turns clockwise, like a dial seen through a window.
fn draw_dial(frame: &mut Framebuffer, net_steps: i16) {
    let shift = i32::from(net_steps) * TICK_PITCH;
    for x in KNOB_BOX.x + DIAL_INSET..KNOB_BOX.x + KNOB_BOX.width - DIAL_INSET {
        let dial_x = x as i32 - (WIDTH / 2) as i32 + shift;
        if dial_x.rem_euclid(TICK_PITCH) != 0 {
            continue;
        }
        let is_long = dial_x.rem_euclid(TICK_PITCH * LONG_TICK_EVERY) == 0;
        frame.bar(x, DIAL_BOTTOM_Y, if is_long { LONG_TICK_HEIGHT } else { TICK_HEIGHT });
    }
}

const _: () = assert!(
    KNOB_LABEL_Y + BIG * GLYPH_HEIGHT < POINTER_Y && POINTER_Y + POINTER_HEIGHT < DIAL_BOTTOM_Y - LONG_TICK_HEIGHT + 1,
    "label, pointer and dial must not overlap inside the knob box"
);

#[cfg(test)]
mod tests {
    use super::super::draw as draw_screen;
    use super::super::test_support::*;
    use super::*;
    use crate::engine::Inputs;
    use crate::keymap::LAYERS;
    use crate::quadrature::Rotation;

    const LEFT_CLOCKWISE: Inputs = Inputs {
        left_rotation: Some(Rotation::Clockwise),
        ..IDLE
    };
    const FULL_BAND: Rect = BELOW_STATUS_BAR;

    fn tap_left_knob(pad: &mut crate::pad::Pad) {
        let left = Inputs {
            left_switch: true,
            ..IDLE
        };
        run(pad, left, 20);
    }

    #[test]
    fn a_layer_change_opens_a_dark_banner_that_closes_again() {
        let mut pad = pad_on(0);
        let before = draw_screen(&state_of(&pad));
        tap_left_knob(&mut pad);
        run(&mut pad, IDLE, 300);
        let banner = draw_screen(&state_of(&pad));
        assert!(ink_in(&banner, FULL_BAND) > FULL_BAND.width * FULL_BAND.height / 2);
        assert_eq!(state_of(&pad).view.layer().name, "EDIT");
        run(&mut pad, IDLE, u32::from(BANNER_MS));
        let after = draw_screen(&state_of(&pad));
        assert!(ink_in(&after, FULL_BAND) < FULL_BAND.width * FULL_BAND.height / 2);
        assert!(after != before, "the main screen now shows the new layer");
    }

    #[test]
    fn the_banner_grows_holds_and_shrinks_without_ever_leaving_the_panel() {
        let heights: Vec<usize> = (0..=BANNER_MS).map(banner_height).collect();
        assert_eq!(heights[0], 0);
        assert_eq!(heights[usize::from(BANNER_OPEN_MS)], BANNER_HEIGHT);
        assert_eq!(heights[usize::from(BANNER_MS / 2)], BANNER_HEIGHT);
        assert_eq!(heights[usize::from(BANNER_MS)], 0);
        assert!(heights.iter().all(|height| *height <= BANNER_HEIGHT && height % 2 == 0));
        let opening = &heights[..usize::from(BANNER_OPEN_MS)];
        assert!(opening.windows(2).all(|pair| pair[0] <= pair[1]));
    }

    #[test]
    fn the_banner_marks_the_new_layer_among_its_pips() {
        let mut frame = Framebuffer::default();
        draw_layer_banner(&mut frame, &LAYERS[2], 2, BANNER_MS / 2);
        let pips_y = FULL_BAND.y + BANNER_PIPS_Y + BANNER_PIP_SIZE / 2;
        let row_x = (WIDTH - (3 * BANNER_PIP_PITCH + BANNER_PIP_SIZE)) / 2;
        let centre_is_paper = |layer: usize| !frame.has_ink(row_x + layer * BANNER_PIP_PITCH + 2, pips_y);
        // The band is inverted, so the filled (active) pip is paper-coloured inside.
        assert_eq!([0, 1, 2, 3].map(centre_is_paper), [false, false, true, false]);
    }

    #[test]
    fn a_knob_step_opens_the_overlay_and_it_closes_after_its_time() {
        let mut pad = pad_on(0);
        let calm = draw_screen(&state_of(&pad));
        run(&mut pad, LEFT_CLOCKWISE, 1);
        let open = draw_screen(&state_of(&pad));
        // A point on the box's bottom border, below the last row of key legends.
        let (border_x, border_y) = (KNOB_BOX.x + 5, KNOB_BOX.y + KNOB_BOX.height - 1);
        assert!(open.has_ink(border_x, border_y) && !calm.has_ink(border_x, border_y));
        run(&mut pad, IDLE, u32::from(KNOB_OVERLAY_MS));
        let closed = draw_screen(&state_of(&pad));
        assert_eq!(ink_in(&closed, BELOW_KNOB_ROW), ink_in(&calm, BELOW_KNOB_ROW));
        assert!(!closed.has_ink(border_x, border_y));
    }

    #[test]
    fn the_overlay_leaves_the_status_bar_and_the_knob_row_alone() {
        let mut pad = pad_on(0);
        let calm = draw_screen(&state_of(&pad));
        run(&mut pad, LEFT_CLOCKWISE, 1);
        let open = draw_screen(&state_of(&pad));
        let above = Rect {
            x: 0,
            y: 0,
            width: WIDTH,
            height: BELOW_KNOB_ROW.y,
        };
        assert_eq!(ink_in(&open, above), ink_in(&calm, above));
    }

    #[test]
    fn each_step_moves_the_dial_by_one_tick_and_four_steps_bring_it_back() {
        let dial = |net_steps| {
            let mut frame = Framebuffer::default();
            draw_dial(&mut frame, net_steps);
            frame
        };
        assert!(dial(0) != dial(1));
        assert!(dial(0) == dial(4) && dial(1) == dial(-3));
        let long_tick_top = DIAL_BOTTOM_Y - LONG_TICK_HEIGHT + 1;
        assert!(dial(0).has_ink(WIDTH / 2, long_tick_top));
        assert!(dial(1).has_ink(WIDTH / 2 - TICK_PITCH as usize, long_tick_top));
    }

    #[test]
    fn the_overlay_names_the_knob_that_turned() {
        let overlay = |side| {
            let mut frame = Framebuffer::default();
            let turn = KnobTurn {
                side,
                net_steps: 2,
                age_ms: 0,
            };
            draw_knob_overlay(&mut frame, &LAYERS[0], turn);
            frame
        };
        assert!(overlay(Side::Left) != overlay(Side::Right));
    }
}
