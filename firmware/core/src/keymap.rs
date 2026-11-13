//! The keymap: edit the four layers below to change what the pad does. `KEYMAP.md` in the
//! firmware directory walks through it.
//!
//! Key order is row-major as seen from the front: index 0 is top-left, 11 is bottom-right.
//! Labels and layer names are drawn on the display; six characters fit. The tests at the end
//! of this file catch a keymap the pad could not show or send.

use crate::hid::{consumer, key, modifier, Stroke};
use crate::led::{Effect, Rgb};

pub const KEY_COUNT: usize = 12;
pub const LAYER_COUNT: usize = 4;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    None,
    Stroke(Stroke),
    Consumer(u16),
    /// Strokes typed one after another.
    Macro(&'static [Stroke]),
    /// Keys only: `tap` when let go within `engine::TAP_HOLD_MS`, `hold` when kept down longer
    /// or when another key or a knob is used meanwhile. `hold` may be modifiers alone.
    TapHold {
        tap: Stroke,
        hold: Stroke,
    },
}

#[derive(Clone, Copy)]
pub struct Binding {
    pub label: &'static str,
    pub action: Action,
}

#[derive(Clone, Copy)]
pub struct KnobBinding {
    pub label: &'static str,
    pub counter_clockwise: Action,
    pub clockwise: Action,
}

pub struct Layer {
    pub name: &'static str,
    pub color: Rgb,
    pub effect: Effect,
    pub keys: [Binding; KEY_COUNT],
    pub left_knob: KnobBinding,
    pub right_knob: KnobBinding,
    /// The left knob's press always switches layer, so only the right press is bindable.
    pub right_knob_press: Binding,
}

const fn tap(label: &'static str, key: u8) -> Binding {
    Binding {
        label,
        action: Action::Stroke(Stroke::plain(key)),
    }
}

const fn ctrl(label: &'static str, key: u8) -> Binding {
    chord(label, modifier::CTRL, key)
}

/// A key with any mix of modifiers, for example `chord("REOPEN", modifier::CTRL | modifier::SHIFT, key::T)`.
const fn chord(label: &'static str, modifiers: u8, key: u8) -> Binding {
    Binding {
        label,
        action: Action::Stroke(Stroke::with(modifiers, key)),
    }
}

/// One key when tapped, another (or just modifiers) while held. The tap is sent on release.
/// Example: `tap_hold("TAB/SH", Stroke::plain(key::TAB), Stroke::modifiers(modifier::SHIFT))`.
const fn tap_hold(label: &'static str, tap: Stroke, hold: Stroke) -> Binding {
    Binding {
        label,
        action: Action::TapHold { tap, hold },
    }
}

/// Strokes typed one after another on a single press. At most `TAP_QUEUE_CAPACITY` of them.
const fn sequence(label: &'static str, strokes: &'static [Stroke]) -> Binding {
    Binding {
        label,
        action: Action::Macro(strokes),
    }
}

const fn media(label: &'static str, usage: u16) -> Binding {
    Binding {
        label,
        action: Action::Consumer(usage),
    }
}

const fn knob(label: &'static str, counter_clockwise: Action, clockwise: Action) -> KnobBinding {
    KnobBinding {
        label,
        counter_clockwise,
        clockwise,
    }
}

const fn strokes(counter_clockwise: Stroke, clockwise: Stroke) -> (Action, Action) {
    (Action::Stroke(counter_clockwise), Action::Stroke(clockwise))
}

const VOLUME: KnobBinding = knob(
    "VOL",
    Action::Consumer(consumer::VOLUME_DOWN),
    Action::Consumer(consumer::VOLUME_UP),
);

const SELECT_LINE: [Stroke; 2] = [Stroke::plain(key::HOME), Stroke::with(modifier::SHIFT, key::END)];
const PREVIOUS_TAB: Stroke = Stroke::with(modifier::CTRL | modifier::SHIFT, key::TAB);
const NEXT_TAB: Stroke = Stroke::with(modifier::CTRL, key::TAB);

