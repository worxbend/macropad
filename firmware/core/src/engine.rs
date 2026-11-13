//! Turns debounced inputs into USB HID reports: layers, held keys, queued taps, knob gestures.
//!
//! Two rules keep one key from changing what another key means to the host:
//! a chord (key plus modifiers) is let go when a newer stroke arrives, so its modifiers never
//! land on that stroke, and a media key is let go when a newer media code arrives, so it is not
//! sent a second time when the newer one ends.
//!
//! Left knob gestures: a tap goes to the next layer. While it is held, the top row of keys jumps
//! straight to a layer and the right knob sets the LED brightness. Both knobs held ask for the
//! USB bootloader.

use crate::hid::KeyboardReport;
use crate::keymap::{Action, KnobBinding, Layer, KEY_COUNT, LAYER_COUNT};
use crate::led::MAX_LEVEL;
use crate::quadrature::Rotation;

/// Taps waiting to be sent. Knob steps and macro strokes queue here.
pub const TAP_QUEUE_CAPACITY: usize = 16;
/// How long a queued tap stays down, and how long the pause after it is.
/// Eight milliseconds spans several 1 ms USB polls, so the host sees both edges.
const TAP_PRESS_MS: u8 = 8;
const TAP_GAP_MS: u8 = 8;
/// A tap-hold key held this long sends its hold stroke. Let go earlier, it sends its tap.
pub const TAP_HOLD_MS: u8 = 200;
/// Holding both knobs down this long asks for the USB bootloader.
pub const BOOTLOADER_HOLD_MS: u16 = 1000;

/// Debounced state of every control for one millisecond.
#[derive(Clone, Copy, Default)]
pub struct Inputs {
    /// Bit `n` is set while key `n` is down.
    pub keys: u16,
    pub left_switch: bool,
    pub right_switch: bool,
    pub left_rotation: Option<Rotation>,
    pub right_rotation: Option<Rotation>,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Reports {
    pub keyboard: KeyboardReport,
    /// Consumer-control usage that is down, or 0.
    pub consumer: u16,
}

impl Reports {
    fn press(&mut self, action: Action) {
        match action {
            Action::Stroke(stroke) => self.keyboard.press(stroke),
            Action::Consumer(usage) => self.consumer = usage,
            // A macro goes through the tap queue; a tap-hold key sends nothing until it is decided.
            Action::None | Action::Macro(_) | Action::TapHold { .. } => {}
        }
    }
}

/// First-in first-out taps, each pressed for `TAP_PRESS_MS` then released for `TAP_GAP_MS`.
struct TapQueue {
    taps: [Action; TAP_QUEUE_CAPACITY],
    head: usize,
    len: usize,
    head_age_ms: u8,
}

impl TapQueue {
    const fn new() -> Self {
        Self {
            taps: [Action::None; TAP_QUEUE_CAPACITY],
            head: 0,
            len: 0,
            head_age_ms: 0,
        }
    }

    fn free_slots(&self) -> usize {
        TAP_QUEUE_CAPACITY - self.len
    }

    fn push(&mut self, tap: Action) {
        debug_assert!(self.free_slots() > 0, "callers check free_slots first");
        self.taps[(self.head + self.len) % TAP_QUEUE_CAPACITY] = tap;
        self.len += 1;
    }

    /// The tap that is down right now, if any.
    fn pressed(&self) -> Action {
        if self.len > 0 && self.head_age_ms < TAP_PRESS_MS {
            self.taps[self.head]
        } else {
            Action::None
        }
    }

