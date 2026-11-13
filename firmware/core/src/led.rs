//! Colours and base effects for the eight side LEDs, and the cap that keeps them inside the
//! USB power budget. What the pad adds on top (ripples, fades, dimming) is in `lighting`.

pub const LED_COUNT: usize = 8;
pub type LedFrame = [Rgb; LED_COUNT];

/// Supply current the LED chain may draw. The pad is a 500 mA USB device and the
/// 3.3 V rail needs its share, so the LEDs get well under half.
pub const CURRENT_BUDGET_MA: u32 = 200;
/// Worst-case current of one colour channel at full brightness (5050-class figure,
/// deliberately above the side-emitting part's typical 12 mA).
const CHANNEL_FULL_MA: u32 = 20;
/// Current of one LED's controller with all channels off.
const IDLE_MA_PER_LED: u32 = 1;

/// Brightness steps the user can pick; `MAX_LEVEL` is full brightness, 0 is off.
pub const MAX_LEVEL: u8 = 8;

/// Time between two frames sent to the chain.
pub const FRAME_PERIOD_MS: u32 = 20;
/// One frame on the wire: 24 bits per LED at 1.25 us per bit.
const FRAME_ON_WIRE_US: u32 = LED_COUNT as u32 * 24 * 5 / 4;
/// The longest latch (reset) gap any SK6812 SIDE datasheet revision asks for.
const LATCH_GAP_US: u32 = 200;
const _: () = assert!(
    FRAME_PERIOD_MS * 1000 >= FRAME_ON_WIRE_US + LATCH_GAP_US,
    "the data line must rest long enough between frames for the LEDs to latch"
);

const BREATH_PERIOD_MS: u32 = 4000;
const BREATH_FLOOR: u32 = 24;
const RAINBOW_PERIOD_MS: u32 = 5120;
const WAVE_PERIOD_MS: u32 = 2400;
const WAVE_FLOOR: u32 = 40;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

impl Rgb {
    pub const BLACK: Self = Self::new(0, 0, 0);
    pub const WHITE: Self = Self::new(255, 255, 255);

