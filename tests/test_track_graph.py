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
from traxgen.plates import is_buildable_on_plate
from traxgen.serializer import serialize_course
from traxgen.track_graph import (
    PIECE_RULES,
    Board,
    Doorway,
    Through,
    TrackStatus,
    check_course,
)
from traxgen.types import LayerKind, TileKind

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


def test_a_starter_alone_loads_no_marble() -> None:
    verdict = check_course(course_of((TileKind.STARTER, (-3, 2), 0)))
    assert verdict.status is TrackStatus.INVALID
    assert "no marble loads" in verdict.reason


def test_a_goal_turned_away_is_no_connection() -> None:
    """Phase 1's geometry with the goal one rotation off: the marble reaches it, is not caught."""
    verdict = check_course(
        course_of((TileKind.STARTER, (0, 0), 0), (TileKind.GOAL_RAIL, (-1, 0), 4))
    )
    assert verdict.status is TrackStatus.INVALID
    assert verdict.reason == "no valid connection to the starter: no marble loads"


def test_the_phase_1_course_is_valid() -> None:
    verdict = check_course(
        course_of((TileKind.STARTER, (0, 0), 0), (TileKind.GOAL_RAIL, (-1, 0), 3))
    )
    assert verdict.status is TrackStatus.VALID


def test_a_piece_with_no_rule_makes_the_course_unmeasured() -> None:
    course = course_of(
        (TileKind.STARTER, (0, 0), 0),
        (TileKind.GOAL_RAIL, (-1, 0), 3),
        (TileKind.THREEWAY, (-4, 3), 0),
    )
    verdict = check_course(course)
    assert verdict.status is TrackStatus.UNMEASURED
    assert "THREEWAY" in verdict.reason


def test_two_valid_connections_are_two_routes_both_caught() -> None:
    """Each valid connection on the starter is a route of its own (Colby, s44)."""
    course = course_of(
        (TileKind.STARTER, (-3, 2), 0),
        (TileKind.GOAL_RAIL, (-3, 3), goal_rotation_for(0)),
        (TileKind.GOAL_RAIL, (-4, 2), goal_rotation_for(2)),
    )
    assert check_course(course).status is TrackStatus.VALID


def test_a_second_route_that_dead_ends_fails_the_course() -> None:
    """Side 0 reaches a goal and is walked first; side 2 runs off the plate and fails it."""
    course = course_of(
        (TileKind.STARTER, (-3, 2), 0),
        (TileKind.GOAL_RAIL, (-3, 3), goal_rotation_for(0)),
        (TileKind.CURVE, (-4, 2), 0),
    )
    rules = {
        **PIECE_RULES,
        TileKind.CURVE: lambda tile, entered, board: Through(exits=frozenset({2})),
    }
    verdict = check_course(course, rules=rules)
    assert verdict.status is TrackStatus.INVALID
    assert verdict.at == Doorway(cell=HexVector(y=-5, x=2), side=5)


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
        *((TileKind.THREEWAY, (c.y, c.x), 0) for c in RING),
    )
    verdict = check_course(course, rules={**PIECE_RULES, TileKind.THREEWAY: ring_rule})
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
        *((TileKind.THREEWAY, (c.y, c.x), 0) for c in RING),
    )
    assert check_course(course).status is TrackStatus.UNMEASURED


@pytest.mark.parametrize("rotation", range(6))
def test_a_starter_with_nothing_attached_is_invalid_at_every_rotation(rotation: int) -> None:
    assert (
        check_course(course_of((TileKind.STARTER, (-3, 2), rotation))).status is TrackStatus.INVALID
    )


def test_a_valid_connection_beside_a_wrong_way_goal_is_valid() -> None:
    """The marble loads on the valid connection only (Colby, s44): the wrong-way goal is not one."""
    course = course_of(
        (TileKind.STARTER, (-3, 2), 0),
        (TileKind.GOAL_RAIL, (-3, 3), goal_rotation_for(0)),
        (TileKind.GOAL_RAIL, (-4, 2), (goal_rotation_for(2) + 1) % 6),
    )
    assert check_course(course).status is TrackStatus.VALID


def test_the_half_hole_misses_are_dead_ends_at_the_goal_not_no_connection() -> None:
    """A goal on an uncompleted half-hole is a connection: the marble rolls in and is not caught."""
    misses = [e for e in MEASURED_FINISHES if not e.finished]
    assert len(misses) == 3
    for entry in misses:
        verdict = check_course(
            cell_course(entry.run, entry.direction, goal_rotation_for(entry.direction))
        )
        assert verdict.reason.startswith("dead end"), verdict.reason
        assert verdict.at == Doorway(cell=HexVector(y=0, x=1), side=3)


