//! Screens that replace the main one: splash, idle, system and flash.

use core::fmt::Write;

use super::{draw_progress, invert_rounded, uptime_clock, Line, UiState};
use crate::engine::BOOTLOADER_HOLD_MS;
use crate::font::{big_text_width, text_width, GLYPH_HEIGHT};
use crate::framebuffer::{Framebuffer, Rect, HEIGHT, WIDTH};
use crate::keymap::LAYER_COUNT;
use crate::led::MAX_LEVEL;
use crate::pad::View;
use crate::reset::ResetCause;

const VERSION: &str = concat!("V", env!("CARGO_PKG_VERSION"));
const MARGIN: usize = 2;
const BIG: usize = 2;
const HUGE: usize = 3;
const PROGRESS: Rect = Rect {
    x: 20,
    y: 52,
    width: 120,
    height: 8,
};

const SPLASH_TITLE: &str = "MACROPAD";
const SPLASH_TITLE_Y: usize = 9;
const SPLASH_SUBTITLE_Y: usize = 33;
/// Shown from the first frame on, so a reboot loop shorter than the splash still shows it.
const SPLASH_RESET_Y: usize = 42;
/// The title is uncovered from left to right over this time.
const SPLASH_REVEAL_MS: u64 = 700;

const IDLE_CLOCK_GAP: usize = 4;
/// Clear space kept around the idle text. Also its smallest distance from the panel edge.
const IDLE_BLOCK_PADDING: usize = 2;
const STAR_COUNT: u64 = 24;
const STAR_STEP_MS: u64 = 50;
/// Steps a star flies before it starts again from the middle.
const STAR_LIFE_STEPS: u64 = 60;
/// The idle block moves one pixel per this many milliseconds, on each axis.
const IDLE_MS_PER_PIXEL_X: u64 = 110;
const IDLE_MS_PER_PIXEL_Y: u64 = 170;

const SYSTEM_RULE_Y: usize = 10;
const SYSTEM_LAYERS_Y: usize = 12;
const SYSTEM_LAYER_CELL: usize = WIDTH / LAYER_COUNT;
const SYSTEM_LAYERS_HINT_Y: usize = 23;
const SYSTEM_LIGHT_Y: usize = 35;
const SYSTEM_LIGHT_BAR_X: usize = 40;
const SYSTEM_LIGHT_SEGMENT: usize = 12;
const SYSTEM_LIGHT_PITCH: usize = 14;
const SYSTEM_LIGHT_HINT_Y: usize = 46;
const SYSTEM_FLASH_HINT_Y: usize = 58;

const FLASH_TITLE_Y: usize = 5;
const FLASH_LINE_1_Y: usize = 26;
const FLASH_LINE_2_Y: usize = 37;

fn centred(frame: &mut Framebuffer, y: usize, text: &str) {
    frame.text(WIDTH.saturating_sub(text_width(text)) / 2, y, text);
}

fn centred_big(frame: &mut Framebuffer, y: usize, text: &str, scale: usize) {
    let x = WIDTH.saturating_sub(big_text_width(text, scale)) / 2;
    frame.big_text(x, y, text, scale);
}

/// Dark tab with a light title in the top-left corner, standing on a rule, as on the main screen.
pub(super) fn draw_title_tab(frame: &mut Framebuffer, title: &str) {
    frame.text(3, 1, title);
    frame.invert(Rect {
        x: 0,
        y: 0,
        width: text_width(title) + 6,
        height: SYSTEM_RULE_Y,
    });
    frame.horizontal_line(SYSTEM_RULE_Y);
}

pub(super) fn draw_splash(frame: &mut Framebuffer, uptime_ms: u64, reset_cause: ResetCause) {
    centred_big(frame, SPLASH_TITLE_Y, SPLASH_TITLE, HUGE);
    let revealed = (WIDTH as u64 * uptime_ms / SPLASH_REVEAL_MS) as usize;
    frame.clear(Rect {
        x: revealed.min(WIDTH),
        y: 0,
        width: WIDTH,
        height: SPLASH_SUBTITLE_Y,
    });
    if uptime_ms >= SPLASH_REVEAL_MS {
        let mut subtitle: Line<24> = Line::new();
        // `Line::write_str` never fails.
        let _ = write!(subtitle, "FIRMWARE {VERSION}");
        centred(frame, SPLASH_SUBTITLE_Y, subtitle.as_str());
    }
    let mut reset: Line<24> = Line::new();
    let _ = write!(reset, "RESET: {}", reset_cause.label());
    centred(frame, SPLASH_RESET_Y, reset.as_str());
    draw_progress(frame, PROGRESS, uptime_ms, super::SPLASH_MS);
}

