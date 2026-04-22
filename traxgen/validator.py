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
from traxgen.inventory import (
    PIECE_CATALOG,
    Inventory,
    PillarKind,
    RailLength,
    WallKind,
)
from traxgen.types import LayerKind, RailKind, TileKind


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
    WALL_ENDPOINT_MISSING = auto()


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

# STRAIGHT rails are fixed-length pieces: a SHORT spans exactly 1 hex, MEDIUM
# spans exactly 2, LONG spans exactly 3. No cascading coverage. A distance
# outside {1, 2, 3} means no available piece can satisfy that placement.
# See docs/refs/rail-specs.md.
_STRAIGHT_DISTANCE_TO_LENGTH: dict[int, RailLength] = {
    1: RailLength.SHORT,
    2: RailLength.MEDIUM,
    3: RailLength.LONG,
}

# Starter and goal kinds derived from PieceSpec flags in PIECE_CATALOG.
# Single source of truth: adding a new piece with is_starter=True (e.g.,
# DOME_STARTER when the POWER line is cataloged) automatically makes it
# satisfy MISSING_STARTER_OR_GOAL without touching this module. Tiles whose
# TileKind isn't in the catalog simply don't match either set — no KeyError.
_STARTER_KINDS: frozenset[TileKind] = frozenset(
    kind for kind, spec in PIECE_CATALOG.items() if spec.is_starter
)
_GOAL_KINDS: frozenset[TileKind] = frozenset(
    kind for kind, spec in PIECE_CATALOG.items() if spec.is_goal
)


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


def _check_inventory_budget_rails(
    course: Course, inventory: Inventory
) -> Iterable[Violation]:
    """INVENTORY_BUDGET_RAILS: rail kinds and STRAIGHT-rail lengths must fit inventory.

    Two kinds of check:

    1. Per-kind count: for every RailKind in the course, count and compare
       against inventory.rails[kind]. All rails count here regardless of
       where their endpoints live.
    2. STRAIGHT-length sub-budget: STRAIGHT rails are fixed-length pieces
       (SHORT spans 1 hex, MEDIUM 2, LONG 3). Each placed STRAIGHT has its
       length inferred from the hex distance between its two cell endpoints.
       An unexpected distance (0 or >3) means no physical piece can satisfy
       that placement — we emit a per-placement violation. Otherwise we
       bucket and compare each bucket against inventory.straight_rail_limits.

    Cross-retainer STRAIGHT rails (endpoints on different layers or stacker
    towers) are SKIPPED from the sub-budget entirely. Rail endpoints use
    cell_local_hex_pos — position within the endpoint's retainer — so for
    cross-retainer rails, local distance doesn't reflect physical span.
    Proper validation requires world coordinates, which in turn requires
    knowing how baseplates tile in world space (PLAN.md open question).
    Until that's resolved, cross-retainer rails count toward the per-kind
    budget but aren't bucketed or span-checked. The GDZJZA3J3T fixture has
    real cross-retainer rails with local distance 0 and 5, confirming this
    skip is necessary to avoid false positives on real courses.
    """
    violations: list[Violation] = []

    # --- Per-kind rail count ---------------------------------------------
    placed_by_kind: Counter[RailKind] = Counter(
        rail.rail_kind for rail in course.rail_construction_data
    )
    for kind in sorted(placed_by_kind, key=lambda k: k.value):
        count = placed_by_kind[kind]
        limit = inventory.rail_count(kind)
        if count > limit:
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.INVENTORY_BUDGET_RAILS,
                message=(
                    f"Rail budget exceeded for {kind.name}: "
                    f"placed {count}, allowed {limit}"
                ),
            ))

    # --- STRAIGHT sub-budget: per-placement invalid span + bucket checks -
    length_counts: Counter[RailLength] = Counter()
    for rail_index, rail in enumerate(course.rail_construction_data):
        if rail.rail_kind is not RailKind.STRAIGHT:
            continue
        exit_1 = rail.exit_1_identifier
        exit_2 = rail.exit_2_identifier
        # Skip cross-retainer rails — local distance isn't physical distance.
        # See docstring.
        if exit_1.retainer_id != exit_2.retainer_id:
            continue
        distance = exit_1.cell_local_hex_pos.distance_to(exit_2.cell_local_hex_pos)
        length = _STRAIGHT_DISTANCE_TO_LENGTH.get(distance)
        if length is None:
            # No physical STRAIGHT piece can span this distance.
            p1 = exit_1.cell_local_hex_pos
            p2 = exit_2.cell_local_hex_pos
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.INVENTORY_BUDGET_RAILS,
                message=(
                    f"STRAIGHT rail with invalid span: distance {distance} "
                    f"between ({p1.y},{p1.x}) and ({p2.y},{p2.x}) — "
                    f"no rail piece available for this span"
                ),
                location=Location(
                    rail_index=rail_index,
                    retainer_id=exit_1.retainer_id,
                    hex_position=p1,
                ),
            ))
            continue
        length_counts[length] += 1

    # Bucket overruns — emitted in SHORT/MEDIUM/LONG order (enum.value order).
    for length in RailLength:
        placed = length_counts[length]
        limit = inventory.straight_rail_limits.get(length, 0)
        if placed > limit:
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.INVENTORY_BUDGET_RAILS,
                message=(
                    f"STRAIGHT {length.name} rail budget exceeded: "
                    f"placed {placed}, allowed {limit}"
                ),
            ))

    return violations


