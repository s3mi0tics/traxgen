"""Soft validation for parsed GraviTrax courses.

Given a domain Course and an Inventory, returns a list of Violations. Each rule
is a private _check_* function registered in _CHECKS; validate() runs them all
and flattens. No cross-rule dependencies in v1 — if profiling complains later,
we can introduce a shared precomputed context.

Path: traxgen/traxgen/validator.py
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from enum import Enum, IntEnum, auto

from traxgen.domain import (
    CellConstructionData,
    Course,
    TileTowerConstructionData,
    TileTowerTreeNodeData,
)
from traxgen.hex import HexVector
from traxgen.inventory import Inventory
from traxgen.types import LayerKind, TileKind


class Severity(IntEnum):
    """How bad a violation is. Higher = worse."""
    WARNING = 1
    ERROR = 2


class Rule(Enum):
    """v1 validation rules. All listed here; implementations land in follow-up steps."""
    INVENTORY_BUDGET_TILES = auto()
    INVENTORY_BUDGET_RAILS = auto()
    BASEPLATE_COVERAGE = auto()
    CELL_COLLISION = auto()
    RAIL_ENDPOINT_MISSING = auto()
    RETAINER_ID_COLLISION = auto()
    LAYER_ID_COLLISION = auto()
    PILLAR_ENDPOINT_MISSING = auto()
    ROTATION_OUT_OF_RANGE = auto()
    MISSING_STARTER_OR_GOAL = auto()
    TILE_INDEX_COLLISION = auto()


@dataclass(frozen=True, slots=True)
class Location:
    """Best-effort locator for a violation. All fields optional — rules fill what they know."""
    layer_id: int | None = None
    hex_position: HexVector | None = None
    retainer_id: int | None = None
    rail_index: int | None = None
    pillar_index: int | None = None


@dataclass(frozen=True, slots=True)
class Violation:
    """One rule failure: severity, rule identity, human message, best-effort location."""
    severity: Severity
    rule: Rule
    message: str
    location: Location | None = None


class ValidationError(Exception):
    """Raised by validate_strict when any ERROR-severity violations are present."""

    def __init__(self, violations: list[Violation]) -> None:
        self.violations = violations
        super().__init__(
            f"{len(violations)} error(s); first: {violations[0].message}"
        )


# --- Shared walk helpers ---------------------------------------------------

def _iter_cells(course: Course) -> Iterator[CellConstructionData]:
    """Yield every CellConstructionData in the course — layer cells + wall-balcony cells."""
    for layer in course.layer_construction_data:
        yield from layer.cell_construction_datas
    for wall in course.wall_construction_data:
        for balcony in wall.balcony_construction_datas:
            if balcony.cell_construction_data is not None:
                yield balcony.cell_construction_data


def _iter_tree_nodes(node: TileTowerTreeNodeData) -> Iterator[TileTowerTreeNodeData]:
    """Pre-order walk of a tile tower tree — yields the root then every descendant."""
    yield node
    for child in node.children:
        yield from _iter_tree_nodes(child)


def _iter_placed_tiles(course: Course) -> Iterator[TileTowerConstructionData]:
    """Every placed TileTowerConstructionData anywhere on the course. Used by budget rules."""
    for cell in _iter_cells(course):
        for node in _iter_tree_nodes(cell.tree_node_data):
            yield node.construction_data


# --- Rules -----------------------------------------------------------------

# Switches are a pool: the two physical pieces can each be configured LEFT or
# RIGHT, so inventory stores limits for both TileKinds but the total placed
# must fit in the pool. Pool size = max of the two limits (symmetric today at
# 2+2 for both starter sets; taking max keeps us robust if future inventories
# are asymmetric). The pool check strictly subsumes the per-kind checks when
# limits are equal, so we skip per-kind for switches to avoid duplicate noise.
_SWITCH_KINDS: frozenset[TileKind] = frozenset({TileKind.SWITCH_LEFT, TileKind.SWITCH_RIGHT})


def _check_inventory_budget_tiles(
    course: Course, inventory: Inventory
) -> Iterable[Violation]:
    """INVENTORY_BUDGET_TILES: placed tiles per TileKind must fit inventory, including baseplates and the switch pool."""
    violations: list[Violation] = []
    placed: Counter[TileKind] = Counter(
        tile.kind for tile in _iter_placed_tiles(course)
    )

    # Baseplate sub-check — count BASE_LAYER layers (not BASE_LAYER_PIECE).
    baseplate_count = sum(
        1
        for layer in course.layer_construction_data
        if layer.layer_kind is LayerKind.BASE_LAYER
    )
    if baseplate_count > inventory.baseplates:
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.INVENTORY_BUDGET_TILES,
            message=(
                f"Baseplate budget exceeded: placed {baseplate_count}, "
                f"allowed {inventory.baseplates}"
            ),
        ))

    # Switch pool sub-check.
    switch_placed = placed[TileKind.SWITCH_LEFT] + placed[TileKind.SWITCH_RIGHT]
    switch_pool = max(
        inventory.tile_count(TileKind.SWITCH_LEFT),
        inventory.tile_count(TileKind.SWITCH_RIGHT),
    )
    if switch_placed > switch_pool:
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.INVENTORY_BUDGET_TILES,
            message=(
                f"Switch pool exceeded: placed {switch_placed} "
                f"(SWITCH_LEFT={placed[TileKind.SWITCH_LEFT]} + "
                f"SWITCH_RIGHT={placed[TileKind.SWITCH_RIGHT]}), "
                f"pool size {switch_pool}"
            ),
        ))

    # Per-kind budget for everything else. Sort by TileKind.value for deterministic output.
    for kind in sorted(placed, key=lambda k: k.value):
        if kind in _SWITCH_KINDS:
            continue
        count = placed[kind]
        limit = inventory.tile_count(kind)
        if count > limit:
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.INVENTORY_BUDGET_TILES,
                message=(
                    f"Tile budget exceeded for {kind.name}: "
                    f"placed {count}, allowed {limit}"
                ),
            ))

    return violations


# --- Rule registry --------------------------------------------------------

# Each entry takes (course, inventory) and yields Violations. Rules register
# here as they're implemented.
_CheckFn = Callable[[Course, Inventory], Iterable[Violation]]
_CHECKS: tuple[_CheckFn, ...] = (
    _check_inventory_budget_tiles,
)


# --- Entry points ---------------------------------------------------------

def validate(course: Course, inventory: Inventory) -> list[Violation]:
    """Run every registered rule and return all violations found (empty list = valid)."""
    return [v for check in _CHECKS for v in check(course, inventory)]


def validate_strict(course: Course, inventory: Inventory) -> None:
    """Run validate(); raise ValidationError if any ERROR-severity violations are present."""
    errors = [v for v in validate(course, inventory) if v.severity is Severity.ERROR]
    if errors:
        raise ValidationError(errors)
