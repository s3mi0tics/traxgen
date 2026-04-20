"""
Binary serializer for GraviTrax .course files.

Inverse of parser.py. For every parse_* function there is a serialize_*
function that writes the same bytes back. Version gating and sentinel
patterns mirror the parser exactly so serialize(parse(bytes)) == bytes.

See parser.py's module docstring for the wire format notes.

Path: traxgen/traxgen/serializer.py
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from traxgen.domain import (
    CellConstructionData,
    Course,
    CourseMetaData,
    LayerConstructionData,
    PillarConstructionData,
    RailConstructionData,
    RailConstructionExitIdentifier,
    SaveDataHeader,
    TileTowerConstructionData,
    TileTowerTreeNodeData,
    WallBalconyConstructionData,
    WallConstructionData,
    WallCoordinate,
)
from traxgen.hex import HexVector
from traxgen.types import CourseSaveDataVersion


# Null / unset sentinels — must match parser.py exactly.
_RETAINER_ID_NULL_SENTINEL = -2147483647
_POWER_SIGNAL_NONE_SENTINEL = 0x80000000
_LIGHT_STONE_COLOR_NONE_SENTINEL = 0x80000000

_POWER_SIGNAL_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.POWER_2022,
    CourseSaveDataVersion.LIGHT_STONES_2023,
})
_LIGHT_STONE_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.LIGHT_STONES_2023,
})
_RAIL_EXIT_POS_Y_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.PRO_2020,
    CourseSaveDataVersion.POWER_2022,
    CourseSaveDataVersion.LIGHT_STONES_2023,
})
_RAIL_MATERIALIZED_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.ZIPLINE_ADDED_2019,
})


@dataclass
class Writer:
    """Appends to a bytearray via little-endian primitive writes. Mirrors Reader."""

    buf: bytearray = field(default_factory=bytearray)

    def write_u8(self, v: int) -> None:
        """Write one unsigned byte."""
        self.buf.append(v & 0xFF)

    def write_u32(self, v: int) -> None:
        """Write a little-endian u32."""
        self.buf.extend(struct.pack("<I", v))

    def write_s32(self, v: int) -> None:
        """Write a little-endian s32."""
        self.buf.extend(struct.pack("<i", v))

    def write_u64(self, v: int) -> None:
        """Write a little-endian u64."""
        self.buf.extend(struct.pack("<Q", v))

    def write_u128(self, v: int) -> None:
        """Write a little-endian u128 — inverse of Reader.read_u128."""
        self.buf.extend(v.to_bytes(16, "little"))

    def write_f32(self, v: float) -> None:
        """Write a little-endian f32."""
        self.buf.extend(struct.pack("<f", v))

    def write_bool(self, v: bool) -> None:
        """Write a u8 bool. No alignment padding follows — matches Reader.read_bool."""
        self.buf.append(1 if v else 0)

    def write_string(self, s: str) -> None:
        """Write a u8-length-prefixed UTF-8 string."""
        b = s.encode("utf-8")
        if len(b) > 0xFF:
            raise ValueError(
                f"string of {len(b)} UTF-8 bytes exceeds u8 length prefix limit (255)"
            )
        self.write_u8(len(b))
        self.buf.extend(b)

    def write_hex_vector(self, h: HexVector) -> None:
        """Write a HexVector: two s32 in (y, x) order."""
        self.write_s32(h.y)
        self.write_s32(h.x)


def serialize_header(w: Writer, header: SaveDataHeader) -> None:
    """Write u128 GUID + u32 save version."""
    w.write_u128(header.guid)
    w.write_u32(header.version.value)


def serialize_meta_data(w: Writer, meta: CourseMetaData) -> None:
    """Write course metadata. Mirrors parse_meta_data exactly."""
    w.write_u64(meta.creation_timestamp)
    w.write_string(meta.title)
    w.write_s32(meta.order_number)
    w.write_u32(meta.course_kind.value)
    w.write_u32(meta.objective_kind.value)
    w.write_s32(meta.difficulty)
    w.write_bool(meta.completed)


def serialize_construction_data(
    w: Writer,
    version: CourseSaveDataVersion,
    tc: TileTowerConstructionData,
) -> None:
    """Write one tile's placement data. Version gates mirror parser."""
    w.write_u32(tc.kind.value)
    w.write_s32(tc.height_in_small_stacker)
    w.write_s32(tc.hex_rotation)
    w.write_s32(
        _RETAINER_ID_NULL_SENTINEL if tc.retainer_id is None else tc.retainer_id
    )
    if version in _POWER_SIGNAL_VERSIONS:
        w.write_u32(
            _POWER_SIGNAL_NONE_SENTINEL
            if tc.power_signal_mode is None
            else tc.power_signal_mode.value
        )
    if version in _LIGHT_STONE_VERSIONS:
        w.write_u32(
            _LIGHT_STONE_COLOR_NONE_SENTINEL
            if tc.light_stone_color_mode is None
            else tc.light_stone_color_mode.value
        )


