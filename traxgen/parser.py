"""
Binary parser for GraviTrax .course files.

Incremental build: currently reads the header (u128 GUID + u32 save version)
and nothing more. We'll expand outward once the header round-trips against
the GDZJZA3J3T fixture.

Wire format notes (POWER_2022, v4):
  - All integers little-endian.
  - Strings: u8 length prefix, UTF-8 bytes, no null terminator.
  - Booleans: u8 (0 or 1), followed by 2 bytes of padding before the next u32.
  - HexVector: two s32 in (y, x) order — the binary stores y before x.
  - Recursive tile tree: index, children_count, construction_data, children[].

Path: traxgen/traxgen/parser.py
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from traxgen.domain import (
    CellConstructionData,
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


@dataclass
class Reader:
    """Cursor over a bytes buffer with little-endian primitive reads."""

    data: bytes
    pos: int = 0

    def _take(self, n: int) -> bytes:
        """Consume n bytes and advance the cursor. Raises on short read."""
        if self.pos + n > len(self.data):
            raise ValueError(
                f"short read: wanted {n} bytes at offset {self.pos}, "
                f"{len(self.data) - self.pos} remaining"
            )
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def read_u8(self) -> int:
        """Read one unsigned byte."""
        return self._take(1)[0]

    def read_u32(self) -> int:
        """Read a little-endian u32."""
        return struct.unpack("<I", self._take(4))[0]

    def read_s32(self) -> int:
        """Read a little-endian s32."""
        return struct.unpack("<i", self._take(4))[0]

    def read_u64(self) -> int:
        """Read a little-endian u64."""
        return struct.unpack("<Q", self._take(8))[0]

    def read_u128(self) -> int:
        """Read a little-endian u128, returned as a Python int."""
        return int.from_bytes(self._take(16), "little")

    def read_f32(self) -> float:
        """Read a little-endian f32."""
        return struct.unpack("<f", self._take(4))[0]

    def read_bool(self) -> bool:
        """Read a u8 bool. Does NOT consume trailing padding — see read_bool_padded."""
        return self.read_u8() != 0

    def read_bool_padded(self) -> bool:
        """Read a u8 bool plus 2 bytes of padding (u32 alignment)."""
        v = self.read_bool()
        self._take(2)
        return v

    def read_string(self) -> str:
        """Read a u8-length-prefixed UTF-8 string."""
        n = self.read_u8()
        return self._take(n).decode("utf-8")

    def read_hex_vector(self) -> HexVector:
        """Read a HexVector: two s32 in (y, x) order to match the wire format."""
        y = self.read_s32()
        x = self.read_s32()
        return HexVector(y, x)

    @property
    def remaining(self) -> int:
        """Bytes left unread."""
        return len(self.data) - self.pos


def parse_header(r: Reader) -> SaveDataHeader:
    """Parse u128 GUID + u32 save version."""
    guid = r.read_u128()
    version = CourseSaveDataVersion(r.read_u32())
    return SaveDataHeader(guid=guid, version=version)


def parse_meta_data(r: Reader) -> CourseMetaData:
    """Parse course metadata: timestamp, title, classification, completion flag."""
    creation_timestamp = r.read_u64()
    title = r.read_string()
    order_number = r.read_s32()
    course_kind = CourseKind(r.read_u32())
    objective_kind = ObjectiveKind(r.read_u32())
    difficulty = r.read_s32()
    completed = r.read_bool()
    return CourseMetaData(
        creation_timestamp=creation_timestamp,
        title=title,
        order_number=order_number,
        course_kind=course_kind,
        objective_kind=objective_kind,
        difficulty=difficulty,
        completed=completed,
    )


# --- Version-conditional field sets ---------------------------------------

_POWER_SIGNAL_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.POWER_2022,
    CourseSaveDataVersion.LIGHT_STONES_2023,
})
_LIGHT_STONE_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.LIGHT_STONES_2023,
})

_RETAINER_ID_NULL_SENTINEL = -2147483647  # i32::MIN + 1, per murmelbahn layer.rs


def parse_construction_data(
    r: Reader, version: CourseSaveDataVersion
) -> TileTowerConstructionData:
    """Parse one tile's placement data. Optional fields depend on save version."""
    # Rust uses i32 for height_in_small_stacker, hex_rotation, retainer_id.
    # TileKind is still a u32-tagged enum.
    kind = TileKind(r.read_u32())
    height_in_small_stacker = r.read_s32()
    hex_rotation = r.read_s32()
    retainer_id_raw = r.read_s32()
    retainer_id = None if retainer_id_raw == _RETAINER_ID_NULL_SENTINEL else retainer_id_raw

    power_signal_mode: PowerSignalMode | None = None
    if version in _POWER_SIGNAL_VERSIONS:
        psm_raw = r.read_u32()
        if psm_raw != PowerSignalMode.NONE.value:
            power_signal_mode = PowerSignalMode(psm_raw)

    light_stone_color_mode: LightStoneColorMode | None = None
    if version in _LIGHT_STONE_VERSIONS:
        lscm_raw = r.read_u32()
        if lscm_raw != LightStoneColorMode.NONE.value:
            light_stone_color_mode = LightStoneColorMode(lscm_raw)

    return TileTowerConstructionData(
        kind=kind,
        height_in_small_stacker=height_in_small_stacker,
        hex_rotation=hex_rotation,
        retainer_id=retainer_id,
        power_signal_mode=power_signal_mode,
        light_stone_color_mode=light_stone_color_mode,
    )


