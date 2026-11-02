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

First build: STARTER and GOAL_RAIL, flat on baseplates, no rails; CURVE since
s46, CROSS since s47, SWITCH_LEFT and SWITCH_RIGHT since s48, for one marble
per switch. Anything else
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

# CURVE's two tracks, in its own frame: each side maps to the side it leaves by.
# A gentle 60-degree track joins sides 0 and 2, a sharp 120-degree one joins 3
# and 4, both ridden either way; sides 1 and 5 have no way in. Measured on
# Colby's board `7UNB5OAAOT` (s45): launch pads at rotation 0, each with a
# curve one step NW, so the marble enters by world side 5, curve side
# (5 - rotation) % 6. Rotations 5, 3, 2, 1 left by the sides below; rotation 0
# (side 5) loaded no marble, twice. Side 1 (rotation 4) is Colby's description
# of the piece plus the four-of-six count, not a run.
CURVE_TRACKS: Mapping[int, int] = MappingProxyType({0: 2, 2: 0, 3: 4, 4: 3})

# CROSS (the X-intersection), in its own frame: two straight tracks, 1-4 and
# 2-5, crossing at one level; sides 0 and 3 have no way in. Measured on the ring
# board `YFUGDSMDUH` (s47-t4, the goal-less twin of `8NN7VNHLIA`): rotations 0,
# 1, 3 and 4 entered by sides 5, 4, 2 and 1, and every marble left straight
# across, by world side 2; rotations 2 and 5 (sides 3 and 0) loaded no marble.
# Every entry is measured once, each track in both directions.
CROSS_TRACKS: Mapping[int, int] = MappingProxyType({1: 4, 4: 1, 2: 5, 5: 2})

# The switch, in its own frame, for the first marble through it: side 2 is where
# its branches 0 and 4 meet. `None` is a side that takes the marble in and stops
# it against the lever. Measured on the goal-less ring boards `Q7AE2SM7MC`
# (SWITCH_LEFT) and `54TI3KWGTH` (SWITCH_RIGHT), s48-t3: launch pads at rotation
# 0 on the piece's world side 5, so it is entered by (5 - rotation) % 6.
# Rotations 3 and 5 left by world side 1 (LEFT) or 3 (RIGHT); at rotation 1
# (LEFT) or 5 (RIGHT) the marble stopped inside; rotations 0, 2, 4 (the odd
# sides) loaded no marble. Each entry measured once.
#
# A passing marble flips the lever (s48-t4, `8WL7RXS9H4`): after one marble
# passes SWITCH_LEFT by 0 -> 2, its side 4 passes to 2, which is SWITCH_RIGHT's
# table, and the mirror. So the kind is the lever's starting position, and a
# second marble's path depends on which marble arrives first -- timing the
# checker does not model. A course where a switch could see a second marble
# reads UNMEASURED.
SWITCH_LEFT_TRACKS: Mapping[int, int | None] = MappingProxyType({0: 2, 2: 4, 4: None})
SWITCH_RIGHT_TRACKS: Mapping[int, int | None] = MappingProxyType({4: 2, 2: 0, 0: None})
SWITCH_KINDS: frozenset[TileKind] = frozenset({TileKind.SWITCH_LEFT, TileKind.SWITCH_RIGHT})


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
    With none, no marble loads. With several, each is a route of its own and
    each has to end in a goal (Colby, s44).
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


def tracks_rule(tracks: Mapping[int, int | None]) -> PieceRule:
    """A piece of fixed tracks: entered by a track's end, in the piece's own frame, it leaves
    by that track's other end; a side mapped to None takes the marble in and holds it (a dead
    end); any other side takes no marble."""

    def rule(tile: PlacedTile, entered: int | None, board: Board) -> Through:
        if entered is None:
            return Through(accepts=False)
        side = (entered - tile.hex_rotation) % 6
        if side not in tracks:
            return Through(accepts=False)
        out = tracks[side]
        if out is None:
            return Through()
        return Through(exits=frozenset({(out + tile.hex_rotation) % 6}))

    return rule


curve_rule = tracks_rule(CURVE_TRACKS)
cross_rule = tracks_rule(CROSS_TRACKS)
switch_left_rule = tracks_rule(SWITCH_LEFT_TRACKS)
switch_right_rule = tracks_rule(SWITCH_RIGHT_TRACKS)


PIECE_RULES: Mapping[TileKind, PieceRule] = MappingProxyType(
    {
        TileKind.STARTER: starter_rule,
        TileKind.GOAL_RAIL: goal_rail_rule,
        TileKind.CURVE: curve_rule,
        TileKind.CROSS: cross_rule,
        TileKind.SWITCH_LEFT: switch_left_rule,
        TileKind.SWITCH_RIGHT: switch_right_rule,
    }
)


def check_course(course: Course, rules: Mapping[TileKind, PieceRule] = PIECE_RULES) -> TrackVerdict:
    """Walk every route from the starter; VALID only if each one ends caught by a goal.

    UNMEASURED is decided before the walk: a course holding anything without a
    rule reads UNMEASURED even if a measured route in it dead-ends. Walking the
    measured routes first, so a known dead end could fail such a course, is
    left until a course needs it. `rules` is injectable so tests can supply
    pieces the record has not measured, to exercise loops.
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

    def launch(self, starter: PlacedTile) -> TrackVerdict:
        through = self.rules[starter.kind](starter, None, self.board)
        if any(t.kind in SWITCH_KINDS for t in self.by_cell.values()):
            marbles = sum(1 for e in through.exits if self._accepts(starter, e))
            if marbles > 1:
                return TrackVerdict(
                    TrackStatus.UNMEASURED,
                    f"{marbles} marbles on a course with a switch: which reaches it first "
                    "decides its lever (s48-t4)",
                )
        verdict = self._leave(starter, through, at=None)
        if verdict is not None:
            return verdict
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
        if behind.kind in SWITCH_KINDS and any(d.cell == nxt for d in self.on_route):
            return TrackVerdict(
                TrackStatus.UNMEASURED,
                f"a route reaches {behind.kind.name} a second time, after its lever has flipped",
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
