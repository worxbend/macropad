//! What the simulator renders: still pictures of every screen, and the scripted demo.

use macropad_core::engine::Inputs;
use macropad_core::quadrature::Rotation::{Clockwise, CounterClockwise};

use crate::session::{Film, Knob, Session, Shot, BOTH_HELD, IDLE, LEFT_HELD};

const MEDIA: usize = 0;
const EDIT: usize = 1;
const NAV: usize = 2;
const NUM: usize = 3;
const TAB_OR_SHIFT_KEY: usize = 9;

pub struct Still {
    pub file_name: &'static str,
    pub caption: &'static str,
    pub shot: Shot,
}

fn still(file_name: &'static str, caption: &'static str, session: &Session) -> Still {
    Still {
        file_name,
        caption,
        shot: session.shot(),
    }
}

/// Keys of the EDIT layer hit quickly one after another, which fills the typing-rate graph.
fn type_burst(session: &mut Session) {
    for key in [0, 5, 2, 9, 4, 7, 1, 10, 6, 3, 8, 5, 0, 2] {
        session.hold_keys(1 << key, 45);
        session.wait(40 + 25 * (key % 3));
    }
}

/// EDIT layer: TAB/SH is a tap-hold key. Held, it is Shift, so the CURSOR knob selects text.
fn select_with_the_tap_hold_key(session: &mut Session) {
    let shift_held = Inputs {
        keys: 1 << TAB_OR_SHIFT_KEY,
        ..IDLE
    };
    session.run(shift_held, 150);
    session.turn(Knob::Right, CounterClockwise, 4, shift_held);
    session.run(shift_held, 200);
    session.wait(500);
}

/// One picture per screen and state, each produced by driving a real `Pad`.
pub fn stills() -> Vec<Still> {
    let mut splash = Session::new();
    splash.wait(1100);

    let media = Session::settled_on(MEDIA);

    let mut edit_typing = Session::settled_on(EDIT);
    edit_typing.host.caps_lock = true;
    (0..3).for_each(|_| type_burst(&mut edit_typing));
    edit_typing.hold_keys(1 << 3 | 1 << 6, 60);

    let mut nav = Session::settled_on(NAV);
    nav.hold_keys(1 << 1, 40);
    nav.wait(80);

    let mut num = Session::settled_on(NUM);
    num.host.num_lock = true;

    let mut layer_banner = Session::settled_on(MEDIA);
    layer_banner.tap_left_knob();
    layer_banner.wait(300);

    let mut knob_overlay = Session::settled_on(MEDIA);
    knob_overlay.turn(Knob::Left, Clockwise, 5, IDLE);

    let mut system = Session::settled_on(NAV);
    system.run(LEFT_HELD, 400);
    system.turn(Knob::Right, CounterClockwise, 3, LEFT_HELD);

    let mut idle = Session::settled_on(EDIT);
    idle.wait(47_000);

    let mut flash_hold = Session::settled_on(MEDIA);
    flash_hold.run(BOTH_HELD, 620);

    let mut flash = Session::settled_on(MEDIA);
    flash.run(BOTH_HELD, 1100);

    vec![
        still("splash.png", "POWER-ON SPLASH", &splash),
        still("media.png", "MEDIA LAYER", &media),
        still("edit_typing.png", "EDIT: TWO KEYS DOWN, CAPS LOCK", &edit_typing),
        still("nav.png", "NAV: A KEY JUST TAPPED", &nav),
        still("num.png", "NUM LAYER, NUM LOCK ON", &num),
        still("layer_banner.png", "LAYER CHANGE BANNER", &layer_banner),
        still("knob_overlay.png", "KNOB OVERLAY: 5 CLICKS UP", &knob_overlay),
        still("system.png", "SYSTEM: LEFT KNOB HELD", &system),
        still("idle.png", "IDLE AFTER 30 S", &idle),
        still("flash_hold.png", "BOTH KNOBS HELD", &flash_hold),
        still("flash.png", "READY FOR A NEW UF2", &flash),
    ]
}

