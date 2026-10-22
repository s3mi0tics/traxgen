"""Probe input: a course with every goal piece removed, uploaded, so a render without the goal
can be set beside a render with it (item 19, option C).

s42-t4. Proves the result differs from the source by the goal pieces and nothing else
before writing it: a pixel that changes must have changed because the goal went, not
because of a stray edit.

    uv run python -m scripts.make_no_goal OUT_DIR NAME=SOURCE.course [NAME=SOURCE.course ...]

Each source is written as OUT_DIR/NAME.course and OUT_DIR/NAME-nogoal.course, both
uploaded; the codes are printed and appended to OUT_DIR/codes.txt.

Path: traxgen/scripts/make_no_goal.py
"""

from __future__ import annotations

import dataclasses as dc
import sys
from pathlib import Path

from scripts.make_goal_variants import tiles
from traxgen.parser import parse_course
from traxgen.serializer import serialize_course
from traxgen.types import TileKind
from traxgen.uploader import upload_course_with_retry

GOAL_KINDS = frozenset({
    TileKind.GOAL_BASIN, TileKind.GOAL_RAIL, TileKind.FINISH_TRIGGER, TileKind.FINISH_ARENA,
})


def without_goal(course) -> bytes:
    """The course with every cell whose bottom piece is a goal removed, a test title, and GUID 0.

    A goal with anything stacked on it, or sitting on top of something, is refused rather
    than guessed at: neither occurs in the courses this was written for.
    """
    def keep(cell) -> bool:
        stack = [cell.tree_node_data]
        while stack:
            node = stack.pop()
            if node.construction_data.kind in GOAL_KINDS and node is not cell.tree_node_data:
                raise ValueError(f"goal stacked on another piece at {cell.local_hex_position}")
            stack.extend(node.children)
        root = cell.tree_node_data
        if root.construction_data.kind in GOAL_KINDS:
            if root.children:
                raise ValueError(f"something stacked on the goal at {cell.local_hex_position}")
            return False
        return True

    layers = tuple(
        dc.replace(layer, cell_construction_datas=tuple(
            c for c in layer.cell_construction_datas if keep(c)))
        for layer in course.layer_construction_data
    )
    return serialize_course(dc.replace(
        course,
        header=dc.replace(course.header, guid=0),
        meta_data=dc.replace(course.meta_data, title="traxgen finish test no goal"),
        layer_construction_data=layers,
    ))


def main(out: Path, sources: dict[str, Path]) -> int:
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, source in sources.items():
        raw_source = source.read_bytes()
        course = parse_course(raw_source)
        raw = without_goal(course)
        parsed = parse_course(raw)
        assert serialize_course(parsed) == raw, "does not round-trip"
        before = [t for t in tiles(course) if t[2].kind not in GOAL_KINDS]
        removed = [t for t in tiles(course) if t[2].kind in GOAL_KINDS]
        assert removed, f"{name}: no goal piece to remove"
        assert list(tiles(parsed)) == before, "more than the goal pieces changed"
        assert parsed.rail_construction_data == course.rail_construction_data, "rails changed"
        assert [layer.layer_id for layer in parsed.layer_construction_data] == [
            layer.layer_id for layer in course.layer_construction_data], "layers changed"
        (out / f"{name}.course").write_bytes(raw_source)
        (out / f"{name}-nogoal.course").write_bytes(raw)
        code_with, _ = upload_course_with_retry(raw_source)
        code_without, _ = upload_course_with_retry(raw)
        kinds = ", ".join(f"{t[2].kind.name}@{t[1]}" for t in removed)
        print(f"{name}: removed {kinds}, nothing else; {len(raw_source)} -> {len(raw)} bytes; "
              f"with goal {code_with}, without {code_without}")
        lines.append(f"{name}={code_with} {name}-nogoal={code_without}")
    with (out / "codes.txt").open("a") as f:
        f.write("".join(line + "\n" for line in lines))
    return 0


if __name__ == "__main__":
    pairs = dict(arg.split("=", 1) for arg in sys.argv[2:])
    sys.exit(main(Path(sys.argv[1]), {k: Path(v) for k, v in pairs.items()}))
