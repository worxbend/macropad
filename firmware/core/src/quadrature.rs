//! Quadrature decoding for a detented rotary encoder (Alps EC11).
//!
//! One electrical cycle is four contact edges. EC11 variants differ in how many clicks that is,
//! so the decoder is told with [`Detents`].

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Rotation {
    Clockwise,
    CounterClockwise,
}

/// How the clicks of the knob line up with the electrical cycle.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Detents {
    /// One click per cycle (for example 20 detents, 20 pulses). The knob rests with both contacts open.
    PerCycle,
    /// Two clicks per cycle (for example 36 detents, 18 pulses, as on the EC11E18244AU).
    /// The knob rests with both contacts open or both closed, alternately.
    PerHalfCycle,
}

impl Detents {
    const fn edges(self) -> i8 {
        match self {
            Self::PerCycle => 4,
            Self::PerHalfCycle => 2,
        }
    }

    const fn rests_at(self, phase: u8) -> bool {
        phase == BOTH_OPEN || (matches!(self, Self::PerHalfCycle) && phase == BOTH_CLOSED)
    }
}

/// Phase with both contacts open, pulled high.
const BOTH_OPEN: u8 = 0b11;
const BOTH_CLOSED: u8 = 0b00;
/// Indexed by `previous_phase << 2 | phase`, phase being `A << 1 | B`.
/// +1 is one clockwise edge (A falls first), -1 one counter-clockwise edge,
/// 0 is no movement or an impossible two-contact jump.
const EDGE_STEPS: [i8; 16] = [0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0];

#[derive(Clone, Copy)]
pub struct QuadratureDecoder {
    detents: Detents,
    previous_phase: u8,
    edges_since_detent: i8,
}

impl Default for QuadratureDecoder {
    fn default() -> Self {
        Self::new(Detents::PerCycle)
    }
}

impl QuadratureDecoder {
    pub const fn new(detents: Detents) -> Self {
        Self {
            detents,
            previous_phase: BOTH_OPEN,
            edges_since_detent: 0,
        }
    }

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
        if !self.detents.rests_at(phase) {
            return None;
        }
        let edges = core::mem::take(&mut self.edges_since_detent);
        let edges_per_detent = self.detents.edges();
        if edges == edges_per_detent {
            Some(Rotation::Clockwise)
        } else if edges == -edges_per_detent {
            Some(Rotation::CounterClockwise)
        } else {
            None
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

    /// Regression: the EC11E18244AU clicks twice per cycle, so a four-edge decoder lost every other click.
    #[test]
    fn a_two_click_per_cycle_knob_reports_every_click() {
        let mut decoder = QuadratureDecoder::new(Detents::PerHalfCycle);
        assert_eq!(feed(&mut decoder, &CLOCKWISE[..2]), [Rotation::Clockwise]);
        assert_eq!(feed(&mut decoder, &CLOCKWISE[2..]), [Rotation::Clockwise]);
        assert_eq!(
            feed(&mut decoder, &COUNTER_CLOCKWISE[..2]),
            [Rotation::CounterClockwise]
        );
        assert_eq!(
            feed(&mut decoder, &COUNTER_CLOCKWISE[2..]),
            [Rotation::CounterClockwise]
        );
    }

    #[test]
    fn a_two_click_knob_ignores_bounce_at_either_rest_position() {
        let mut decoder = QuadratureDecoder::new(Detents::PerHalfCycle);
        assert_eq!(feed(&mut decoder, &[(false, true), (true, true)]), []);
        assert_eq!(feed(&mut decoder, &CLOCKWISE[..2]), [Rotation::Clockwise]);
        assert_eq!(feed(&mut decoder, &[(true, false), (false, false)]), []);
    }

    #[test]
    fn a_two_click_knob_resting_closed_at_power_on_reports_nothing_until_it_moves() {
        let mut decoder = QuadratureDecoder::new(Detents::PerHalfCycle);
        assert_eq!(feed(&mut decoder, &[(false, false); 3]), []);
        assert_eq!(feed(&mut decoder, &CLOCKWISE[2..]), [Rotation::Clockwise]);
    }
}
