//! What the user did and how long ago, for the display animations and the LED effects.

use crate::engine::Inputs;
use crate::keymap::KEY_COUNT;
use crate::led::LED_COUNT;
use crate::quadrature::Rotation;

/// Without input for this long, the display shows the idle screen and the LEDs dim.
pub const IDLE_AFTER_MS: u32 = 30_000;
/// How long the knob overlay stays after the last step. A later step starts a new count.
pub const KNOB_OVERLAY_MS: u16 = 900;
/// An age that means "longer ago than anything cares about", including "never".
pub const LONG_AGO_MS: u16 = u16::MAX;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Side {
    Left,
    Right,
}

/// The latest run of knob steps.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct KnobTurn {
    pub side: Side,
    /// Clockwise steps minus counter-clockwise steps since the run began.
    pub net_steps: i16,
    /// Time since the latest step.
    pub age_ms: u16,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Activity {
    pub uptime_ms: u64,
    /// Time since any key, knob switch or knob step.
    pub idle_ms: u32,
    pub layer_index: usize,
    /// The layer shown before the latest change, for the cross-fade.
    pub previous_layer_index: usize,
    pub layer_age_ms: u16,
    /// Time since each key last went down.
    pub key_age_ms: [u16; KEY_COUNT],
    pub knob: KnobTurn,
    /// Which LED the knob "comet" sits on. Each step of either knob moves it by one.
    pub ring_position: u8,
    /// How long the left knob has been held on its own.
    pub left_hold_ms: u16,
    /// Key state of the previous tick, to find the keys that just went down.
    pub(crate) keys: u16,
}

impl Activity {
    pub const fn new() -> Self {
        Self {
            uptime_ms: 0,
            idle_ms: 0,
            layer_index: 0,
            previous_layer_index: 0,
            layer_age_ms: LONG_AGO_MS,
            key_age_ms: [LONG_AGO_MS; KEY_COUNT],
            knob: KnobTurn {
                side: Side::Left,
                net_steps: 0,
                age_ms: LONG_AGO_MS,
            },
            ring_position: 0,
            left_hold_ms: 0,
            keys: 0,
        }
    }

    /// Advances one millisecond. `layer_index` is the layer the engine is on after this tick.
    pub fn tick(&mut self, inputs: &Inputs, layer_index: usize) {
        self.uptime_ms += 1;
        self.age_everything();
        self.note_keys(inputs.keys);
        self.note_layer(layer_index);
        if let Some(rotation) = inputs.left_rotation {
            self.note_step(Side::Left, rotation);
        }
        if let Some(rotation) = inputs.right_rotation {
            self.note_step(Side::Right, rotation);
        }
        let held_alone = inputs.left_switch && !inputs.right_switch;
        self.left_hold_ms = if held_alone {
            self.left_hold_ms.saturating_add(1)
        } else {
            0
        };
        if inputs.keys != 0 || inputs.left_switch || inputs.right_switch {
            self.idle_ms = 0;
        }
    }

    fn age_everything(&mut self) {
        self.idle_ms = self.idle_ms.saturating_add(1);
        self.layer_age_ms = self.layer_age_ms.saturating_add(1);
        self.knob.age_ms = self.knob.age_ms.saturating_add(1);
        for age in &mut self.key_age_ms {
            *age = age.saturating_add(1);
        }
    }

    fn note_keys(&mut self, keys: u16) {
        let went_down = keys & !self.keys;
        self.keys = keys;
        for key in (0..KEY_COUNT).filter(|key| went_down & (1 << key) != 0) {
            self.key_age_ms[key] = 0;
        }
    }

    fn note_layer(&mut self, layer_index: usize) {
        if layer_index != self.layer_index {
            self.previous_layer_index = self.layer_index;
            self.layer_index = layer_index;
            self.layer_age_ms = 0;
        }
    }

    fn note_step(&mut self, side: Side, rotation: Rotation) {
        let step: i16 = match rotation {
            Rotation::Clockwise => 1,
            Rotation::CounterClockwise => -1,
        };
        let continues_run = self.knob.side == side && self.knob.age_ms < KNOB_OVERLAY_MS;
        let net_steps = if continues_run { self.knob.net_steps } else { 0 };
        self.knob = KnobTurn {
            side,
            net_steps: net_steps.saturating_add(step),
            age_ms: 0,
        };
        self.ring_position = (i16::from(self.ring_position) + step).rem_euclid(LED_COUNT as i16) as u8;
        self.idle_ms = 0;
    }
}

impl Default for Activity {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const IDLE: Inputs = Inputs {
        keys: 0,
        left_switch: false,
        right_switch: false,
        left_rotation: None,
        right_rotation: None,
    };

