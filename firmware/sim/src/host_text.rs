//! Readable names for what the pad sends, for the simulator's host readout.

use macropad_core::engine::Reports;
use macropad_core::hid::{consumer, key, modifier};

const NAMED_KEYS: [(u8, &str); 17] = [
    (key::ENTER, "ENTER"),
    (key::ESCAPE, "ESC"),
    (key::BACKSPACE, "BKSP"),
    (key::TAB, "TAB"),
    (key::SPACE, "SPACE"),
    (key::MINUS, "-"),
    (key::EQUAL, "="),
    (key::PERIOD, "."),
    (key::HOME, "HOME"),
    (key::PAGE_UP, "PGUP"),
    (key::DELETE, "DEL"),
    (key::END, "END"),
    (key::PAGE_DOWN, "PGDN"),
    (key::RIGHT, "RIGHT"),
    (key::LEFT, "LEFT"),
    (key::DOWN, "DOWN"),
    (key::UP, "UP"),
];

const NAMED_MEDIA: [(u16, &str); 9] = [
    (consumer::VOLUME_UP, "VOLUME UP"),
    (consumer::VOLUME_DOWN, "VOLUME DOWN"),
    (consumer::MUTE, "MUTE"),
    (consumer::PLAY_PAUSE, "PLAY/PAUSE"),
    (consumer::NEXT_TRACK, "NEXT TRACK"),
    (consumer::PREVIOUS_TRACK, "PREVIOUS TRACK"),
    (consumer::STOP, "STOP"),
    (consumer::BRIGHTNESS_UP, "BRIGHTNESS UP"),
    (consumer::BRIGHTNESS_DOWN, "BRIGHTNESS DOWN"),
];

const MODIFIER_NAMES: [(u8, &str); 4] = [
    (modifier::CTRL, "CTRL"),
    (modifier::SHIFT, "SHIFT"),
    (modifier::ALT, "ALT"),
    (modifier::GUI, "GUI"),
];

/// The key a usage code names on a US layout, or the code in hex.
pub fn key_name(code: u8) -> String {
    let run = |first: u8, names: &str| names.chars().nth(usize::from(code - first)).map(String::from);
    let named = NAMED_KEYS.iter().find(|(named_code, _)| *named_code == code);
    match (code, named) {
        (_, Some((_, name))) => (*name).to_owned(),
        (key::A..=key::Z, _) => run(key::A, "ABCDEFGHIJKLMNOPQRSTUVWXYZ").unwrap_or_default(),
        (key::N1..=key::N0, _) => run(key::N1, "1234567890").unwrap_or_default(),
        (key::F1..=key::F12, _) => format!("F{}", code - key::F1 + 1),
        (key::F13..=key::F24, _) => format!("F{}", code - key::F13 + 13),
        _ => format!("0X{code:02X}"),
    }
}

/// What a host would make of the two reports, for example `CTRL+Z` or `VOLUME UP`.
pub fn describe(reports: &Reports) -> String {
    let modifiers = MODIFIER_NAMES
        .iter()
        .filter(|(bit, _)| reports.keyboard.modifiers & bit != 0)
        .map(|(_, name)| (*name).to_owned());
    let keys = reports
        .keyboard
        .keys
        .iter()
        .filter(|code| **code != 0)
        .map(|code| key_name(*code));
    let keyboard = modifiers.chain(keys).collect::<Vec<_>>().join("+");
    let media = match NAMED_MEDIA.iter().find(|(usage, _)| *usage == reports.consumer) {
        Some((_, name)) => (*name).to_owned(),
        None if reports.consumer == 0 => String::new(),
        None => format!("MEDIA 0X{:04X}", reports.consumer),
    };
    let parts: Vec<String> = [keyboard, media].into_iter().filter(|part| !part.is_empty()).collect();
    if parts.is_empty() {
        "ALL RELEASED".to_owned()
    } else {
        parts.join(", ")
    }
}

/// Bytes as the host receives them, for example `01 00 1D 00`.
pub fn hex(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|byte| format!("{byte:02X}"))
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;
    use macropad_core::hid::Stroke;

    #[test]
    fn letters_digits_and_function_keys_are_named_from_their_code_runs() {
        assert_eq!(key_name(key::A), "A");
        assert_eq!(key_name(key::Z), "Z");
        assert_eq!(key_name(key::N1), "1");
        assert_eq!(key_name(key::N0), "0");
        assert_eq!(key_name(key::F12), "F12");
        assert_eq!(key_name(key::F13), "F13");
        assert_eq!(key_name(key::F24), "F24");
        assert_eq!(key_name(key::CAPS_LOCK), "0X39");
    }

    #[test]
    fn a_chord_reads_modifiers_first() {
        let mut reports = Reports::default();
        reports
            .keyboard
            .press(Stroke::with(modifier::CTRL | modifier::SHIFT, key::TAB));
        assert_eq!(describe(&reports), "CTRL+SHIFT+TAB");
    }

    #[test]
    fn media_and_keys_are_listed_side_by_side_and_nothing_reads_as_released() {
        let mut reports = Reports {
            consumer: consumer::VOLUME_UP,
            ..Reports::default()
        };
        assert_eq!(describe(&reports), "VOLUME UP");
        reports.keyboard.press(Stroke::plain(key::F13));
        assert_eq!(describe(&reports), "F13, VOLUME UP");
        reports.consumer = consumer::CALCULATOR;
        assert_eq!(describe(&reports), "F13, MEDIA 0X0192");
        assert_eq!(describe(&Reports::default()), "ALL RELEASED");
    }

    #[test]
    fn every_name_can_be_drawn_in_the_firmware_font() {
        let names = NAMED_KEYS.iter().map(|(_, name)| *name);
        let names = names.chain(NAMED_MEDIA.iter().map(|(_, name)| *name));
        for name in names.chain(MODIFIER_NAMES.iter().map(|(_, name)| *name)) {
            assert!(name.bytes().all(|byte| (0x20..0x60).contains(&byte)), "{name}");
        }
    }

    #[test]
    fn hex_separates_bytes_with_spaces() {
        assert_eq!(hex(&[0x01, 0x00, 0x1D]), "01 00 1D");
    }
}
