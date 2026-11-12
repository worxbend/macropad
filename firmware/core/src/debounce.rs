//! Switch debouncing by consecutive-sample counting.

/// Samples a switch must hold a new level before it is accepted. At 1 kHz this is 5 ms.
pub const DEBOUNCE_SAMPLES: u8 = 5;

#[derive(Clone, Copy, Default)]
pub struct Debouncer {
    stable: bool,
    differing_samples: u8,
}

impl Debouncer {
    /// Feeds one raw sample and returns the debounced level.
    pub fn sample(&mut self, raw: bool) -> bool {
        if raw == self.stable {
            self.differing_samples = 0;
            return self.stable;
        }
        self.differing_samples += 1;
        if self.differing_samples >= DEBOUNCE_SAMPLES {
            self.stable = raw;
            self.differing_samples = 0;
        }
        self.stable
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn feed(debouncer: &mut Debouncer, raw: bool, samples: u8) -> bool {
        (0..samples).map(|_| debouncer.sample(raw)).last().unwrap()
    }

    #[test]
    fn starts_released() {
        assert!(!Debouncer::default().sample(false));
    }

    #[test]
    fn accepts_a_level_held_for_the_full_window() {
        let mut debouncer = Debouncer::default();
        assert!(!feed(&mut debouncer, true, DEBOUNCE_SAMPLES - 1));
        assert!(debouncer.sample(true));
    }

    #[test]
    fn ignores_a_bounce_shorter_than_the_window() {
        let mut debouncer = Debouncer::default();
        feed(&mut debouncer, true, DEBOUNCE_SAMPLES - 1);
        debouncer.sample(false);
        assert!(!feed(&mut debouncer, true, DEBOUNCE_SAMPLES - 1));
    }

    #[test]
    fn releases_after_the_full_window() {
        let mut debouncer = Debouncer::default();
        feed(&mut debouncer, true, DEBOUNCE_SAMPLES);
        assert!(feed(&mut debouncer, false, DEBOUNCE_SAMPLES - 1));
        assert!(!debouncer.sample(false));
    }
}