    fn step(side: Side, rotation: Rotation) -> Inputs {
        match side {
            Side::Left => Inputs {
                left_rotation: Some(rotation),
                ..IDLE
            },
            Side::Right => Inputs {
                right_rotation: Some(rotation),
                ..IDLE
            },
        }
    }

    fn wait(activity: &mut Activity, ms: u32) {
        (0..ms).for_each(|_| activity.tick(&IDLE, activity.layer_index));
    }

    #[test]
    fn nothing_has_happened_at_power_on() {
        let activity = Activity::new();
        assert_eq!(activity.layer_age_ms, LONG_AGO_MS);
        assert_eq!(activity.knob.age_ms, LONG_AGO_MS);
        assert_eq!(activity.key_age_ms, [LONG_AGO_MS; KEY_COUNT]);
    }

    #[test]
    fn a_key_press_restarts_that_keys_age_and_the_idle_time() {
        let mut activity = Activity::new();
        wait(&mut activity, 100);
        activity.tick(&Inputs { keys: 1 << 4, ..IDLE }, 0);
        wait(&mut activity, 7);
        assert_eq!(activity.key_age_ms[4], 7);
        assert_eq!(activity.key_age_ms[3], LONG_AGO_MS);
        assert_eq!(activity.idle_ms, 7);
    }

    #[test]
    fn a_held_key_keeps_the_pad_awake_but_does_not_restart_its_age() {
        let mut activity = Activity::new();
        let held = Inputs { keys: 1, ..IDLE };
        (0..50).for_each(|_| activity.tick(&held, 0));
        assert_eq!(activity.idle_ms, 0);
        assert_eq!(activity.key_age_ms[0], 49);
    }

    #[test]
    fn a_layer_change_remembers_where_it_came_from() {
        let mut activity = Activity::new();
        activity.tick(&IDLE, 2);
        activity.tick(&IDLE, 2);
        assert_eq!((activity.previous_layer_index, activity.layer_index), (0, 2));
        assert_eq!(activity.layer_age_ms, 1);
    }

    #[test]
    fn steps_of_one_knob_add_up_while_the_overlay_is_showing() {
        let mut activity = Activity::new();
        activity.tick(&step(Side::Left, Rotation::Clockwise), 0);
        wait(&mut activity, u32::from(KNOB_OVERLAY_MS) - 2);
        activity.tick(&step(Side::Left, Rotation::Clockwise), 0);
        activity.tick(&step(Side::Left, Rotation::CounterClockwise), 0);
        assert_eq!(activity.knob.net_steps, 1);
        assert_eq!(activity.knob.age_ms, 0);
    }

    #[test]
    fn a_step_after_the_overlay_closed_or_on_the_other_knob_starts_a_new_count() {
        let mut activity = Activity::new();
        activity.tick(&step(Side::Left, Rotation::Clockwise), 0);
        activity.tick(&step(Side::Right, Rotation::CounterClockwise), 0);
        assert_eq!((activity.knob.side, activity.knob.net_steps), (Side::Right, -1));
        wait(&mut activity, u32::from(KNOB_OVERLAY_MS));
        activity.tick(&step(Side::Right, Rotation::CounterClockwise), 0);
        assert_eq!(activity.knob.net_steps, -1);
    }

    #[test]
    fn the_ring_position_wraps_in_both_directions() {
        let mut activity = Activity::new();
        activity.tick(&step(Side::Left, Rotation::CounterClockwise), 0);
        assert_eq!(usize::from(activity.ring_position), LED_COUNT - 1);
        activity.tick(&step(Side::Right, Rotation::Clockwise), 0);
        assert_eq!(activity.ring_position, 0);
    }

    #[test]
    fn the_left_hold_counts_only_while_the_left_knob_is_down_alone() {
        let mut activity = Activity::new();
        let left = Inputs {
            left_switch: true,
            ..IDLE
        };
        (0..30).for_each(|_| activity.tick(&left, 0));
        assert_eq!(activity.left_hold_ms, 30);
        activity.tick(
            &Inputs {
                right_switch: true,
                ..left
            },
            0,
        );
        assert_eq!(activity.left_hold_ms, 0);
    }

    #[test]
    fn ages_stop_at_long_ago_instead_of_wrapping() {
        let mut activity = Activity::new();
        activity.tick(&Inputs { keys: 1, ..IDLE }, 0);
        wait(&mut activity, 70_000);
        assert_eq!(activity.key_age_ms[0], LONG_AGO_MS);
        assert_eq!(activity.idle_ms, 70_000);
    }
}