/// The layer name and the uptime, drifting slowly around the panel so no pixel stays dark for
/// hours. The block's own area is wiped first, so the stars behind never touch the text.
pub(super) fn draw_idle(frame: &mut Framebuffer, state: &UiState) {
    let view = &state.view;
    let name = view.layer().name;
    let clock = uptime_clock(view.activity.uptime_ms);
    let second_line = if state.host.asleep {
        "HOST ASLEEP"
    } else {
        clock.as_str()
    };
    let block = idle_block(view.activity.uptime_ms, name, second_line);
    frame.clear(block);
    let (x, y) = (block.x + IDLE_BLOCK_PADDING, block.y + IDLE_BLOCK_PADDING);
    frame.big_text(x, y, name, BIG);
    frame.text(x, y + BIG * GLYPH_HEIGHT + IDLE_CLOCK_GAP, second_line);
}

/// Where the idle text and the clear space around it are at `uptime_ms`.
fn idle_block(uptime_ms: u64, name: &str, second_line: &str) -> Rect {
    let width = big_text_width(name, BIG).max(text_width(second_line)) + 2 * IDLE_BLOCK_PADDING;
    let height = BIG * GLYPH_HEIGHT + IDLE_CLOCK_GAP + GLYPH_HEIGHT + 2 * IDLE_BLOCK_PADDING;
    Rect {
        x: bounce(uptime_ms / IDLE_MS_PER_PIXEL_X, WIDTH - width),
        y: bounce(uptime_ms / IDLE_MS_PER_PIXEL_Y, HEIGHT - height),
        width,
        height,
    }
}

/// Stars that fly outward from the middle of the panel and speed up on the way, behind the
/// idle text. Each star takes a new direction every time it starts again.
pub(super) fn draw_stars(frame: &mut Framebuffer, uptime_ms: u64) {
    let step = uptime_ms / STAR_STEP_MS;
    for star in 0..STAR_COUNT {
        let staggered = step + star * STAR_LIFE_STEPS / STAR_COUNT;
        let (flight, age) = (staggered / STAR_LIFE_STEPS, (staggered % STAR_LIFE_STEPS) as i64);
        let (reach_x, reach_y) = star_direction(star, flight);
        let life = STAR_LIFE_STEPS as i64;
        // Half steady, half speeding up: 0 at the start of a flight, `2 * life * life` at its end.
        let travelled = age * life + age * age;
        let x = WIDTH as i64 / 2 + reach_x * travelled / (2 * life * life);
        let y = HEIGHT as i64 / 2 + reach_y * travelled / (2 * life * life);
        if x >= 0 && y >= 0 {
            // `ink` clips on the right and at the bottom.
            frame.ink(x as usize, y as usize);
        }
    }
}

/// Where a star would be at the end of its flight, relative to the middle: anywhere up to one
/// panel width and height away, so most stars leave through an edge.
fn star_direction(star: u64, flight: u64) -> (i64, i64) {
    let scrambled = (star.wrapping_mul(0x9E37_79B9) ^ flight.wrapping_mul(0x85EB_CA6B)).wrapping_mul(0xC2B2_AE35);
    let within = |bits: u64, span: usize| (bits % (2 * span as u64 + 1)) as i64 - span as i64;
    (within(scrambled >> 8, WIDTH), within(scrambled >> 24, HEIGHT))
}

/// A position that walks 0..=`span` and back again as `step` grows.
fn bounce(step: u64, span: usize) -> usize {
    if span == 0 {
        return 0;
    }
    let span = span as u64;
    let phase = step % (2 * span);
    (if phase <= span { phase } else { 2 * span - phase }) as usize
}

