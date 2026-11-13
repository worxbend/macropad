//! USB device: a boot keyboard (with lock LEDs) and a consumer-control interface.
//!
//! It also watches the bus state: while the host sleeps, the rest of the firmware goes dark.

use core::sync::atomic::Ordering;

use embassy_executor::Spawner;
use embassy_rp::peripherals::USB;
use embassy_rp::usb::Driver;
use embassy_rp::Peri;
use embassy_usb::class::hid::{
    self, HidBootProtocol, HidReader, HidReaderWriter, HidSubclass, HidWriter, ReportId, RequestHandler,
};
use embassy_usb::control::OutResponse;
use embassy_usb::{Builder, Handler, UsbDevice};
use macropad_core::engine::Reports;
use static_cell::StaticCell;

use crate::state::{HOST_ASLEEP, HOST_LOCKS, REPORTS};
use crate::Irqs;

/// pid.codes test IDs: fine for development on your own desk, not for a product that ships.
/// Request a real PID from https://pid.codes before distributing boards.
const VENDOR_ID: u16 = 0x1209;
const PRODUCT_ID: u16 = 0x0001;

const KEYBOARD_REPORT_BYTES: usize = 8;
const LOCK_REPORT_BYTES: usize = 1;
const CONSUMER_REPORT_BYTES: usize = 2;
const POLL_MS: u8 = 1;

/// Modifier byte, reserved byte, five lock LEDs out, six key slots covering every usage up to 0xFF.
#[rustfmt::skip]
const KEYBOARD_DESCRIPTOR: [u8; 65] = [
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01,
    0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
    0x95, 0x01, 0x75, 0x08, 0x81, 0x01,
    0x95, 0x05, 0x75, 0x01, 0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02,
    0x95, 0x01, 0x75, 0x03, 0x91, 0x01,
    0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x26, 0xFF, 0x00, 0x05, 0x07, 0x19, 0x00, 0x2A, 0xFF, 0x00, 0x81, 0x00,
    0xC0,
];

/// One 16-bit consumer usage, 0 when nothing is pressed.
#[rustfmt::skip]
const CONSUMER_DESCRIPTOR: [u8; 23] = [
    0x05, 0x0C, 0x09, 0x01, 0xA1, 0x01,
    0x15, 0x00, 0x26, 0xFF, 0x03, 0x19, 0x00, 0x2A, 0xFF, 0x03, 0x75, 0x10, 0x95, 0x01, 0x81, 0x00,
    0xC0,
];

type UsbDriver = Driver<'static, USB>;
type KeyboardWriter = HidWriter<'static, UsbDriver, KEYBOARD_REPORT_BYTES>;
type LockReader = HidReader<'static, UsbDriver, LOCK_REPORT_BYTES>;
type ConsumerWriter = HidWriter<'static, UsbDriver, CONSUMER_REPORT_BYTES>;

/// Stores the host's lock LED report, whichever pipe it arrives on.
struct LockLeds;

impl RequestHandler for LockLeds {
    fn set_report(&mut self, id: ReportId, report: &[u8]) -> OutResponse {
        match (id, report.first()) {
            (ReportId::Out(_), Some(&locks)) => {
                HOST_LOCKS.store(locks, Ordering::Relaxed);
                OutResponse::Accepted
            }
            _ => OutResponse::Rejected,
        }
    }
}

/// Follows what the host does to the bus.
struct BusWatcher;

impl Handler for BusWatcher {
    /// A suspended bus allows a device 2.5 mA, so the LEDs must go off while the host sleeps.
    fn suspended(&mut self, suspended: bool) {
        HOST_ASLEEP.store(suspended, Ordering::Relaxed);
    }

    /// After a bus reset the host is awake and will send its lock states again.
    fn reset(&mut self) {
        HOST_ASLEEP.store(false, Ordering::Relaxed);
        HOST_LOCKS.store(0, Ordering::Relaxed);
    }
}

