"""Tests for the validator — types, entry points, and registered rules.

Path: traxgen/tests/test_validator.py
"""

from __future__ import annotations

import pytest

from traxgen.domain import (
    CellConstructionData,
    Course,
    CourseMetaData,
    LayerConstructionData,
    RailConstructionData,
    RailConstructionExitIdentifier,
    SaveDataHeader,
    TileTowerConstructionData,
    TileTowerTreeNodeData,
    WallBalconyConstructionData,
    WallConstructionData,
    WallCoordinate,
)
from traxgen.hex import HexVector
from traxgen.inventory import CORE_STARTER_SET, PRO_VERTICAL_STARTER_SET, PillarKind, WallKind
from traxgen.types import (
    CourseElementGeneration,
    CourseKind,
    CourseSaveDataVersion,
    LayerKind,
    ObjectiveKind,
    RailKind,
    TileKind,
    WallSide,
)
from traxgen.validator import (
    Location,
    Rule,
    Severity,
    ValidationError,
    Violation,
    validate,
    validate_strict,
)


# --- Builders -------------------------------------------------------------

def _empty_course() -> Course:
    """Minimal valid Course with no layers/rails/pillars/walls."""
    return Course(
        header=SaveDataHeader(guid=0, version=CourseSaveDataVersion.POWER_2022),
        meta_data=CourseMetaData(
            creation_timestamp=0,
            title="",
            order_number=-1,
            course_kind=CourseKind.CUSTOM,
            objective_kind=ObjectiveKind.NONE,
            difficulty=0,
            completed=False,
        ),
        layer_construction_data=(),
        rail_construction_data=(),
        pillar_construction_data=(),
        generation=CourseElementGeneration.POWER,
        wall_construction_data=(),
    )


def _tile(kind: TileKind, *, h: int = 0, rot: int = 0) -> TileTowerConstructionData:
    """Build a minimal TileTowerConstructionData for the given TileKind."""
    return TileTowerConstructionData(
        kind=kind,
        height_in_small_stacker=h,
        hex_rotation=rot,
    )


def _node(
    kind: TileKind, *, index: int = 0, h: int = 0,
    children: tuple[TileTowerTreeNodeData, ...] = (),
) -> TileTowerTreeNodeData:
    """Build a tree node wrapping a tile of the given kind."""
    return TileTowerTreeNodeData(
        index=index,
        construction_data=_tile(kind, h=h),
        children=children,
    )


def _cell(kind: TileKind, *, y: int = 0, x: int = 0) -> CellConstructionData:
    """Build a cell at (y, x) containing a single-tile tree."""
    return CellConstructionData(
        local_hex_position=HexVector(y=y, x=x),
        tree_node_data=_node(kind),
    )


def _cell_with_h(
    kind: TileKind, *, h: int, y: int = 0, x: int = 0,
) -> CellConstructionData:
    """Build a cell at (y, x) containing a single tile with the given h value."""
    return CellConstructionData(
        local_hex_position=HexVector(y=y, x=x),
        tree_node_data=_node(kind, h=h),
    )


def _layer(
    *cells: CellConstructionData, layer_id: int = 0,
    kind: LayerKind = LayerKind.BASE_LAYER,
) -> LayerConstructionData:
    """Build a layer from the given cells."""
    return LayerConstructionData(
        layer_id=layer_id,
        layer_kind=kind,
        layer_height=0.0,
        world_hex_position=HexVector(y=0, x=0),
        cell_construction_datas=cells,
    )


def _course_with(
    *layers: LayerConstructionData,
    walls: tuple[WallConstructionData, ...] = (),
    rails: tuple[RailConstructionData, ...] = (),
) -> Course:
    """Build a course with the given layers and optional walls/rails."""
    return Course(
        header=SaveDataHeader(guid=0, version=CourseSaveDataVersion.POWER_2022),
        meta_data=CourseMetaData(
            creation_timestamp=0, title="", order_number=-1,
            course_kind=CourseKind.CUSTOM, objective_kind=ObjectiveKind.NONE,
            difficulty=0, completed=False,
        ),
        layer_construction_data=layers,
        rail_construction_data=rails,
        pillar_construction_data=(),
        generation=CourseElementGeneration.POWER,
        wall_construction_data=walls,
    )


# --- Type construction ----------------------------------------------------

def test_violation_construction_without_location() -> None:
    v = Violation(Severity.ERROR, Rule.INVENTORY_BUDGET_TILES, "test")
    assert v.severity is Severity.ERROR
    assert v.rule is Rule.INVENTORY_BUDGET_TILES
    assert v.message == "test"
    assert v.location is None


def test_violation_construction_with_location() -> None:
    loc = Location(layer_id=0)
    v = Violation(Severity.WARNING, Rule.CELL_COLLISION, "x", location=loc)
    assert v.location is loc


def test_severity_ordering() -> None:
    """ERROR > WARNING so severity filtering works as expected."""
    assert Severity.ERROR > Severity.WARNING


def test_location_all_fields_optional() -> None:
    loc = Location()
    assert loc.layer_id is None
    assert loc.hex_position is None
    assert loc.retainer_id is None
    assert loc.rail_index is None
    assert loc.pillar_index is None


def test_rule_values_are_unique() -> None:
    values = [r.value for r in Rule]
    assert len(values) == len(set(values))


# --- ValidationError ------------------------------------------------------

def test_validation_error_carries_violations() -> None:
    v = Violation(Severity.ERROR, Rule.CELL_COLLISION, "bang")
    exc = ValidationError([v])
    assert exc.violations == [v]
    assert "bang" in str(exc)


def test_validation_error_is_raisable() -> None:
    v = Violation(Severity.ERROR, Rule.INVENTORY_BUDGET_TILES, "x")
    with pytest.raises(ValidationError) as info:
        raise ValidationError([v])
    assert info.value.violations == [v]


# --- Entry points, empty course ------------------------------------------

def test_validate_flags_missing_starter_and_goal_on_empty_course() -> None:
    """An empty course is missing both a starter and a goal — fundamental requirements.

    An empty course has no placed pieces, so no budget rule fires. The only
    violations come from MISSING_STARTER_OR_GOAL — two of them, one for the
    missing starter, one for the missing goal.
    """
    violations = validate(_empty_course(), CORE_STARTER_SET)
    assert len(violations) == 2
    assert all(v.rule is Rule.MISSING_STARTER_OR_GOAL for v in violations)


def test_validate_strict_raises_for_empty_course() -> None:
    """An empty course fails MISSING_STARTER_OR_GOAL; strict mode raises."""
    with pytest.raises(ValidationError):
        validate_strict(_empty_course(), CORE_STARTER_SET)


# --- INVENTORY_BUDGET_TILES -----------------------------------------------

def _budget_tiles_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just INVENTORY_BUDGET_TILES violations."""
    return [v for v in violations if v.rule is Rule.INVENTORY_BUDGET_TILES]


def test_budget_tiles_under_limit_passes() -> None:
    """Exactly-at-budget placement (1 starter, 28 curves) produces no tiles violations."""
    cells = [_cell(TileKind.STARTER, y=0, x=0)]
    cells += [_cell(TileKind.CURVE, y=i, x=0) for i in range(1, 29)]
    course = _course_with(_layer(*cells))
    assert _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_tiles_single_overrun_fires_once() -> None:
    """29 curves against a 28-curve budget fires one tiles violation, no more."""
    cells = [_cell(TileKind.CURVE, y=i, x=0) for i in range(29)]
    course = _course_with(_layer(*cells))
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.INVENTORY_BUDGET_TILES
    assert v.severity is Severity.ERROR
    assert "CURVE" in v.message
    assert "29" in v.message
    assert "28" in v.message


def test_budget_tiles_piece_not_in_inventory_is_overrun() -> None:
    """Placing a piece absent from inventory (VOLCANO in PRO) trips the rule (budget = 0)."""
    course = _course_with(_layer(_cell(TileKind.VOLCANO)))
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert violations[0].rule is Rule.INVENTORY_BUDGET_TILES
    assert "VOLCANO" in violations[0].message


def test_budget_tiles_counts_tiles_in_stacked_tree() -> None:
    """Tiles stacked as children also count against the budget."""
    # Single cell with 29 CURVEs stacked in one tree (parent + 28 children).
    stack = _node(TileKind.CURVE, index=0, children=tuple(
        _node(TileKind.CURVE, index=i) for i in range(1, 29)
    ))
    cell = CellConstructionData(
        local_hex_position=HexVector(y=0, x=0),
        tree_node_data=stack,
    )
    course = _course_with(_layer(cell))
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "CURVE" in violations[0].message


def test_budget_tiles_counts_tiles_in_balcony_cells() -> None:
    """Tiles placed in wall-balcony cells also count against the budget."""
    # 28 curves on the baseplate (at budget) + 1 in a balcony → over budget.
    base_cells = [_cell(TileKind.CURVE, y=i, x=0) for i in range(28)]
    balcony_cell = CellConstructionData(
        local_hex_position=HexVector(y=99, x=99),
        tree_node_data=_node(TileKind.CURVE),
    )
    wall = WallConstructionData(
        lower_stacker_tower_1_retainer_id=0,
        lower_stacker_tower_1_local_hex_pos=HexVector(y=0, x=0),
        lower_stacker_tower_2_retainer_id=1,
        lower_stacker_tower_2_local_hex_pos=HexVector(y=1, x=0),
        balcony_construction_datas=(
            WallBalconyConstructionData(
                retainer_id=42,
                wall_side=WallSide.WEST,
                wall_coordinate=WallCoordinate(column=0, row=0),
                cell_construction_data=balcony_cell,
            ),
        ),
    )
    course = _course_with(_layer(*base_cells), walls=(wall,))
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "CURVE" in violations[0].message
    assert "29" in violations[0].message


# --- Baseplate sub-check --------------------------------------------------

def test_budget_tiles_baseplate_overrun() -> None:
    """5 BASE_LAYER layers vs budget of 4 fires one violation."""
    layers = tuple(_layer(layer_id=i, kind=LayerKind.BASE_LAYER) for i in range(5))
    course = _course_with(*layers)
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.INVENTORY_BUDGET_TILES
    assert "Baseplate" in v.message
    assert "5" in v.message
    assert "4" in v.message


def test_budget_tiles_baseplate_does_not_count_base_layer_piece() -> None:
    """BASE_LAYER_PIECE layers don't count toward baseplate budget."""
    # 4 real baseplates + 20 BASE_LAYER_PIECE layers; still at budget.
    real = [_layer(layer_id=i, kind=LayerKind.BASE_LAYER) for i in range(4)]
    pieces = [
        _layer(layer_id=100 + i, kind=LayerKind.BASE_LAYER_PIECE) for i in range(20)
    ]
    course = _course_with(*real, *pieces)
    assert _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


