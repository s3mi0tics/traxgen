"""Minimal generator for GraviTrax courses.

M5.b-minimal (corrected): produces the smallest Course the GraviTrax app
accepts as a valid, playable course.

Shape: one BASE_LAYER_PIECE at world (0,0) holding two adjacent tiles —
a STARTER at local (0,0) and a GOAL_RAIL at local (-1,0) (its NW neighbor),
with the goal rotated to 3 so its integrated rail faces the starter. There
is NO explicit rail object.

Why no explicit rail: the 2026-06-12 M6.b breakthrough showed that valid
app-built courses connecting a STARTER to a GOAL_RAIL have `rail_count = 0`.
`GOAL_RAIL` (TileKind 19) is a goal-with-integrated-rail tile; the
connection is made by tile adjacency plus the goal tile's `hex_rotation`,
not by a `RailConstructionData`. The earlier minimal generator emitted a
spurious STRAIGHT rail that never rendered. This shape (STARTER@(0,0) rot 0
+ GOAL_RAIL@(-1,0) rot 3, zero rails) was verified end-to-end: uploaded as
share code FLW4TMLP5V and rendered by the app with an active play button.
See docs/PLAN.md "Rail model breakthrough".

Geometry note: the goal rotation (3) is the value observed in both valid
oracles, which share one geometry (goal NW of starter). The general rule
mapping relative position -> required goal rotation is not yet derived; this
generator hardcodes the one proven-valid geometry.

GUID=0 (M6 follow-up, accepted by the app). No graph, no physics, hardcoded
inventory. Future work: per-mode dispatch via `GenerationMode`.

Path: traxgen/traxgen/generator.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from traxgen.domain import (
    CellConstructionData,
    Course,
    CourseMetaData,
    LayerConstructionData,
    SaveDataHeader,
    TileTowerConstructionData,
    TileTowerTreeNodeData,
)
from traxgen.graph import (
    ConnectionStatus,
    connection_status,
    goal_rotation_for,
    predict_connection,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET, Inventory
from traxgen.layout import TilePlacement, build_course, owning_plate
from traxgen.plates import (
    STANDARD_SQUARE,
    is_buildable_on_plate,
    plate_footprint,
)
from traxgen.types import (
    CourseElementGeneration,
    CourseKind,
    CourseSaveDataVersion,
    LayerKind,
    ObjectiveKind,
    TileKind,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

# Single layer's retainer ID. Arbitrary; any non-colliding value works.
# (Matches the value both valid v7 oracles happen to use.)
_LAYER_ID = 100


def _make_tile(kind: TileKind, *, hex_rotation: int = 0) -> TileTowerTreeNodeData:
    """Build a single-tile tree node at the given rotation, no stackers, no retainer."""
    return TileTowerTreeNodeData(
        index=0,
        construction_data=TileTowerConstructionData(
            kind=kind,
            height_in_small_stacker=0,
            hex_rotation=hex_rotation,
        ),
        children=(),
    )


def _make_cell(
    kind: TileKind, *, y: int, x: int, hex_rotation: int = 0
) -> CellConstructionData:
    """Build a cell at local (y, x) containing a single tile at the given rotation."""
    return CellConstructionData(
        local_hex_position=HexVector(y=y, x=x),
        tree_node_data=_make_tile(kind, hex_rotation=hex_rotation),
    )


def generate_minimal(inventory: Inventory = PRO_VERTICAL_STARTER_SET) -> Course:
    """Generate the smallest course the GraviTrax app accepts as valid.

    Two adjacent tiles, no explicit rail: STARTER at local (0,0) and
    GOAL_RAIL at local (-1,0) (its NW neighbor) rotated to 3 so the goal's
    integrated rail faces the starter. Passes validate_strict against PRO
    Vertical and was verified to render with an active play button in the
    app (share code FLW4TMLP5V).

    Inventory parameter is accepted for future extension but unused in v1 —
    the minimal course is hardcoded against PRO Vertical's pieces and
    doesn't adapt to the inventory shape.
    """
    # STARTER at (0,0); GOAL_RAIL at its NW neighbor (-1,0), rotated so its
    # built-in rail points back toward the starter. The two tiles connect by
    # adjacency — no RailConstructionData. See module docstring.
    starter_cell = _make_cell(TileKind.STARTER, y=0, x=0, hex_rotation=0)
    goal_cell = _make_cell(TileKind.GOAL_RAIL, y=-1, x=0, hex_rotation=3)

    layer = LayerConstructionData(
        layer_id=_LAYER_ID,
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        # The app's own output for this BASE_LAYER_PIECE uses 0.0 (observed in
        # both valid v7 oracles); the proven-valid FLW4TMLP5V replica used 0.0.
        layer_height=0.0,
        world_hex_position=HexVector(y=0, x=0),
        cell_construction_datas=(starter_cell, goal_cell),
    )

    return Course(
        header=SaveDataHeader(
            guid=0,  # accepted by the app (M6.b disproved risk)
            version=CourseSaveDataVersion.POWER_2022,
        ),
        meta_data=CourseMetaData(
            creation_timestamp=0,
            title="traxgen-minimal",
            order_number=-1,  # -1 = unset for user courses
            course_kind=CourseKind.CUSTOM,
            objective_kind=ObjectiveKind.NONE,
            difficulty=0,
            completed=False,
        ),
        layer_construction_data=(layer,),
        rail_construction_data=(),  # no explicit rail: GOAL_RAIL carries its own
        pillar_construction_data=(),
        generation=CourseElementGeneration.POWER,
        wall_construction_data=(),
    )


# --- Multi-plate placement (plan.md item 14) --------------------------------
#
# `generate_minimal()` above emits the one geometry the app has certified, on
# one plate, hardcoded. This surface is the other thing a generator can do:
# *propose* a placement the connection model predicts, on a board of several
# plates, and hand it over labelled as unmeasured.
#
# Why it lives in this module rather than a new one: nothing breaks without a
# new module, and `generator.py` is already "the thing that produces a
# Course". What it gains is a dependency on `graph.py`'s prediction surface,
# which is what a generator is *supposed* to consume -- the claims surface
# stays out, so this file can propose and can never claim.
#
# The s35 ruling (`decisions.md`): the generator may emit anything the model
# predicts, with `measured_only=True` for the conservative mode. A predicted
# course is CONNECTED to nobody until `traxgen.android.render_course` says so;
# `graph.start_goal_status` is what reports that, and it is deliberately not
# consulted here -- a generator that labelled its own output would be a second
# opinion free to drift from the record.


class UnmodelledGoalKindError(ValueError):
    """The caller asked for a goal piece the connection model says nothing about."""

    def __init__(self, kind: TileKind) -> None:
        self.kind = kind
        super().__init__(
            f"{kind.name} is outside the connection model: `predict_connection` "
            "models STARTER -> GOAL_RAIL only and takes no tile kind at all "
            "(decisions.md, s33), so a prediction for it would have nothing "
            "behind it. Ask for GOAL_RAIL, or measure this pairing first."
        )


class NoBuildablePlacementError(LookupError):
    """No cross-plate placement on this board satisfied the constraints."""

    def __init__(
        self, *, measured_only: bool, plate_offsets: tuple[tuple[int, int], ...]
    ) -> None:
        self.measured_only = measured_only
        self.plate_offsets = plate_offsets
        if measured_only:
            why = "no placement on this board is CONNECTED in the rendered record"
            fix = (
                "Drop measured_only to propose one the model predicts, then "
                "render it -- that render is what turns a prediction into a row."
            )
        else:
            why = (
                "the connection model predicts no cross-plate placement on this board"
            )
            fix = "Check the board has two plates whose footprints meet."
        super().__init__(f"{why} (plate offsets {plate_offsets}). {fix}")


@dataclass(frozen=True, slots=True)
class _Placement:
    """One candidate cross-plate geometry, carrying every term the model needs."""

    starter_local: HexVector
    starter_rot: int
    direction: int
    goal_plate_index: int
    goal_local: HexVector
    goal_rot: int
    goal_plate_offset: tuple[int, int]


def _cross_plate_placements(
    plate_positions: Sequence[HexVector],
) -> Iterator[_Placement]:
    """Every cross-plate placement the model predicts live, in a stable order.

    Stable because the order decides which one `generate_multi_plate` returns:
    footprint cells sorted, then starter rotation, then direction. A search
    whose answer depends on set iteration order is a course that changes
    between runs, which no render could be attributed to.

    The starter goes on the first plate by construction; "cross-plate" here
    means the goal's *owning* plate is a different one, resolved through
    `layout.owning_plate` rather than by arithmetic on an index -- that
    function raises rather than guessing when a layout overlaps.
    """
    kind = LayerKind.BASE_LAYER_PIECE
    home = plate_positions[0]
    for cell in sorted(plate_footprint(kind)):
        starter_local = HexVector(y=cell[0], x=cell[1])
        if not is_buildable_on_plate(kind, starter_local):
            continue
        starter_world = home + starter_local
        for starter_rot in range(6):
            # All six directions, deliberately: `predict_connection` below is
            # the *only* gate on whether a direction is live. Pre-filtering by
            # `starter_world_ports` here was a hand-rolled copy of the model's
            # own port term, and it made the model call redundant -- a mutation
            # that deleted `predict_connection` entirely left every test green,
            # because the loop had already enforced what the model was being
            # asked to confirm. The model is the measured, documented surface;
            # the loop must consult it, not restate it (observations #12).
            for direction in range(6):
                owner = owning_plate(plate_positions, starter_world.neighbor(direction))
                if owner is None:
                    continue
                goal_index, goal_local = owner
                if goal_index == 0 or not is_buildable_on_plate(kind, goal_local):
                    continue
                goal_plate = plate_positions[goal_index]
                offset = (goal_plate.y - home.y, goal_plate.x - home.x)
                goal_rot = goal_rotation_for(direction)
                if not predict_connection(
                    starter_rot,
                    direction,
                    goal_rot,
                    layer_kind=kind,
                    starter_local_pos=starter_local,
                    goal_plate_offset=offset,
                ):
                    continue
                yield _Placement(
                    starter_local=starter_local,
                    starter_rot=starter_rot,
                    direction=direction,
                    goal_plate_index=goal_index,
                    goal_local=goal_local,
                    goal_rot=goal_rot,
                    goal_plate_offset=offset,
                )


def generate_multi_plate(
    inventory: Inventory = PRO_VERTICAL_STARTER_SET,
    *,
    plate_offsets: Sequence[tuple[int, int]] = STANDARD_SQUARE,
    goal_kind: TileKind = TileKind.GOAL_RAIL,
    measured_only: bool = False,
) -> Course:
    """Generate a course whose goal sits on a different baseplate than its starter.

    The first placement `_cross_plate_placements` yields, built through
    `layout.build_course`. With `measured_only=True` the search additionally
    requires `graph.connection_status` to answer CONNECTED, which today no
    multi-plate configuration does -- so that mode raises
    `NoBuildablePlacementError` until a render puts a row in the record. That
    is the mode working, not failing.

    Raises `UnmodelledGoalKindError` for any goal but `GOAL_RAIL`: the model
    covers that pairing alone, so predicting for a basin would be inventing a
    claim (`decisions.md`, s33).

    `inventory` is accepted and unused, as in `generate_minimal` -- the board
    and the two pieces are fixed here, and the inventory becomes a real
    parameter when the palette drives the search.
    """
    if goal_kind is not TileKind.GOAL_RAIL:
        raise UnmodelledGoalKindError(goal_kind)
    plate_positions = tuple(HexVector(y=y, x=x) for y, x in plate_offsets)
    if len(plate_positions) < 2:
        raise ValueError(
            f"a cross-plate placement needs at least two plates, got "
            f"{len(plate_positions)}; `generate_minimal()` is the one-plate course"
        )

    home = plate_positions[0]
    record_offsets = tuple(
        sorted((pos.y - home.y, pos.x - home.x) for pos in plate_positions)
    )

    for placement in _cross_plate_placements(plate_positions):
        if measured_only:
            status = connection_status(
                placement.starter_rot,
                placement.direction,
                placement.goal_rot,
                layer_kind=LayerKind.BASE_LAYER_PIECE,
                starter_local_pos=placement.starter_local,
                starter_kind=TileKind.STARTER,
                plate_offsets=record_offsets,
                goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
                goal_plate_offset=placement.goal_plate_offset,
                goal_kind=goal_kind,
            )
            if status is not ConnectionStatus.CONNECTED:
                continue
        return build_course(
            plate_world_positions=plate_positions,
            tiles=(
                TilePlacement(
                    kind=TileKind.STARTER,
                    plate_index=0,
                    local_pos=placement.starter_local,
                    hex_rotation=placement.starter_rot,
                ),
                TilePlacement(
                    kind=goal_kind,
                    plate_index=placement.goal_plate_index,
                    local_pos=placement.goal_local,
                    hex_rotation=placement.goal_rot,
                ),
            ),
            title="traxgen-multi-plate",
        )

    raise NoBuildablePlacementError(
        measured_only=measured_only, plate_offsets=record_offsets
    )
