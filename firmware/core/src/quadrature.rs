//! Quadrature decoding for a detented rotary encoder (Alps EC11).
//!
//! One electrical cycle is four contact edges. EC11 variants differ in how many clicks that is,
//! and in which contact is settled while the knob rests in a click, so the decoder is told
//! with [`Detents`].

use crate::debounce::{Debouncer, DEBOUNCE_SAMPLES};

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
    /// Two clicks per cycle, and the knob rests with both contacts open or both closed, alternately.
    /// Not for the EC11E18244AU: its contact B may rest on its own edge, so a click can wait for
    /// a level that never comes.
    PerHalfCycle,
    /// One click per edge of contact A, two per cycle (36 detents, 18 pulses, as on the EC11E18244AU).
    /// Alps' output-wave figure for that part: "The stable detent position cannot be identified
    /// in phase B." At rest A is settled and B may sit on its edge, so only A is counted, after
    /// debouncing, and B gives the direction.
    PerEdgeOfA,
}

impl Detents {
    const fn edges(self) -> i8 {
        match self {
            Self::PerCycle => 4,
            Self::PerHalfCycle | Self::PerEdgeOfA => 2,
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
    method: Method,
}

#[derive(Clone, Copy)]
enum Method {
    Phases(PhaseCounter),
    EdgesOfA(EdgeOfACounter),
}

impl Default for QuadratureDecoder {
    fn default() -> Self {
        Self::new(Detents::PerCycle)
    }
}

impl QuadratureDecoder {
    pub const fn new(detents: Detents) -> Self {
        let method = match detents {
            Detents::PerEdgeOfA => Method::EdgesOfA(EdgeOfACounter::new()),
            Detents::PerCycle | Detents::PerHalfCycle => Method::Phases(PhaseCounter::new(detents)),
        };
        Self { method }
    }

    /// Feeds the two contact levels (high = open) and returns a rotation when a click completes.
    pub fn sample(&mut self, a_high: bool, b_high: bool) -> Option<Rotation> {
        match &mut self.method {
            Method::Phases(counter) => counter.sample(a_high, b_high),
            Method::EdgesOfA(counter) => counter.sample(a_high, b_high),
        }
    }
}

/// Follows every contact edge and reports when the knob is back at a rest phase.
#[derive(Clone, Copy)]
struct PhaseCounter {
    detents: Detents,
    previous_phase: u8,
    edges_since_detent: i8,
}

impl PhaseCounter {
    const fn new(detents: Detents) -> Self {
        Self {
            detents,
            previous_phase: BOTH_OPEN,
            edges_since_detent: 0,
        }
    }

    fn sample(&mut self, a_high: bool, b_high: bool) -> Option<Rotation> {
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

/// One click per debounced edge of contact A.
///
/// Clockwise, A changes first (see `EDGE_STEPS`), so right after a clockwise A edge the two
/// contacts differ; after a counter-clockwise one they are equal. B is read on the first raw
/// sample where A leaves its settled level, not when the debounced edge is accepted: on a fast
/// turn B may already have moved on. Later bounces of the same edge keep that first reading.
/// A return to the settled level that lasts a full debounce window was a glitch, so the next
/// change of A reads B again.
#[derive(Clone, Copy)]
struct EdgeOfACounter {
    /// `None` until the first sample, which only learns where A rests.
    a: Option<Debouncer>,
    /// B on the first raw change of A since the last click or glitch; `None` while A rests.
    b_at_first_change: Option<bool>,
    /// Consecutive raw samples of A at its settled level.
    samples_at_rest: u8,
}

impl EdgeOfACounter {
    const fn new() -> Self {
        Self {
            a: None,
            b_at_first_change: None,
            samples_at_rest: 0,
        }
    }

    fn sample(&mut self, a_high: bool, b_high: bool) -> Option<Rotation> {
        let Some(a) = &mut self.a else {
            self.a = Some(Debouncer::settled(a_high));
            return None;
        };
        let settled = a.level();
        if a_high == settled {
            self.samples_at_rest = self.samples_at_rest.saturating_add(1);
            if self.samples_at_rest >= DEBOUNCE_SAMPLES {
                self.b_at_first_change = None;
            }
        } else {
            self.samples_at_rest = 0;
            self.b_at_first_change.get_or_insert(b_high);
        }
        let a_now = a.sample(a_high);
        if a_now == settled {
            return None;
        }
        // An accepted edge needs A away from `settled` on this sample, so B was read above.
        let b_then = self.b_at_first_change.take().unwrap_or(b_high);
        Some(if a_now != b_then {
            Rotation::Clockwise
        } else {
            Rotation::CounterClockwise
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const CLOCKWISE: [(bool, bool); 4] = [(false, true), (false, false), (true, false), (true, true)];
    const COUNTER_CLOCKWISE: [(bool, bool); 4] = [(true, false), (false, false), (false, true), (true, true)];
    /// Samples each phase is held in the `PerEdgeOfA` tests: one more than the debounce window.
    const HOLD: usize = DEBOUNCE_SAMPLES as usize + 1;

    fn feed(decoder: &mut QuadratureDecoder, phases: &[(bool, bool)]) -> Vec<Rotation> {
        phases.iter().filter_map(|&(a, b)| decoder.sample(a, b)).collect()
    }

    fn held(phases: &[(bool, bool)]) -> Vec<(bool, bool)> {
        phases.iter().flat_map(|&phase| [phase; HOLD]).collect()
    }

    /// A decoder for the EC11E18244AU that has already seen the knob resting with both contacts open.
    fn edge_of_a_decoder() -> QuadratureDecoder {
        let mut decoder = QuadratureDecoder::new(Detents::PerEdgeOfA);
        assert_eq!(feed(&mut decoder, &[(true, true); HOLD]), []);
        decoder
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

    /// Regression: `PerHalfCycle` waits for B to settle at rest, which the EC11E18244AU does not promise.
    #[test]
    fn the_half_cycle_decoder_loses_a_click_when_b_rests_on_its_edge() {
        let mut decoder = QuadratureDecoder::new(Detents::PerHalfCycle);
        // A falls, then the knob rests in the click with B still open: nothing is reported.
        assert_eq!(feed(&mut decoder, &[(false, true); 20]), []);
        let mut edge_of_a = edge_of_a_decoder();
        assert_eq!(feed(&mut edge_of_a, &[(false, true); 20]), [Rotation::Clockwise]);
    }

    #[test]
    fn a_clockwise_turn_reports_one_click_per_edge_of_a() {
        let mut decoder = edge_of_a_decoder();
        assert_eq!(feed(&mut decoder, &held(&CLOCKWISE)), [Rotation::Clockwise; 2]);
        assert_eq!(feed(&mut decoder, &held(&CLOCKWISE)), [Rotation::Clockwise; 2]);
    }

    #[test]
    fn a_counter_clockwise_turn_reports_one_click_per_edge_of_a() {
        let mut decoder = edge_of_a_decoder();
        assert_eq!(
            feed(&mut decoder, &held(&COUNTER_CLOCKWISE)),
            [Rotation::CounterClockwise; 2]
        );
    }

    #[test]
    fn the_click_comes_when_a_has_held_its_new_level_for_the_debounce_window() {
        let mut decoder = edge_of_a_decoder();
        let window = DEBOUNCE_SAMPLES as usize;
        assert_eq!(feed(&mut decoder, &vec![(false, true); window - 1]), []);
        assert_eq!(decoder.sample(false, true), Some(Rotation::Clockwise));
    }

    #[test]
    fn b_chattering_at_rest_reports_nothing() {
        let mut decoder = edge_of_a_decoder();
        let chatter_open: Vec<_> = (0..100).map(|sample| (true, sample % 3 == 0)).collect();
        assert_eq!(feed(&mut decoder, &chatter_open), []);
        // The same with A resting closed, one click further on.
        assert_eq!(feed(&mut decoder, &held(&CLOCKWISE[..1])), [Rotation::Clockwise]);
        let chatter_closed: Vec<_> = (0..100).map(|sample| (false, sample % 2 == 0)).collect();
        assert_eq!(feed(&mut decoder, &chatter_closed), []);
    }

    #[test]
    fn a_bouncing_inside_the_debounce_window_reports_one_click() {
        let mut decoder = edge_of_a_decoder();
        let bounce = [(false, true), (true, true), (false, true), (false, true), (true, true)];
        assert_eq!(feed(&mut decoder, &bounce), []);
        assert_eq!(feed(&mut decoder, &held(&[(false, true)])), [Rotation::Clockwise]);
    }

    #[test]
    fn a_glitch_on_a_shorter_than_the_window_reports_nothing() {
        let mut decoder = edge_of_a_decoder();
        let glitch = vec![(false, true); DEBOUNCE_SAMPLES as usize - 1];
        assert_eq!(feed(&mut decoder, &glitch), []);
        assert_eq!(feed(&mut decoder, &held(&[(true, true)])), []);
    }

    #[test]
    fn turning_back_reports_the_other_direction() {
        let mut decoder = edge_of_a_decoder();
        assert_eq!(feed(&mut decoder, &held(&[(false, true)])), [Rotation::Clockwise]);
        assert_eq!(feed(&mut decoder, &held(&[(true, true)])), [Rotation::CounterClockwise]);
        assert_eq!(
            feed(&mut decoder, &held(&[(true, false), (false, false)])),
            [Rotation::CounterClockwise]
        );
        assert_eq!(feed(&mut decoder, &held(&[(true, false)])), [Rotation::Clockwise]);
    }

    #[test]
    fn the_direction_comes_from_b_when_a_started_to_change() {
        let mut decoder = edge_of_a_decoder();
        // A fast clockwise turn: B follows A two samples later, before the A edge is accepted.
        let fast = [
            (false, true),
            (false, true),
            (false, false),
            (false, false),
            (false, false),
        ];
        assert_eq!(feed(&mut decoder, &fast), [Rotation::Clockwise]);
    }

    #[test]
    fn a_knob_resting_with_a_closed_at_power_on_reports_nothing_until_it_moves() {
        let mut decoder = QuadratureDecoder::new(Detents::PerEdgeOfA);
        assert_eq!(feed(&mut decoder, &[(false, false); 20]), []);
        assert_eq!(feed(&mut decoder, &held(&[(true, false)])), [Rotation::Clockwise]);
    }

    /// Regression: B was read again on every bounce of A, so B's own edge inside A's bounce
    /// turned a fast clockwise click into a counter-clockwise one.
    #[test]
    fn b_moving_during_the_bounce_of_a_keeps_the_first_reading() {
        let mut decoder = edge_of_a_decoder();
        let bounce_then_b = [
            (false, true),
            (true, true),
            (false, false),
            (true, false),
            (false, false),
        ];
        assert_eq!(feed(&mut decoder, &bounce_then_b), []);
        assert_eq!(feed(&mut decoder, &held(&[(false, false)])), [Rotation::Clockwise]);
    }

    #[test]
    fn a_glitch_on_a_does_not_fix_the_direction_of_the_next_click() {
        let mut decoder = edge_of_a_decoder();
        // A glitches while B is open, rests for a full window, then the knob turns back.
        assert_eq!(feed(&mut decoder, &[(false, true); 2]), []);
        assert_eq!(
            feed(&mut decoder, &held(&[(true, true), (true, false), (false, false)])),
            [Rotation::CounterClockwise]
        );
    }
}
