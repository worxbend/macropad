//! Typing-rate history for the display's sparkline.

/// Bars in the sparkline.
pub const HISTORY_BUCKETS: usize = 32;
/// Time one bar covers.
pub const BUCKET_MS: u16 = 250;

#[derive(Clone, Copy)]
pub struct KpsMeter {
    /// Key presses per bucket, oldest first; the last entry is still filling.
    history: [u8; HISTORY_BUCKETS],
    bucket_age_ms: u16,
}

impl Default for KpsMeter {
    fn default() -> Self {
        Self {
            history: [0; HISTORY_BUCKETS],
            bucket_age_ms: 0,
        }
    }
}

impl KpsMeter {
    /// Advances time by one millisecond and counts the presses that happened in it.
    pub fn tick(&mut self, presses: u8) {
        let newest = &mut self.history[HISTORY_BUCKETS - 1];
        *newest = newest.saturating_add(presses);
        self.bucket_age_ms += 1;
        if self.bucket_age_ms == BUCKET_MS {
            self.bucket_age_ms = 0;
            self.history.rotate_left(1);
            self.history[HISTORY_BUCKETS - 1] = 0;
        }
    }

    pub fn history(&self) -> [u8; HISTORY_BUCKETS] {
        self.history
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn presses_land_in_the_newest_bucket() {
        let mut meter = KpsMeter::default();
        meter.tick(2);
        meter.tick(1);
        assert_eq!(meter.history()[HISTORY_BUCKETS - 1], 3);
    }

    #[test]
    fn a_full_bucket_shifts_one_place_toward_the_past() {
        let mut meter = KpsMeter::default();
        meter.tick(4);
        (1..BUCKET_MS).for_each(|_| meter.tick(0));
        assert_eq!(meter.history()[HISTORY_BUCKETS - 2..], [4, 0]);
    }

    #[test]
    fn presses_fall_off_after_the_whole_history() {
        let mut meter = KpsMeter::default();
        meter.tick(1);
        (1..u32::from(BUCKET_MS) * HISTORY_BUCKETS as u32).for_each(|_| meter.tick(0));
        assert_eq!(meter.history(), [0; HISTORY_BUCKETS]);
    }
}
