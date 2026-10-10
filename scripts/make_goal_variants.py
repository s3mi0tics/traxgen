"""Probe input: PROBOOK12 with only the goal rail's rotation changed, one file per rotation.

s41-t3. Proves each variant differs from the corpus course in that one field and nothing
else before writing it -- a miss course must be a miss because of the goal, not a stray edit.

    uv run python -m scripts.make_goal_variants screenshots/finish_frames/variants 0 2

Path: traxgen/scripts/make_goal_variants.py
"""

from __future__ import annotations

import dataclasses as dc
import sys
from collections.abc import Iterator
from pathlib import Path

from traxgen.parser import parse_course
from traxgen.serializer import serialize_course
from traxgen.types import TileKind

SOURCE = Path.home() / "Claude/Projects/traxgen-corpus/raw/PROBOOK12.course"


def tiles(course) -> Iterator[tuple]:
    """Every tile in the course as (layer id, local cell, construction data)."""
    for layer in course.layer_construction_data:
        for cell in layer.cell_construction_datas:
            stack = [cell.tree_node_data]
            while stack:
                node = stack.pop()
                yield layer.layer_id, cell.local_hex_position, node.construction_data
                stack.extend(node.children)


def variant(course, rotation: int) -> bytes:
    """The course with every GOAL_RAIL set to `rotation`, a test title, and GUID 0."""

    def turn(node):
        cd = node.construction_data
        if cd.kind == TileKind.GOAL_RAIL:
            cd = dc.replace(cd, hex_rotation=rotation)
        return dc.replace(node, construction_data=cd, children=tuple(map(turn, node.children)))

    layers = tuple(
        dc.replace(layer, cell_construction_datas=tuple(
            dc.replace(cell, tree_node_data=turn(cell.tree_node_data))
            for cell in layer.cell_construction_datas
        ))
        for layer in course.layer_construction_data
    )
    return serialize_course(dc.replace(
        course,
        header=dc.replace(course.header, guid=0),
        meta_data=dc.replace(course.meta_data, title=f"traxgen finish test goal {rotation}"),
        layer_construction_data=layers,
    ))


def main(out: Path, rotations: list[int]) -> int:
    course = parse_course(SOURCE.read_bytes())
    base = list(tiles(course))
    out.mkdir(parents=True, exist_ok=True)
    for rotation in rotations:
        raw = variant(course, rotation)
        parsed = parse_course(raw)
        assert serialize_course(parsed) == raw, "does not round-trip"
        diff = [(a, b) for a, b in zip(base, tiles(parsed), strict=True) if a != b]
        assert len(diff) == 1 and diff[0][0][2].kind == TileKind.GOAL_RAIL, "more than the goal"
        (old, new), = diff
        assert dc.replace(old[2], hex_rotation=rotation) == new[2], "more than its rotation"
        assert parsed.rail_construction_data == course.rail_construction_data, "rails changed"
        path = out / f"goal{rotation}.course"
        path.write_bytes(raw)
        print(f"{path}: goal rail {old[2].hex_rotation} -> {rotation}, nothing else; "
              f"{len(raw)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), [int(r) for r in sys.argv[2:]]))