def straight_east_rule(tile: PlacedTile, entered: int | None, board: Board) -> Through:
    """Test piece: whatever it was entered by, it leaves by side 0 (E)."""
    return Through(exits=frozenset({0}))


def test_a_route_into_a_wrong_way_goal_names_the_goal() -> None:
    """Mid-route, a goal turned away is a dead end at its own doorway, said as 'no way in'."""
    course = course_of(
        (TileKind.STARTER, (-3, 2), 0),
        (TileKind.CURVE, (-3, 3), 0),
        (TileKind.GOAL_RAIL, (-3, 4), (goal_rotation_for(0) + 1) % 6),
    )
    verdict = check_course(course, rules={**PIECE_RULES, TileKind.CURVE: straight_east_rule})
    assert verdict.status is TrackStatus.INVALID
    assert verdict.reason == "dead end: GOAL_RAIL has no way in here"
    assert verdict.at == Doorway(cell=HexVector(y=-3, x=4), side=3)


# --- CURVE, measured on Colby's board 7UNB5OAAOT (s45) -------------------------

CURVE_CELL = HexVector(y=-3, x=2)  # every neighbour is on a lone plate, none a half-hole
CURVE_STARTER = CURVE_CELL.neighbor(5)  # the curve one step NW of the pad, as on the board
# The board's rows: curve rotation -> the world side the marble left by (None: no marble).
CURVE_BOARD_ROWS: dict[int, int | None] = {0: None, 5: 1, 3: 3, 2: 0, 1: 4, 4: None}


def test_the_curve_cell_and_its_ring_are_buildable() -> None:
    cells = [CURVE_CELL, *(CURVE_CELL.neighbor(d) for d in range(6))]
    assert all(is_buildable_on_plate(LayerKind.BASE_LAYER_PIECE, c) for c in cells)


def curve_ring(rotation: int) -> Course:
    """The launch pad feeding a curve, and a goal facing it on each of its other five sides."""
    goals = [
        (TileKind.GOAL_RAIL, (c.y, c.x), goal_rotation_for(d))
        for d in range(5)
        for c in (CURVE_CELL.neighbor(d),)
    ]
    return course_of(
        (TileKind.STARTER, (CURVE_STARTER.y, CURVE_STARTER.x), 0),
        (TileKind.CURVE, (CURVE_CELL.y, CURVE_CELL.x), rotation),
        *goals,
    )


def curve_with_one_goal(rotation: int, side: int) -> Course:
    """The launch pad, the curve, and a single goal facing the curve on `side`."""
    goal = CURVE_CELL.neighbor(side)
    return course_of(
        (TileKind.STARTER, (CURVE_STARTER.y, CURVE_STARTER.x), 0),
        (TileKind.CURVE, (CURVE_CELL.y, CURVE_CELL.x), rotation),
        (TileKind.GOAL_RAIL, (goal.y, goal.x), goal_rotation_for(side)),
    )


@pytest.mark.parametrize("rotation", sorted(CURVE_BOARD_ROWS))
def test_each_board_row_leaves_by_its_measured_side_and_no_other(rotation: int) -> None:
    """One goal at a time on each of the five free sides: only the measured side is VALID.

    A single goal, not the ring, so a wrong exit cannot hide behind another goal catching it.
    """
    exit_side = CURVE_BOARD_ROWS[rotation]
    for side in range(5):
        verdict = check_course(curve_with_one_goal(rotation, side))
        if side == exit_side:
            assert verdict.status is TrackStatus.VALID, (rotation, side, verdict)
        else:
            assert verdict.status is TrackStatus.INVALID, (rotation, side, verdict)


@pytest.mark.parametrize("rotation", sorted(CURVE_BOARD_ROWS))
def test_the_ring_is_valid_exactly_where_a_marble_loads(rotation: int) -> None:
    """QTOVZBN3AV's shape at every rotation: a closed side facing the pad loads no marble."""
    verdict = check_course(curve_ring(rotation))
    if CURVE_BOARD_ROWS[rotation] is None:
        assert verdict.status is TrackStatus.INVALID
        assert verdict.reason == "no valid connection to the starter: no marble loads"
    else:
        assert verdict.status is TrackStatus.VALID, verdict


def test_a_curve_ridden_into_from_a_goal_side_reads_the_track_both_ways() -> None:
    """Gentle track entered by side 2 leaves by 0, and the sharp one entered by 3 leaves by 4."""
    tile = PlacedTile(
        kind=TileKind.CURVE,
        world_pos=CURVE_CELL,
        local_pos=CURVE_CELL,
        hex_rotation=1,
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        layer_id=1,
    )
    board = Board(plate_positions=frozenset({(0, 0)}))
    rule = PIECE_RULES[TileKind.CURVE]
    assert rule(tile, (2 + 1) % 6, board).exits == frozenset({(0 + 1) % 6})
    assert rule(tile, (3 + 1) % 6, board).exits == frozenset({(4 + 1) % 6})
    assert not rule(tile, (1 + 1) % 6, board).accepts
    assert not rule(tile, (5 + 1) % 6, board).accepts
    assert not rule(tile, None, board).accepts


