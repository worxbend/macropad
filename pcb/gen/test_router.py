"""Tests for router.py. Run with: python3 -m unittest discover -s pcb/gen -p 'test_*.py'"""

from __future__ import annotations

import math
import unittest

from router import BACK, BOTH_LAYERS, FRONT, Pad, Router, Rules, Track, Via

RULES = Rules()


def small_board() -> Router:
    return Router(20.0, 10.0, 1.0, RULES)


def pad(name: str, net: str, x: float, y: float, layers: tuple[int, ...] = (BACK,), half: float = 0.3) -> Pad:
    return Pad(name, net, (x - half, y - half, x + half, y + half), layers)


def segment_gap(first: Track, second: Track) -> float:
    """Shortest distance between the centre lines of two tracks, sampled every 0.02 mm."""
    def samples(track: Track) -> list[tuple[float, float]]:
        steps = max(1, round(track.length / 0.02))
        return [(track.start[0] + (track.end[0] - track.start[0]) * i / steps,
                 track.start[1] + (track.end[1] - track.start[1]) * i / steps) for i in range(steps + 1)]
    return min(math.dist(a, b) for a in samples(first) for b in samples(second))


def rect_gap(track: Track, rect: tuple[float, float, float, float]) -> float:
    left, top, right, bottom = rect
    steps = max(1, round(track.length / 0.02))
    gaps = []
    for i in range(steps + 1):
        x = track.start[0] + (track.end[0] - track.start[0]) * i / steps
        y = track.start[1] + (track.end[1] - track.start[1]) * i / steps
        gaps.append(math.hypot(max(left - x, x - right, 0), max(top - y, y - bottom, 0)))
    return min(gaps)


def is_connected(tracks: list[Track], vias: list[Via], first: Pad, second: Pad) -> bool:
    """Walks the copper from one pad to the other: track ends that meet, and vias that join the layers."""
    def touches(point: tuple[float, float], target: Pad) -> bool:
        left, top, right, bottom = target.rect
        return left <= point[0] <= right and top <= point[1] <= bottom

    reached = {(layer, first.centre) for layer in first.layers}
    grew = True
    while grew:
        grew = False
        for track in tracks:
            for here, there in ((track.start, track.end), (track.end, track.start)):
                if (track.layer, here) in reached and (track.layer, there) not in reached:
                    reached.add((track.layer, there))
                    grew = True
        for via in vias:
            spot = (via.x, via.y)
            if any((layer, spot) in reached for layer in BOTH_LAYERS):
                before = len(reached)
                reached.update((layer, spot) for layer in BOTH_LAYERS)
                grew = grew or len(reached) != before
    return any(touches(point, second) and layer in second.layers for layer, point in reached)


def loose_ends(tracks: list[Track], vias: list[Via], pads: list[Pad]) -> list[tuple[float, float]]:
    """Track ends that touch no pad, no via and no other track of their layer."""
    def on_segment(point: tuple[float, float], track: Track) -> bool:
        return abs(math.dist(track.start, point) + math.dist(point, track.end) - track.length) < 1e-6

    loose = []
    for track in tracks:
        for end in (track.start, track.end):
            on_pad = any(p.rect[0] <= end[0] <= p.rect[2] and p.rect[1] <= end[1] <= p.rect[3] for p in pads)
            on_via = any((via.x, via.y) == end for via in vias)
            on_track = any(other is not track and other.layer == track.layer and on_segment(end, other)
                           for other in tracks)
            if not (on_pad or on_via or on_track):
                loose.append(end)
    return loose


