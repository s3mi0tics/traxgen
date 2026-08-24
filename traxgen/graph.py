# Path: traxgen/traxgen/graph.py
"""Connection semantics and the Phase-1 track graph (M5.c + the first slice of M5.a).

Whether a STARTER connects to a GOAL_RAIL is a **conjunction of two measured
terms**, separated here so neither can absorb the other (`decisions.md`
2026-08-21):

    live(s, pos) = plate_available(pos) INTERSECT starter_world_ports(s)

  * `starter_world_ports` -- the STARTER's own openings, in world frame. Its
    intrinsic ports are the even tile-relative edges {0, 2, 4} (corpus mining,
    n=380 unambiguous, zero odd observations), so the set is all-even at even
    rotations and all-odd at odd ones. This term rotates with the starter.
  * `plate_available` -- which neighbouring cells sit on a baseplate at all,
    from `plates.py`'s corpus-measured footprints. This term is **world-fixed**:
    it does not rotate, which is why the live set never rotated either.
  * `goal_rotation_for` -- the goal-side rule `g = (d + 1) % 6`, which takes no
    starter term and has never once been violated on any active cell
    (`decisions.md`, "Goal rotation is a goal-side rule").

Until 2026-08-21 this module keyed connection on the starter's rotation alone.
Every sweep behind that table had pinned the STARTER at BASE_LAYER_PIECE local
(0, 0) -- a plate **corner**, whose W, SW and SE neighbours are unobserved in
28,494 corpus placements -- and the table recorded the rotation while silently
absorbing the position. That is where the unexplained 2-vs-1 asymmetry came
from: at the corner, `plate_available` is `{E, NE, NW}`, so intersecting the
even port set leaves two directions and the odd set leaves one. The mechanism
was a missing coordinate, not a property of the starter.

**The conjunction is a model, and this module does not let a model make
claims.** `connection_status` answers only from `MEASURED_RUNS` -- the rendered
record -- and returns UNMEASURED everywhere else. The model is exposed
separately, on `predicted_live_directions` / `predict_connection`, for callers
that want to *propose* geometries (a generator ordering candidates) rather than
*assert* them. Corpus proposes, render disposes; the three-valued status is
where that discipline lives in code.

Connection here means the rail-free mechanism locked on 2026-06-12: a STARTER
adjacent to a GOAL_RAIL whose integrated rail faces it, `rail_count = 0`.

Path: traxgen/traxgen/graph.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from types import MappingProxyType
from typing import TYPE_CHECKING

from traxgen.hex import HexVector
from traxgen.inventory import PIECE_CATALOG
from traxgen.plates import plate_available_directions
from traxgen.types import LayerKind, TileKind

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

# The STARTER's intrinsic ports as tile-relative edges, from corpus mining
# (2026-08-18): rel = (side_hex_rot - tile.hex_rotation) % 6 over 380
# unambiguous observations, histogram {0: 130, 2: 122, 4: 128}. Even-only and
# balanced, with zero odd-edge observations -- an even-only set is what makes
# the world-frame ports flip parity with the rotation.
#
# Positive evidence only, and thin in one specific place: GOAL_RAIL has **zero**
# port records in 43,375, because it carries its own rail and so never appears
# in a RailConstructionExitIdentifier. Its port is derived (rel = 2, which is
# what makes `goal_rotation_for` carry no starter term), never measured.
STARTER_INTRINSIC_PORTS: frozenset[int] = frozenset({0, 2, 4})


@dataclass(frozen=True, slots=True)
class MeasuredRun:
    """One rendered campaign, and exactly what it covered.

    `goal_rotations_swept` is the difference between a 36-cell sweep, which
    rendered every direction at every goal rotation, and a probe run, which
    rendered each direction only at its connecting rotation `(d + 1) % 6`.
    A probe run therefore says nothing about the other five rotations, and
    `connection_status` reports UNMEASURED for them rather than borrowing the
    sweeps' coverage.
    """

    layer_kind: LayerKind
    starter_local_pos: tuple[int, int]
    starter_rot: int
    live_directions: frozenset[int]
    goal_rotations_swept: bool
    provenance: str


# The rendered record. Direction indices follow hex.HEX_DIRECTIONS
# (0=E, 1=NE, 2=NW, 3=W, 4=SW, 5=SE). Every run was bracketed by an active
# control at both ends (`decisions.md` 2026-08-07), and the two probe runs also
# carried a local control at the position under test (2026-08-21).
MEASURED_RUNS: tuple[MeasuredRun, ...] = (
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=0,
        live_directions=frozenset({0, 2}),  # E, NW
        goal_rotations_swept=True,
        provenance="2026-08-07 36-cell sweep + 2026-08-08 NW-rot-0 backfill",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=1,
        live_directions=frozenset({1}),  # NE
        goal_rotations_swept=True,
        provenance="2026-08-08 full sweep -- exactly one live cell in 36",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=2,
        live_directions=frozenset({0, 2}),  # E, NW
        goal_rotations_swept=True,
        provenance="2026-08-10 queue run; one 520'd upload closed by auto-resume",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=3,
        live_directions=frozenset({1}),  # NE
        goal_rotations_swept=True,
        provenance="2026-08-10 queue run",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=4,
        live_directions=frozenset({0, 2}),  # E, NW
        goal_rotations_swept=True,
        provenance="2026-08-10 queue run; one frame-guard hole closed by auto-resume",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=5,
        live_directions=frozenset({1}),  # NE
        goal_rotations_swept=True,
        provenance="2026-08-10 queue run",
    ),
    # The two runs that found the missing coordinate. Both declared every
    # cell's verdict in code before rendering (`decisions.md` 2026-08-08).
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 1),
        starter_rot=0,
        live_directions=frozenset({2}),  # NW alone
        goal_rotations_swept=False,
        provenance=(
            "2026-08-21 edge probe -- E and SW are port-allowed but off-plate "
            "and both rendered inactive, which refuted the port-only model"
        ),
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(-3, 2),
        starter_rot=0,
        live_directions=frozenset({0, 2, 4}),  # E, NW, SW
        goal_rotations_swept=False,
        provenance=(
            "2026-08-21 interior probe -- SW rendered active after six "
            "exhaustive corner sweeps called it dark, which refuted this "
            "module's own position-blind table"
        ),
    ),
    # The first measurement of an ODD rotation away from the plate corner.
    # Until this run, every odd-rotation row in the record sat at (0,0), where
    # three of six neighbours are off-plate -- so "odd gives one live
    # direction" was a corner fact being read as a rotation fact.
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(-3, 2),
        starter_rot=1,
        live_directions=frozenset({1, 3, 5}),  # NE, W, SE
        goal_rotations_swept=False,
        provenance=(
            "2026-08-23 interior probe at odd rotation -- W and SE rendered "
            "active after being dark in all six exhaustive corner sweeps, "
            "refuting the frozen position-blind table on two cells at once. "
            "7/7 predicted correctly, declared in code before rendering; "
            "bracketed by an active certified control at both ends plus a "
            "local control at (-3,2). plate and port_only are equivalent here "
            "by construction -- nothing is off-plate to separate them; the "
            "2026-08-21 edge run is what separates that pair"
        ),
    ),
)

# The corner table, derived from the runs above rather than restated. Kept as a
# named surface because it is the regression fixture the conjunction has to
# reproduce: parity (even -> {E, NW}, odd -> {NE}) is the shape six exhaustive
# sweeps measured, and any change to the model that stops reproducing it has
# broken against real renders rather than against an opinion.
MEASURED_LIVE_DIRECTIONS: Mapping[int, frozenset[int]] = MappingProxyType(
    {
        run.starter_rot: run.live_directions
        for run in MEASURED_RUNS
        if run.layer_kind is LayerKind.BASE_LAYER_PIECE
        and run.starter_local_pos == (0, 0)
        and run.goal_rotations_swept
    }
)


class UnsweptStarterRotationError(LookupError):
    """Raised when the corner table is asked about an unswept starter rotation."""

    def __init__(self, starter_rot: int) -> None:
        self.starter_rot = starter_rot
        super().__init__(
            f"starter rotation {starter_rot} has not been exhaustively swept at "
            f"the plate corner; measured rotations: {sorted(MEASURED_LIVE_DIRECTIONS)}. "
            "The record does not interpolate (decisions.md 2026-08-08); "
            "for an unmeasured configuration use predicted_live_directions(), "
            "which is explicitly a model rather than a claim."
        )


def goal_rotation_for(direction: int) -> int:
    """The goal rotation that connects from `direction`: g = (d + 1) % 6.

    Goal-side rule, no starter term. Six exhaustive 36-cell corner sweeps
    tested it against all five rival rotations per direction and it was never
    violated -- E->1, NW->3, NE->2.

    The two 2026-08-21 probe runs are **not** further tests of it: they rendered
    each direction only at `(d + 1) % 6`, because the rule was assumed in order
    to spend renders on the plate term instead. They are consistent with it and
    they do not confirm it, and those are different things (observation #19).
    """
    if not 0 <= direction <= 5:
        raise ValueError(f"direction must be 0..5, got {direction}")
    return (direction + 1) % 6


def starter_world_ports(starter_rot: int) -> frozenset[int]:
    """The STARTER's port edges in world frame at `starter_rot`.

    A tile-relative edge r presents at world edge `(r + rotation) % 6`. With an
    even-only intrinsic set this is all-even at even rotations and all-odd at
    odd ones -- the parity flip the measured table shows.

    Refuses rotations outside 0..5 rather than taking the modulo: whether the
    app normalises an out-of-range `hex_rotation` is open unknown #11, so
    answering would be guessing at the thing that is unknown.
    """
    if not 0 <= starter_rot <= 5:
        raise ValueError(f"starter_rot must be 0..5, got {starter_rot}")
    return frozenset((r + starter_rot) % 6 for r in STARTER_INTRINSIC_PORTS)


def predicted_live_directions(
    starter_rot: int, *, layer_kind: LayerKind, starter_local_pos: HexVector
) -> frozenset[int]:
    """The conjunction's **prediction** for which directions connect.

    This is a model, not a claim -- it will happily answer for geometries no
    render has visited. Callers that need to know what the record supports want
    `measured_live_directions` or `connection_status` instead; callers that want
    to propose candidates for rendering want this.

    Survived 14 forward-predicted cells across the 2026-08-21 edge and interior
    runs, at two starter positions no sweep had used, with zero misses.
    """
    return plate_available_directions(layer_kind, starter_local_pos) & starter_world_ports(
        starter_rot
    )


def live_directions(starter_rot: int) -> frozenset[int]:
    """The measured live directions at the plate corner, BASE_LAYER_PIECE local (0, 0).

    Refuses rotations outside the swept range rather than guessing. Note the
    coordinate in the signature's absence: this answers for the corner only,
    which is exactly what the pre-2026-08-21 version of this function claimed
    for every position on the plate.
    """
    try:
        return MEASURED_LIVE_DIRECTIONS[starter_rot]
    except KeyError:
        raise UnsweptStarterRotationError(starter_rot) from None


def measured_run(
    starter_rot: int, *, layer_kind: LayerKind, starter_local_pos: HexVector
) -> MeasuredRun | None:
    """The rendered run covering this starter placement, or None if none does."""
    key = (starter_local_pos.y, starter_local_pos.x)
    for run in MEASURED_RUNS:
        if (
            run.layer_kind is layer_kind
            and run.starter_local_pos == key
            and run.starter_rot == starter_rot
        ):
            return run
    return None


def measured_live_directions(
    starter_rot: int, *, layer_kind: LayerKind, starter_local_pos: HexVector
) -> frozenset[int] | None:
    """The live directions a render measured here, or None if none has."""
    run = measured_run(
        starter_rot, layer_kind=layer_kind, starter_local_pos=starter_local_pos
    )
    return None if run is None else run.live_directions


class ConnectionStatus(Enum):
    """What the measured record lets us claim about one starter/goal pair."""

    CONNECTED = auto()
    DISCONNECTED = auto()
    UNMEASURED = auto()


def connection_status(
    starter_rot: int,
    direction: int,
    goal_rotation: int,
    *,
    layer_kind: LayerKind,
    starter_local_pos: HexVector,
) -> ConnectionStatus:
    """Classify one cell against the rendered record.

    `layer_kind` and `starter_local_pos` are required, deliberately. Their
    absence is what made this function wrong between 2026-08-10 and 2026-08-21:
    it answered for the plate corner and applied that answer everywhere, so a
    valid course whose starter sat elsewhere could be called DISCONNECTED at
    ERROR severity. A default here would restore exactly that.

    CONNECTED and DISCONNECTED are claimed only inside a `MeasuredRun`'s
    coverage. Everything else is UNMEASURED -- including configurations the
    conjunction confidently predicts, which is the point of keeping
    `predict_connection` on a separate surface.
    """
    if not 0 <= direction <= 5:
        raise ValueError(f"direction must be 0..5, got {direction}")
    run = measured_run(
        starter_rot, layer_kind=layer_kind, starter_local_pos=starter_local_pos
    )
    if run is None:
        return ConnectionStatus.UNMEASURED
    at_connecting_rotation = goal_rotation == goal_rotation_for(direction)
    if not (run.goal_rotations_swept or at_connecting_rotation):
        return ConnectionStatus.UNMEASURED
    if at_connecting_rotation and direction in run.live_directions:
        return ConnectionStatus.CONNECTED
    return ConnectionStatus.DISCONNECTED


def predict_connection(
    starter_rot: int,
    direction: int,
    goal_rotation: int,
    *,
    layer_kind: LayerKind,
    starter_local_pos: HexVector,
) -> bool:
    """Whether the conjunction predicts this cell connects. A model, not a claim.

    Two-valued on purpose: a model has an opinion everywhere, and pretending
    otherwise would blur the line this module exists to keep sharp. Use
    `connection_status` for what the renders actually support.
    """
    if not 0 <= direction <= 5:
        raise ValueError(f"direction must be 0..5, got {direction}")
    if goal_rotation != goal_rotation_for(direction):
        return False
    return direction in predicted_live_directions(
        starter_rot, layer_kind=layer_kind, starter_local_pos=starter_local_pos
    )


@dataclass(frozen=True, slots=True)
class PlacedTile:
    """One tile with its world position -- the node type of the track graph.

    Carries `local_pos` and `layer_kind` alongside `world_pos` because plate
    membership is defined in a layer's local frame against a per-kind
    footprint. The pre-2026-08-21 version kept only `world_pos` and was
    therefore lossy for precisely the coordinate that decides connection.
    """

    kind: TileKind
    world_pos: HexVector
    local_pos: HexVector
    hex_rotation: int
    layer_id: int
    layer_kind: LayerKind


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
                    local_pos=cell.local_hex_position,
                    hex_rotation=node.construction_data.hex_rotation,
                    layer_id=layer.layer_id,
                    layer_kind=layer.layer_kind,
                )
                stack.extend(node.children)


def classify_pair(starter: PlacedTile, goal: PlacedTile) -> ConnectionStatus:
    """Classify one placed starter/goal pair against the rendered record.

    Cross-layer pairs are UNMEASURED: every measurement to date sits on a
    single BASE_LAYER_PIECE layer.

    Non-adjacent same-layer pairs are DISCONNECTED, on the **mechanism**: the
    rail-free connection is tile adjacency with `rail_count = 0`, so there is
    nothing to carry a connection across a gap. This module used to cite the
    sweeps' distance-2 far controls as the evidence for that, and it should
    not have -- `FAR_CONTROL_POS = (0, 2)` is itself off the measured plate
    footprint, so those controls measured cell invalidity rather than distance
    (`plan.md`, sequenced item 2). The conclusion stands on the mechanism; the
    citation was withdrawn 2026-08-21 and an on-plate distance-2 control is
    owed before the empirical version of this claim is made.
    """
    if starter.layer_id != goal.layer_id:
        return ConnectionStatus.UNMEASURED
    direction = starter.world_pos.direction_to(goal.world_pos)
    if direction is None:
        return ConnectionStatus.DISCONNECTED
    return connection_status(
        starter.hex_rotation,
        direction,
        goal.hex_rotation,
        layer_kind=starter.layer_kind,
        starter_local_pos=starter.local_pos,
    )


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