/// What the pad itself can do while the left knob is held: pick a layer, set the LED brightness.
pub(super) fn draw_system(frame: &mut Framebuffer, view: &View) {
    draw_title_tab(frame, "SYSTEM");
    frame.text(WIDTH - MARGIN - text_width(VERSION), 1, VERSION);
    for (index, layer) in view.layers.iter().enumerate() {
        let cell_x = index * SYSTEM_LAYER_CELL;
        let name_x = cell_x + (SYSTEM_LAYER_CELL - text_width(layer.name)) / 2;
        frame.text(name_x, SYSTEM_LAYERS_Y + 1, layer.name);
        if index == view.activity.layer_index {
            invert_rounded(
                frame,
                Rect {
                    x: cell_x + 1,
                    y: SYSTEM_LAYERS_Y,
                    width: SYSTEM_LAYER_CELL - 2,
                    height: GLYPH_HEIGHT + 2,
                },
            );
        }
    }
    centred(frame, SYSTEM_LAYERS_HINT_Y, "TOP ROW KEYS PICK A LAYER");
    frame.text(MARGIN, SYSTEM_LIGHT_Y, "LIGHT");
    draw_light_bar(frame, view.led_level);
    centred(frame, SYSTEM_LIGHT_HINT_Y, "RIGHT KNOB SETS THE LIGHT");
    centred(frame, SYSTEM_FLASH_HINT_Y, "HOLD BOTH KNOBS: FLASH");
}

/// One segment per brightness level: filled up to the current one, outlined above it.
fn draw_light_bar(frame: &mut Framebuffer, level: u8) {
    for segment in 0..usize::from(MAX_LEVEL) {
        let area = Rect {
            x: SYSTEM_LIGHT_BAR_X + segment * SYSTEM_LIGHT_PITCH,
            y: SYSTEM_LIGHT_Y,
            width: SYSTEM_LIGHT_SEGMENT,
            height: GLYPH_HEIGHT,
        };
        if segment < usize::from(level) {
            frame.fill(area);
        } else {
            frame.outline(area);
        }
    }
}

/// Progress of the two-knob hold, then what to do once the pad is a USB drive.
/// The panel keeps its picture without being driven, so this stays readable in the bootloader.
pub(super) fn draw_flash(frame: &mut Framebuffer, view: &View) {
    centred_big(frame, FLASH_TITLE_Y, "FLASH MODE", BIG);
    if view.flash_requested {
        centred(frame, FLASH_LINE_1_Y, "COPY MACROPAD.UF2");
        centred(frame, FLASH_LINE_2_Y, "TO THE RP2350 DRIVE");
        frame.fill(PROGRESS);
    } else {
        centred(frame, FLASH_LINE_1_Y, "KEEP HOLDING BOTH KNOBS");
        centred(frame, FLASH_LINE_2_Y, "LET GO TO CANCEL");
        draw_progress(frame, PROGRESS, view.flash_hold_ms.into(), BOOTLOADER_HOLD_MS.into());
    }
}

const _: () = assert!(
    SPLASH_TITLE_Y + HUGE * GLYPH_HEIGHT < SPLASH_SUBTITLE_Y,
    "the splash title must end above its subtitle"
);
const _: () = assert!(
    SPLASH_SUBTITLE_Y + GLYPH_HEIGHT < SPLASH_RESET_Y && SPLASH_RESET_Y + GLYPH_HEIGHT < PROGRESS.y,
    "the reset cause must sit between the subtitle and the progress bar"
);
const _: () = assert!(
    SYSTEM_LIGHT_BAR_X + MAX_LEVEL as usize * SYSTEM_LIGHT_PITCH <= WIDTH,
    "the brightness bar must fit the panel"
);

#[cfg(test)]
mod tests {
    use super::super::test_support::*;
    use super::super::{draw, Screen, SPLASH_MS};
    use super::*;
    use crate::engine::Inputs;
    use crate::keymap::LAYERS;
    use crate::pad::{Host, Pad};
    use crate::quadrature::Rotation;

    const LEFT_HELD: Inputs = Inputs {
        left_switch: true,
        ..IDLE
    };

    fn splash_at(uptime_ms: u64) -> Framebuffer {
        let mut frame = Framebuffer::default();
        draw_splash(&mut frame, uptime_ms, ResetCause::PowerOn);
        frame
    }

    fn progress_fill(frame: &Framebuffer) -> usize {
        let inside = PROGRESS.inset(2);
        (inside.x..inside.x + inside.width)
            .filter(|&x| frame.has_ink(x, inside.y))
            .count()
    }

    fn everything() -> Rect {
        Rect {
            x: 0,
            y: 0,
            width: WIDTH,
            height: HEIGHT,
        }
    }

