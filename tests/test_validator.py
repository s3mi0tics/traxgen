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
) -> Course:
    """Build a course with the given layers and optional walls."""
    return Course(
        header=SaveDataHeader(guid=0, version=CourseSaveDataVersion.POWER_2022),
        meta_data=CourseMetaData(
            creation_timestamp=0, title="", order_number=-1,
            course_kind=CourseKind.CUSTOM, objective_kind=ObjectiveKind.NONE,
            difficulty=0, completed=False,
        ),
        layer_construction_data=layers,
        rail_construction_data=(),
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

def test_validate_returns_empty_for_empty_course() -> None:
    """An empty course has no placed pieces — no budget rule can fire."""
    assert validate(_empty_course(), CORE_STARTER_SET) == []


def test_validate_strict_does_not_raise_for_empty_course() -> None:
    validate_strict(_empty_course(), CORE_STARTER_SET)


# --- INVENTORY_BUDGET_TILES -----------------------------------------------

def test_budget_tiles_under_limit_passes() -> None:
    """Exactly-at-budget placement (1 starter, 28 curves) produces no violations."""
    cells = [_cell(TileKind.STARTER, y=0, x=0)]
    cells += [_cell(TileKind.CURVE, y=i, x=0) for i in range(1, 29)]
    course = _course_with(_layer(*cells))
    assert validate(course, PRO_VERTICAL_STARTER_SET) == []


def test_budget_tiles_single_overrun_fires_once() -> None:
    """29 curves against a 28-curve budget fires one violation, no more."""
    cells = [_cell(TileKind.CURVE, y=i, x=0) for i in range(29)]
    course = _course_with(_layer(*cells))
    violations = validate(course, PRO_VERTICAL_STARTER_SET)
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
    violations = validate(course, PRO_VERTICAL_STARTER_SET)
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
    violations = validate(course, PRO_VERTICAL_STARTER_SET)
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
    violations = validate(course, PRO_VERTICAL_STARTER_SET)
    assert len(violations) == 1
    assert "CURVE" in violations[0].message
    assert "29" in violations[0].message


# --- Baseplate sub-check --------------------------------------------------

def test_budget_tiles_baseplate_overrun() -> None:
    """5 BASE_LAYER layers vs budget of 4 fires one violation."""
    layers = tuple(_layer(layer_id=i, kind=LayerKind.BASE_LAYER) for i in range(5))
    course = _course_with(*layers)
    violations = validate(course, PRO_VERTICAL_STARTER_SET)  # 4 baseplates
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
    assert validate(course, PRO_VERTICAL_STARTER_SET) == []


# --- Switch pool ----------------------------------------------------------

def test_budget_tiles_switch_pool_at_limit_passes() -> None:
    """2 SWITCH_LEFT + 0 SWITCH_RIGHT = exactly at pool size, no violations."""
    course = _course_with(_layer(
        _cell(TileKind.SWITCH_LEFT, y=0, x=0),
        _cell(TileKind.SWITCH_LEFT, y=1, x=0),
    ))
    assert validate(course, PRO_VERTICAL_STARTER_SET) == []


def test_budget_tiles_switch_pool_exceeded() -> None:
    """2 SWITCH_LEFT + 1 SWITCH_RIGHT against pool of 2 fires one pool violation."""
    course = _course_with(_layer(
        _cell(TileKind.SWITCH_LEFT, y=0, x=0),
        _cell(TileKind.SWITCH_LEFT, y=1, x=0),
        _cell(TileKind.SWITCH_RIGHT, y=2, x=0),
    ))
    violations = validate(course, PRO_VERTICAL_STARTER_SET)
    # Exactly one violation — pool check, not per-kind (per-kind is skipped for switches).
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
    violations = validate(course, PRO_VERTICAL_STARTER_SET)
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
    violations = validate(course, PRO_VERTICAL_STARTER_SET)
    assert len(violations) == 2
    assert "STARTER" in violations[0].message
    assert "CURVE" in violations[1].message


def test_budget_tiles_strict_raises() -> None:
    """validate_strict raises ValidationError when budget violations exist."""
    course = _course_with(_layer(*[_cell(TileKind.CURVE, y=i) for i in range(29)]))
    with pytest.raises(ValidationError) as info:
        validate_strict(course, PRO_VERTICAL_STARTER_SET)
    assert len(info.value.violations) == 1
    assert info.value.violations[0].rule is Rule.INVENTORY_BUDGET_TILES


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
