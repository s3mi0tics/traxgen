"""
Domain dataclasses for parsed GraviTrax courses.

Structures mirror the POWER_2022 (v4) binary format 1:1. Field names match
murmelbahn's JSON dump output so parsed courses can be converted to a dict
and diffed directly against /api/course/{code}/dump for oracle-based testing.

Frozen + slots: immutability protects against accidental mutation during
parse; slots catches typo'd field assignments at construction time and
reduces memory overhead for large courses.

Path: traxgen/traxgen/domain.py
"""

from dataclasses import dataclass

from traxgen.hex import HexVector
from traxgen.types import (
    CourseElementGeneration,
    CourseKind,
    CourseSaveDataVersion,
    LayerKind,
    LightStoneColorMode,
    ObjectiveKind,
    PowerSignalMode,
    RailKind,
    TileKind,
    WallSide,
)


@dataclass(frozen=True, slots=True)
class SaveDataHeader:
    """Binary header: u128 GUID + u32 save version."""
    guid: int
    version: CourseSaveDataVersion


@dataclass(frozen=True, slots=True)
class CourseMetaData:
    """Course metadata: title, creation time, classification."""
    creation_timestamp: int  # u64, ms since epoch
    title: str               # u8 length prefix + UTF-8 bytes
    order_number: int        # s32 (-1 = unset for user courses)
    course_kind: CourseKind
    objective_kind: ObjectiveKind
    difficulty: int          # u32
    completed: bool


@dataclass(frozen=True, slots=True)
class TileTowerConstructionData:
    """One tile's placement data. Optional fields depend on save version."""
    kind: TileKind
    height_in_small_stacker: int     # u32
    hex_rotation: int                # u32, 0-5 for hex rotation steps
    retainer_id: int | None = None   # s32 in binary; sentinel value -> None
    power_signal_mode: PowerSignalMode | None = None       # POWER_2022+
    light_stone_color_mode: LightStoneColorMode | None = None  # LIGHT_STONES_2023


@dataclass(frozen=True, slots=True)
class TileTowerTreeNodeData:
    """Recursive stacking tree node. Children stack physically above parent."""
    index: int                       # u32, cell-local tile index
    construction_data: TileTowerConstructionData
    children: tuple["TileTowerTreeNodeData", ...] = ()


@dataclass(frozen=True, slots=True)
class CellConstructionData:
    """One occupied cell on a layer: position + root of its stacking tree."""
    local_hex_position: HexVector
    tree_node_data: TileTowerTreeNodeData


@dataclass(frozen=True, slots=True)
class RailConstructionExitIdentifier:
    """Identifies one end of a rail by (retainer, cell, hex edge)."""
    retainer_id: int                 # u32, refers to a layer or stacker tower
    cell_local_hex_pos: HexVector
    side_hex_rot: int                # u32, 0-5 = which of 6 hex edges
    exit_local_pos_y: float          # f32, vertical offset on the exit face


@dataclass(frozen=True, slots=True)
class RailConstructionData:
    """A single rail connecting two exits."""
    exit_1_identifier: RailConstructionExitIdentifier
    exit_2_identifier: RailConstructionExitIdentifier
    rail_kind: RailKind
    # Null in POWER_2022 dumps; present in binary only for ZIPLINE_ADDED_2019.
    # Kept here for dict compatibility with dump output.
    materialized: bool | None = None


@dataclass(frozen=True, slots=True)
class PillarConstructionData:
    """Vertical support: connects a lower-layer cell to an upper-layer cell."""
    lower_layer_id: int              # u32
    lower_cell_local_position: HexVector
    upper_layer_id: int              # u32
    upper_cell_local_position: HexVector


@dataclass(frozen=True, slots=True)
class WallCoordinate:
    """Grid coordinate on a PRO wall (column + row)."""
    column: int                      # s32
    row: int                         # s32


@dataclass(frozen=True, slots=True)
class WallBalconyConstructionData:
    """A balcony attached to a PRO wall, optionally holding one cell."""
    retainer_id: int                 # s32
    wall_side: WallSide
    wall_coordinate: WallCoordinate
    cell_construction_data: CellConstructionData | None = None


@dataclass(frozen=True, slots=True)
class WallConstructionData:
    """A PRO wall spanning two stacker towers, with its attached balconies."""
    lower_stacker_tower_1_retainer_id: int       # s32
    lower_stacker_tower_1_local_hex_pos: HexVector
    lower_stacker_tower_2_retainer_id: int       # s32
    lower_stacker_tower_2_local_hex_pos: HexVector
    balcony_construction_datas: tuple[WallBalconyConstructionData, ...]


@dataclass(frozen=True, slots=True)
class LayerConstructionData:
    """One horizontal layer (baseplate or transparent level) with its cells."""
    layer_id: int                    # u32
    layer_kind: LayerKind
    layer_height: float              # f32
    world_hex_position: HexVector    # schema calls this 'hex_vector'; dump uses this name
    cell_construction_datas: tuple[CellConstructionData, ...]


@dataclass(frozen=True, slots=True)
class Course:
    """Top-level parsed course. This is what the parser returns."""
    header: SaveDataHeader
    meta_data: CourseMetaData
    layer_construction_data: tuple[LayerConstructionData, ...]
    rail_construction_data: tuple[RailConstructionData, ...]
    pillar_construction_data: tuple[PillarConstructionData, ...]
    generation: CourseElementGeneration
    wall_construction_data: tuple[WallConstructionData, ...]
