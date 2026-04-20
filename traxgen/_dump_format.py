"""
Convert a parsed Course to the dict shape murmelbahn's /dump endpoint produces.

Used only for round-trip testing the parser against the oracle dump.
Not part of the public API.

Shape rules derived from /api/course/{code}/dump:
  - Rust enum variants render as CamelCase strings (e.g. TileKind.CURVE -> "Curve")
  - Field names stay snake_case (matches our dataclass attribute names)
  - None renders as JSON null via json.dumps; we emit Python None
  - HexVector and WallCoordinate render as nested objects, not tuples
  - Optional-version fields (power_signal_mode etc.) are always present as keys;
    value is None if not set, else the CamelCase variant name
  - GUID is a big integer, not a hex string
  - Floats are left as Python floats; the diff layer decides tolerance

Path: traxgen/traxgen/_dump_format.py
"""

from __future__ import annotations

from enum import Enum
from typing import Any

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


def _name_to_camel(name: str) -> str:
    """Convert SCREAMING_SNAKE_CASE to CamelCase. POWER_2022 -> Power2022, FLEX_TUBE_240 -> FlexTube240."""
    return "".join(chunk.title() for chunk in name.split("_"))


def _enum(value: Enum | None) -> str | None:
    """Render an enum as its CamelCase variant name, or None if unset."""
    return None if value is None else _name_to_camel(value.name)


def _hex(h: HexVector) -> dict[str, int]:
    """HexVector -> {'y': ..., 'x': ...}."""
    return {"y": h.y, "x": h.x}


def _wall_coordinate(c: WallCoordinate) -> dict[str, int]:
    return {"column": c.column, "row": c.row}


def _tile_construction(tc: TileTowerConstructionData) -> dict[str, Any]:
    return {
        "kind": _enum(tc.kind),
        "height_in_small_stacker": tc.height_in_small_stacker,
        "hex_rotation": tc.hex_rotation,
        "retainer_id": tc.retainer_id,
        "power_signal_mode": _enum(tc.power_signal_mode),
        "light_stone_color_mode": _enum(tc.light_stone_color_mode),
    }


def _tree_node(node: TileTowerTreeNodeData) -> dict[str, Any]:
    return {
        "index": node.index,
        "construction_data": _tile_construction(node.construction_data),
        "children": [_tree_node(c) for c in node.children],
    }


def _cell(cell: CellConstructionData) -> dict[str, Any]:
    return {
        "local_hex_position": _hex(cell.local_hex_position),
        "tree_node_data": _tree_node(cell.tree_node_data),
    }


def _layer(layer: LayerConstructionData) -> dict[str, Any]:
    return {
        "layer_id": layer.layer_id,
        "layer_kind": _enum(layer.layer_kind),
        "layer_height": layer.layer_height,
        "world_hex_position": _hex(layer.world_hex_position),
        "cell_construction_datas": [_cell(c) for c in layer.cell_construction_datas],
    }


def _rail_exit(e: RailConstructionExitIdentifier) -> dict[str, Any]:
    return {
        "retainer_id": e.retainer_id,
        "cell_local_hex_pos": _hex(e.cell_local_hex_pos),
        "side_hex_rot": e.side_hex_rot,
        "exit_local_pos_y": e.exit_local_pos_y,
    }


def _rail(rail: RailConstructionData) -> dict[str, Any]:
    return {
        "exit_1_identifier": _rail_exit(rail.exit_1_identifier),
        "exit_2_identifier": _rail_exit(rail.exit_2_identifier),
        "rail_kind": _enum(rail.rail_kind),
        "materialized": rail.materialized,
    }


def _pillar(pillar: PillarConstructionData) -> dict[str, Any]:
    return {
        "lower_layer_id": pillar.lower_layer_id,
        "lower_cell_local_position": _hex(pillar.lower_cell_local_position),
        "upper_layer_id": pillar.upper_layer_id,
        "upper_cell_local_position": _hex(pillar.upper_cell_local_position),
    }


def _balcony(b: WallBalconyConstructionData) -> dict[str, Any]:
    # Dump uses the key "cell_construction_datas" (plural) even though it's a single optional cell.
    return {
        "retainer_id": b.retainer_id,
        "wall_side": _enum(b.wall_side),
        "wall_coordinate": _wall_coordinate(b.wall_coordinate),
        "cell_construction_datas": None if b.cell_construction_data is None else _cell(b.cell_construction_data),
    }


def _wall(wall: WallConstructionData) -> dict[str, Any]:
    return {
        "lower_stacker_tower_1_retainer_id": wall.lower_stacker_tower_1_retainer_id,
        "lower_stacker_tower_1_local_hex_pos": _hex(wall.lower_stacker_tower_1_local_hex_pos),
        "lower_stacker_tower_2_retainer_id": wall.lower_stacker_tower_2_retainer_id,
        "lower_stacker_tower_2_local_hex_pos": _hex(wall.lower_stacker_tower_2_local_hex_pos),
        "balcony_construction_datas": [_balcony(b) for b in wall.balcony_construction_datas],
    }


def _header(h: SaveDataHeader) -> dict[str, Any]:
    return {"guid": h.guid, "version": _enum(h.version)}


def _meta(m: CourseMetaData) -> dict[str, Any]:
    return {
        "creation_timestamp": m.creation_timestamp,
        "title": m.title,
        "order_number": m.order_number,
        "course_kind": _enum(m.course_kind),
        "objective_kind": _enum(m.objective_kind),
        "difficulty": m.difficulty,
        "completed": m.completed,
    }


def course_to_dump_dict(course: Course) -> dict[str, Any]:
    """Convert a parsed Course to the dict shape murmelbahn's /dump endpoint produces."""
    return {
        "header": _header(course.header),
        "course": {
            "meta_data": _meta(course.meta_data),
            "layer_construction_data": [_layer(la) for la in course.layer_construction_data],
            "rail_construction_data": [_rail(r) for r in course.rail_construction_data],
            "pillar_construction_data": [_pillar(p) for p in course.pillar_construction_data],
            "generation": _enum(course.generation),
            "wall_construction_data": [_wall(w) for w in course.wall_construction_data],
        },
    }
