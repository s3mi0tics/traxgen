# Path: traxgen/scripts/probe_tile_index_dupes.py
"""Follow-up probe: inspect the cells with duplicate `index` values.

Initial probe (probe_tile_index.py) found 4 cells in GDZJZA3J3T with
within-cell duplicates — all at index=0. This probe digs in:

1. What kinds of tiles share index=0? (Testing the 'inserts are
   sentinel-0' hypothesis.)
2. Are non-zero indices ever duplicated? (Maybe the real rule is
   'unique *except* 0 as sentinel'.)
3. Full tree shape for each duplicate cell, including parent/child
   relationships, so we can see whether duplicates cluster at roots,
   leaves, or both.

Run: `uv run python -m scripts.probe_tile_index_dupes`
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from traxgen.domain import CellConstructionData, TileTowerTreeNodeData
from traxgen.parser import parse_course


def _walk_with_depth(
    node: TileTowerTreeNodeData, depth: int = 0
) -> list[tuple[int, int, str, int]]:
    """Pre-order walk returning (depth, index, kind_name, h) tuples."""
    out: list[tuple[int, int, str, int]] = [(
        depth,
        node.index,
        node.construction_data.kind.name,
        node.construction_data.height_in_small_stacker,
    )]
    for child in node.children:
        out.extend(_walk_with_depth(child, depth + 1))
    return out


def _dump_cell(cell_idx: int, cell: CellConstructionData, source: str) -> None:
    print(f"=== cell #{cell_idx} ({source}) at {cell.local_hex_position} ===")
    walk = _walk_with_depth(cell.tree_node_data)
    idx_counts = Counter(i for _, i, _, _ in walk)
    dupes = {i: n for i, n in idx_counts.items() if n > 1}
    print(f"  duplicates: {dupes}")
    for depth, idx, kind, h in walk:
        indent = "  " + "  " * depth
        marker = " <-- DUPE" if idx_counts[idx] > 1 else ""
        print(f"{indent}[{depth}] index={idx:>3} kind={kind:<25} h={h}{marker}")


def main() -> None:
    fixture_path = Path("tests/fixtures/GDZJZA3J3T.course")
    course = parse_course(fixture_path.read_bytes())

    # Collect all cells with their source-labels so we can trace back.
    labeled_cells: list[tuple[int, CellConstructionData, str]] = []
    cell_counter = 0
    for layer_i, layer in enumerate(course.layer_construction_data):
        for cell in layer.cell_construction_datas:
            labeled_cells.append((cell_counter, cell, f"layer #{layer_i} id={layer.layer_id}"))
            cell_counter += 1
    for wall_i, wall in enumerate(course.wall_construction_data):
        for bal_i, balcony in enumerate(wall.balcony_construction_datas):
            if balcony.cell_construction_data is None:
                continue
            labeled_cells.append((
                cell_counter,
                balcony.cell_construction_data,
                f"wall #{wall_i} balcony #{bal_i}",
            ))
            cell_counter += 1

    # --- Dump every duplicate cell in full ---
    print("=" * 72)
    print("DUPLICATE-INDEX CELLS (full tree dumps)")
    print("=" * 72)
    dupe_cells = []
    for cell_idx, cell, source in labeled_cells:
        indices = [n.index for n in _all_nodes(cell.tree_node_data)]
        if len(indices) != len(set(indices)):
            dupe_cells.append((cell_idx, cell, source))

    for cell_idx, cell, source in dupe_cells:
        _dump_cell(cell_idx, cell, source)
        print()

    # --- Aggregate: which kinds ever appear at index=0? -------------------
    print("=" * 72)
    print("KINDS AT index=0 ACROSS THE COURSE")
    print("=" * 72)
    kinds_at_zero: Counter[str] = Counter()
    kinds_overall_at_any_duplicated_idx: Counter[tuple[int, str]] = Counter()
    for _, cell, _ in labeled_cells:
        walk = _walk_with_depth(cell.tree_node_data)
        for _, idx, kind, _ in walk:
            if idx == 0:
                kinds_at_zero[kind] += 1
        # Also tally (idx, kind) for cells where this idx is duplicated.
        idx_counts = Counter(i for _, i, _, _ in walk)
        for _, idx, kind, _ in walk:
            if idx_counts[idx] > 1:
                kinds_overall_at_any_duplicated_idx[(idx, kind)] += 1
    for kind, n in kinds_at_zero.most_common():
        print(f"  {kind:<30} appears at index=0: {n} time(s)")
    print()
    print("Kinds at *any* duplicated index (within their cell):")
    for (idx, kind), n in sorted(kinds_overall_at_any_duplicated_idx.items()):
        print(f"  index={idx} kind={kind:<30} : {n} occurrence(s)")

    # --- Non-zero duplicate check ----------------------------------------
    print()
    print("=" * 72)
    print("NON-ZERO DUPLICATES?")
    print("=" * 72)
    found_nonzero = False
    for cell_idx, cell, source in labeled_cells:
        walk = _walk_with_depth(cell.tree_node_data)
        idx_counts = Counter(i for _, i, _, _ in walk)
        for idx, n in idx_counts.items():
            if n > 1 and idx != 0:
                found_nonzero = True
                print(f"  cell #{cell_idx} ({source}): index={idx} appears {n} times")
    if not found_nonzero:
        print("  None. Every within-cell duplicate in this fixture is specifically "
              "at index=0.")


def _all_nodes(node: TileTowerTreeNodeData) -> list[TileTowerTreeNodeData]:
    out = [node]
    for c in node.children:
        out.extend(_all_nodes(c))
    return out


if __name__ == "__main__":
    main()
