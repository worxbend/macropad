//! USB HID report contents and the usage codes the keymap uses.

/// Keys a boot-protocol keyboard report can hold at once.
pub const ROLLOVER: usize = 6;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct KeyboardReport {
    pub modifiers: u8,
    pub keys: [u8; ROLLOVER],
}

impl KeyboardReport {
    /// The boot-keyboard input report: modifiers, a reserved byte, six key slots.
    pub fn to_bytes(self) -> [u8; 2 + ROLLOVER] {
        let mut bytes = [0; 2 + ROLLOVER];
        bytes[0] = self.modifiers;
        bytes[2..].copy_from_slice(&self.keys);
        bytes
    }

    /// Adds a key. A seventh simultaneous key is left out: the boot report has no room for it.
    pub fn press(&mut self, stroke: Stroke) {
        self.modifiers |= stroke.modifiers;
        if self.keys.contains(&stroke.key) {
            return;
        }
        if let Some(free_slot) = self.keys.iter_mut().find(|slot| **slot == 0) {
            *free_slot = stroke.key;
        }
    }
}

/// One key with the modifiers held while it is down.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Stroke {
    pub modifiers: u8,
    pub key: u8,
}

impl Stroke {
    pub const fn plain(key: u8) -> Self {
        Self { modifiers: 0, key }
    }

    pub const fn with(modifiers: u8, key: u8) -> Self {
        Self { modifiers, key }
    }

    /// Modifiers with no key, for the hold half of a tap-hold key.
    pub const fn modifiers(modifiers: u8) -> Self {
        Self { modifiers, key: 0 }
    }

    /// A key together with modifiers. Its modifiers would also apply to any other key in the
    /// same report, which is why the engine lets a chord go when a newer stroke arrives.
    pub const fn is_chord(self) -> bool {
        self.modifiers != 0 && self.key != 0
    }
}

/// Bits of the host's keyboard LED output report.
pub mod lock {
    pub const NUM: u8 = 0x01;
    pub const CAPS: u8 = 0x02;
}

pub mod modifier {
    pub const CTRL: u8 = 0x01;
    pub const SHIFT: u8 = 0x02;
    pub const ALT: u8 = 0x04;
    /// The Windows, Command or Super key.
    pub const GUI: u8 = 0x08;
}

/// Keyboard/Keypad usage page (0x07). Codes name the key's position on a US layout.
pub mod key {
    pub const A: u8 = 0x04;
    pub const B: u8 = 0x05;
    pub const C: u8 = 0x06;
    pub const D: u8 = 0x07;
    pub const E: u8 = 0x08;
    pub const F: u8 = 0x09;
    pub const G: u8 = 0x0A;
    pub const H: u8 = 0x0B;
    pub const I: u8 = 0x0C;
    pub const J: u8 = 0x0D;
    pub const K: u8 = 0x0E;
    pub const L: u8 = 0x0F;
    pub const M: u8 = 0x10;
    pub const N: u8 = 0x11;
    pub const O: u8 = 0x12;
    pub const P: u8 = 0x13;
    pub const Q: u8 = 0x14;
    pub const R: u8 = 0x15;
    pub const S: u8 = 0x16;
    pub const T: u8 = 0x17;
    pub const U: u8 = 0x18;
    pub const V: u8 = 0x19;
    pub const W: u8 = 0x1A;
    pub const X: u8 = 0x1B;
    pub const Y: u8 = 0x1C;
    pub const Z: u8 = 0x1D;
    pub const N1: u8 = 0x1E;
    pub const N2: u8 = 0x1F;
    pub const N3: u8 = 0x20;
    pub const N4: u8 = 0x21;
    pub const N5: u8 = 0x22;
    pub const N6: u8 = 0x23;
    pub const N7: u8 = 0x24;
    pub const N8: u8 = 0x25;
    pub const N9: u8 = 0x26;
    pub const N0: u8 = 0x27;
    pub const ENTER: u8 = 0x28;
    pub const ESCAPE: u8 = 0x29;
    pub const BACKSPACE: u8 = 0x2A;
    pub const TAB: u8 = 0x2B;
    pub const SPACE: u8 = 0x2C;
    pub const MINUS: u8 = 0x2D;
    pub const EQUAL: u8 = 0x2E;
    pub const LEFT_BRACKET: u8 = 0x2F;
    pub const RIGHT_BRACKET: u8 = 0x30;
    pub const BACKSLASH: u8 = 0x31;
    pub const SEMICOLON: u8 = 0x33;
    pub const QUOTE: u8 = 0x34;
    pub const GRAVE: u8 = 0x35;
    pub const COMMA: u8 = 0x36;
    pub const PERIOD: u8 = 0x37;
    pub const SLASH: u8 = 0x38;
    pub const CAPS_LOCK: u8 = 0x39;
    pub const F1: u8 = 0x3A;
    pub const F2: u8 = 0x3B;
    pub const F3: u8 = 0x3C;
    pub const F4: u8 = 0x3D;
    pub const F5: u8 = 0x3E;
    pub const F6: u8 = 0x3F;
    pub const F7: u8 = 0x40;
    pub const F8: u8 = 0x41;
    pub const F9: u8 = 0x42;
    pub const F10: u8 = 0x43;
    pub const F11: u8 = 0x44;
    pub const F12: u8 = 0x45;
    pub const PRINT_SCREEN: u8 = 0x46;
    pub const SCROLL_LOCK: u8 = 0x47;
    pub const PAUSE: u8 = 0x48;
    pub const INSERT: u8 = 0x49;
    pub const HOME: u8 = 0x4A;
    pub const PAGE_UP: u8 = 0x4B;
    pub const DELETE: u8 = 0x4C;
    pub const END: u8 = 0x4D;
    pub const PAGE_DOWN: u8 = 0x4E;
    pub const RIGHT: u8 = 0x4F;
    pub const LEFT: u8 = 0x50;
    pub const DOWN: u8 = 0x51;
    pub const UP: u8 = 0x52;
    pub const NUM_LOCK: u8 = 0x53;
    pub const KEYPAD_SLASH: u8 = 0x54;
    pub const KEYPAD_ASTERISK: u8 = 0x55;
    pub const KEYPAD_MINUS: u8 = 0x56;
    pub const KEYPAD_PLUS: u8 = 0x57;
    pub const KEYPAD_ENTER: u8 = 0x58;
    pub const MENU: u8 = 0x65;
    pub const F13: u8 = 0x68;
    pub const F14: u8 = 0x69;
    pub const F15: u8 = 0x6A;
    pub const F16: u8 = 0x6B;
    pub const F17: u8 = 0x6C;
    pub const F18: u8 = 0x6D;
    pub const F19: u8 = 0x6E;
    pub const F20: u8 = 0x6F;
    pub const F21: u8 = 0x70;
    pub const F22: u8 = 0x71;
    pub const F23: u8 = 0x72;
    pub const F24: u8 = 0x73;
}

