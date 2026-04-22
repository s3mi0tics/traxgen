# Path: traxgen/scripts/probe_tile_index.py
"""Probe TileTowerTreeNodeData.index semantics in GDZJZA3J3T.

Answers two questions:

1. Is `index` cell-local or course-wide? If cell-local, each cell's tree
   has its own 0..N sequence. If course-wide, we'd see monotonically
   increasing values across cells.

2. Is `index` dense (0,1,2,...) or just unique (could have gaps)? The
   rule spec only asserts uniqueness, but if the app also requires
   density, we'd want to log that as a separate concern.

Also scans for duplicates within each cell (which would invalidate the
intended TILE_INDEX_COLLISION rule) and across cells (which would
suggest the rule is actually about global uniqueness, not cell-local).

Run: `uv run python -m scripts.probe_tile_index`
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from traxgen.domain import CellConstructionData, TileTowerTreeNodeData
from traxgen.parser import parse_course


def _walk_tree(node: TileTowerTreeNodeData) -> list[tuple[int, str]]:
    """Pre-order walk. Returns (index, kind_name) pairs."""
    out: list[tuple[int, str]] = [(node.index, node.construction_data.kind.name)]
    for child in node.children:
        out.extend(_walk_tree(child))
    return out


def _indices_in_cell(cell: CellConstructionData) -> list[tuple[int, str]]:
    return _walk_tree(cell.tree_node_data)


def main() -> None:
    fixture_path = Path("tests/fixtures/GDZJZA3J3T.course")
    course = parse_course(fixture_path.read_bytes())

    # Collect every (source, index, kind) so we can answer both questions.
    per_cell_indices: list[list[tuple[int, str]]] = []
    all_indices_global: list[int] = []

    for layer in course.layer_construction_data:
        for cell_num, cell in enumerate(layer.cell_construction_datas):
            indices = _indices_in_cell(cell)
            per_cell_indices.append(indices)
            all_indices_global.extend(i for i, _ in indices)

    for wall in course.wall_construction_data:
        for balcony in wall.balcony_construction_datas:
            if balcony.cell_construction_data is None:
                continue
            indices = _indices_in_cell(balcony.cell_construction_data)
            per_cell_indices.append(indices)
            all_indices_global.extend(i for i, _ in indices)

    print(f"Total cells scanned: {len(per_cell_indices)}")
    print(f"Total tree nodes: {len(all_indices_global)}")
    print()

    # --- Q1: cell-local or global? ---------------------------------------
    # If cell-local, we'd expect each cell's sequence to start at or near 0
    # and not overlap with other cells by coincidence. If global, indices
    # would be unique course-wide and probably monotonic.
    print("--- Q1: Is `index` cell-local or course-wide? ---")
    global_counts = Counter(all_indices_global)
    global_dupes = {idx: n for idx, n in global_counts.items() if n > 1}
    if global_dupes:
        print(f"Globally, {len(global_dupes)} index value(s) appear in multiple cells:")
        for idx, n in sorted(global_dupes.items())[:10]:
            print(f"  index={idx}: appears {n} times across cells")
        if len(global_dupes) > 10:
            print(f"  ... and {len(global_dupes) - 10} more")
        print("=> Strongly suggests CELL-LOCAL semantics.")
    else:
        print("All indices unique across the entire course.")
        print("=> Could be global, OR cell-local with non-colliding ranges.")
        print(f"   (Range: {min(all_indices_global)}..{max(all_indices_global)}, "
              f"expected if dense global: 0..{len(all_indices_global) - 1})")
    print()

    # --- Q2: dense or sparse per cell? ------------------------------------
    print("--- Q2: Are per-cell indices dense (0..N-1) or sparse? ---")
    sparse_cells = 0
    total_nonempty = 0
    starts_at_zero = 0
    sample_sparse: list[tuple[int, list[int], list[str]]] = []
    for cell_idx, indices in enumerate(per_cell_indices):
        if not indices:
            continue
        total_nonempty += 1
        idx_values = sorted(i for i, _ in indices)
        kinds = [k for _, k in indices]
        expected_dense = list(range(len(idx_values)))
        if idx_values[0] == 0:
            starts_at_zero += 1
        if idx_values != expected_dense:
            sparse_cells += 1
            if len(sample_sparse) < 5:
                sample_sparse.append((cell_idx, idx_values, kinds))
    print(f"Cells with tree nodes: {total_nonempty}")
    print(f"Cells where indices start at 0: {starts_at_zero}")
    print(f"Cells with non-dense indices: {sparse_cells}")
    if sample_sparse:
        print("Sample sparse cells:")
        for cell_idx, idx_values, kinds in sample_sparse:
            print(f"  cell #{cell_idx}: indices={idx_values}, kinds={kinds}")
    print()

    # --- Q3: within-cell duplicates? (what the rule checks) ---------------
    print("--- Q3: Any within-cell index duplicates? ---")
    cells_with_dupes = 0
    for cell_idx, indices in enumerate(per_cell_indices):
        idx_values = [i for i, _ in indices]
        if len(idx_values) != len(set(idx_values)):
            cells_with_dupes += 1
            counts = Counter(idx_values)
            dupes = {i: n for i, n in counts.items() if n > 1}
            print(f"  cell #{cell_idx}: duplicates = {dupes}")
    if cells_with_dupes == 0:
        print("No within-cell duplicates found. The proposed rule would pass on "
              "this fixture (as expected for valid data).")
    else:
        print(f"Found duplicates in {cells_with_dupes} cell(s) — would invalidate "
              "the planned rule shape.")
    print()

    # --- Q4: root index distribution --------------------------------------
    # Does every cell's root tree node have index=0? That's a simple shape
    # the rule could additionally assert.
    print("--- Q4: What index do root tree nodes have? ---")
    root_indices = Counter(
        cell.tree_node_data.index
        for layer in course.layer_construction_data
        for cell in layer.cell_construction_datas
    )
    root_indices.update(
        balcony.cell_construction_data.tree_node_data.index
        for wall in course.wall_construction_data
        for balcony in wall.balcony_construction_datas
        if balcony.cell_construction_data is not None
    )
    for idx, n in sorted(root_indices.items()):
        print(f"  root index={idx}: {n} cell(s)")


if __name__ == "__main__":
    main()