const MEDIA: Layer = Layer {
    name: "MEDIA",
    color: Rgb::new(120, 40, 255),
    effect: Effect::Breathing,
    keys: [
        media("PREV", consumer::PREVIOUS_TRACK),
        media("PLAY", consumer::PLAY_PAUSE),
        media("NEXT", consumer::NEXT_TRACK),
        media("STOP", consumer::STOP),
        tap("F13", key::F13),
        tap("F14", key::F14),
        tap("F15", key::F15),
        tap("F16", key::F16),
        tap("F17", key::F17),
        tap("F18", key::F18),
        tap("F19", key::F19),
        tap("F20", key::F20),
    ],
    left_knob: VOLUME,
    right_knob: knob(
        "BRIGHT",
        Action::Consumer(consumer::BRIGHTNESS_DOWN),
        Action::Consumer(consumer::BRIGHTNESS_UP),
    ),
    right_knob_press: media("MUTE", consumer::MUTE),
};

const EDIT: Layer = {
    let (undo, redo) = strokes(
        Stroke::with(modifier::CTRL, key::Z),
        Stroke::with(modifier::CTRL, key::Y),
    );
    let (left, right) = strokes(Stroke::plain(key::LEFT), Stroke::plain(key::RIGHT));
    Layer {
        name: "EDIT",
        color: Rgb::new(0, 200, 255),
        effect: Effect::Solid,
        keys: [
            ctrl("UNDO", key::Z),
            ctrl("REDO", key::Y),
            ctrl("CUT", key::X),
            ctrl("COPY", key::C),
            ctrl("PASTE", key::V),
            ctrl("ALL", key::A),
            ctrl("SAVE", key::S),
            ctrl("FIND", key::F),
            tap("ESC", key::ESCAPE),
            tap_hold("TAB/SH", Stroke::plain(key::TAB), Stroke::modifiers(modifier::SHIFT)),
            tap("DEL", key::DELETE),
            sequence("LINE", &SELECT_LINE),
        ],
        left_knob: knob("HIST", undo, redo),
        right_knob: knob("CURSOR", left, right),
        right_knob_press: tap("ENTER", key::ENTER),
    }
};

const NAV: Layer = {
    let (up, down) = strokes(Stroke::plain(key::UP), Stroke::plain(key::DOWN));
    let (previous_tab, next_tab) = strokes(PREVIOUS_TAB, NEXT_TAB);
    Layer {
        name: "NAV",
        color: Rgb::new(40, 255, 80),
        effect: Effect::Wave,
        keys: [
            tap("HOME", key::HOME),
            tap("UP", key::UP),
            tap("END", key::END),
            tap("PGUP", key::PAGE_UP),
            tap("LEFT", key::LEFT),
            tap("DOWN", key::DOWN),
            tap("RIGHT", key::RIGHT),
            tap("PGDN", key::PAGE_DOWN),
            Binding {
                label: "TAB-",
                action: previous_tab,
            },
            Binding {
                label: "TAB+",
                action: next_tab,
            },
            chord("BACK", modifier::ALT, key::LEFT),
            chord("FWD", modifier::ALT, key::RIGHT),
        ],
        left_knob: knob("SCROLL", up, down),
        right_knob: knob("TABS", previous_tab, next_tab),
        right_knob_press: tap("ENTER", key::ENTER),
    }
};

const NUM: Layer = {
    let (minus, plus) = strokes(Stroke::plain(key::MINUS), Stroke::with(modifier::SHIFT, key::EQUAL));
    Layer {
        name: "NUM",
        color: Rgb::new(255, 120, 0),
        effect: Effect::Rainbow,
        keys: [
            tap("7", key::N7),
            tap("8", key::N8),
            tap("9", key::N9),
            tap("BKSP", key::BACKSPACE),
            tap("4", key::N4),
            tap("5", key::N5),
            tap("6", key::N6),
            tap("ENTER", key::ENTER),
            tap("1", key::N1),
            tap("2", key::N2),
            tap("3", key::N3),
            tap("0", key::N0),
        ],
        left_knob: VOLUME,
        right_knob: knob("-/+", minus, plus),
        right_knob_press: tap(".", key::PERIOD),
    }
};

