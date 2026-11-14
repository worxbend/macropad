//! Reads why the chip last started.

use embassy_rp::pac::POWMAN;
use embassy_rp::watchdog::{ResetReason, Watchdog};
use macropad_core::reset::{ResetCause, ResetFlags};

/// Read before the watchdog is started. The register names are those of the RP2350 datasheet,
/// as rp-pac 7 spells them.
pub fn cause(watchdog: &Watchdog) -> ResetCause {
    let chip = POWMAN.chip_reset().read();
    let watchdog_reason = watchdog.reset_reason();
    ResetCause::from_flags(ResetFlags {
        watchdog_timeout: watchdog_reason == Some(ResetReason::TimedOut),
        watchdog_forced: watchdog_reason == Some(ResetReason::Forced),
        power_on: chip.had_por() || chip.had_bor(),
        run_pin: chip.had_run_low(),
        debugger: chip.had_dp_reset_req() || chip.had_rescue() || chip.had_hzd_sys_reset_req(),
    })
}