/// The demo film: power-on, keys, knobs, layers, the system screen, idle, and the flash hold.
pub fn demo() -> Film {
    let mut session = Session::new();
    session.start_recording();
    session.wait(2300);

    session.hold_keys(1 << 1, 130);
    session.wait(450);
    session.hold_keys(1 << 6, 130);
    session.wait(350);
    session.hold_keys(1 << 8 | 1 << 3, 160);
    session.wait(650);

    session.turn(Knob::Left, Clockwise, 6, IDLE);
    session.wait(250);
    session.turn(Knob::Left, CounterClockwise, 2, IDLE);
    session.wait(1150);

    session.tap_left_knob();
    session.wait(1250);
    type_burst(&mut session);
    session.wait(500);
    session.turn(Knob::Right, Clockwise, 4, IDLE);
    session.wait(1150);
    select_with_the_tap_hold_key(&mut session);
    session.host.caps_lock = true;
    session.wait(1200);
    session.host.caps_lock = false;
    session.wait(300);

    session.run(LEFT_HELD, 700);
    session.turn(Knob::Right, CounterClockwise, 5, LEFT_HELD);
    session.turn(Knob::Right, Clockwise, 5, LEFT_HELD);
    session.run(LEFT_HELD, 200);
    session.run(
        Inputs {
            keys: 1 << NUM,
            ..LEFT_HELD
        },
        150,
    );
    session.run(LEFT_HELD, 350);
    session.wait(1800);

    session.skip(30_500);
    session.wait(2500);
    session.hold_keys(1 << 5, 130);
    session.wait(900);

    session.run(BOTH_HELD, 1000);
    session.wait(900);
    session.into_film()
}

#[cfg(test)]
mod tests {
    use super::*;
    use macropad_core::led::Rgb;
    use macropad_core::ui::Screen;

    #[test]
    fn the_stills_have_unique_names_and_every_screen_is_among_them() {
        let stills = stills();
        let mut names: Vec<_> = stills.iter().map(|still| still.file_name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), stills.len());
        for screen in [
            Screen::Splash,
            Screen::Main,
            Screen::System,
            Screen::Idle,
            Screen::Flash,
        ] {
            assert!(stills.iter().any(|still| still.shot.screen == screen), "{screen:?}");
        }
    }

    #[test]
    fn no_two_stills_show_the_same_picture() {
        let stills = stills();
        for (index, still) in stills.iter().enumerate() {
            let same = stills[index + 1..]
                .iter()
                .find(|other| other.shot.display == still.shot.display);
            assert!(same.is_none(), "{} repeats", still.file_name);
        }
    }

    #[test]
    fn the_demo_visits_every_screen_and_ends_dark_in_flash_mode() {
        let frames = demo().frames;
        for screen in [
            Screen::Splash,
            Screen::Main,
            Screen::System,
            Screen::Idle,
            Screen::Flash,
        ] {
            assert!(frames.iter().any(|frame| frame.screen == screen), "{screen:?}");
        }
        let last = frames.last().expect("the demo records frames");
        assert_eq!(last.screen, Screen::Flash);
        assert_eq!(last.leds, [Rgb::BLACK; 8]);
    }

    #[test]
    fn the_demo_shows_the_tap_hold_key_as_shift_and_the_caps_lock_leds() {
        use macropad_core::hid::{key, modifier};
        let film = demo();
        let shift_left = film.host_log.iter().any(|event| {
            let keyboard = event.reports.keyboard;
            keyboard.modifiers == modifier::SHIFT && keyboard.keys[0] == key::LEFT
        });
        assert!(shift_left, "the host log has no Shift+Left");
        let corners_whiter = film.frames.iter().any(|frame| {
            frame.screen == Screen::Main
                && frame.leds[0].r.saturating_sub(frame.leds[1].r) > 40
                && frame.leds[7] == frame.leds[0]
        });
        assert!(corners_whiter, "no frame shows the caps lock corners");
    }

    #[test]
    fn the_demo_is_the_same_every_time() {
        let (first, second) = (demo().frames, demo().frames);
        assert_eq!(first.len(), second.len());
        assert!(first
            .iter()
            .zip(&second)
            .all(|(a, b)| a.display == b.display && a.leds == b.leds));
    }
}
