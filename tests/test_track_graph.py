"""The graph checker against the record, and on hand-made courses it must fail (s44-t2).

Path: traxgen/tests/test_track_graph.py
"""

from __future__ import annotations

import hashlib

import pytest

from traxgen.domain import Course
from traxgen.graph import (
    MEASURED_FINISHES,
    MEASURED_RUNS,
    MeasuredRun,
    PlacedTile,
    goal_rotation_for,
)
from traxgen.hex import HEX_DIRECTIONS, HexVector
from traxgen.layout import TilePlacement, build_course
from traxgen.serializer import serialize_course
from traxgen.track_graph import (
    PIECE_RULES,
    Board,
    Doorway,
    Through,
    TrackStatus,
    check_course,
)
from traxgen.types import TileKind

ORIGIN_PLATE = (HexVector(y=0, x=0),)


def cell_course(run: MeasuredRun, direction: int, goal_rotation: int) -> Course:
    """A recorded row's starter, a GOAL_RAIL one step in `direction`; `finish_record`'s course.

    Rebuilt here rather than imported, so the test does not depend on `scripts/` (plan item 16).
    """
    plates = [HexVector(y=y, x=x) for y, x in run.plate_offsets]
    sy, sx = run.starter_local_pos
    dy, dx = HEX_DIRECTIONS[direction]
    goal_world = plates[0] + HexVector(y=sy + dy, x=sx + dx)
    offset = run.goal_plate_offset
    goal_plate = 0 if offset is None else run.plate_offsets.index(offset)
    return build_course(
        plate_world_positions=plates,
        tiles=(
            TilePlacement(run.starter_kind, 0, HexVector(y=sy, x=sx), run.starter_rot),
            TilePlacement(
                run.goal_kind, goal_plate, goal_world - plates[goal_plate], goal_rotation
            ),
        ),
        title=f"traxgen-finish r{MEASURED_RUNS.index(run):02d}-d{direction}",
    )


def test_every_measured_finish_is_reproduced() -> None:
    """17 VALID and 3 INVALID, each on the exact course that was played (its sha256 first)."""
    verdicts = {}
    for entry in MEASURED_FINISHES:
        course = cell_course(entry.run, entry.direction, goal_rotation_for(entry.direction))
        assert hashlib.sha256(serialize_course(course)).hexdigest() == entry.course_sha256
        verdicts[entry] = check_course(course).status
    for entry, status in verdicts.items():
        expected = TrackStatus.VALID if entry.finished else TrackStatus.INVALID
        assert status is expected, (entry.share_code, status)
    statuses = list(verdicts.values())
    assert statuses.count(TrackStatus.VALID) == 17
    assert statuses.count(TrackStatus.INVALID) == 3


def test_no_placement_dark_cell_reads_valid() -> None:
    """Every probed cell the record calls dark, at every goal rotation it rendered, is not VALID."""
    checked = 0
    for run in MEASURED_RUNS:
        for direction in sorted(run.directions_probed):
            rotations = range(6) if run.goal_rotations_swept else (goal_rotation_for(direction),)
            for rotation in rotations:
                if direction in run.live_directions and rotation == goal_rotation_for(direction):
                    continue
                verdict = check_course(cell_course(run, direction, rotation))
                assert verdict.status is not TrackStatus.VALID, (
                    run.provenance,
                    direction,
                    rotation,
                )
                checked += 1
    assert checked > 100  # the corner sweeps alone are 36-cell grids


def course_of(*tiles: tuple[TileKind, tuple[int, int], int]) -> Course:
    """One lone plate holding `tiles`, each (kind, local (y, x), rotation)."""
    return build_course(
        plate_world_positions=ORIGIN_PLATE,
        tiles=tuple(TilePlacement(k, 0, HexVector(y=y, x=x), r) for k, (y, x), r in tiles),
    )


def test_a_starter_alone_is_a_dead_end() -> None:
    verdict = check_course(course_of((TileKind.STARTER, (-3, 2), 0)))
    assert verdict.status is TrackStatus.INVALID
    assert "dead end" in verdict.reason


def test_a_goal_turned_away_is_a_dead_end_at_its_doorway() -> None:
    """Phase 1's geometry with the goal one rotation off: the marble reaches it, is not caught."""
    verdict = check_course(
        course_of((TileKind.STARTER, (0, 0), 0), (TileKind.GOAL_RAIL, (-1, 0), 4))
    )
    assert verdict.status is TrackStatus.INVALID
    assert verdict.at == Doorway(cell=HexVector(y=-1, x=0), side=5)