    pub const fn new(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b }
    }

    /// The colour `amount`/255 of the way from `self` to `toward`.
    pub fn mixed(self, toward: Self, amount: u8) -> Self {
        let amount = u32::from(amount);
        let mix = |from: u8, to: u8| ((u32::from(from) * (255 - amount) + u32::from(to) * amount) / 255) as u8;
        Self::new(mix(self.r, toward.r), mix(self.g, toward.g), mix(self.b, toward.b))
    }

    /// The colour at `numerator`/`denominator` of its brightness. The fraction must not exceed 1.
    pub fn scaled(self, numerator: u32, denominator: u32) -> Self {
        let scale = |channel: u8| (u32::from(channel) * numerator / denominator) as u8;
        Self::new(scale(self.r), scale(self.g), scale(self.b))
    }

    fn channel_sum(self) -> u32 {
        u32::from(self.r) + u32::from(self.g) + u32::from(self.b)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Effect {
    Solid,
    Breathing,
    Rainbow,
    /// A bright spot of the layer colour that runs around the pad.
    Wave,
}

/// The frame an effect shows at `time_ms`, before current limiting.
pub fn render(effect: Effect, color: Rgb, time_ms: u32) -> LedFrame {
    match effect {
        Effect::Solid => [color; LED_COUNT],
        Effect::Breathing => [color.scaled(breath_level(time_ms), 255); LED_COUNT],
        Effect::Rainbow => core::array::from_fn(|led| rainbow_color(led, time_ms)),
        Effect::Wave => core::array::from_fn(|led| color.scaled(wave_level(led, time_ms), 255)),
    }
}

/// Triangle wave between `WAVE_FLOOR` and 255, one crest spread over the whole chain.
fn wave_level(led: usize, time_ms: u32) -> u32 {
    let turn = (time_ms % WAVE_PERIOD_MS) * 256 / WAVE_PERIOD_MS;
    let spread = (led * 256 / LED_COUNT) as u32;
    let phase = (turn + 256 - spread) % 256;
    let rising = if phase < 128 { phase } else { 256 - phase };
    WAVE_FLOOR + rising * (255 - WAVE_FLOOR) / 128
}

/// Triangle wave between `BREATH_FLOOR` and 255.
fn breath_level(time_ms: u32) -> u32 {
    let half_period = BREATH_PERIOD_MS / 2;
    let phase = time_ms % BREATH_PERIOD_MS;
    let rising = if phase < half_period {
        phase
    } else {
        BREATH_PERIOD_MS - phase
    };
    BREATH_FLOOR + rising * (255 - BREATH_FLOOR) / half_period
}

fn rainbow_color(led: usize, time_ms: u32) -> Rgb {
    let turn = (time_ms % RAINBOW_PERIOD_MS) * 256 / RAINBOW_PERIOD_MS;
    let spread = (led * 256 / LED_COUNT) as u32;
    color_wheel(((turn + spread) % 256) as u8)
}

/// Red -> green -> blue -> red over 0..=255, always at full saturation.
fn color_wheel(position: u8) -> Rgb {
    match position {
        0..=84 => Rgb::new(255 - position * 3, position * 3, 0),
        85..=169 => Rgb::new(0, 255 - (position - 85) * 3, (position - 85) * 3),
        _ => Rgb::new((position - 170) * 3, 0, 255 - (position - 170) * 3),
    }
}

/// Estimated supply current of a frame.
pub fn estimated_current_ma(frame: &LedFrame) -> u32 {
    let channel_sum: u32 = frame.iter().map(|led| led.channel_sum()).sum();
    LED_COUNT as u32 * IDLE_MA_PER_LED + (channel_sum * CHANNEL_FULL_MA).div_ceil(255)
}

/// The same frame, dimmed evenly if it would draw more than `CURRENT_BUDGET_MA`.
pub fn within_current_budget(frame: LedFrame) -> LedFrame {
    if estimated_current_ma(&frame) <= CURRENT_BUDGET_MA {
        return frame;
    }
    let light_budget_ma = CURRENT_BUDGET_MA - LED_COUNT as u32 * IDLE_MA_PER_LED;
    let channel_sum: u32 = frame.iter().map(|led| led.channel_sum()).sum();
    let allowed_channel_sum = light_budget_ma * 255 / CHANNEL_FULL_MA;
    frame.map(|led| led.scaled(allowed_channel_sum, channel_sum))
}

#[cfg(test)]
mod tests {
    use super::*;

    const WHITE: Rgb = Rgb::WHITE;

    #[test]
    fn full_white_is_dimmed_to_the_budget() {
        let capped = within_current_budget([WHITE; LED_COUNT]);
        assert!(estimated_current_ma(&capped) <= CURRENT_BUDGET_MA);
        assert!(capped[0].r > 0, "dimmed, not switched off");
    }

    #[test]
    fn a_frame_inside_the_budget_is_unchanged() {
        let dim = [Rgb::new(40, 10, 60); LED_COUNT];
        assert_eq!(within_current_budget(dim), dim);
    }

    #[test]
    fn dimming_keeps_the_colour_ratio() {
        let capped = within_current_budget([Rgb::new(255, 255, 0); LED_COUNT]);
        assert_eq!(capped[0].r, capped[0].g);
        assert_eq!(capped[0].b, 0);
    }

    #[test]
    fn no_effect_ever_exceeds_the_budget_after_capping() {
        for effect in [Effect::Solid, Effect::Breathing, Effect::Rainbow, Effect::Wave] {
            for time_ms in (0..10_000).step_by(37) {
                let capped = within_current_budget(render(effect, WHITE, time_ms));
                assert!(
                    estimated_current_ma(&capped) <= CURRENT_BUDGET_MA,
                    "{effect:?} at {time_ms}"
                );
            }
        }
    }

    #[test]
    fn solid_shows_the_layer_colour_on_every_led() {
        let color = Rgb::new(1, 2, 3);
        assert_eq!(render(Effect::Solid, color, 1234), [color; LED_COUNT]);
    }

    #[test]
    fn breathing_peaks_at_half_period_and_never_goes_dark() {
        let dimmest = render(Effect::Breathing, WHITE, 0)[0];
        let brightest = render(Effect::Breathing, WHITE, BREATH_PERIOD_MS / 2)[0];
        assert_eq!(brightest, WHITE);
        assert_eq!(dimmest, Rgb::new(24, 24, 24));
    }

    #[test]
    fn rainbow_gives_each_led_a_different_hue() {
        let frame = render(Effect::Rainbow, WHITE, 0);
        assert_eq!(frame[0], Rgb::new(255, 0, 0));
        assert!(frame
            .iter()
            .all(|led| frame.iter().filter(|other| *other == led).count() == 1));
    }

    #[test]
    fn color_wheel_is_continuous_at_segment_borders() {
        assert_eq!(color_wheel(84), Rgb::new(3, 252, 0));
        assert_eq!(color_wheel(85), Rgb::new(0, 255, 0));
        assert_eq!(color_wheel(170), Rgb::new(0, 0, 255));
        assert_eq!(color_wheel(255), Rgb::new(255, 0, 0));
    }

    #[test]
    fn mixing_runs_from_one_colour_to_the_other() {
        let (from, to) = (Rgb::new(10, 200, 0), Rgb::new(250, 0, 0));
        assert_eq!(from.mixed(to, 0), from);
        assert_eq!(from.mixed(to, 255), to);
        assert_eq!(Rgb::BLACK.mixed(WHITE, 128), Rgb::new(128, 128, 128));
    }

    #[test]
    fn the_wave_has_one_crest_that_moves_along_the_chain() {
        let brightest = |time_ms| {
            let frame = render(Effect::Wave, WHITE, time_ms);
            (0..LED_COUNT).max_by_key(|&led| frame[led].r).unwrap()
        };
        assert_eq!(brightest(WAVE_PERIOD_MS / 2), 0);
        assert_eq!(brightest(WAVE_PERIOD_MS / 2 + WAVE_PERIOD_MS / 4), 2);
        let frame = render(Effect::Wave, WHITE, 0);
        assert!(frame.iter().all(|led| u32::from(led.r) >= WAVE_FLOOR));
    }
}
