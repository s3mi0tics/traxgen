"""Walk GDZJZA3J3T's cell trees and show how stackers are represented.

Path: traxgen/scripts/probe_stackers.py
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from traxgen.parser import parse_course
from traxgen.types import TileKind


def walk(node, depth=0):
    """Yield (depth, construction_data) for every node in the tree."""
    yield depth, node.construction_data
    for child in node.children:
        yield from walk(child, depth + 1)


def main() -> None:
    fixture = Path("tests/fixtures/GDZJZA3J3T.course")
    course = parse_course(fixture.read_bytes())

    # Aggregate: kind counts across all tree nodes, and height_in_small_stacker
    # distribution per kind.
    kind_counts: Counter[TileKind] = Counter()
    height_by_kind: dict[TileKind, Counter[int]] = {}

    for layer in course.layer_construction_data:
        for cell in layer.cell_construction_datas:
            for depth, cd in walk(cell.tree_node_data):
                kind_counts[cd.kind] += 1
                height_by_kind.setdefault(cd.kind, Counter())[cd.height_in_small_stacker] += 1

    print("=== All TileKinds appearing in tree nodes ===")
    for kind, count in sorted(kind_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {kind.name:30s} count={count}")

    print()
    print("=== height_in_small_stacker distribution per kind ===")
    for kind, heights in sorted(height_by_kind.items(), key=lambda kv: kv[0].name):
        dist = ", ".join(f"h={h}:{n}" for h, n in sorted(heights.items()))
        print(f"  {kind.name:30s} {dist}")

    print()
    print("=== Tree shape examples (first 5 cells across all layers) ===")
    shown = 0
    for layer in course.layer_construction_data:
        for cell in layer.cell_construction_datas:
            if shown >= 5:
                break
            print(f"\n  layer_id={layer.layer_id} cell@{cell.local_hex_position}:")
            for depth, cd in walk(cell.tree_node_data):
                indent = "    " + "  " * depth
                print(f"{indent}{cd.kind.name} h={cd.height_in_small_stacker} rot={cd.hex_rotation}")
            shown += 1
        if shown >= 5:
            break

    print()
    print("=== Quick sanity questions ===")
    has_stacker_nodes = kind_counts.get(TileKind.STACKER, 0) + kind_counts.get(TileKind.STACKER_SMALL, 0)
    print(f"  Does STACKER/STACKER_SMALL appear as its own tree node?  "
          f"{'YES' if has_stacker_nodes else 'NO'}  (count={has_stacker_nodes})")

    non_stacker_with_height = sum(
        heights.get(h, 0)
        for kind, heights in height_by_kind.items()
        if kind not in (TileKind.STACKER, TileKind.STACKER_SMALL)
        for h in heights
        if h > 0
    )
    print(f"  Do non-stacker tiles carry height>0?                     "
          f"{'YES' if non_stacker_with_height else 'NO'}  (count={non_stacker_with_height})")


if __name__ == "__main__":
    main()