# --- Switch pool ----------------------------------------------------------

def test_budget_tiles_switch_pool_at_limit_passes() -> None:
    """2 SWITCH_LEFT + 0 SWITCH_RIGHT = exactly at pool size, no tiles violations."""
    course = _course_with(_layer(
        _cell(TileKind.SWITCH_LEFT, y=0, x=0),
        _cell(TileKind.SWITCH_LEFT, y=1, x=0),
    ))
    assert _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_tiles_switch_pool_exceeded() -> None:
    """2 SWITCH_LEFT + 1 SWITCH_RIGHT against pool of 2 fires one pool violation."""
    course = _course_with(_layer(
        _cell(TileKind.SWITCH_LEFT, y=0, x=0),
        _cell(TileKind.SWITCH_LEFT, y=1, x=0),
        _cell(TileKind.SWITCH_RIGHT, y=2, x=0),
    ))
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    # Exactly one tiles violation — pool check, not per-kind (per-kind is skipped for switches).
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.INVENTORY_BUDGET_TILES
    assert "pool" in v.message.lower()
    assert "SWITCH_LEFT" in v.message
    assert "SWITCH_RIGHT" in v.message


def test_budget_tiles_switch_per_kind_not_reported() -> None:
    """Switches never produce per-kind violations, only pool violations."""
    # 3 SWITCH_LEFT against a kind-limit of 2 — would be per-kind violation
    # if we weren't skipping switches, plus a pool violation. We only want the pool one.
    course = _course_with(_layer(
        _cell(TileKind.SWITCH_LEFT, y=0, x=0),
        _cell(TileKind.SWITCH_LEFT, y=1, x=0),
        _cell(TileKind.SWITCH_LEFT, y=2, x=0),
    ))
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "pool" in violations[0].message.lower()


# --- Multiple independent overruns ----------------------------------------

def test_budget_tiles_multiple_overruns_all_reported() -> None:
    """Per-kind violations are sorted by TileKind.value for deterministic output."""
    # STARTER budget is 1 → place 2. CURVE budget is 28 → place 29.
    # STARTER.value=1, CURVE.value=2, so STARTER violation comes first.
    cells = [
        _cell(TileKind.STARTER, y=0, x=0),
        _cell(TileKind.STARTER, y=0, x=1),
    ]
    cells += [_cell(TileKind.CURVE, y=1, x=i) for i in range(29)]
    course = _course_with(_layer(*cells))
    violations = _budget_tiles_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    assert "STARTER" in violations[0].message
    assert "CURVE" in violations[1].message


def test_budget_tiles_strict_raises() -> None:
    """validate_strict raises ValidationError when budget violations exist."""
    course = _course_with(_layer(*[_cell(TileKind.CURVE, y=i) for i in range(29)]))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    tiles_violations = [
        v for v in info.value.violations
        if v.rule is Rule.INVENTORY_BUDGET_TILES
    ]
    assert len(tiles_violations) == 1
    assert tiles_violations[0].rule is Rule.INVENTORY_BUDGET_TILES


# --- INVENTORY_BUDGET_STACKERS --------------------------------------------
#
# PRO Vertical budget: 20 large + 9 small = 49 small-stacker units capacity,
# 9 smalls available for odd-height stacks.

def _stacker_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just INVENTORY_BUDGET_STACKERS violations."""
    return [v for v in violations if v.rule is Rule.INVENTORY_BUDGET_STACKERS]


def test_budget_stackers_all_zero_heights_passes() -> None:
    """Many tiles with h=0 across the board → stacker rule doesn't fire."""
    # 28 curves at h=0 fits tile budget comfortably, stacker usage is 0.
    cells = [_cell(TileKind.CURVE, y=i, x=0) for i in range(28)]
    course = _course_with(_layer(*cells))
    assert _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_stackers_at_total_capacity_passes() -> None:
    """49 units total, all even (no odd stacks) — exactly at capacity, no violations."""
    # Need stacks summing to 49 with zero odd-h stacks. 49 is odd, but the
    # rule only counts *per-stack* oddness, not total — actually wait, 49
    # can't be reached with all-even stacks (sum of evens is even). Use 48
    # units all-even: 24 stacks of h=2. That's under capacity; still no
    # violation. To test the at-capacity edge exactly, use e.g. 23 stacks
    # of h=2 (46) + 3 stacks of h=1 (3 units, 3 odd): total 49 = capacity,
    # 3 odd <= 9 smalls. Passes both checks at the edge.
    cells = [
        _cell_with_h(TileKind.CURVE, h=2, y=0, x=i) for i in range(23)
    ]
    cells += [
        _cell_with_h(TileKind.CURVE, h=1, y=1, x=i) for i in range(3)
    ]
    course = _course_with(_layer(*cells))
    assert _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_stackers_total_overrun_only() -> None:
    """50 units total, all even (0 odd stacks) — total fails, parity passes."""
    # 25 stacks of h=2 = 50 units, 0 odd. Over capacity (49).
    cells = [_cell_with_h(TileKind.CURVE, h=2, y=0, x=i) for i in range(25)]
    course = _course_with(_layer(*cells))
    violations = _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.INVENTORY_BUDGET_STACKERS
    assert v.severity is Severity.ERROR
    assert "50" in v.message
    assert "49" in v.message
    assert "Stacker budget exceeded" in v.message


def test_budget_stackers_parity_overrun_only() -> None:
    """10 stacks of h=1 = 10 units (under capacity), 10 odd (over 9 smalls)."""
    cells = [_cell_with_h(TileKind.CURVE, h=1, y=0, x=i) for i in range(10)]
    course = _course_with(_layer(*cells))
    violations = _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.INVENTORY_BUDGET_STACKERS
    assert "10" in v.message
    assert "9" in v.message
    assert "Small stacker shortfall" in v.message


def test_budget_stackers_both_overruns_reported() -> None:
    """Total > 49 AND odd_count > 9 → both violations emitted."""
    # 10 stacks of h=11 (odd): total 110, odd_count 10. Breaks both checks.
    cells = [_cell_with_h(TileKind.CURVE, h=11, y=0, x=i) for i in range(10)]
    course = _course_with(_layer(*cells))
    violations = _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    messages = [v.message for v in violations]
    assert any("Stacker budget exceeded" in m for m in messages)
    assert any("Small stacker shortfall" in m for m in messages)


def test_budget_stackers_counts_heights_on_stacked_children() -> None:
    """h values on child nodes count toward the sum, not just roots."""
    # Single cell: pillar(h=2) → curve(h=48). Total 50 > 49 capacity.
    tree = _node(TileKind.STACKER_TOWER_CLOSED, index=0, h=2, children=(
        _node(TileKind.CURVE, index=1, h=48),
    ))
    cell = CellConstructionData(
        local_hex_position=HexVector(y=0, x=0),
        tree_node_data=tree,
    )
    course = _course_with(_layer(cell))
    violations = _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "Stacker budget exceeded" in violations[0].message
    assert "50" in violations[0].message


def test_budget_stackers_counts_heights_in_balcony_cells() -> None:
    """h values on tiles in balcony-mounted cells count too."""
    # 24 curves at h=2 on baseplate = 48 units, 0 odd. Balcony-mounted curve
    # at h=2 pushes total to 50, triggering total overrun.
    base_cells = [_cell_with_h(TileKind.CURVE, h=2, y=i, x=0) for i in range(24)]
    balcony_cell = CellConstructionData(
        local_hex_position=HexVector(y=99, x=99),
        tree_node_data=_node(TileKind.CURVE, h=2),
    )
    wall = WallConstructionData(
        lower_stacker_tower_1_retainer_id=0,
        lower_stacker_tower_1_local_hex_pos=HexVector(y=0, x=0),
        lower_stacker_tower_2_retainer_id=1,
        lower_stacker_tower_2_local_hex_pos=HexVector(y=1, x=0),
        balcony_construction_datas=(
            WallBalconyConstructionData(
                retainer_id=42,
                wall_side=WallSide.WEST,
                wall_coordinate=WallCoordinate(column=0, row=0),
                cell_construction_data=balcony_cell,
            ),
        ),
    )
    course = _course_with(_layer(*base_cells), walls=(wall,))
    violations = _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "50" in violations[0].message