    fn advance_one_ms(&mut self) {
        if self.len == 0 {
            return;
        }
        self.head_age_ms += 1;
        if self.head_age_ms == TAP_PRESS_MS + TAP_GAP_MS {
            self.head = (self.head + 1) % TAP_QUEUE_CAPACITY;
            self.len -= 1;
            self.head_age_ms = 0;
        }
    }
}

#[derive(Default)]
struct KnobTaps {
    left: bool,
    right: bool,
}

/// Tells a tap of one knob from the two-knob bootloader hold.
#[derive(Default)]
struct KnobSwitches {
    left_down: bool,
    right_down: bool,
    /// The current gesture already did something (both knobs down, or a system action),
    /// so releases are not taps.
    gesture_used: bool,
    both_down_ms: u16,
    bootloader_requested: bool,
}

impl KnobSwitches {
    fn update(&mut self, left_down: bool, right_down: bool) -> KnobTaps {
        self.track_both_down(left_down && right_down);
        let taps = KnobTaps {
            left: self.left_down && !left_down && !self.gesture_used,
            right: self.right_down && !right_down && !self.gesture_used,
        };
        if !left_down && !right_down {
            self.gesture_used = false;
        }
        self.left_down = left_down;
        self.right_down = right_down;
        taps
    }

    fn mark_gesture_used(&mut self) {
        self.gesture_used = true;
    }

    fn track_both_down(&mut self, both_down: bool) {
        if !both_down {
            self.both_down_ms = 0;
            return;
        }
        self.gesture_used = true;
        self.both_down_ms = self.both_down_ms.saturating_add(1);
        if self.both_down_ms >= BOOTLOADER_HOLD_MS {
            self.bootloader_requested = true;
        }
    }
}

pub struct Engine {
    layers: &'static [Layer; LAYER_COUNT],
    layer_index: usize,
    /// What each held key sends, fixed at press time so a layer change cannot strand a key.
    held: [Action; KEY_COUNT],
    /// How long each undecided tap-hold key has been down.
    tap_hold_age_ms: [u8; KEY_COUNT],
    /// The held key whose chord is in the report, if any. A newer stroke releases it.
    chord_key: Option<usize>,
    /// The held key whose media code is in the report, if any. A newer media code releases it.
    media_key: Option<usize>,
    pressed_keys: u16,
    taps: TapQueue,
    knob_switches: KnobSwitches,
    presses_this_tick: u8,
    led_level: u8,
}

impl Engine {
    pub fn new(layers: &'static [Layer; LAYER_COUNT]) -> Self {
        Self {
            layers,
            layer_index: 0,
            held: [Action::None; KEY_COUNT],
            tap_hold_age_ms: [0; KEY_COUNT],
            chord_key: None,
            media_key: None,
            pressed_keys: 0,
            taps: TapQueue::new(),
            knob_switches: KnobSwitches::default(),
            presses_this_tick: 0,
            led_level: MAX_LEVEL,
        }
    }

    /// Advances one millisecond and returns what the host should see now.
    pub fn tick(&mut self, inputs: &Inputs) -> Reports {
        self.presses_this_tick = 0;
        self.age_tap_holds();
        if Self::system_held(inputs) {
            self.apply_system_keys(inputs.keys);
            self.apply_brightness_step(inputs.right_rotation);
        } else {
            self.apply_key_changes(inputs.keys);
            self.apply_rotation(self.layer().right_knob, inputs.right_rotation);
        }
        self.apply_rotation(self.layer().left_knob, inputs.left_rotation);
        self.apply_knob_switches(inputs.left_switch, inputs.right_switch);
        let reports = self.reports();
        self.taps.advance_one_ms();
        reports
    }

    pub fn layer(&self) -> &'static Layer {
        &self.layers[self.layer_index]
    }

    pub fn layer_index(&self) -> usize {
        self.layer_index
    }

    /// LED brightness, 0 (off) to `MAX_LEVEL`.
    pub fn led_level(&self) -> u8 {
        self.led_level
    }

    /// How long both knobs have been down, for the "hold to flash" progress bar.
    pub fn bootloader_hold_ms(&self) -> u16 {
        self.knob_switches.both_down_ms
    }

    /// Bit `n` is set while key `n` is down.
    pub fn pressed_keys(&self) -> u16 {
        self.pressed_keys
    }

    /// Keys that went down in the latest tick.
    pub fn presses_this_tick(&self) -> u8 {
        self.presses_this_tick
    }

    /// Latches once both knobs were held for `BOOTLOADER_HOLD_MS`.
    pub fn bootloader_requested(&self) -> bool {
        self.knob_switches.bootloader_requested
    }

    /// The left knob is held on its own: keys and the right knob act on the pad, not the host.
    fn system_held(inputs: &Inputs) -> bool {
        inputs.left_switch && !inputs.right_switch
    }

