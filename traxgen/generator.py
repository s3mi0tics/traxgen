"""Minimal generator for GraviTrax courses.

M5.b-minimal: produces the smallest possible Course that passes
validate_strict against the PRO Vertical Starter-Set inventory.

Shape: one BASE_LAYER_PIECE at world (0,0), one STARTER at local (0,0),
one GOAL_RAIL at local (0,1), one STRAIGHT rail between them. Empty
pillars/walls. GUID=0 (M6 follow-up). No physics, no graph, no
aesthetics. Proves the pipeline end-to-end.

Path: traxgen/traxgen/generator.py
"""

from __future__ import annotations

from traxgen.domain import (
    CellConstructionData,
    Course,
    CourseMetaData,
    LayerConstructionData,
    RailConstructionData,
    RailConstructionExitIdentifier,
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
    RailKind,
    TileKind,
)

# Single layer's retainer ID. Arbitrary; any non-colliding value works.
_LAYER_ID = 100


def _make_tile(kind: TileKind) -> TileTowerTreeNodeData:
    """Build a single-tile tree node at rotation 0, no stackers, no retainer."""
    return TileTowerTreeNodeData(
        index=0,
        construction_data=TileTowerConstructionData(
            kind=kind,
            height_in_small_stacker=0,
            hex_rotation=0,
        ),
        children=(),
    )


def _make_cell(kind: TileKind, *, y: int, x: int) -> CellConstructionData:
    """Build a cell at local (y, x) containing a single tile."""
    return CellConstructionData(
        local_hex_position=HexVector(y=y, x=x),
        tree_node_data=_make_tile(kind),
    )


def generate_minimal(inventory: Inventory = PRO_VERTICAL_STARTER_SET) -> Course:
    """Generate the smallest course that passes validate_strict.

    Inventory parameter is accepted for future extension but unused in v1 —
    the minimal course is hardcoded against PRO Vertical's pieces and
    doesn't adapt to the inventory shape.
    """
    # Cells: STARTER at (0,0), GOAL_RAIL at (0,1) — adjacent hexes.
    starter_cell = _make_cell(TileKind.STARTER, y=0, x=0)
    goal_cell = _make_cell(TileKind.GOAL_RAIL, y=0, x=1)

    layer = LayerConstructionData(
        layer_id=_LAYER_ID,
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        layer_height=-0.2,  # Per Rust doc-comment: "-0.2 is the layer height for all base plates"
        world_hex_position=HexVector(y=0, x=0),
        cell_construction_datas=(starter_cell, goal_cell),
    )

    # STRAIGHT rail between the two cells. Distance 1 -> SHORT.
    # side_hex_rot values are placeholder; validator accepts anything in [0,5].
    # Real connection semantics (which hex edge the rail attaches to) are
    # PLAN.md open unknown #2 — to be resolved in M6.
    rail = RailConstructionData(
        exit_1_identifier=RailConstructionExitIdentifier(
            retainer_id=_LAYER_ID,
            cell_local_hex_pos=HexVector(y=0, x=0),
            side_hex_rot=0,
            exit_local_pos_y=0.0,
        ),
        exit_2_identifier=RailConstructionExitIdentifier(
            retainer_id=_LAYER_ID,
            cell_local_hex_pos=HexVector(y=0, x=1),
            side_hex_rot=3,  # opposite edge of target cell; placeholder
            exit_local_pos_y=0.0,
        ),
        rail_kind=RailKind.STRAIGHT,
    )

    return Course(
        header=SaveDataHeader(
            guid=0,  # M6 follow-up: app may reject guid=0; try random u128
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
        rail_construction_data=(rail,),
        pillar_construction_data=(),
        generation=CourseElementGeneration.POWER,
        wall_construction_data=(),
    )
