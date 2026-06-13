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

from traxgen.domain import (
    CellConstructionData,
    Course,
    CourseMetaData,
    LayerConstructionData,
    SaveDataHeader,
    TileTowerConstructionData,
    TileTowerTreeNodeData,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET, Inventory
from traxgen.types import (
    CourseElementGeneration,
    CourseKind,
    CourseSaveDataVersion,
    LayerKind,
    ObjectiveKind,
    TileKind,
)

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
