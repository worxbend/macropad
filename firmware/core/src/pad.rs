//! The whole pad as one state machine: inputs in, USB reports out, and a view for the display
//! and the LEDs. The firmware and the PC simulator both run this, so they cannot drift apart.

use crate::activity::Activity;
use crate::engine::{Engine, Inputs, Reports};
use crate::framebuffer::Framebuffer;
use crate::keymap::{Layer, LAYER_COUNT};
use crate::kps::{KpsMeter, HISTORY_BUCKETS};
use crate::led::{LedFrame, MAX_LEVEL};
use crate::lighting::{self, Lighting};
use crate::ui::{self, UiState};

/// What the host computer told the pad.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Host {
    pub caps_lock: bool,
    pub num_lock: bool,
    /// The host suspended the USB bus (it sleeps), so the pad must draw almost no current.
    pub asleep: bool,
}

pub struct Pad {
    engine: Engine,
    activity: Activity,
    kps: KpsMeter,
    layers: &'static [Layer; LAYER_COUNT],
}

impl Pad {
    pub fn new(layers: &'static [Layer; LAYER_COUNT]) -> Self {
        Self {
            engine: Engine::new(layers),
            activity: Activity::new(),
            kps: KpsMeter::default(),
            layers,
        }
    }

    /// Advances one millisecond and returns what the host should see now.
    pub fn tick(&mut self, inputs: &Inputs) -> Reports {
        let reports = self.engine.tick(inputs);
        self.kps.tick(self.engine.presses_this_tick());
        self.activity.tick(inputs, self.engine.layer_index());
        reports
    }

    pub fn view(&self) -> View {
        View {
            layers: self.layers,
            pressed_keys: self.engine.pressed_keys(),
            kps_history: self.kps.history(),
            activity: self.activity,
            led_level: self.engine.led_level(),
            flash_hold_ms: self.engine.bootloader_hold_ms(),
            flash_requested: self.engine.bootloader_requested(),
        }
    }
}

/// A snapshot of the pad for the display and the LEDs.
#[derive(Clone, Copy)]
pub struct View {
    pub layers: &'static [Layer; LAYER_COUNT],
    /// Bit `n` is set while key `n` is down.
    pub pressed_keys: u16,
    pub kps_history: [u8; HISTORY_BUCKETS],
    pub activity: Activity,
    pub led_level: u8,
    /// How long both knobs have been held toward the bootloader.
    pub flash_hold_ms: u16,
    /// The pad is about to restart as a USB drive.
    pub flash_requested: bool,
}

impl View {
    /// The view before the first tick.
    pub const fn at_power_on(layers: &'static [Layer; LAYER_COUNT]) -> Self {
        Self {
            layers,
            pressed_keys: 0,
            kps_history: [0; HISTORY_BUCKETS],
            activity: Activity::new(),
            led_level: MAX_LEVEL,
            flash_hold_ms: 0,
            flash_requested: false,
        }
    }

    pub fn layer(&self) -> &'static Layer {
        &self.layers[self.activity.layer_index]
    }

    pub fn screen(&self, host: Host) -> Framebuffer {
        ui::draw(&UiState { view: *self, host })
    }

    pub fn leds(&self, host: Host) -> LedFrame {
        lighting::frame(&Lighting {
            layer: self.layer(),
            previous_layer: &self.layers[self.activity.previous_layer_index],
            activity: &self.activity,
            level: self.led_level,
            caps_lock: host.caps_lock,
            lights_out: host.asleep || self.flash_requested,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::BOOTLOADER_HOLD_MS;
    use crate::keymap::LAYERS;
    use crate::led::Rgb;
    use crate::quadrature::Rotation;

    const IDLE: Inputs = Inputs {
        keys: 0,
        left_switch: false,
        right_switch: false,
        left_rotation: None,
        right_rotation: None,
    };

    fn run(pad: &mut Pad, inputs: Inputs, ms: u32) {
        (0..ms).for_each(|_| {
            pad.tick(&inputs);
        });
    }

    #[test]
    fn the_view_follows_the_engine_and_the_activity() {
        let mut pad = Pad::new(&LAYERS);
        run(
            &mut pad,
            Inputs {
                left_switch: true,
                ..IDLE
            },
            10,
        );
        run(&mut pad, Inputs { keys: 1 << 9, ..IDLE }, 5);
        let view = pad.view();
        assert_eq!(view.layer().name, "EDIT");
        assert_eq!(view.pressed_keys, 1 << 9);
        assert_eq!(view.activity.key_age_ms[9], 4);
        assert_eq!(view.kps_history[HISTORY_BUCKETS - 1], 1);
    }

    #[test]
    fn the_power_on_view_equals_a_new_pads_view() {
        let pad = Pad::new(&LAYERS);
        assert_eq!(pad.view().activity, View::at_power_on(&LAYERS).activity);
        assert_eq!(pad.view().led_level, View::at_power_on(&LAYERS).led_level);
    }

    #[test]
    fn the_leds_go_dark_when_the_host_sleeps_or_the_pad_restarts() {
        let mut pad = Pad::new(&LAYERS);
        run(&mut pad, IDLE, 3000);
        let awake = Host::default();
        assert_ne!(pad.view().leds(awake), [Rgb::BLACK; 8]);
        assert_eq!(pad.view().leds(Host { asleep: true, ..awake }), [Rgb::BLACK; 8]);
        let both = Inputs {
            left_switch: true,
            right_switch: true,
            ..IDLE
        };
        run(&mut pad, both, u32::from(BOOTLOADER_HOLD_MS));
        assert!(pad.view().flash_requested);
        assert_eq!(pad.view().leds(awake), [Rgb::BLACK; 8]);
    }

    #[test]
    fn brightness_set_with_the_knob_reaches_the_leds() {
        let mut pad = Pad::new(&LAYERS);
        run(&mut pad, IDLE, 3000);
        let full = pad.view().leds(Host::default());
        let dim_step = Inputs {
            left_switch: true,
            right_rotation: Some(Rotation::CounterClockwise),
            ..IDLE
        };
        (0..MAX_LEVEL).for_each(|_| run(&mut pad, dim_step, 1));
        run(&mut pad, IDLE, 1000);
        assert_ne!(full, [Rgb::BLACK; 8]);
        assert_eq!(pad.view().leds(Host::default()), [Rgb::BLACK; 8]);
    }
}