def serialize_tree_node(
    w: Writer,
    version: CourseSaveDataVersion,
    node: TileTowerTreeNodeData,
) -> None:
    """Write a recursive stacking-tree node: index, children_count, data, children[]."""
    w.write_s32(node.index)
    w.write_s32(len(node.children))
    serialize_construction_data(w, version, node.construction_data)
    for child in node.children:
        serialize_tree_node(w, version, child)


def serialize_cell(
    w: Writer,
    version: CourseSaveDataVersion,
    cell: CellConstructionData,
) -> None:
    """Write one cell: local position + root of its stacking tree."""
    w.write_hex_vector(cell.local_hex_position)
    serialize_tree_node(w, version, cell.tree_node_data)


def serialize_layer(
    w: Writer,
    version: CourseSaveDataVersion,
    layer: LayerConstructionData,
) -> None:
    """Write one layer with all its cells. cell_count is s32 to match parser."""
    w.write_s32(layer.layer_id)
    w.write_u32(layer.layer_kind.value)
    w.write_f32(layer.layer_height)
    w.write_hex_vector(layer.world_hex_position)
    w.write_s32(len(layer.cell_construction_datas))
    for cell in layer.cell_construction_datas:
        serialize_cell(w, version, cell)


def serialize_rail_exit_identifier(
    w: Writer,
    version: CourseSaveDataVersion,
    e: RailConstructionExitIdentifier,
) -> None:
    """Write one end of a rail. exit_local_pos_y only for PRO_2020+."""
    w.write_s32(e.retainer_id)
    w.write_hex_vector(e.cell_local_hex_pos)
    w.write_s32(e.side_hex_rot)
    if version in _RAIL_EXIT_POS_Y_VERSIONS:
        w.write_f32(e.exit_local_pos_y)


def serialize_rail(
    w: Writer,
    version: CourseSaveDataVersion,
    rail: RailConstructionData,
) -> None:
    """Write one rail. materialized only for ZIPLINE_ADDED_2019."""
    serialize_rail_exit_identifier(w, version, rail.exit_1_identifier)
    serialize_rail_exit_identifier(w, version, rail.exit_2_identifier)
    w.write_u32(rail.rail_kind.value)
    if version in _RAIL_MATERIALIZED_VERSIONS:
        if rail.materialized is None:
            raise ValueError(
                f"rail.materialized is required for version {version.name} but is None"
            )
        w.write_bool(rail.materialized)


def serialize_pillar(w: Writer, pillar: PillarConstructionData) -> None:
    """Write a pillar. layer_ids are u32 to mirror parser (Rust uses i32, bytes are identical for non-negative values)."""
    w.write_u32(pillar.lower_layer_id)
    w.write_hex_vector(pillar.lower_cell_local_position)
    w.write_u32(pillar.upper_layer_id)
    w.write_hex_vector(pillar.upper_cell_local_position)


def serialize_wall_coordinate(w: Writer, c: WallCoordinate) -> None:
    """Write a wall grid coordinate: (column, row) as two s32."""
    w.write_s32(c.column)
    w.write_s32(c.row)


def serialize_wall_balcony(
    w: Writer,
    version: CourseSaveDataVersion,
    b: WallBalconyConstructionData,
) -> None:
    """Write a balcony: retainer, side, coord, has_cell flag, optional cell."""
    w.write_s32(b.retainer_id)
    w.write_u32(b.wall_side.value)
    serialize_wall_coordinate(w, b.wall_coordinate)
    has_cell = b.cell_construction_data is not None
    w.write_bool(has_cell)
    if has_cell:
        serialize_cell(w, version, b.cell_construction_data)


def serialize_wall(
    w: Writer,
    version: CourseSaveDataVersion,
    wall: WallConstructionData,
) -> None:
    """Write a wall with its balconies. balcony_count is s32."""
    w.write_s32(wall.lower_stacker_tower_1_retainer_id)
    w.write_hex_vector(wall.lower_stacker_tower_1_local_hex_pos)
    w.write_s32(wall.lower_stacker_tower_2_retainer_id)
    w.write_hex_vector(wall.lower_stacker_tower_2_local_hex_pos)
    w.write_s32(len(wall.balcony_construction_datas))
    for bal in wall.balcony_construction_datas:
        serialize_wall_balcony(w, version, bal)


def serialize_course(course: Course) -> bytes:
    """Serialize a full Course. Inverse of parse_course."""
    w = Writer()
    serialize_header(w, course.header)
    serialize_meta_data(w, course.meta_data)

    w.write_u32(len(course.layer_construction_data))
    for layer in course.layer_construction_data:
        serialize_layer(w, course.header.version, layer)

    w.write_u32(len(course.rail_construction_data))
    for rail in course.rail_construction_data:
        serialize_rail(w, course.header.version, rail)

    w.write_u32(len(course.pillar_construction_data))
    for pillar in course.pillar_construction_data:
        serialize_pillar(w, pillar)

    w.write_u32(course.generation.value)

    w.write_s32(len(course.wall_construction_data))
    for wall in course.wall_construction_data:
        serialize_wall(w, course.header.version, wall)

    return bytes(w.buf)
