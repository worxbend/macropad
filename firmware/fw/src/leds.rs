//! Drives the eight side LEDs with whatever `macropad_core::lighting` decides.

use embassy_rp::pio::Pio;
use embassy_rp::pio_programs::ws2812::{Grb, PioWs2812, PioWs2812Program};
use embassy_time::{Duration, Ticker};
use macropad_core::led::{LedFrame, Rgb, FRAME_PERIOD_MS, LED_COUNT};
use smart_leds::RGB8;

use crate::board::LedPins;
use crate::log::info;
use crate::state::{host, shown};
use crate::Irqs;

#[embassy_executor::task]
pub async fn run(pins: LedPins) {
    let Pio { mut common, sm0, .. } = Pio::new(pins.pio, Irqs);
    let program = PioWs2812Program::new(&mut common);
    // SK6812 takes the same 800 kHz signal as WS2812, green byte first. The driver's bit timing
    // (0.25 us high for a 0, 0.875 us high for a 1, 1.25 us per bit) is inside the SK6812 SIDE
    // datasheet windows; see the timing table in the firmware README.
    let mut chain: PioWs2812<'_, _, 0, LED_COUNT, Grb> =
        PioWs2812::new(&mut common, sm0, pins.dma, Irqs, pins.data, &program);
    let mut ticker = Ticker::every(Duration::from_millis(FRAME_PERIOD_MS.into()));
    chain.write(&wire_colours(shown().leds(host()))).await;
    info!("leds: first frame sent");
    loop {
        ticker.next().await;
        chain.write(&wire_colours(shown().leds(host()))).await;
    }
}

fn wire_colours(frame: LedFrame) -> [RGB8; LED_COUNT] {
    frame.map(|Rgb { r, g, b }| RGB8 { r, g, b })
}
