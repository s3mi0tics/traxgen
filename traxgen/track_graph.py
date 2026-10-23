"""A course as a graph of doorways: valid when every route from the starter ends in a goal.

Path: traxgen/track_graph.py

The design is s44-t1's (`allostatik/knowledge/task_reports/`). A node is the
marble crossing one doorway *into* one cell: the cell entered, the side it came
in by, and a height step. Arrows run inside a piece (enter by this side, leave
by that one) and between neighbouring pieces (one's way out is the other's way
in, on the opposite side). Checking every route is LeetCode 1059, *All Paths
From Source Lead to Destination*: a reachable way out with nothing behind it is
a dead end, and reaching a doorway already on the current route is a loop.

**This is a model, in `graph.py`'s sense, not a claim.** It answers for courses
no render has played. What the app actually did is `graph.MEASURED_FINISHES`;
this module is checked against it, and the generator and the unattended loop
use it to propose. Its answer is three-valued for the same reason
`ConnectionStatus` is: a piece with no measured rule makes the answer
UNMEASURED, never a guess.

First build: STARTER and GOAL_RAIL, flat on baseplates, no rails. Anything else
in a course -- another piece, a stacked cell, a rail, a pillar, a wall, a
raised layer -- reads UNMEASURED.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from traxgen.domain import Course
from traxgen.graph import STARTER_INTRINSIC_PORTS, PlacedTile, course_plate_positions, placed_tiles
from traxgen.hex import HexVector
from traxgen.plates import half_hole_cells, is_on_plate
from traxgen.types import TileKind

# The plate that completes a half-hole sits at this offset from the half-hole's
# own plate (D066; `plates.is_buildable_on_plate`).
HALF_HOLE_COMPLETER_OFFSET: tuple[int, int] = (5, 0)

# GOAL_RAIL's way in, in its own frame. World side = (2 + hex_rotation) % 6,
# which is the goal-side rule `(d + 1) % 6` seen from the goal's cell: a goal
# one step in direction d has its way in on side (d + 3) % 6.
GOAL_RAIL_ENTRANCE: int = 2


class TrackStatus(Enum):
    """The checker's answer for a whole course."""

    VALID = "valid"
    INVALID = "invalid"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True, slots=True)
class Doorway:
    """The marble crossing into `cell` by its side `side`, at height step `height`."""

    cell: HexVector
    side: int
    height: int = 0


@dataclass(frozen=True, slots=True)
class TrackVerdict:
    """The answer, why, and the doorway where it was decided (None for a whole-course reason)."""

    status: TrackStatus
    reason: str
    at: Doorway | None = None


@dataclass(frozen=True, slots=True)
class Through:
    """What a piece does with a marble entering by one side.

    `exits` are world sides the marble may leave by. `caught` means the piece
    is a goal that holds it. `only_where_joined` is the starter's rule: its
    sides with nothing behind them are not routes (every recorded course has
    two such sides and still finishes). `accepts` is False when the piece has
    no way in by that side at all -- a goal turned away -- as distinct from a
    piece that takes the marble in and has no way on, which is a dead end.

    Which side a starter's marble leaves by depends on where the marbles sit in
    it, and the app loads a marble only where the starter has a **valid
    connection** -- a neighbour that accepts the marble from that side -- not
    merely a piece beside it, and not only on a valid track (Colby, s44, by
    eye in the app). So the starter's routes are its accepting neighbours.
    With none, no marble loads. With more than one, where the marbles go is
    unmeasured and the answer is UNMEASURED.
    """

    exits: frozenset[int] = frozenset()
    caught: bool = False
    only_where_joined: bool = False
    accepts: bool = True


@dataclass(frozen=True, slots=True)
class Board:
    """The course facts a piece rule may need besides its own tile."""

    plate_positions: frozenset[tuple[int, int]]


# A piece rule: the tile, the side it was entered by (None for the launch), the board.
PieceRule = Callable[[PlacedTile, int | None, Board], Through]


def starter_rule(tile: PlacedTile, entered: int | None, board: Board) -> Through:
    """STARTER: launched from START, it may leave by sides (0, 2, 4) turned by its rotation."""
    if entered is not None:
        return Through(accepts=False)
    return Through(
        exits=frozenset((p + tile.hex_rotation) % 6 for p in STARTER_INTRINSIC_PORTS),
        only_where_joined=True,
    )


def goal_rail_rule(tile: PlacedTile, entered: int | None, board: Board) -> Through:
    """GOAL_RAIL: entered by its way in, it catches the marble -- unless it stands on an
    uncompleted half-hole, where the marble arrives and is not caught (s43, MEASURED_FINISHES).

    The half-hole term is fitted to the record's 3 misses, which share one
    placement (s44-t1); it is goal-only because a *starter* on the same
    half-hole finished (r06).
    """
    if entered != (GOAL_RAIL_ENTRANCE + tile.hex_rotation) % 6:
        return Through(accepts=False)
    return Through(caught=not _on_uncompleted_half_hole(tile, board))


PIECE_RULES: Mapping[TileKind, PieceRule] = MappingProxyType(
    {
        TileKind.STARTER: starter_rule,
        TileKind.GOAL_RAIL: goal_rail_rule,
    }
)


