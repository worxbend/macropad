//! Refreshes the nice!view thirty times a second.

use embassy_rp::gpio::{Level, Output};
use embassy_rp::peripherals::SPI0;
use embassy_rp::spi::{Async, Config, Spi};
use embassy_time::{Duration, Ticker, Timer};
use macropad_core::sharp_lcd::FrameEncoder;

use crate::board::{DisplayPins, DISPLAY_ORIENTATION};
use crate::log::info;
use crate::state::{host, shown};
use crate::Irqs;

/// The panel's limit. One frame is 1498 bytes, so it takes 12 ms on the wire.
const SPI_HZ: u32 = 1_000_000;
/// Fast enough for the animations. The panel's VCOM bit must also flip at least once a second;
/// every frame flips it.
const FRAME_PERIOD: Duration = Duration::from_millis(33);
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
    send(&mut spi, &mut select, &encoder.encode(&shown().screen(host()))).await;
    info!("display: first frame sent");
    loop {
        ticker.next().await;
        send(&mut spi, &mut select, &encoder.encode(&shown().screen(host()))).await;
    }
}

async fn send(spi: &mut Spi<'static, SPI0, Async>, select: &mut Output<'static>, bytes: &[u8]) {
    select.set_high();
    Timer::after_micros(SELECT_SETUP_US).await;
    spi.write(bytes).await.expect("embassy-rp's spi::Error has no variants");
    Timer::after_micros(SELECT_HOLD_US).await;
    select.set_low();
}