    /// Records the new key state, releases what went up and returns the keys that went down.
    fn take_new_presses(&mut self, keys: u16) -> impl Iterator<Item = usize> {
        let changed = keys ^ self.pressed_keys;
        self.pressed_keys = keys;
        for key in (0..KEY_COUNT).filter(|key| changed & !keys & (1 << key) != 0) {
            self.release_key(key);
        }
        let pressed = changed & keys;
        self.presses_this_tick += pressed.count_ones() as u8;
        (0..KEY_COUNT).filter(move |key| pressed & (1 << key) != 0)
    }

    fn apply_key_changes(&mut self, keys: u16) {
        for key in self.take_new_presses(keys) {
            self.settle_tap_holds_as_held();
            self.press_key(key);
        }
    }

    /// A tap-hold key let go before it was decided sends its tap now.
    fn release_key(&mut self, key: usize) {
        self.chord_key = self.chord_key.filter(|&owner| owner != key);
        self.media_key = self.media_key.filter(|&owner| owner != key);
        if let Action::TapHold { tap, .. } = core::mem::replace(&mut self.held[key], Action::None) {
            self.enqueue(Action::Stroke(tap));
        }
    }

    fn age_tap_holds(&mut self) {
        for key in 0..KEY_COUNT {
            let Action::TapHold { hold, .. } = self.held[key] else {
                continue;
            };
            self.tap_hold_age_ms[key] += 1;
            if self.tap_hold_age_ms[key] >= TAP_HOLD_MS {
                self.hold(key, Action::Stroke(hold));
            }
        }
    }

    /// Another key or a knob click while a tap-hold key is down means it is being held on
    /// purpose: Shift plus a knob turn must not wait for `TAP_HOLD_MS`.
    fn settle_tap_holds_as_held(&mut self) {
        for key in 0..KEY_COUNT {
            if let Action::TapHold { hold, .. } = self.held[key] {
                self.hold(key, Action::Stroke(hold));
            }
        }
    }

    /// Keeps `action` down for as long as `key` is, after letting go what it must not mix with.
    fn hold(&mut self, key: usize, action: Action) {
        self.yield_to(action);
        self.held[key] = action;
        match action {
            Action::Stroke(stroke) if stroke.is_chord() => self.chord_key = Some(key),
            Action::Consumer(_) => self.media_key = Some(key),
            Action::TapHold { .. } => self.tap_hold_age_ms[key] = 0,
            _ => {}
        }
    }

    /// Lets go of the held chord before a newer stroke, and of the held media key before a newer
    /// media code. Without this, Ctrl+Z held plus ESC would reach the host as Ctrl+ESC, and PLAY
    /// held across a volume click would be sent again when the click ends.
    fn yield_to(&mut self, newer: Action) {
        let older_key = match newer {
            Action::Stroke(_) | Action::Macro(_) => self.chord_key.take(),
            Action::Consumer(_) => self.media_key.take(),
            Action::None | Action::TapHold { .. } => None,
        };
        if let Some(key) = older_key {
            self.held[key] = Action::None;
        }
    }

    /// Key `n` of the top row jumps to layer `n`. Nothing is sent to the host.
    fn apply_system_keys(&mut self, keys: u16) {
        for key in self.take_new_presses(keys) {
            self.knob_switches.mark_gesture_used();
            if key < LAYER_COUNT {
                self.layer_index = key;
            }
        }
    }

    fn apply_brightness_step(&mut self, rotation: Option<Rotation>) {
        let Some(rotation) = rotation else { return };
        self.knob_switches.mark_gesture_used();
        self.led_level = match rotation {
            Rotation::Clockwise => (self.led_level + 1).min(MAX_LEVEL),
            Rotation::CounterClockwise => self.led_level.saturating_sub(1),
        };
    }

    fn press_key(&mut self, key: usize) {
        match self.layer().keys[key].action {
            Action::Macro(strokes) => self.enqueue(Action::Macro(strokes)),
            held_action => self.hold(key, held_action),
        }
    }