def test_budget_stackers_pillar_h_counts_as_stack() -> None:
    """A pillar with h>0 counts as a stack like any other tree node (no kind exceptions)."""
    # 10 pillars, each with h=1 (cells are independent so no tree nesting needed).
    # Total 10 units (under capacity), but 10 odd stacks (over 9 smalls).
    cells = [_cell_with_h(TileKind.STACKER_TOWER_CLOSED, h=1, y=0, x=i) for i in range(10)]
    course = _course_with(_layer(*cells))
    violations = _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "Small stacker shortfall" in violations[0].message
    assert "10" in violations[0].message


def test_budget_stackers_zero_h_does_not_count_as_stack() -> None:
    """h=0 tiles must not be counted as 'even stacks' (they're not stacks at all)."""
    # 50 tiles at h=0. If h=0 counted as an even stack, total would still be 0
    # (fine) and odd_count would be 0 (fine). So this test is really about
    # ensuring the behavior is correct for the boundary: no false positives
    # from zero-height placements.
    cells = [_cell(TileKind.CURVE, y=0, x=i) for i in range(28)]
    course = _course_with(_layer(*cells))
    assert _stacker_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_stackers_strict_raises() -> None:
    """validate_strict raises when stacker violations exist."""
    cells = [_cell_with_h(TileKind.CURVE, h=2, y=0, x=i) for i in range(25)]
    course = _course_with(_layer(*cells))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    stacker_violations = [
        v for v in info.value.violations
        if v.rule is Rule.INVENTORY_BUDGET_STACKERS
    ]
    assert len(stacker_violations) == 1


# --- INVENTORY_BUDGET_STRUCTURAL -------------------------------------------
#
# PRO Vertical structural budget:
#   Pillars: 8 CLOSED + 4 OPENED
#   Walls:   1 SHORT + 2 MEDIUM + 2 LONG
#   Balconies: 16 single + 4 double

def _structural_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just INVENTORY_BUDGET_STRUCTURAL violations."""
    return [v for v in violations if v.rule is Rule.INVENTORY_BUDGET_STRUCTURAL]


def _wall(
    *, tower1: HexVector, tower2: HexVector,
    balconies: tuple[WallBalconyConstructionData, ...] = (),
) -> WallConstructionData:
    """Build a wall between two tower positions with optional balconies."""
    return WallConstructionData(
        lower_stacker_tower_1_retainer_id=0,
        lower_stacker_tower_1_local_hex_pos=tower1,
        lower_stacker_tower_2_retainer_id=1,
        lower_stacker_tower_2_local_hex_pos=tower2,
        balcony_construction_datas=balconies,
    )


def test_budget_structural_empty_passes() -> None:
    """A course with no structural pieces has no structural violations."""
    course = _course_with(_layer(_cell(TileKind.CURVE, y=0, x=0)))
    assert _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_structural_pillar_closed_overrun() -> None:
    """9 CLOSED pillars against PRO Vertical budget of 8 fires one violation."""
    cells = [_cell(TileKind.STACKER_TOWER_CLOSED, y=0, x=i) for i in range(9)]
    course = _course_with(_layer(*cells))
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.INVENTORY_BUDGET_STRUCTURAL
    assert v.severity is Severity.ERROR
    assert "CLOSED" in v.message
    assert "9" in v.message
    assert "8" in v.message


def test_budget_structural_pillar_opened_overrun() -> None:
    """5 OPENED pillars against PRO Vertical budget of 4 fires one violation."""
    cells = [_cell(TileKind.STACKER_TOWER_OPENED, y=0, x=i) for i in range(5)]
    course = _course_with(_layer(*cells))
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "OPENED" in violations[0].message


def test_budget_structural_pillars_at_limit_pass() -> None:
    """Exactly 8 CLOSED and 4 OPENED pillars — at budget, no violations."""
    closed = [_cell(TileKind.STACKER_TOWER_CLOSED, y=0, x=i) for i in range(8)]
    opened = [_cell(TileKind.STACKER_TOWER_OPENED, y=1, x=i) for i in range(4)]
    course = _course_with(_layer(*closed, *opened))
    assert _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_structural_pillars_counted_in_stacked_trees() -> None:
    """Pillars nested as children of other tree nodes still count."""
    # 8 root CLOSED pillars + 1 child CLOSED pillar = 9 CLOSED → over budget.
    root_with_child = _node(TileKind.STACKER_TOWER_CLOSED, index=0, children=(
        _node(TileKind.STACKER_TOWER_CLOSED, index=1),
    ))
    cell_nested = CellConstructionData(
        local_hex_position=HexVector(y=99, x=99),
        tree_node_data=root_with_child,
    )
    other_cells = [_cell(TileKind.STACKER_TOWER_CLOSED, y=0, x=i) for i in range(7)]
    course = _course_with(_layer(*other_cells, cell_nested))
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "CLOSED" in violations[0].message


def test_budget_structural_wall_short_inferred_from_distance_one() -> None:
    """A wall with endpoints 1 hex apart is SHORT; PRO budget is 1."""
    # 2 SHORT walls → over budget (1).
    wall_1 = _wall(tower1=HexVector(y=0, x=0), tower2=HexVector(y=0, x=1))
    wall_2 = _wall(tower1=HexVector(y=2, x=0), tower2=HexVector(y=2, x=1))
    course = _course_with(_layer(), walls=(wall_1, wall_2))
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "SHORT" in violations[0].message
    assert "2" in violations[0].message
    assert "1" in violations[0].message


def test_budget_structural_wall_medium_inferred_from_distance_two() -> None:
    """A wall with endpoints 2 hexes apart is MEDIUM; PRO budget is 2."""
    # 3 MEDIUM walls → over budget (2).
    walls = tuple(
        _wall(
            tower1=HexVector(y=i, x=0),
            tower2=HexVector(y=i, x=2),
        )
        for i in range(3)
    )
    course = _course_with(_layer(), walls=walls)
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "MEDIUM" in violations[0].message


def test_budget_structural_wall_long_inferred_from_distance_three() -> None:
    """A wall with endpoints 3 hexes apart is LONG; PRO budget is 2."""
    # 3 LONG walls → over budget (2).
    walls = tuple(
        _wall(
            tower1=HexVector(y=i, x=0),
            tower2=HexVector(y=i, x=3),
        )
        for i in range(3)
    )
    course = _course_with(_layer(), walls=walls)
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "LONG" in violations[0].message


def test_budget_structural_wall_unmappable_distance_silently_skipped() -> None:
    """Walls with hex distance outside {1,2,3} don't count toward any wall budget."""
    # A wall spanning 5 hexes — not a valid wall length. Should be ignored,
    # not double-counted as a LONG. Budget is 2 LONG walls; we add 2 LONG +
    # 1 unmappable. Total valid LONG = 2, at budget, no violation.
    long_walls = tuple(
        _wall(tower1=HexVector(y=i, x=0), tower2=HexVector(y=i, x=3))
        for i in range(2)
    )
    bogus_wall = _wall(tower1=HexVector(y=10, x=0), tower2=HexVector(y=10, x=5))
    course = _course_with(_layer(), walls=long_walls + (bogus_wall,))
    assert _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_structural_single_balcony_overrun() -> None:
    """17 mounted single balconies against PRO budget of 16 fires one violation."""
    # One wall with 17 mounted balcony cells. Use distance 1 so wall-length
    # inference picks SHORT (PRO has 1 SHORT budget → 1 wall fits).
    mounted = tuple(
        WallBalconyConstructionData(
            retainer_id=100 + i,
            wall_side=WallSide.WEST,
            wall_coordinate=WallCoordinate(column=i, row=0),
            cell_construction_data=CellConstructionData(
                local_hex_position=HexVector(y=i, x=0),
                tree_node_data=_node(TileKind.CURVE),
            ),
        )
        for i in range(17)
    )
    wall = _wall(
        tower1=HexVector(y=0, x=0),
        tower2=HexVector(y=0, x=1),
        balconies=mounted,
    )
    course = _course_with(_layer(), walls=(wall,))
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert "Single balcony" in v.message
    assert "17" in v.message
    assert "16" in v.message


def test_budget_structural_empty_balcony_slots_do_not_count() -> None:
    """Balcony slots with cell_construction_data=None don't consume inventory."""
    # 20 empty balcony slots on a SHORT wall. Should not trip 16-balcony limit.
    empty_slots = tuple(
        WallBalconyConstructionData(
            retainer_id=100 + i,
            wall_side=WallSide.WEST,
            wall_coordinate=WallCoordinate(column=i, row=0),
            cell_construction_data=None,
        )
        for i in range(20)
    )
    wall = _wall(
        tower1=HexVector(y=0, x=0),
        tower2=HexVector(y=0, x=1),
        balconies=empty_slots,
    )
    course = _course_with(_layer(), walls=(wall,))
    assert _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_structural_double_balcony_overrun() -> None:
    """5 DOUBLE_BALCONY tree nodes against PRO budget of 4 fires one violation."""
    cells = [_cell(TileKind.DOUBLE_BALCONY, y=0, x=i) for i in range(5)]
    course = _course_with(_layer(*cells))
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert "Double balcony" in v.message
    assert "5" in v.message
    assert "4" in v.message