def _check_missing_starter_or_goal(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """MISSING_STARTER_OR_GOAL: course must contain at least one starter and one goal tile.

    Fundamental requirement for single-track mode: the ball has to start
    somewhere (a STARTER piece) and finish somewhere (a GOAL_BASIN or
    GOAL_RAIL). Without either, the course is unplayable by construction.

    Two independent checks, each emits its own violation if the count is
    zero. Starter and goal kinds are derived from PieceSpec.is_starter /
    is_goal flags in PIECE_CATALOG — see the module-level _STARTER_KINDS
    and _GOAL_KINDS.

    Inventory is unused by this rule; it's a property of the course, not
    of what pieces are available. Signature matches the _CheckFn protocol
    for registration in _CHECKS.

    Race mode (Phase 3) will want N starters and N goals, and perpetual
    mode has no goal at all — those modes will likely bypass or parameterise
    this rule via the future GenerationMode mechanism. For v1 single-track,
    "at least one of each" is the bar.
    """
    violations: list[Violation] = []

    has_starter = any(
        tile.kind in _STARTER_KINDS for tile in _iter_placed_tiles(course)
    )
    has_goal = any(
        tile.kind in _GOAL_KINDS for tile in _iter_placed_tiles(course)
    )

    if not has_starter:
        allowed = ", ".join(sorted(k.name for k in _STARTER_KINDS))
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.MISSING_STARTER_OR_GOAL,
            message=f"No starter tile placed: course needs at least one of {{{allowed}}}",
        ))

    if not has_goal:
        allowed = ", ".join(sorted(k.name for k in _GOAL_KINDS))
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.MISSING_STARTER_OR_GOAL,
            message=f"No goal tile placed: course needs at least one of {{{allowed}}}",
        ))

    return violations


def _check_layer_id_collision(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """LAYER_ID_COLLISION: every layer_id in course.layer_construction_data must be unique.

    Layer IDs are labels used by other parts of the course file to
    reference specific layers — pillar endpoints, for instance, point to
    layers by ID. Two layers sharing an ID would make any such reference
    ambiguous, so the labels must be unique course-wide.

    Emits one violation per duplicated ID (not one per duplicate pair),
    with the involved `LayerKind`s listed in the message for debuggability.
    Violations are sorted by layer_id ascending for deterministic output.

    Inventory is unused — this is a pure schema-validity check.

    Expected to never fire on real app-produced fixtures (the app
    generates valid IDs); the rule's primary value is protecting our own
    generator from emitting broken files in M5.
    """
    violations: list[Violation] = []

    # Build layer_id -> list of layer_kinds for every layer.
    by_id: dict[int, list[LayerKind]] = {}
    for layer in course.layer_construction_data:
        by_id.setdefault(layer.layer_id, []).append(layer.layer_kind)

    for layer_id in sorted(by_id):
        kinds = by_id[layer_id]
        if len(kinds) <= 1:
            continue
        kinds_str = ", ".join(k.name for k in kinds)
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.LAYER_ID_COLLISION,
            message=(
                f"Layer ID collision: layer_id={layer_id} appears "
                f"{len(kinds)} times (kinds: {kinds_str})"
            ),
            location=Location(layer_id=layer_id),
        ))

    return violations


