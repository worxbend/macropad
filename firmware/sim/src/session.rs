//! A scripted session with the pad: the same `Pad` the firmware runs, fed with timed inputs.

use macropad_core::engine::{Inputs, Reports};
use macropad_core::framebuffer::Framebuffer;
use macropad_core::keymap::LAYERS;
use macropad_core::led::LedFrame;
use macropad_core::pad::{Host, Pad};
use macropad_core::quadrature::Rotation;
use macropad_core::sharp_lcd::{FrameEncoder, Orientation};
use macropad_core::ui::{screen_for, Screen, UiState};

use crate::panel::Panel;

/// Time between two recorded frames: 20 frames per second.
pub const FRAME_MS: u32 = 50;
/// A knob spun by hand: time from one click to the next.
const STEP_GAP_MS: u32 = 90;

pub const IDLE: Inputs = Inputs {
    keys: 0,
    left_switch: false,
    right_switch: false,
    left_rotation: None,
    right_rotation: None,
};
pub const LEFT_HELD: Inputs = Inputs {
    left_switch: true,
    ..IDLE
};
pub const BOTH_HELD: Inputs = Inputs {
    right_switch: true,
    ..LEFT_HELD
};

#[derive(Clone, Copy)]
pub enum Knob {
    Left,
    Right,
}

/// The pad at one moment: what it showed, what was being done to it, what it told the host.
#[derive(Clone)]
pub struct Shot {
    pub screen: Screen,
    /// The picture in the panel model's memory after it received the firmware's SPI frame.
    pub display: Framebuffer,
    pub leds: LedFrame,
    pub uptime_ms: u64,
    pub layer_index: usize,
    pub led_level: u8,
    pub inputs: Inputs,
    /// Clicks each knob has turned since power-on, clockwise positive: left, right.
    pub knob_clicks: [i32; 2],
    pub reports: Reports,
    /// How many entries of the session's host log existed at this moment.
    pub log_len: usize,
}

/// A change of what the host sees.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct HostEvent {
    pub at_ms: u64,
    pub reports: Reports,
}

/// A recorded session: its frames and everything the host was sent meanwhile.
pub struct Film {
    pub frames: Vec<Shot>,
    pub host_log: Vec<HostEvent>,
}

/// The screen as the panel would hold it: encoded by the firmware, decoded by the panel model.
fn through_the_wire(screen: &Framebuffer) -> Framebuffer {
    let mut panel = Panel::default();
    panel
        .receive(&FrameEncoder::new(Orientation::Normal).encode(screen))
        .expect("the firmware's LCD frame must be one the panel model accepts");
    panel.memory().clone()
}

pub struct Session {
    pad: Pad,
    pub host: Host,
    recording: bool,
    ms_since_frame: u32,
    frames: Vec<Shot>,
    inputs: Inputs,
    knob_clicks: [i32; 2],
    reports: Reports,
    host_log: Vec<HostEvent>,
}

impl Session {
    pub fn new() -> Self {
        Self {
            pad: Pad::new(&LAYERS),
            host: Host::default(),
            recording: false,
            ms_since_frame: 0,
            frames: Vec::new(),
            inputs: IDLE,
            knob_clicks: [0; 2],
            reports: Reports::default(),
            host_log: Vec::new(),
        }
    }

    /// A pad that finished its power-on splash and sits on layer `layer_index`.
    pub fn settled_on(layer_index: usize) -> Self {
        let mut session = Self::new();
        session.run(LEFT_HELD, 1);
        session.run(
            Inputs {
                keys: 1 << layer_index,
                ..LEFT_HELD
            },
            1,
        );
        session.wait(2500);
        session
    }

    /// From now on, every `FRAME_MS` of pad time adds one frame.
    pub fn start_recording(&mut self) {
        self.recording = true;
    }

    pub fn into_film(self) -> Film {
        Film {
            frames: self.frames,
            host_log: self.host_log,
        }
    }

    pub fn shot(&self) -> Shot {
        let view = self.pad.view();
        Shot {
            screen: screen_for(&UiState { view, host: self.host }),
            display: through_the_wire(&view.screen(self.host)),
            leds: view.leds(self.host),
            uptime_ms: view.activity.uptime_ms,
            layer_index: view.activity.layer_index,
            led_level: view.led_level,
            inputs: self.inputs,
            knob_clicks: self.knob_clicks,
            reports: self.reports,
            log_len: self.host_log.len(),
        }
    }

