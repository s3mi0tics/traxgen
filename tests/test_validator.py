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
from traxgen.inventory import CORE_STARTER_SET, PRO_VERTICAL_STARTER_SET
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
