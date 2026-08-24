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
    MEASURED_RUNS,
    STARTER_INTRINSIC_PORTS,
    STARTER_KINDS,
    ConnectionStatus,
    PlacedTile,
    UnsweptStarterRotationError,
    classify_pair,
    connection_status,
    goal_rotation_for,
    live_directions,
    measured_live_directions,
    placed_tiles,
    predict_connection,
    predicted_live_directions,
    start_goal_status,
    starter_world_ports,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.types import LayerKind, RailKind, TileKind
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

# Every sweep behind the corner table pinned the STARTER here. Naming it is the
# point of the s22 change: the coordinate used to be invisible.
PLATE = LayerKind.BASE_LAYER_PIECE
CORNER = HexVector(0, 0)
EDGE = HexVector(0, 1)
INTERIOR = HexVector(-3, 2)


def _at_corner(starter_rot: int, direction: int, goal_rot: int) -> ConnectionStatus:
    """`connection_status` at the plate corner -- the placement the table measured."""
    return connection_status(
        starter_rot, direction, goal_rot, layer_kind=PLATE, starter_local_pos=CORNER
    )


@pytest.mark.parametrize(("starter_rot", "direction", "goal_rot"), MEASURED_ACTIVE)
def test_every_measured_active_cell_is_connected(
    starter_rot: int, direction: int, goal_rot: int
) -> None:
    assert _at_corner(starter_rot, direction, goal_rot) is ConnectionStatus.CONNECTED


@given(st.sampled_from(LIVE_CELLS), rotations)
def test_a_live_direction_connects_only_at_the_rule_rotation(
    cell: tuple[int, int], goal_rot: int
) -> None:
    """Property: even on a live direction, 5 of 6 goal rotations are measured
    dead. The sweep rendered all of them; this pins that record."""
    starter_rot, direction = cell
    assume(goal_rot != goal_rotation_for(direction))
    assert _at_corner(starter_rot, direction, goal_rot) is ConnectionStatus.DISCONNECTED


@given(swept_rotations, directions, rotations)
def test_a_dead_direction_is_disconnected_at_every_rotation(
    starter_rot: int, direction: int, goal_rot: int
) -> None:
    """Property: at a swept starter rotation, a direction outside the live set
    never connects, whatever the goal rotation."""
    assume(direction not in MEASURED_LIVE_DIRECTIONS[starter_rot])
    assert _at_corner(starter_rot, direction, goal_rot) is ConnectionStatus.DISCONNECTED


@given(unmeasured_rotations, directions, rotations)
def test_an_unmeasured_starter_rotation_is_never_a_claim(
    starter_rot: int, direction: int, goal_rot: int
) -> None:
    """Property: outside the measured space the module answers UNMEASURED --
    never CONNECTED, never DISCONNECTED. The three-valued honesty invariant."""
    assert _at_corner(starter_rot, direction, goal_rot) is ConnectionStatus.UNMEASURED


def test_cell_classification_rejects_an_out_of_range_direction() -> None:
    with pytest.raises(ValueError):
        _at_corner(0, 6, 1)


# --- Placed tiles and pair classification ----------------------------------


def _tile(
    kind: TileKind, y: int, x: int, rot: int = 0, layer_id: int = 100
) -> PlacedTile:
    """A tile on a layer whose `world_hex_position` is the origin, so local == world."""
    return PlacedTile(
        kind=kind,
        world_pos=HexVector(y, x),
        local_pos=HexVector(y, x),
        hex_rotation=rot,
        layer_id=layer_id,
        layer_kind=PLATE,
    )


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
    """Non-adjacent pairs do not connect, on the mechanism -- not on the far control.

    This test used to cite the sweeps' distance-2 far control as its evidence.
    It should not have: `FAR_CONTROL_POS = (0, 2)` is off the measured plate
    footprint, so those renders measured cell invalidity rather than distance
    (`plan.md`, sequenced item 2). What holds the claim up is that a rail-free
    connection is tile adjacency with `rail_count = 0`, and there is nothing
    left to carry one across a gap. An on-plate distance-2 control is owed
    before the empirical version of this claim is made.
    """
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


# --- The conjunction: does the model reproduce every render ever run? -------
#
# This is the section the s22 change rests on. `plan.md`'s sequenced item 2 was
# a defect report, not a feature request: shipped code claimed DISCONNECTED at
# ERROR severity for valid courses, because `connection_status` was keyed on
# starter rotation alone. The fix is only worth trusting if the model that
# replaces the position-blind table reproduces every cell any render has ever
# produced -- which is what these run over.


