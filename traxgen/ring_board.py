"""One board that tests every rotation of a piece: a ring per rotation, read per goal (s46).

Path: traxgen/ring_board.py

Colby's design (s45, `7UNB5OAAOT`): the app plays any number of launch pads on
one board, and each loads a marble only where it has a valid connection, so
tests that don't touch can share a board. A **ring** is one test: the piece at
its centre, a launch pad on its SE side at rotation 0 (so the marble enters the
piece by world side 5, as on Colby's board), and a goal facing the piece on
each of the other five sides. Whichever side the marble leaves by, a goal
catches it, so the board *measures* the exit rather than checking a guess.

Rings are placed greedily, in a fixed order, at least four cells apart centre
to centre, which leaves an empty cell between any two rings: no launch pad or
goal of one ring is beside a piece of another.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from traxgen.domain import Course
from traxgen.graph import goal_rotation_for
from traxgen.hex import HexVector
from traxgen.layout import TilePlacement, build_course, owning_plate
from traxgen.plates import STANDARD_SQUARE, half_hole_cells
from traxgen.types import LayerKind, TileKind

# The launch pad's side of the piece, and its rotation: the piece is one step
# NW of it, which is one of a rotation-0 launch pad's three ways out.
STARTER_SIDE: int = 5
STARTER_ROTATION: int = 0
GOAL_SIDES: tuple[int, ...] = tuple(d for d in range(6) if d != STARTER_SIDE)

# Centre-to-centre distance between rings. Each ring has radius 1, so 4 leaves
# at least one empty cell between any two of them.
RING_SPACING: int = 4

HALF_HOLE_COMPLETER_OFFSET: tuple[int, int] = (5, 0)


@dataclass(frozen=True, slots=True)
class Ring:
    """One test: the piece at `centre` at `rotation`; `goals` maps each side to its goal's cell."""

    rotation: int
    centre: HexVector
    starter: HexVector
    goals: Mapping[int, HexVector]

    def cells(self) -> tuple[HexVector, ...]:
        """Every world cell the ring occupies."""
        return (self.centre, self.starter, *self.goals.values())


@dataclass(frozen=True, slots=True)
class RingBoard:
    """The course, and which ring is where -- the manifest a per-goal reader needs."""

    kind: TileKind
    course: Course
    plates: tuple[HexVector, ...]
    rings: tuple[Ring, ...]


def hex_distance(a: HexVector, b: HexVector) -> int:
    """Steps between two cells on this project's axial grid."""
    dy, dx = a.y - b.y, a.x - b.x
    return max(abs(dy), abs(dx), abs(dy + dx))


def is_buildable(plates: Sequence[HexVector], world_cell: HexVector) -> bool:
    """On exactly one plate's footprint, and not an uncompleted half-hole there (D066)."""
    owner = owning_plate(plates, world_cell)
    if owner is None:
        return False
    index, local = owner
    if (local.y, local.x) not in half_hole_cells(LayerKind.BASE_LAYER_PIECE):
        return True
    dy, dx = HALF_HOLE_COMPLETER_OFFSET
    return plates[index] + HexVector(y=dy, x=dx) in plates


def ring_at(centre: HexVector, rotation: int) -> Ring:
    """The ring for one rotation, centred on `centre`."""
    return Ring(
        rotation=rotation,
        centre=centre,
        starter=centre.neighbor(STARTER_SIDE),
        goals=MappingProxyType({d: centre.neighbor(d) for d in GOAL_SIDES}),
    )


def place_rings(plates: Sequence[HexVector], rotations: Iterable[int]) -> tuple[Ring, ...]:
    """Greedy placement, scanning cells in a fixed order; raises if a rotation does not fit."""
    wanted = list(rotations)
    candidates = sorted(
        {plate + HexVector(y=y, x=x) for plate in plates for y in range(-6, 1) for x in range(6)},
        key=lambda c: (c.y, c.x),
    )
    rings: list[Ring] = []
    for centre in candidates:
        if len(rings) == len(wanted):
            break
        ring = ring_at(centre, wanted[len(rings)])
        if not all(is_buildable(plates, c) for c in ring.cells()):
            continue
        if any(hex_distance(centre, r.centre) < RING_SPACING for r in rings):
            continue
        rings.append(ring)
    if len(rings) < len(wanted):
        raise ValueError(f"only {len(rings)} of {len(wanted)} rings fit on {len(plates)} plates")
    return tuple(rings)


def ring_tiles(kind: TileKind, plates: Sequence[HexVector], ring: Ring) -> list[TilePlacement]:
    """The ring's seven tiles, each addressed on the plate that owns its cell."""
    placed = [
        (kind, ring.centre, ring.rotation),
        (TileKind.STARTER, ring.starter, STARTER_ROTATION),
    ]
    placed += [(TileKind.GOAL_RAIL, cell, goal_rotation_for(d)) for d, cell in ring.goals.items()]
    tiles = []
    for tile_kind, cell, rotation in placed:
        owner = owning_plate(plates, cell)
        if owner is None:
            raise ValueError(f"cell ({cell.y}, {cell.x}) is on no plate")
        tiles.append(TilePlacement(tile_kind, owner[0], owner[1], rotation))
    return tiles


def ring_board(
    kind: TileKind,
    rotations: Iterable[int] = range(6),
    plate_positions: Sequence[tuple[int, int]] = STANDARD_SQUARE,
) -> RingBoard:
    """A course with one ring of `kind` per rotation."""
    plates = tuple(HexVector(y=y, x=x) for y, x in plate_positions)
    rings = place_rings(plates, rotations)
    tiles = [t for ring in rings for t in ring_tiles(kind, plates, ring)]
    course = build_course(
        plate_world_positions=plates, tiles=tiles, title=f"traxgen-rings-{kind.name.lower()}"
    )
    return RingBoard(kind=kind, course=course, plates=plates, rings=rings)


def single_ring_course(board: RingBoard, ring: Ring) -> Course:
    """The same plates holding only `ring`: what the checker reads, one launch pad at a time."""
    return build_course(
        plate_world_positions=board.plates,
        tiles=ring_tiles(board.kind, board.plates, ring),
        title="traxgen-ring",
    )
