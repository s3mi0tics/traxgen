"""The two-marble board: each launch pad has two valid connections, on equal routes (s50-t1).

Path: traxgen/tests/test_probe_two_marbles.py
"""

from __future__ import annotations

from itertools import combinations

import pytest

from scripts.probe_two_marbles import STARTER_PORTS, TESTS, PadTest, Placed, layout, placements
from traxgen.graph import course_plate_positions, placed_tiles
from traxgen.hex import HexVector
from traxgen.layout import build_course
from traxgen.plates import STANDARD_SQUARE
from traxgen.ring_board import hex_distance, is_buildable, under_toolbar
from traxgen.track_graph import PIECE_RULES, Board, TrackStatus, check_course
from traxgen.types import TileKind

PLATES = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)


@pytest.fixture(scope="module")
def board() -> list[tuple[PadTest, Placed]]:
    return layout(PLATES, run=2)


def accepting_ports(placed: Placed) -> list[int]:
    """The pad's ports whose neighbour takes the marble in, read through the checker's own rules."""
    course = build_course(plate_world_positions=PLATES, tiles=placements(PLATES, placed))
    tiles = {(t.world_pos.y, t.world_pos.x): t for t in placed_tiles(course)}
    pad = next(t for t in tiles.values() if t.kind is TileKind.STARTER)
    board = Board(frozenset(course_plate_positions(course)))
    out = []
    for port in STARTER_PORTS:
        cell = pad.world_pos.neighbor((port + pad.hex_rotation) % 6)
        tile = tiles.get((cell.y, cell.x))
        if tile is not None and PIECE_RULES[tile.kind](tile, (port + 3) % 6, board).accepts:
            out.append(port)
    return out


def test_one_test_per_port_pair(board: list[tuple[PadTest, Placed]]) -> None:
    assert [t.ports for t, _ in board] == [(0, 2), (2, 4), (0, 4)]
    assert [t for t, _ in board] == list(TESTS)


def test_each_pad_has_exactly_its_two_ports_connected(board: list[tuple[PadTest, Placed]]) -> None:
    """The third port faces nothing that accepts, so two marbles and no more."""
    for test, placed in board:
        assert accepting_ports(placed) == list(test.ports), test.name


def test_the_third_port_faces_an_empty_cell(board: list[tuple[PadTest, Placed]]) -> None:
    for test, placed in board:
        pad = placed[0][1]
        (third,) = set(STARTER_PORTS) - set(test.ports)
        assert pad.neighbor(third) not in {c for _, c, _ in placed}, test.name


def test_both_routes_have_the_same_length(board: list[tuple[PadTest, Placed]]) -> None:
    """Two X-intersections and a goal on each, so travel time cancels."""
    for test, placed in board:
        pad = placed[0][1]
        for side in test.ports:
            route = [pad.neighbor(side), pad.neighbor(side).neighbor(side)]
            goal = route[-1].neighbor(side)
            kinds = {c: k for k, c, _ in placed}
            assert [kinds.get(c) for c in route] == [TileKind.CROSS, TileKind.CROSS], test.name
            assert kinds.get(goal) is TileKind.GOAL_RAIL, test.name
        assert len(placed) == 7, test.name


def test_each_test_alone_checks_valid(board: list[tuple[PadTest, Placed]]) -> None:
    """VALID, not UNMEASURED: the marble guard only fires with a switch on the course."""
    for test, placed in board:
        course = build_course(plate_world_positions=PLATES, tiles=placements(PLATES, placed))
        verdict = check_course(course)
        assert verdict.status is TrackStatus.VALID, (test.name, verdict.reason)


def test_every_cell_is_buildable_and_on_screen(board: list[tuple[PadTest, Placed]]) -> None:
    for test, placed in board:
        for _, cell, _ in placed:
            assert is_buildable(PLATES, cell) and not under_toolbar(cell), (test.name, cell)


def test_tests_are_at_least_three_apart(board: list[tuple[PadTest, Placed]]) -> None:
    """Two empty cells between tests, so no marble can reach another test's piece."""
    for (a, pa), (b, pb) in combinations(board, 2):
        gap = min(hex_distance(c, d) for _, c, _ in pa for _, d, _ in pb)
        assert gap >= 3, (a.name, b.name, gap)


def test_a_run_of_three_does_not_fit_all_three() -> None:
    """Why the default is 2: the standard square holds one test at a run of 3."""
    with pytest.raises(ValueError, match="only 1 of 3"):
        layout(PLATES, run=3)
