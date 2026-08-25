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

from traxgen.hex import HEX_DIRECTIONS, HexVector
from traxgen.inventory import PIECE_CATALOG
from traxgen.plates import BASEPLATE_LAYER_KINDS, plate_available_directions
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

    `directions_probed` is which of the six directions the run actually
    rendered, and it is a **different question** from `goal_rotations_swept`.
    That flag records rotation coverage within a direction; this records
    coverage across directions. Every campaign to date probed all six -- the
    corner sweeps by being exhaustive 36-cell grids, the three probe runs
    because `probe_plate_membership.build_cells` emits a cell for every
    direction regardless of which ones the model expects to be live. So adding
    this field moved no verdict, and that is exactly why it is worth stating
    rather than leaving implied: the first run that probes *fewer* than six is
    the #17 2x2, where a single cell is rendered on a plate layout nothing has
    measured. Without this term that run would have to be recorded as a
    six-direction result, asserting five verdicts it never measured -- the s21
    / s24 / s25 defect family a fourth time, in the record rather than in a
    guard.

    Note the fixture hazard this creates and does not solve (observations #26):
    every row below carries the identical value, so the field is a shared
    coincidence across the whole record. `tests/test_graph.py` therefore builds
    a partial-coverage run of its own rather than relying on these rows, and
    the gate in `connection_status` is mutation-checked against it.

    `goal_layer_kind` and `goal_plate_offset` say **where the goal stood**, and
    they are two terms rather than one for a reason worth stating. Together they
    make the goal side symmetric with the starter side, which has keyed on
    `layer_kind` plus `starter_local_pos` since s22: a campaign is identified by
    what kind of layer each tile stood on and where that layer sat.

    Until s27 the goal side had no terms at all. `classify_pair` instead
    *refused* any pair whose tiles sat on different layers, which is why arm 1
    of the #17 2x2 -- goal on a neighbouring plate -- had nowhere to be written
    down even after s25 made arm 2 recordable. Replacing that refusal with key
    terms is the same move s25 made for the plate set and s22 for the starter
    position: a term the configuration silently supplied becomes part of the
    key, and the verdict for an unmeasured shape becomes a consequence rather
    than a rule.

    **`goal_plate_offset` is `None` when the goal stood on the starter's own
    layer**, and a coordinate only when it stood on a different one. That is a
    sum type rather than a zero vector, and the difference is not cosmetic: two
    distinct layers can sit at the *same* world position, so `(0, 0)` cannot
    mean both "the same layer" and "a different layer that happens to coincide".
    Keying on the coordinate alone was the first implementation and an existing
    test refuted it by enactment -- `test_a_cross_layer_pair_is_unmeasured`
    builds exactly that degenerate course and it flipped UNMEASURED to
    CONNECTED. This is s25's set-versus-tuple lock one level over: a positional
    key collapses multiplicity, and `layout.build_course` refuses to emit such a
    course while the **parser** will happily read one.

    **Why the kind term is not redundant.** Dropping the cross-layer refusal in
    favour of an offset alone opens a hole the refusal was closing by accident:
    a goal on a *non-baseplate* layer -- `LARGE_LAYER` or `SMALL_LAYER`, both
    present in the committed `GDZJZA3J3T` fixture -- computes an offset like any
    other, and a layer sitting at the starter's plate position would give
    `(0, 0)` and match a row. The record would then answer about a pair spanning
    a baseplate and something that is not a plate. Keying on the kind makes that
    course miss the record instead, with no rule written anywhere.

    One alternative was considered and refused: resolving the goal's plate with
    `layout.owning_plate`, which answers "which baseplate covers this world
    cell" and raises on ambiguity. The import direction allows it (`layout` does
    not import this module). It is refused because it answers a *different*
    question -- a tile on a raised `LARGE_LAYER` sits above a baseplate without
    standing on it, and resolving it to the plate beneath would smuggle that
    equivalence into the record as if a render had established it.

    Broken window, named rather than fixed here: `layer_kind` is the *starter's*
    and now sits beside `goal_layer_kind`, which reads worse than it should.
    Renaming it `starter_layer_kind` is mechanical and touches `measured_run`,
    `connection_status`, `measured_live_directions` and every caller, so it
    belongs in its own pass rather than inside a change about the goal side.

    `plate_offsets` is where every baseplate in the rendered course sat
    **relative to the starter's own plate** -- the precondition all nine
    campaigns carried and none recorded until 2026-08-24 (s25). Every one of
    them was built by a sweep helper that copies `layer_construction_data[0]`
    and returns a 1-tuple, so each ran on exactly one plate and the starter
    stood on it: `((0, 0),)`. Two helpers, not one -- the 2026-08-07 campaign
    predates `scripts/sweep_starter_rotation.build_variant` (first committed
    `32d6078`, 2026-08-09) and was built by `sweep_goal_rotation._goal_variant`
    at `8929ad0`, which ends in the same 1-tuple. Until this field existed that
    fact lived only in those builders, and `start_goal_status` reproduced it by
    *counting* baseplates and refusing above one.

    Recording it instead of counting it is the difference between a special
    case and a lookup key. A course whose plate layout is not in the record now
    misses the record, so multi-plate falls to UNMEASURED because nothing
    measured it -- not because a guard was written to say so. It also closes a
    hole the counting version had: that guard counted `BASE_LAYER_PIECE` alone
    while `plates.BASEPLATE_LAYER_KINDS` (and the validator) count `BASE_LAYER`
    too, so the certified course plus one empty `BASE_LAYER` returned CONNECTED
    from a single-plate record. Same shape as s22 making `starter_local_pos`
    required with no default: the term that was silently absorbed becomes part
    of the key.

    **Offsets rather than absolute world positions**, for a reason that is a
    claim about the model and is spelled out on `plate_offsets_from`: absolute
    keying would refuse a course that is a pure translation of a measured one,
    and the suite contains exactly that course as the s22 moved-board fixture.

    A **sorted tuple**, not a set. Sorted so that order is not a degree of
    freedom a consumer can depend on untested (the s24 reordering defect,
    observations #30, one module over). A tuple rather than a `frozenset` so
    that two plates at one position stay two plates: a set would collapse them
    and hand a degenerate course the single-plate record's answer, which is the
    same latent hole this field exists to close, one shape over.
    `plate_offsets_from` is what produces the canonical form; a caller that
    hand-writes an unsorted one gets a mismatch, which is a false UNMEASURED
    and therefore the safe direction to fail in.
    """

    layer_kind: LayerKind
    starter_local_pos: tuple[int, int]
    starter_rot: int
    live_directions: frozenset[int]
    directions_probed: frozenset[int]
    goal_rotations_swept: bool
    plate_offsets: tuple[tuple[int, int], ...]
    goal_layer_kind: LayerKind
    goal_plate_offset: tuple[int, int] | None
    provenance: str

    def __post_init__(self) -> None:
        unprobed_but_live = self.live_directions - self.directions_probed
        if unprobed_but_live:
            raise ValueError(
                f"live_directions {sorted(unprobed_but_live)} are not in "
                f"directions_probed {sorted(self.directions_probed)} -- a "
                "direction cannot render active in a run that never rendered it"
            )


# The plate layout every rendered campaign to date actually had: the starter's
# own plate and nothing else. Named once rather than repeated across the nine
# rows below, and pinned by a test that builds a real `build_variant` course
# and reads its layout back through `plate_offsets_from` -- so this constant is
# graded against the builder rather than against itself (observations #12).
STARTER_PLATE_ONLY: tuple[tuple[int, int], ...] = ((0, 0),)


# What every campaign to date probed: all six directions. Named once rather
# than repeated across the rows below, and derived from the direction space
# rather than typed as `{0,1,2,3,4,5}`, so it cannot drift from `HEX_DIRECTIONS`
# if the hex model ever gains or loses a direction.
ALL_DIRECTIONS: frozenset[int] = frozenset(range(len(HEX_DIRECTIONS)))



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
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=True,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
        provenance="2026-08-07 36-cell sweep + 2026-08-08 NW-rot-0 backfill",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=1,
        live_directions=frozenset({1}),  # NE
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=True,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
        provenance="2026-08-08 full sweep -- exactly one live cell in 36",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=2,
        live_directions=frozenset({0, 2}),  # E, NW
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=True,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
        provenance="2026-08-10 queue run; one 520'd upload closed by auto-resume",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=3,
        live_directions=frozenset({1}),  # NE
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=True,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
        provenance="2026-08-10 queue run",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=4,
        live_directions=frozenset({0, 2}),  # E, NW
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=True,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
        provenance="2026-08-10 queue run; one frame-guard hole closed by auto-resume",
    ),
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 0),
        starter_rot=5,
        live_directions=frozenset({1}),  # NE
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=True,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
        provenance="2026-08-10 queue run",
    ),
    # The two runs that found the missing coordinate. Both declared every
    # cell's verdict in code before rendering (`decisions.md` 2026-08-08).
    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 1),
        starter_rot=0,
        live_directions=frozenset({2}),  # NW alone
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=False,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
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
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=False,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
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
        directions_probed=ALL_DIRECTIONS,
        goal_rotations_swept=False,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=None,  # the goal stood on the starter's own layer
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
        # Currently unexercised, and said out loud rather than left to look
        # like coverage: every row carries the same layout, so this clause is
        # universally true today and deleting it changes nothing (proven by
        # mutation). It becomes load-bearing the moment a multi-plate campaign
        # is recorded at the corner with goal rotations swept -- which is what
        # the #17 2x2 will do -- and it is a corner-table filter, so it belongs
        # beside the coordinate filter above rather than added later.
        and run.plate_offsets == STARTER_PLATE_ONLY
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

    **Takes no plate-set term, and that is a scope statement rather than an
    omission.** `plate_available_directions` reads the footprint of the
    starter's own layer, so this predicts for a cell on one plate. Whether a
    neighbouring plate makes an otherwise-off-plate cell available is open
    unknown #17 -- the thing the 2x2 exists to render -- so a plate-set
    argument here would have to encode an answer nobody has. On a multi-plate
    course this function still returns a set; it is the single-plate model's
    set, and the claim surface holds such courses at UNMEASURED precisely
    because this is not known to be the right answer there.
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
    starter_rot: int,
    *,
    layer_kind: LayerKind,
    starter_local_pos: HexVector,
    plate_offsets: tuple[tuple[int, int], ...],
    goal_layer_kind: LayerKind,
    goal_plate_offset: tuple[int, int] | None,
) -> MeasuredRun | None:
    """The rendered run covering this placement, or None if none does.

    `plate_offsets` is part of the key, not a filter applied afterwards. A
    course whose plates sit differently *around the starter* than any rendered
    campaign's simply has no covering run, which is what makes multi-plate
    UNMEASURED without a rule that says so.

    The two goal terms work the same way and replaced a refusal (s27). A goal on
    a neighbouring plate, or on a layer that is not a baseplate at all, now
    misses the record rather than being turned away by `classify_pair` before
    the key was built -- which is why arm 1 of the #17 2x2 is expressible here
    and was not before.
    """
    key = (starter_local_pos.y, starter_local_pos.x)
    for run in MEASURED_RUNS:
        if (
            run.layer_kind is layer_kind
            and run.starter_local_pos == key
            and run.starter_rot == starter_rot
            and run.plate_offsets == plate_offsets
            and run.goal_layer_kind is goal_layer_kind
            and run.goal_plate_offset == goal_plate_offset
        ):
            return run
    return None


def measured_live_directions(
    starter_rot: int,
    *,
    layer_kind: LayerKind,
    starter_local_pos: HexVector,
    plate_offsets: tuple[tuple[int, int], ...],
    goal_layer_kind: LayerKind,
    goal_plate_offset: tuple[int, int] | None,
) -> frozenset[int] | None:
    """The live directions a render measured here, or None if none has.

    Takes the goal terms too, which reads as overreach for a question phrased
    about the starter -- and is not. `goal_plate_offset` is a property of the
    *campaign*: every cell in a 36-cell sweep put its goal on the starter's own
    plate, and arm 1 of the #17 2x2 will put it on a neighbour. Two campaigns
    can share a starter placement and differ in that, so a lookup without the
    term would have to pick one silently. Defaulting it to the same-plate value
    is exactly the absorbed-precondition failure the last three sessions fixed
    three times over.
    """
    run = measured_run(
        starter_rot,
        layer_kind=layer_kind,
        starter_local_pos=starter_local_pos,
        plate_offsets=plate_offsets,
        goal_layer_kind=goal_layer_kind,
        goal_plate_offset=goal_plate_offset,
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
    plate_offsets: tuple[tuple[int, int], ...],
    goal_layer_kind: LayerKind,
    goal_plate_offset: tuple[int, int] | None,
) -> ConnectionStatus:
    """Classify one cell against the rendered record.

    `layer_kind`, `starter_local_pos`, `plate_offsets`, `goal_layer_kind` and
    `goal_plate_offset` are required, all five deliberately and all five for the
    same reason: each was once a term this function silently absorbed from the
    configuration that happened to be rendered.

    The first two were absorbed between 2026-08-10 and 2026-08-21 -- it answered
    for the plate corner and applied that answer everywhere, so a valid course
    whose starter sat elsewhere could be called DISCONNECTED at ERROR severity.
    `plate_offsets` was absorbed until 2026-08-24: every campaign ran on the
    starter's plate and no other, and nothing recorded it, so a four-plate
    course was answered from a single-plate record. A default on any of the
    three restores the corresponding defect, which is why none has one.

    CONNECTED and DISCONNECTED are claimed only inside a `MeasuredRun`'s
    coverage. Everything else is UNMEASURED -- including configurations the
    conjunction confidently predicts, which is the point of keeping
    `predict_connection` on a separate surface.
    """
    if not 0 <= direction <= 5:
        raise ValueError(f"direction must be 0..5, got {direction}")
    run = measured_run(
        starter_rot,
        layer_kind=layer_kind,
        starter_local_pos=starter_local_pos,
        plate_offsets=plate_offsets,
        goal_layer_kind=goal_layer_kind,
        goal_plate_offset=goal_plate_offset,
    )
    if run is None:
        return ConnectionStatus.UNMEASURED
    # Direction coverage before rotation coverage, and both before any verdict.
    # A direction the run never rendered has no rotation of it measured either,
    # so this is the outermost of the two gates -- and the level a guard sits at
    # is part of the guard (`decisions.md`, s25). Putting it below the rotation
    # check would leave it unreached for a probe run's non-connecting rotations,
    # which is the narrowing that reopened the s24 defect one session later.
    if direction not in run.directions_probed:
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

    Carries `predicted_live_directions`' scope, since it is that function plus
    the goal-side rule: **no plate-set term**, so on a multi-plate course this
    answers from the starter's own plate footprint alone. That is the
    single-plate model applied to a case open unknown #17 has not decided.
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


def plate_offsets_from(
    plate_positions: tuple[tuple[int, int], ...], starter: PlacedTile
) -> tuple[tuple[int, int], ...]:
    """`plate_positions` rebased so the starter's own plate sits at (0, 0).

    The starter's plate is `world_pos - local_pos`, which is its layer's
    `world_hex_position` recovered from the tile rather than passed alongside
    it.

    **Why the record keys on offsets and not on absolute world positions.**
    Absolute keying would be the literal reading of "record what the campaign
    ran on", and it is wrong here for a reason worth stating: it would hold a
    course that is a pure *translation* of a measured one at UNMEASURED, and
    the suite already contains that course. The s22 moved-board fixture
    translates the certified interior geometry to world (3, -2) specifically so
    that a bug reading world coordinates where board coordinates belong lands
    the starter on the measured-dead corner (observations #26). Under absolute
    keying both the honest reading and that bug return UNMEASURED, so the test
    stops discriminating and the blind spot s22 closed quietly reopens.

    The assumption this makes explicit rather than introduces: **the absolute
    world offset of the whole course does not affect connection.** No render has
    tested it -- every campaign to date sits at world (0, 0) -- but the shipped
    model has always claimed it, since `connection_status` is a function of
    local position and rotation and never sees a world coordinate at all.
    Naming it here is the point: it was a precondition nobody had written down,
    which is the same thing the plate set itself was until this session.
    """
    origin = starter.world_pos - starter.local_pos
    return tuple(sorted((y - origin.y, x - origin.x) for y, x in plate_positions))


def goal_plate_offset_from(starter: PlacedTile, goal: PlacedTile) -> tuple[int, int]:
    """Where the goal's layer sat, relative to the starter's own plate.

    Same convention and the same recovery trick as `plate_offsets_from`: a
    tile's layer origin is `world_pos - local_pos`, read off the tile rather
    than passed alongside it. `(0, 0)` means both tiles stood on the same layer,
    which every campaign to date did and which is why the term was invisible
    until something needed to say otherwise.

    Deliberately *not* "which baseplate covers the goal's world cell". That is
    `layout.owning_plate`'s question and a different one -- see `MeasuredRun`.
    """
    if starter.layer_id == goal.layer_id:
        return None
    starter_origin = starter.world_pos - starter.local_pos
    goal_origin = goal.world_pos - goal.local_pos
    return (goal_origin.y - starter_origin.y, goal_origin.x - starter_origin.x)


def classify_pair(
    starter: PlacedTile,
    goal: PlacedTile,
    *,
    plate_positions: tuple[tuple[int, int], ...],
) -> ConnectionStatus:
    """Classify one placed starter/goal pair against the rendered record.

    `plate_positions` is the course's absolute baseplate positions, a property
    of the *course*, so it is passed in rather than read off either tile.
    Hanging it on `PlacedTile` would copy one fact onto every tile and give
    them a way to disagree; `PlacedTile` carries what varies per tile, and the
    plate layout does not. It is rebased here, per starter, by
    `plate_offsets_from` -- see there for why the record keys on offsets.

    **Where the goal stood is a key term, not a refusal (s27).** This function
    used to turn away any pair whose tiles sat on different layers, before the
    key was built -- so arm 1 of the #17 2x2, whose goal is on a neighbouring
    plate, could be rendered and had nowhere to be recorded. Now the goal's
    layer kind and its plate offset go into the lookup, and a configuration
    nothing has measured misses the record on its own. The verdict for every
    shape that exists today is unchanged: no row carries a non-zero goal offset
    or a non-baseplate goal kind, so cross-layer pairs still come back
    UNMEASURED -- as a consequence rather than a rule.

    **The record is consulted before any claim is made, including the
    adjacency one.** That ordering is the whole fix and it is easy to get
    wrong -- this function got it wrong for the length of one session. The
    non-adjacency verdict rests on the *mechanism* rather than on a rendered
    cell, which makes it feel safe to answer early; but `DISCONNECTED` is a
    claim like any other, and answering it before the plate layout enters the
    key means a four-plate course nobody has rendered gets told, at ERROR
    severity, that its pair was measured disconnected. s24 was safe from this
    only by accident of level: its baseplate count sat in `start_goal_status`,
    *above* the short-circuit. Replacing that count with a lookup moved the
    guard below it and reopened the hole for every non-adjacent pair -- caught
    by an adversarial panel, not by the suite, because the one multi-plate
    fixture happened to use an adjacent goal (`tests/test_layout.py`).

    So: no covering run, no verdict. Where a run does cover the placement, the
    non-adjacent answer is DISCONNECTED on the **mechanism** -- the rail-free
    connection is tile adjacency with `rail_count = 0`, so there is nothing to
    carry a connection across a gap. This module used to cite the sweeps'
    distance-2 far controls as the evidence for that, and it should not have --
    `FAR_CONTROL_POS = (0, 2)` is itself off the measured plate footprint, so
    those controls measured cell invalidity rather than distance (`plan.md`,
    sequenced item 2). The conclusion stands on the mechanism; the citation was
    withdrawn 2026-08-21 and an on-plate distance-2 control is owed before the
    empirical version of this claim is made.
    """
    plate_offsets = plate_offsets_from(plate_positions, starter)
    goal_offset = goal_plate_offset_from(starter, goal)
    if (
        measured_run(
            starter.hex_rotation,
            layer_kind=starter.layer_kind,
            starter_local_pos=starter.local_pos,
            plate_offsets=plate_offsets,
            goal_layer_kind=goal.layer_kind,
            goal_plate_offset=goal_offset,
        )
        is None
    ):
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
        plate_offsets=plate_offsets,
        goal_layer_kind=goal.layer_kind,
        goal_plate_offset=goal_offset,
    )


def course_plate_positions(course: Course) -> tuple[tuple[int, int], ...]:
    """The world `(y, x)` of every baseplate layer in `course`, sorted.

    "Baseplate" here means `plates.BASEPLATE_LAYER_KINDS` -- both `BASE_LAYER`
    and `BASE_LAYER_PIECE`, the classification locked at `b8052e4` and shared
    with the validator. This module previously counted `BASE_LAYER_PIECE`
    alone, which let a two-baseplate course through the multi-plate guard when
    its second plate was a `BASE_LAYER`: measured on the certified course plus
    one empty extra layer, which returned CONNECTED.

    `BASE_LAYER` appears in **zero** of the 640 parsed corpus courses -- not
    zero cells, zero layers -- so the hole was latent rather than live.
    Regenerate with `scripts/probe_plate_arrangement.py`, whose `kind=` tallies
    exist because this sentence had no producer when it was first written: the
    footprint probe counts kinds only from within `cell_construction_datas`, so
    an **empty** layer, which is precisely the shape at issue, was invisible to
    it (observations #24). And "never observed in 640" is not "cannot occur",
    which is the whole reason to key off the shared classification rather than
    the narrower one.

    Positions, not a count: what the record needs to know is *which* plates,
    and reducing that to a number is what turned a lookup into a special case.
    Sorted so the result is canonical regardless of layer order, and kept as a
    tuple rather than a set so two plates at one world position stay two
    entries -- `build_course` refuses to emit that and the corpus has never
    contained it (zero footprint collisions across 640 courses, which two
    plates at one position could not survive), but the parser will read one, and
    collapsing it here would answer a course no run has measured.
    """
    return tuple(
        sorted(
            (layer.world_hex_position.y, layer.world_hex_position.x)
            for layer in course.layer_construction_data
            if layer.layer_kind in BASEPLATE_LAYER_KINDS
        )
    )


def start_goal_status(course: Course) -> ConnectionStatus | None:
    """The best connection status over every starter/goal pair, or None if
    the course has no starter or no goal (that absence is
    MISSING_STARTER_OR_GOAL's finding, not this module's).

    CONNECTED beats UNMEASURED beats DISCONNECTED: one measured connection
    makes the course connected no matter how many dead pairs surround it, and
    one unmeasured pair keeps "disconnected" from being claimed on evidence
    we do not have.

    **The course's plate layout is part of every pair's lookup key**, because
    `classify_pair` sends only *cross-layer* pairs to UNMEASURED and a
    same-plate pair on a multi-plate course would otherwise be classified
    exactly as on a single-plate one. Every row in `MEASURED_RUNS` was rendered
    through a builder that emits exactly one layer (`build_variant`, and
    `_goal_variant` before it -- both 1-tuples), so "one plate at world (0,0)"
    was an unrecorded precondition on all nine campaigns --
    unreachable until `traxgen/layout.py` made multi-plate courses buildable,
    and a false ERROR the moment it was reachable.

    That false ERROR landed on the exact arm the #17 2x2 exists to render: four
    plates, starter at home-plate local (0,0), goal at the out-of-window W cell.
    Claiming "measured disconnected" there asserts one reading of open unknown
    #17 -- that adding a plate changes nothing -- as a harness finding. That is
    the s21 defect one level up (an answer measured in one configuration,
    applied to another) and it is what the 2026-08-10 severity lock forbids: a
    gap in the record must not become a claim about the course.

    s24 closed it by counting baseplates here and refusing above one. This
    function no longer counts anything. `MeasuredRun.plate_offsets` records
    what each campaign ran on, so a multi-plate course simply has no covering
    run and every pair comes back UNMEASURED on its own. The behaviour is the
    same everywhere the suite looked, and the reason is different, which
    matters in two measurable ways -- one in each direction.

    Tighter: the count was over `BASE_LAYER_PIECE` alone, so the certified
    course plus one empty `BASE_LAYER` slipped past it and was answered
    CONNECTED from the single-plate record. Deriving the key from
    `plates.BASEPLATE_LAYER_KINDS` removes that kind-specific hole along with
    the special case.

    Looser, and this one was a defect rather than a fix: the count sat *above*
    `classify_pair`'s non-adjacency short-circuit, so it covered every pair,
    while the lookup sits inside `connection_status`, below it. Non-adjacent
    pairs on a multi-plate course were briefly claimed measured-disconnected at
    ERROR severity -- the very thing this rewrite exists to prevent. Found by
    an adversarial panel; fixed by consulting the record before any verdict.
    See `classify_pair`.
    """
    tiles = list(placed_tiles(course))
    starters = [t for t in tiles if t.kind in STARTER_KINDS]
    goals = [t for t in tiles if t.kind in GOAL_KINDS]
    if not starters or not goals:
        return None
    plate_positions = course_plate_positions(course)
    statuses = {
        classify_pair(s, g, plate_positions=plate_positions)
        for s in starters
        for g in goals
    }
    for status in (
        ConnectionStatus.CONNECTED,
        ConnectionStatus.UNMEASURED,
        ConnectionStatus.DISCONNECTED,
    ):
        if status in statuses:
            return status
    raise AssertionError("unreachable: statuses is non-empty")
