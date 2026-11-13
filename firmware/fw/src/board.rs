//! Pin map of the board. `board.toml` at the repository root is the source of truth;
//! `tools/check_pins.py` fails when this file disagrees with it.

use embassy_rp::gpio::{AnyPin, Input, Pull};
use embassy_rp::peripherals::{DMA_CH0, DMA_CH1, PIN_22, PIN_23, PIN_24, PIN_9, PIO0, SPI0, USB, WATCHDOG};
use embassy_rp::{Peri, Peripherals};
use macropad_core::keymap::KEY_COUNT;
use macropad_core::quadrature::Detents;
use macropad_core::sharp_lcd::Orientation;

/// Change to `Rotated180` if the picture is upside down on your module.
pub const DISPLAY_ORIENTATION: Orientation = Orientation::Normal;

/// The Alps EC11E18244AU has 36 detents and 18 pulses per turn: two clicks per electrical cycle.
/// `tools/check_pins.py` fails when this disagrees with the encoder part in `board.toml`.
pub const KNOB_DETENTS: Detents = Detents::PerHalfCycle;

pub struct Knob {
    pub a: Input<'static>,
    pub b: Input<'static>,
    pub switch: Input<'static>,
}

pub struct DisplayPins {
    pub spi: Peri<'static, SPI0>,
    pub sck: Peri<'static, PIN_22>,
    pub mosi: Peri<'static, PIN_23>,
    pub cs: Peri<'static, PIN_24>,
    pub dma: Peri<'static, DMA_CH1>,
}

pub struct LedPins {
    pub pio: Peri<'static, PIO0>,
    pub data: Peri<'static, PIN_9>,
    pub dma: Peri<'static, DMA_CH0>,
}

pub struct Board {
    /// Row-major from the top-left key.
    pub keys: [Input<'static>; KEY_COUNT],
    pub left_knob: Knob,
    pub right_knob: Knob,
    pub display: DisplayPins,
    pub leds: LedPins,
    pub usb: Peri<'static, USB>,
    pub watchdog: Peri<'static, WATCHDOG>,
}

impl Board {
    /// Every switch and encoder contact closes to ground, so all inputs are pulled up.
    #[rustfmt::skip]
    pub fn take(p: Peripherals) -> Self {
        let pulled_up = |pin: Peri<'static, AnyPin>| Input::new(pin, Pull::Up);
        Self {
            keys: [
                pulled_up(p.PIN_21.into()), pulled_up(p.PIN_20.into()), pulled_up(p.PIN_4.into()), pulled_up(p.PIN_3.into()),
                pulled_up(p.PIN_19.into()), pulled_up(p.PIN_18.into()), pulled_up(p.PIN_6.into()), pulled_up(p.PIN_5.into()),
                pulled_up(p.PIN_17.into()), pulled_up(p.PIN_16.into()), pulled_up(p.PIN_8.into()), pulled_up(p.PIN_7.into()),
            ],
            left_knob: Knob { a: pulled_up(p.PIN_27.into()), b: pulled_up(p.PIN_28.into()), switch: pulled_up(p.PIN_29.into()) },
            right_knob: Knob { a: pulled_up(p.PIN_0.into()), b: pulled_up(p.PIN_1.into()), switch: pulled_up(p.PIN_2.into()) },
            display: DisplayPins { spi: p.SPI0, sck: p.PIN_22, mosi: p.PIN_23, cs: p.PIN_24, dma: p.DMA_CH1 },
            leds: LedPins { pio: p.PIO0, data: p.PIN_9, dma: p.DMA_CH0 },
            usb: p.USB,
            watchdog: p.WATCHDOG,
        }
    }
}
