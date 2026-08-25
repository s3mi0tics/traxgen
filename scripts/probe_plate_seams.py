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

**Two controls, on two different axes**, because one answers only half the
question (observations #21: ask what a null would prove).

- `flush_edge_cells` -- the whole holes at the *same* edge. If nobody builds at
  a plate edge at all, "zero on half-holes" measures nothing. Non-empty is what
  makes the result mean anything.
- `mirror_edge_cells` -- the outermost cells of the *opposite* edge. The
  footprint is mirror-symmetric in column, and `seam_cells` picks the maximum
  without arguing why. If builders avoided the minimum edge equally, the
  derivation would be choosing a side the evidence does not support. Added s27.

**The tally is per cell as well as in aggregate**, because the three half-holes
are not interchangeable and the plate-level completion test cannot show it: one
delta answers for all three, while `seam_requirements` shows `(-2,5)` sits at
the seam's corner with off-plate neighbours no tiling neighbour reaches. A
single summed figure averages three facts and hides where an exception sits --
and the one exception the s26 run found is at `(-2,5)`.

Run: `uv run python -m scripts.probe_plate_seams --corpus-dir <dir>`

Path: traxgen/scripts/probe_plate_seams.py
"""

from __future__ import annotations

import argparse
import collections
import sys
from fractions import Fraction
from pathlib import Path

from traxgen.hex import DIRECTION_NAMES, HEX_DIRECTIONS
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


def translate(footprint: frozenset[Cell], delta: Cell) -> frozenset[Cell]:
    """The footprint moved by `delta` -- one plate's cells in another's frame."""
    return frozenset((y + delta[0], x + delta[1]) for y, x in footprint)


def find_tiling_delta(footprint: frozenset[Cell]) -> Cell:
    """The translation that places the *completing* plate immediately alongside.

    Derived by search rather than named: the delta leaves the two footprints
    disjoint *and* leaves no gap between them, which is what "the plates butt
    together" means in coordinates. Searching rather than hardcoding is what
    lets this file carry no copy of `STANDARD_SQUARE`.

    The **side** is derived too, and it was not before. The plate tiles equally
    well on either side -- `(5,0)` and `(-5,0)` are both gapless and both at
    distance 5 -- so the nearest-first tie-break cannot separate them, and an
    earlier version picked the seam side by searching `dy > 0` only. Lifting
    that bound makes `(-5,0)` sort first and inverts every `completed` verdict
    in `scan()` below, which is a loop bound doing load-bearing work while
    reading as a search range (s27; observations #12). What actually picks the
    side is the property the neighbour is wanted for: only the plate on the
    seam side reaches *past* the boundary column, so only it can supply the
    missing halves. Filter on that, then take the nearest.
    """
    seam_column = max(column_centre(cell) for cell in footprint)
    candidates = [
        delta
        for delta in tiling_deltas(footprint)
        if max(column_centre(cell) for cell in translate(footprint, delta)) > seam_column
    ]
    if not candidates:
        raise ValueError("no gapless completing translation found for this footprint")
    # Nearest first: a further-away plate that happens to tile is a multiple.
    return min(candidates, key=lambda d: (abs(d[0]) + abs(d[1]), d))


def tiling_deltas(footprint: frozenset[Cell]) -> list[Cell]:
    """Every translation that leaves the two footprints disjoint and gapless.

    **Not** "every way two plates really abut", and the difference matters. The
    gapless test is one-axis (see `_is_gapless`), so it admits **116** deltas for
    the measured footprint, of which only a few are edge-to-edge tilings: `(-4,
    -2)`, `(0,±6)` and `(0,±7)` all pass while lying off the lattice that real
    arrangements actually use. Measured s27, when deriving that lattice from
    this set was tried and refused to generate -- which is how the looseness
    surfaced. So this is a *superset* of the tilings, sound for
    `find_tiling_delta` (which takes the nearest completing-side member, and the
    spurious ones are all farther or on the flush side) and unsound as a
    definition of the lattice. `probe_plate_arrangement` derives that from the
    corpus instead.
    """
    span = max(abs(v) for cell in footprint for v in cell) + 2
    out = []
    for dy in range(-span, span + 1):
        for dx in range(-span, span + 1):
            if (dy, dx) == (0, 0):
                continue
            moved = translate(footprint, (dy, dx))
            if moved & footprint:
                continue
            if not _is_gapless(set(footprint | moved)):
                continue
            out.append((dy, dx))
    return out


def _is_gapless(cells: set[Cell]) -> bool:
    """Every row (constant x) of the union is a contiguous run of y.

    One axis, deliberately: the union of two plates that abut along the seam is
    checked for holes *between* them, and the seam runs along x. Stated as what
    it does rather than as "no gaps anywhere", which it does not check.
    """
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


def mirror_edge_cells(kind: LayerKind = LayerKind.BASE_LAYER_PIECE) -> frozenset[Cell]:
    """The outermost cells of the OPPOSITE edge -- the mirror control.

    The footprint is mirror-symmetric in column: three cells reach the maximum
    column and three reach the minimum, on the same alternating rows. Nothing in
    `seam_cells` argues why the maximum is the bisected edge rather than the
    minimum -- it takes `max` and says the boundary sits there.

    There is a correct argument and the code did not make it: hole centres span
    4 column-units while the tiling delta is 5, so exactly one hole-width of
    surplus plate material sits across the two edges, and a gapless abutment
    forces all of it onto one side. But an argument is not a measurement, so
    this group exists to be measured. If builders avoid the minimum edge the way
    they avoid the maximum, the derivation is picking a side the evidence does
    not support; if they use it freely, `max` is vindicated by something other
    than taste.

    Distinct from `flush_edge_cells`, which controls for "do builders use edge
    cells at all" on the *same* edge. This controls for "is this edge special".
    """
    footprint = frozenset(MEASURED_FOOTPRINTS[kind])
    edge = min(column_centre(cell) for cell in footprint)
    return frozenset(cell for cell in footprint if column_centre(cell) == edge)


def seam_requirements(
    kind: LayerKind = LayerKind.BASE_LAYER_PIECE,
) -> dict[Cell, tuple[frozenset[int], frozenset[int]]]:
    """Per half-hole: which off-plate neighbours the completing plate supplies.

    Returns `{cell: (supplied, unreachable)}` as direction indices.

    The three half-holes are **not interchangeable**, and a single plate-level
    test ("is there a plate at `here + delta`") cannot show it, because the same
    delta answers for all three. Derived here rather than asserted: `(0,1)` and
    `(-1,3)` each have three off-plate neighbours and the completing plate
    supplies all three, while `(-2,5)` sits at the *corner* of the seam and has
    four, of which the completing plate supplies two -- its E and NE neighbours
    lie past the plate corner, where no single tiling neighbour reaches.

    That asymmetry is why `report()` breaks the tally out per cell. The one
    corpus exception the s26 run found sits at `(-2,5)`, which is the cell whose
    completion condition the single-delta test speaks to least (s27).
    """
    footprint = frozenset(MEASURED_FOOTPRINTS[kind])
    delta = find_tiling_delta(footprint)
    neighbour = translate(footprint, delta)
    out: dict[Cell, tuple[frozenset[int], frozenset[int]]] = {}
    for cell in sorted(seam_cells(kind)):
        supplied, unreachable = set(), set()
        for index, (dy, dx) in enumerate(HEX_DIRECTIONS):
            here = (cell[0] + dy, cell[1] + dx)
            if here in footprint:
                continue
            (supplied if here in neighbour else unreachable).add(index)
        out[cell] = (frozenset(supplied), frozenset(unreachable))
    return out


def cell_groups(kind: LayerKind = LayerKind.BASE_LAYER_PIECE) -> dict[Cell, str]:
    """Every cell the scan counts, mapped to which group it belongs to.

    Built rather than branched on in the loop so the three groups can be checked
    disjoint here, once. An overlap would silently make one group measure part
    of another -- the failure the control exists to prevent, one level down.
    """
    groups: dict[Cell, str] = {}
    for name, cells in (
        ("seam", seam_cells(kind)),
        ("flush", flush_edge_cells(kind)),
        ("mirror", mirror_edge_cells(kind)),
    ):
        for cell in cells:
            if cell in groups:
                raise ValueError(
                    f"cell {cell} is in both '{groups[cell]}' and '{name}' -- "
                    "the groups must be disjoint or each measures the other"
                )
            groups[cell] = name
    return groups


def scan(corpus_dir: Path) -> collections.Counter:
    """Tally tiles by cell class and by whether the completing plate is present."""
    delta = find_tiling_delta(frozenset(MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]))
    groups = cell_groups()
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
                group = groups.get(local)
                if group is None:
                    continue
                state = "completed" if completed else "incomplete"
                tally[f"{group}_{state}"] += 1
                if group == "seam":
                    # Per cell as well as in aggregate: the three half-holes have
                    # different completion geometry (`seam_requirements`), so one
                    # summed figure averages three facts and hides where an
                    # exception sits. The s26 run's lone exception is at (-2,5).
                    tally[f"seamcell{local}_{state}"] += 1
                    if not completed:
                        tally[f"offender:{path.stem}@{here}:{local}"] += 1
    return tally


def report(tally: collections.Counter) -> None:
    delta = find_tiling_delta(frozenset(MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]))
    print("Half-hole placement in the shared-course corpus\n")
    print(f"  derived half-hole cells   : {sorted(seam_cells())}")
    print(f"  same-edge control cells   : {sorted(flush_edge_cells())}")
    print(f"  opposite-edge control     : {sorted(mirror_edge_cells())}")
    print(f"  completing plate delta    : {delta}\n")

    print("  what the completing plate supplies, per half-hole:")
    for cell, (supplied, unreachable) in seam_requirements().items():
        got = ",".join(DIRECTION_NAMES[i] for i in sorted(supplied)) or "-"
        missed = ",".join(DIRECTION_NAMES[i] for i in sorted(unreachable))
        note = f"   beyond any tiling neighbour: {missed}" if missed else ""
        print(f"    {cell!s:>10}  supplies {got}{note}")
    print()

    print(f"  courses parsed            : {tally['parsed']}")
    print(f"  tiles on baseplates       : {tally['tiles_total']}\n")

    print("  half-holes, per cell (NOT completed <-- predicted 0):")
    for cell in sorted(seam_cells()):
        done = tally[f"seamcell{cell}_completed"]
        miss = tally[f"seamcell{cell}_incomplete"]
        print(f"    {cell!s:>10}  completed {done:>5}   NOT completed {miss:>5}")
    print()

    print(f"  half-hole, NOT completed  : {tally['seam_incomplete']}   <-- predicted 0")
    print(f"  half-hole, completed      : {tally['seam_completed']}")
    print(f"  whole hole, NOT completed : {tally['flush_incomplete']}   <-- same-edge control")
    print(f"  whole hole, completed     : {tally['flush_completed']}")
    print(f"  opposite edge, NOT compl. : {tally['mirror_incomplete']}   <-- mirror control")
    print(f"  opposite edge, completed  : {tally['mirror_completed']}")

    if not tally["flush_incomplete"]:
        print(
            "\n  CONTROL FAILED: no tile anywhere sits on an edge cell of an "
            "uncompleted plate, so a zero above measures nothing."
        )
        return

    if not tally["mirror_incomplete"]:
        print(
            "\n  MIRROR CONTROL FAILED: the opposite edge is avoided too, so "
            "'max is the bisected edge' is not what the corpus is showing."
        )
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