def _check_rotation_out_of_range(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """ROTATION_OUT_OF_RANGE: hex_rotation and side_hex_rot must be in [0, 5].

    Hexagonal coordinates have 6 orientations (one per 60° rotation);
    valid rotation values are 0 through 5 inclusive. Two loci to check:

    1. `TileTowerConstructionData.hex_rotation` — the rotation of every
       placed tile (including stacked children and balcony-mounted tiles).
    2. `RailConstructionExitIdentifier.side_hex_rot` — the hex edge each
       rail endpoint attaches to, on both ends of each rail.

    Emits one violation per out-of-range value. Rail endpoints fire
    independently (a rail with both ends bad produces two violations).

    Inventory is unused — this is a pure schema-validity check. Expected
    to never fire on real app-produced courses; the rule's primary value
    is protecting our own M5 generator from emitting bad rotations.
    """
    violations: list[Violation] = []
    valid = range(6)

    # --- Tile rotations -------------------------------------------------
    # Walk order matches _iter_placed_tiles: layer cells (pre-order tree),
    # then balcony-mounted cells. We don't carry layer_id in the location
    # — _iter_placed_tiles is a flat iterator, and hex_position is enough
    # to pinpoint placements on any given layer for v1 debugging.
    for cell in _iter_cells(course):
        for node in _iter_tree_nodes(cell.tree_node_data):
            rot = node.construction_data.hex_rotation
            if rot in valid:
                continue
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.ROTATION_OUT_OF_RANGE,
                message=(
                    f"hex_rotation out of range: value={rot} at position "
                    f"({cell.local_hex_position.y},{cell.local_hex_position.x}) "
                    f"on tile {node.construction_data.kind.name} "
                    f"— valid range [0, 5]"
                ),
                location=Location(hex_position=cell.local_hex_position),
            ))

    # --- Rail endpoint rotations ----------------------------------------
    for rail_index, rail in enumerate(course.rail_construction_data):
        for exit_num, exit_id in (
            (1, rail.exit_1_identifier),
            (2, rail.exit_2_identifier),
        ):
            rot = exit_id.side_hex_rot
            if rot in valid:
                continue
            pos = exit_id.cell_local_hex_pos
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.ROTATION_OUT_OF_RANGE,
                message=(
                    f"side_hex_rot out of range: value={rot} at rail "
                    f"#{rail_index} exit {exit_num} "
                    f"(retainer {exit_id.retainer_id}, pos ({pos.y},{pos.x})) "
                    f"— valid range [0, 5]"
                ),
                location=Location(
                    rail_index=rail_index,
                    retainer_id=exit_id.retainer_id,
                    hex_position=pos,
                ),
            ))

    return violations


def _check_cell_collision(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """CELL_COLLISION: no two cells on the same layer share a local_hex_position.

    Each (layer_id, local_hex_position) pair identifies a physical hex on
    a physical layer. Two cells occupying the same pair would mean two
    physical pieces occupying the same physical hex — impossible.

    Scope: layer cells only. Balcony-mounted cells have their own
    coordinate space (local to the balcony, not the layer), so they
    can't collide with layer cells. A future rule could check balcony
    cell collisions separately if that becomes relevant.

    Emits one violation per colliding (layer_id, position) pair with
    the root TileKinds listed for debuggability. Violations sorted by
    (layer_id, position.y, position.x) for determinism.

    Inventory is unused — this is a pure schema-validity check.
    Expected to never fire on real app-produced courses.
    """
    violations: list[Violation] = []

    # Build (layer_id, position) -> list of root TileKinds.
    # Using root-kind rather than walking the tree: a collision is about
    # the cell itself occupying a hex, and each cell has exactly one root.
    by_pos: dict[tuple[int, HexVector], list[TileKind]] = {}
    for layer in course.layer_construction_data:
        for cell in layer.cell_construction_datas:
            key = (layer.layer_id, cell.local_hex_position)
            by_pos.setdefault(key, []).append(
                cell.tree_node_data.construction_data.kind
            )

    # Sort by (layer_id, y, x) for deterministic output.
    def _sort_key(item: tuple[int, HexVector]) -> tuple[int, int, int]:
        layer_id, pos = item
        return (layer_id, pos.y, pos.x)

    for key in sorted(by_pos, key=_sort_key):
        kinds = by_pos[key]
        if len(kinds) <= 1:
            continue
        layer_id, pos = key
        kinds_str = ", ".join(k.name for k in kinds)
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.CELL_COLLISION,
            message=(
                f"Cell collision: layer_id={layer_id}, position "
                f"({pos.y},{pos.x}) has {len(kinds)} cells "
                f"(root kinds: {kinds_str})"
            ),
            location=Location(layer_id=layer_id, hex_position=pos),
        ))

    return violations


