//! Drives the eight side LEDs with the active layer's colour and effect.

use embassy_rp::pio::Pio;
use embassy_rp::pio_programs::ws2812::{Grb, PioWs2812, PioWs2812Program};
use embassy_time::{Duration, Instant, Ticker};
use macropad_core::led::{render, within_current_budget, Rgb, LED_COUNT};
use smart_leds::RGB8;

use crate::board::LedPins;
use crate::state::snapshot;
use crate::Irqs;

const FRAME_PERIOD: Duration = Duration::from_millis(20);

#[embassy_executor::task]
pub async fn run(pins: LedPins) {
    let Pio { mut common, sm0, .. } = Pio::new(pins.pio, Irqs);
    let program = PioWs2812Program::new(&mut common);
    // SK6812 takes the same 800 kHz signal as WS2812, green byte first.
    let mut chain: PioWs2812<'_, _, 0, LED_COUNT, Grb> =
        PioWs2812::new(&mut common, sm0, pins.dma, Irqs, pins.data, &program);
    let started = Instant::now();
    let mut ticker = Ticker::every(FRAME_PERIOD);
    loop {
        let layer = snapshot().layer;
        // Effects are periodic, so the millisecond counter may wrap.
        let time_ms = started.elapsed().as_millis() as u32;
        let frame = within_current_budget(render(layer.effect, layer.color, time_ms));
        chain.write(&frame.map(|Rgb { r, g, b }| RGB8 { r, g, b })).await;
        ticker.next().await;
    }
}