def test_budget_structural_multiple_overruns_all_reported() -> None:
    """Independent structural overruns each get their own violation."""
    # 9 CLOSED pillars (over 8), 5 DOUBLE_BALCONY (over 4), all in one course.
    closed = [_cell(TileKind.STACKER_TOWER_CLOSED, y=0, x=i) for i in range(9)]
    doubles = [_cell(TileKind.DOUBLE_BALCONY, y=1, x=i) for i in range(5)]
    course = _course_with(_layer(*closed, *doubles))
    violations = _structural_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    messages = [v.message for v in violations]
    assert any("CLOSED" in m for m in messages)
    assert any("Double balcony" in m for m in messages)


def test_budget_structural_pillars_do_not_trip_tiles_rule() -> None:
    """Structural tile kinds are skipped in the tiles per-kind budget check."""
    # Place pillars at limit in a Core-inventory context (zero structural budget).
    # Without the structural-kinds skip in the tiles rule, this would emit
    # false-positive 'piece not in inventory' violations for each pillar.
    cells = [_cell(TileKind.STACKER_TOWER_CLOSED, y=0, x=0)]
    course = _course_with(_layer(*cells))
    violations = validate(course, CORE_STARTER_SET)
    # Tiles rule should not fire for the pillar (structural kind skipped).
    tile_violations = [v for v in violations if v.rule is Rule.INVENTORY_BUDGET_TILES]
    assert tile_violations == []
    # Structural rule should fire because CORE has zero pillar budget.
    structural_violations = _structural_violations(violations)
    assert len(structural_violations) == 1
    assert "CLOSED" in structural_violations[0].message


def test_budget_structural_strict_raises() -> None:
    """validate_strict raises when structural violations exist."""
    cells = [_cell(TileKind.STACKER_TOWER_CLOSED, y=0, x=i) for i in range(9)]
    course = _course_with(_layer(*cells))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    structural = [
        v for v in info.value.violations
        if v.rule is Rule.INVENTORY_BUDGET_STRUCTURAL
    ]
    assert len(structural) == 1


# --- INVENTORY_BUDGET_RAILS ------------------------------------------------
#
# PRO Vertical rail budget:
#   STRAIGHT pool: 18 total (9 SHORT + 6 MEDIUM + 3 LONG by length)
#   Bernoulli: 3 LEFT + 3 RIGHT + 2 STRAIGHT

def _rail_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just INVENTORY_BUDGET_RAILS violations."""
    return [v for v in violations if v.rule is Rule.INVENTORY_BUDGET_RAILS]


def _rail(
    kind: RailKind,
    *, p1: HexVector, p2: HexVector,
    retainer_1: int = 0, retainer_2: int = 0,
) -> RailConstructionData:
    """Build a rail between two endpoints at cell-local positions p1 and p2."""
    return RailConstructionData(
        exit_1_identifier=RailConstructionExitIdentifier(
            retainer_id=retainer_1,
            cell_local_hex_pos=p1,
            side_hex_rot=0,
            exit_local_pos_y=0.0,
        ),
        exit_2_identifier=RailConstructionExitIdentifier(
            retainer_id=retainer_2,
            cell_local_hex_pos=p2,
            side_hex_rot=0,
            exit_local_pos_y=0.0,
        ),
        rail_kind=kind,
    )


def _straight(distance: int, *, offset: int = 0) -> RailConstructionData:
    """Build a STRAIGHT rail spanning `distance` hexes. `offset` disambiguates multiple rails."""
    return _rail(
        RailKind.STRAIGHT,
        p1=HexVector(y=offset, x=0),
        p2=HexVector(y=offset, x=distance),
    )


def test_budget_rails_empty_passes() -> None:
    """Course with no rails has no rail violations."""
    course = _course_with(_layer(_cell(TileKind.CURVE, y=0, x=0)))
    assert _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_rails_under_budget_passes() -> None:
    """A modest sprinkling of rails, all within budget, produces no violations."""
    rails = (
        _straight(1, offset=0),  # SHORT
        _straight(2, offset=1),  # MEDIUM
        _straight(3, offset=2),  # LONG
        _rail(RailKind.BERNOULLI_SMALL_LEFT,
              p1=HexVector(y=10, x=0), p2=HexVector(y=10, x=1)),
    )
    course = _course_with(_layer(), rails=rails)
    assert _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_budget_rails_per_kind_bernoulli_overrun() -> None:
    """4 BERNOULLI_SMALL_LEFT against PRO budget of 3 fires one per-kind violation."""
    rails = tuple(
        _rail(RailKind.BERNOULLI_SMALL_LEFT,
              p1=HexVector(y=i, x=0), p2=HexVector(y=i, x=1))
        for i in range(4)
    )
    course = _course_with(_layer(), rails=rails)
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.INVENTORY_BUDGET_RAILS
    assert v.severity is Severity.ERROR
    assert "BERNOULLI_SMALL_LEFT" in v.message
    assert "4" in v.message
    assert "3" in v.message


def test_budget_rails_short_bucket_overrun() -> None:
    """10 distance-1 STRAIGHT rails against PRO budget of 9 SHORT fires bucket violation."""
    rails = tuple(_straight(1, offset=i) for i in range(10))
    course = _course_with(_layer(), rails=rails)
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    # STRAIGHT per-kind is 10/18 (fine). SHORT bucket is 10/9 (over).
    assert len(violations) == 1
    v = violations[0]
    assert "SHORT" in v.message
    assert "10" in v.message
    assert "9" in v.message


def test_budget_rails_medium_bucket_overrun() -> None:
    """7 distance-2 STRAIGHT rails against PRO budget of 6 MEDIUM fires bucket violation."""
    rails = tuple(_straight(2, offset=i) for i in range(7))
    course = _course_with(_layer(), rails=rails)
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "MEDIUM" in violations[0].message


def test_budget_rails_long_bucket_overrun() -> None:
    """4 distance-3 STRAIGHT rails against PRO budget of 3 LONG fires bucket violation."""
    rails = tuple(_straight(3, offset=i) for i in range(4))
    course = _course_with(_layer(), rails=rails)
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "LONG" in violations[0].message


def test_budget_rails_straight_per_kind_overrun_fires_independently() -> None:
    """19 STRAIGHT rails distributed across lengths so no bucket overruns.

    9 SHORT + 6 MEDIUM + 3 LONG = 18 at budget. Add a 10th SHORT and remove
    one MEDIUM — bucket stays fine? No, 10 SHORT overruns SHORT bucket too.
    This scenario is constructed to isolate the per-kind STRAIGHT check:
    go up in LONG-distance placements which our local metric handles fine.
    Actually: the per-kind STRAIGHT check compares placed vs inventory.rails[STRAIGHT]
    = 18. Each bucket has its own limit summing to 18, so hitting exactly 18
    STRAIGHT means every bucket is at its own limit (no over). 19 total means
    at least one bucket is over. The per-kind and bucket checks are not
    cleanly separable in PRO Vertical — they'd always fire together.
    """
    # 10 SHORT + 6 MEDIUM + 3 LONG = 19 STRAIGHT total.
    rails = (
        *(_straight(1, offset=i) for i in range(10)),
        *(_straight(2, offset=100 + i) for i in range(6)),
        *(_straight(3, offset=200 + i) for i in range(3)),
    )
    course = _course_with(_layer(), rails=rails)
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    # Expect both: per-kind STRAIGHT (19 > 18) and SHORT bucket (10 > 9).
    assert len(violations) == 2
    messages = [v.message for v in violations]
    assert any("STRAIGHT" in m and "SHORT" not in m for m in messages)
    assert any("SHORT" in m for m in messages)


def test_budget_rails_invalid_span_distance_zero() -> None:
    """A STRAIGHT rail with both endpoints at the same position has distance 0 — invalid."""
    bad = _rail(RailKind.STRAIGHT,
                p1=HexVector(y=0, x=0), p2=HexVector(y=0, x=0))
    course = _course_with(_layer(), rails=(bad,))
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.severity is Severity.ERROR
    assert "invalid span" in v.message
    assert "distance 0" in v.message
    assert v.location is not None
    assert v.location.rail_index == 0


def test_budget_rails_invalid_span_distance_four() -> None:
    """A STRAIGHT rail with distance 4 exceeds LONG's fixed span — invalid."""
    bad = _rail(RailKind.STRAIGHT,
                p1=HexVector(y=0, x=0), p2=HexVector(y=0, x=4))
    course = _course_with(_layer(), rails=(bad,))
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert "invalid span" in v.message
    assert "distance 4" in v.message


