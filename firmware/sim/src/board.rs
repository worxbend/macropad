//! Where the parts sit that only the simulator draws. Copied from `board.toml` in micrometres;
//! `tools/check_pins.py` fails when they disagree. Key and LED positions come from
//! `macropad_core::geometry`, which the same check covers.

pub const BOARD_WIDTH_UM: i32 = 84_000;
pub const BOARD_HEIGHT_UM: i32 = 82_500;
pub const LEFT_KNOB_UM: (i32, i32) = (13_425, 11_000);
pub const RIGHT_KNOB_UM: (i32, i32) = (70_575, 11_000);
/// Centre of the display's visible glass.
pub const DISPLAY_WINDOW_UM: (i32, i32) = (43_500, 11_000);
/// Clicks per turn of the knobs (EC11E18244AU).
pub const KNOB_DETENTS_PER_TURN: i32 = 36;

/// Not in `board.toml`, picture only: a common 1u keycap and a guess at the knob cap.
pub const KEYCAP_UM: i32 = 17_500;
pub const KNOB_CAP_DIAMETER_UM: i32 = 15_000;
