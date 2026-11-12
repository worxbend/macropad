//! Reads the keys and knobs once per millisecond.

use embassy_rp::gpio::Input;
use macropad_core::debounce::Debouncer;
use macropad_core::engine::Inputs;
use macropad_core::keymap::KEY_COUNT;
use macropad_core::quadrature::{QuadratureDecoder, Rotation};

use crate::board::Knob;

struct KnobScanner {
    pins: Knob,
    decoder: QuadratureDecoder,
    switch: Debouncer,
}

impl KnobScanner {
    fn new(pins: Knob) -> Self {
        Self {
            pins,
            decoder: QuadratureDecoder::default(),
            switch: Debouncer::default(),
        }
    }

    /// If a knob turns the wrong way, swap `a` and `b` here.
    fn rotation(&mut self) -> Option<Rotation> {
        self.decoder.sample(self.pins.a.is_high(), self.pins.b.is_high())
    }

    fn switch_down(&mut self) -> bool {
        self.switch.sample(self.pins.switch.is_low())
    }
}

pub struct Scanner {
    keys: [Input<'static>; KEY_COUNT],
    key_debouncers: [Debouncer; KEY_COUNT],
    left_knob: KnobScanner,
    right_knob: KnobScanner,
}

impl Scanner {
    pub fn new(keys: [Input<'static>; KEY_COUNT], left_knob: Knob, right_knob: Knob) -> Self {
        Self {
            keys,
            key_debouncers: [Debouncer::default(); KEY_COUNT],
            left_knob: KnobScanner::new(left_knob),
            right_knob: KnobScanner::new(right_knob),
        }
    }

    pub fn sample(&mut self) -> Inputs {
        Inputs {
            keys: self.debounced_keys(),
            left_switch: self.left_knob.switch_down(),
            right_switch: self.right_knob.switch_down(),
            left_rotation: self.left_knob.rotation(),
            right_rotation: self.right_knob.rotation(),
        }
    }

    fn debounced_keys(&mut self) -> u16 {
        let mut down_mask = 0;
        for (key, (pin, debouncer)) in self.keys.iter().zip(&mut self.key_debouncers).enumerate() {
            if debouncer.sample(pin.is_low()) {
                down_mask |= 1 << key;
            }
        }
        down_mask
    }
}