    fn apply_rotation(&mut self, knob: KnobBinding, rotation: Option<Rotation>) {
        if rotation.is_some() {
            self.settle_tap_holds_as_held();
        }
        match rotation {
            Some(Rotation::Clockwise) => self.enqueue(knob.clockwise),
            Some(Rotation::CounterClockwise) => self.enqueue(knob.counter_clockwise),
            None => {}
        }
    }

    fn apply_knob_switches(&mut self, left_down: bool, right_down: bool) {
        let taps = self.knob_switches.update(left_down, right_down);
        if taps.right {
            self.enqueue(self.layer().right_knob_press.action);
        }
        if taps.left {
            self.layer_index = (self.layer_index + 1) % LAYER_COUNT;
        }
    }

    /// Queues an action as taps. When the queue is full the action is dropped whole:
    /// a knob spun faster than the host can follow loses steps rather than lagging behind,
    /// and a macro is never typed in part.
    fn enqueue(&mut self, action: Action) {
        self.yield_to(action);
        match action {
            Action::None | Action::TapHold { .. } => {}
            Action::Macro(strokes) if strokes.len() <= self.taps.free_slots() => {
                strokes
                    .iter()
                    .for_each(|&stroke| self.taps.push(Action::Stroke(stroke)));
            }
            Action::Macro(_) => {}
            single_tap if self.taps.free_slots() > 0 => self.taps.push(single_tap),
            _ => {}
        }
    }

