//! The display. `draw` picks one screen for the moment and renders it.
//!
//! | Screen | Shown |
//! | --- | --- |
//! | flash | while both knobs are held, and after the bootloader was requested |
//! | splash | for `SPLASH_MS` after power-on |
//! | system | while the left knob is held on its own |
//! | idle | after `IDLE_AFTER_MS` without input, or while the host sleeps |
//! | main | otherwise, with the layer banner or the knob overlay on top when one is due |

mod main_screen;
mod overlays;
mod screens;

use core::fmt::{self, Write};

use crate::activity::IDLE_AFTER_MS;
use crate::framebuffer::{Framebuffer, Rect};
use crate::pad::{Host, View};

/// Longest label, and longest layer name, that fits its place on the screen.
pub const MAX_LABEL_CHARS: usize = 6;
pub const SPLASH_MS: u64 = 1600;
/// The left knob must be held this long before the system screen replaces the main one,
/// so a quick "next layer" tap does not flash it.
pub const SYSTEM_SCREEN_AFTER_MS: u16 = 250;
/// Likewise for the two-knob hold and the flash screen.
pub const FLASH_SCREEN_AFTER_MS: u16 = 150;

/// Everything the screen shows.
#[derive(Clone, Copy)]
pub struct UiState {
    pub view: View,
    pub host: Host,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Screen {
    Flash,
    Splash,
    System,
    Idle,
    Main,
}

pub fn screen_for(state: &UiState) -> Screen {
    let view = &state.view;
    if view.flash_requested || view.flash_hold_ms >= FLASH_SCREEN_AFTER_MS {
        Screen::Flash
    } else if view.activity.uptime_ms < SPLASH_MS {
        Screen::Splash
    } else if view.activity.left_hold_ms >= SYSTEM_SCREEN_AFTER_MS {
        Screen::System
    } else if state.host.asleep || view.activity.idle_ms >= IDLE_AFTER_MS {
        Screen::Idle
    } else {
        Screen::Main
    }
}

pub fn draw(state: &UiState) -> Framebuffer {
    let mut frame = Framebuffer::default();
    match screen_for(state) {
        Screen::Flash => screens::draw_flash(&mut frame, &state.view),
        Screen::Splash => screens::draw_splash(&mut frame, state.view.activity.uptime_ms),
        Screen::System => screens::draw_system(&mut frame, &state.view),
        Screen::Idle => {
            screens::draw_stars(&mut frame, state.view.activity.uptime_ms);
            screens::draw_idle(&mut frame, state);
        }
        Screen::Main => {
            main_screen::draw(&mut frame, state);
            overlays::draw(&mut frame, &state.view);
        }
    }
    frame
}

/// Flips a box and leaves its four corner pixels alone, which reads as rounded corners.
fn invert_rounded(frame: &mut Framebuffer, area: Rect) {
    frame.invert(area);
    for corner in corners(area) {
        frame.invert(corner);
    }
}

/// A one-pixel border with the four corner pixels left out.
fn outline_rounded(frame: &mut Framebuffer, area: Rect) {
    frame.outline(area);
    for corner in corners(area) {
        frame.clear(corner);
    }
}

fn corners(area: Rect) -> [Rect; 4] {
    let (right, bottom) = (area.x + area.width - 1, area.y + area.height - 1);
    [(area.x, area.y), (right, area.y), (area.x, bottom), (right, bottom)].map(|(x, y)| Rect {
        x,
        y,
        width: 1,
        height: 1,
    })
}

/// A progress bar: a border with `part`/`whole` of its inside filled.
fn draw_progress(frame: &mut Framebuffer, area: Rect, part: u64, whole: u64) {
    frame.outline(area);
    let inside = area.inset(2);
    let filled = (inside.width as u64 * part.min(whole) / whole) as usize;
    frame.fill(Rect {
        width: filled,
        ..inside
    });
}

/// Text built at run time without a heap. Output that does not fit is cut off.
struct Line<const N: usize> {
    bytes: [u8; N],
    len: usize,
}

impl<const N: usize> Line<N> {
    fn new() -> Self {
        Self { bytes: [0; N], len: 0 }
    }

    fn as_str(&self) -> &str {
        // Only whole ASCII bytes are stored, so this cannot fail; an empty line is the safe fallback.
        core::str::from_utf8(&self.bytes[..self.len]).unwrap_or("")
    }
}

impl<const N: usize> Write for Line<N> {
    fn write_str(&mut self, text: &str) -> fmt::Result {
        for byte in text.bytes().filter(u8::is_ascii).take(N - self.len) {
            self.bytes[self.len] = byte;
            self.len += 1;
        }
        Ok(())
    }
}

/// `HH:MM:SS`, with the hours running past 99 if the pad stays on that long.
fn uptime_clock(uptime_ms: u64) -> Line<12> {
    let seconds = uptime_ms / 1000;
    let mut clock = Line::new();
    // `Line::write_str` never fails.
    let _ = write!(
        clock,
        "{:02}:{:02}:{:02}",
        seconds / 3600,
        seconds / 60 % 60,
        seconds % 60
    );
    clock
}

#[cfg(test)]
pub(crate) mod test_support {
    use super::*;
    use crate::engine::Inputs;
    use crate::keymap::LAYERS;
    use crate::pad::Pad;

    pub const IDLE: Inputs = Inputs {
        keys: 0,
        left_switch: false,
        right_switch: false,
        left_rotation: None,
        right_rotation: None,
    };
    /// Long enough for the splash, the layer banner and the knob overlay to be over.
    pub const SETTLE_MS: u32 = 2000;

