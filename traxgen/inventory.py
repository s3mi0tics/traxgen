"""
Inventory: what pieces exist, what they do, what you have.

Three responsibilities:

1. Define PieceSpec — the static properties of each tile type (connections,
   energy profile, which GraviTrax set it belongs to).
2. Define EnergyProfile — per-piece physics metadata. Most values are
   placeholders in v1; Phase 2 calibrates them.
3. Define the Core Starter-Set (22410) as a concrete Inventory object.

Sources consulted:
  - https://gravitrax.fandom.com/wiki/Starter_Set
  - https://gravitrax.fandom.com/wiki/Three_way_merge
  - https://gravitrax.fandom.com/wiki/Basic_tile
  - https://gravitrax.fandom.com/wiki/Gravitrax
  - Staples listing (22410 contents)

Path: traxgen/traxgen/inventory.py
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from traxgen.types import TileKind

# --- Energy profile --------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EnergyProfile:
    """
    Per-piece physics metadata.

    Values are placeholders in Phase 1. Phase 2 populates them with textbook
    defaults (μ_r ≈ 0.005 for steel-on-plastic). We don't calibrate to real
    measurements — ±1s tolerance is generous enough.

    Variance is a first-class feature: pieces like the vortex and trampoline
    are intentionally stochastic. Tiers:
      - Low     (<50ms):   straight rails, curves, drops, magnetic cannon
      - Medium  (50-300):  splash, catch, switches, junctions
      - High    (300-1000): vortex, turntable, cascade, mixer
      - Very hi (1000+):   trampoline, volcano, spring-loaded pieces
    """
    path_length_mm: float = 0.0
    """Physical distance the marble travels through this piece."""

    height_change_mm: float = 0.0
    """Δh across the piece — positive = climbs, negative = drops."""

    energy_input_j: float = 0.0
    """Active energy added by the piece (cannon, catapult, lift). 0 for passive pieces."""

    loss_coefficient: float = 0.005
    """Piece-specific friction multiplier. Default ≈ steel-on-plastic rolling resistance."""

    expected_time_ms: float = 0.0
    """Mean traversal time at nominal entry speed."""

    time_variance_ms: float = 0.0
    """Stddev of traversal time. Non-zero for intentionally stochastic pieces."""


# A placeholder profile for v1 when we don't care about physics yet.
NO_PHYSICS = EnergyProfile()


# --- Piece specification ---------------------------------------------------

@dataclass(frozen=True, slots=True)
class PieceSpec:
    """
    Static properties of a tile type — what it is, what it connects to, how it behaves.

    The `exits` field is *not* populated yet. Exit directions depend on the
    piece's rotation, and we haven't yet nailed down how rotations map to
    hex directions (this is unknown #1 in the plan — verified in M2 against
    real courses). Once we have that, each PieceSpec will declare its exit
    edges at rotation 0, and we derive rotated exits from that.
    """
    kind: TileKind
    display_name: str
    """Human-readable name — used in logs, CLI output, error messages."""

    height_in_small_stackers: int = 0
    """
    Vertical height the piece itself occupies, measured in small-stacker units.
    Stackers are 0 (they ARE the height unit). Most tiles are 0 too — they
    sit ON a stack and don't add to it. Taller pieces (e.g., Volcano) are > 0.
    """

    energy_profile: EnergyProfile = field(default_factory=lambda: NO_PHYSICS)

    is_starter: bool = False
    """True for pieces that can launch a ball (Starter, DomeStarter, Cannon)."""

    is_goal: bool = False
    """True for pieces that end a track (GoalBasin, GoalRail, FinishArena)."""


# --- Piece catalog (subset — Starter-Set pieces only for v1) ---------------

# Only pieces that appear in the Core Starter-Set (22410).
# Extensions / PRO / POWER pieces will be added in later phases.
#
# Sourced from the GraviTrax Fandom wiki (see module docstring) plus the
# Staples listing for 22410. Four ambiguous-in-v1 pieces resolved:
#   - "3-in-1 tile": distinct from junctions; most likely maps to a binary
#     TileKind NOT in the Starter-Set catalog below — see TODO at the bottom.
#   - "2 switches": assumed 1 LEFT + 1 RIGHT. Ravensburger marketing doesn't
#     distinguish, but the schema has separate TileKinds; 1+1 is the natural
#     assumption. TODO(M2): verify from a parsed real course.
#   - "finish line" vs "landing": confirmed distinct.
#       Landing = GOAL_BASIN (insert into a solid basic tile).
#       Finish Line = GOAL_RAIL (standalone, connects via rails).
#   - Large vs small stacker height: confirmed 2:1 ratio ("full" vs "half")
#     from consistent marketing language across sets.
_STARTER_SET_PIECES: tuple[PieceSpec, ...] = (
    PieceSpec(
        kind=TileKind.STARTER,
        display_name="Launch Pad",
        is_starter=True,
    ),
    PieceSpec(
        kind=TileKind.CURVE,
        display_name="Curve",
    ),
    PieceSpec(
        kind=TileKind.CATCH,
        display_name="Catcher (insert)",
    ),
    PieceSpec(
        kind=TileKind.GOAL_BASIN,
        display_name="Landing (insert into solid basic tile)",
        is_goal=True,
    ),
    PieceSpec(
        kind=TileKind.DROP,
        display_name="Freefall (insert into hollow basic tile)",
    ),
    PieceSpec(
        kind=TileKind.SPLASH,
        display_name="Splash (insert)",
    ),
    PieceSpec(
        kind=TileKind.THREEWAY,
        display_name="Junction",
        # Three-way junction tile. Distinct from the "3-in-1" merge — see
        # the note at the bottom of the inventory list.
    ),
    PieceSpec(
        kind=TileKind.SPIRAL,
        display_name="Vortex",
        energy_profile=EnergyProfile(
            loss_coefficient=0.015,  # higher than straight rail
            time_variance_ms=800.0,  # intentionally stochastic
        ),
    ),
    PieceSpec(
        kind=TileKind.CANNON,
        display_name="Magnetic Cannon",
        is_starter=True,   # can also be used as a track starter
        energy_profile=EnergyProfile(
            energy_input_j=0.020,  # placeholder — Phase 2 calibrates
        ),
    ),
    PieceSpec(
        kind=TileKind.STACKER,
        display_name="Large Height Tile (full)",
        # Confirmed 2× small — marketed as "full" vs "half" height tiles.
        height_in_small_stackers=2,
    ),
    PieceSpec(
        kind=TileKind.STACKER_SMALL,
        display_name="Small Height Tile (half)",
        height_in_small_stackers=1,
    ),
    PieceSpec(
        kind=TileKind.SWITCH_LEFT,
        display_name="Switch (Left)",
    ),
    PieceSpec(
        kind=TileKind.SWITCH_RIGHT,
        display_name="Switch (Right)",
    ),
    PieceSpec(
        kind=TileKind.GOAL_RAIL,
        display_name="Finish Line (connects via rails)",
        is_goal=True,
    ),
)


# Look up a PieceSpec by TileKind. Returns None for kinds not in the catalog.
PIECE_CATALOG: Mapping[TileKind, PieceSpec] = {p.kind: p for p in _STARTER_SET_PIECES}


def get_piece_spec(kind: TileKind) -> PieceSpec:
    """Return the PieceSpec for a TileKind. Raises if not in the catalog."""
    spec = PIECE_CATALOG.get(kind)
    if spec is None:
        raise KeyError(
            f"No PieceSpec registered for {kind!r}. "
            f"Only Starter-Set pieces are cataloged in v1."
        )
    return spec


# --- Inventory -------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RailInventory:
    """
    Rails are counted by length, not by TileKind. The Starter-Set ships with
    three lengths (short, medium, long), all STRAIGHT rail kind.
    """
    short: int = 0
    medium: int = 0
    long: int = 0

    @property
    def total(self) -> int:
        return self.short + self.medium + self.long


@dataclass(frozen=True, slots=True)
class Inventory:
    """
    What the generator has to work with: piece counts, rail counts, baseplates.

    Immutable. The generator consumes pieces by producing a new Inventory with
    decremented counts (functional style — easy to backtrack).
    """
    name: str
    """Human-readable name, e.g., 'Core Starter-Set (22410)'."""

    tiles: Mapping[TileKind, int]
    """How many of each tile type."""

    rails: RailInventory

    baseplates: int
    """Number of cardboard baseplates."""

    transparent_levels: int
    """Number of transparent stacking levels."""

    marbles: int

    def tile_count(self, kind: TileKind) -> int:
        """How many of the given tile do we have? 0 if not in inventory."""
        return self.tiles.get(kind, 0)

    def has_tile(self, kind: TileKind) -> bool:
        return self.tile_count(kind) > 0

    def total_tiles(self) -> int:
        return sum(self.tiles.values())


# --- The Core Starter-Set (22410) ------------------------------------------

# Contents from the 22410 box:
#   - 1 launch pad → STARTER
#   - 21 curves → CURVE
#   - 3 junctions → THREEWAY
#   - 2 switches → assumed 1 SWITCH_LEFT + 1 SWITCH_RIGHT
#   - 1 "3-in-1 tile" → NOT CATALOGED (see TODO below)
#   - 1 vortex → SPIRAL
#   - 1 magnetic cannon → CANNON
#   - 1 finish line → GOAL_RAIL
#   - 4 "basic tiles" (frames for inserts — we model them as their insert kind):
#       - 2 catchers → CATCH
#       - 1 freefall → DROP
#       - 1 splash → SPLASH
#       - 1 landing → GOAL_BASIN
#   - 40 full + 12 half height tiles → STACKER (40) + STACKER_SMALL (12)
#
# TODO(M2): The "3-in-1 tile" is the Three-Way Merge — distinct from the
# THREEWAY junction tile. Its binary TileKind isn't yet confirmed. The schema
# has MULTI_JUNCTION (60) and other candidates, but none obviously matches.
# Most likely the Starter-Set predates whatever TileKind it now uses, or it's
# stored in a way we haven't yet seen. We'll identify it in M2 by parsing a
# real course that uses the piece. Until then, the generator works without it.
CORE_STARTER_SET: Inventory = Inventory(
    name="Core Starter-Set (22410)",
    tiles={
        TileKind.STARTER: 1,
        TileKind.CURVE: 21,
        TileKind.THREEWAY: 3,
        TileKind.SWITCH_LEFT: 1,
        TileKind.SWITCH_RIGHT: 1,
        TileKind.SPIRAL: 1,
        TileKind.CANNON: 1,
        TileKind.GOAL_RAIL: 1,
        TileKind.STACKER: 40,
        TileKind.STACKER_SMALL: 12,
        TileKind.CATCH: 2,
        TileKind.DROP: 1,
        TileKind.SPLASH: 1,
        TileKind.GOAL_BASIN: 1,
        # The "3-in-1 tile" (Three-Way Merge) is excluded until M2 confirms
        # its TileKind. It's 1 piece out of 122, so omission is low-impact.
    },
    rails=RailInventory(short=9, medium=6, long=3),
    baseplates=4,
    transparent_levels=2,
    marbles=6,
)