def test_budget_rails_multiple_invalid_spans_each_reported() -> None:
    """Each invalid STRAIGHT placement gets its own per-placement violation."""
    rails = (
        _rail(RailKind.STRAIGHT, p1=HexVector(y=0, x=0), p2=HexVector(y=0, x=4)),
        _rail(RailKind.STRAIGHT, p1=HexVector(y=1, x=0), p2=HexVector(y=1, x=5)),
        _rail(RailKind.STRAIGHT, p1=HexVector(y=2, x=0), p2=HexVector(y=2, x=0)),
    )
    course = _course_with(_layer(), rails=rails)
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 3
    assert all("invalid span" in v.message for v in violations)
    # Rail indices in Location should be 0, 1, 2.
    rail_indices = [v.location.rail_index for v in violations if v.location]
    assert rail_indices == [0, 1, 2]


def test_budget_rails_invalid_span_does_not_count_toward_buckets() -> None:
    """An invalid-span rail must not be bucketed and pass the bucket check."""
    # 9 valid SHORT (at budget) + 1 invalid-span rail.
    # Bucket check: SHORT = 9/9, fine. Invalid span: 1 violation. Total: 1.
    valid = tuple(_straight(1, offset=i) for i in range(9))
    bad = _rail(RailKind.STRAIGHT, p1=HexVector(y=0, x=0), p2=HexVector(y=0, x=4))
    course = _course_with(_layer(), rails=valid + (bad,))
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "invalid span" in violations[0].message


def test_budget_rails_strict_raises() -> None:
    """validate_strict raises when rail violations exist."""
    rails = tuple(
        _rail(RailKind.BERNOULLI_SMALL_LEFT,
              p1=HexVector(y=i, x=0), p2=HexVector(y=i, x=1))
        for i in range(4)
    )
    course = _course_with(_layer(), rails=rails)
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    rail_vs = [
        v for v in info.value.violations
        if v.rule is Rule.INVENTORY_BUDGET_RAILS
    ]
    assert len(rail_vs) == 1


def test_budget_rails_cross_retainer_straight_is_skipped_from_sub_budget() -> None:
    """Cross-retainer STRAIGHT rails skip the invalid-span and bucket checks.

    Local distance between endpoints on different retainers isn't physical
    distance. Until we have world-coordinate math (blocked on baseplate
    arrangement — PLAN.md open question), we skip these from the sub-budget
    rather than false-positive flag them. The GDZJZA3J3T integration test
    confirms this is necessary against real courses.

    The rail still counts toward the per-kind STRAIGHT budget since the
    piece physically exists in the course.
    """
    # A rail with cross-retainer endpoints and a would-be invalid span (5).
    # If we weren't skipping cross-retainer, this would emit "invalid span".
    cross = _rail(
        RailKind.STRAIGHT,
        p1=HexVector(y=0, x=0), p2=HexVector(y=0, x=5),
        retainer_1=100, retainer_2=200,
    )
    course = _course_with(_layer(), rails=(cross,))
    violations = _rail_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert violations == [], f"Expected no rail violations, got: {violations}"


# --- MISSING_STARTER_OR_GOAL ----------------------------------------------
#
# Fundamental requirement: the course must contain at least one starter
# tile and at least one goal tile. Starter/goal kinds are derived from
# PieceSpec.is_starter / is_goal in PIECE_CATALOG; with the current catalog,
# starters = {STARTER} and goals = {GOAL_BASIN, GOAL_RAIL}.

def _starter_goal_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just MISSING_STARTER_OR_GOAL violations."""
    return [v for v in violations if v.rule is Rule.MISSING_STARTER_OR_GOAL]


def test_starter_goal_both_present_passes() -> None:
    """A course with a STARTER and a GOAL_BASIN produces no starter/goal violations."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=0, x=0),
        _cell(TileKind.GOAL_BASIN, y=0, x=1),
    ))
    assert _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_starter_goal_missing_goal_only() -> None:
    """A course with a STARTER but no goal fires one violation for the missing goal."""
    course = _course_with(_layer(_cell(TileKind.STARTER, y=0, x=0)))
    violations = _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.MISSING_STARTER_OR_GOAL
    assert v.severity is Severity.ERROR
    assert "goal" in v.message.lower()
    # Message mentions both valid goal kinds.
    assert "GOAL_BASIN" in v.message
    assert "GOAL_RAIL" in v.message


def test_starter_goal_missing_starter_only() -> None:
    """A course with a goal but no starter fires one violation for the missing starter."""
    course = _course_with(_layer(_cell(TileKind.GOAL_BASIN, y=0, x=0)))
    violations = _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.MISSING_STARTER_OR_GOAL
    assert "starter" in v.message.lower()
    assert "STARTER" in v.message


def test_starter_goal_empty_course_fires_both() -> None:
    """An empty course fires two independent violations: one for starter, one for goal."""
    violations = _starter_goal_violations(validate(_empty_course(), PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    messages_lower = [v.message.lower() for v in violations]
    assert any("starter" in m and "goal" not in m for m in messages_lower)
    assert any("goal" in m and "starter" not in m for m in messages_lower)


def test_starter_goal_goal_basin_satisfies_goal_requirement() -> None:
    """GOAL_BASIN (the 'landing' insert) is a valid goal piece."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=0, x=0),
        _cell(TileKind.GOAL_BASIN, y=0, x=1),
    ))
    assert _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_starter_goal_goal_rail_satisfies_goal_requirement() -> None:
    """GOAL_RAIL (the 'finish line') is a valid goal piece."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=0, x=0),
        _cell(TileKind.GOAL_RAIL, y=0, x=1),
    ))
    assert _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_starter_goal_starter_in_stacked_child_counts() -> None:
    """A STARTER placed as a stacked child node still satisfies the starter requirement.

    Defensive test — ensures the walk descends into tree children, not just
    roots. Structurally odd placement (starter stacked on a curve) but the
    rule doesn't care about structural sensibility, only presence.
    """
    tree = _node(TileKind.CURVE, index=0, children=(
        _node(TileKind.STARTER, index=1),
    ))
    cell_stacked = CellConstructionData(
        local_hex_position=HexVector(y=0, x=0),
        tree_node_data=tree,
    )
    goal_cell = _cell(TileKind.GOAL_BASIN, y=0, x=1)
    course = _course_with(_layer(cell_stacked, goal_cell))
    assert _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_starter_goal_goal_in_balcony_cell_counts() -> None:
    """A goal placed in a wall-balcony cell still satisfies the goal requirement.

    Defensive test — ensures the walk visits balcony-mounted cells, not
    just layer cells.
    """
    starter_cell = _cell(TileKind.STARTER, y=0, x=0)
    goal_balcony_cell = CellConstructionData(
        local_hex_position=HexVector(y=99, x=99),
        tree_node_data=_node(TileKind.GOAL_RAIL),
    )
    wall = WallConstructionData(
        lower_stacker_tower_1_retainer_id=0,
        lower_stacker_tower_1_local_hex_pos=HexVector(y=0, x=0),
        lower_stacker_tower_2_retainer_id=1,
        lower_stacker_tower_2_local_hex_pos=HexVector(y=1, x=0),
        balcony_construction_datas=(
            WallBalconyConstructionData(
                retainer_id=42,
                wall_side=WallSide.WEST,
                wall_coordinate=WallCoordinate(column=0, row=0),
                cell_construction_data=goal_balcony_cell,
            ),
        ),
    )
    course = _course_with(_layer(starter_cell), walls=(wall,))
    assert _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_starter_goal_cannon_alone_does_not_satisfy_starter() -> None:
    """A course with only a CANNON (no STARTER) still fires the starter violation.

    End-to-end assertion that the cannon-is-not-a-starter fix flows through
    the validator. CANNON is an energy injector, not a starter — it requires
    an incoming ball to do anything. If this test fails, someone likely
    re-flagged is_starter=True on the CANNON PieceSpec.
    """
    course = _course_with(_layer(
        _cell(TileKind.CANNON, y=0, x=0),
        _cell(TileKind.GOAL_BASIN, y=0, x=1),
    ))
    violations = _starter_goal_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "starter" in violations[0].message.lower()


def test_starter_goal_strict_raises() -> None:
    """validate_strict raises when starter/goal violations exist."""
    # Goal only, no starter.
    course = _course_with(_layer(_cell(TileKind.GOAL_BASIN, y=0, x=0)))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    sg_violations = [
        v for v in info.value.violations
        if v.rule is Rule.MISSING_STARTER_OR_GOAL
    ]
    assert len(sg_violations) == 1
    assert "starter" in sg_violations[0].message.lower()


# --- LAYER_ID_COLLISION ----------------------------------------------------
#
# Layer IDs are labels used to reference layers from elsewhere in the
# binary (pillar endpoints, etc). Two layers sharing an ID would be
# ambiguous. Expected to never fire on real app-produced courses;
# primary value is guarding against our own M5 generator emitting bad IDs.