    #[test]
    fn the_splash_title_is_uncovered_from_the_left() {
        let title = Rect {
            x: 0,
            y: SPLASH_TITLE_Y,
            width: WIDTH,
            height: HUGE * GLYPH_HEIGHT,
        };
        let right_half = Rect {
            x: WIDTH / 2,
            width: WIDTH / 2,
            ..title
        };
        let half_way = splash_at(SPLASH_REVEAL_MS / 2);
        assert!(ink_in(&half_way, title) > 0);
        assert_eq!(ink_in(&half_way, right_half), 0);
        assert!(ink_in(&splash_at(SPLASH_REVEAL_MS), right_half) > 0);
    }

    #[test]
    fn the_splash_shows_the_reset_cause_from_the_first_frame() {
        let reset_line = Rect {
            x: 0,
            y: SPLASH_RESET_Y,
            width: WIDTH,
            height: GLYPH_HEIGHT,
        };
        let draw_at_start = |cause| {
            let mut frame = Framebuffer::default();
            draw_splash(&mut frame, 0, cause);
            frame
        };
        let power_on = draw_at_start(ResetCause::PowerOn);
        let watchdog = draw_at_start(ResetCause::Watchdog);
        assert!(ink_in(&power_on, reset_line) > 0);
        assert!(power_on != watchdog);
    }

    #[test]
    fn every_reset_cause_fits_the_splash_line() {
        let causes = [
            ResetCause::PowerOn,
            ResetCause::ResetPin,
            ResetCause::Debugger,
            ResetCause::Watchdog,
            ResetCause::Restart,
            ResetCause::Unknown,
        ];
        for cause in causes {
            let line = text_width("RESET: ") + text_width(cause.label());
            assert!(line + 2 * MARGIN <= WIDTH, "{cause:?}");
        }
    }

    #[test]
    fn the_splash_progress_bar_is_full_exactly_when_the_splash_ends() {
        assert_eq!(progress_fill(&splash_at(0)), 0);
        assert!(progress_fill(&splash_at(SPLASH_MS / 2)) > 0);
        assert_eq!(progress_fill(&splash_at(SPLASH_MS)), PROGRESS.inset(2).width);
    }

    #[test]
    fn the_title_fits_the_panel_with_room_on_both_sides() {
        assert!(big_text_width(SPLASH_TITLE, HUGE) < WIDTH - 2 * MARGIN);
    }

    #[test]
    fn bounce_walks_there_and_back() {
        let walked: Vec<usize> = (0..8).map(|step| bounce(step, 3)).collect();
        assert_eq!(walked, [0, 1, 2, 3, 2, 1, 0, 1]);
        assert_eq!(bounce(5, 0), 0);
    }

    #[test]
    fn the_idle_block_moves_and_always_stays_whole() {
        let mut state = settled(0);
        state.host.asleep = true;
        let ink_at = |uptime_ms| {
            let mut state = state;
            state.view.activity.uptime_ms = uptime_ms;
            let mut frame = Framebuffer::default();
            draw_idle(&mut frame, &state);
            (ink_in(&frame, everything()), frame)
        };
        let (ink, first) = ink_at(0);
        for uptime_ms in (0..120_000).step_by(1_370) {
            assert_eq!(ink_at(uptime_ms).0, ink, "clipped at {uptime_ms} ms");
        }
        assert!(ink_at(5_000).1 != first);
    }

    #[test]
    fn the_stars_move_and_are_at_most_one_pixel_each() {
        let sky_at = |uptime_ms| {
            let mut frame = Framebuffer::default();
            draw_stars(&mut frame, uptime_ms);
            frame
        };
        for uptime_ms in (0..60_000).step_by(977) {
            let ink = ink_in(&sky_at(uptime_ms), everything());
            assert!(ink > 0 && ink <= STAR_COUNT as usize, "{ink} at {uptime_ms} ms");
        }
        assert!(sky_at(40_000) != sky_at(40_000 + 4 * STAR_STEP_MS));
        assert!(sky_at(40_000) == sky_at(40_000 + STAR_STEP_MS - 1));
    }

    #[test]
    fn a_star_takes_a_new_direction_on_every_flight_and_stays_within_reach() {
        let directions: Vec<_> = (0..50).map(|flight| star_direction(3, flight)).collect();
        assert!(directions.iter().any(|direction| *direction != directions[0]));
        for (reach_x, reach_y) in directions {
            assert!(reach_x.unsigned_abs() <= WIDTH as u64 && reach_y.unsigned_abs() <= HEIGHT as u64);
        }
    }

