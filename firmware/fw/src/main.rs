//! Macropad firmware for the RP2354A.
//!
//! The scan loop below runs every millisecond; USB, the display and the LEDs are separate tasks
//! that read what it publishes.
#![no_std]
#![no_main]

mod board;
mod display;
mod inputs;
mod leds;
mod state;
mod usb;

use embassy_executor::Spawner;
use embassy_rp::peripherals::{DMA_CH0, DMA_CH1, PIO0, USB};
use embassy_rp::{bind_interrupts, dma, pio, rom_data};
use embassy_time::{Duration, Ticker};
use macropad_core::engine::{Engine, Reports};
use macropad_core::keymap::LAYERS;
use macropad_core::kps::KpsMeter;
use panic_halt as _;

use crate::board::Board;
use crate::inputs::Scanner;
use crate::state::{publish, Snapshot, REPORTS};

bind_interrupts!(struct Irqs {
    USBCTRL_IRQ => embassy_rp::usb::InterruptHandler<USB>;
    PIO0_IRQ_0 => pio::InterruptHandler<PIO0>;
    DMA_IRQ_0 => dma::InterruptHandler<DMA_CH0>, dma::InterruptHandler<DMA_CH1>;
});

const SCAN_PERIOD: Duration = Duration::from_millis(1);

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let board = Board::take(embassy_rp::init(Default::default()));
    usb::start(spawner, board.usb);
    // Each task is spawned exactly once, so its single-slot pool cannot be full.
    spawner.spawn(display::run(board.display).unwrap());
    spawner.spawn(leds::run(board.leds).unwrap());
    scan_forever(Scanner::new(board.keys, board.left_knob, board.right_knob)).await
}

async fn scan_forever(mut scanner: Scanner) -> ! {
    let mut engine = Engine::new(&LAYERS);
    let mut kps = KpsMeter::default();
    let mut published = Reports::default();
    let mut ticker = Ticker::every(SCAN_PERIOD);
    loop {
        let reports = engine.tick(&scanner.sample());
        kps.tick(engine.presses_this_tick());
        if engine.bootloader_requested() {
            // Both knobs were held: restart as a USB drive that accepts a UF2 file.
            rom_data::reset_to_usb_boot(0, 0);
        }
        if reports != published {
            REPORTS.signal(reports);
            published = reports;
        }
        publish(Snapshot {
            layer: engine.layer(),
            pressed_keys: engine.pressed_keys(),
            kps_history: kps.history(),
        });
        ticker.next().await;
    }
}
