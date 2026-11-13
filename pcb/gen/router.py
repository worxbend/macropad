"""A small two-layer grid router. Pure Python, no KiCad import, so it can be tested anywhere.

The board is a grid of nodes (0.1 mm pitch) on the two outer copper layers. Every piece of copper
claims the nodes a track of another net must stay away from. A node claimed by one net is open to
that net only; a node claimed by two nets, by a hole or by the board edge is closed to all.
Routes are A* paths over 45 degree moves, with vias as moves between the layers.

Coordinates are millimetres, top view, same as board.toml.
"""

from __future__ import annotations

import heapq
import math
from array import array
from dataclasses import dataclass
from typing import Callable, Iterable

FRONT, BACK = 0, 1
BOTH_LAYERS = (FRONT, BACK)
_FREE = 0
_CLOSED = -1

_STEPS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
_NO_HEADING = 8
_HEADINGS = 9
_STRAIGHT_COST = 10
_DIAGONAL_COST = 14
# Indexed by the heading change in 45 degree steps. Sharper than 90 degrees is not allowed.
_TURN_COST = (0, 3, 15)
_VIA_COST = 300  # a via costs as much as 3 mm of track
# A pad of a plane net reaches for copper that already has a via only if that is this much nearer
# than a via of its own. Cheap, or the pads chain up into long bars that wall in their neighbours.
_OWN_VIA_COST = 40
_SEARCH_LIMIT = 3_000_000
# The distance still to go counts 1.5 times: far fewer nodes searched, for a slightly longer track.
_GREED_NUMERATOR, _GREED_DENOMINATOR = 3, 2

Rect = tuple[float, float, float, float]  # left, top, right, bottom
Node = tuple[int, int, int]  # layer, column, row


@dataclass(frozen=True)
class Rules:
    pitch: float = 0.1
    track_width: float = 0.15
    wide_track_width: float = 0.3
    clearance: float = 0.15
    via_diameter: float = 0.6
    via_drill: float = 0.3
    edge_clearance: float = 0.3
    hole_clearance: float = 0.25
    # A track between two nodes can come this much closer to a corner than the nodes themselves.
    grid_allowance: float = 0.02
    # Vias stay out of pads, so solder does not wick into them.
    via_to_pad_gap: float = 0.05
    via_to_via_gap: float = 0.25


@dataclass(frozen=True)
class Pad:
    name: str  # "U1.5"
    net: str  # "" for a pad without a net
    rect: Rect
    layers: tuple[int, ...]

    @property
    def centre(self) -> tuple[float, float]:
        left, top, right, bottom = self.rect
        return (left + right) / 2, (top + bottom) / 2


@dataclass(frozen=True)
class Track:
    net: str
    layer: int
    start: tuple[float, float]
    end: tuple[float, float]
    width: float

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)


@dataclass(frozen=True)
class Via:
    net: str
    x: float
    y: float