pub static LAYERS: [Layer; LAYER_COUNT] = [MEDIA, EDIT, NAV, NUM];

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::TAP_QUEUE_CAPACITY;
    use crate::hid::consumer::MAX_USAGE;
    use crate::ui::MAX_LABEL_CHARS;

    fn labels(layer: &Layer) -> impl Iterator<Item = &'static str> + '_ {
        let knobs = [
            layer.left_knob.label,
            layer.right_knob.label,
            layer.right_knob_press.label,
        ];
        layer.keys.iter().map(|binding| binding.label).chain(knobs)
    }

    #[test]
    fn every_label_fits_its_display_cell() {
        for layer in &LAYERS {
            for label in labels(layer) {
                assert!(label.len() <= MAX_LABEL_CHARS, "{} / {label}", layer.name);
            }
        }
    }

    #[test]
    fn every_macro_fits_the_tap_queue() {
        for binding in LAYERS.iter().flat_map(|layer| layer.keys.iter()) {
            if let Action::Macro(strokes) = binding.action {
                assert!(strokes.len() <= TAP_QUEUE_CAPACITY, "{}", binding.label);
            }
        }
    }

    fn actions(layer: &Layer) -> impl Iterator<Item = Action> + '_ {
        let knobs = [&layer.left_knob, &layer.right_knob]
            .into_iter()
            .flat_map(|knob| [knob.counter_clockwise, knob.clockwise]);
        let keys = layer.keys.iter().map(|binding| binding.action);
        keys.chain(knobs).chain([layer.right_knob_press.action])
    }

    #[test]
    fn every_layer_name_fits_its_tab_and_is_unique() {
        for (index, layer) in LAYERS.iter().enumerate() {
            assert!(
                !layer.name.is_empty() && layer.name.len() <= MAX_LABEL_CHARS,
                "{}",
                layer.name
            );
            assert!(
                LAYERS[..index].iter().all(|earlier| earlier.name != layer.name),
                "{}",
                layer.name
            );
        }
    }

    #[test]
    fn every_label_and_name_uses_characters_the_font_has() {
        for layer in &LAYERS {
            for text in labels(layer).chain([layer.name]) {
                assert!(
                    text.bytes().all(|byte| (0x20..0x60).contains(&byte)),
                    "{} / {text}",
                    layer.name
                );
            }
        }
    }

    #[test]
    fn every_consumer_usage_fits_the_report_descriptor() {
        for layer in &LAYERS {
            for action in actions(layer) {
                if let Action::Consumer(usage) = action {
                    assert!(usage != 0 && usage <= MAX_USAGE, "{} / {usage:#06x}", layer.name);
                }
            }
        }
    }

    #[test]
    fn no_stroke_is_empty_and_knobs_never_carry_macros() {
        for layer in &LAYERS {
            for action in actions(layer) {
                if let Action::Stroke(stroke) = action {
                    assert!(stroke.key != 0, "{}: a stroke needs a key", layer.name);
                }
            }
            for knob in [&layer.left_knob, &layer.right_knob] {
                let turns = [knob.counter_clockwise, knob.clockwise];
                assert!(
                    turns.iter().all(|turn| !matches!(turn, Action::Macro(_))),
                    "{}",
                    knob.label
                );
            }
        }
    }

    #[test]
    fn tap_hold_is_on_keys_only_and_both_halves_send_something() {
        for layer in &LAYERS {
            for binding in &layer.keys {
                if let Action::TapHold { tap, hold } = binding.action {
                    assert!(tap.key != 0, "{}: the tap needs a key", binding.label);
                    assert!(hold.key != 0 || hold.modifiers != 0, "{}: empty hold", binding.label);
                }
            }
            let knobs = [&layer.left_knob, &layer.right_knob]
                .into_iter()
                .flat_map(|knob| [knob.counter_clockwise, knob.clockwise]);
            for action in knobs.chain([layer.right_knob_press.action]) {
                assert!(
                    !matches!(action, Action::TapHold { .. }),
                    "{}: a knob has no hold",
                    layer.name
                );
            }
        }
    }

    #[test]
    fn every_layer_has_a_colour_the_leds_can_show() {
        for layer in &LAYERS {
            assert_ne!(
                layer.color,
                Rgb::BLACK,
                "{}: a black layer looks like a dead pad",
                layer.name
            );
        }
    }
}
