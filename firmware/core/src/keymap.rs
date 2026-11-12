//! The keymap: edit `LAYERS` to change what the pad does.
//!
//! Key order is row-major as seen from the front: index 0 is top-left, 11 is bottom-right.
//! Labels are drawn on the display; six characters fit in a key cell.

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
    Binding {
        label,
        action: Action::Stroke(Stroke::with(modifier::CTRL, key)),
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
            tap("TAB", key::TAB),
            tap("DEL", key::DELETE),
            Binding {
                label: "LINE",
                action: Action::Macro(&SELECT_LINE),
            },
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
        effect: Effect::Solid,
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
            Binding {
                label: "BACK",
                action: Action::Stroke(Stroke::with(modifier::ALT, key::LEFT)),
            },
            Binding {
                label: "FWD",
                action: Action::Stroke(Stroke::with(modifier::ALT, key::RIGHT)),
            },
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
}
