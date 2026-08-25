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
from traxgen import graph
from traxgen.domain import (
    Course,
    RailConstructionData,
    RailConstructionExitIdentifier,
)
from traxgen.generator import generate_minimal
from traxgen.graph import (
    ALL_DIRECTIONS,
    GOAL_KINDS,
    MEASURED_LIVE_DIRECTIONS,
    MEASURED_RUNS,
    STARTER_INTRINSIC_PORTS,
    STARTER_KINDS,
    STARTER_PLATE_ONLY,
    ConnectionStatus,
    MeasuredRun,
    PlacedTile,
    UnsweptStarterRotationError,
    classify_pair,
    connection_status,
    course_plate_positions,
    goal_rotation_for,
    live_directions,
    measured_live_directions,
    measured_run,
    placed_tiles,
    plate_offsets_from,
    predict_connection,
    predicted_live_directions,
    start_goal_status,
    starter_world_ports,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.layout import TilePlacement, build_course
from traxgen.plates import BASEPLATE_LAYER_KINDS, STANDARD_SQUARE
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
        starter_rot,
        direction,
        goal_rot,
        layer_kind=PLATE,
        starter_local_pos=CORNER,
        plate_offsets=STARTER_PLATE_ONLY,
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


# The absolute plate layout that matches `_tile`'s courses: one baseplate at
# the world origin. Distinct from graph.STARTER_PLATE_ONLY, which is the same
# course expressed as offsets *from the starter's plate* -- they coincide only
# because `_tile` puts the layer at the origin, and writing them as one name
# would hide exactly the frame distinction these tests exist to protect.
ORIGIN_PLATE_ONLY: tuple[tuple[int, int], ...] = ((0, 0),)


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
    assert (
        classify_pair(starter, goal, plate_positions=ORIGIN_PLATE_ONLY)
        is ConnectionStatus.UNMEASURED
    )


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
    assert (
        classify_pair(starter, goal, plate_positions=ORIGIN_PLATE_ONLY)
        is ConnectionStatus.DISCONNECTED
    )


def test_the_certified_geometry_classifies_connected_as_a_pair() -> None:
    starter = _tile(TileKind.STARTER, 0, 0, rot=0)
    goal = _tile(TileKind.GOAL_RAIL, -1, 0, rot=3)
    assert (
        classify_pair(starter, goal, plate_positions=ORIGIN_PLATE_ONLY)
        is ConnectionStatus.CONNECTED
    )


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
        0,
        layer_kind=PLATE,
        starter_local_pos=unrendered,
        plate_offsets=STARTER_PLATE_ONLY,
    ) is None
    assert predict_connection(
        0, 0, goal_rotation_for(0), layer_kind=PLATE, starter_local_pos=unrendered
    )
    assert (
        connection_status(
            0,
            0,
            goal_rotation_for(0),
            layer_kind=PLATE,
            starter_local_pos=unrendered,
            plate_offsets=STARTER_PLATE_ONLY,
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
            plate_offsets=STARTER_PLATE_ONLY,
        )
        is ConnectionStatus.CONNECTED
    )
    for goal_rot in range(6):
        if goal_rot == goal_rotation_for(live_at_edge):
            continue
        assert (
            connection_status(
                0,
                live_at_edge,
                goal_rot,
                layer_kind=PLATE,
                starter_local_pos=EDGE,
                plate_offsets=STARTER_PLATE_ONLY,
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


# --- The plate layout as a recorded term, not an absorbed one (s25) ---------
#
# Until 2026-08-24 the record said which rotation and which board cell each
# campaign used, and said nothing about the plates the course carried.
# `start_goal_status` compensated by *counting* baseplates and refusing above
# one. These tests pin the replacement: the layout is part of the lookup key,
# so a course the record never covered misses the record instead of tripping a
# special case.


def test_the_record_records_the_plate_layout_the_builder_actually_produced() -> None:
    """`MEASURED_RUNS` claims every campaign ran on the starter's plate alone.

    That claim is graded here against a builder rather than against itself:
    `build_variant` is called for real, its plates are read back off the built
    course through the production path, and the recorded rows must agree. A
    test that compared `STARTER_PLATE_ONLY` to the rows would be comparing two
    copies of one sentence (observations #12).

    Two limits, stated rather than implied. `build_variant` did not exist until
    2026-08-09, so the 2026-08-07 row was built by
    `sweep_goal_rotation._goal_variant` and is graded here only by family
    resemblance. And this pins "today's builder agrees with the rows", not "the
    rows describe what rendered": editing the builder alone fails this test
    without the record being wrong, and editing both together passes it with
    both wrong. It is a drift alarm on a live builder, not a proof about
    history -- the history is what `provenance` carries.
    """
    course = build_variant(
        generate_minimal(), starter_rot=0, goal_pos=HexVector(-1, 0), goal_rot=3
    )
    (starter,) = [t for t in placed_tiles(course) if t.kind in STARTER_KINDS]
    built = plate_offsets_from(course_plate_positions(course), starter)

    assert built == STARTER_PLATE_ONLY
    assert {run.plate_offsets for run in MEASURED_RUNS} == {built}


def test_a_second_baseplate_of_the_other_kind_is_not_a_single_plate_course() -> None:
    """The hole the counting guard had, executable.

    s24's guard counted `BASE_LAYER_PIECE` layers and refused above one, while
    `plates.BASEPLATE_LAYER_KINDS` -- and `validator.py`, and the `b8052e4`
    lock -- count `BASE_LAYER` too. So the certified course plus one empty
    `BASE_LAYER` was a two-baseplate course that the guard waved through, and
    it came back CONNECTED from a record measured on one plate. Measured
    against the pre-fix code before the fix was written, not reasoned about.

    Zero of the 640 parsed corpus courses use `BASE_LAYER` at all, so nothing
    real ever hit this. That is a reason to record it as latent, not a reason
    to leave the two definitions of "baseplate" disagreeing.
    """
    certified = generate_minimal()
    assert start_goal_status(certified) is ConnectionStatus.CONNECTED

    for kind in (LayerKind.BASE_LAYER_PIECE, LayerKind.BASE_LAYER):
        extra = dataclasses.replace(
            certified.layer_construction_data[0],
            layer_id=999,
            layer_kind=kind,
            world_hex_position=HexVector(y=3, x=-6),
            cell_construction_datas=(),
        )
        two_plates = dataclasses.replace(
            certified,
            layer_construction_data=(*certified.layer_construction_data, extra),
        )
        assert start_goal_status(two_plates) is ConnectionStatus.UNMEASURED, kind


def test_the_layout_is_read_relative_to_the_starters_own_plate() -> None:
    """Translating the whole course leaves the recorded layout unchanged.

    This is why the record keys on offsets rather than absolute world
    positions, and it is not a free choice: under absolute keying the s22
    moved-board fixture above would return UNMEASURED, and so would the
    world/local confusion it exists to catch -- the two become
    indistinguishable and the blind spot #26 closed reopens.

    What the choice assumes is that the absolute world offset of a course does
    not affect connection. No render has tested that; every campaign to date
    sits at world (0, 0). The shipped model has always claimed it, because
    `connection_status` never sees a world coordinate at all. The test states
    the claim rather than establishing it.
    """
    course = build_variant(
        generate_minimal(), starter_rot=0, goal_pos=HexVector(-1, 0), goal_rot=3
    )
    moved = dataclasses.replace(
        course,
        layer_construction_data=tuple(
            dataclasses.replace(layer, world_hex_position=HexVector(y=7, x=-4))
            for layer in course.layer_construction_data
        ),
    )
    assert course_plate_positions(course) != course_plate_positions(moved)

    for variant in (course, moved):
        (starter,) = [t for t in placed_tiles(variant) if t.kind in STARTER_KINDS]
        offsets = plate_offsets_from(course_plate_positions(variant), starter)
        assert offsets == STARTER_PLATE_ONLY
        assert start_goal_status(variant) is ConnectionStatus.CONNECTED


def test_two_plates_at_one_world_position_are_two_plates() -> None:
    """A degenerate layout must miss the record rather than collapse into it.

    `layout.build_course` refuses to emit two plates at one position and the
    corpus has never contained one -- s24 measured zero footprint collisions
    across 640 courses, which two coincident plates could not survive. The
    parser will read one, though, so this is the path that reaches
    `start_goal_status`, and it is why the layout is a tuple rather than a set:
    a set would fold the pair into a single entry and hand the course the
    single-plate record's answer.
    """
    certified = generate_minimal()
    home = certified.layer_construction_data[0]
    stacked = dataclasses.replace(
        certified,
        layer_construction_data=(
            home,
            dataclasses.replace(home, layer_id=999, cell_construction_datas=()),
        ),
    )
    assert len(course_plate_positions(stacked)) == 2
    assert start_goal_status(stacked) is ConnectionStatus.UNMEASURED


def test_the_plate_layout_cannot_go_missing_either() -> None:
    """`plate_offsets` is keyword-only with no default, like the two before it.

    Sibling of `test_the_position_cannot_go_missing_again`, and for the same
    reason one layer on: a default would let `connection_status` answer for
    whatever layout happened to be rendered and apply it to any other, which is
    precisely the defect that reached ERROR severity on 2026-08-24. Supplying
    the two s22 terms and omitting this one must still be a TypeError.
    """
    with pytest.raises(TypeError):
        connection_status(  # type: ignore[call-arg]
            0, 0, 1, layer_kind=PLATE, starter_local_pos=CORNER
        )


def test_the_baseplate_classification_includes_base_layer() -> None:
    """A literal-vs-derived guard on the one term the defect turned on.

    `course_plate_positions` derives the layout from
    `plates.BASEPLATE_LAYER_KINDS`, so a test that swept that constant would
    grade it against itself (observations #12) -- narrowing the constant would
    narrow the test's own domain and stay green. The kinds are therefore named
    literally here, the same transcription-guard shape s22 gave
    `TABLE_CLAIM_2026_08_10`.

    This pins what the classification *is*, not that it is right. The
    justification -- the Rust `layer_height` doc-comment's plural "all base
    plates" -- lives with the constant and in
    docs/refs/layer-kinds-and-world-coords.md.
    """
    assert set(BASEPLATE_LAYER_KINDS) == {
        LayerKind.BASE_LAYER,
        LayerKind.BASE_LAYER_PIECE,
    }

    certified = generate_minimal()
    home = certified.layer_construction_data[0]
    for kind, expected in (
        (LayerKind.BASE_LAYER, 2),
        (LayerKind.BASE_LAYER_PIECE, 2),
        (LayerKind.LARGE_LAYER, 1),
        (LayerKind.SMALL_LAYER, 1),
        (LayerKind.LARGE_GHOST_LAYER, 1),
    ):
        extra = dataclasses.replace(
            home, layer_id=999, layer_kind=kind, cell_construction_datas=()
        )
        course = dataclasses.replace(
            certified,
            layer_construction_data=(*certified.layer_construction_data, extra),
        )
        assert len(course_plate_positions(course)) == expected, kind


def test_the_plate_layout_is_canonical_regardless_of_layer_order() -> None:
    """Layer order is a wire-format accident; the lookup key must not carry it.

    Found by mutation, and it is observations #26's shape: every fixture in the
    suite -- `STANDARD_SQUARE` included -- happens to list its plates already
    in sorted order, so dropping the `sorted()` from `course_plate_positions`
    left the entire suite green. That is the s24 reordering defect (#30)
    arriving from the other side: there a *generated constant's* order was
    load-bearing and untested, here a *parsed course's* would be.

    Scope, corrected by the panel: the sort here is **not** what protects the
    lookup key, because `plate_offsets_from` sorts again after rebasing and
    translation preserves order. It protects every caller that reads
    `course_plate_positions` directly -- which is the function's whole public
    job, and what a future consumer will reach for.

    Two courses, same plates, opposite layer order, one canonical answer.
    """
    certified = generate_minimal()
    home = certified.layer_construction_data[0]
    away = dataclasses.replace(
        home,
        layer_id=999,
        world_hex_position=HexVector(y=3, x=-6),
        cell_construction_datas=(),
    )

    in_order = dataclasses.replace(certified, layer_construction_data=(home, away))
    reversed_order = dataclasses.replace(
        certified, layer_construction_data=(away, home)
    )

    assert course_plate_positions(in_order) == course_plate_positions(reversed_order)
    assert course_plate_positions(in_order) == ((0, 0), (3, -6))

    # Assert the key's *value*, not that it equals itself: `away` holds no
    # cells, so both variants yield the identical starter and the loop would
    # otherwise compare one function call to a copy of itself -- true for any
    # implementation, including one that ignores both arguments (#12).
    for variant in (in_order, reversed_order):
        (starter,) = [t for t in placed_tiles(variant) if t.kind in STARTER_KINDS]
        assert plate_offsets_from(course_plate_positions(variant), starter) == (
            (0, 0),
            (3, -6),
        )


# --- What an adversarial panel found in the section above (s25) -------------
#
# The tests above were green and self-reviewed when a three-lens panel graded
# them (observations #19). Two lenses independently found that replacing the
# baseplate count with a lookup had *reopened* the defect it was meant to
# close, and a mutation lens found that most of the new key's arithmetic was
# only ever exercised at zero. These are the tests that were missing.


def test_a_multi_plate_course_is_not_claimed_disconnected_when_the_pair_is_far() -> None:
    """The defect the s25 fix introduced, and the reason ordering matters.

    `classify_pair` answers DISCONNECTED for non-adjacent pairs from the
    *mechanism*, without reading the record. s24's baseplate count lived in
    `start_goal_status`, above that short-circuit, so it covered every pair.
    Replacing the count with a lookup inside `connection_status` moved the
    guard *below* it: a four-plate course whose starter and goal are not
    adjacent was claimed measured-disconnected at ERROR severity, on a layout
    no campaign has rendered. 599 of 640 corpus courses are multi-plate, so
    this was the common shape rather than a corner.

    The sibling in `tests/test_layout.py` did not catch it because its goal is
    the *adjacent* W cell -- the one arm that still reaches the lookup. This
    test walks the distances the sweeps themselves used as far controls.
    """
    square = tuple(HexVector(y, x) for y, x in STANDARD_SQUARE)
    for goal_local in (HexVector(0, 2), HexVector(2, 0), HexVector(3, -1)):
        course = build_course(
            plate_world_positions=square,
            tiles=(
                TilePlacement(TileKind.STARTER, 0, HexVector(0, 0), 0),
                TilePlacement(TileKind.GOAL_RAIL, 0, goal_local, 4),
            ),
        )
        assert start_goal_status(course) is ConnectionStatus.UNMEASURED, goal_local
        assert _start_goal_violations(course)[0].severity is Severity.WARNING


def test_a_single_plate_in_the_wrong_place_is_not_the_measured_one() -> None:
    """The key is positions, not a count -- which nothing above actually tested.

    Every row in `MEASURED_RUNS` carries a one-element layout, so "the layout
    matches" and "there is one plate" were the same predicate across the whole
    suite. A mutation replacing the comparison with `len(plate_offsets) == 1`
    -- s24's count, moved inside the lookup -- left all 626 tests green while
    answering a *differently placed* single plate from the record.

    Coincidence enumerated by the panel's mutation lens (observations #26); the
    fix is one assertion that the offset value has to match, not its length.
    """
    elsewhere = ((3, -6),)
    assert elsewhere != STARTER_PLATE_ONLY
    assert len(elsewhere) == len(STARTER_PLATE_ONLY)  # the count cannot tell them apart

    assert (
        measured_live_directions(
            0, layer_kind=PLATE, starter_local_pos=CORNER, plate_offsets=elsewhere
        )
        is None
    )
    assert (
        connection_status(
            0,
            0,
            goal_rotation_for(0),
            layer_kind=PLATE,
            starter_local_pos=CORNER,
            plate_offsets=elsewhere,
        )
        is ConnectionStatus.UNMEASURED
    )


def test_the_rebase_is_arithmetic_not_a_predicate() -> None:
    """`plate_offsets_from` must be graded away from zero, or it is barely graded.

    Every offset the rest of the suite compares is `(0, 0)`, because no fixture
    had both a non-origin board *and* more than one plate. Transposing y/x,
    negating the rebase, dropping its `sorted()`, sorting by x alone, rebasing
    off the wrong plate, and returning `()` for every multi-plate layout all
    fix or bypass zero -- so seven distinct mutations survived the full suite.

    One asymmetric, off-origin, two-plate expectation kills all seven. This
    matters prospectively rather than today: the #17 2x2 is what puts a
    multi-plate row into `MEASURED_RUNS`, and every one of those mutations goes
    live the moment it does.
    """
    certified = generate_minimal()
    home = dataclasses.replace(
        certified.layer_construction_data[0], world_hex_position=HexVector(y=7, x=-4)
    )
    away = dataclasses.replace(
        home,
        layer_id=999,
        world_hex_position=HexVector(y=10, x=-10),
        cell_construction_datas=(),
    )
    course = dataclasses.replace(certified, layer_construction_data=(home, away))

    (starter,) = [t for t in placed_tiles(course) if t.kind in STARTER_KINDS]
    assert starter.local_pos == HexVector(0, 0)
    assert course_plate_positions(course) == ((7, -4), (10, -10))
    assert plate_offsets_from(course_plate_positions(course), starter) == (
        (0, 0),
        (3, -6),
    )


@pytest.mark.parametrize(
    "omit", ["layer_kind", "starter_local_pos", "plate_offsets"]
)
def test_no_term_of_the_key_may_go_missing(omit: str) -> None:
    """All three terms, not just the newest one.

    `connection_status`'s docstring says a default on *any* of the three
    restores the corresponding defect. Only one was pinned: the older
    `test_the_position_cannot_go_missing_again` omits all three at once, so it
    passes as long as any single one lacks a default -- and once the s25
    sibling forbade a default on `plate_offsets`, that older test could no
    longer fail for any implementation. Defaults on both s22 terms passed the
    whole suite, reproducing the s22 defect exactly (the corner's answer
    handed to an unrendered cell).

    Omitting one term at a time is what makes each guard independent.
    """
    kwargs = {
        "layer_kind": PLATE,
        "starter_local_pos": CORNER,
        "plate_offsets": STARTER_PLATE_ONLY,
    }
    del kwargs[omit]
    with pytest.raises(TypeError):
        connection_status(0, 0, 1, **kwargs)  # type: ignore[arg-type]


def test_the_key_is_required_on_every_surface_that_takes_it() -> None:
    """`classify_pair` is the surface an external caller reaches first.

    A default on it returns CONNECTED for the four-plate probe arm -- the exact
    false claim on the exact course the #17 experiment exists to render. The
    guard on `connection_status` alone does not cover its three siblings.
    """
    starter = _tile(TileKind.STARTER, 0, 0, rot=0)
    goal = _tile(TileKind.GOAL_RAIL, -1, 0, rot=3)
    with pytest.raises(TypeError):
        classify_pair(starter, goal)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        measured_run(0, layer_kind=PLATE, starter_local_pos=CORNER)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        measured_live_directions(  # type: ignore[call-arg]
            0, layer_kind=PLATE, starter_local_pos=CORNER
        )


def test_a_base_layer_course_does_not_inherit_the_pieces_record() -> None:
    """Widening "baseplate" made `layer_kind` newly load-bearing in the key.

    `BASE_LAYER` now counts toward the layout, so a course whose single
    baseplate is a `BASE_LAYER` produces the *matching* key `((0, 0),)`. Only
    the `layer_kind` term keeps it out of the record -- and nothing tested that
    term, so dropping it from the comparison left the suite green while
    handing `BASE_LAYER` the `BASE_LAYER_PIECE` campaigns' answers.

    The complement of `test_a_second_baseplate_of_the_other_kind_...`: that one
    proves `BASE_LAYER` counts toward the layout, this one proves it does not
    inherit the record. `plates.MEASURED_FOOTPRINTS` has no entry for it, so
    refusing is the coherent answer rather than a conservative one.
    """
    certified = generate_minimal()
    recoloured = dataclasses.replace(
        certified,
        layer_construction_data=tuple(
            dataclasses.replace(layer, layer_kind=LayerKind.BASE_LAYER)
            for layer in certified.layer_construction_data
        ),
    )
    assert course_plate_positions(recoloured) == course_plate_positions(certified)
    assert start_goal_status(certified) is ConnectionStatus.CONNECTED
    assert start_goal_status(recoloured) is ConnectionStatus.UNMEASURED


def test_a_measured_run_cannot_be_written_without_its_layout() -> None:
    """The change's own thesis, applied to the record that carries it.

    A term with a default gets absorbed silently -- that is the whole argument
    for `plate_offsets` existing. The same argument applies to writing a row:
    a future 2x2 campaign whose author omits the layout must not default into
    claiming the single-plate one.

    Supplies every *other* required term deliberately, including the s27
    coverage one. An earlier version omitted `directions_probed` too, so once
    that field landed this test raised for either reason and would have stayed
    green if `plate_offsets` had quietly gained a default -- a stronger sibling
    hollowing out the test beside it (observations #12, the s25 (e) instance).
    """
    with pytest.raises(TypeError):
        MeasuredRun(  # type: ignore[call-arg]
            layer_kind=PLATE,
            starter_local_pos=(0, 0),
            starter_rot=0,
            live_directions=frozenset({0}),
            directions_probed=ALL_DIRECTIONS,
            goal_rotations_swept=False,
            provenance="a campaign whose author forgot the layout",
        )


def test_a_measured_run_cannot_be_written_without_its_direction_coverage() -> None:
    """The same argument as the layout term, for the term s27 added.

    A default here would mean "assume all six were probed", which is the exact
    claim the #17 2x2 cannot make -- it renders one cell on a plate layout
    nothing has measured.
    """
    with pytest.raises(TypeError):
        MeasuredRun(  # type: ignore[call-arg]
            layer_kind=PLATE,
            starter_local_pos=(0, 0),
            starter_rot=0,
            live_directions=frozenset({0}),
            goal_rotations_swept=False,
            plate_offsets=STARTER_PLATE_ONLY,
            provenance="a campaign whose author forgot what it rendered",
        )


def test_a_run_cannot_claim_a_direction_it_never_probed() -> None:
    """Two fields that could contradict, made unconstructable rather than checked.

    `live_directions` and `directions_probed` are separate frozensets, so a row
    could assert a direction rendered active in a run that never rendered it.
    The invariant lives in `__post_init__` so the incoherent row cannot exist,
    rather than in a docstring a reader is trusted to honour.
    """
    with pytest.raises(ValueError, match="never rendered it"):
        MeasuredRun(
            layer_kind=PLATE,
            starter_local_pos=(0, 0),
            starter_rot=0,
            live_directions=frozenset({0, 3}),
            directions_probed=frozenset({0}),
            goal_rotations_swept=False,
            plate_offsets=STARTER_PLATE_ONLY,
            provenance="claims W active in a run that only rendered E",
        )


def test_an_unprobed_direction_is_unmeasured_rather_than_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate, against a partial-coverage run built here rather than borrowed.

    Every row in `MEASURED_RUNS` probes all six directions, so this property is
    invisible to the real record -- the fixture coincidence observations #26
    names, present on the field's first day. This builds the run the record does
    not yet contain: one direction rendered, one active, four never touched.

    Deleting the `directions_probed` gate in `connection_status` turns the four
    unprobed directions into DISCONNECTED and fails this test -- verified by
    enacting that deletion, not by assuming the assertion is load-bearing.
    """
    partial = MeasuredRun(
        layer_kind=PLATE,
        starter_local_pos=(0, 0),
        starter_rot=0,
        live_directions=frozenset({0}),
        directions_probed=frozenset({0, 3}),
        goal_rotations_swept=False,
        plate_offsets=STARTER_PLATE_ONLY,
        provenance="synthetic: E rendered active, W rendered dark, rest untouched",
    )
    monkeypatch.setattr(graph, "MEASURED_RUNS", (partial,))

    def status(direction: int) -> ConnectionStatus:
        return connection_status(
            0,
            direction,
            goal_rotation_for(direction),
            layer_kind=PLATE,
            starter_local_pos=HexVector(y=0, x=0),
            plate_offsets=STARTER_PLATE_ONLY,
        )

    assert status(0) is ConnectionStatus.CONNECTED, "probed and live"
    assert status(3) is ConnectionStatus.DISCONNECTED, "probed and dark"
    for direction in (1, 2, 4, 5):
        assert status(direction) is ConnectionStatus.UNMEASURED, (
            f"direction {direction} was never rendered, so the record cannot "
            "call it disconnected"
        )


def test_every_measured_run_has_a_distinct_lookup_key() -> None:
    """`measured_run` returns the first match, so a duplicate key shadows.

    Not a regression -- adding the layout term makes collisions less likely,
    not more -- but the #17 campaign adds rows, and a shadowed row would
    silently answer with its twin's `live_directions` rather than raise.
    """
    keys = [
        (r.layer_kind, r.starter_local_pos, r.starter_rot, r.plate_offsets)
        for r in MEASURED_RUNS
    ]
    assert len(set(keys)) == len(keys)


def test_one_live_goal_beats_a_dead_one_whichever_is_listed_first() -> None:
    """`start_goal_status`'s precedence ladder has never run on two goals.

    Every fixture in the suite has exactly one starter and exactly one goal, so
    the cross-product is 1x1 and the CONNECTED > UNMEASURED > DISCONNECTED
    ladder always ran on a one-element set. Reversing the ladder, or
    classifying only the first pair, both passed the full suite -- and both
    turn this course into a **false DISCONNECTED at ERROR severity**, which is
    what the 2026-08-10 severity lock exists to forbid.

    Pre-existing rather than introduced here, but it sits inside the function
    this change rewrote, and the dead goal is listed first on purpose.
    """
    certified = generate_minimal()
    layer = certified.layer_construction_data[0]
    live_goal = next(
        cell
        for cell in layer.cell_construction_datas
        if cell.tree_node_data.construction_data.kind is TileKind.GOAL_RAIL
    )
    dead_goal = dataclasses.replace(live_goal, local_hex_position=HexVector(y=-2, x=2))
    starter = next(
        cell
        for cell in layer.cell_construction_datas
        if cell.tree_node_data.construction_data.kind is TileKind.STARTER
    )
    two_goals = dataclasses.replace(
        certified,
        layer_construction_data=(
            dataclasses.replace(
                layer, cell_construction_datas=(dead_goal, starter, live_goal)
            ),
        ),
    )
    per_pair = {
        classify_pair(s, g, plate_positions=course_plate_positions(two_goals))
        for s in placed_tiles(two_goals)
        if s.kind in STARTER_KINDS
        for g in placed_tiles(two_goals)
        if g.kind in GOAL_KINDS
    }
    assert per_pair == {ConnectionStatus.CONNECTED, ConnectionStatus.DISCONNECTED}
    assert start_goal_status(two_goals) is ConnectionStatus.CONNECTED


def test_plate_offsets_from_is_canonical_and_starter_anchored() -> None:
    """Three more mutants the course-level fixtures cannot reach.

    Each survived the whole suite because a coincidence hid it, and each is a
    unit-level fact about `plate_offsets_from` rather than a course-level one:

      * **Its own `sorted()` looked redundant.** In production the input comes
        from `course_plate_positions`, which already sorts, and a translation
        preserves order -- so dropping it changed nothing. But this is a public
        function taking a sequence, and a caller that hands it an unsorted one
        must still get the canonical key.
      * **The anchor was never observed away from the plate.** Every fixture's
        starter stands on one of the counted baseplates, so "rebase off the
        starter's layer" and "return the zero vector" were the same function.
      * **The starter's plate always sorted first**, so rebasing off
        `plate_positions[0]` was indistinguishable from rebasing off the
        starter's own.
    """
    at_origin = PlacedTile(
        kind=TileKind.STARTER,
        world_pos=HexVector(0, 0),
        local_pos=HexVector(0, 0),
        hex_rotation=0,
        layer_id=100,
        layer_kind=PLATE,
    )
    assert plate_offsets_from(((5, 0), (0, 0)), at_origin) == ((0, 0), (5, 0))

    # A starter whose layer sits at world (5, 5) -- not one of the plates given.
    off_plate = dataclasses.replace(at_origin, world_pos=HexVector(5, 5))
    assert plate_offsets_from(((0, 0),), off_plate) == ((-5, -5),)

    # The starter's plate is (0, 0), which sorts *second* here.
    assert plate_offsets_from(((-3, 6), (0, 0)), at_origin) == ((-3, 6), (0, 0))


def test_every_measured_run_is_a_base_layer_piece_campaign() -> None:
    """The condition under which one surviving mutant is genuinely equivalent.

    `classify_pair` now consults the record before any verdict, using
    `starter.layer_kind`. Hardcoding `BASE_LAYER_PIECE` in the call it then
    forwards survives the whole suite -- and provably must, because the
    pre-check only passes when some run's `layer_kind` matches the starter's,
    and every run is `BASE_LAYER_PIECE`. So the two values cannot differ.

    That is a concession, not a defect, and it is written down rather than
    quietly left green (the s24 precedent for an untestable constant). But the
    equivalence is *conditional*, and this is the condition. Record a campaign
    on any other layer kind and the mutant stops being equivalent, at which
    point this test fails and says so.
    """
    assert {run.layer_kind for run in MEASURED_RUNS} == {LayerKind.BASE_LAYER_PIECE}