    /// Feeds the same inputs for `ms` milliseconds. Knob rotations are events: put them in a 1 ms run.
    pub fn run(&mut self, inputs: Inputs, ms: u32) {
        for _ in 0..ms {
            self.tick(inputs);
            self.ms_since_frame += 1;
            if self.recording && self.ms_since_frame >= FRAME_MS {
                self.ms_since_frame = 0;
                self.frames.push(self.shot());
            }
        }
    }

    fn tick(&mut self, inputs: Inputs) {
        let reports = self.pad.tick(&inputs);
        self.inputs = inputs;
        for (clicks, rotation) in self
            .knob_clicks
            .iter_mut()
            .zip([inputs.left_rotation, inputs.right_rotation])
        {
            *clicks += match rotation {
                Some(Rotation::Clockwise) => 1,
                Some(Rotation::CounterClockwise) => -1,
                None => 0,
            };
        }
        if reports != self.reports {
            self.reports = reports;
            self.host_log.push(HostEvent {
                at_ms: self.pad.view().activity.uptime_ms,
                reports,
            });
        }
    }

    pub fn wait(&mut self, ms: u32) {
        self.run(IDLE, ms);
    }

    /// Lets time pass without recording it: a cut in the film.
    pub fn skip(&mut self, ms: u32) {
        let was_recording = std::mem::replace(&mut self.recording, false);
        self.wait(ms);
        self.recording = was_recording;
    }

    pub fn hold_keys(&mut self, keys: u16, ms: u32) {
        self.run(Inputs { keys, ..IDLE }, ms);
    }

    /// Turns a knob by `steps` clicks while `held` stays as it is.
    pub fn turn(&mut self, knob: Knob, rotation: Rotation, steps: u32, held: Inputs) {
        let step = match knob {
            Knob::Left => Inputs {
                left_rotation: Some(rotation),
                ..held
            },
            Knob::Right => Inputs {
                right_rotation: Some(rotation),
                ..held
            },
        };
        for _ in 0..steps {
            self.run(step, 1);
            self.run(held, STEP_GAP_MS - 1);
        }
    }

    pub fn tap_left_knob(&mut self) {
        self.run(LEFT_HELD, 120);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_settled_session_is_on_the_main_screen_of_the_asked_layer() {
        for (layer_index, layer) in LAYERS.iter().enumerate() {
            let session = Session::settled_on(layer_index);
            assert_eq!(session.shot().screen, Screen::Main);
            assert_eq!(session.pad.view().layer().name, layer.name);
        }
    }

    #[test]
    fn recording_takes_one_frame_per_frame_period_and_skips_cuts() {
        let mut session = Session::new();
        session.wait(500);
        session.start_recording();
        session.wait(10 * FRAME_MS);
        session.skip(5000);
        session.wait(2 * FRAME_MS);
        assert_eq!(session.into_film().frames.len(), 12);
    }

    #[test]
    fn turning_a_knob_feeds_one_step_per_click() {
        let mut session = Session::settled_on(0);
        session.turn(Knob::Left, Rotation::Clockwise, 3, IDLE);
        session.turn(Knob::Right, Rotation::CounterClockwise, 2, IDLE);
        assert_eq!(session.pad.view().activity.knob.net_steps, -2);
        assert_eq!(session.shot().knob_clicks, [3, -2]);
    }

    #[test]
    fn the_host_log_has_one_entry_per_change_of_the_reports() {
        let mut session = Session::settled_on(1);
        session.hold_keys(1 << 3, 50);
        session.wait(50);
        let log = session.into_film().host_log;
        let copy = macropad_core::hid::Stroke::with(macropad_core::hid::modifier::CTRL, macropad_core::hid::key::C);
        assert_eq!(log.len(), 2);
        assert_eq!(log[0].reports.keyboard.to_bytes()[..3], [copy.modifiers, 0, copy.key]);
        assert_eq!(log[1].reports, Reports::default());
        assert_eq!(log[1].at_ms - log[0].at_ms, 50);
    }

    #[test]
    fn a_shot_shows_the_screen_as_it_arrives_in_the_panel() {
        let session = Session::settled_on(2);
        let view = session.pad.view();
        assert!(session.shot().display == view.screen(session.host));
    }
}