/// Consumer usage page (0x0C). The report descriptor accepts usages up to 0x03FF.
pub mod consumer {
    pub const BRIGHTNESS_UP: u16 = 0x006F;
    pub const BRIGHTNESS_DOWN: u16 = 0x0070;
    pub const NEXT_TRACK: u16 = 0x00B5;
    pub const PREVIOUS_TRACK: u16 = 0x00B6;
    pub const STOP: u16 = 0x00B7;
    pub const PLAY_PAUSE: u16 = 0x00CD;
    pub const MUTE: u16 = 0x00E2;
    pub const VOLUME_UP: u16 = 0x00E9;
    pub const VOLUME_DOWN: u16 = 0x00EA;
    pub const MEDIA_PLAYER: u16 = 0x0183;
    pub const MAIL: u16 = 0x018A;
    pub const CALCULATOR: u16 = 0x0192;
    pub const FILE_BROWSER: u16 = 0x0194;
    pub const BROWSER_SEARCH: u16 = 0x0221;
    pub const BROWSER_HOME: u16 = 0x0223;
    pub const BROWSER_BACK: u16 = 0x0224;
    pub const BROWSER_FORWARD: u16 = 0x0225;
    pub const BROWSER_REFRESH: u16 = 0x0227;
    /// Highest usage the consumer report descriptor declares.
    pub const MAX_USAGE: u16 = 0x03FF;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn press_merges_modifiers_and_fills_slots_in_order() {
        let mut report = KeyboardReport::default();
        report.press(Stroke::with(modifier::CTRL, key::C));
        report.press(Stroke::with(modifier::SHIFT, key::V));
        assert_eq!(report.modifiers, modifier::CTRL | modifier::SHIFT);
        assert_eq!(report.keys, [key::C, key::V, 0, 0, 0, 0]);
    }

    #[test]
    fn press_of_a_key_already_down_takes_no_second_slot() {
        let mut report = KeyboardReport::default();
        report.press(Stroke::plain(key::A));
        report.press(Stroke::plain(key::A));
        assert_eq!(report.keys, [key::A, 0, 0, 0, 0, 0]);
    }

    #[test]
    fn report_bytes_keep_the_reserved_byte_zero() {
        let mut report = KeyboardReport::default();
        report.press(Stroke::with(modifier::ALT, key::F13));
        assert_eq!(report.to_bytes(), [modifier::ALT, 0, key::F13, 0, 0, 0, 0, 0]);
    }

    #[test]
    fn seventh_key_is_left_out() {
        let mut report = KeyboardReport::default();
        for key in key::N1..=key::N7 {
            report.press(Stroke::plain(key));
        }
        assert_eq!(report.keys, [key::N1, key::N2, key::N3, key::N4, key::N5, key::N6]);
    }

    /// Spot checks against the HID Usage Tables, one per generated run of codes.
    #[test]
    fn generated_code_runs_land_on_the_documented_usages() {
        assert_eq!((key::A, key::Z), (0x04, 0x1D));
        assert_eq!((key::F1, key::F12), (0x3A, 0x45));
        assert_eq!((key::F13, key::F24), (0x68, 0x73));
    }
}
