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
use embassy_rp::watchdog::Watchdog;
use embassy_rp::{bind_interrupts, dma, pio, rom_data};
use embassy_time::{Duration, Ticker, Timer};
use macropad_core::engine::Reports;
use macropad_core::keymap::LAYERS;
use macropad_core::pad::Pad;
// A panic stops the scan loop, so the watchdog below restarts the pad half a second later.
use panic_halt as _;

use crate::board::Board;
use crate::inputs::Scanner;
use crate::state::{publish, REPORTS};

bind_interrupts!(struct Irqs {
    USBCTRL_IRQ => embassy_rp::usb::InterruptHandler<USB>;
    PIO0_IRQ_0 => pio::InterruptHandler<PIO0>;
    DMA_IRQ_0 => dma::InterruptHandler<DMA_CH0>, dma::InterruptHandler<DMA_CH1>;
});

const SCAN_PERIOD: Duration = Duration::from_millis(1);
/// If the scan loop stops for this long, the chip restarts. Without this, a hung pad would
/// leave its last key report "held down" on the host until someone pulls the cable.
const WATCHDOG_TIMEOUT: Duration = Duration::from_millis(500);
/// Before the pad restarts as a USB drive: time for the host to see every key released, for
/// the display to take the "flash mode" picture and for the LEDs to go dark.
/// Must stay well below `WATCHDOG_TIMEOUT`.
const FAREWELL: Duration = Duration::from_millis(150);

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let board = Board::take(embassy_rp::init(Default::default()));
    usb::start(spawner, board.usb);
    // Each task is spawned exactly once, so its single-slot pool cannot be full.
    spawner.spawn(display::run(board.display).unwrap());
    spawner.spawn(leds::run(board.leds).unwrap());
    let mut watchdog = Watchdog::new(board.watchdog);
    watchdog.pause_on_debug(true);
    watchdog.start(WATCHDOG_TIMEOUT);
    scan_forever(Scanner::new(board.keys, board.left_knob, board.right_knob), watchdog).await
}

async fn scan_forever(mut scanner: Scanner, mut watchdog: Watchdog) -> ! {
    let mut pad = Pad::new(&LAYERS);
    let mut published = Reports::default();
    let mut ticker = Ticker::every(SCAN_PERIOD);
    loop {
        watchdog.feed(WATCHDOG_TIMEOUT);
        let reports = pad.tick(&scanner.sample());
        let view = pad.view();
        publish(view);
        if view.flash_requested {
            restart_as_usb_drive().await;
        }
        if reports != published {
            REPORTS.signal(reports);
            published = reports;
        }
        ticker.next().await;
    }
}

/// Both knobs were held: restart in the boot ROM's USB drive mode, which accepts a UF2 file.
async fn restart_as_usb_drive() -> ! {
    REPORTS.signal(Reports::default());
    Timer::after(FAREWELL).await;
    rom_data::reset_to_usb_boot(0, 0);
    // The ROM call restarts the chip a few milliseconds later. If it ever did not, the
    // watchdog would, because nothing feeds it any more.
    loop {
        core::hint::spin_loop();
    }
}