    pub fn run(pad: &mut Pad, inputs: Inputs, ms: u32) {
        (0..ms).for_each(|_| {
            pad.tick(&inputs);
        });
    }

    /// A pad that was switched on, moved to `layer_index` and then left alone for two seconds.
    pub fn pad_on(layer_index: usize) -> Pad {
        let mut pad = Pad::new(&LAYERS);
        let left_held = Inputs {
            left_switch: true,
            ..IDLE
        };
        run(&mut pad, left_held, 1);
        run(
            &mut pad,
            Inputs {
                keys: 1 << layer_index,
                ..left_held
            },
            1,
        );
        run(&mut pad, IDLE, SETTLE_MS);
        pad
    }

    pub fn state_of(pad: &Pad) -> UiState {
        UiState {
            view: pad.view(),
            host: Host::default(),
        }
    }

    pub fn settled(layer_index: usize) -> UiState {
        state_of(&pad_on(layer_index))
    }

    pub fn ink_in(frame: &Framebuffer, area: Rect) -> usize {
        let xs = area.x..area.x + area.width;
        (area.y..area.y + area.height)
            .flat_map(|y| xs.clone().map(move |x| (x, y)))
            .filter(|&(x, y)| frame.has_ink(x, y))
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::test_support::*;
    use super::*;
    use crate::engine::{Inputs, BOOTLOADER_HOLD_MS};
    use crate::keymap::LAYERS;
    use crate::pad::Pad;

    const LEFT_HELD: Inputs = Inputs {
        left_switch: true,
        ..IDLE
    };
    const BOTH_HELD: Inputs = Inputs {
        right_switch: true,
        ..LEFT_HELD
    };

    #[test]
    fn the_splash_shows_first_and_then_gives_way_to_the_main_screen() {
        let mut pad = Pad::new(&LAYERS);
        run(&mut pad, IDLE, SPLASH_MS as u32 - 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Splash);
        run(&mut pad, IDLE, 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Main);
    }

    #[test]
    fn a_quick_left_knob_tap_never_shows_the_system_screen() {
        let mut pad = pad_on(0);
        run(&mut pad, LEFT_HELD, u32::from(SYSTEM_SCREEN_AFTER_MS) - 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Main);
        run(&mut pad, LEFT_HELD, 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::System);
        run(&mut pad, IDLE, 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Main);
    }

    #[test]
    fn the_idle_screen_comes_after_the_idle_time_and_leaves_on_any_input() {
        let mut pad = pad_on(0);
        run(&mut pad, IDLE, IDLE_AFTER_MS - SETTLE_MS - 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Main);
        run(&mut pad, IDLE, 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Idle);
        run(&mut pad, Inputs { keys: 1, ..IDLE }, 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Main);
    }

    #[test]
    fn a_sleeping_host_shows_the_idle_screen_at_once() {
        let asleep = UiState {
            host: Host {
                asleep: true,
                ..Host::default()
            },
            ..settled(0)
        };
        assert_eq!(screen_for(&asleep), Screen::Idle);
    }

    #[test]
    fn the_flash_screen_follows_the_two_knob_hold_and_stays_once_requested() {
        let mut pad = pad_on(0);
        run(&mut pad, BOTH_HELD, u32::from(FLASH_SCREEN_AFTER_MS) - 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Main);
        run(&mut pad, BOTH_HELD, 1);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Flash);
        run(&mut pad, BOTH_HELD, u32::from(BOOTLOADER_HOLD_MS));
        run(&mut pad, IDLE, 50);
        assert_eq!(screen_for(&state_of(&pad)), Screen::Flash);
    }

    #[test]
    fn every_screen_draws_something() {
        let mut pad = Pad::new(&LAYERS);
        run(&mut pad, IDLE, 800);
        let splash = draw(&state_of(&pad));
        run(&mut pad, IDLE, 1200);
        let main = draw(&state_of(&pad));
        run(&mut pad, LEFT_HELD, 400);
        let system = draw(&state_of(&pad));
        run(&mut pad, BOTH_HELD, 400);
        let flash = draw(&state_of(&pad));
        let blank = Framebuffer::default();
        assert!([&splash, &main, &system, &flash].iter().all(|frame| **frame != blank));
        assert!(splash != main && main != system && system != flash);
    }

    #[test]
    fn a_progress_bar_fills_in_proportion_and_never_overflows() {
        let area = Rect {
            x: 10,
            y: 10,
            width: 104,
            height: 7,
        };
        let filled_columns = |part| {
            let mut frame = Framebuffer::default();
            draw_progress(&mut frame, area, part, 100);
            (12..112).filter(|&x| frame.has_ink(x, 13)).count()
        };
        assert_eq!(filled_columns(0), 0);
        assert_eq!(filled_columns(50), 50);
        assert_eq!(filled_columns(100), 100);
        assert_eq!(filled_columns(900), 100);
    }

    #[test]
    fn the_uptime_clock_counts_hours_minutes_and_seconds() {
        assert_eq!(uptime_clock(0).as_str(), "00:00:00");
        assert_eq!(uptime_clock(3_723_999).as_str(), "01:02:03");
        assert_eq!(uptime_clock(360_000_000).as_str(), "100:00:00");
    }

    #[test]
    fn a_line_cuts_off_what_does_not_fit() {
        let mut line: Line<4> = Line::new();
        let _ = write!(line, "{}", 1_234_567);
        assert_eq!(line.as_str(), "1234");
    }
}