def parse_tree_node(r: Reader, version: CourseSaveDataVersion) -> TileTowerTreeNodeData:
    """Parse a recursive stacking-tree node: index, children_count, data, children[]."""
    index = r.read_s32()
    children_count = r.read_s32()
    construction_data = parse_construction_data(r, version)
    children = tuple(parse_tree_node(r, version) for _ in range(children_count))
    return TileTowerTreeNodeData(
        index=index,
        construction_data=construction_data,
        children=children,
    )


def parse_cell(r: Reader, version: CourseSaveDataVersion) -> CellConstructionData:
    """Parse one cell: local position + root of its stacking tree."""
    local_hex_position = r.read_hex_vector()
    tree_node_data = parse_tree_node(r, version)
    return CellConstructionData(
        local_hex_position=local_hex_position,
        tree_node_data=tree_node_data,
    )


def parse_layer(r: Reader, version: CourseSaveDataVersion) -> LayerConstructionData:
    """Parse one horizontal layer with all its cells."""
    layer_id = r.read_s32()
    layer_kind = LayerKind(r.read_u32())
    layer_height = r.read_f32()
    world_hex_position = r.read_hex_vector()
    cell_count = r.read_s32()
    cells = tuple(parse_cell(r, version) for _ in range(cell_count))
    return LayerConstructionData(
        layer_id=layer_id,
        layer_kind=layer_kind,
        layer_height=layer_height,
        world_hex_position=world_hex_position,
        cell_construction_datas=cells,
    )


# --- Rails ----------------------------------------------------------------

_RAIL_EXIT_POS_Y_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.PRO_2020,
    CourseSaveDataVersion.POWER_2022,
    CourseSaveDataVersion.LIGHT_STONES_2023,
})
_RAIL_MATERIALIZED_VERSIONS: frozenset[CourseSaveDataVersion] = frozenset({
    CourseSaveDataVersion.ZIPLINE_ADDED_2019,
})


def parse_rail_exit_identifier(
    r: Reader, version: CourseSaveDataVersion
) -> RailConstructionExitIdentifier:
    """Parse one end of a rail: (retainer, cell, edge, optional vertical offset)."""
    retainer_id = r.read_s32()
    cell_local_hex_pos = r.read_hex_vector()
    side_hex_rot = r.read_s32()
    # exit_local_pos_y is only present in PRO_2020+. For older versions, the
    # field is logically absent; our domain type requires it, so older-version
    # support would need a domain.py change. POWER_2022 always has it.
    if version in _RAIL_EXIT_POS_Y_VERSIONS:
        exit_local_pos_y = r.read_f32()
    else:
        # Should not happen for POWER_2022 fixtures; parser branch guard only.
        raise ValueError(f"rail exit_local_pos_y missing for version {version.name}")
    return RailConstructionExitIdentifier(
        retainer_id=retainer_id,
        cell_local_hex_pos=cell_local_hex_pos,
        side_hex_rot=side_hex_rot,
        exit_local_pos_y=exit_local_pos_y,
    )


