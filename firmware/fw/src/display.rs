//! Refreshes the nice!view ten times a second.

use embassy_rp::gpio::{Level, Output};
use embassy_rp::spi::{Config, Spi};
use embassy_time::{Duration, Ticker, Timer};
use macropad_core::sharp_lcd::FrameEncoder;
use macropad_core::ui;

use crate::board::{DisplayPins, DISPLAY_ORIENTATION};
use crate::state::snapshot;
use crate::Irqs;

/// The panel's limit. Its VCOM bit must also flip at least once a second; every frame flips it.
const SPI_HZ: u32 = 1_000_000;
const FRAME_PERIOD: Duration = Duration::from_millis(100);
/// Chip-select setup and hold times from the panel datasheet, rounded up.
const SELECT_SETUP_US: u64 = 6;
const SELECT_HOLD_US: u64 = 2;

#[embassy_executor::task]
pub async fn run(pins: DisplayPins) {
    let mut config = Config::default();
    config.frequency = SPI_HZ;
    let mut spi = Spi::new_txonly(pins.spi, pins.sck, pins.mosi, pins.dma, Irqs, config);
    // This panel's chip select is active high.
    let mut select = Output::new(pins.cs, Level::Low);
    let mut encoder = FrameEncoder::new(DISPLAY_ORIENTATION);
    let mut ticker = Ticker::every(FRAME_PERIOD);
    loop {
        let bytes = encoder.encode(&ui::draw(&snapshot().ui_state()));
        select.set_high();
        Timer::after_micros(SELECT_SETUP_US).await;
        spi.write(&bytes)
            .await
            .expect("embassy-rp's spi::Error has no variants");
        Timer::after_micros(SELECT_HOLD_US).await;
        select.set_low();
        ticker.next().await;
    }
}
