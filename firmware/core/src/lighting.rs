//! What the side LEDs show: the layer's effect, plus feedback for what the user just did.
//!
//! Order of the stages matters. Highlights are added first, then the whole frame is capped to
//! the current budget, and only then dimmed, so no user setting can push it over the budget.

use crate::activity::{Activity, IDLE_AFTER_MS};
use crate::geometry::key_to_led_tenth_mm;
use crate::keymap::Layer;
use crate::led::{render, within_current_budget, LedFrame, Rgb, LED_COUNT, MAX_LEVEL};

/// A new layer's colours fade in over this time.
pub const LAYER_FADE_MS: u16 = 300;
/// At power-on the LEDs come on one after another, this far apart.
const BOOT_STEP_MS: u64 = 120;
/// A key press sends a ring of light outward at this speed, in 0.1 mm per millisecond.
const RIPPLE_SPEED: u32 = 2;
const RIPPLE_MS: u32 = 600;
/// Half the width of the ring of light, in 0.1 mm.
const RIPPLE_HALF_WIDTH: u32 = 150;
/// A knob step lights one LED, which then fades over this time.
const COMET_MS: u32 = 500;
const COMET_NEIGHBOUR_SHARE: u32 = 4;
/// While caps lock is on, the two LEDs at the back corners (the ends of the chain) turn this
/// far toward white, so the lock shows without a look at the display.
const CAPS_LOCK_STRENGTH: u8 = 170;
const BACK_CORNER_LEDS: [usize; 2] = [0, LED_COUNT - 1];
/// Once idle, the LEDs fade to `IDLE_LEVEL`/255 over `IDLE_FADE_MS`.
const IDLE_FADE_MS: u32 = 2000;
const IDLE_LEVEL: u32 = 48;

/// Everything that decides one LED frame.
pub struct Lighting<'a> {
    pub layer: &'a Layer,
    pub previous_layer: &'a Layer,
    pub activity: &'a Activity,
    /// User brightness, 0 to `MAX_LEVEL`.
    pub level: u8,
    /// The host's caps lock is on.
    pub caps_lock: bool,
    /// The host sleeps or the pad is about to restart: a USB device must then go dark.
    pub lights_out: bool,
}

/// The frame to send to the chain. It never exceeds the current budget.
pub fn frame(lighting: &Lighting) -> LedFrame {
    if lighting.lights_out {
        return [Rgb::BLACK; LED_COUNT];
    }
    let activity = lighting.activity;
    let lit: LedFrame = core::array::from_fn(|led| {
        if !switched_on_at_boot(led, activity.uptime_ms) {
            return Rgb::BLACK;
        }
        let feedback = ripple_strength(led, activity).max(comet_strength(led, activity));
        let highlight = feedback.max(caps_lock_strength(led, lighting.caps_lock));
        layer_color(lighting, led).mixed(Rgb::WHITE, highlight)
    });
    let dimming = idle_level(activity.idle_ms) * u32::from(lighting.level.min(MAX_LEVEL));
    within_current_budget(lit).map(|led| led.scaled(dimming, 255 * u32::from(MAX_LEVEL)))
}

fn switched_on_at_boot(led: usize, uptime_ms: u64) -> bool {
    uptime_ms >= (led as u64 + 1) * BOOT_STEP_MS
}

/// The layer's effect, cross-faded from the previous layer's just after a change.
fn layer_color(lighting: &Lighting, led: usize) -> Rgb {
    let activity = lighting.activity;
    // Effects are periodic, so dropping the high bits of the uptime only costs one jump in 49 days.
    let time_ms = activity.uptime_ms as u32;
    let now = render(lighting.layer.effect, lighting.layer.color, time_ms)[led];
    if activity.layer_age_ms >= LAYER_FADE_MS {
        return now;
    }
    let before = render(lighting.previous_layer.effect, lighting.previous_layer.color, time_ms)[led];
    before.mixed(now, fraction_255(activity.layer_age_ms.into(), LAYER_FADE_MS.into()))
}

/// 0..=255: how strongly the rings from recent key presses light this LED.
fn ripple_strength(led: usize, activity: &Activity) -> u8 {
    let strongest = activity
        .key_age_ms
        .iter()
        .enumerate()
        .filter(|&(_, &age_ms)| u32::from(age_ms) < RIPPLE_MS)
        .map(|(key, &age_ms)| ring_strength(key_to_led_tenth_mm(key, led), age_ms.into()))
        .max();
    strongest.unwrap_or(0)
}

/// Brightness of a ring that started `age_ms` ago, seen `distance` (0.1 mm) from its centre.
fn ring_strength(distance: u32, age_ms: u32) -> u8 {
    let off_ring = distance.abs_diff(age_ms * RIPPLE_SPEED);
    if off_ring >= RIPPLE_HALF_WIDTH {
        return 0;
    }
    let sharpness = fraction_255(RIPPLE_HALF_WIDTH - off_ring, RIPPLE_HALF_WIDTH);
    let fade = fraction_255(RIPPLE_MS - age_ms, RIPPLE_MS);
    (u32::from(sharpness) * u32::from(fade) / 255) as u8
}