# --- CROSS, measured on the ring board YFUGDSMDUH (s47-t4) ---------------------

# The board's rows: cross rotation -> the world side the marble left by (None: no marble).
# The launch pad sits on the piece's world side 5, so it enters by its own side (5 - r) % 6.
CROSS_BOARD_ROWS: dict[int, int | None] = {0: 2, 1: 2, 2: None, 3: 2, 4: 2, 5: None}


def piece_with_one_goal(kind: TileKind, rotation: int, side: int) -> Course:
    """The launch pad, the piece at CURVE_CELL, and a single goal facing it on `side`."""
    goal = CURVE_CELL.neighbor(side)
    return course_of(
        (TileKind.STARTER, (CURVE_STARTER.y, CURVE_STARTER.x), 0),
        (kind, (CURVE_CELL.y, CURVE_CELL.x), rotation),
        (TileKind.GOAL_RAIL, (goal.y, goal.x), goal_rotation_for(side)),
    )


@pytest.mark.parametrize("rotation", sorted(CROSS_BOARD_ROWS))
def test_each_cross_row_leaves_by_its_measured_side_and_no_other(rotation: int) -> None:
    exit_side = CROSS_BOARD_ROWS[rotation]
    for side in range(5):
        verdict = check_course(piece_with_one_goal(TileKind.CROSS, rotation, side))
        if side == exit_side:
            assert verdict.status is TrackStatus.VALID, (rotation, side, verdict)
        else:
            assert verdict.status is TrackStatus.INVALID, (rotation, side, verdict)


@pytest.mark.parametrize("rotation", [r for r, s in CROSS_BOARD_ROWS.items() if s is None])
def test_a_closed_cross_side_facing_the_pad_loads_no_marble(rotation: int) -> None:
    verdict = check_course(piece_with_one_goal(TileKind.CROSS, rotation, 2))
    assert verdict.reason == "no valid connection to the starter: no marble loads"


def test_both_cross_tracks_run_both_ways_and_two_sides_stay_shut() -> None:
    """Read in the piece's own frame at rotation 1, so a world-frame table would fail."""
    tile = PlacedTile(
        kind=TileKind.CROSS,
        world_pos=CURVE_CELL,
        local_pos=CURVE_CELL,
        hex_rotation=1,
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        layer_id=1,
    )
    board = Board(plate_positions=frozenset({(0, 0)}))
    rule = PIECE_RULES[TileKind.CROSS]
    for a, b in ((1, 4), (4, 1), (2, 5), (5, 2)):
        assert rule(tile, (a + 1) % 6, board).exits == frozenset({(b + 1) % 6}), (a, b)
    for shut in (0, 3):
        assert not rule(tile, (shut + 1) % 6, board).accepts
    assert not rule(tile, None, board).accepts


# --- The switch, measured on the goal-less ring boards (s48-t3, t4) ------------

# The boards' rows: rotation -> the world side the marble left by, "stops" for a
# marble that went in and stopped against the lever, None for no marble. The
# launch pad sits on the piece's world side 5, as on the CROSS board.
SWITCH_BOARD_ROWS: dict[TileKind, dict[int, int | str | None]] = {
    TileKind.SWITCH_LEFT: {0: None, 1: "stops", 2: None, 3: 1, 4: None, 5: 1},
    TileKind.SWITCH_RIGHT: {0: None, 1: 3, 2: None, 3: 3, 4: None, 5: "stops"},
}
SWITCH_ROWS = [(k, r) for k, rows in SWITCH_BOARD_ROWS.items() for r in sorted(rows)]


@pytest.mark.parametrize(("kind", "rotation"), SWITCH_ROWS)
def test_each_switch_row_leaves_by_its_measured_side_and_no_other(
    kind: TileKind, rotation: int
) -> None:
    """One goal at a time on each free side; a stopping row is a dead end on every side."""
    row = SWITCH_BOARD_ROWS[kind][rotation]
    for side in range(5):
        verdict = check_course(piece_with_one_goal(kind, rotation, side))
        if row is None:
            assert verdict.reason == "no valid connection to the starter: no marble loads"
        elif row == "stops":
            assert verdict.status is TrackStatus.INVALID, (kind, rotation, side, verdict)
            assert verdict.reason == f"dead end: {kind.name} has no way on", verdict
        elif side == row:
            assert verdict.status is TrackStatus.VALID, (kind, rotation, side, verdict)
        else:
            assert verdict.status is TrackStatus.INVALID, (kind, rotation, side, verdict)


