"""Tests for traxgen.graph -- the measured connection table and the track graph.

Two kinds of test live here, and the split matters:

  * Replay-of-record tests pin the module to what the sweeps measured --
    every known-active cell classifies CONNECTED, every rendered miss
    DISCONNECTED. Per observations #20 these guard against later edits
    silently rewriting the record; they are not evidence the record is right.
  * Property tests (hypothesis) state invariants over whole input spaces --
    "an unswept rotation never yields a claim", "only the rule's rotation can
    connect" -- and let the fuzzer hunt for counterexamples nobody thought to
    write down. Fixtures pin known points; strategies patrol the space
    between them.

Path: traxgen/tests/test_graph.py
"""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from scripts.sweep_starter_rotation import build_variant
from traxgen.domain import (
    Course,
    RailConstructionData,
    RailConstructionExitIdentifier,
)
from traxgen.generator import generate_minimal
from traxgen.graph import (
    GOAL_KINDS,
    MEASURED_LIVE_DIRECTIONS,
    STARTER_KINDS,
    ConnectionStatus,
    PlacedTile,
    UnsweptStarterRotationError,
    classify_pair,
    connection_status,
    goal_rotation_for,
    live_directions,
    placed_tiles,
    start_goal_status,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.types import RailKind, TileKind
from traxgen.validator import Rule, Severity, ValidationError, validate, validate_strict

# --- Strategies and shared data --------------------------------------------

directions = st.integers(min_value=0, max_value=5)
rotations = st.integers(min_value=0, max_value=5)
swept_rotations = st.sampled_from(sorted(MEASURED_LIVE_DIRECTIONS))
# All six standard rotations are now measured; what remains unmeasured is
# anything outside 0..5 (the app's modulo behaviour is open unknown #11).
unmeasured_rotations = st.sampled_from([-1, 6, 7, 42])

# Every cell ever measured active, as (starter_rot, direction, goal_rot):
# even rotations give E rot 1 + NW rot 3, odd give NE rot 2. Harness-bracketed
# exhaustive sweeps, 2026-08-07/08 (s=0, s=1) and the 2026-08-10 queue run
# (s=2..5).
MEASURED_ACTIVE = (
    (0, 0, 1), (0, 2, 3),
    (1, 1, 2),
    (2, 0, 1), (2, 2, 3),
    (3, 1, 2),
    (4, 0, 1), (4, 2, 3),
    (5, 1, 2),
)

# (starter_rot, live direction) pairs straight from the measured table.
LIVE_CELLS = [
    (s, d) for s, dirs in sorted(MEASURED_LIVE_DIRECTIONS.items()) for d in sorted(dirs)
]


# --- The goal-side rule ----------------------------------------------------


@pytest.mark.parametrize(("_s", "direction", "goal_rot"), MEASURED_ACTIVE)
def test_goal_rule_reproduces_every_measured_active_cell(
    _s: int, direction: int, goal_rot: int
) -> None:
    assert goal_rotation_for(direction) == goal_rot


def test_goal_rule_is_a_bijection_on_rotations() -> None:
    """Each direction demands a distinct goal rotation, covering all six."""
    assert {goal_rotation_for(d) for d in range(6)} == set(range(6))


@pytest.mark.parametrize("bad", (-1, 6, 7))
def test_goal_rule_rejects_an_out_of_range_direction(bad: int) -> None:
    with pytest.raises(ValueError):
        goal_rotation_for(bad)


# --- The measured live-direction table -------------------------------------


def test_the_table_holds_exactly_the_swept_rotations() -> None:
    """Even -> {E, NW}, odd -> {NE}, all six rotations. A row means a full
    36-cell sweep; the parity shape is measured, not assumed."""
    assert dict(MEASURED_LIVE_DIRECTIONS) == {
        0: frozenset({0, 2}),
        1: frozenset({1}),
        2: frozenset({0, 2}),
        3: frozenset({1}),
        4: frozenset({0, 2}),
        5: frozenset({1}),
    }


@pytest.mark.parametrize("s", (0, 2, 4))
def test_live_directions_at_even_rotations(s: int) -> None:
    assert live_directions(s) == frozenset({0, 2})


@pytest.mark.parametrize("s", (1, 3, 5))
def test_live_directions_at_odd_rotations(s: int) -> None:
    assert live_directions(s) == frozenset({1})


@given(unmeasured_rotations)
def test_live_directions_refuses_a_rotation_outside_the_measured_range(s: int) -> None:
    """No interpolation (decisions.md 2026-08-08): absence means unknown --
    including rotations outside 0..5, where the app's modulo behaviour is
    open unknown #11."""
    with pytest.raises(UnsweptStarterRotationError):
        live_directions(s)


# --- Cell-level classification ---------------------------------------------


@pytest.mark.parametrize(("starter_rot", "direction", "goal_rot"), MEASURED_ACTIVE)
def test_every_measured_active_cell_is_connected(
    starter_rot: int, direction: int, goal_rot: int
) -> None:
    assert connection_status(starter_rot, direction, goal_rot) is ConnectionStatus.CONNECTED


@given(st.sampled_from(LIVE_CELLS), rotations)
def test_a_live_direction_connects_only_at_the_rule_rotation(
    cell: tuple[int, int], goal_rot: int
) -> None:
    """Property: even on a live direction, 5 of 6 goal rotations are measured
    dead. The sweep rendered all of them; this pins that record."""
    starter_rot, direction = cell
    assume(goal_rot != goal_rotation_for(direction))
    assert connection_status(starter_rot, direction, goal_rot) is ConnectionStatus.DISCONNECTED


@given(swept_rotations, directions, rotations)
def test_a_dead_direction_is_disconnected_at_every_rotation(
    starter_rot: int, direction: int, goal_rot: int
) -> None:
    """Property: at a swept starter rotation, a direction outside the live set
    never connects, whatever the goal rotation."""
    assume(direction not in MEASURED_LIVE_DIRECTIONS[starter_rot])
    assert connection_status(starter_rot, direction, goal_rot) is ConnectionStatus.DISCONNECTED


@given(unmeasured_rotations, directions, rotations)
def test_an_unmeasured_starter_rotation_is_never_a_claim(
    starter_rot: int, direction: int, goal_rot: int
) -> None:
    """Property: outside the measured space the module answers UNMEASURED --
    never CONNECTED, never DISCONNECTED. The three-valued honesty invariant."""
    assert connection_status(starter_rot, direction, goal_rot) is ConnectionStatus.UNMEASURED


def test_cell_classification_rejects_an_out_of_range_direction() -> None:
    with pytest.raises(ValueError):
        connection_status(0, 6, 1)


# --- Placed tiles and pair classification ----------------------------------


def _tile(
    kind: TileKind, y: int, x: int, rot: int = 0, layer_id: int = 100
) -> PlacedTile:
    return PlacedTile(kind=kind, world_pos=HexVector(y, x), hex_rotation=rot, layer_id=layer_id)


def test_placed_tiles_positions_the_minimal_course_in_world_coords() -> None:
    tiles = sorted(placed_tiles(generate_minimal()), key=lambda t: t.kind.name)
    assert [(t.kind, t.world_pos, t.hex_rotation) for t in tiles] == [
        (TileKind.GOAL_RAIL, HexVector(-1, 0), 3),
        (TileKind.STARTER, HexVector(0, 0), 0),
    ]


def test_starter_and_goal_kind_sets_come_from_the_catalog() -> None:
    assert TileKind.STARTER in STARTER_KINDS
    assert TileKind.GOAL_RAIL in GOAL_KINDS
    assert TileKind.CANNON not in STARTER_KINDS  # energy injector, not an origin (decisions.md)


def test_a_cross_layer_pair_is_unmeasured() -> None:
    """Every measurement to date sits on one layer; across layers we know nothing."""
    starter = _tile(TileKind.STARTER, 0, 0, layer_id=100)
    goal = _tile(TileKind.GOAL_RAIL, -1, 0, rot=3, layer_id=101)
    assert classify_pair(starter, goal) is ConnectionStatus.UNMEASURED


@given(rotations)
def test_a_distance_two_pair_is_disconnected_at_every_goal_rotation(goal_rot: int) -> None:
    """The sweeps' far control: (0,2) is measured dead at all rotations, and
    a rail-free connection has no mechanism beyond adjacency."""
    starter = _tile(TileKind.STARTER, 0, 0)
    goal = _tile(TileKind.GOAL_RAIL, 0, 2, rot=goal_rot)
    assert classify_pair(starter, goal) is ConnectionStatus.DISCONNECTED


def test_the_certified_geometry_classifies_connected_as_a_pair() -> None:
    starter = _tile(TileKind.STARTER, 0, 0, rot=0)
    goal = _tile(TileKind.GOAL_RAIL, -1, 0, rot=3)
    assert classify_pair(starter, goal) is ConnectionStatus.CONNECTED


# --- Course-level status + the validator rule ------------------------------


def _start_goal_violations(course: Course) -> list:
    return [
        v
        for v in validate(course, PRO_VERTICAL_STARTER_SET)
        if v.rule is Rule.START_GOAL_CONNECTED
    ]


def test_the_generated_minimal_course_is_connected() -> None:
    course = generate_minimal()
    assert start_goal_status(course) is ConnectionStatus.CONNECTED
    assert _start_goal_violations(course) == []


def test_the_other_certified_shape_s1_ne_also_passes() -> None:
    """The 2026-08-08 sweep's one active cell at s=1: NE (-1,1), goal rot 2."""
    course = build_variant(
        generate_minimal(), starter_rot=1, goal_pos=HexVector(-1, 1), goal_rot=2
    )
    assert start_goal_status(course) is ConnectionStatus.CONNECTED
    assert _start_goal_violations(course) == []


def test_a_wrong_goal_rotation_is_a_validator_error() -> None:
    course = build_variant(
        generate_minimal(), starter_rot=0, goal_pos=HexVector(-1, 0), goal_rot=4
    )
    (violation,) = _start_goal_violations(course)
    assert violation.severity is Severity.ERROR
    with pytest.raises(ValidationError):
        validate_strict(course, PRO_VERTICAL_STARTER_SET)


def test_a_dead_direction_at_a_swept_rotation_is_a_validator_error() -> None:
    """At s=1 only NE connects; the certified NW geometry is measured dead."""
    course = build_variant(
        generate_minimal(), starter_rot=1, goal_pos=HexVector(-1, 0), goal_rot=3
    )
    (violation,) = _start_goal_violations(course)
    assert violation.severity is Severity.ERROR


@pytest.mark.parametrize(
    ("starter_rot", "goal_pos", "goal_rot"),
    [
        (0, HexVector(0, 1), 1), (0, HexVector(-1, 0), 3),
        (1, HexVector(-1, 1), 2),
        (2, HexVector(0, 1), 1), (2, HexVector(-1, 0), 3),
        (3, HexVector(-1, 1), 2),
        (4, HexVector(0, 1), 1), (4, HexVector(-1, 0), 3),
        (5, HexVector(-1, 1), 2),
    ],
)
def test_every_measured_active_geometry_passes_at_course_level(
    starter_rot: int, goal_pos: HexVector, goal_rot: int
) -> None:
    """The full parity table, replayed as whole courses through the validator:
    all nine harness-certified geometries classify CONNECTED."""
    course = build_variant(
        generate_minimal(), starter_rot=starter_rot, goal_pos=goal_pos, goal_rot=goal_rot
    )
    assert start_goal_status(course) is ConnectionStatus.CONNECTED
    assert _start_goal_violations(course) == []


def test_a_cross_layer_pair_is_a_warning_not_an_error() -> None:
    """Splitting starter and goal onto different layers leaves the record
    silent -- every measurement sits on one layer -- so the rule warns rather
    than inventing a verdict, and validate_strict (errors only) still passes."""
    base = generate_minimal()
    layer = base.layer_construction_data[0]
    by_kind = {
        c.tree_node_data.construction_data.kind: c for c in layer.cell_construction_datas
    }
    split = dataclasses.replace(
        base,
        layer_construction_data=(
            dataclasses.replace(
                layer, cell_construction_datas=(by_kind[TileKind.STARTER],)
            ),
            dataclasses.replace(
                layer, layer_id=101, cell_construction_datas=(by_kind[TileKind.GOAL_RAIL],)
            ),
        ),
    )
    assert start_goal_status(split) is ConnectionStatus.UNMEASURED
    (violation,) = _start_goal_violations(split)
    assert violation.severity is Severity.WARNING
    validate_strict(split, PRO_VERTICAL_STARTER_SET)  # warnings do not raise


def test_a_course_with_rails_is_out_of_scope_for_the_rule() -> None:
    """Railed connection paths are unmodeled (open unknowns #2, #7): the rule
    must stay silent rather than manufacture findings about them."""
    exit_1 = RailConstructionExitIdentifier(
        retainer_id=100, cell_local_hex_pos=HexVector(0, 0), side_hex_rot=0, exit_local_pos_y=0.0
    )
    exit_2 = RailConstructionExitIdentifier(
        retainer_id=100, cell_local_hex_pos=HexVector(-1, 0), side_hex_rot=3, exit_local_pos_y=0.0
    )
    rail = RailConstructionData(
        exit_1_identifier=exit_1, exit_2_identifier=exit_2, rail_kind=RailKind.STRAIGHT
    )
    disconnected = build_variant(
        generate_minimal(), starter_rot=0, goal_pos=HexVector(-1, 0), goal_rot=4
    )
    railed = dataclasses.replace(disconnected, rail_construction_data=(rail,))
    assert _start_goal_violations(railed) == []


def test_a_course_without_a_goal_is_not_this_rules_finding() -> None:
    """MISSING_STARTER_OR_GOAL owns absence; this rule owns connection."""
    base = generate_minimal()
    layer = base.layer_construction_data[0]
    starter_only = dataclasses.replace(
        base,
        layer_construction_data=(
            dataclasses.replace(
                layer,
                cell_construction_datas=tuple(
                    c
                    for c in layer.cell_construction_datas
                    if c.tree_node_data.construction_data.kind is TileKind.STARTER
                ),
            ),
        ),
    )
    assert start_goal_status(starter_only) is None
    assert _start_goal_violations(starter_only) == []
    rules_fired = {v.rule for v in validate(starter_only, PRO_VERTICAL_STARTER_SET)}
    assert Rule.MISSING_STARTER_OR_GOAL in rules_fired