class RouterTest(unittest.TestCase):
    def test_straight_connection_is_one_segment_between_pad_centres(self) -> None:
        router = small_board()
        a, b = pad("A.1", "N", 5.0, 5.0), pad("B.1", "N", 12.0, 5.0)
        router.add_pad(a)
        router.add_pad(b)
        self.assertEqual(router.route_net("N", [a, b]), [])
        self.assertTrue(is_connected(router.tracks, router.vias, a, b))
        self.assertEqual(router.vias, [])
        self.assertAlmostEqual(router.net_length("N"), 7.0, places=3)
        self.assertTrue(all(track.start[1] == 5.0 and track.end[1] == 5.0 for track in router.tracks))

    def test_track_goes_round_a_foreign_pad_with_clearance(self) -> None:
        router = small_board()
        a, b = pad("A.1", "N", 5.0, 5.0), pad("B.1", "N", 12.0, 5.0)
        wall = Pad("W.1", "OTHER", (8.0, 3.0, 9.0, 7.0), (BACK,))
        for item in (a, b, wall):
            router.add_pad(item)
        self.assertEqual(router.route_net("N", [a, b]), [])
        self.assertEqual(router.vias, [], "going round is cheaper than two vias here")
        needed = RULES.clearance + RULES.track_width / 2
        for track in router.tracks:
            self.assertGreaterEqual(rect_gap(track, wall.rect), needed - 1e-6)

    def test_wall_across_the_board_forces_two_vias(self) -> None:
        router = small_board()
        a, b = pad("A.1", "N", 5.0, 5.0), pad("B.1", "N", 12.0, 5.0)
        wall = Pad("W.1", "OTHER", (8.0, 0.0, 9.0, 10.0), (BACK,))
        for item in (a, b, wall):
            router.add_pad(item)
        self.assertEqual(router.route_net("N", [a, b]), [])
        self.assertEqual(len(router.vias), 2)
        self.assertTrue(is_connected(router.tracks, router.vias, a, b))
        self.assertTrue(any(track.layer == FRONT for track in router.tracks))

    def test_blocked_on_both_layers_reports_the_pad_and_adds_no_copper(self) -> None:
        router = small_board()
        a, b = pad("A.1", "N", 5.0, 5.0), pad("B.1", "N", 12.0, 5.0)
        wall = Pad("W.1", "OTHER", (8.0, 0.0, 9.0, 10.0), BOTH_LAYERS)
        for item in (a, b, wall):
            router.add_pad(item)
        self.assertEqual(router.route_net("N", [a, b]), ["B.1"])
        self.assertEqual(router.tracks, [])

    def test_second_net_keeps_clearance_to_the_first(self) -> None:
        router = small_board()
        a, b = pad("A.1", "ONE", 4.0, 5.0), pad("B.1", "ONE", 16.0, 5.0)
        c, d = pad("C.1", "TWO", 10.0, 2.0), pad("D.1", "TWO", 10.0, 8.0)
        for item in (a, b, c, d):
            router.add_pad(item)
        self.assertEqual(router.route_net("ONE", [a, b]), [])
        self.assertEqual(router.route_net("TWO", [c, d]), [])
        self.assertEqual(len(router.vias), 2, "the second net has to cross on the other layer")
        needed = RULES.clearance + RULES.track_width
        for first in (t for t in router.tracks if t.net == "ONE"):
            for second in (t for t in router.tracks if t.net == "TWO" and t.layer == first.layer):
                self.assertGreaterEqual(segment_gap(first, second), needed - 1e-6)
        via_needed = RULES.clearance + RULES.track_width / 2 + RULES.via_diameter / 2
        for via in router.vias:
            for track in (t for t in router.tracks if t.net == "ONE"):
                self.assertGreaterEqual(rect_gap(track, (via.x, via.y, via.x, via.y)), via_needed - 1e-6)

    def test_parallel_tracks_fit_at_fine_pitch(self) -> None:
        """Two 0.2 mm pads 0.4 mm apart, like the MCU: both escape straight out."""
        router = small_board()
        pins = [Pad(f"U.{n}", f"N{n}", (5.0, y - 0.1, 5.8, y + 0.1), (BACK,)) for n, y in ((1, 5.0), (2, 5.4))]
        ends = [pad(f"E.{n}", f"N{n}", 12.0, y) for n, y in ((1, 3.0), (2, 7.0))]
        for item in pins + ends:
            router.add_pad(item)
        for pin, end in zip(pins, ends):
            self.assertEqual(router.route_net(pin.net, [pin, end]), [])
        self.assertEqual(router.vias, [])

    def test_three_pads_become_one_tree(self) -> None:
        router = small_board()
        pads = [pad("A.1", "N", 4.0, 5.0), pad("B.1", "N", 16.0, 5.0), pad("C.1", "N", 10.0, 8.0)]
        for item in pads:
            router.add_pad(item)
        self.assertEqual(router.route_net("N", pads), [])
        self.assertTrue(is_connected(router.tracks, router.vias, pads[0], pads[1]))
        self.assertTrue(is_connected(router.tracks, router.vias, pads[0], pads[2]))
        self.assertLess(router.net_length("N"), 12.0 + 3.6, "the third pad taps the trunk, it does not run home")

    def test_fan_out_drops_one_via_outside_the_pad_and_inside_the_plane(self) -> None:
        router = small_board()
        supply = pad("C.1", "+3V3", 6.0, 5.0)
        router.add_pad(supply)
        self.assertTrue(router.fan_out("+3V3", supply, lambda x, y: x >= 8.0))
        self.assertEqual(len(router.vias), 1)
        via = router.vias[0]
        self.assertGreaterEqual(via.x, 8.0)
        self.assertTrue(any(track.end == (via.x, via.y) for track in router.tracks))

    def test_fan_out_shares_a_via_that_is_already_there(self) -> None:
        router = small_board()
        first, second = pad("C.1", "GND", 6.0, 5.0), pad("C.2", "GND", 6.0, 6.2)
        router.add_pad(first)
        router.add_pad(second)
        self.assertTrue(router.fan_out("GND", first, lambda x, y: True))
        self.assertTrue(router.fan_out("GND", second, lambda x, y: True))
        self.assertEqual(len(router.vias), 1)

    def test_hand_placed_via_is_refused_where_it_would_crowd_a_foreign_pad(self) -> None:
        router = small_board()
        router.add_pad(pad("X.1", "OTHER", 6.0, 5.0))
        with self.assertRaises(AssertionError):
            router.add_via("GND", 6.6, 5.0)
        router.add_via("GND", 7.0, 5.0)
        self.assertEqual(router.vias, [Via("GND", 7.0, 5.0)])

    def test_escape_leaves_the_square_and_its_unused_end_is_cut_off(self) -> None:
        router = small_board()
        pin, far = pad("U.1", "N", 10.0, 5.0, half=0.1), pad("J.1", "N", 3.0, 8.0)
        router.add_pad(pin)
        router.add_pad(far)
        self.assertTrue(router.escape("N", pin, (10.0, 5.0), 2.0))
        self.assertAlmostEqual(router.net_length("N"), 2.0, places=3)
        self.assertEqual(len(loose_ends(router.tracks, router.vias, [pin, far])), 1, "the escape is still open")
        self.assertEqual(router.route_net("N", [pin, far]), [])
        self.assertTrue(is_connected(router.tracks, router.vias, pin, far))
        self.assertEqual(loose_ends(router.tracks, router.vias, [pin, far]), [])

    def test_tree_of_three_pads_has_no_loose_ends(self) -> None:
        router = small_board()
        pads = [pad("A.1", "N", 4.0, 5.0), pad("B.1", "N", 16.0, 5.0), pad("C.1", "N", 10.0, 8.0)]
        for item in pads:
            router.add_pad(item)
        router.route_net("N", pads)
        self.assertEqual(loose_ends(router.tracks, router.vias, pads), [])

    def test_no_track_or_via_near_the_board_edge_or_a_hole(self) -> None:
        router = small_board()
        a, b = pad("A.1", "N", 1.0, 1.2), pad("B.1", "N", 19.0, 1.2)
        hole = (9.5, 0.5, 10.5, 1.9)
        router.add_pad(a)
        router.add_pad(b)
        router.add_hole(hole)
        self.assertEqual(router.route_net("N", [a, b]), [])
        edge_needed = RULES.edge_clearance + RULES.track_width / 2
        for track in router.tracks:
            if track.length > 0.5:  # the stubs to the pad centres lie inside the pads
                for x, y in (track.start, track.end):
                    self.assertGreaterEqual(min(x, y, 20.0 - x, 10.0 - y), edge_needed - 1e-6)
            self.assertGreaterEqual(rect_gap(track, hole), RULES.hole_clearance + RULES.track_width / 2 - 1e-6)

    def test_wide_track_keeps_clearance_too(self) -> None:
        router = small_board()
        a, b = pad("A.1", "N", 5.0, 5.0), pad("B.1", "N", 12.0, 5.0)
        wall = Pad("W.1", "OTHER", (8.0, 3.0, 9.0, 7.0), (BACK,))
        for item in (a, b, wall):
            router.add_pad(item)
        self.assertEqual(router.route_net("N", [a, b], wide=True), [])
        needed = RULES.clearance + RULES.wide_track_width / 2
        for track in router.tracks:
            self.assertEqual(track.width, RULES.wide_track_width)
            self.assertGreaterEqual(rect_gap(track, wall.rect), needed - 1e-6)

    def test_same_input_gives_the_same_copper(self) -> None:
        def run() -> tuple[list[Track], list[Via]]:
            router = small_board()
            pads = [pad("A.1", "N", 4.0, 5.0), pad("B.1", "N", 16.0, 5.0), pad("C.1", "N", 10.0, 8.0)]
            wall = Pad("W.1", "OTHER", (8.0, 0.0, 9.0, 6.0), (BACK,))
            for item in pads + [wall]:
                router.add_pad(item)
            router.route_net("N", pads)
            return router.tracks, router.vias
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