@pytest.mark.parametrize("kind", sorted(SWITCH_BOARD_ROWS, key=lambda k: k.name))
def test_the_switch_tables_are_in_the_pieces_own_frame(kind: TileKind) -> None:
    """Read at rotation 1, so a world-frame table fails; the two kinds are mirror images."""
    tile = PlacedTile(
        kind=kind,
        world_pos=CURVE_CELL,
        local_pos=CURVE_CELL,
        hex_rotation=1,
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        layer_id=1,
    )
    board = Board(plate_positions=frozenset({(0, 0)}))
    rule = PIECE_RULES[kind]
    passes = {0: 2, 2: 4} if kind is TileKind.SWITCH_LEFT else {4: 2, 2: 0}
    stops = 4 if kind is TileKind.SWITCH_LEFT else 0
    for a, b in passes.items():
        assert rule(tile, (a + 1) % 6, board).exits == frozenset({(b + 1) % 6}), (a, b)
    held = rule(tile, (stops + 1) % 6, board)
    assert held.accepts and not held.exits
    for shut in (1, 3, 5):
        assert not rule(tile, (shut + 1) % 6, board).accepts


def two_marbles(second: TileKind) -> Course:
    """A starter with two valid connections: a goal on side 0, and `second` on side 2.

    With a SWITCH_LEFT on side 2, entered by its branch 0, its marble passes out
    its side 2 into a goal -- so the course is VALID except for the guard.
    """
    pad = HexVector(y=-3, x=2)
    piece = pad.neighbor(2)
    tiles = [
        (TileKind.STARTER, (pad.y, pad.x), 0),
        (TileKind.GOAL_RAIL, (pad.neighbor(0).y, pad.neighbor(0).x), goal_rotation_for(0)),
    ]
    if second is TileKind.GOAL_RAIL:
        tiles.append((TileKind.GOAL_RAIL, (piece.y, piece.x), goal_rotation_for(2)))
    else:
        # Rotation 5: the pad is on the switch's world side 5, its own side 0, which passes
        # to its side 2, world side 1 -- where a goal waits.
        out = piece.neighbor(1)
        tiles += [
            (second, (piece.y, piece.x), 5),
            (TileKind.GOAL_RAIL, (out.y, out.x), goal_rotation_for(1)),
        ]
    return course_of(*tiles)


def test_two_marbles_on_a_course_with_a_switch_are_unmeasured() -> None:
    """s48-t4: with two marbles, which arrives first decides the lever."""
    verdict = check_course(two_marbles(TileKind.SWITCH_LEFT))
    assert verdict.status is TrackStatus.UNMEASURED
    assert verdict.reason.startswith("2 marbles on a course with a switch")


def test_the_two_marble_courses_are_valid_but_for_the_guard() -> None:
    """Controls: the same layout with a goal in the switch's place is VALID, and the switch's
    route alone (its own pad, no second marble) is VALID."""
    assert check_course(two_marbles(TileKind.GOAL_RAIL)).status is TrackStatus.VALID
    pad = CURVE_CELL.neighbor(5)
    out = CURVE_CELL.neighbor(1)
    alone = course_of(
        (TileKind.STARTER, (pad.y, pad.x), 0),
        (TileKind.SWITCH_LEFT, (CURVE_CELL.y, CURVE_CELL.x), 5),
        (TileKind.GOAL_RAIL, (out.y, out.x), goal_rotation_for(1)),
    )
    assert check_course(alone).status is TrackStatus.VALID


def back_round(tile: PlacedTile, entered: int | None, board: Board) -> Through:
    """Test piece: hands the marble round the ring around CENTRE, and from RING[4] into CENTRE."""
    i = RING.index(tile.world_pos)
    to = CENTRE if i == 4 else RING[(i + 1) % 6]
    side = tile.world_pos.direction_to(to)
    assert side is not None
    return Through(exits=frozenset({side}))


def test_a_route_back_into_its_own_switch_is_unmeasured() -> None:
    """SWITCH_LEFT at CENTRE, fed by its branch 0 from RING[0]; out by 2 into RING[2], round
    to RING[4], and back in by its side 4. Without the guard that is a dead end (4 stops)."""
    course = course_of(
        (TileKind.STARTER, (RING[0].y, RING[0].x), 1),
        (TileKind.SWITCH_LEFT, (CENTRE.y, CENTRE.x), 0),
        *((TileKind.THREEWAY, (c.y, c.x), 0) for c in RING[2:5]),
    )
    verdict = check_course(course, rules={**PIECE_RULES, TileKind.THREEWAY: back_round})
    assert verdict.status is TrackStatus.UNMEASURED, verdict
    assert verdict.at == Doorway(cell=CENTRE, side=4)
