//! State shared between the scan loop and the USB, display and LED tasks.

use core::cell::Cell;
use core::sync::atomic::{AtomicU8, Ordering};

use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::signal::Signal;
use macropad_core::engine::Reports;
use macropad_core::hid::lock;
use macropad_core::keymap::{Layer, LAYERS};
use macropad_core::kps::HISTORY_BUCKETS;
use macropad_core::ui::UiState;

/// The newest HID reports. Only the latest matters: reports are states, not events.
pub static REPORTS: Signal<CriticalSectionRawMutex, Reports> = Signal::new();

/// The host's keyboard LED report (num lock, caps lock, ...).
pub static HOST_LOCKS: AtomicU8 = AtomicU8::new(0);

/// What the scan loop last saw, for the display and the LEDs.
#[derive(Clone, Copy)]
pub struct Snapshot {
    pub layer: &'static Layer,
    pub pressed_keys: u16,
    pub kps_history: [u8; HISTORY_BUCKETS],
}

impl Snapshot {
    pub fn ui_state(&self) -> UiState<'static> {
        let locks = HOST_LOCKS.load(Ordering::Relaxed);
        UiState {
            layer: self.layer,
            pressed_keys: self.pressed_keys,
            kps_history: self.kps_history,
            caps_lock: locks & lock::CAPS != 0,
            num_lock: locks & lock::NUM != 0,
        }
    }
}

static SNAPSHOT: Mutex<CriticalSectionRawMutex, Cell<Snapshot>> = Mutex::new(Cell::new(Snapshot {
    layer: &LAYERS[0],
    pressed_keys: 0,
    kps_history: [0; HISTORY_BUCKETS],
}));

pub fn publish(snapshot: Snapshot) {
    SNAPSHOT.lock(|shared| shared.set(snapshot));
}

pub fn snapshot() -> Snapshot {
    SNAPSHOT.lock(Cell::get)
}