def _layer_id_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just LAYER_ID_COLLISION violations."""
    return [v for v in violations if v.rule is Rule.LAYER_ID_COLLISION]


def test_layer_id_empty_course_has_no_collisions() -> None:
    """No layers, nothing to collide."""
    assert _layer_id_violations(validate(_empty_course(), PRO_VERTICAL_STARTER_SET)) == []


def test_layer_id_single_layer_has_no_collisions() -> None:
    """A single layer can't collide with itself."""
    course = _course_with(_layer(_cell(TileKind.STARTER, y=0, x=0), layer_id=42))
    assert _layer_id_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_layer_id_distinct_ids_pass() -> None:
    """Two layers with different IDs — no violation."""
    course = _course_with(
        _layer(_cell(TileKind.STARTER, y=0, x=0), layer_id=1),
        _layer(_cell(TileKind.GOAL_BASIN, y=0, x=0), layer_id=2),
    )
    assert _layer_id_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_layer_id_duplicate_fires_one_violation() -> None:
    """Two layers with the same ID → exactly one violation."""
    course = _course_with(
        _layer(layer_id=5, kind=LayerKind.BASE_LAYER),
        _layer(layer_id=5, kind=LayerKind.SMALL_LAYER),
    )
    violations = _layer_id_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.LAYER_ID_COLLISION
    assert v.severity is Severity.ERROR
    assert "layer_id=5" in v.message
    assert "2 times" in v.message
    assert "BASE_LAYER" in v.message
    assert "SMALL_LAYER" in v.message


def test_layer_id_triple_duplicate_dedup_to_one_violation() -> None:
    """Three layers with the same ID → one violation, not two or three."""
    course = _course_with(
        _layer(layer_id=7, kind=LayerKind.BASE_LAYER),
        _layer(layer_id=7, kind=LayerKind.LARGE_LAYER),
        _layer(layer_id=7, kind=LayerKind.SMALL_LAYER),
    )
    violations = _layer_id_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert "layer_id=7" in v.message
    assert "3 times" in v.message


def test_layer_id_independent_collisions_each_reported() -> None:
    """Multiple independent collisions → one violation per colliding ID, sorted ascending."""
    course = _course_with(
        _layer(layer_id=10, kind=LayerKind.BASE_LAYER),
        _layer(layer_id=10, kind=LayerKind.BASE_LAYER),  # collides with above
        _layer(layer_id=3, kind=LayerKind.SMALL_LAYER),
        _layer(layer_id=3, kind=LayerKind.SMALL_LAYER),  # collides with above
        _layer(layer_id=99, kind=LayerKind.LARGE_LAYER),  # unique
    )
    violations = _layer_id_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    # Sorted ascending by layer_id: 3 first, then 10.
    assert "layer_id=3" in violations[0].message
    assert "layer_id=10" in violations[1].message


def test_layer_id_mixed_some_collide_some_unique() -> None:
    """A mix of unique and colliding IDs reports only the collisions."""
    course = _course_with(
        _layer(layer_id=1),
        _layer(layer_id=2),
        _layer(layer_id=2),  # collides with above
        _layer(layer_id=3),
    )
    violations = _layer_id_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "layer_id=2" in violations[0].message


def test_layer_id_violation_populates_location() -> None:
    """The Location on a collision violation carries the colliding ID."""
    course = _course_with(
        _layer(layer_id=42),
        _layer(layer_id=42),
    )
    violations = _layer_id_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.location is not None
    assert v.location.layer_id == 42


def test_layer_id_strict_raises() -> None:
    """validate_strict raises when layer-ID collisions exist."""
    course = _course_with(
        _layer(layer_id=1),
        _layer(layer_id=1),
    )
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    collisions = [
        v for v in info.value.violations
        if v.rule is Rule.LAYER_ID_COLLISION
    ]
    assert len(collisions) == 1


# --- ROTATION_OUT_OF_RANGE -------------------------------------------------
#
# Valid rotation values are 0..5 (6 orientations on a hex grid). Checks
# two loci: TileTowerConstructionData.hex_rotation on every placed tile,
# and RailConstructionExitIdentifier.side_hex_rot on both endpoints of
# every rail. Expected to never fire on real courses; primary value is
# guarding the M5 generator.

def _rotation_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just ROTATION_OUT_OF_RANGE violations."""
    return [v for v in violations if v.rule is Rule.ROTATION_OUT_OF_RANGE]


def _cell_with_rot(kind: TileKind, *, rot: int, y: int = 0, x: int = 0) -> CellConstructionData:
    """Build a cell with a single tile whose hex_rotation is explicitly set."""
    return CellConstructionData(
        local_hex_position=HexVector(y=y, x=x),
        tree_node_data=TileTowerTreeNodeData(
            index=0,
            construction_data=TileTowerConstructionData(
                kind=kind, height_in_small_stacker=0, hex_rotation=rot,
            ),
            children=(),
        ),
    )


def _rail_with_rot(
    *, rot_1: int, rot_2: int,
    p1: HexVector = HexVector(y=0, x=0),
    p2: HexVector = HexVector(y=0, x=1),
    retainer_1: int = 0, retainer_2: int = 0,
) -> RailConstructionData:
    """Build a STRAIGHT rail with explicit side_hex_rot values on each endpoint."""
    return RailConstructionData(
        exit_1_identifier=RailConstructionExitIdentifier(
            retainer_id=retainer_1, cell_local_hex_pos=p1,
            side_hex_rot=rot_1, exit_local_pos_y=0.0,
        ),
        exit_2_identifier=RailConstructionExitIdentifier(
            retainer_id=retainer_2, cell_local_hex_pos=p2,
            side_hex_rot=rot_2, exit_local_pos_y=0.0,
        ),
        rail_kind=RailKind.STRAIGHT,
    )


# --- Tile rotation boundary checks ---------------------------------------

def test_rotation_tile_valid_boundaries_pass() -> None:
    """Rotations 0 and 5 are the inclusive boundaries — both valid."""
    course = _course_with(_layer(
        _cell_with_rot(TileKind.CURVE, rot=0, y=0, x=0),
        _cell_with_rot(TileKind.CURVE, rot=5, y=1, x=0),
    ))
    assert _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_rotation_tile_all_valid_values_pass() -> None:
    """Every value in [0, 5] is valid — no violations across all six."""
    cells = [_cell_with_rot(TileKind.CURVE, rot=r, y=r, x=0) for r in range(6)]
    course = _course_with(_layer(*cells))
    assert _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_rotation_tile_six_is_out_of_range() -> None:
    """6 is just past the valid upper bound — one violation."""
    course = _course_with(_layer(_cell_with_rot(TileKind.CURVE, rot=6, y=0, x=0)))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.ROTATION_OUT_OF_RANGE
    assert v.severity is Severity.ERROR
    assert "hex_rotation" in v.message
    assert "value=6" in v.message
    assert "CURVE" in v.message
    assert "[0, 5]" in v.message


def test_rotation_tile_negative_is_out_of_range() -> None:
    """-1 is below the valid lower bound — one violation."""
    course = _course_with(_layer(_cell_with_rot(TileKind.CURVE, rot=-1, y=0, x=0)))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "value=-1" in violations[0].message


def test_rotation_tile_violation_populates_location() -> None:
    """Tile rotation violations carry hex_position in Location."""
    course = _course_with(_layer(_cell_with_rot(TileKind.CURVE, rot=7, y=3, x=-1)))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.location is not None
    assert v.location.hex_position == HexVector(y=3, x=-1)


def test_rotation_tile_stacked_children_checked() -> None:
    """Bad rotations on stacked child tiles also fire."""
    # Root rotation is valid, child rotation is bad.
    stack = TileTowerTreeNodeData(
        index=0,
        construction_data=TileTowerConstructionData(
            kind=TileKind.CURVE, height_in_small_stacker=0, hex_rotation=0,
        ),
        children=(
            TileTowerTreeNodeData(
                index=1,
                construction_data=TileTowerConstructionData(
                    kind=TileKind.CURVE, height_in_small_stacker=0, hex_rotation=99,
                ),
                children=(),
            ),
        ),
    )
    cell = CellConstructionData(
        local_hex_position=HexVector(y=0, x=0),
        tree_node_data=stack,
    )
    course = _course_with(_layer(cell))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "value=99" in violations[0].message


def test_rotation_tile_balcony_cells_checked() -> None:
    """Bad rotations on tiles in wall-balcony cells also fire."""
    balcony_cell = _cell_with_rot(TileKind.CURVE, rot=10, y=5, x=5)
    wall = WallConstructionData(
        lower_stacker_tower_1_retainer_id=0,
        lower_stacker_tower_1_local_hex_pos=HexVector(y=0, x=0),
        lower_stacker_tower_2_retainer_id=1,
        lower_stacker_tower_2_local_hex_pos=HexVector(y=1, x=0),
        balcony_construction_datas=(
            WallBalconyConstructionData(
                retainer_id=42,
                wall_side=WallSide.WEST,
                wall_coordinate=WallCoordinate(column=0, row=0),
                cell_construction_data=balcony_cell,
            ),
        ),
    )
    course = _course_with(_layer(), walls=(wall,))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    assert "value=10" in violations[0].message


# --- Rail rotation boundary checks ---------------------------------------

def test_rotation_rail_both_endpoints_valid_pass() -> None:
    """Both endpoints at valid rotations — no violation."""
    rail = _rail_with_rot(rot_1=0, rot_2=5)
    course = _course_with(_layer(), rails=(rail,))
    assert _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_rotation_rail_exit_1_out_of_range() -> None:
    """Exit 1 bad, exit 2 valid — one violation for exit 1."""
    rail = _rail_with_rot(rot_1=9, rot_2=2)
    course = _course_with(_layer(), rails=(rail,))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert "side_hex_rot" in v.message
    assert "value=9" in v.message
    assert "exit 1" in v.message
    assert "[0, 5]" in v.message


def test_rotation_rail_exit_2_out_of_range() -> None:
    """Exit 1 valid, exit 2 bad — one violation for exit 2."""
    rail = _rail_with_rot(rot_1=1, rot_2=6)
    course = _course_with(_layer(), rails=(rail,))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert "value=6" in v.message
    assert "exit 2" in v.message


def test_rotation_rail_both_endpoints_bad_fires_twice() -> None:
    """Both ends bad on the same rail — two independent violations."""
    rail = _rail_with_rot(rot_1=7, rot_2=8)
    course = _course_with(_layer(), rails=(rail,))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    # Exit 1 violation comes first in the course-order walk.
    assert "exit 1" in violations[0].message
    assert "value=7" in violations[0].message
    assert "exit 2" in violations[1].message
    assert "value=8" in violations[1].message


def test_rotation_rail_violation_populates_location() -> None:
    """Rail rotation violations carry rail_index, retainer_id, and hex_position."""
    rail = _rail_with_rot(
        rot_1=42, rot_2=0,
        p1=HexVector(y=7, x=3),
        retainer_1=123,
    )
    course = _course_with(_layer(), rails=(rail,))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    loc = violations[0].location
    assert loc is not None
    assert loc.rail_index == 0
    assert loc.retainer_id == 123
    assert loc.hex_position == HexVector(y=7, x=3)


# --- Combined + strict-mode checks ---------------------------------------

def test_rotation_tile_and_rail_violations_both_reported() -> None:
    """A course with both bad tile rotation and bad rail rotation reports both."""
    bad_tile = _cell_with_rot(TileKind.CURVE, rot=99, y=0, x=0)
    bad_rail = _rail_with_rot(rot_1=7, rot_2=0)
    course = _course_with(_layer(bad_tile), rails=(bad_rail,))
    violations = _rotation_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    messages = [v.message for v in violations]
    assert any("hex_rotation" in m for m in messages)
    assert any("side_hex_rot" in m for m in messages)


def test_rotation_strict_raises() -> None:
    """validate_strict raises when rotation violations exist."""
    course = _course_with(_layer(_cell_with_rot(TileKind.CURVE, rot=7, y=0, x=0)))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    rot_violations = [
        v for v in info.value.violations
        if v.rule is Rule.ROTATION_OUT_OF_RANGE
    ]
    assert len(rot_violations) == 1


# --- CELL_COLLISION --------------------------------------------------------
#
# No two cells on the same layer share a local_hex_position. Expected to
# never fire on real courses; primary value is guarding the M5 generator.
# Scope is layer cells only; balcony cells use a different coordinate
# space and can't collide with layer cells.

def _cell_collision_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just CELL_COLLISION violations."""
    return [v for v in violations if v.rule is Rule.CELL_COLLISION]


