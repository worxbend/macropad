//! Quadrature decoding for a detented rotary encoder (Alps EC11: four edges per detent).

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Rotation {
    Clockwise,
    CounterClockwise,
}

const EDGES_PER_DETENT: i8 = 4;
/// Both contacts open, pulled high: the encoder rests here between detents.
const DETENT_PHASE: u8 = 0b11;
/// Indexed by `previous_phase << 2 | phase`, phase being `A << 1 | B`.
/// +1 is one clockwise edge (A falls first), -1 one counter-clockwise edge,
/// 0 is no movement or an impossible two-contact jump.
const EDGE_STEPS: [i8; 16] = [0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0];

#[derive(Clone, Copy)]
pub struct QuadratureDecoder {
    previous_phase: u8,
    edges_since_detent: i8,
}

impl Default for QuadratureDecoder {
    fn default() -> Self {
        Self {
            previous_phase: DETENT_PHASE,
            edges_since_detent: 0,
        }
    }
}

impl QuadratureDecoder {
    /// Feeds the two contact levels and returns a rotation when a full detent completes.
    pub fn sample(&mut self, a_high: bool, b_high: bool) -> Option<Rotation> {
        let phase = (a_high as u8) << 1 | b_high as u8;
        let step = EDGE_STEPS[usize::from(self.previous_phase << 2 | phase)];
        let jumped_two_contacts = phase != self.previous_phase && step == 0;
        self.previous_phase = phase;
        if jumped_two_contacts {
            // A missed sample: the direction is unknown, so the partial detent is thrown away.
            self.edges_since_detent = 0;
            return None;
        }
        self.edges_since_detent += step;
        if phase != DETENT_PHASE {
            return None;
        }
        let edges = core::mem::take(&mut self.edges_since_detent);
        match edges {
            EDGES_PER_DETENT => Some(Rotation::Clockwise),
            e if e == -EDGES_PER_DETENT => Some(Rotation::CounterClockwise),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const CLOCKWISE: [(bool, bool); 4] = [(false, true), (false, false), (true, false), (true, true)];
    const COUNTER_CLOCKWISE: [(bool, bool); 4] = [(true, false), (false, false), (false, true), (true, true)];

    fn feed(decoder: &mut QuadratureDecoder, phases: &[(bool, bool)]) -> Vec<Rotation> {
        phases.iter().filter_map(|&(a, b)| decoder.sample(a, b)).collect()
    }

    #[test]
    fn one_clockwise_detent_reports_once_at_the_detent() {
        let mut decoder = QuadratureDecoder::default();
        assert_eq!(feed(&mut decoder, &CLOCKWISE[..3]), []);
        assert_eq!(decoder.sample(true, true), Some(Rotation::Clockwise));
    }

    #[test]
    fn one_counter_clockwise_detent_reports_once() {
        let mut decoder = QuadratureDecoder::default();
        assert_eq!(feed(&mut decoder, &COUNTER_CLOCKWISE), [Rotation::CounterClockwise]);
    }

    #[test]
    fn repeated_samples_of_the_same_phase_change_nothing() {
        let mut decoder = QuadratureDecoder::default();
        let stuttered: Vec<_> = CLOCKWISE.iter().flat_map(|&phase| [phase; 3]).collect();
        assert_eq!(feed(&mut decoder, &stuttered), [Rotation::Clockwise]);
    }

    #[test]
    fn contact_bounce_back_to_the_detent_reports_nothing() {
        let mut decoder = QuadratureDecoder::default();
        assert_eq!(
            feed(
                &mut decoder,
                &[(false, true), (true, true), (false, true), (true, true)]
            ),
            []
        );
    }

    #[test]
    fn half_turn_and_back_reports_nothing() {
        let mut decoder = QuadratureDecoder::default();
        assert_eq!(
            feed(
                &mut decoder,
                &[(false, true), (false, false), (false, true), (true, true)]
            ),
            []
        );
    }

    #[test]
    fn two_contact_jump_discards_the_partial_detent() {
        let mut decoder = QuadratureDecoder::default();
        // 11 -> 00 skips a phase; the remaining two clockwise edges must not count as a detent.
        assert_eq!(feed(&mut decoder, &[(false, false), (true, false), (true, true)]), []);
        assert_eq!(feed(&mut decoder, &CLOCKWISE), [Rotation::Clockwise]);
    }
}
