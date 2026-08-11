"""Connection semantics and the Phase-1 track graph (M5.c + the first slice of M5.a).

Encodes what the exhaustive starter-rotation sweeps actually measured
(2026-08-07/08 for s=0 and s=1; the 2026-08-10 queue run for s=2..5, all
harness-bracketed), split into the two constraints the 2026-08-08 session
separated:

  * `goal_rotation_for` -- the goal-side rule `g = (d + 1) % 6`, which takes
    NO starter term and has never once been violated on any active cell
    (decisions.md, "Goal rotation is a goal-side rule").
  * `MEASURED_LIVE_DIRECTIONS` -- which directions connect at all, a
    starter-side property. As of the 2026-08-10 queue run the table covers
    all six starter rotations exhaustively, and the measured pattern is
    parity: even rotations give {E, NW}, odd give {NE}. That is recorded as
    measurement, not mechanism -- WHY parity, and why the sizes are 2 and 1,
    is what remains of open unknown #15. The table still REFUSES rotations
    outside the measured range rather than interpolating (decisions.md, "The
    live direction set is a measured table, not a derived rule").

Connection here means the rail-free mechanism locked on 2026-06-12: a STARTER
adjacent to a GOAL_RAIL whose integrated rail faces it, `rail_count = 0`.
Distance-2 cells are measured dead at every swept rotation (the sweeps' far
controls), and a 0-rail connection has no physical mechanism beyond
adjacency, so non-adjacent pairs classify DISCONNECTED. Anything the table
has not measured classifies UNMEASURED -- the three-valued status is the
empirical discipline made explicit: we only claim what a render has shown.

Path: traxgen/traxgen/graph.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from types import MappingProxyType
from typing import TYPE_CHECKING

from traxgen.hex import HexVector
from traxgen.inventory import PIECE_CATALOG
from traxgen.types import TileKind

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from traxgen.domain import Course

# Tile kinds that can anchor each end of a connection, derived from the same
# catalog flags the validator uses (one source of truth for "what is a starter").
STARTER_KINDS: frozenset[TileKind] = frozenset(
    kind for kind, spec in PIECE_CATALOG.items() if spec.is_starter
)
GOAL_KINDS: frozenset[TileKind] = frozenset(
    kind for kind, spec in PIECE_CATALOG.items() if spec.is_goal
)

# The measured live-direction table: starter hex_rotation -> directions with a
# connecting goal rotation. Direction indices follow hex.HEX_DIRECTIONS
# (0=E, 1=NE, 2=NW, 3=W, 4=SW, 5=SE). Provenance, per row:
#
#   s=0: E and NW      (2026-08-07 sweep + 2026-08-08 NW-rot-0 backfill)
#   s=1: NE only       (2026-08-08 full sweep -- exactly one cell in 36)
#   s=2: E and NW      (2026-08-10 queue run; one 520'd upload closed by auto-resume)
#   s=3: NE only       (2026-08-10 queue run)
#   s=4: E and NW      (2026-08-10 queue run; one frame-guard hole closed by auto-resume)
#   s=5: NE only       (2026-08-10 queue run)
#
# Every row is an exhaustive 36-cell sweep bracketed by an active control at
# both ends. A row claims the complete set; partial knowledge never earns one
# -- which is also why s=4 and s=5 count as forward predictions of the parity
# pattern rather than fits: even -> {E, NW}, odd -> {NE} was declared before
# their renders ran, and both landed.
MEASURED_LIVE_DIRECTIONS: Mapping[int, frozenset[int]] = MappingProxyType(
    {
        0: frozenset({0, 2}),  # E, NW
        1: frozenset({1}),  # NE
        2: frozenset({0, 2}),  # E, NW
        3: frozenset({1}),  # NE
        4: frozenset({0, 2}),  # E, NW
        5: frozenset({1}),  # NE
    }
)


class UnsweptStarterRotationError(LookupError):
    """Raised when the live-direction table is asked about an unswept starter rotation."""

    def __init__(self, starter_rot: int) -> None:
        self.starter_rot = starter_rot
        super().__init__(
            f"starter rotation {starter_rot} has not been exhaustively swept; "
            f"measured rotations: {sorted(MEASURED_LIVE_DIRECTIONS)}. "
            "The table does not interpolate (decisions.md 2026-08-08); "
            "run scripts/run_sweep_queue.py to measure it."
        )


def goal_rotation_for(direction: int) -> int:
    """The goal rotation that connects from `direction`: g = (d + 1) % 6.

    Goal-side rule, no starter term. Confirmed on every active cell ever
    measured (E->1, NW->3, NE->2) across two exhaustively swept starter
    rotations, zero exceptions.
    """
    if not 0 <= direction <= 5:
        raise ValueError(f"direction must be 0..5, got {direction}")
    return (direction + 1) % 6


def live_directions(starter_rot: int) -> frozenset[int]:
    """The measured set of connecting directions at `starter_rot`.

    Refuses rotations outside the measured range rather than guessing --
    absence from the table means "unknown", never "none". All six standard
    rotations are measured (even -> {E, NW}, odd -> {NE}); out-of-range
    values stay refusals because the app's modulo behaviour is still open
    unknown #11.
    """
    try:
        return MEASURED_LIVE_DIRECTIONS[starter_rot]
    except KeyError:
        raise UnsweptStarterRotationError(starter_rot) from None


class ConnectionStatus(Enum):
    """What the measured record lets us claim about one starter/goal pair."""

    CONNECTED = auto()
    DISCONNECTED = auto()
    UNMEASURED = auto()


def connection_status(starter_rot: int, direction: int, goal_rotation: int) -> ConnectionStatus:
    """Classify one (starter rotation, direction, goal rotation) cell.

    CONNECTED and DISCONNECTED are only ever claimed inside the measured
    space: at a swept starter rotation, every one of the 36 direction x
    rotation cells was rendered, so a miss there is a measured miss.
    An unswept starter rotation is UNMEASURED regardless of the other two
    coordinates -- including rotations outside 0..5, which the app's modulo
    behaviour is an open unknown for (#11).
    """
    if not 0 <= direction <= 5:
        raise ValueError(f"direction must be 0..5, got {direction}")
    if starter_rot not in MEASURED_LIVE_DIRECTIONS:
        return ConnectionStatus.UNMEASURED
    if direction not in MEASURED_LIVE_DIRECTIONS[starter_rot]:
        return ConnectionStatus.DISCONNECTED
    if goal_rotation != goal_rotation_for(direction):
        return ConnectionStatus.DISCONNECTED
    return ConnectionStatus.CONNECTED


@dataclass(frozen=True, slots=True)
class PlacedTile:
    """One tile with its world position -- the node type of the track graph."""

    kind: TileKind
    world_pos: HexVector
    hex_rotation: int
    layer_id: int


def placed_tiles(course: Course) -> Iterator[PlacedTile]:
    """Every layer-cell tile in the course, positioned in world coordinates.

    World position = layer world_hex_position + cell local_hex_position, the
    same composition the validator's retainer resolution uses. Balcony cells
    are skipped: they live in their wall's coordinate system, which is still
    unreconciled with layer world-coords (open unknown #4).
    """
    for layer in course.layer_construction_data:
        for cell in layer.cell_construction_datas:
            world = layer.world_hex_position + cell.local_hex_position
            stack = [cell.tree_node_data]
            while stack:
                node = stack.pop()
                yield PlacedTile(
                    kind=node.construction_data.kind,
                    world_pos=world,
                    hex_rotation=node.construction_data.hex_rotation,
                    layer_id=layer.layer_id,
                )
                stack.extend(node.children)


def classify_pair(starter: PlacedTile, goal: PlacedTile) -> ConnectionStatus:
    """Classify one placed starter/goal pair against the measured record.

    Cross-layer pairs are UNMEASURED: every measurement to date sits on a
    single BASE_LAYER_PIECE layer. Non-adjacent same-layer pairs are
    DISCONNECTED: distance-2 is measured dead at every swept rotation (the
    sweeps' far controls), and the rail-free mechanism is tile adjacency --
    there is nothing left to carry a connection across a gap.
    """
    if starter.layer_id != goal.layer_id:
        return ConnectionStatus.UNMEASURED
    direction = starter.world_pos.direction_to(goal.world_pos)
    if direction is None:
        return ConnectionStatus.DISCONNECTED
    return connection_status(starter.hex_rotation, direction, goal.hex_rotation)


def start_goal_status(course: Course) -> ConnectionStatus | None:
    """The best connection status over every starter/goal pair, or None if
    the course has no starter or no goal (that absence is
    MISSING_STARTER_OR_GOAL's finding, not this module's).

    CONNECTED beats UNMEASURED beats DISCONNECTED: one measured connection
    makes the course connected no matter how many dead pairs surround it, and
    one unmeasured pair keeps "disconnected" from being claimed on evidence
    we do not have.
    """
    tiles = list(placed_tiles(course))
    starters = [t for t in tiles if t.kind in STARTER_KINDS]
    goals = [t for t in tiles if t.kind in GOAL_KINDS]
    if not starters or not goals:
        return None
    statuses = {classify_pair(s, g) for s in starters for g in goals}
    for status in (
        ConnectionStatus.CONNECTED,
        ConnectionStatus.UNMEASURED,
        ConnectionStatus.DISCONNECTED,
    ):
        if status in statuses:
            return status
    raise AssertionError("unreachable: statuses is non-empty")
