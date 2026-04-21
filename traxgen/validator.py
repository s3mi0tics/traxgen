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
from traxgen.inventory import Inventory, PillarKind, WallKind
from traxgen.types import LayerKind, TileKind


class Severity(IntEnum):
    """How bad a violation is. Higher = worse."""
    WARNING = 1
    ERROR = 2


class Rule(Enum):
    """v1 validation rules. All listed here; implementations land in follow-up steps."""
    INVENTORY_BUDGET_TILES = auto()
    INVENTORY_BUDGET_STACKERS = auto()
    INVENTORY_BUDGET_STRUCTURAL = auto()
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

# Structural pieces appear as tree nodes but are budgeted by
# INVENTORY_BUDGET_STRUCTURAL, not INVENTORY_BUDGET_TILES. Skipping them in
# the tiles rule prevents false-positive "not in inventory" overruns (they're
# absent from inventory.tiles by design).
_STRUCTURAL_TILE_KINDS: frozenset[TileKind] = frozenset({
    TileKind.STACKER_TOWER_CLOSED,
    TileKind.STACKER_TOWER_OPENED,
    TileKind.DOUBLE_BALCONY,
})

# Wall length is not stored on the wall itself — it's inferred from hex
# distance between the two tower endpoints. See docs/refs/pro-structural-notes.md.
_WALL_DISTANCE_TO_KIND: dict[int, WallKind] = {
    1: WallKind.SHORT,
    2: WallKind.MEDIUM,
    3: WallKind.LONG,
}


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
    # STACKER and STACKER_SMALL never appear here because stackers aren't tree
    # nodes — they live as the height_in_small_stacker field on whatever sits
    # on top. INVENTORY_BUDGET_STACKERS handles their budgeting separately.
    # See docs/refs/tree-node-height-semantics.md.
    #
    # Structural tile kinds (pillars, double balconies) are also skipped here —
    # they're budgeted by INVENTORY_BUDGET_STRUCTURAL against the separate
    # StructuralInventory, not against inventory.tiles.
    for kind in sorted(placed, key=lambda k: k.value):
        if kind in _SWITCH_KINDS or kind in _STRUCTURAL_TILE_KINDS:
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


def _check_inventory_budget_stackers(
    course: Course, inventory: Inventory
) -> Iterable[Violation]:
    """INVENTORY_BUDGET_STACKERS: total small-stacker units and parity feasibility against inventory.

    Each tree node's height_in_small_stacker field represents an independent
    stack of stackers — not a pool. A large stacker provides 2 units at one
    spot, indivisibly; a small provides 1. Feasibility has two constraints:

      1. Total units: sum(h) <= 2*large + small.
      2. Parity: each odd-h stack must consume exactly one small stacker
         (you can't build an odd number out of 2s alone), so the count of
         odd-h stacks must not exceed the small-stacker inventory.

    Either constraint can fail independently; we emit both violations if
    both fail. See docs/refs/tree-node-height-semantics.md.
    """
    violations: list[Violation] = []
    stacks = [
        tile.height_in_small_stacker
        for tile in _iter_placed_tiles(course)
        if tile.height_in_small_stacker > 0
    ]
    total_units = sum(stacks)
    odd_count = sum(1 for h in stacks if h % 2 == 1)
    large = inventory.tile_count(TileKind.STACKER)
    small = inventory.tile_count(TileKind.STACKER_SMALL)
    capacity = 2 * large + small

    if total_units > capacity:
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.INVENTORY_BUDGET_STACKERS,
            message=(
                f"Stacker budget exceeded: {total_units} small-stacker units required, "
                f"capacity {capacity} ({large} large * 2 + {small} small)"
            ),
        ))

    if odd_count > small:
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.INVENTORY_BUDGET_STACKERS,
            message=(
                f"Small stacker shortfall: {odd_count} odd-height stack(s) "
                f"require small stackers, but inventory has {small}"
            ),
        ))

    return violations