def test_the_conjunction_reproduces_every_rendered_run() -> None:
    """The whole class, not a named instance of it.

    Eight campaigns: six exhaustive 36-cell corner sweeps (2026-08-07 through
    2026-08-10) and the two 2026-08-21 probe runs at starter positions no sweep
    had used. `plate_available INTERSECT starter_world_ports` has to give back
    each one's live set exactly -- no free parameters, no per-run fudge.

    Written as a sweep over `MEASURED_RUNS` rather than as named asserts on
    purpose: a typed list of the runs would be the same untested claim one
    layer down, and it would go stale the moment a ninth run lands.
    """
    for run in MEASURED_RUNS:
        predicted = predicted_live_directions(
            run.starter_rot,
            layer_kind=run.layer_kind,
            starter_local_pos=HexVector(*run.starter_local_pos),
        )
        assert predicted == run.live_directions, (
            f"{run.layer_kind.name} {run.starter_local_pos} rot {run.starter_rot}: "
            f"model says {sorted(predicted)}, render measured "
            f"{sorted(run.live_directions)} -- {run.provenance}"
        )


def test_the_rendered_record_covers_more_than_the_corner() -> None:
    """Guards the test above from passing vacuously on corner rows alone.

    If a refactor ever dropped the two 2026-08-21 runs, the sweep would still be
    green while checking only the geometry the model was built to explain --
    observation #12's shape, and exactly the trap this whole change is about.
    """
    positions = {(run.layer_kind, run.starter_local_pos) for run in MEASURED_RUNS}
    assert (LayerKind.BASE_LAYER_PIECE, (0, 1)) in positions
    assert (LayerKind.BASE_LAYER_PIECE, (-3, 2)) in positions


def test_the_corner_table_is_derived_from_the_runs_not_restated() -> None:
    """`MEASURED_LIVE_DIRECTIONS` is the six exhaustive corner sweeps, and only those."""
    corner_rows = {
        run.starter_rot: run.live_directions
        for run in MEASURED_RUNS
        if run.starter_local_pos == (0, 0) and run.goal_rotations_swept
    }
    assert dict(MEASURED_LIVE_DIRECTIONS) == corner_rows
    assert set(MEASURED_LIVE_DIRECTIONS) == set(range(6))


@pytest.mark.parametrize("starter_rot", range(6))
def test_the_ports_term_flips_parity_with_the_rotation(starter_rot: int) -> None:
    """Why parity was ever the shape: an even-only intrinsic set has no odd member.

    Corpus mining put the STARTER's ports at even tile-relative edges {0, 2, 4}
    (n=380, zero odd observations), so the world-frame set is all-even at even
    rotations and all-odd at odd ones. The table's parity was this term; its
    2-vs-1 sizes were the plate corner.
    """
    ports = starter_world_ports(starter_rot)
    assert len(ports) == len(STARTER_INTRINSIC_PORTS)
    assert all(d % 2 == starter_rot % 2 for d in ports)


# --- Model and claim are different surfaces --------------------------------


def test_the_model_answers_where_the_record_is_silent() -> None:
    """The separation this module exists to keep: prediction is not measurement.

    At an unrendered starter cell the conjunction has an opinion and
    `connection_status` refuses to have one. Collapsing these would make the
    generator's proposals indistinguishable from the harness's findings.
    """
    unrendered = HexVector(y=-2, x=3)
    assert measured_live_directions(
        0, layer_kind=PLATE, starter_local_pos=unrendered
    ) is None
    assert predict_connection(
        0, 0, goal_rotation_for(0), layer_kind=PLATE, starter_local_pos=unrendered
    )
    assert (
        connection_status(
            0, 0, goal_rotation_for(0), layer_kind=PLATE, starter_local_pos=unrendered
        )
        is ConnectionStatus.UNMEASURED
    )


def test_a_probe_run_does_not_borrow_the_sweeps_goal_rotation_coverage() -> None:
    """The 2026-08-21 runs rendered each direction only at `(d + 1) % 6`.

    So at those positions the other five goal rotations are unmeasured, not
    measured-dead. A sweep row claims all 36 cells; a probe row claims six.
    """
    live_at_edge = 2  # NW, the one active cell of the edge run
    assert (
        connection_status(
            0,
            live_at_edge,
            goal_rotation_for(live_at_edge),
            layer_kind=PLATE,
            starter_local_pos=EDGE,
        )
        is ConnectionStatus.CONNECTED
    )
    for goal_rot in range(6):
        if goal_rot == goal_rotation_for(live_at_edge):
            continue
        assert (
            connection_status(
                0, live_at_edge, goal_rot, layer_kind=PLATE, starter_local_pos=EDGE
            )
            is ConnectionStatus.UNMEASURED
        )


def test_the_position_cannot_go_missing_again() -> None:
    """`layer_kind` and `starter_local_pos` are keyword-only and have no defaults.

    A default would restore the exact bug: an answer measured at the plate
    corner, applied everywhere, with nothing in the signature to say so.
    """
    with pytest.raises(TypeError):
        connection_status(0, 0, 1)  # type: ignore[call-arg]