def parse_rail(r: Reader, version: CourseSaveDataVersion) -> RailConstructionData:
    """Parse a single rail: two exit identifiers, kind, and optional materialized flag."""
    exit_1 = parse_rail_exit_identifier(r, version)
    exit_2 = parse_rail_exit_identifier(r, version)
    rail_kind = RailKind(r.read_u32())
    # materialized is only present in ZIPLINE_ADDED_2019; absent otherwise.
    materialized: bool | None = None
    if version in _RAIL_MATERIALIZED_VERSIONS:
        materialized = r.read_bool()
    return RailConstructionData(
        exit_1_identifier=exit_1,
        exit_2_identifier=exit_2,
        rail_kind=rail_kind,
        materialized=materialized,
    )


# --- Pillars --------------------------------------------------------------

def parse_pillar(r: Reader) -> PillarConstructionData:
    """Parse a vertical pillar connecting a lower-layer cell to an upper-layer cell."""
    lower_layer_id = r.read_u32()
    lower_cell_local_position = r.read_hex_vector()
    upper_layer_id = r.read_u32()
    upper_cell_local_position = r.read_hex_vector()
    return PillarConstructionData(
        lower_layer_id=lower_layer_id,
        lower_cell_local_position=lower_cell_local_position,
        upper_layer_id=upper_layer_id,
        upper_cell_local_position=upper_cell_local_position,
    )


# --- Walls (PRO; optional cells inside balconies) -------------------------

def parse_wall_coordinate(r: Reader) -> WallCoordinate:
    """Parse a PRO wall grid coordinate: (column, row) as two i32."""
    column = r.read_s32()
    row = r.read_s32()
    return WallCoordinate(column=column, row=row)


def parse_wall_balcony(
    r: Reader, version: CourseSaveDataVersion
) -> WallBalconyConstructionData:
    """Parse a balcony attached to a PRO wall; may or may not hold a cell."""
    retainer_id = r.read_s32()
    wall_side = WallSide(r.read_u32())
    wall_coordinate = parse_wall_coordinate(r)
    has_cell = r.read_bool()
    cell = parse_cell(r, version) if has_cell else None
    return WallBalconyConstructionData(
        retainer_id=retainer_id,
        wall_side=wall_side,
        wall_coordinate=wall_coordinate,
        cell_construction_data=cell,
    )


def parse_wall(r: Reader, version: CourseSaveDataVersion) -> WallConstructionData:
    """Parse a PRO wall spanning two stacker towers, with its attached balconies."""
    lower1_id = r.read_s32()
    lower1_pos = r.read_hex_vector()
    lower2_id = r.read_s32()
    lower2_pos = r.read_hex_vector()
    balcony_count = r.read_s32()
    balconies = tuple(parse_wall_balcony(r, version) for _ in range(balcony_count))
    return WallConstructionData(
        lower_stacker_tower_1_retainer_id=lower1_id,
        lower_stacker_tower_1_local_hex_pos=lower1_pos,
        lower_stacker_tower_2_retainer_id=lower2_id,
        lower_stacker_tower_2_local_hex_pos=lower2_pos,
        balcony_construction_datas=balconies,
    )


# --- Top-level course parser ----------------------------------------------

def parse_course(data: bytes):
    """Parse a full .course file. Returns a Course (from traxgen.domain)."""
    from traxgen.domain import Course

    r = Reader(data)
    header = parse_header(r)
    meta_data = parse_meta_data(r)

    layer_count = r.read_u32()
    layers = tuple(parse_layer(r, header.version) for _ in range(layer_count))

    rail_count = r.read_u32()
    rails = tuple(parse_rail(r, header.version) for _ in range(rail_count))

    pillar_count = r.read_u32()
    pillars = tuple(parse_pillar(r) for _ in range(pillar_count))

    generation = CourseElementGeneration(r.read_u32())

    wall_count = r.read_s32()
    walls = tuple(parse_wall(r, header.version) for _ in range(wall_count))

    if r.remaining != 0:
        raise ValueError(
            f"parser finished with {r.remaining} bytes left over "
            f"(cursor at {r.pos} of {len(data)})"
        )

    return Course(
        header=header,
        meta_data=meta_data,
        layer_construction_data=layers,
        rail_construction_data=rails,
        pillar_construction_data=pillars,
        generation=generation,
        wall_construction_data=walls,
    )
