"""The ring test board: one ring per rotation, nothing touching, every tile buildable (s46-t2).

Path: traxgen/tests/test_ring_board.py
"""

from __future__ import annotations

from itertools import combinations

import pytest

from traxgen.graph import goal_rotation_for, placed_tiles
from traxgen.hex import HexVector
from traxgen.plates import half_hole_cells, is_on_plate
from traxgen.ring_board import (
    GOAL_SIDES,
    STARTER_SIDE,
    RingBoard,
    hex_distance,
    is_buildable,
    ring_board,
    single_ring_course,
)
from traxgen.track_graph import CURVE_TRACKS, TrackStatus, check_course
from traxgen.types import LayerKind, TileKind


@pytest.fixture(scope="module")
def curve_board() -> RingBoard:
    return ring_board(TileKind.CURVE)


def test_every_rotation_gets_one_ring(curve_board: RingBoard) -> None:
    assert sorted(r.rotation for r in curve_board.rings) == list(range(6))


def test_no_two_rings_touch(curve_board: RingBoard) -> None:
    """Between any two rings there is at least one empty cell."""
    for a, b in combinations(curve_board.rings, 2):
        closest = min(hex_distance(p, q) for p in a.cells() for q in b.cells())
        assert closest >= 2, (a.rotation, b.rotation, closest)


def test_every_tile_is_on_its_plate_and_off_uncompleted_half_holes(curve_board: RingBoard) -> None:
    tiles = list(placed_tiles(curve_board.course))
    assert len(tiles) == 6 * 7
    assert len({(t.world_pos.y, t.world_pos.x) for t in tiles}) == len(tiles)
    plates = {(p.y, p.x) for p in curve_board.plates}
    for tile in tiles:
        assert is_on_plate(tile.layer_kind, tile.local_pos)
        if (tile.local_pos.y, tile.local_pos.x) in half_hole_cells(LayerKind.BASE_LAYER_PIECE):
            plate = tile.world_pos - tile.local_pos
            assert (plate.y + 5, plate.x) in plates, tile


def test_the_manifest_names_the_tiles_the_course_holds(curve_board: RingBoard) -> None:
    """Each ring read back from the course: the piece, the pad, a goal facing it per side."""
    by_cell = {(t.world_pos.y, t.world_pos.x): t for t in placed_tiles(curve_board.course)}
    for ring in curve_board.rings:
        centre = by_cell[(ring.centre.y, ring.centre.x)]
        assert (centre.kind, centre.hex_rotation) == (TileKind.CURVE, ring.rotation)
        assert ring.starter == ring.centre.neighbor(STARTER_SIDE)
        assert by_cell[(ring.starter.y, ring.starter.x)].kind is TileKind.STARTER
        assert sorted(ring.goals) == list(GOAL_SIDES)
        for side, cell in ring.goals.items():
            assert cell == ring.centre.neighbor(side)
            goal = by_cell[(cell.y, cell.x)]
            assert (goal.kind, goal.hex_rotation) == (TileKind.GOAL_RAIL, goal_rotation_for(side))


def test_each_ring_alone_reads_as_the_curve_rule_says(curve_board: RingBoard) -> None:
    """A marble loads where the pad faces a track's end (rotations 1, 2, 3, 5), and is caught."""
    for ring in curve_board.rings:
        verdict = check_course(single_ring_course(curve_board, ring))
        entered = (STARTER_SIDE - ring.rotation) % 6
        if entered in CURVE_TRACKS:
            assert verdict.status is TrackStatus.VALID, (ring.rotation, verdict)
        else:
            assert verdict.reason == "no valid connection to the starter: no marble loads"
    assert sorted(
        r.rotation for r in curve_board.rings if (STARTER_SIDE - r.rotation) % 6 in CURVE_TRACKS
    ) == [1, 2, 3, 5]


def test_too_many_rings_for_the_plates_is_refused() -> None:
    with pytest.raises(ValueError, match="rings fit"):
        ring_board(TileKind.CURVE, plate_positions=((0, 0),))


def test_hex_distance_is_one_for_every_neighbour() -> None:
    origin = HexVector(y=2, x=-3)
    assert {hex_distance(origin, origin.neighbor(d)) for d in range(6)} == {1}
    assert hex_distance(origin, origin.neighbor(0).neighbor(0).neighbor(1)) == 3


def test_a_half_hole_is_buildable_only_with_its_completing_plate() -> None:
    """The curve board never lands on one, so this is the test that holds the rule (D066)."""
    half_holes = sorted(half_hole_cells(LayerKind.BASE_LAYER_PIECE))
    assert half_holes
    lone = (HexVector(y=0, x=0),)
    completed = (HexVector(y=0, x=0), HexVector(y=5, x=0))
    for y, x in half_holes:
        assert not is_buildable(lone, HexVector(y=y, x=x))
        assert is_buildable(completed, HexVector(y=y, x=x))


def test_the_goalless_board_is_the_same_board_minus_its_goals(curve_board: RingBoard) -> None:
    """Same rings, same pieces and pads, no GOAL_RAIL: the reference frame for the reader."""
    bare = ring_board(TileKind.CURVE, goals=False)
    assert bare.rings == curve_board.rings
    full = {
        (t.world_pos.y, t.world_pos.x, t.kind, t.hex_rotation)
        for t in placed_tiles(curve_board.course)
    }
    rest = {
        (t.world_pos.y, t.world_pos.x, t.kind, t.hex_rotation) for t in placed_tiles(bare.course)
    }
    assert rest == {t for t in full if t[2] is not TileKind.GOAL_RAIL}
    assert len(full) - len(rest) == 6 * 5
