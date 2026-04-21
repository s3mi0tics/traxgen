"""
Inventory: what pieces exist, what they do, what you have.

Responsibilities:

1. Define PieceSpec — static properties of each tile type.
2. Define EnergyProfile — per-piece physics metadata. Mostly placeholders
   in v1; Phase 2 calibrates them.
3. Define structural inventory types (pillars, walls, balconies) for
   PRO-line pieces that don't cleanly map to TileKind.
4. Define Inventory — what the generator has to work with, including
   rails (flat map keyed by RailKind), tiles, stackers, structural, etc.
5. Define concrete inventories: CORE_STARTER_SET (22410) and
   PRO_VERTICAL_STARTER_SET (26832, populated in a follow-up step).

Sources:
  - docs/refs/ for reconciled piece counts, rail specs, pillar semantics
  - Fandom wiki for 22410 and 26832 contents
  - Physical piece inspection

Path: traxgen/traxgen/inventory.py
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from types import MappingProxyType

from traxgen.types import RailKind, TileKind

# --- Energy profile --------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EnergyProfile:
    """Per-piece physics metadata. Placeholder values in Phase 1."""
    path_length_mm: float = 0.0
    height_change_mm: float = 0.0
    energy_input_j: float = 0.0
    loss_coefficient: float = 0.005
    expected_time_ms: float = 0.0
    time_variance_ms: float = 0.0


NO_PHYSICS = EnergyProfile()


# --- Piece specification ---------------------------------------------------

@dataclass(frozen=True, slots=True)
class PieceSpec:
    """Static properties of a tile type."""
    kind: TileKind
    display_name: str
    height_in_small_stackers: int = 0
    energy_profile: EnergyProfile = field(default_factory=lambda: NO_PHYSICS)
    is_starter: bool = False
    is_goal: bool = False


# --- Piece catalog ---------------------------------------------------------

# Pieces cataloged for Core + PRO Vertical starter sets. Expand as needed.
# See docs/refs/pro-vertical-starter-set-26832.md for piece-identity notes.
_CATALOGED_PIECES: tuple[PieceSpec, ...] = (
    PieceSpec(kind=TileKind.STARTER, display_name="Launch Pad", is_starter=True),
    PieceSpec(kind=TileKind.CURVE, display_name="Curve"),
    PieceSpec(kind=TileKind.CATCH, display_name="Catcher (insert)"),
    PieceSpec(
        kind=TileKind.GOAL_BASIN,
        display_name="Landing (insert into solid basic tile)",
        is_goal=True,
    ),
    PieceSpec(kind=TileKind.DROP, display_name="Freefall (insert into hollow basic tile)"),
    PieceSpec(kind=TileKind.SPLASH, display_name="Splash (insert)"),
    PieceSpec(kind=TileKind.CROSS, display_name="X-intersection"),
    PieceSpec(kind=TileKind.THREEWAY, display_name="Threeway / Y-point (insert)"),
    PieceSpec(
        kind=TileKind.SPIRAL,
        display_name="Vortex",
        energy_profile=EnergyProfile(loss_coefficient=0.015, time_variance_ms=800.0),
    ),
    PieceSpec(
        kind=TileKind.CANNON,
        display_name="Magnetic Cannon",
        # Not a starter — the cannon is an energy injector. A ball must
        # arrive (via gravity from elsewhere) for the cannon to do anything;
        # it can't initiate a run on its own. Flagged and corrected during
        # M4 validator design for MISSING_STARTER_OR_GOAL. The cannon's role
        # is modeled via energy_profile.energy_input_j, not is_starter.
        energy_profile=EnergyProfile(energy_input_j=0.020),
    ),
    PieceSpec(
        kind=TileKind.STACKER,
        display_name="Large Height Tile (full)",
        height_in_small_stackers=2,
    ),
    PieceSpec(
        kind=TileKind.STACKER_SMALL,
        display_name="Small Height Tile (half)",
        height_in_small_stackers=1,
    ),
    PieceSpec(kind=TileKind.SWITCH_LEFT, display_name="Switch (Left-start)"),
    PieceSpec(kind=TileKind.SWITCH_RIGHT, display_name="Switch (Right-start)"),
    PieceSpec(
        kind=TileKind.GOAL_RAIL,
        display_name="Finish Line (connects via rails)",
        is_goal=True,
    ),
    # THREE_ENTRANCE_FUNNEL = the "3-in-1" / "3-way merge" tile. TileKind
    # assignment is best-guess from the schema name, consistent with the
    # piece behavior (3 entrances → 1 fixed exit). Confirmable by parsing
    # a real fixture using this piece. See
    # docs/refs/pro-vertical-starter-set-26832.md for details.
    PieceSpec(kind=TileKind.THREE_ENTRANCE_FUNNEL, display_name="3-way Merge / 3-in-1"),
)


PIECE_CATALOG: Mapping[TileKind, PieceSpec] = MappingProxyType(
    {p.kind: p for p in _CATALOGED_PIECES}
)


def get_piece_spec(kind: TileKind) -> PieceSpec:
    """Return the PieceSpec for a TileKind. Raises if not in the catalog."""
    spec = PIECE_CATALOG.get(kind)
    if spec is None:
        raise KeyError(
            f"No PieceSpec registered for {kind!r}. Catalog covers Core + PRO Vertical pieces."
        )
    return spec


# --- Structural inventory --------------------------------------------------

class PillarKind(IntEnum):
    """Pillar variants. Inventory accounting only — not a wire-format enum.

    Maps to TileKinds via PILLAR_KIND_TO_TILE_KIND:
      CLOSED  -> TileKind.STACKER_TOWER_CLOSED
      OPENED  -> TileKind.STACKER_TOWER_OPENED (has rail-passthrough cutout)
    """
    CLOSED = 0
    OPENED = 1


class WallKind(IntEnum):
    """Wall length. Walls have no TileKind — they live in course.wall_construction_data.

    Length inferred from hex distance between the wall's two tower endpoints.
    """
    SHORT = 0   # spans 1 hex, 2 balcony-mount columns
    MEDIUM = 1  # spans 2 hex, 3 balcony-mount columns
    LONG = 2    # spans 3 hex, 4 balcony-mount columns


PILLAR_KIND_TO_TILE_KIND: Mapping[PillarKind, TileKind] = MappingProxyType({
    PillarKind.CLOSED: TileKind.STACKER_TOWER_CLOSED,
    PillarKind.OPENED: TileKind.STACKER_TOWER_OPENED,
})


@dataclass(frozen=True, slots=True)
class StructuralInventory:
    """PRO-line structural pieces. Empty (all zero) for Core-only sets."""
    pillars: Mapping[PillarKind, int] = field(default_factory=dict)
    walls: Mapping[WallKind, int] = field(default_factory=dict)
    single_balconies: int = 0
    double_balconies: int = 0

    def pillar_count(self, kind: PillarKind) -> int:
        return self.pillars.get(kind, 0)

    def wall_count(self, kind: WallKind) -> int:
        return self.walls.get(kind, 0)

    @property
    def total_pillars(self) -> int:
        return sum(self.pillars.values())

    @property
    def total_walls(self) -> int:
        return sum(self.walls.values())


EMPTY_STRUCTURAL = StructuralInventory()


# --- Rail length specification (per-length capacity for STRAIGHT rails) ----

class RailLength(IntEnum):
    """Length bucket for STRAIGHT rails. Inferred from endpoint hex distance."""
    SHORT = 1
    MEDIUM = 2
    LONG = 3


@dataclass(frozen=True, slots=True)
class RailLengthSpec:
    """Per-length straight-rail capacity. See docs/refs/rail-specs.md."""
    max_hex_distance: int
    max_delta_small_stacker: int
    """Maximum absolute Δheight in small-stacker units the rail can span."""


# Starter-set straight-rail specs. Values reconciled from physical manual +
# physical testing; override community wiki numbers where they disagree.
STRAIGHT_RAIL_SPECS: Mapping[RailLength, RailLengthSpec] = MappingProxyType({
    RailLength.SHORT: RailLengthSpec(max_hex_distance=1, max_delta_small_stacker=5),
    RailLength.MEDIUM: RailLengthSpec(max_hex_distance=2, max_delta_small_stacker=7),
    RailLength.LONG: RailLengthSpec(max_hex_distance=3, max_delta_small_stacker=8),
})


# --- Inventory -------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Inventory:
    """What the generator has to work with.

    `rails` is a flat map keyed by RailKind. For STRAIGHT rails, the total
    is a pool — length is inferred at validation time from endpoint distance,
    and capacity per length is given by `straight_rail_limits`.

    `basic_tile_frames` is the physical count of hollow hex frames that
    accept inserts (CATCH, DROP, THREEWAY, GOAL_BASIN). Only this many
    inserts can be active simultaneously, regardless of how many inserts
    the inventory holds. Not validator-enforced in v1.
    """
    name: str
    tiles: Mapping[TileKind, int]
    rails: Mapping[RailKind, int]
    straight_rail_limits: Mapping[RailLength, int]
    """Capacity per STRAIGHT-rail length bucket (short/medium/long counts)."""
    baseplates: int
    transparent_levels: int
    marbles: int
    basic_tile_frames: int = 0
    structural: StructuralInventory = field(default_factory=StructuralInventory)

    def tile_count(self, kind: TileKind) -> int:
        return self.tiles.get(kind, 0)

    def has_tile(self, kind: TileKind) -> bool:
        return self.tile_count(kind) > 0

    def total_tiles(self) -> int:
        return sum(self.tiles.values())

    def rail_count(self, kind: RailKind) -> int:
        return self.rails.get(kind, 0)

    def total_rails(self) -> int:
        return sum(self.rails.values())


# --- The Core Starter-Set (22410) ------------------------------------------

# 3 basic tile frames accept 5 inserts: 2 CATCH + 1 DROP + 1 SPLASH + 1 GOAL_BASIN.
# Note: Core HAS a SPLASH — unlike 26832, which does not.
CORE_STARTER_SET: Inventory = Inventory(
    name="Core Starter-Set (22410)",
    tiles=MappingProxyType({
        TileKind.STARTER: 1,
        TileKind.CURVE: 21,
        TileKind.THREEWAY: 3,
        # Switches: 2 physical pieces, each configurable as LEFT-start or
        # RIGHT-start. Encoded as 2 of each TileKind (pool semantics).
        # Validator enforces pool constraint: total placed <= 2.
        # UNVERIFIED: the assumption that the app encodes starting state via
        # TileKind (vs. a separate field) needs empirical testing — export a
        # course with a known-state switch and check which TileKind lands in
        # the binary. See docs/refs/pro-vertical-starter-set-26832.md.
        TileKind.SWITCH_LEFT: 2,
        TileKind.SWITCH_RIGHT: 2,
        TileKind.SPIRAL: 1,
        TileKind.CANNON: 1,
        TileKind.GOAL_RAIL: 1,
        TileKind.STACKER: 40,
        TileKind.STACKER_SMALL: 12,
        TileKind.CATCH: 2,
        TileKind.DROP: 1,
        TileKind.SPLASH: 1,
        TileKind.GOAL_BASIN: 1,
        TileKind.THREE_ENTRANCE_FUNNEL: 1,
    }),
    rails=MappingProxyType({
        RailKind.STRAIGHT: 18,  # 9 short + 6 medium + 3 long = 18 straight rails
    }),
    straight_rail_limits=MappingProxyType({
        RailLength.SHORT: 9,
        RailLength.MEDIUM: 6,
        RailLength.LONG: 3,
    }),
    baseplates=4,
    transparent_levels=2,
    marbles=6,
    basic_tile_frames=4,  # 4 frames for 5 inserts (1 loose)
    structural=EMPTY_STRUCTURAL,
)


# --- The PRO Vertical Starter-Set (26832) ----------------------------------

# Reconciled contents list derived from Colby's physical piece inspection +
# the Fandom wiki page for 26832. See docs/refs/pro-vertical-starter-set-26832.md
# for source reconciliation notes, ambiguity resolutions, and the full
# breakdown.
#
# Key piece-identity decisions encoded here:
#  - SWITCHES: pool of 2 physical pieces, each configurable LEFT or RIGHT.
#    Encoded as 2 of each TileKind; validator enforces pool constraint
#    (total SWITCH_LEFT + SWITCH_RIGHT placed <= 2).
#  - THREE_ENTRANCE_FUNNEL: best-guess TileKind mapping for the "3-in-1" /
#    "3-way merge" piece. Physical behavior is 3 entrances -> 1 fixed exit.
#  - No SPLASH piece in this set (unlike Core Starter-Set).
#  - DOUBLE_BALCONY is tracked in structural, not tiles.
#
# Total piece count: 151 (Ravensburger advertises 153; 2-piece discrepancy
# unresolved, suspected to be rail connectors or similar small hardware).
PRO_VERTICAL_STARTER_SET: Inventory = Inventory(
    name="PRO Vertical Starter-Set (26832)",
    tiles=MappingProxyType({
        # Standalone track tiles
        TileKind.STARTER: 1,
        TileKind.CURVE: 28,
        TileKind.CROSS: 4,
        TileKind.SPIRAL: 1,
        TileKind.CANNON: 1,
        TileKind.GOAL_RAIL: 1,
        TileKind.THREE_ENTRANCE_FUNNEL: 1,  # the "3-in-1" / 3-way merge
        # Inserts (live as tree nodes; fit into basic tile frames)
        TileKind.CATCH: 2,
        TileKind.DROP: 1,
        TileKind.THREEWAY: 1,  # the Y-point / junction insert
        TileKind.GOAL_BASIN: 1,
        # Switches (pool of 2 physical pieces, each configurable L/R).
        # Validator enforces pool constraint: total placed <= 2.
        # See Core comment above re: empirical verification of TileKind
        # encoding for switch starting state.
        TileKind.SWITCH_LEFT: 2,
        TileKind.SWITCH_RIGHT: 2,
        # Stackers
        TileKind.STACKER: 20,
        TileKind.STACKER_SMALL: 9,
    }),
    rails=MappingProxyType({
        RailKind.STRAIGHT: 18,  # 9 short + 6 medium + 3 long pool
        RailKind.BERNOULLI_SMALL_LEFT: 3,
        RailKind.BERNOULLI_SMALL_RIGHT: 3,
        RailKind.BERNOULLI_SMALL_STRAIGHT: 2,
    }),
    straight_rail_limits=MappingProxyType({
        RailLength.SHORT: 9,
        RailLength.MEDIUM: 6,
        RailLength.LONG: 3,
    }),
    baseplates=4,
    transparent_levels=1,
    marbles=6,
    basic_tile_frames=3,
    structural=StructuralInventory(
        pillars=MappingProxyType({
            PillarKind.CLOSED: 8,
            PillarKind.OPENED: 4,
        }),
        walls=MappingProxyType({
            WallKind.SHORT: 1,
            WallKind.MEDIUM: 2,
            WallKind.LONG: 2,
        }),
        single_balconies=16,
        double_balconies=4,
    ),
)
