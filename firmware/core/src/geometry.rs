//! Where the keys and the side LEDs sit on the PCB, for effects that travel across the pad.
//!
//! Copied from `board.toml` in micrometres; `tools/check_pins.py` fails when they disagree.
//! Origin: top-left corner of the PCB seen from the key side. Y grows toward the front.

use crate::keymap::KEY_COUNT;
use crate::led::LED_COUNT;

pub const KEY_COLUMNS: usize = 4;
pub const KEY_FIRST_X_UM: i32 = 13_425;
pub const KEY_FIRST_Y_UM: i32 = 32_000;
pub const KEY_PITCH_UM: i32 = 19_050;

/// In chain order: right side back to front, then left side front to back.
/// Seen from above, the chain therefore runs clockwise around the pad.
pub const LED_POSITIONS_UM: [(i32, i32); LED_COUNT] = [
    (83_200, 30_000),
    (83_200, 43_500),
    (83_200, 57_000),
    (83_200, 70_500),
    (800, 70_500),
    (800, 57_000),
    (800, 43_500),
    (800, 30_000),
];

const UM_PER_TENTH_MM: i32 = 100;

fn key_position_um(key: usize) -> (i32, i32) {
    debug_assert!(key < KEY_COUNT);
    let (column, row) = ((key % KEY_COLUMNS) as i32, (key / KEY_COLUMNS) as i32);
    (
        KEY_FIRST_X_UM + column * KEY_PITCH_UM,
        KEY_FIRST_Y_UM + row * KEY_PITCH_UM,
    )
}

/// Straight-line distance from a key centre to an LED, in tenths of a millimetre.
pub fn key_to_led_tenth_mm(key: usize, led: usize) -> u32 {
    let (key_x, key_y) = key_position_um(key);
    let (led_x, led_y) = LED_POSITIONS_UM[led];
    let dx = ((key_x - led_x) / UM_PER_TENTH_MM).unsigned_abs();
    let dy = ((key_y - led_y) / UM_PER_TENTH_MM).unsigned_abs();
    (dx * dx + dy * dy).isqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_top_right_key_is_nearest_to_the_first_led() {
        let nearest = (0..LED_COUNT).min_by_key(|&led| key_to_led_tenth_mm(3, led));
        assert_eq!(nearest, Some(0));
    }

    #[test]
    fn the_bottom_left_key_is_nearest_to_the_front_left_led() {
        let nearest = (0..LED_COUNT).min_by_key(|&led| key_to_led_tenth_mm(8, led));
        assert_eq!(nearest, Some(4));
    }

    #[test]
    fn distances_are_in_tenths_of_a_millimetre() {
        // Key 0 is at (13.425, 32.0), LED 7 at (0.8, 30.0): 12.78 mm apart.
        assert_eq!(key_to_led_tenth_mm(0, 7), 127);
    }
}
