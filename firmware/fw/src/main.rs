//! Macropad firmware for the RP2354A.
//!
//! The scan loop below runs every millisecond; USB, the display and the LEDs are separate tasks
//! that read what it publishes. Key K0 held at start runs the hardware test mode instead.
#![no_std]
#![no_main]

mod board;
mod display;
mod inputs;
mod leds;
mod log;
mod reset;
mod state;
mod usb;

use embassy_executor::Spawner;
use embassy_rp::peripherals::{DMA_CH0, DMA_CH1, PIO0, USB};
use embassy_rp::watchdog::Watchdog;
use embassy_rp::{bind_interrupts, dma, pio, rom_data};
use embassy_time::{Duration, Ticker, Timer};
use macropad_core::engine::Reports;
use macropad_core::hardware_test::{self, HardwareTest, ENTRY_SAMPLES};
use macropad_core::keymap::LAYERS;
use macropad_core::pad::Pad;
use macropad_core::reset::ResetCause;
// A probe build logs over RTT and prints a panic there before it halts.
#[cfg(feature = "probe")]
use {defmt_rtt as _, panic_probe as _};
// A panic stops the scan loop, so the watchdog below restarts the pad half a second later.
#[cfg(not(feature = "probe"))]
use panic_halt as _;

use crate::board::Board;
use crate::inputs::Scanner;
use crate::log::info;
use crate::state::{publish, Shown, REPORTS};

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
    info!("boot: macropad firmware {=str}", env!("CARGO_PKG_VERSION"));
    let mut watchdog = Watchdog::new(board.watchdog);
    let reset_cause = reset::cause(&watchdog);
    info!("boot: reset cause {=str}", reset_cause.label());
    let scanner = Scanner::new(board.keys, board.left_knob, board.right_knob);
    let test_requested = hardware_test_requested(&scanner).await;
    // Each task is spawned exactly once, so its single-slot pool cannot be full.
    spawner.spawn(display::run(board.display).unwrap());
    spawner.spawn(leds::run(board.leds).unwrap());
    watchdog.pause_on_debug(true);
    watchdog.start(WATCHDOG_TIMEOUT);
    if test_requested {
        info!("boot: hardware test mode");
        test_forever(scanner, watchdog).await
    }
    usb::start(spawner, board.usb);
    scan_forever(scanner, watchdog, reset_cause).await
}

/// Key K0 read closed in each of the first few milliseconds.
async fn hardware_test_requested(scanner: &Scanner) -> bool {
    let mut key_samples = [0; ENTRY_SAMPLES];
    for sample in &mut key_samples {
        Timer::after(SCAN_PERIOD).await;
        *sample = scanner.raw().keys;
    }
    hardware_test::requested(&key_samples)
}

async fn scan_forever(mut scanner: Scanner, mut watchdog: Watchdog, reset_cause: ResetCause) -> ! {
    let mut pad = Pad::after_reset(&LAYERS, reset_cause);
    let mut published = Reports::default();
    let mut ticker = Ticker::every(SCAN_PERIOD);
    loop {
        watchdog.feed(WATCHDOG_TIMEOUT);
        let reports = pad.tick(&scanner.sample());
        let view = pad.view();
        publish(Shown::Pad(view));
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

/// The hardware test mode: no USB, the raw contacts on the display, the LEDs one by one.
/// It ends when the pad is unplugged.
async fn test_forever(scanner: Scanner, mut watchdog: Watchdog) -> ! {
    let mut test = HardwareTest::default();
    let mut ticker = Ticker::every(SCAN_PERIOD);
    loop {
        watchdog.feed(WATCHDOG_TIMEOUT);
        test.tick(scanner.raw());
        publish(Shown::HardwareTest(test.view()));
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
