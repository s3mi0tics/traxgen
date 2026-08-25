"""Which plate cells are half-holes, and does the corpus ever build on one?

A GraviTrax baseplate does not end cleanly on every side. Along one pair of
edges the outermost hole of every other row is bisected by the plate boundary:
half the hole is on this plate, half is missing until a neighbouring plate is
attached to complete it. Colby confirmed the consequence in the app editor on
2026-08-24 -- **a piece cannot be placed on a half-hole unless a neighbouring
baseplate completes it** -- which makes it a legality rule the generator has to
obey, and one the corpus can check.

This probe does two things:

1. **Derives** which cells are half-holes, from `plates.MEASURED_FOOTPRINTS`.
   Never typed. A second typed copy of a measured set is the same untested
   claim one file over (observations #12's *Classes* discipline, and the
   `STANDARD_SQUARE` lesson in `plates.py`).
2. **Scans the corpus** for tiles standing on those cells, split by whether the
   completing plate is present. The prediction is zero in the incomplete case.

The control matters as much as the test. If nobody ever builds at a plate edge
at all, "zero on half-holes" is not evidence -- so the probe also counts tiles
on the *whole* holes at the same edge. That group must be non-empty for the
result to mean anything (observations #21: ask what a null would prove).

Run: `uv run python -m scripts.probe_plate_seams --corpus-dir <dir>`

Path: traxgen/scripts/probe_plate_seams.py
"""

from __future__ import annotations

import argparse
import collections
import sys
from fractions import Fraction
from pathlib import Path

from traxgen.parser import parse_course
from traxgen.plates import BASEPLATE_LAYER_KINDS, MEASURED_FOOTPRINTS
from traxgen.types import LayerKind

# Same set the other corpus probes refuse: v1/v2 are a different schema family
# the v4 path misparses into garbage, and v7 (SkyTrax) needs parser work that
# is `plan.md` item 8.
UNSUPPORTED_VERSIONS = frozenset({1, 2, 7})

Cell = tuple[int, int]  # (y, x), matching `plates.is_on_plate`'s own ordering


def column_centre(cell: Cell) -> Fraction:
    """Physical column of a cell's centre, in hole widths.

    Axial hex coordinates stagger every other row by half a hole, so the
    physical column is `y + x/2`. `Fraction` rather than `float` because every
    quantity here is a half-integer and the whole point is exact comparison at
    the half-hole boundary.

    This is the one modelling choice in the file. What justifies it is NOT the
    tiling search below -- that is purely combinatorial and never calls this
    function, so it holds under either stagger direction. The evidence is
    independent and came from outside the code: Colby reported from the app
    editor, before any of this was computed, that the outermost holes of *every
    other row* are halves. This stagger reproduces exactly that -- one bisected
    cell on alternating rows. The mirror (`y - x/2`) collapses the same
    derivation to a single cell on one row, which contradicts what is visibly
    on the plate. Pinned by test rather than left as a preference.
    """
    y, x = cell
    return Fraction(y) + Fraction(x, 2)


def find_tiling_delta(footprint: frozenset[Cell]) -> Cell:
    """The translation that places the neighbouring plate immediately alongside.

    Derived by search rather than named: the delta is the one that leaves the
    two footprints disjoint *and* leaves no gap between them, which is what
    "the plates butt together" means in coordinates. Searching rather than
    hardcoding is what lets this file carry no copy of `STANDARD_SQUARE`.
    """
    span = max(abs(v) for cell in footprint for v in cell) + 2
    candidates = []
    for dy in range(1, span + 1):
        for dx in range(-span, span + 1):
            moved = {(y + dy, x + dx) for y, x in footprint}
            if moved & footprint:
                continue
            if not _is_gapless(footprint | moved):
                continue
            candidates.append((dy, dx))
    if not candidates:
        raise ValueError("no gapless tiling translation found for this footprint")
    # Nearest first: a further-away plate that happens to tile is a multiple.
    return min(candidates, key=lambda d: (abs(d[0]) + abs(d[1]), d))


def _is_gapless(cells: set[Cell]) -> bool:
    """Every row of the union is a contiguous run of columns."""
    rows: dict[int, list[int]] = collections.defaultdict(list)
    for y, x in cells:
        rows[x].append(y)
    return all(
        sorted(ys) == list(range(min(ys), max(ys) + 1)) for ys in rows.values()
    )


