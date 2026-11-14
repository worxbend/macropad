//! Why the chip last started, for the splash screen. A watchdog reboot loop shows there
//! without a debug probe.

/// The reset flags the chip keeps. The firmware reads them at start; see `fw/src/reset.rs`.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ResetFlags {
    /// The watchdog was not fed in time (WATCHDOG REASON.TIMER).
    pub watchdog_timeout: bool,
    /// Something triggered the watchdog on purpose, as a reboot does (WATCHDOG REASON.FORCE).
    pub watchdog_forced: bool,
    /// Power-on or brown-out reset (POWMAN CHIP_RESET.HAD_POR or HAD_BOR).
    pub power_on: bool,
    /// The RUN pin was pulled low (CHIP_RESET.HAD_RUN_LOW).
    pub run_pin: bool,
    /// A debugger asked for the reset (CHIP_RESET.HAD_DP_RESET_REQ, HAD_RESCUE or HAD_HZD_SYS_RESET_REQ).
    pub debugger: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ResetCause {
    PowerOn,
    ResetPin,
    Debugger,
    Watchdog,
    Restart,
    Unknown,
}

impl ResetCause {
    /// The watchdog's reason comes first. The RP2350 clears it on a hardware reset and on a
    /// debugger warm reset (datasheet text in rp-pac's WATCHDOG REASON), while a watchdog reset
    /// may leave the CHIP_RESET flags of the start before it set. The order of the CHIP_RESET
    /// flags among themselves is a guess until a board shows whether two can be set at once.
    pub const fn from_flags(flags: ResetFlags) -> Self {
        if flags.watchdog_timeout {
            Self::Watchdog
        } else if flags.watchdog_forced {
            Self::Restart
        } else if flags.debugger {
            Self::Debugger
        } else if flags.run_pin {
            Self::ResetPin
        } else if flags.power_on {
            Self::PowerOn
        } else {
            Self::Unknown
        }
    }

    /// Short enough for one line of the splash screen.
    pub const fn label(self) -> &'static str {
        match self {
            Self::PowerOn => "POWER-ON",
            Self::ResetPin => "RESET PIN",
            Self::Debugger => "DEBUGGER",
            Self::Watchdog => "WATCHDOG",
            Self::Restart => "RESTART",
            Self::Unknown => "UNKNOWN",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const NONE: ResetFlags = ResetFlags {
        watchdog_timeout: false,
        watchdog_forced: false,
        power_on: false,
        run_pin: false,
        debugger: false,
    };

    #[test]
    fn each_flag_on_its_own_names_its_cause() {
        let cases = [
            (ResetFlags { power_on: true, ..NONE }, ResetCause::PowerOn),
            (ResetFlags { run_pin: true, ..NONE }, ResetCause::ResetPin),
            (ResetFlags { debugger: true, ..NONE }, ResetCause::Debugger),
            (
                ResetFlags {
                    watchdog_timeout: true,
                    ..NONE
                },
                ResetCause::Watchdog,
            ),
            (
                ResetFlags {
                    watchdog_forced: true,
                    ..NONE
                },
                ResetCause::Restart,
            ),
            (NONE, ResetCause::Unknown),
        ];
        for (flags, cause) in cases {
            assert_eq!(ResetCause::from_flags(flags), cause, "{flags:?}");
        }
    }

    /// A watchdog reset may keep the power-on flag of the start before it, so the watchdog must win.
    #[test]
    fn a_watchdog_timeout_after_power_on_reads_as_watchdog() {
        let flags = ResetFlags {
            watchdog_timeout: true,
            power_on: true,
            ..NONE
        };
        assert_eq!(ResetCause::from_flags(flags), ResetCause::Watchdog);
    }
}