# --- The defect, as a falsifier --------------------------------------------


def test_the_interior_sw_course_is_no_longer_a_false_error() -> None:
    """The bug report, executable.

    SW at an interior starter rendered **active** on 2026-08-21 after being dark
    in all six exhaustive corner sweeps. Before s22 this course classified
    DISCONNECTED and `START_GOAL_CONNECTED` threw ERROR at it -- a validator
    rejecting a geometry the app had certified. It now classifies from the run
    that measured it.
    """
    direction = 4  # SW
    goal_pos = INTERIOR.neighbor(direction)
    course = build_variant(
        generate_minimal(),
        starter_rot=0,
        starter_pos=INTERIOR,
        goal_pos=goal_pos,
        goal_rot=goal_rotation_for(direction),
    )
    assert start_goal_status(course) is ConnectionStatus.CONNECTED
    assert _start_goal_violations(course) == []


@pytest.mark.parametrize("direction", [0, 2, 4])  # E, NW, SW -- the interior run's live set
def test_every_live_cell_of_the_interior_run_passes_at_course_level(
    direction: int,
) -> None:
    """All three cells the interior run rendered active, replayed as whole courses."""
    course = build_variant(
        generate_minimal(),
        starter_rot=0,
        starter_pos=INTERIOR,
        goal_pos=INTERIOR.neighbor(direction),
        goal_rot=goal_rotation_for(direction),
    )
    assert start_goal_status(course) is ConnectionStatus.CONNECTED


def test_an_off_plate_goal_at_a_rendered_position_is_a_measured_error() -> None:
    """The edge run's E cell: port-allowed, off-plate, and it rendered inactive.

    That is a measured negative at a rendered position, so ERROR is the honest
    severity -- the same claim the corner rows earn, now for the plate term.
    """
    direction = 0  # E, off-plate from (0,1)
    course = build_variant(
        generate_minimal(),
        starter_rot=0,
        starter_pos=EDGE,
        goal_pos=EDGE.neighbor(direction),
        goal_rot=goal_rotation_for(direction),
    )
    assert start_goal_status(course) is ConnectionStatus.DISCONNECTED
    (violation,) = _start_goal_violations(course)
    assert violation.severity is Severity.ERROR


def test_an_unrendered_starter_position_warns_rather_than_errors() -> None:
    """The minimum honest behaviour off the measured positions.

    The conjunction predicts this course connects, and no render has visited the
    cell -- so the rule warns. Before s22 the position was invisible and the
    corner table answered for it; a wrong answer here was an ERROR.
    """
    starter = HexVector(y=-2, x=3)
    direction = 4  # SW: on-plate here, and port-allowed at rotation 0
    course = build_variant(
        generate_minimal(),
        starter_rot=0,
        starter_pos=starter,
        goal_pos=starter.neighbor(direction),
        goal_rot=goal_rotation_for(direction),
    )
    assert start_goal_status(course) is ConnectionStatus.UNMEASURED
    (violation,) = _start_goal_violations(course)
    assert violation.severity is Severity.WARNING
    validate_strict(course, PRO_VERTICAL_STARTER_SET)


def test_plate_membership_is_local_even_when_the_layer_sits_off_origin() -> None:
    """The board can sit anywhere in the world; membership is a fact about the board.

    Every other fixture in this suite puts the layer's world_hex_position at the
    origin, so local and world coordinates coincide and a bug that reads the
    starter's *world* position where its *board* position belongs is invisible
    to all of them -- the s22 panel review demonstrated exactly that mutation
    passing the full suite. This course breaks the coincidence: the layer is
    translated so the interior starter's world position lands on (0, 0), the
    plate corner. Confusing the frames turns the render-certified SW course
    into the corner's measured-dead SW -- DISCONNECTED at ERROR severity, the
    original s22 symptom -- while the honest local reading keeps it CONNECTED.
    """
    direction = 4  # SW -- rendered active at the interior on 2026-08-21
    course = build_variant(
        generate_minimal(),
        starter_rot=0,
        starter_pos=INTERIOR,
        goal_pos=INTERIOR.neighbor(direction),
        goal_rot=goal_rotation_for(direction),
    )
    moved_layers = tuple(
        dataclasses.replace(layer, world_hex_position=HexVector(y=3, x=-2))
        for layer in course.layer_construction_data
    )
    moved = dataclasses.replace(course, layer_construction_data=moved_layers)
    starter_world = {
        t.world_pos for t in placed_tiles(moved) if t.kind in STARTER_KINDS
    }
    assert starter_world == {HexVector(0, 0)}  # the trap is armed: world == corner
    assert start_goal_status(moved) is ConnectionStatus.CONNECTED
    assert _start_goal_violations(moved) == []