/// 0..=255: the LED the knob points at glows, its two neighbours a little.
fn comet_strength(led: usize, activity: &Activity) -> u8 {
    let age_ms = u32::from(activity.knob.age_ms);
    if age_ms >= COMET_MS {
        return 0;
    }
    let head = u32::from(fraction_255(COMET_MS - age_ms, COMET_MS));
    let steps_away = led.abs_diff(usize::from(activity.ring_position));
    match steps_away.min(LED_COUNT - steps_away) {
        0 => head as u8,
        1 => (head / COMET_NEIGHBOUR_SHARE) as u8,
        _ => 0,
    }
}

fn caps_lock_strength(led: usize, caps_lock: bool) -> u8 {
    if caps_lock && BACK_CORNER_LEDS.contains(&led) {
        CAPS_LOCK_STRENGTH
    } else {
        0
    }
}

/// 255 while in use, falling to `IDLE_LEVEL` once the pad has been idle for `IDLE_AFTER_MS`.
fn idle_level(idle_ms: u32) -> u32 {
    let fading_ms = idle_ms.saturating_sub(IDLE_AFTER_MS).min(IDLE_FADE_MS);
    255 - (255 - IDLE_LEVEL) * fading_ms / IDLE_FADE_MS
}

/// `part`/`whole` on a 0..=255 scale. `part` must not exceed `whole`.
fn fraction_255(part: u32, whole: u32) -> u8 {
    debug_assert!(part <= whole && whole > 0);
    (part * 255 / whole) as u8
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::activity::KnobTurn;
    use crate::keymap::LAYERS;
    use crate::led::{estimated_current_ma, Effect, CURRENT_BUDGET_MA};

    const AFTER_BOOT_MS: u64 = 5_000;
    const TEAL: Rgb = Rgb::new(0, 200, 255);
    const GREEN: Rgb = Rgb::new(40, 255, 80);

    /// A layer that shows one steady colour, so the tests do not depend on the keymap's choices.
    fn solid(color: Rgb) -> Layer {
        Layer {
            name: "TEST",
            color,
            effect: Effect::Solid,
            keys: LAYERS[0].keys,
            left_knob: LAYERS[0].left_knob,
            right_knob: LAYERS[0].right_knob,
            right_knob_press: LAYERS[0].right_knob_press,
        }
    }

    fn settled() -> Activity {
        Activity {
            uptime_ms: AFTER_BOOT_MS,
            ..Activity::new()
        }
    }

    fn frame_between(previous_layer: &Layer, layer: &Layer, activity: &Activity) -> LedFrame {
        frame(&Lighting {
            layer,
            previous_layer,
            activity,
            level: MAX_LEVEL,
            caps_lock: false,
            lights_out: false,
        })
    }

    /// The frame on a steady teal layer.
    fn frame_of(activity: &Activity, level: u8) -> LedFrame {
        frame(&Lighting {
            layer: &solid(TEAL),
            previous_layer: &solid(TEAL),
            activity,
            level,
            caps_lock: false,
            lights_out: false,
        })
    }

    fn brightness(led: Rgb) -> u32 {
        u32::from(led.r) + u32::from(led.g) + u32::from(led.b)
    }

    #[test]
    fn a_settled_solid_layer_is_the_capped_layer_colour() {
        let frame = frame_of(&settled(), MAX_LEVEL);
        assert_eq!(frame, within_current_budget([TEAL; LED_COUNT]));
    }

    #[test]
    fn nothing_the_user_can_do_exceeds_the_current_budget() {
        for layer_index in 0..LAYERS.len() {
            for age_ms in (0..600).step_by(7) {
                let activity = Activity {
                    layer_age_ms: age_ms,
                    key_age_ms: [age_ms; 12],
                    knob: KnobTurn {
                        age_ms,
                        ..settled().knob
                    },
                    uptime_ms: AFTER_BOOT_MS + u64::from(age_ms) * 13,
                    ..settled()
                };
                let previous_layer = &LAYERS[(layer_index + 1) % LAYERS.len()];
                let lit = frame(&Lighting {
                    layer: &LAYERS[layer_index],
                    previous_layer,
                    activity: &activity,
                    level: MAX_LEVEL,
                    caps_lock: true,
                    lights_out: false,
                });
                let current_ma = estimated_current_ma(&lit);
                assert!(current_ma <= CURRENT_BUDGET_MA, "layer {layer_index} at {age_ms} ms");
            }
        }
    }

    #[test]
    fn a_key_press_lights_the_nearest_led_first_and_the_far_side_later() {
        let pressed_top_right = |age_ms| {
            let mut activity = settled();
            activity.key_age_ms[3] = age_ms;
            frame_of(&activity, MAX_LEVEL)
        };
        let calm = frame_of(&settled(), MAX_LEVEL);
        let early = pressed_top_right(30);
        assert!(early[0].r > calm[0].r, "the LED next to the key turns whiter");
        assert!(early[0].r > early[7].r, "the far side has not been reached yet");
        let late = pressed_top_right(340);
        assert!(late[7].r > late[0].r, "the ring has crossed the pad");
        assert_eq!(pressed_top_right(RIPPLE_MS as u16), calm);
    }

    #[test]
    fn a_knob_step_lights_the_led_it_points_at_and_fades() {
        let turned = |age_ms| Activity {
            ring_position: 5,
            knob: KnobTurn {
                age_ms,
                ..settled().knob
            },
            ..settled()
        };
        let fresh = frame_of(&turned(0), MAX_LEVEL);
        assert!(fresh[5].r > fresh[4].r && fresh[4].r > fresh[2].r);
        assert_eq!(fresh[4], fresh[6]);
        assert_eq!(
            frame_of(&turned(COMET_MS as u16), MAX_LEVEL),
            frame_of(&settled(), MAX_LEVEL)
        );
    }

    #[test]
    fn the_comet_wraps_around_the_end_of_the_chain() {
        let activity = Activity {
            ring_position: 0,
            knob: KnobTurn {
                age_ms: 0,
                ..settled().knob
            },
            ..settled()
        };
        let frame = frame_of(&activity, MAX_LEVEL);
        assert_eq!(frame[1], frame[LED_COUNT - 1]);
        assert!(frame[1].r > frame[2].r);
    }

    #[test]
    fn a_layer_change_fades_from_the_old_colours_to_the_new() {
        let changed = |age_ms| {
            let activity = Activity {
                layer_age_ms: age_ms,
                ..settled()
            };
            frame_between(&solid(GREEN), &solid(TEAL), &activity)
        };
        let old = within_current_budget([GREEN; LED_COUNT]);
        let new = within_current_budget([TEAL; LED_COUNT]);
        assert_eq!(changed(0), old);
        let halfway = changed(LAYER_FADE_MS / 2)[0];
        assert!(halfway.g < old[0].g && halfway.g > new[0].g);
        assert_eq!(changed(LAYER_FADE_MS), new);
    }

    #[test]
    fn the_brightness_level_scales_the_frame_down_to_off() {
        let full = frame_of(&settled(), MAX_LEVEL);
        let half = frame_of(&settled(), MAX_LEVEL / 2);
        assert_eq!(brightness(half[0]), brightness(full[0]) / 2);
        assert_eq!(frame_of(&settled(), 0), [Rgb::BLACK; LED_COUNT]);
    }

    #[test]
    fn an_idle_pad_dims_but_stays_lit() {
        let idle_for = |idle_ms| Activity { idle_ms, ..settled() };
        let awake = frame_of(&idle_for(IDLE_AFTER_MS), MAX_LEVEL);
        let dimmed = frame_of(&idle_for(IDLE_AFTER_MS + IDLE_FADE_MS), MAX_LEVEL);
        assert_eq!(awake, frame_of(&settled(), MAX_LEVEL));
        assert!(brightness(dimmed[0]) < brightness(awake[0]) / 4);
        assert!(brightness(dimmed[0]) > 0);
        assert_eq!(frame_of(&idle_for(u32::MAX), MAX_LEVEL), dimmed);
    }

    #[test]
    fn the_leds_come_on_one_by_one_at_power_on() {
        let at = |uptime_ms| {
            let activity = Activity {
                uptime_ms,
                ..Activity::new()
            };
            frame_of(&activity, MAX_LEVEL)
                .iter()
                .filter(|led| **led != Rgb::BLACK)
                .count()
        };
        assert_eq!(at(0), 0);
        assert_eq!(at(BOOT_STEP_MS), 1);
        assert_eq!(at(BOOT_STEP_MS * 8), LED_COUNT);
    }

    #[test]
    fn caps_lock_whitens_the_two_back_corner_leds_only() {
        let activity = settled();
        let with_caps = |caps_lock| {
            frame(&Lighting {
                layer: &solid(TEAL),
                previous_layer: &solid(TEAL),
                activity: &activity,
                level: MAX_LEVEL,
                caps_lock,
                lights_out: false,
            })
        };
        let (off, on) = (with_caps(false), with_caps(true));
        // The cap dims the whole frame a little when two LEDs get whiter, so compare red shares.
        for led in BACK_CORNER_LEDS {
            assert!(on[led].r > off[led].r + 50, "LED {led} gains red on its way to white");
        }
        assert!((1..LED_COUNT - 1).all(|led| on[led].r <= off[led].r));
        assert!(estimated_current_ma(&on) <= CURRENT_BUDGET_MA);
    }

    #[test]
    fn the_back_corner_leds_are_the_ones_nearest_the_back_edge() {
        use crate::geometry::LED_POSITIONS_UM;
        let back_edge_y = LED_POSITIONS_UM.iter().map(|(_, y)| *y).min();
        for led in BACK_CORNER_LEDS {
            assert_eq!(Some(LED_POSITIONS_UM[led].1), back_edge_y);
        }
    }

    #[test]
    fn lights_out_is_completely_dark() {
        let activity = settled();
        let dark = frame(&Lighting {
            layer: &solid(TEAL),
            previous_layer: &solid(TEAL),
            activity: &activity,
            level: MAX_LEVEL,
            caps_lock: false,
            lights_out: true,
        });
        assert_eq!(dark, [Rgb::BLACK; LED_COUNT]);
    }
}