def _collect_retainer_declarers(course: Course) -> list[tuple[int, str]]:
    """Yield (retainer_id, source_type) for every declarer in the course.

    Declarer sources:
      1. LayerConstructionData.layer_id -> source 'layer'
      2. TileTowerConstructionData.retainer_id (when non-null) -> 'tile'
      3. WallBalconyConstructionData.retainer_id -> 'balcony'

    Order is layers -> tiles (in cell walk order) -> balconies, preserving
    stability across calls. Shared by RETAINER_ID_COLLISION,
    RAIL_ENDPOINT_MISSING, and PILLAR_ENDPOINT_MISSING — whenever a rule
    needs the set or list of valid retainer targets, it goes through here.
    """
    declarers: list[tuple[int, str]] = []
    for layer in course.layer_construction_data:
        declarers.append((layer.layer_id, "layer"))
    for cell in _iter_cells(course):
        for node in _iter_tree_nodes(cell.tree_node_data):
            rid = node.construction_data.retainer_id
            if rid is not None:
                declarers.append((rid, "tile"))
    for wall in course.wall_construction_data:
        for balcony in wall.balcony_construction_datas:
            declarers.append((balcony.retainer_id, "balcony"))
    return declarers


def _check_retainer_id_collision(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """RETAINER_ID_COLLISION: retainer IDs must be unique across all declarer sources.

    Retainer IDs live in a single global namespace spanning three declarer
    sources:

      1. LayerConstructionData.layer_id — layers are retainers
      2. TileTowerConstructionData.retainer_id (when non-null) — structural
         tiles (STACKER_TOWER_*, DOUBLE_BALCONY) declare retainers
      3. WallBalconyConstructionData.retainer_id — balcony mounts declare
         retainers

    Other parts of the binary (rail endpoints, pillar endpoints, wall
    stacker-tower references) point to retainers by ID; if two declarers
    share an ID, those references become ambiguous.

    This rule overlaps with LAYER_ID_COLLISION for the layer-layer case.
    Both fire together for a two-layer collision — that's intentional,
    keeps the rules independent and the messages complementary
    (LAYER_ID_COLLISION lists the LayerKinds; this lists the declarer
    types).

    Emits one violation per colliding ID, sorted ascending. Inventory is
    unused. Expected to never fire on real app-produced courses;
    GDZJZA3J3T probe confirmed zero collisions across 48 declarers.
    """
    violations: list[Violation] = []

    # Build id -> list of sources (preserving order for determinism).
    by_id: dict[int, list[str]] = {}
    for rid, source in _collect_retainer_declarers(course):
        by_id.setdefault(rid, []).append(source)

    for rid in sorted(by_id):
        sources = by_id[rid]
        if len(sources) <= 1:
            continue
        sources_str = ", ".join(sources)
        violations.append(Violation(
            severity=Severity.ERROR,
            rule=Rule.RETAINER_ID_COLLISION,
            message=(
                f"Retainer ID collision: id={rid} declared {len(sources)} times "
                f"(sources: {sources_str})"
            ),
            location=Location(retainer_id=rid),
        ))

    return violations


def _check_rail_endpoint_missing(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """RAIL_ENDPOINT_MISSING: every rail endpoint must reference a declared retainer.

    Each rail has two endpoints (exit_1 and exit_2), each of which
    references a retainer by ID. That retainer must be declared somewhere
    (as a layer, a structural tile, or a balcony). A reference to an
    undeclared ID means the rail points into the void — no target to
    actually attach to.

    Emits one violation per bad endpoint. A rail with both endpoints
    pointing to missing retainers fires twice (matches the ROTATION rule's
    per-endpoint granularity). Violations preserve course order.

    Inventory is unused. Expected to never fire on real app-produced
    courses; GDZJZA3J3T probe confirmed 40/40 rail endpoints resolve.
    """
    violations: list[Violation] = []

    declared: set[int] = {rid for rid, _ in _collect_retainer_declarers(course)}

    for rail_index, rail in enumerate(course.rail_construction_data):
        for exit_num, exit_id in (
            (1, rail.exit_1_identifier),
            (2, rail.exit_2_identifier),
        ):
            rid = exit_id.retainer_id
            if rid in declared:
                continue
            pos = exit_id.cell_local_hex_pos
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.RAIL_ENDPOINT_MISSING,
                message=(
                    f"Rail endpoint references missing retainer: rail "
                    f"#{rail_index} exit {exit_num} points to "
                    f"retainer_id={rid} (not declared by any layer, "
                    f"structural tile, or balcony)"
                ),
                location=Location(
                    rail_index=rail_index,
                    retainer_id=rid,
                    hex_position=pos,
                ),
            ))

    return violations


