//! Log lines for a debug probe. With the `probe` feature they go out over RTT with defmt;
//! without it `info!` compiles to nothing and evaluates nothing.

#[cfg(feature = "probe")]
macro_rules! info {
    ($($argument:tt)*) => {
        defmt::info!($($argument)*)
    };
}

/// Takes a reference to each argument so a value used only in a log line is not "unused".
#[cfg(not(feature = "probe"))]
macro_rules! info {
    ($format:literal $(, $argument:expr)* $(,)?) => {{
        $(let _ = &$argument;)*
    }};
}

pub(crate) use info;