class Router:
    def __init__(self, width: float, height: float, corner_radius: float, rules: Rules = Rules()) -> None:
        self.rules = rules
        self.board_width, self.board_height = width, height
        self._pitch = rules.pitch
        self._columns = round(width / rules.pitch) + 1
        self._rows = round(height / rules.pitch) + 1
        node_count = self._columns * self._rows
        self._track_cells = [array("i", bytes(4 * node_count)) for _ in BOTH_LAYERS]
        self._via_cells = array("i", bytes(4 * node_count))
        self._net_ids: dict[str, int] = {}
        self._tree: dict[str, set[tuple[int, int]]] = {}  # copper already joined, per net: (layer, index)
        self._plane_tree: dict[str, set[tuple[int, int]]] = {}  # copper that already has a via to its plane
        self._pad_centre: dict[tuple[int, int], tuple[float, float]] = {}
        self._escaped: set[str] = set()  # names of pads that already have a track out to their net's tree
        self._open_escapes: dict[str, tuple[list[Node], list[Track], list[Via]]] = {}  # not yet continued
        self.tracks: list[Track] = []
        self.vias: list[Via] = []
        self._half_track = rules.track_width / 2
        self._via_radius = rules.via_diameter / 2
        self._track_reach = self._half_track + rules.clearance + rules.grid_allowance
        self._via_reach = self._via_radius + rules.clearance + rules.grid_allowance
        self._close_board_edge(corner_radius)

    # --- obstacles ----------------------------------------------------------------------------

    def add_pad(self, pad: Pad) -> None:
        owner = self._net_id(pad.net) if pad.net else _CLOSED
        for layer in pad.layers:
            self._claim_rect(self._track_cells[layer], pad.rect, self._track_reach, owner)
            if pad.net:
                for index in self._nodes_in(pad.rect):
                    self._pad_centre[(layer, index)] = pad.centre
        self._claim_rect(self._via_cells, pad.rect, self._via_reach, owner)
        self._claim_rect(self._via_cells, pad.rect, self._via_radius + self.rules.via_to_pad_gap, _CLOSED)

    def add_hole(self, rect: Rect) -> None:
        """A hole without copper: tracks and vias keep the hole clearance."""
        reach = self.rules.hole_clearance + self.rules.grid_allowance
        for layer in BOTH_LAYERS:
            self._claim_rect(self._track_cells[layer], rect, self._half_track + reach, _CLOSED)
        self._claim_rect(self._via_cells, rect, self._via_radius + reach, _CLOSED)

    def add_keepout(self, rect: Rect, layers: Iterable[int]) -> None:
        """No tracks on these layers inside the rectangle, and no vias."""
        for layer in layers:
            self._claim_rect(self._track_cells[layer], rect, 0.0, _CLOSED)
        self._claim_rect(self._via_cells, rect, 0.0, _CLOSED)

    def add_via(self, net: str, x: float, y: float) -> None:
        """A via placed by hand, already joined to its plane. The position is snapped to the grid."""
        assert self.via_fits(net, x, y), f"{net} via at ({x}, {y}) has no room"
        self._add_plane_via(net, self._index_at(x, y))

    def snapped(self, x: float, y: float) -> tuple[float, float]:
        """The grid node nearest to a point."""
        return self._xy(self._index_at(x, y))

    def via_fits(self, net: str, x: float, y: float) -> bool:
        return self._via_cells[self._index_at(x, y)] in (_FREE, self._net_id(net))

    def add_via_in_pad(self, net: str, x: float, y: float) -> None:
        """The same, inside a pad of its own net: for the vias in a chip's exposed pad."""
        self._add_plane_via(net, self._index_at(x, y))

    def _add_plane_via(self, net: str, index: int) -> None:
        self._commit_via(net, index)
        self._plane_tree.setdefault(net, set()).update((layer, index) for layer in BOTH_LAYERS)

    def _index_at(self, x: float, y: float) -> int:
        return round(y / self._pitch) * self._columns + round(x / self._pitch)

    def _close_board_edge(self, corner_radius: float) -> None:
        track_inset = self.rules.edge_clearance + self._half_track + self.rules.grid_allowance
        via_inset = self.rules.edge_clearance + self._via_radius + self.rules.grid_allowance
        for cells, inset in ((self._track_cells[FRONT], track_inset), (self._track_cells[BACK], track_inset),
                             (self._via_cells, via_inset)):
            self._close_outside_rounded_rectangle(cells, inset, corner_radius)

    def _close_outside_rounded_rectangle(self, cells: array, inset: float, corner_radius: float) -> None:
        pitch, width, height = self._pitch, self.board_width, self.board_height
        band = math.ceil(max(inset, corner_radius) / pitch) + 1
        for row in range(self._rows):
            y = row * pitch
            near_horizontal_edge = row < band or row >= self._rows - band
            columns = range(self._columns) if near_horizontal_edge else (
                list(range(band)) + list(range(self._columns - band, self._columns)))
            for column in columns:
                x = column * pitch
                # Distance into the board, measured from the rounded outline.
                dx = max(corner_radius - x, x - (width - corner_radius), 0.0)
                dy = max(corner_radius - y, y - (height - corner_radius), 0.0)
                if dx > 0 and dy > 0:
                    depth = corner_radius - math.hypot(dx, dy)
                else:
                    depth = min(x, width - x, y, height - y)
                if depth < inset:
                    cells[row * self._columns + column] = _CLOSED

    def _net_id(self, net: str) -> int:
        return self._net_ids.setdefault(net, len(self._net_ids) + 1)

    def _row_range(self, low: float, high: float) -> range:
        return range(max(0, math.ceil(low / self._pitch - 1e-9)),
                     min(self._rows - 1, math.floor(high / self._pitch + 1e-9)) + 1)

    def _column_range(self, low: float, high: float) -> range:
        return range(max(0, math.ceil(low / self._pitch - 1e-9)),
                     min(self._columns - 1, math.floor(high / self._pitch + 1e-9)) + 1)

    def _nodes_in(self, rect: Rect) -> list[int]:
        left, top, right, bottom = rect
        return [row * self._columns + column
                for row in self._row_range(top, bottom) for column in self._column_range(left, right)]

    def _claim_rect(self, cells: array, rect: Rect, reach: float, owner: int) -> None:
        """Claims every node closer than `reach` to the rectangle (or inside it)."""
        left, top, right, bottom = rect
        pitch, reach_squared = self._pitch, reach * reach + 1e-12
        for row in self._row_range(top - reach, bottom + reach):
            y = row * pitch
            dy = max(top - y, y - bottom, 0.0)
            base = row * self._columns
            for column in self._column_range(left - reach, right + reach):
                x = column * pitch
                dx = max(left - x, x - right, 0.0)
                if dx * dx + dy * dy <= reach_squared:
                    _claim(cells, base + column, owner)

    def _claim_segment(self, cells: array, start: tuple[float, float], end: tuple[float, float],
                       reach: float, owner: int) -> None:
        (x1, y1), (x2, y2) = start, end
        pitch, reach_squared = self._pitch, reach * reach
        span_x, span_y = x2 - x1, y2 - y1
        span_squared = span_x * span_x + span_y * span_y
        for row in self._row_range(min(y1, y2) - reach, max(y1, y2) + reach):
            y = row * pitch
            base = row * self._columns
            for column in self._column_range(min(x1, x2) - reach, max(x1, x2) + reach):
                x = column * pitch
                along = 0.0 if span_squared == 0 else max(
                    0.0, min(1.0, ((x - x1) * span_x + (y - y1) * span_y) / span_squared))
                dx, dy = x - (x1 + along * span_x), y - (y1 + along * span_y)
                if dx * dx + dy * dy < reach_squared:
                    _claim(cells, base + column, owner)

    # --- queries ------------------------------------------------------------------------------

    def _xy(self, index: int) -> tuple[float, float]:
        row, column = divmod(index, self._columns)
        return round(column * self._pitch, 4), round(row * self._pitch, 4)

    def pad_nodes(self, pad: Pad) -> set[tuple[int, int]]:
        indices = self._nodes_in(pad.rect)
        assert indices, f"{pad.name}: no grid node inside the pad"
        return {(layer, index) for layer in pad.layers for index in indices}

    def net_length(self, net: str) -> float:
        return sum(track.length for track in self.tracks if track.net == net)

    # --- routing ------------------------------------------------------------------------------

    def route_net(self, net: str, pads: list[Pad], wide: bool = False) -> list[str]:
        """Joins the pads into one tree, nearest pad first. Returns the names of pads it could not reach."""
        tree = self._tree.setdefault(net, set())
        waiting = [pad for pad in pads if pad.name not in self._escaped]
        if not tree:
            tree |= self.pad_nodes(waiting.pop(0))
        joined_centres = [pad.centre for pad in pads if pad not in waiting] or [pads[0].centre]
        unreached = []
        while waiting:
            nearest = min(waiting, key=lambda pad: min(math.dist(pad.centre, c) for c in joined_centres))
            waiting.remove(nearest)
            path = self._route_to_pad(net, tree, nearest, wide)
            if path is None:
                unreached.append(nearest.name)
                continue
            tree.update(self._indexed(path))
            tree.update(self.pad_nodes(nearest))
            joined_centres.append(nearest.centre)
            if path and net in self._open_escapes:
                self._trim_escape(net, path[0])
        return unreached

    def route_pair(self, net: str, first: Pad, second: Pad, wide: bool = False) -> bool:
        """One direct connection between two pads. It does not become part of the net's tree."""
        return self._route_to_pad(net, self.pad_nodes(first), second, wide) is not None

    def route_to_via(self, net: str, pads: list[Pad], via: Via, wide: bool = False) -> bool:
        """Joins the pads' copper to a via that is already there, on either layer."""
        sources = set().union(*(self.pad_nodes(pad) for pad in pads))
        target = Pad("via", net, (via.x, via.y, via.x, via.y), BOTH_LAYERS)
        return self._route_to_pad(net, sources, target, wide) is not None

    def _route_to_pad(self, net: str, sources: set[tuple[int, int]], target: Pad, wide: bool) -> list[Node] | None:
        """Writes the copper from any source node to the pad. Returns the path, empty if they already touch."""
        target_nodes = self.pad_nodes(target)
        if sources & target_nodes:
            return []
        left, top, right, bottom = (round(v / self._pitch) for v in target.rect)
        target_layers = target.layers

        def remaining(layer: int, column: int, row: int) -> int:
            dx = max(left - column, column - right, 0)
            dy = max(top - row, row - bottom, 0)
            estimate = _STRAIGHT_COST * max(dx, dy) + (_DIAGONAL_COST - _STRAIGHT_COST) * min(dx, dy)
            return estimate if layer in target_layers else estimate + _VIA_COST

        path = self._search(net, sources, target_nodes.__contains__, remaining, wide, vias_allowed=True)
        if path is not None:
            self._commit(net, path, wide)
        return path

    def _indexed(self, path: list[Node]) -> list[tuple[int, int]]:
        return [(layer, row * self._columns + column) for layer, column, row in path]

    def escape(self, net: str, pad: Pad, centre: tuple[float, float], distance: float) -> bool:
        """Shortest way from a pad out of the square of half-side `distance` around `centre`.

        The rest of the net then leaves this track wherever it likes, and the unused end is cut off.
        """
        centre_column, centre_row = round(centre[0] / self._pitch), round(centre[1] / self._pitch)
        reach = round(distance / self._pitch)

        def steps_to_go(column: int, row: int) -> int:
            return max(0, reach - max(abs(column - centre_column), abs(row - centre_row)))

        def is_outside(node: tuple[int, int]) -> bool:
            row, column = divmod(node[1], self._columns)
            return steps_to_go(column, row) == 0

        path = self._search(net, self.pad_nodes(pad), is_outside,
                            lambda layer, column, row: _STRAIGHT_COST * steps_to_go(column, row),
                            wide=False, vias_allowed=True)
        if path is None:
            return False
        tracks, vias = self._commit(net, path, wide=False)
        self._open_escapes[net] = (path, tracks, vias)
        self._tree[net] = set(self._indexed(path))
        self._escaped.add(pad.name)
        return True

    def _trim_escape(self, net: str, branch: Node) -> None:
        """Cuts the escape track back to the node where the rest of the net left it."""
        path, tracks, vias = self._open_escapes.pop(net)
        if branch not in path:
            return
        kept = path[:path.index(branch) + 1]
        for track in tracks:
            self.tracks.remove(track)
        for via in vias:
            self.vias.remove(via)
        kept_tracks, kept_vias = self._copper(net, kept, wide=False)
        self.tracks += kept_tracks
        self.vias += kept_vias
        self._tree[net] -= set(self._indexed(path[len(kept):]))

    def has_escaped(self, pad: Pad) -> bool:
        return pad.name in self._escaped

    def fan_out(self, net: str, pad: Pad, plane_here: Callable[[float, float], bool], wide: bool = False) -> bool:
        """Short track from a surface pad to a new via into the net's plane, or to copper that has one."""
        connected = self._plane_tree.setdefault(net, set())
        pad_nodes = self.pad_nodes(pad)
        if pad_nodes & connected:
            return True
        net_id = self._net_id(net)
        via_cells = self._via_cells

        def reaches_plane(node: tuple[int, int]) -> bool:
            return node in connected

        def via_fits(index: int) -> bool:
            return via_cells[index] in (_FREE, net_id) and plane_here(*self._xy(index))

        path = self._search(net, pad_nodes, reaches_plane, lambda *_: 0, wide, vias_allowed=False,
                            via_fits=via_fits)
        if path is None:
            return False
        ends_on_new_via = path[-1][0] < 0
        if ends_on_new_via:
            path.pop()
        self._commit(net, path, wide)
        last_layer, last_column, last_row = path[-1]
        if ends_on_new_via:
            self._commit_via(net, last_row * self._columns + last_column)
        connected.update(pad_nodes)
        connected.update(self._indexed(path))
        return True

    def _search(self, net: str, sources: Iterable[tuple[int, int]], is_target: Callable[[tuple[int, int]], bool],
                remaining: Callable[[int, int, int], int], wide: bool, vias_allowed: bool,
                via_fits: Callable[[int], bool] | None = None) -> list[Node] | None:
        """A* over (layer, node, heading). With `via_fits`, a node where a via fits is also a target,
        at the price of one via; the returned path then ends with a marker node on layer -1."""
        net_id = self._net_id(net)
        columns = self._columns
        node_count = columns * self._rows
        cells_by_layer = self._track_cells
        via_cells = self._via_cells
        offsets = [dy * columns + dx for dx, dy in _STEPS]
        open_to_net = (_FREE, net_id)
        neighbours = offsets if wide else []

        def greedy(estimate: int) -> int:
            return estimate * _GREED_NUMERATOR // _GREED_DENOMINATOR

        best: dict[int, int] = {}
        parent: dict[int, int] = {}
        queue: list[tuple[int, int, int]] = []
        for layer, index in sorted(sources):
            state = (layer * node_count + index) * _HEADINGS + _NO_HEADING
            start_cost = self._cost_from_pad_centre(layer, index)
            best[state] = start_cost
            row, column = divmod(index, columns)
            queue.append((start_cost + greedy(remaining(layer, column, row)), start_cost, state))
        heapq.heapify(queue)
        via_marker_base = 2 * node_count * _HEADINGS

        expansions = 0
        while queue:
            _, cost, state = heapq.heappop(queue)
            if state >= via_marker_base:
                return self._trace_back(parent, parent[state]) + [(-1, 0, 0)]
            if cost > best[state]:
                continue
            located, heading = divmod(state, _HEADINGS)
            layer, index = divmod(located, node_count)
            if is_target((layer, index)):
                return self._trace_back(parent, state)
            expansions += 1
            if expansions > _SEARCH_LIMIT:
                return None
            cells = cells_by_layer[layer]
            for direction in range(8):
                if heading == _NO_HEADING:
                    turn_cost = 0
                else:
                    turn = (direction - heading) % 8
                    turn = min(turn, 8 - turn)
                    if turn > 2:
                        continue
                    turn_cost = _TURN_COST[turn]
                next_index = index + offsets[direction]
                if cells[next_index] not in open_to_net:
                    continue
                if wide and any(cells[next_index + offset] not in open_to_net for offset in neighbours):
                    continue
                step_cost = _DIAGONAL_COST if direction % 2 else _STRAIGHT_COST
                next_cost = cost + step_cost + turn_cost
                next_state = (layer * node_count + next_index) * _HEADINGS + direction
                if next_cost < best.get(next_state, 1 << 60):
                    best[next_state] = next_cost
                    parent[next_state] = state
                    row, column = divmod(next_index, columns)
                    heapq.heappush(queue, (next_cost + greedy(remaining(layer, column, row)), next_cost, next_state))
            if via_fits is not None and via_fits(index):
                marker = via_marker_base + index
                if cost + _OWN_VIA_COST < best.get(marker, 1 << 60):
                    best[marker] = cost + _OWN_VIA_COST
                    parent[marker] = state
                    heapq.heappush(queue, (cost + _OWN_VIA_COST, cost + _OWN_VIA_COST, marker))
            if vias_allowed and via_cells[index] in open_to_net:
                other = 1 - layer
                if cells_by_layer[other][index] in open_to_net:
                    next_state = (other * node_count + index) * _HEADINGS + _NO_HEADING
                    next_cost = cost + _VIA_COST
                    if next_cost < best.get(next_state, 1 << 60):
                        best[next_state] = next_cost
                        parent[next_state] = state
                        row, column = divmod(index, columns)
                        heapq.heappush(queue, (next_cost + greedy(remaining(other, column, row)), next_cost, next_state))
        return None

    def _cost_from_pad_centre(self, layer: int, index: int) -> int:
        """Start cost of a source node on a pad, so that a path leaves the pad as if from its centre."""
        centre = self._pad_centre.get((layer, index))
        if centre is None:
            return 0
        return round(_STRAIGHT_COST * math.dist(self._xy(index), centre) / self._pitch)

    def _trace_back(self, parent: dict[int, int], state: int) -> list[Node]:
        node_count = self._columns * self._rows
        path = []
        while True:
            layer, index = divmod(state // _HEADINGS, node_count)
            row, column = divmod(index, self._columns)
            path.append((layer, column, row))
            if state not in parent:
                break
            state = parent[state]
        path.reverse()
        return path

    # --- writing copper -----------------------------------------------------------------------

    def _commit(self, net: str, path: list[Node], wide: bool) -> tuple[list[Track], list[Via]]:
        """Adds the path's copper to the board and closes the nodes around it to other nets."""
        tracks, vias = self._copper(net, path, wide)
        for track in tracks:
            self._commit_track(track)
        for via in vias:
            self._commit_via(net, self._index_at(via.x, via.y))
        return tracks, vias

    def _copper(self, net: str, path: list[Node], wide: bool) -> tuple[list[Track], list[Via]]:
        """The tracks and vias that draw a path."""
        width = self.rules.wide_track_width if wide else self.rules.track_width
        corners = self._corners(path)
        tracks, vias = [], []
        for (layer, start), (next_layer, end) in zip(corners, corners[1:]):
            if layer != next_layer:
                vias.append(Via(net, *start))
            elif start != end:
                tracks.append(Track(net, layer, start, end, width))
        return tracks, vias

    def _corners(self, path: list[Node]) -> list[tuple[int, tuple[float, float]]]:
        """The path as corner points, with a stub to the pad centre at each end that sits on a pad."""
        points = [(layer, (round(column * self._pitch, 4), round(row * self._pitch, 4)))
                  for layer, column, row in path]
        first_layer, first_column, first_row = path[0]
        last_layer, last_column, last_row = path[-1]
        first_centre = self._pad_centre.get((first_layer, first_row * self._columns + first_column))
        last_centre = self._pad_centre.get((last_layer, last_row * self._columns + last_column))
        if first_centre is not None and first_centre != points[0][1]:
            points.insert(0, (first_layer, first_centre))
        if last_centre is not None and last_centre != points[-1][1]:
            points.append((last_layer, last_centre))
        corners = [points[0]]
        for previous, current, following in zip(points, points[1:], points[2:]):
            same_layer = previous[0] == current[0] == following[0]
            if not (same_layer and _collinear(previous[1], current[1], following[1])):
                corners.append(current)
        if len(points) > 1:
            corners.append(points[-1])
        return corners

    def _commit_track(self, track: Track) -> None:
        owner = self._net_id(track.net)
        half_width = track.width / 2
        self._claim_segment(self._track_cells[track.layer], track.start, track.end,
                            half_width + self._track_reach, owner)
        self._claim_segment(self._via_cells, track.start, track.end, half_width + self._via_reach, owner)
        self.tracks.append(track)

    def _commit_via(self, net: str, index: int) -> None:
        owner = self._net_id(net)
        x, y = self._xy(index)
        spot = (x, y, x, y)
        for layer in BOTH_LAYERS:
            self._claim_rect(self._track_cells[layer], spot, self._via_radius + self._track_reach, owner)
        self._claim_rect(self._via_cells, spot, self._via_radius + self._via_reach, owner)
        self._claim_rect(self._via_cells, spot, self.rules.via_diameter + self.rules.via_to_via_gap, _CLOSED)
        self.vias.append(Via(net, x, y))


def _claim(cells: array, index: int, owner: int) -> None:
    current = cells[index]
    if current == _FREE:
        cells[index] = owner
    elif current != owner:
        cells[index] = _CLOSED


def _collinear(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    return abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) < 1e-9