def check_course(course: Course, rules: Mapping[TileKind, PieceRule] = PIECE_RULES) -> TrackVerdict:
    """Walk every route from the starter; VALID only if each one ends caught by a goal.

    INVALID beats UNMEASURED: one measured dead end or loop fails the course
    whatever the unmeasured routes do. `rules` is injectable so tests can
    supply pieces the record has not measured, to exercise loops.
    """
    refusal = _unmodelled(course)
    if refusal is not None:
        return TrackVerdict(TrackStatus.UNMEASURED, refusal)

    tiles = list(placed_tiles(course))
    by_cell: dict[tuple[int, int], PlacedTile] = {}
    for tile in tiles:
        key = (tile.world_pos.y, tile.world_pos.x)
        if key in by_cell:
            return TrackVerdict(TrackStatus.UNMEASURED, f"cell {key} holds more than one tile")
        by_cell[key] = tile
    unruled = sorted({t.kind.name for t in tiles if t.kind not in rules})
    if unruled:
        return TrackVerdict(TrackStatus.UNMEASURED, f"no measured rule for {', '.join(unruled)}")
    starters = [t for t in tiles if t.kind is TileKind.STARTER]
    if len(starters) != 1:
        return TrackVerdict(TrackStatus.UNMEASURED, f"{len(starters)} starters; measured with one")
    if not is_on_plate(starters[0].layer_kind, starters[0].local_pos):
        return TrackVerdict(TrackStatus.UNMEASURED, "starter is off its plate's footprint")

    walk = _Walk(by_cell, rules, Board(frozenset(course_plate_positions(course))))
    return walk.launch(starters[0])


def _unmodelled(course: Course) -> str | None:
    """Why this course is outside the first build, or None."""
    if course.rail_construction_data:
        return "course has rails"
    if course.pillar_construction_data:
        return "course has pillars"
    if any(w.balcony_construction_datas for w in course.wall_construction_data):
        return "course has balconies"
    for layer in course.layer_construction_data:
        if layer.layer_height != 0.0:
            return f"layer {layer.layer_id} is raised"
        for cell in layer.cell_construction_datas:
            if cell.tree_node_data.children:
                return f"layer {layer.layer_id} has a stacked cell"
    return None


def _on_uncompleted_half_hole(tile: PlacedTile, board: Board) -> bool:
    local = (tile.local_pos.y, tile.local_pos.x)
    if local not in half_hole_cells(tile.layer_kind):
        return False
    plate = tile.world_pos - tile.local_pos
    dy, dx = HALF_HOLE_COMPLETER_OFFSET
    return (plate.y + dy, plate.x + dx) not in board.plate_positions


class _Walk:
    """One depth-first walk; `on_route` holds the doorways of the route being followed."""

    def __init__(
        self,
        by_cell: Mapping[tuple[int, int], PlacedTile],
        rules: Mapping[TileKind, PieceRule],
        board: Board,
    ) -> None:
        self.by_cell = by_cell
        self.rules = rules
        self.board = board
        self.on_route: set[Doorway] = set()
        self.done: set[Doorway] = set()
        self.unmeasured: TrackVerdict | None = None

    def launch(self, starter: PlacedTile) -> TrackVerdict:
        through = self.rules[starter.kind](starter, None, self.board)
        verdict = self._leave(starter, through, at=None)
        if verdict is not None:
            return verdict
        if self.unmeasured is not None:
            return self.unmeasured
        return TrackVerdict(TrackStatus.VALID, "every route ends in a goal")

    def _leave(self, tile: PlacedTile, through: Through, at: Doorway | None) -> TrackVerdict | None:
        """Follow every way out of `tile`; an INVALID verdict, or None if none was found."""
        if through.caught:
            return None
        exits = sorted(through.exits)
        if through.only_where_joined:
            exits = [e for e in exits if self._accepts(tile, e)]
            if not exits:
                return TrackVerdict(
                    TrackStatus.INVALID, "no valid connection to the starter: no marble loads", at
                )
            if len(exits) > 1:
                self.unmeasured = self.unmeasured or TrackVerdict(
                    TrackStatus.UNMEASURED,
                    "starter has more than one valid connection; where its marbles go "
                    "is unmeasured",
                    at,
                )
                return None
        if not exits:
            return TrackVerdict(
                TrackStatus.INVALID, f"dead end: {tile.kind.name} has no way on", at
            )
        for side in exits:
            verdict = self._enter(tile, side)
            if verdict is not None:
                return verdict
        return None

    def _enter(self, tile: PlacedTile, side: int) -> TrackVerdict | None:
        """The marble leaves `tile` by `side` into the neighbouring cell."""
        nxt = tile.world_pos.neighbor(side)
        door = Doorway(cell=nxt, side=(side + 3) % 6)
        if door in self.on_route:
            return TrackVerdict(
                TrackStatus.INVALID, "loop: a route comes back to this doorway", door
            )
        if door in self.done:
            return None
        behind = self._tile_behind(tile, side)
        if behind is None:
            return TrackVerdict(TrackStatus.INVALID, "dead end: nothing behind this doorway", door)
        if not is_on_plate(behind.layer_kind, behind.local_pos):
            return TrackVerdict(
                TrackStatus.INVALID,
                f"dead end: {behind.kind.name} is off its plate's footprint",
                door,
            )
        self.on_route.add(door)
        through = self.rules[behind.kind](behind, door.side, self.board)
        if not through.accepts:
            self.on_route.discard(door)
            return TrackVerdict(
                TrackStatus.INVALID, f"dead end: {behind.kind.name} has no way in here", door
            )
        verdict = self._leave(behind, through, at=door)
        self.on_route.discard(door)
        self.done.add(door)
        return verdict

    def _accepts(self, tile: PlacedTile, side: int) -> bool:
        """Whether the neighbour across `side` is on its plate and takes the marble in there."""
        behind = self._tile_behind(tile, side)
        if behind is None or not is_on_plate(behind.layer_kind, behind.local_pos):
            return False
        return self.rules[behind.kind](behind, (side + 3) % 6, self.board).accepts

    def _tile_behind(self, tile: PlacedTile, side: int) -> PlacedTile | None:
        nxt = tile.world_pos.neighbor(side)
        return self.by_cell.get((nxt.y, nxt.x))