def _check_pillar_endpoint_missing(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """PILLAR_ENDPOINT_MISSING: pillar endpoints must reference declared retainers.

    Each pillar has two layer/retainer endpoints (lower and upper). The
    field names are 'lower_layer_id' / 'upper_layer_id' for historical
    reasons, but they reference any declared retainer — not only literal
    layers. A pillar can connect a baseplate layer (low-numbered id) to
    a pillar-on-pillar structural tile (high-numbered retainer id).

    Emits one violation per bad endpoint. A pillar with both ends pointing
    to missing retainers fires twice.

    Inventory is unused. Expected to never fire on real app-produced
    courses; GDZJZA3J3T probe confirmed 30/30 pillar endpoints resolve.
    """
    violations: list[Violation] = []

    declared: set[int] = {rid for rid, _ in _collect_retainer_declarers(course)}

    for pillar_index, pillar in enumerate(course.pillar_construction_data):
        for side, rid, pos in (
            ("lower", pillar.lower_layer_id, pillar.lower_cell_local_position),
            ("upper", pillar.upper_layer_id, pillar.upper_cell_local_position),
        ):
            if rid in declared:
                continue
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.PILLAR_ENDPOINT_MISSING,
                message=(
                    f"Pillar endpoint references missing layer/retainer: "
                    f"pillar #{pillar_index} {side} points to layer_id={rid} "
                    f"(not declared by any layer, structural tile, or balcony)"
                ),
                location=Location(
                    pillar_index=pillar_index,
                    retainer_id=rid,
                    hex_position=pos,
                ),
            ))

    return violations


def _check_wall_endpoint_missing(
    course: Course, inventory: Inventory  # noqa: ARG001
) -> Iterable[Violation]:
    """WALL_ENDPOINT_MISSING: wall stacker-tower references must resolve.

    Each PRO wall spans between two stacker towers, referenced by
    lower_stacker_tower_1_retainer_id and lower_stacker_tower_2_retainer_id.
    Those retainer IDs must be declared somewhere (typically by structural
    tile retainers on pillar pieces, but any declared retainer is valid).
    A reference to an undeclared ID means the wall dangles with no tower
    to anchor to.

    Discovered during probe work for the retainer family (commit fb2e547) —
    not in the original v1 plan. Added once the probe showed wall
    references are a third kind of retainer reference alongside rails and
    pillars.

    Emits one violation per bad endpoint. A wall with both towers missing
    fires twice (same granularity as the rail/pillar endpoint rules).

    Inventory is unused. Expected to never fire on real app-produced
    courses; GDZJZA3J3T probe confirmed 8/8 wall tower references resolve.
    """
    violations: list[Violation] = []

    declared: set[int] = {rid for rid, _ in _collect_retainer_declarers(course)}

    for wall_index, wall in enumerate(course.wall_construction_data):
        for tower_num, rid, pos in (
            (1, wall.lower_stacker_tower_1_retainer_id,
             wall.lower_stacker_tower_1_local_hex_pos),
            (2, wall.lower_stacker_tower_2_retainer_id,
             wall.lower_stacker_tower_2_local_hex_pos),
        ):
            if rid in declared:
                continue
            violations.append(Violation(
                severity=Severity.ERROR,
                rule=Rule.WALL_ENDPOINT_MISSING,
                message=(
                    f"Wall endpoint references missing retainer: wall "
                    f"#{wall_index} tower {tower_num} points to "
                    f"retainer_id={rid} (not declared by any layer, "
                    f"structural tile, or balcony)"
                ),
                location=Location(
                    retainer_id=rid,
                    hex_position=pos,
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
    _check_inventory_budget_rails,
    _check_missing_starter_or_goal,
    _check_layer_id_collision,
    _check_rotation_out_of_range,
    _check_cell_collision,
    _check_retainer_id_collision,
    _check_rail_endpoint_missing,
    _check_pillar_endpoint_missing,
    _check_wall_endpoint_missing,
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
