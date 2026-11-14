//! Hardware test mode, for a freshly built board: hold key K0 (top left) while plugging in.
//!
//! The display shows every contact as the pins read it, with no debouncing and no keymap. The
//! LEDs light one at a time, red, then green, then blue, so a wrong colour order or chain order
//! is plain to see. The pad sends nothing to the host. Unplug to leave.

use crate::debounce::DEBOUNCE_SAMPLES;
use crate::framebuffer::Framebuffer;
use crate::led::{self, LedFrame, Rgb, LED_COUNT};

/// Row-major from the top left, as `Inputs::keys`.
pub const ENTRY_KEY: usize = 0;
/// One-millisecond samples K0 must read closed at start.
pub const ENTRY_SAMPLES: usize = DEBOUNCE_SAMPLES as usize;
/// How long each LED shows each colour.
pub const LED_STEP_MS: u64 = 500;
/// Channel value of the lit LED: dim, so the test draws a few milliamps.
pub const LED_TEST_LEVEL: u8 = 32;

/// The test colours in the order they are shown, with the names the display gives them.
pub const LED_COLOURS: [(Rgb, &str); 3] = [
    (Rgb::new(LED_TEST_LEVEL, 0, 0), "RED"),
    (Rgb::new(0, LED_TEST_LEVEL, 0), "GREEN"),
    (Rgb::new(0, 0, LED_TEST_LEVEL), "BLUE"),
];

/// The three contacts of a knob. `true` is closed: the pin reads low.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct KnobContacts {
    pub a: bool,
    pub b: bool,
    pub switch: bool,
}

/// Every contact of the pad, undebounced. `true` is closed.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct RawInputs {
    /// Bit `n` is set while key `n` is closed.
    pub keys: u16,
    pub left: KnobContacts,
    pub right: KnobContacts,
}

/// True when K0 read closed in every one of the first samples after start.
pub fn requested(key_samples: &[u16; ENTRY_SAMPLES]) -> bool {
    key_samples.iter().all(|keys| keys & 1 << ENTRY_KEY != 0)
}

/// Which LED is lit, and in which of `LED_COLOURS`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct LedStep {
    pub led: usize,
    pub colour: usize,
}

impl LedStep {
    pub fn at(uptime_ms: u64) -> Self {
        let step = (uptime_ms / LED_STEP_MS) as usize % (LED_COUNT * LED_COLOURS.len());
        Self {
            led: step / LED_COLOURS.len(),
            colour: step % LED_COLOURS.len(),
        }
    }

    pub fn colour_name(self) -> &'static str {
        LED_COLOURS[self.colour].1
    }
}

/// The test mode's state machine: one tick per millisecond, like `Pad`.
#[derive(Default)]
pub struct HardwareTest {
    uptime_ms: u64,
    raw: RawInputs,
}

impl HardwareTest {
    pub fn tick(&mut self, raw: RawInputs) {
        self.raw = raw;
        self.uptime_ms += 1;
    }

    pub fn view(&self) -> TestView {
        TestView {
            raw: self.raw,
            uptime_ms: self.uptime_ms,
        }
    }
}

/// A snapshot of the test mode for the display and the LEDs.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct TestView {
    pub raw: RawInputs,
    pub uptime_ms: u64,
}

impl TestView {
    pub fn led_step(&self) -> LedStep {
        LedStep::at(self.uptime_ms)
    }

    pub fn screen(&self) -> Framebuffer {
        crate::ui::draw_hardware_test(self)
    }

    pub fn leds(&self) -> LedFrame {
        let step = self.led_step();
        let mut frame = [Rgb::BLACK; LED_COUNT];
        frame[step.led] = LED_COLOURS[step.colour].0;
        led::within_current_budget(frame)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::led::{estimated_current_ma, CURRENT_BUDGET_MA};

    #[test]
    fn k0_held_through_every_entry_sample_starts_the_test() {
        assert!(requested(&[0b1; ENTRY_SAMPLES]));
        assert!(requested(&[0b1111_1111_1111; ENTRY_SAMPLES]));
    }

    #[test]
    fn k0_missing_from_any_entry_sample_starts_the_pad_as_usual() {
        assert!(!requested(&[0; ENTRY_SAMPLES]));
        assert!(!requested(&[0b10; ENTRY_SAMPLES]));
        let mut bounced = [0b1; ENTRY_SAMPLES];
        bounced[ENTRY_SAMPLES - 1] = 0;
        assert!(!requested(&bounced));
    }

    #[test]
    fn the_leds_step_through_red_green_blue_one_led_at_a_time_in_chain_order() {
        let order: Vec<(usize, &str)> = (0..LED_COUNT as u64 * 3)
            .map(|step| LedStep::at(step * LED_STEP_MS))
            .map(|step| (step.led, step.colour_name()))
            .collect();
        assert_eq!(&order[..4], [(0, "RED"), (0, "GREEN"), (0, "BLUE"), (1, "RED")]);
        assert_eq!(order.last(), Some(&(LED_COUNT - 1, "BLUE")));
        assert_eq!(
            LedStep::at(LED_COUNT as u64 * 3 * LED_STEP_MS),
            LedStep { led: 0, colour: 0 }
        );
    }

    #[test]
    fn exactly_one_led_is_lit_in_the_named_colour() {
        let view = TestView {
            uptime_ms: 4 * LED_STEP_MS + 1,
            ..TestView::default()
        };
        let frame = view.leds();
        assert_eq!(view.led_step(), LedStep { led: 1, colour: 1 });
        assert_eq!(frame[1], Rgb::new(0, LED_TEST_LEVEL, 0));
        assert_eq!(frame.iter().filter(|&&led| led != Rgb::BLACK).count(), 1);
    }

    #[test]
    fn the_test_light_stays_far_inside_the_current_cap_and_is_never_dimmed() {
        for step in 0..LED_COUNT as u64 * 3 {
            let view = TestView {
                uptime_ms: step * LED_STEP_MS,
                ..TestView::default()
            };
            let frame = view.leds();
            assert_eq!(frame[view.led_step().led], LED_COLOURS[view.led_step().colour].0);
            assert!(estimated_current_ma(&frame) * 10 < CURRENT_BUDGET_MA);
        }
    }

    #[test]
    fn the_state_machine_keeps_the_newest_contacts_and_counts_milliseconds() {
        let mut test = HardwareTest::default();
        let pressed = RawInputs {
            keys: 0b100,
            left: KnobContacts {
                a: true,
                ..KnobContacts::default()
            },
            ..RawInputs::default()
        };
        test.tick(RawInputs::default());
        test.tick(pressed);
        assert_eq!(
            test.view(),
            TestView {
                raw: pressed,
                uptime_ms: 2
            }
        );
    }
}