def test_cell_collision_empty_course_passes() -> None:
    """No cells, nothing to collide."""
    assert _cell_collision_violations(validate(_empty_course(), PRO_VERTICAL_STARTER_SET)) == []


def test_cell_collision_distinct_positions_pass() -> None:
    """Cells at different positions on the same layer — no violation."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=0, x=0),
        _cell(TileKind.GOAL_BASIN, y=0, x=1),
        _cell(TileKind.CURVE, y=1, x=0),
    ))
    assert _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_cell_collision_same_position_different_layers_pass() -> None:
    """Same hex position on different layers is fine — they're on different
    physical surfaces."""
    course = _course_with(
        _layer(_cell(TileKind.STARTER, y=0, x=0), layer_id=1),
        _layer(_cell(TileKind.GOAL_BASIN, y=0, x=0), layer_id=2),
    )
    assert _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_cell_collision_duplicate_position_fires_one_violation() -> None:
    """Two cells at the same (layer_id, position) → exactly one violation."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=2, x=3),
        _cell(TileKind.CURVE, y=2, x=3),  # same layer, same position
        layer_id=10,
    ))
    violations = _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.CELL_COLLISION
    assert v.severity is Severity.ERROR
    assert "layer_id=10" in v.message
    assert "(2,3)" in v.message
    assert "2 cells" in v.message
    assert "STARTER" in v.message
    assert "CURVE" in v.message


def test_cell_collision_triple_duplicate_dedup_to_one_violation() -> None:
    """Three cells at the same position → one violation, not two or three."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=0, x=0),
        _cell(TileKind.CURVE, y=0, x=0),
        _cell(TileKind.GOAL_BASIN, y=0, x=0),
        layer_id=5,
    ))
    violations = _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    v = violations[0]
    assert "3 cells" in v.message


def test_cell_collision_independent_collisions_each_reported() -> None:
    """Multiple independent collisions → one violation per colliding position,
    sorted by (layer_id, y, x)."""
    course = _course_with(
        _layer(
            _cell(TileKind.STARTER, y=1, x=0),
            _cell(TileKind.CURVE, y=1, x=0),  # collision at layer 1
            layer_id=1,
        ),
        _layer(
            _cell(TileKind.GOAL_BASIN, y=0, x=0),
            _cell(TileKind.CURVE, y=0, x=0),  # collision at layer 2
            layer_id=2,
        ),
    )
    violations = _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 2
    # Sort is (layer_id, y, x). Layer 1 violation comes first.
    assert "layer_id=1" in violations[0].message
    assert "layer_id=2" in violations[1].message


def test_cell_collision_sort_order_within_layer() -> None:
    """Within a layer, violations sort by (y, x) — smaller first."""
    course = _course_with(_layer(
        _cell(TileKind.CURVE, y=5, x=5),
        _cell(TileKind.STARTER, y=5, x=5),  # collision at (5, 5)
        _cell(TileKind.CURVE, y=1, x=0),
        _cell(TileKind.GOAL_BASIN, y=1, x=0),  # collision at (1, 0)
        _cell(TileKind.CURVE, y=1, x=2),
        _cell(TileKind.CURVE, y=1, x=2),  # collision at (1, 2)
        layer_id=0,
    ))
    violations = _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 3
    # (1,0) comes before (1,2) comes before (5,5).
    assert "(1,0)" in violations[0].message
    assert "(1,2)" in violations[1].message
    assert "(5,5)" in violations[2].message


def test_cell_collision_balcony_cells_not_in_scope() -> None:
    """Balcony-mounted cells use a different coordinate space and don't
    collide with layer cells, even at matching positions."""
    # Layer cell at (0, 0) and a balcony cell at (0, 0) — not a collision.
    balcony_cell = CellConstructionData(
        local_hex_position=HexVector(y=0, x=0),
        tree_node_data=_node(TileKind.CURVE),
    )
    wall = WallConstructionData(
        lower_stacker_tower_1_retainer_id=0,
        lower_stacker_tower_1_local_hex_pos=HexVector(y=0, x=0),
        lower_stacker_tower_2_retainer_id=1,
        lower_stacker_tower_2_local_hex_pos=HexVector(y=1, x=0),
        balcony_construction_datas=(
            WallBalconyConstructionData(
                retainer_id=42,
                wall_side=WallSide.WEST,
                wall_coordinate=WallCoordinate(column=0, row=0),
                cell_construction_data=balcony_cell,
            ),
        ),
    )
    course = _course_with(
        _layer(_cell(TileKind.STARTER, y=0, x=0), layer_id=1),
        walls=(wall,),
    )
    assert _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET)) == []


def test_cell_collision_violation_populates_location() -> None:
    """CELL_COLLISION violations carry layer_id and hex_position in Location."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=4, x=-2),
        _cell(TileKind.CURVE, y=4, x=-2),
        layer_id=77,
    ))
    violations = _cell_collision_violations(validate(course, PRO_VERTICAL_STARTER_SET))
    assert len(violations) == 1
    loc = violations[0].location
    assert loc is not None
    assert loc.layer_id == 77
    assert loc.hex_position == HexVector(y=4, x=-2)


def test_cell_collision_strict_raises() -> None:
    """validate_strict raises when cell collisions exist."""
    course = _course_with(_layer(
        _cell(TileKind.STARTER, y=0, x=0),
        _cell(TileKind.CURVE, y=0, x=0),
    ))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    cell_violations = [
        v for v in info.value.violations
        if v.rule is Rule.CELL_COLLISION
    ]
    assert len(cell_violations) == 1


# --- RETAINER_ID_COLLISION -------------------------------------------------
#
# Retainer IDs live in one global namespace across three declarer sources:
# LayerConstructionData.layer_id, TileTowerConstructionData.retainer_id
# (when non-null), and WallBalconyConstructionData.retainer_id. No two
# declarers may share an ID. Overlaps with LAYER_ID_COLLISION for the
# layer-layer case — both fire, messages are complementary.

def _retainer_collision_violations(violations: list[Violation]) -> list[Violation]:
    """Filter to just RETAINER_ID_COLLISION violations."""
    return [v for v in violations if v.rule is Rule.RETAINER_ID_COLLISION]


def _cell_with_retainer(
    kind: TileKind, *, retainer_id: int, y: int = 0, x: int = 0,
) -> CellConstructionData:
    """Build a cell whose root tile declares an explicit retainer_id."""
    return CellConstructionData(
        local_hex_position=HexVector(y=y, x=x),
        tree_node_data=TileTowerTreeNodeData(
            index=0,
            construction_data=TileTowerConstructionData(
                kind=kind, height_in_small_stacker=0, hex_rotation=0,
                retainer_id=retainer_id,
            ),
            children=(),
        ),
    )