def seam_cells(kind: LayerKind = LayerKind.BASE_LAYER_PIECE) -> frozenset[Cell]:
    """Cells whose centre lies exactly on the plate boundary -- the half-holes.

    The boundary sits at the largest column any cell reaches, so a cell centred
    there has half its hole hanging past the plate. Every other cell's hole is
    wholly inside.
    """
    footprint = frozenset(MEASURED_FOOTPRINTS[kind])
    edge = max(column_centre(cell) for cell in footprint)
    return frozenset(cell for cell in footprint if column_centre(cell) == edge)


def flush_edge_cells(kind: LayerKind = LayerKind.BASE_LAYER_PIECE) -> frozenset[Cell]:
    """The outermost WHOLE hole of each row that has no half-hole -- the control.

    These sit at the same plate edge and are always usable, so they measure
    whether builders use edge cells at all.
    """
    footprint = frozenset(MEASURED_FOOTPRINTS[kind])
    seams = seam_cells(kind)
    by_row: dict[int, list[Cell]] = collections.defaultdict(list)
    for cell in footprint:
        by_row[cell[1]].append(cell)
    out = set()
    for cells in by_row.values():
        outermost = max(cells, key=column_centre)
        if outermost not in seams:
            out.add(outermost)
    return frozenset(out)


def scan(corpus_dir: Path) -> collections.Counter:
    """Tally tiles by cell class and by whether the completing plate is present."""
    seams = seam_cells()
    flush = flush_edge_cells()
    delta = find_tiling_delta(frozenset(MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]))
    tally: collections.Counter = collections.Counter()
    tally["_delta"] = 0  # placeholder so the key exists; the value is reported separately

    for path in sorted(corpus_dir.glob("*.course")):
        data = path.read_bytes()
        if int.from_bytes(data[16:20], "little") in UNSUPPORTED_VERSIONS:
            tally["skipped(version)"] += 1
            continue
        try:
            course = parse_course(data)
        except Exception as exc:  # skip-and-record; never invent a placement
            tally[f"skipped({type(exc).__name__})"] += 1
            continue
        tally["parsed"] += 1
        plates = [
            layer
            for layer in course.layer_construction_data
            if layer.layer_kind in BASEPLATE_LAYER_KINDS
        ]
        occupied = {
            (layer.world_hex_position.y, layer.world_hex_position.x) for layer in plates
        }
        for layer in plates:
            here = (layer.world_hex_position.y, layer.world_hex_position.x)
            completed = (here[0] + delta[0], here[1] + delta[1]) in occupied
            for cell in layer.cell_construction_datas:
                local = (cell.local_hex_position.y, cell.local_hex_position.x)
                tally["tiles_total"] += 1
                if local in seams:
                    tally["seam_completed" if completed else "seam_incomplete"] += 1
                    if not completed:
                        tally[f"offender:{path.stem}@{here}:{local}"] += 1
                elif local in flush:
                    tally["flush_completed" if completed else "flush_incomplete"] += 1
    return tally


def report(tally: collections.Counter) -> None:
    delta = find_tiling_delta(frozenset(MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]))
    print("Half-hole placement in the shared-course corpus\n")
    print(f"  derived half-hole cells   : {sorted(seam_cells())}")
    print(f"  derived control cells     : {sorted(flush_edge_cells())}")
    print(f"  completing plate delta    : {delta}\n")
    print(f"  courses parsed            : {tally['parsed']}")
    print(f"  tiles on baseplates       : {tally['tiles_total']}\n")
    print(f"  half-hole, NOT completed  : {tally['seam_incomplete']}   <-- predicted 0")
    print(f"  half-hole, completed      : {tally['seam_completed']}")
    print(f"  whole hole, NOT completed : {tally['flush_incomplete']}   <-- control")
    print(f"  whole hole, completed     : {tally['flush_completed']}")

    if not tally["flush_incomplete"]:
        print(
            "\n  CONTROL FAILED: no tile anywhere sits on an edge cell of an "
            "uncompleted plate, so a zero above measures nothing."
        )
        return
    offenders = sorted(k for k in tally if k.startswith("offender:"))
    if offenders:
        print("\n  exceptions:")
        for key in offenders:
            print(f"    {key.removeprefix('offender:')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path.home() / "Claude" / "Projects" / "traxgen-corpus" / "raw",
    )
    args = parser.parse_args(argv)
    if not args.corpus_dir.is_dir():
        print(f"error: no such corpus dir {args.corpus_dir}", file=sys.stderr)
        return 2
    tally = scan(args.corpus_dir)
    if not tally["parsed"]:
        print(f"error: no parseable courses in {args.corpus_dir}", file=sys.stderr)
        return 2
    report(tally)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