    #[test]
    fn the_stars_never_touch_the_idle_text() {
        let mut state = settled(1);
        for uptime_ms in (0..90_000).step_by(1_130) {
            state.view.activity.uptime_ms = uptime_ms;
            let (mut with_stars, mut text_only) = (Framebuffer::default(), Framebuffer::default());
            draw_stars(&mut with_stars, uptime_ms);
            draw_idle(&mut with_stars, &state);
            draw_idle(&mut text_only, &state);
            let clock = uptime_clock(uptime_ms);
            let block = idle_block(uptime_ms, state.view.layer().name, clock.as_str());
            assert_eq!(ink_in(&with_stars, block), ink_in(&text_only, block), "{uptime_ms} ms");
        }
    }

    #[test]
    fn the_idle_screen_shows_the_uptime_unless_the_host_sleeps() {
        let awake = settled(0);
        let asleep = UiState {
            host: Host {
                asleep: true,
                ..Host::default()
            },
            ..awake
        };
        let (mut clock, mut sleeping) = (Framebuffer::default(), Framebuffer::default());
        draw_idle(&mut clock, &awake);
        draw_idle(&mut sleeping, &asleep);
        assert!(clock != sleeping);
    }

    #[test]
    fn the_system_screen_marks_the_active_layer() {
        let cell = |index: usize| Rect {
            x: index * SYSTEM_LAYER_CELL,
            y: SYSTEM_LAYERS_Y,
            width: SYSTEM_LAYER_CELL,
            height: GLYPH_HEIGHT + 2,
        };
        let mut pad = pad_on(2);
        run(&mut pad, LEFT_HELD, 400);
        assert_eq!(super::super::screen_for(&state_of(&pad)), Screen::System);
        let frame = draw(&state_of(&pad));
        let half = SYSTEM_LAYER_CELL * (GLYPH_HEIGHT + 2) / 2;
        assert!(ink_in(&frame, cell(2)) > half);
        assert!([0, 1, 3].iter().all(|&other| ink_in(&frame, cell(other)) < half));
    }

    #[test]
    fn the_light_bar_follows_the_brightness_level() {
        let filled_segments = |pad: &Pad| {
            let frame = draw(&state_of(pad));
            (0..usize::from(MAX_LEVEL))
                .filter(|segment| {
                    frame.has_ink(
                        SYSTEM_LIGHT_BAR_X + segment * SYSTEM_LIGHT_PITCH + 3,
                        SYSTEM_LIGHT_Y + 3,
                    )
                })
                .count()
        };
        let mut pad = Pad::new(&LAYERS);
        run(&mut pad, IDLE, SETTLE_MS);
        run(&mut pad, LEFT_HELD, 400);
        assert_eq!(filled_segments(&pad), usize::from(MAX_LEVEL));
        let dimmer = Inputs {
            right_rotation: Some(Rotation::CounterClockwise),
            ..LEFT_HELD
        };
        (0..3).for_each(|_| run(&mut pad, dimmer, 1));
        assert_eq!(filled_segments(&pad), usize::from(MAX_LEVEL) - 3);
    }

    #[test]
    fn the_flash_bar_fills_with_the_hold_and_is_solid_once_requested() {
        let mut view = settled(0).view;
        let flash = |view: &View| {
            let mut frame = Framebuffer::default();
            draw_flash(&mut frame, view);
            frame
        };
        view.flash_hold_ms = BOOTLOADER_HOLD_MS / 2;
        assert_eq!(progress_fill(&flash(&view)), PROGRESS.inset(2).width / 2);
        view.flash_requested = true;
        let requested = flash(&view);
        assert_eq!(ink_in(&requested, PROGRESS), PROGRESS.width * PROGRESS.height);
    }

    #[test]
    fn no_screen_text_is_wider_than_the_panel() {
        let lines = [
            "TOP ROW KEYS PICK A LAYER",
            "RIGHT KNOB SETS THE LIGHT",
            "HOLD BOTH KNOBS: FLASH",
            "KEEP HOLDING BOTH KNOBS",
            "TO THE RP2350 DRIVE",
        ];
        assert!(lines.iter().all(|line| text_width(line) <= WIDTH - 2 * MARGIN));
        assert!(big_text_width("FLASH MODE", BIG) <= WIDTH - 2 * MARGIN);
    }
}
