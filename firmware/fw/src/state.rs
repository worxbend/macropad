//! State shared between the scan loop and the USB, display and LED tasks.

use core::cell::Cell;
use core::sync::atomic::{AtomicBool, AtomicU8, Ordering};

use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::signal::Signal;
use macropad_core::engine::Reports;
use macropad_core::hid::lock;
use macropad_core::keymap::LAYERS;
use macropad_core::pad::{Host, View};

/// The newest HID reports. Only the latest matters: reports are states, not events.
pub static REPORTS: Signal<CriticalSectionRawMutex, Reports> = Signal::new();

/// The host's keyboard LED report (num lock, caps lock, ...).
pub static HOST_LOCKS: AtomicU8 = AtomicU8::new(0);
/// Set while the host has suspended the USB bus.
pub static HOST_ASLEEP: AtomicBool = AtomicBool::new(false);

/// What the USB tasks last heard from the host.
pub fn host() -> Host {
    let locks = HOST_LOCKS.load(Ordering::Relaxed);
    Host {
        caps_lock: locks & lock::CAPS != 0,
        num_lock: locks & lock::NUM != 0,
        asleep: HOST_ASLEEP.load(Ordering::Relaxed),
    }
}

/// What the scan loop last saw, for the display and the LEDs.
static VIEW: Mutex<CriticalSectionRawMutex, Cell<View>> = Mutex::new(Cell::new(View::at_power_on(&LAYERS)));

pub fn publish(view: View) {
    VIEW.lock(|shared| shared.set(view));
}

pub fn view() -> View {
    VIEW.lock(Cell::get)
}