def _wall_with_balconies(
    *, balcony_retainer_ids: tuple[int, ...],
) -> WallConstructionData:
    """Build a wall with balconies at the given retainer IDs (no mounted cells)."""
    return WallConstructionData(
        lower_stacker_tower_1_retainer_id=0,
        lower_stacker_tower_1_local_hex_pos=HexVector(y=0, x=0),
        lower_stacker_tower_2_retainer_id=1,
        lower_stacker_tower_2_local_hex_pos=HexVector(y=1, x=0),
        balcony_construction_datas=tuple(
            WallBalconyConstructionData(
                retainer_id=rid,
                wall_side=WallSide.WEST,
                wall_coordinate=WallCoordinate(column=i, row=0),
                cell_construction_data=None,
            )
            for i, rid in enumerate(balcony_retainer_ids)
        ),
    )


def test_retainer_collision_empty_course_passes() -> None:
    """No declarers at all, no collisions possible."""
    assert _retainer_collision_violations(
        validate(_empty_course(), PRO_VERTICAL_STARTER_SET)
    ) == []


def test_retainer_collision_unique_across_all_sources_passes() -> None:
    """Layer, tile, and balcony IDs all distinct — no violation."""
    course = _course_with(
        _layer(
            _cell_with_retainer(TileKind.STACKER_TOWER_CLOSED, retainer_id=1001, y=0, x=0),
            layer_id=100,
        ),
        walls=(_wall_with_balconies(balcony_retainer_ids=(2001,)),),
    )
    assert _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    ) == []


def test_retainer_collision_layer_vs_tile() -> None:
    """A layer and a tile sharing an ID → one violation naming both sources."""
    course = _course_with(_layer(
        _cell_with_retainer(TileKind.STACKER_TOWER_CLOSED, retainer_id=42, y=0, x=0),
        layer_id=42,  # same as the tile's retainer_id
    ))
    violations = _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.rule is Rule.RETAINER_ID_COLLISION
    assert v.severity is Severity.ERROR
    assert "id=42" in v.message
    assert "layer" in v.message
    assert "tile" in v.message


def test_retainer_collision_layer_vs_balcony() -> None:
    """A layer and a balcony sharing an ID → one violation."""
    course = _course_with(
        _layer(layer_id=7),
        walls=(_wall_with_balconies(balcony_retainer_ids=(7,)),),
    )
    violations = _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    )
    assert len(violations) == 1
    v = violations[0]
    assert "id=7" in v.message
    assert "layer" in v.message
    assert "balcony" in v.message


def test_retainer_collision_tile_vs_balcony() -> None:
    """A tile and a balcony sharing an ID → one violation."""
    course = _course_with(
        _layer(
            _cell_with_retainer(TileKind.DOUBLE_BALCONY, retainer_id=555, y=0, x=0),
        ),
        walls=(_wall_with_balconies(balcony_retainer_ids=(555,)),),
    )
    violations = _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    )
    assert len(violations) == 1
    v = violations[0]
    assert "id=555" in v.message
    assert "tile" in v.message
    assert "balcony" in v.message


def test_retainer_collision_two_layers_also_fires_here() -> None:
    """LAYER_ID_COLLISION and RETAINER_ID_COLLISION both fire for layer-layer case.

    Not a bug — the rules are independent and emit complementary info:
    LAYER_ID lists the LayerKinds, this rule lists the declarer types.
    """
    course = _course_with(
        _layer(layer_id=99, kind=LayerKind.BASE_LAYER),
        _layer(layer_id=99, kind=LayerKind.SMALL_LAYER),
    )
    all_violations = validate(course, PRO_VERTICAL_STARTER_SET)
    layer_violations = [v for v in all_violations if v.rule is Rule.LAYER_ID_COLLISION]
    retainer_violations = _retainer_collision_violations(all_violations)
    assert len(layer_violations) == 1
    assert len(retainer_violations) == 1
    # Messages are complementary.
    assert "BASE_LAYER" in layer_violations[0].message  # kinds
    assert "layer, layer" in retainer_violations[0].message  # sources


def test_retainer_collision_triple_dedup_to_one_violation() -> None:
    """Three declarers sharing an ID → one violation, count=3 in message."""
    course = _course_with(
        _layer(
            _cell_with_retainer(TileKind.STACKER_TOWER_CLOSED, retainer_id=30, y=0, x=0),
            layer_id=30,
        ),
        walls=(_wall_with_balconies(balcony_retainer_ids=(30,)),),
    )
    violations = _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    )
    assert len(violations) == 1
    assert "3 times" in violations[0].message


def test_retainer_collision_independent_collisions_sorted_ascending() -> None:
    """Multiple independent collisions → one violation each, sorted by ID ascending."""
    course = _course_with(
        _layer(
            _cell_with_retainer(TileKind.STACKER_TOWER_CLOSED, retainer_id=100, y=0, x=0),
            layer_id=100,  # collision at id=100
        ),
        _layer(
            _cell_with_retainer(TileKind.DOUBLE_BALCONY, retainer_id=5, y=0, x=0),
            layer_id=5,  # collision at id=5
        ),
    )
    violations = _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    )
    assert len(violations) == 2
    # Ascending: 5 first, then 100.
    assert "id=5" in violations[0].message
    assert "id=100" in violations[1].message


def test_retainer_collision_tile_with_null_retainer_not_counted() -> None:
    """Tiles with retainer_id=None don't declare anything and don't collide.

    Most TileKinds leave retainer_id as None (its default). Only structural
    kinds like STACKER_TOWER_* and DOUBLE_BALCONY typically declare IDs.
    """
    # A curve with retainer_id=None; layer_id=42. No collision even though
    # the _cell builder defaults tile.retainer_id to None.
    course = _course_with(_layer(
        _cell(TileKind.CURVE, y=0, x=0),
        layer_id=42,
    ))
    assert _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    ) == []


def test_retainer_collision_violation_populates_location() -> None:
    """Violations carry the colliding retainer_id in Location."""
    course = _course_with(_layer(
        _cell_with_retainer(TileKind.STACKER_TOWER_CLOSED, retainer_id=333, y=0, x=0),
        layer_id=333,
    ))
    violations = _retainer_collision_violations(
        validate(course, PRO_VERTICAL_STARTER_SET)
    )
    assert len(violations) == 1
    loc = violations[0].location
    assert loc is not None
    assert loc.retainer_id == 333


def test_retainer_collision_strict_raises() -> None:
    """validate_strict raises when retainer collisions exist."""
    course = _course_with(_layer(
        _cell_with_retainer(TileKind.STACKER_TOWER_CLOSED, retainer_id=8, y=0, x=0),
        layer_id=8,
    ))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    collisions = [
        v for v in info.value.violations
        if v.rule is Rule.RETAINER_ID_COLLISION
    ]
    assert len(collisions) == 1


# --- Real-fixture integration test ----------------------------------------
#
# Validates the GDZJZA3J3T fixture against an "unlimited" inventory — one
# big enough that no budget rule can possibly fire. Any violation we see
# here indicates a bug in our rules' assumptions about the binary format
# (wrong field path, wrong TileKind handling, bad walk, etc.), not a
# legitimate inventory overrun.
#
# This is our canary for assumption drift as we add more rules. If this
# starts failing after a rule change, we investigate before shipping.

def _unlimited_inventory() -> "Inventory":  # type: ignore[name-defined]
    """Build an inventory with huge budgets for every TileKind, rail, and structural piece."""
    from types import MappingProxyType

    from traxgen.inventory import (
        Inventory,
        RailLength,
        StructuralInventory,
    )
    from traxgen.types import RailKind

    big = 10_000
    return Inventory(
        name="unlimited (integration test)",
        tiles=MappingProxyType({kind: big for kind in TileKind}),
        rails=MappingProxyType({kind: big for kind in RailKind}),
        straight_rail_limits=MappingProxyType({length: big for length in RailLength}),
        baseplates=big,
        transparent_levels=big,
        marbles=big,
        basic_tile_frames=big,
        structural=StructuralInventory(
            pillars=MappingProxyType({kind: big for kind in PillarKind}),
            walls=MappingProxyType({kind: big for kind in WallKind}),
            single_balconies=big,
            double_balconies=big,
        ),
    )


def test_validate_gdzjza3j3t_against_unlimited_inventory_is_clean() -> None:
    """The real kitchen-sink fixture must produce zero violations against an unlimited inventory.

    This catches bugs in our rules' binary-format assumptions (field paths,
    TileKind handling, walk correctness). Any violation here means a rule
    is misreading real data. Details are printed in the assertion message
    so failures are debuggable without re-running.
    """
    from pathlib import Path

    from traxgen.parser import parse_course

    fixture_path = Path(__file__).parent / "fixtures" / "GDZJZA3J3T.course"
    course = parse_course(fixture_path.read_bytes())

    violations = validate(course, _unlimited_inventory())

    assert violations == [], (
        f"Expected zero violations on GDZJZA3J3T with unlimited inventory, "
        f"got {len(violations)}:\n"
        + "\n".join(f"  - [{v.rule.name}] {v.message}" for v in violations)
    )