    fn reports(&self) -> Reports {
        let mut reports = Reports::default();
        self.held.iter().for_each(|&action| reports.press(action));
        reports.press(self.taps.pressed());
        reports
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hid::{consumer, key, modifier, Stroke};
    use crate::keymap::LAYERS;

    const LEFT_SWITCH: Inputs = Inputs {
        keys: 0,
        left_switch: true,
        right_switch: false,
        left_rotation: None,
        right_rotation: None,
    };
    const RIGHT_SWITCH: Inputs = Inputs {
        left_switch: false,
        right_switch: true,
        ..LEFT_SWITCH
    };
    const BOTH_SWITCHES: Inputs = Inputs {
        right_switch: true,
        ..LEFT_SWITCH
    };
    const IDLE: Inputs = Inputs {
        left_switch: false,
        ..LEFT_SWITCH
    };
    const LEFT_CLOCKWISE: Inputs = Inputs {
        left_rotation: Some(Rotation::Clockwise),
        ..IDLE
    };

    fn keys(mask: u16) -> Inputs {
        Inputs { keys: mask, ..IDLE }
    }

    /// Runs `ticks` milliseconds of the same input and returns each distinct report in order.
    fn run(engine: &mut Engine, inputs: Inputs, ticks: usize) -> Vec<Reports> {
        let mut distinct: Vec<Reports> = Vec::new();
        for tick in 0..ticks {
            // Rotations are events: they belong to the first tick only.
            let inputs = if tick == 0 {
                inputs
            } else {
                Inputs {
                    left_rotation: None,
                    right_rotation: None,
                    ..inputs
                }
            };
            let reports = engine.tick(&inputs);
            if distinct.last() != Some(&reports) {
                distinct.push(reports);
            }
        }
        distinct
    }

    fn keyboard(modifiers: u8, key: u8) -> Reports {
        let mut reports = Reports::default();
        reports.keyboard.press(Stroke::with(modifiers, key));
        reports
    }

    fn consumer(usage: u16) -> Reports {
        Reports {
            consumer: usage,
            ..Reports::default()
        }
    }

    fn tap_left_knob(engine: &mut Engine) {
        engine.tick(&LEFT_SWITCH);
        engine.tick(&IDLE);
    }

    fn engine_on_layer(index: usize) -> Engine {
        let mut engine = Engine::new(&LAYERS);
        (0..index).for_each(|_| tap_left_knob(&mut engine));
        engine
    }

    #[test]
    fn a_stroke_key_is_down_while_held_and_up_after() {
        let mut engine = engine_on_layer(1);
        assert_eq!(engine.tick(&keys(1 << 3)), keyboard(modifier::CTRL, key::C));
        assert_eq!(engine.tick(&keys(1 << 3)), keyboard(modifier::CTRL, key::C));
        assert_eq!(engine.tick(&IDLE), Reports::default());
    }

    #[test]
    fn a_consumer_key_is_down_while_held() {
        let mut engine = Engine::new(&LAYERS);
        assert_eq!(engine.tick(&keys(1 << 1)), consumer(consumer::PLAY_PAUSE));
        assert_eq!(engine.tick(&IDLE), Reports::default());
    }

    #[test]
    fn two_held_keys_share_one_report() {
        let mut engine = engine_on_layer(3);
        let reports = engine.tick(&keys(0b11));
        assert_eq!(reports.keyboard.keys[..2], [key::N7, key::N8]);
    }

    #[test]
    fn left_knob_tap_cycles_through_all_layers_and_wraps() {
        let mut engine = Engine::new(&LAYERS);
        let mut visited = Vec::new();
        for _ in 0..=LAYER_COUNT {
            visited.push(engine.layer().name);
            tap_left_knob(&mut engine);
        }
        assert_eq!(visited, ["MEDIA", "EDIT", "NAV", "NUM", "MEDIA"]);
    }

    #[test]
    fn layer_changes_on_release_not_on_press() {
        let mut engine = Engine::new(&LAYERS);
        engine.tick(&LEFT_SWITCH);
        assert_eq!(engine.layer().name, "MEDIA");
    }

    #[test]
    fn a_key_held_across_a_layer_change_keeps_its_action_until_released() {
        let mut engine = engine_on_layer(3);
        let seven_held = Inputs {
            left_switch: true,
            ..keys(1)
        };
        engine.tick(&keys(1));
        engine.tick(&seven_held);
        assert_eq!(engine.tick(&keys(1)), keyboard(0, key::N7));
        assert_eq!(engine.layer().name, "MEDIA");
        assert_eq!(engine.tick(&IDLE), Reports::default());
    }

    #[test]
    fn a_knob_step_is_a_timed_tap() {
        let mut engine = Engine::new(&LAYERS);
        let reports: Vec<_> = (0..20)
            .map(|tick| engine.tick(if tick == 0 { &LEFT_CLOCKWISE } else { &IDLE }))
            .collect();
        assert!(reports[..8].iter().all(|r| *r == consumer(consumer::VOLUME_UP)));
        assert!(reports[8..].iter().all(|r| *r == Reports::default()));
    }

    #[test]
    fn counter_clockwise_sends_the_other_binding() {
        let mut engine = Engine::new(&LAYERS);
        let step = Inputs {
            left_rotation: Some(Rotation::CounterClockwise),
            ..IDLE
        };
        assert_eq!(engine.tick(&step), consumer(consumer::VOLUME_DOWN));
    }

    #[test]
    fn the_right_knob_uses_its_own_binding() {
        let mut engine = Engine::new(&LAYERS);
        let step = Inputs {
            right_rotation: Some(Rotation::Clockwise),
            ..IDLE
        };
        assert_eq!(engine.tick(&step), consumer(consumer::BRIGHTNESS_UP));
    }

    #[test]
    fn two_quick_steps_become_two_separate_taps() {
        let mut engine = Engine::new(&LAYERS);
        engine.tick(&LEFT_CLOCKWISE);
        let after_second_step = run(&mut engine, LEFT_CLOCKWISE, 40);
        let volume_up = consumer(consumer::VOLUME_UP);
        assert_eq!(
            after_second_step,
            [volume_up, Reports::default(), volume_up, Reports::default()]
        );
    }

    #[test]
    fn a_macro_types_its_strokes_in_order() {
        let mut engine = engine_on_layer(1);
        let typed = run(&mut engine, keys(1 << 11), 40);
        let released = Reports::default();
        assert_eq!(
            typed,
            [
                keyboard(0, key::HOME),
                released,
                keyboard(modifier::SHIFT, key::END),
                released
            ]
        );
    }

    #[test]
    fn steps_beyond_the_queue_capacity_are_dropped() {
        let mut engine = Engine::new(&LAYERS);
        let steps = TAP_QUEUE_CAPACITY + 5;
        let mut reports: Vec<Reports> = (0..steps).map(|_| engine.tick(&LEFT_CLOCKWISE)).collect();
        reports.extend((0..1000).map(|_| engine.tick(&IDLE)));
        reports.dedup();
        let taps_sent = reports.iter().filter(|r| r.consumer != 0).count();
        // The first tap finished while the steps were still arriving, which freed one slot.
        assert_eq!(taps_sent, TAP_QUEUE_CAPACITY + 1);
    }

    #[test]
    fn a_macro_that_does_not_fit_is_dropped_whole() {
        let mut engine = engine_on_layer(1);
        let right_step = Inputs {
            right_rotation: Some(Rotation::Clockwise),
            ..IDLE
        };
        (0..TAP_QUEUE_CAPACITY - 1).for_each(|_| {
            engine.tick(&right_step);
        });
        let typed = run(&mut engine, keys(1 << 11), 1000);
        assert!(typed
            .iter()
            .all(|r| r.keyboard.keys[0] != key::HOME && r.keyboard.keys[0] != key::END));
    }

    #[test]
    fn right_knob_tap_sends_its_binding_on_release() {
        let mut engine = Engine::new(&LAYERS);
        assert_eq!(engine.tick(&RIGHT_SWITCH), Reports::default());
        assert_eq!(engine.tick(&IDLE), consumer(consumer::MUTE));
    }

    #[test]
    fn holding_both_knobs_requests_the_bootloader_after_the_hold_time() {
        let mut engine = Engine::new(&LAYERS);
        run(&mut engine, BOTH_SWITCHES, usize::from(BOOTLOADER_HOLD_MS) - 1);
        assert!(!engine.bootloader_requested());
        engine.tick(&BOTH_SWITCHES);
        assert!(engine.bootloader_requested());
    }

    #[test]
    fn a_short_two_knob_press_does_nothing_at_all() {
        let mut engine = Engine::new(&LAYERS);
        run(&mut engine, BOTH_SWITCHES, 100);
        engine.tick(&RIGHT_SWITCH);
        let after_release = run(&mut engine, IDLE, 40);
        assert_eq!(after_release, [Reports::default()]);
        assert_eq!(engine.layer().name, "MEDIA");
        assert!(!engine.bootloader_requested());
    }

    #[test]
    fn an_interrupted_two_knob_hold_starts_counting_again() {
        let mut engine = Engine::new(&LAYERS);
        run(&mut engine, BOTH_SWITCHES, usize::from(BOOTLOADER_HOLD_MS) - 1);
        engine.tick(&LEFT_SWITCH);
        run(&mut engine, BOTH_SWITCHES, usize::from(BOOTLOADER_HOLD_MS) - 1);
        assert!(!engine.bootloader_requested());
    }

    #[test]
    fn knob_taps_work_again_after_a_two_knob_press() {
        let mut engine = Engine::new(&LAYERS);
        run(&mut engine, BOTH_SWITCHES, 10);
        engine.tick(&IDLE);
        tap_left_knob(&mut engine);
        assert_eq!(engine.layer().name, "EDIT");
    }

    #[test]
    fn presses_are_counted_in_the_tick_they_happen() {
        let mut engine = Engine::new(&LAYERS);
        engine.tick(&keys(0b101));
        assert_eq!(engine.presses_this_tick(), 2);
        assert_eq!(engine.pressed_keys(), 0b101);
        engine.tick(&keys(0b101));
        assert_eq!(engine.presses_this_tick(), 0);
    }

    fn holding_left(inputs: Inputs) -> Inputs {
        Inputs {
            left_switch: true,
            ..inputs
        }
    }

    const RIGHT_CLOCKWISE: Inputs = Inputs {
        right_rotation: Some(Rotation::Clockwise),
        ..IDLE
    };
    const RIGHT_COUNTER_CLOCKWISE: Inputs = Inputs {
        right_rotation: Some(Rotation::CounterClockwise),
        ..IDLE
    };

    #[test]
    fn left_knob_held_plus_a_top_row_key_jumps_to_that_layer() {
        let mut engine = Engine::new(&LAYERS);
        engine.tick(&LEFT_SWITCH);
        assert_eq!(engine.tick(&holding_left(keys(1 << 2))), Reports::default());
        assert_eq!(engine.layer().name, "NAV");
        // Releasing the knob afterwards is not a "next layer" tap.
        run(&mut engine, IDLE, 5);
        assert_eq!(engine.layer().name, "NAV");
    }

    #[test]
    fn a_layer_jump_key_sends_nothing_even_if_it_outlasts_the_knob() {
        let mut engine = Engine::new(&LAYERS);
        engine.tick(&LEFT_SWITCH);
        engine.tick(&holding_left(keys(1 << 1)));
        assert_eq!(run(&mut engine, keys(1 << 1), 30), [Reports::default()]);
    }

    #[test]
    fn keys_below_the_top_row_do_nothing_while_the_left_knob_is_held() {
        let mut engine = Engine::new(&LAYERS);
        engine.tick(&LEFT_SWITCH);
        assert_eq!(engine.tick(&holding_left(keys(1 << 7))), Reports::default());
        engine.tick(&IDLE);
        assert_eq!(engine.layer().name, "MEDIA");
    }

    #[test]
    fn left_knob_held_plus_right_knob_sets_the_led_level_and_sends_nothing() {
        let mut engine = Engine::new(&LAYERS);
        assert_eq!(engine.led_level(), MAX_LEVEL);
        engine.tick(&LEFT_SWITCH);
        let sent = run(&mut engine, holding_left(RIGHT_COUNTER_CLOCKWISE), 30);
        assert_eq!(sent, [Reports::default()]);
        assert_eq!(engine.led_level(), MAX_LEVEL - 1);
        engine.tick(&holding_left(RIGHT_CLOCKWISE));
        assert_eq!(engine.led_level(), MAX_LEVEL);
        engine.tick(&IDLE);
        assert_eq!(engine.layer().name, "MEDIA", "the release is not a layer tap");
    }

    #[test]
    fn the_led_level_stops_at_both_ends() {
        let mut engine = Engine::new(&LAYERS);
        engine.tick(&holding_left(RIGHT_CLOCKWISE));
        assert_eq!(engine.led_level(), MAX_LEVEL);
        (0..=MAX_LEVEL).for_each(|_| {
            engine.tick(&holding_left(RIGHT_COUNTER_CLOCKWISE));
        });
        assert_eq!(engine.led_level(), 0);
    }

    /// Regression: PLAY held across a volume click came back when the click ended, so the host
    /// saw PLAY pressed twice and toggled playback back.
    #[test]
    fn a_held_media_key_is_not_sent_again_after_a_knob_click() {
        let mut engine = Engine::new(&LAYERS);
        let play_held = keys(1 << 1);
        let click = Inputs {
            left_rotation: Some(Rotation::Clockwise),
            ..play_held
        };
        engine.tick(&play_held);
        let seen = run(&mut engine, click, 40);
        assert_eq!(seen, [consumer(consumer::VOLUME_UP), Reports::default()]);
    }

    /// Regression: with PREV and NEXT both held, letting go of NEXT sent PREV a second time.
    #[test]
    fn the_older_of_two_held_media_keys_does_not_come_back() {
        let mut engine = Engine::new(&LAYERS);
        assert_eq!(engine.tick(&keys(1 << 0)), consumer(consumer::PREVIOUS_TRACK));
        assert_eq!(engine.tick(&keys(1 << 0 | 1 << 2)), consumer(consumer::NEXT_TRACK));
        assert_eq!(engine.tick(&keys(1 << 0)), Reports::default());
    }

    /// Regression: UNDO (Ctrl+Z) held plus ESC reached the host as Ctrl+ESC.
    #[test]
    fn a_held_chord_does_not_lend_its_modifiers_to_the_next_key() {
        let mut engine = engine_on_layer(1);
        assert_eq!(engine.tick(&keys(1 << 0)), keyboard(modifier::CTRL, key::Z));
        assert_eq!(engine.tick(&keys(1 << 0 | 1 << 8)), keyboard(0, key::ESCAPE));
        assert_eq!(engine.tick(&keys(1 << 0)), Reports::default());
    }

    /// Regression: COPY (Ctrl+C) held plus a CURSOR knob click reached the host as Ctrl+RIGHT.
    #[test]
    fn a_held_chord_does_not_lend_its_modifiers_to_a_knob_click() {
        let mut engine = engine_on_layer(1);
        let copy_held = keys(1 << 3);
        let click = Inputs {
            right_rotation: Some(Rotation::Clockwise),
            ..copy_held
        };
        engine.tick(&copy_held);
        assert_eq!(
            run(&mut engine, click, 40),
            [keyboard(0, key::RIGHT), Reports::default()]
        );
    }

    #[test]
    fn a_released_chord_key_can_be_pressed_again() {
        let mut engine = engine_on_layer(1);
        engine.tick(&keys(1 << 0));
        engine.tick(&keys(1 << 0 | 1 << 8));
        engine.tick(&IDLE);
        assert_eq!(engine.tick(&keys(1 << 0)), keyboard(modifier::CTRL, key::Z));
    }

    #[test]
    fn plain_keys_and_a_media_key_stay_down_together() {
        let mut engine = Engine::new(&LAYERS);
        let reports = engine.tick(&keys(1 << 1 | 1 << 4 | 1 << 5));
        assert_eq!(reports.consumer, consumer::PLAY_PAUSE);
        assert_eq!(reports.keyboard.keys[..2], [key::F13, key::F14]);
    }

    const TAB_OR_SHIFT: Inputs = Inputs { keys: 1 << 9, ..IDLE };

    #[test]
    fn a_tap_hold_key_let_go_early_sends_its_tap_on_release() {
        let mut engine = engine_on_layer(1);
        assert_eq!(
            run(&mut engine, TAB_OR_SHIFT, usize::from(TAP_HOLD_MS) - 1),
            [Reports::default()]
        );
        assert_eq!(run(&mut engine, IDLE, 40), [keyboard(0, key::TAB), Reports::default()]);
    }

    #[test]
    fn a_tap_hold_key_kept_down_sends_its_hold_until_let_go_and_no_tap() {
        let mut engine = engine_on_layer(1);
        let seen = run(&mut engine, TAB_OR_SHIFT, usize::from(TAP_HOLD_MS) + 50);
        assert_eq!(seen, [Reports::default(), keyboard(modifier::SHIFT, 0)]);
        assert_eq!(run(&mut engine, IDLE, 40), [Reports::default()]);
    }

    #[test]
    fn another_key_decides_a_tap_hold_key_as_held_at_once() {
        let mut engine = engine_on_layer(1);
        engine.tick(&TAB_OR_SHIFT);
        let with_escape = Inputs {
            keys: 1 << 9 | 1 << 8,
            ..IDLE
        };
        assert_eq!(engine.tick(&with_escape), keyboard(modifier::SHIFT, key::ESCAPE));
    }

    #[test]
    fn a_knob_click_decides_a_tap_hold_key_as_held_so_shift_reaches_the_click() {
        let mut engine = engine_on_layer(1);
        engine.tick(&TAB_OR_SHIFT);
        let click = Inputs {
            right_rotation: Some(Rotation::CounterClockwise),
            ..TAB_OR_SHIFT
        };
        assert_eq!(
            run(&mut engine, click, 40),
            [keyboard(modifier::SHIFT, key::LEFT), keyboard(modifier::SHIFT, 0)]
        );
    }

    #[test]
    fn a_tap_hold_key_can_be_tapped_twice_in_a_row() {
        let mut engine = engine_on_layer(1);
        for _ in 0..2 {
            run(&mut engine, TAB_OR_SHIFT, 30);
            assert_eq!(run(&mut engine, IDLE, 40), [keyboard(0, key::TAB), Reports::default()]);
        }
    }

    #[test]
    fn the_bootloader_hold_time_is_visible_while_both_knobs_are_down() {
        let mut engine = Engine::new(&LAYERS);
        run(&mut engine, BOTH_SWITCHES, 250);
        assert_eq!(engine.bootloader_hold_ms(), 250);
        engine.tick(&IDLE);
        assert_eq!(engine.bootloader_hold_ms(), 0);
    }
}