def test_the_phase_1_course_is_valid() -> None:
    verdict = check_course(
        course_of((TileKind.STARTER, (0, 0), 0), (TileKind.GOAL_RAIL, (-1, 0), 3))
    )
    assert verdict.status is TrackStatus.VALID


def test_a_piece_with_no_rule_makes_the_course_unmeasured() -> None:
    course = course_of(
        (TileKind.STARTER, (0, 0), 0),
        (TileKind.GOAL_RAIL, (-1, 0), 3),
        (TileKind.CURVE, (-4, 3), 0),
    )
    verdict = check_course(course)
    assert verdict.status is TrackStatus.UNMEASURED
    assert "CURVE" in verdict.reason


def test_two_pieces_on_the_starter_are_unmeasured() -> None:
    """Which way the marbles leave depends on where they sit in the starter (Colby, s44)."""
    course = course_of(
        (TileKind.STARTER, (-3, 2), 0),
        (TileKind.GOAL_RAIL, (-3, 3), goal_rotation_for(0)),
        (TileKind.GOAL_RAIL, (-4, 2), goal_rotation_for(2)),
    )
    assert check_course(course).status is TrackStatus.UNMEASURED


def test_a_goal_on_a_completed_half_hole_is_caught() -> None:
    """The half-hole term reads the layout: with the completing plate present, (0,1) catches."""
    course = build_course(
        plate_world_positions=(HexVector(y=0, x=0), HexVector(y=5, x=0)),
        tiles=(
            TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
            TilePlacement(TileKind.GOAL_RAIL, 0, HexVector(y=0, x=1), goal_rotation_for(0)),
        ),
    )
    assert check_course(course).status is TrackStatus.VALID


# --- A loop, with a test piece the record has not measured ---------------------

CENTRE = HexVector(y=-3, x=2)
RING = tuple(CENTRE.neighbor(d) for d in range(6))


def ring_rule(tile: PlacedTile, entered: int | None, board: Board) -> Through:
    """Test piece: leaves toward the next cell of the ring around CENTRE, whatever it entered by."""
    i = RING.index(tile.world_pos)
    side = tile.world_pos.direction_to(RING[(i + 1) % 6])
    assert side is not None
    return Through(exits=frozenset({side}))


def test_a_ring_of_pieces_is_a_loop_named_at_its_doorway() -> None:
    """The starter feeds RING[0] from outside; the ring hands the marble round and back to RING[0].

    The walk has to *detect* the loop: stopping early would read VALID or a dead end instead.
    """
    starter = CENTRE + HexVector(y=2 * HEX_DIRECTIONS[0][0], x=2 * HEX_DIRECTIONS[0][1])
    into_ring = starter.direction_to(RING[0])
    assert into_ring is not None and into_ring % 2 == 1  # an odd starter rotation faces it
    others = [starter.neighbor(d) for d in ((into_ring + 2) % 6, (into_ring + 4) % 6)]
    assert not set(others) & set(RING)  # only one piece attached to the starter
    course = course_of(
        (TileKind.STARTER, (starter.y, starter.x), 1),
        *((TileKind.CURVE, (c.y, c.x), 0) for c in RING),
    )
    verdict = check_course(course, rules={**PIECE_RULES, TileKind.CURVE: ring_rule})
    assert verdict.status is TrackStatus.INVALID
    assert verdict.reason.startswith("loop")
    # RING[0] is entered twice by *different* sides (from the starter, then from
    # RING[5]), so that is not yet a repeat. The first doorway crossed twice the
    # same way is RING[0] -> RING[1].
    first_step = RING[0].direction_to(RING[1])
    assert first_step is not None
    assert verdict.at == Doorway(cell=RING[1], side=(first_step + 3) % 6)


def test_without_the_ring_rule_the_same_course_is_unmeasured() -> None:
    """Control for the loop test: the loop comes from the injected rule, not from the course."""
    starter = CENTRE + HexVector(y=2 * HEX_DIRECTIONS[0][0], x=2 * HEX_DIRECTIONS[0][1])
    course = course_of(
        (TileKind.STARTER, (starter.y, starter.x), 1),
        *((TileKind.CURVE, (c.y, c.x), 0) for c in RING),
    )
    assert check_course(course).status is TrackStatus.UNMEASURED


@pytest.mark.parametrize("rotation", range(6))
def test_a_starter_with_nothing_attached_is_invalid_at_every_rotation(rotation: int) -> None:
    assert (
        check_course(course_of((TileKind.STARTER, (-3, 2), rotation))).status is TrackStatus.INVALID
    )