def _check_inventory_budget_structural(
    course: Course, inventory: Inventory
) -> Iterable[Violation]:
    """INVENTORY_BUDGET_STRUCTURAL: pillars, walls, and balconies must fit StructuralInventory.

    Pillars appear as tree nodes (TileKind.STACKER_TOWER_CLOSED / OPENED).
    Walls live in course.wall_construction_data; length is inferred from the
    hex distance between the two tower endpoints (1=SHORT, 2=MEDIUM, 3=LONG).
    Double balconies appear as tree nodes (TileKind.DOUBLE_BALCONY).
    Single balconies are mounted cells in WallBalconyConstructionData entries
    on walls — only entries with a non-null cell count as mounted.

    TODO: unverified whether the "mounted-only" counting rule is correct —
    might be that every entry in balcony_construction_datas represents a
    physical balcony piece, mounted or not. Verify when we have a fixture
    with explicit balcony placements.

    TODO: walls with hex distance outside {1,2,3} are silently skipped. A
    future schema-validity rule should flag those as invalid placements.
    """
    violations: list[Violation] = []

    # --- Pillars ---------------------------------------------------------
    # Count pillar tree nodes by TileKind, then compare to inventory.structural.pillars.
    placed_kinds = Counter(tile.kind for tile in _iter_placed_tiles(course))
    for pillar_kind in PillarKind:
        tile_kind = {
            PillarKind.CLOSED: TileKind.STACKER_TOWER_CLOSED,
            PillarKind.OPENED: TileKind.STACKER_TOWER_OPENED,
        }[pillar_kind]
        placed = placed_kinds[tile_kind]
        limit = inventory.structural.pillar_count(pillar_kind)
        if placed > limit:
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.INVENTORY_BUDGET_STRUCTURAL,
                message=(
                    f"Pillar budget exceeded for {pillar_kind.name}: "
                    f"placed {placed}, allowed {limit}"
                ),
            ))

    # --- Walls (length inferred from hex distance between endpoints) -----
    wall_kind_counts: Counter[WallKind] = Counter()
    for wall in course.wall_construction_data:
        distance = wall.lower_stacker_tower_1_local_hex_pos.distance_to(
            wall.lower_stacker_tower_2_local_hex_pos
        )
        wall_kind = _WALL_DISTANCE_TO_KIND.get(distance)
        if wall_kind is None:
            # See TODO above — future rule territory.
            continue
        wall_kind_counts[wall_kind] += 1

    for wall_kind in WallKind:
        placed = wall_kind_counts[wall_kind]
        limit = inventory.structural.wall_count(wall_kind)
        if placed > limit:
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.INVENTORY_BUDGET_STRUCTURAL,
                message=(
                    f"Wall budget exceeded for {wall_kind.name}: "
                    f"placed {placed}, allowed {limit}"
                ),
            ))

    # --- Single balconies (mounted cells on walls) ----------------------
    single_balconies_placed = sum(
        1
        for wall in course.wall_construction_data
        for balcony in wall.balcony_construction_datas
        if balcony.cell_construction_data is not None
    )
    if single_balconies_placed > inventory.structural.single_balconies:
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.INVENTORY_BUDGET_STRUCTURAL,
            message=(
                f"Single balcony budget exceeded: placed {single_balconies_placed}, "
                f"allowed {inventory.structural.single_balconies}"
            ),
        ))

    # --- Double balconies (DOUBLE_BALCONY tree nodes) -------------------
    double_balconies_placed = placed_kinds[TileKind.DOUBLE_BALCONY]
    if double_balconies_placed > inventory.structural.double_balconies:
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.INVENTORY_BUDGET_STRUCTURAL,
            message=(
                f"Double balcony budget exceeded: placed {double_balconies_placed}, "
                f"allowed {inventory.structural.double_balconies}"
            ),
        ))

    return violations


# --- Rule registry --------------------------------------------------------

# Each entry takes (course, inventory) and yields Violations. Rules register
# here as they're implemented.
_CheckFn = Callable[[Course, Inventory], Iterable[Violation]]
_CHECKS: tuple[_CheckFn, ...] = (
    _check_inventory_budget_tiles,
    _check_inventory_budget_stackers,
    _check_inventory_budget_structural,
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
