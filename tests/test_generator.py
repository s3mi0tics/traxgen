"""Tests for the M5.b-minimal generator.

Proves the pipeline: generate_minimal() produces a Course that (a) passes
validate_strict against PRO Vertical, and (b) round-trips through the
serializer and parser byte-for-byte. If both hold, the only thing left
to discover in M6 is whether the GraviTrax app accepts our bytes.

Path: traxgen/tests/test_generator.py
"""

from __future__ import annotations

import pytest

from traxgen import graph
from traxgen.domain import Course
from traxgen.generator import (
    NoBuildablePlacementError,
    UnmodelledGoalKindError,
    _cross_plate_placements,
    generate_minimal,
    generate_multi_plate,
)
from traxgen.graph import (
    GOAL_KINDS,
    STARTER_KINDS,
    ConnectionStatus,
    PlacedTile,
    placed_tiles,
    predict_connection,
    start_goal_status,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.parser import parse_course
from traxgen.plates import STANDARD_SQUARE, half_hole_cells, is_buildable_on_plate
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind, TileKind
from traxgen.validator import validate_strict


def test_generate_minimal_passes_validate_strict() -> None:
    """The minimal course must pass every v1 validator rule against PRO Vertical."""
    course = generate_minimal()
    validate_strict(course, PRO_VERTICAL_STARTER_SET)  # raises on failure


def test_generate_minimal_roundtrips() -> None:
    """Serialize -> parse -> serialize produces identical bytes.

    This is the strong correctness claim: every byte we emit is a byte
    our proven parser recognizes as valid POWER_2022.
    """
    course = generate_minimal()
    bytes_1 = serialize_course(course)
    reparsed = parse_course(bytes_1)
    bytes_2 = serialize_course(reparsed)
    assert bytes_1 == bytes_2, "Round-trip byte mismatch"


def test_generate_minimal_has_expected_shape() -> None:
    """Sanity checks on the minimal course's structure.

    The minimal valid course is two adjacent tiles with NO explicit rail:
    the connection is GOAL_RAIL's integrated rail via adjacency. See
    docs/PLAN.md "Rail model breakthrough" (verified active as FLW4TMLP5V).
    """
    course = generate_minimal()

    # One layer, NO explicit rail, no pillars, no walls.
    assert len(course.layer_construction_data) == 1
    assert len(course.rail_construction_data) == 0
    assert len(course.pillar_construction_data) == 0
    assert len(course.wall_construction_data) == 0

    # Layer has exactly two cells.
    layer = course.layer_construction_data[0]
    assert len(layer.cell_construction_datas) == 2

    # Exactly one STARTER and one GOAL_RAIL present.
    cells_by_kind = {
        cell.tree_node_data.construction_data.kind: cell
        for cell in layer.cell_construction_datas
    }
    assert TileKind.STARTER in cells_by_kind
    assert TileKind.GOAL_RAIL in cells_by_kind

    # The two tiles are adjacent (hex distance 1), and the goal is rotated
    # so its integrated rail faces the starter — the proven-valid geometry.
    starter = cells_by_kind[TileKind.STARTER]
    goal = cells_by_kind[TileKind.GOAL_RAIL]
    assert starter.local_hex_position.distance_to(goal.local_hex_position) == 1
    assert goal.tree_node_data.construction_data.hex_rotation == 3


# --- Multi-plate placement (plan.md item 14) --------------------------------
#
# The s35 ruling: `generate` may propose placements the *model* predicts, not
# only ones the record has measured, with `--measured-only` as the
# conservative mode. So these tests assert both halves of that bargain
# together -- the proposal is what the model predicts, AND the course is
# *labelled* unmeasured rather than claimed valid.
#
# The label is not the generator's opinion. It comes from
# `graph.start_goal_status`, the claim surface, which answers UNMEASURED for
# any plate layout no `MeasuredRun` covers. Keeping one source for the label
# is why the generator never sets it itself.

# The geometry the search is expected to pick, frozen so a change to the
# search has to be deliberate rather than silent. Derived 2026-09-12 from
# `plates.plate_footprint` + `graph.starter_world_ports` over
# `STANDARD_SQUARE`: 33 of 36 cross-plate candidates the model calls live sit
# on a buildable square, and this is the lowest-rotation one, kept at starter
# rotation 0 so this course differs from the certified FLW4TMLP5V in plate
# count and goal cell alone.
EXPECTED_STARTER_LOCAL = HexVector(y=-4, x=0)
EXPECTED_STARTER_ROT = 0
EXPECTED_DIRECTION = 4
EXPECTED_GOAL_LOCAL = HexVector(y=-6, x=5)
EXPECTED_GOAL_ROT = 5
EXPECTED_GOAL_PLATE_OFFSET = (3, -6)


def _starter_and_goal(course: Course) -> tuple[PlacedTile, PlacedTile]:
    """The course's single starter and single goal, as placed tiles."""
    tiles = list(placed_tiles(course))
    starters = [t for t in tiles if t.kind in STARTER_KINDS]
    goals = [t for t in tiles if t.kind in GOAL_KINDS]
    assert len(starters) == 1, f"expected one starter, got {len(starters)}"
    assert len(goals) == 1, f"expected one goal, got {len(goals)}"
    return starters[0], goals[0]


def test_multi_plate_spans_more_than_one_plate() -> None:
    """The whole point of item 14: the goal is not on the starter's plate."""
    course = generate_multi_plate()
    assert len(course.layer_construction_data) > 1
    starter, goal = _starter_and_goal(course)
    starter_plate = starter.world_pos - starter.local_pos
    goal_plate = goal.world_pos - goal.local_pos
    assert (goal_plate.y, goal_plate.x) != (starter_plate.y, starter_plate.x)


def test_multi_plate_emits_the_frozen_geometry() -> None:
    """The search picks the placement recorded above, or the change is deliberate."""
    starter, goal = _starter_and_goal(generate_multi_plate())
    assert starter.local_pos == EXPECTED_STARTER_LOCAL
    assert starter.hex_rotation == EXPECTED_STARTER_ROT
    assert goal.local_pos == EXPECTED_GOAL_LOCAL
    assert goal.hex_rotation == EXPECTED_GOAL_ROT
    assert goal.kind == TileKind.GOAL_RAIL


def test_multi_plate_placement_is_one_the_model_predicts() -> None:
    """The emitted geometry is what `predict_connection` calls live.

    Not a re-implementation of the search: it asks the model surface directly,
    with `goal_plate_offset` passed explicitly, which is the term the #17 2x2
    forced and which has no default anywhere.
    """
    starter, goal = _starter_and_goal(generate_multi_plate())
    assert predict_connection(
        starter.hex_rotation,
        EXPECTED_DIRECTION,
        goal.hex_rotation,
        layer_kind=starter.layer_kind,
        starter_local_pos=starter.local_pos,
        goal_plate_offset=EXPECTED_GOAL_PLATE_OFFSET,
    )


def record_without_the_s36_row() -> tuple[graph.MeasuredRun, ...]:
    """`MEASURED_RUNS` as it stood before plan item 14's render -- s35 and earlier.

    Selected by layout rather than by position: the s36 row is the only one on
    the four-plate square, so an append elsewhere in the record cannot make
    this drop the wrong row. Asserted to drop exactly one.
    """
    before = tuple(
        run
        for run in graph.MEASURED_RUNS
        if run.plate_offsets != graph.STANDARD_SQUARE_FROM_ORIGIN_PLATE
    )
    assert len(before) == len(graph.MEASURED_RUNS) - 1
    return before


def test_the_rendered_multi_plate_course_is_claimed_connected() -> None:
    """Plan item 14, closed: a render certified this placement (s36), so the claim says so.

    Until 2026-09-14 this asserted UNMEASURED. What changed is the record, not
    the generator -- the same 253 bytes, now covered by a `MeasuredRun`.
    """
    assert start_goal_status(generate_multi_plate()) is ConnectionStatus.CONNECTED


def test_the_claim_comes_from_the_record_and_not_from_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The honesty assertion, kept by taking the render away: the same course is UNMEASURED.

    If the CONNECTED above came from anywhere but the record -- the model
    leaking onto the claim surface, say -- removing the one row that covers it
    would leave it CONNECTED, and this would fail. D041 as a test: claims and
    predictions are separate surfaces, and only a render moves a claim.
    """
    monkeypatch.setattr(graph, "MEASURED_RUNS", record_without_the_s36_row())
    assert start_goal_status(generate_multi_plate()) is ConnectionStatus.UNMEASURED


def test_half_hole_cells_are_the_three_measured_ones() -> None:
    """The derivation, pinned: a lone plate has 30 addressable cells and 27 buildable.

    Derived from the footprint rather than typed, so this asserts the
    derivation still produces what `scripts/probe_plate_seams.py` measured.
    """
    assert half_hole_cells(LayerKind.BASE_LAYER_PIECE) == frozenset(
        {(-2, 5), (-1, 3), (0, 1)}
    )


def test_no_candidate_places_a_tile_on_a_half_hole() -> None:
    """D066 over the whole candidate set, not just the one the search returns.

    Asserting it of the chosen placement alone was vacuous: that cell is not a
    half-hole, so the assertion held whether or not the rule was applied.
    Swept over every candidate, this test fails the moment
    `is_buildable_on_plate` stops excluding them -- which is the only way it
    can be a test of the rule rather than of one lucky cell.
    """
    kind = LayerKind.BASE_LAYER_PIECE
    plate_positions = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)
    candidates = list(_cross_plate_placements(plate_positions))
    assert candidates, "the sweep needs candidates to be a sweep"
    holes = half_hole_cells(kind)
    for c in candidates:
        assert (c.starter_local.y, c.starter_local.x) not in holes
        assert (c.goal_local.y, c.goal_local.x) not in holes


def test_the_candidate_set_is_the_size_the_record_says() -> None:
    """The measured envelope, pinned so a model change shows up as a count change.

    33 candidates over 11 distinct starter->goal pairs, on `STANDARD_SQUARE`,
    as of 2026-09-12. Goals land on plates 1 and 2 only: plate 3 sits
    diagonally from the starter's plate and shares no cell boundary with it.
    """
    plate_positions = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)
    candidates = list(_cross_plate_placements(plate_positions))
    pairs = {
        (
            (c.starter_local.y, c.starter_local.x),
            (c.goal_plate_index, c.goal_local.y, c.goal_local.x),
        )
        for c in candidates
    }
    assert len(candidates) == 33
    assert len(pairs) == 11
    assert {c.goal_plate_index for c in candidates} == {1, 2}


def test_the_certified_starter_cell_cannot_reach_another_plate_unrotated() -> None:
    """Why this course is not a one-variable change from the certified one.

    At rotation 0 the starter's three ports face the even directions, and from
    the certified cell (0,0) all three land on its own plate. So crossing a
    plate boundary from that cell *requires* an odd rotation: no candidate
    exists at rotation 0. The minimum honest delta from FLW4TMLP5V is two
    terms, and this test is why the search holds rotation at 0 -- the
    best-covered value in the record -- and moves the cell instead.
    """
    plate_positions = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)
    from_certified_cell = [
        c
        for c in _cross_plate_placements(plate_positions)
        if (c.starter_local.y, c.starter_local.x) == (0, 0)
    ]
    assert from_certified_cell, "the certified cell should reach a plate somehow"
    assert {c.starter_rot for c in from_certified_cell} == {1, 3, 5}


def test_multi_plate_goal_sits_on_a_buildable_square() -> None:
    """D066 for the emitted course: the editor would accept this square."""
    course = generate_multi_plate()
    _, goal = _starter_and_goal(course)
    assert is_buildable_on_plate(goal.layer_kind, goal.local_pos)


def test_measured_only_returns_exactly_the_course_a_render_certified() -> None:
    """The conservative mode has something to emit now, and it is the rendered course.

    Until s36 this asserted a refusal, and its own docstring said it would
    change meaning once a render certified a placement. Byte identity with the
    default search is the strong form of the claim: it proves the row keys on
    precisely what the generator emits, not on some neighbouring placement
    that happens to share a lookup key.
    """
    measured = generate_multi_plate(measured_only=True)
    assert serialize_course(measured) == serialize_course(generate_multi_plate())
    assert start_goal_status(measured) is ConnectionStatus.CONNECTED


def test_measured_only_still_refuses_where_nothing_is_measured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal path survives the row: take it away and the mode refuses again."""
    monkeypatch.setattr(graph, "MEASURED_RUNS", record_without_the_s36_row())
    with pytest.raises(NoBuildablePlacementError):
        generate_multi_plate(measured_only=True)


def test_unmodelled_goal_kind_is_refused_not_predicted() -> None:
    """D074: the model is STARTER -> GOAL_RAIL only, so a basin gets no prediction."""
    with pytest.raises(UnmodelledGoalKindError):
        generate_multi_plate(goal_kind=TileKind.GOAL_BASIN)


def test_multi_plate_passes_validate_strict() -> None:
    """Every v1 validator rule, against PRO Vertical."""
    validate_strict(generate_multi_plate(), PRO_VERTICAL_STARTER_SET)


def test_multi_plate_roundtrips() -> None:
    """Serialize -> parse -> serialize is byte-identical, as for the minimal course."""
    course = generate_multi_plate()
    bytes_1 = serialize_course(course)
    bytes_2 = serialize_course(parse_course(bytes_1))
    assert bytes_1 == bytes_2, "Round-trip byte mismatch"