/// Builds the USB device and starts its tasks.
pub fn start(spawner: Spawner, usb: Peri<'static, USB>) {
    static BUS_WATCHER: StaticCell<BusWatcher> = StaticCell::new();
    let mut builder = builder(Driver::new(usb, Irqs));
    builder.handler(BUS_WATCHER.init(BusWatcher));
    let (lock_reader, keyboard) = keyboard_interface(&mut builder);
    let consumer = consumer_interface(&mut builder);
    // Each task below is spawned exactly once, so its single-slot pool cannot be full.
    spawner.spawn(run_device(builder.build()).unwrap());
    spawner.spawn(read_lock_leds(lock_reader).unwrap());
    spawner.spawn(send_reports(keyboard, consumer).unwrap());
}

fn builder(driver: UsbDriver) -> Builder<'static, UsbDriver> {
    static CONFIG_DESCRIPTOR: StaticCell<[u8; 128]> = StaticCell::new();
    static BOS_DESCRIPTOR: StaticCell<[u8; 16]> = StaticCell::new();
    static CONTROL_BUFFER: StaticCell<[u8; 64]> = StaticCell::new();
    let mut config = embassy_usb::Config::new(VENDOR_ID, PRODUCT_ID);
    config.manufacturer = Some("worxbend");
    config.product = Some("macropad");
    config.max_power = 500;
    // No remote wakeup: embassy-rp 0.10's USB driver answers `remote_wakeup` with `Unsupported`,
    // so the descriptor must not promise it. A key press cannot wake a sleeping host.
    Builder::new(
        driver,
        config,
        CONFIG_DESCRIPTOR.init([0; 128]),
        BOS_DESCRIPTOR.init([0; 16]),
        &mut [],
        CONTROL_BUFFER.init([0; 64]),
    )
}

fn keyboard_interface(builder: &mut Builder<'static, UsbDriver>) -> (LockReader, KeyboardWriter) {
    static STATE: StaticCell<hid::State> = StaticCell::new();
    static CONTROL_PIPE_LOCKS: StaticCell<LockLeds> = StaticCell::new();
    let config = hid::Config {
        report_descriptor: &KEYBOARD_DESCRIPTOR,
        request_handler: Some(CONTROL_PIPE_LOCKS.init(LockLeds)),
        poll_ms: POLL_MS,
        max_packet_size: 8,
        hid_subclass: HidSubclass::Boot,
        hid_boot_protocol: HidBootProtocol::Keyboard,
    };
    HidReaderWriter::<_, LOCK_REPORT_BYTES, KEYBOARD_REPORT_BYTES>::new(builder, STATE.init(hid::State::new()), config)
        .split()
}

fn consumer_interface(builder: &mut Builder<'static, UsbDriver>) -> ConsumerWriter {
    static STATE: StaticCell<hid::State> = StaticCell::new();
    let config = hid::Config {
        report_descriptor: &CONSUMER_DESCRIPTOR,
        request_handler: None,
        poll_ms: POLL_MS,
        max_packet_size: 8,
        hid_subclass: HidSubclass::No,
        hid_boot_protocol: HidBootProtocol::None,
    };
    HidWriter::new(builder, STATE.init(hid::State::new()), config)
}

#[embassy_executor::task]
async fn run_device(mut device: UsbDevice<'static, UsbDriver>) -> ! {
    device.run().await
}

#[embassy_executor::task]
async fn read_lock_leds(reader: LockReader) -> ! {
    reader.run(false, &mut LockLeds).await
}

#[embassy_executor::task]
async fn send_reports(mut keyboard: KeyboardWriter, mut consumer: ConsumerWriter) -> ! {
    let mut sent = Reports::default();
    loop {
        let reports = REPORTS.wait().await;
        // A write fails only while the host is not listening (unplugged or suspended).
        // `sent` then stays behind, so the next change is written again in full.
        if reports.keyboard != sent.keyboard && keyboard.write(&reports.keyboard.to_bytes()).await.is_ok() {
            sent.keyboard = reports.keyboard;
        }
        if reports.consumer != sent.consumer && consumer.write(&reports.consumer.to_le_bytes()).await.is_ok() {
            sent.consumer = reports.consumer;
        }
    }
}
