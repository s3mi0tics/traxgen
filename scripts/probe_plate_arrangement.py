# Path: traxgen/scripts/probe_plate_arrangement.py
"""Measure how real courses arrange their baseplates (open unknowns #16, #17).

`probe_plate_footprint.py` measures what one plate *is* -- which local cells it
occupies. This measures how plates *sit together*: how many a course carries,
which world positions they take, and whether the footprints tile or collide.

Same discipline, same corpus, zero renders. The constant it emits lives in
`traxgen/plates.py` and is regenerated from here rather than hand-typed -- a
typed list of a measured set is an untested claim wearing a constant's clothes.

**Supersedes `scripts/probe_baseplate_arrangement.py`**, which asks these
questions of a single fixture and filters on `LayerKind.BASE_LAYER`. Run against
its own named fixture (GDZJZA3J3T) that filter matches **zero** layers -- the
fixture's 15 baseplates are all `BASE_LAYER_PIECE`, which `decisions.md`
(b8052e4) locked as a baseplate kind. Its overlap check then reports "No
overlaps across 0 world-hex positions", a green over an empty set. Retiring it
is a decision for a human, so it is left in place and named here.

Run:
    uv run python -m scripts.probe_plate_arrangement ~/Claude/Projects/traxgen-corpus/raw

Path: traxgen/scripts/probe_plate_arrangement.py
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from traxgen.parser import parse_course
from traxgen.plates import MEASURED_FOOTPRINTS
from traxgen.types import LayerKind

if TYPE_CHECKING:
    from traxgen.domain import Course

# Same skip policy as probe_plate_footprint.py: by declared version, recorded
# rather than swallowed. v1/v2 are a separate schema family the v4-path reader
# misparses into garbage; v7 (SkyTrax) needs the parser sequenced as plan.md
# item 5.
UNSUPPORTED_VERSIONS = frozenset({1, 2, 7})

PlatePositions = tuple[tuple[int, int], ...]


def plate_positions(course: Course) -> PlatePositions:
    """The world positions of a course's `BASE_LAYER_PIECE` layers, in file order."""
    return tuple(
        (layer.world_hex_position.y, layer.world_hex_position.x)
        for layer in course.layer_construction_data
        if layer.layer_kind is LayerKind.BASE_LAYER_PIECE
    )


def footprint_collisions(positions: PlatePositions) -> int:
    """How many world cells two plates in this arrangement would both claim."""
    footprint = MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]
    cells = [(py + fy, px + fx) for py, px in positions for fy, fx in footprint]
    return len(cells) - len(set(cells))


def pairwise_deltas(positions: PlatePositions) -> list[tuple[int, int]]:
    """Every ordered plate-to-plate world offset within one arrangement.

    Paired by *index*, not by value: two plates at the same world position are
    a real (degenerate) arrangement that `footprint_collisions` is written to
    catch, and value-distinctness would silently drop them to no delta at all.
    """
    return [
        (b[0] - a[0], b[1] - a[1])
        for i, a in enumerate(positions)
        for j, b in enumerate(positions)
        if i != j
    ]


def normalised(positions: PlatePositions) -> PlatePositions:
    """`positions` translated so its minimum sits at the origin.

    Two arrangements are the same *shape* when their normalised forms are
    equal. Without this the claim "the remaining sets are this shape
    translated" is unverifiable prose sitting inside a generated constant.
    """
    if not positions:
        return ()
    oy, ox = min(positions)
    return tuple(sorted((y - oy, x - ox) for y, x in positions))


def scan(corpus_dir: Path) -> tuple[list[PlatePositions], collections.Counter]:
    """Return (one plate-position tuple per parsed course, a parse tally).

    The tally also carries figures cited elsewhere in the library --
    `plates_total`, `plates_empty`, a `height=` count per distinct
    `layer_height`, and a `kind=` count per `LayerKind` -- so they are
    regenerable rather than remembered.

    The `kind=` counts were added 2026-08-24 (s25) for a claim that had none.
    `graph.py` cites "zero of the 640 parsed corpus courses use `BASE_LAYER`",
    which nothing in the repo could produce: this script filtered
    `BASE_LAYER_PIECE` before counting, and `probe_plate_footprint.py` tallies
    kinds only from within `cell_construction_datas`, so an **empty** layer --
    exactly the shape at issue -- is invisible to it. Counting every layer's
    kind, cells or not, is what makes the sentence checkable (observations
    #24: an artifact can be durable and a claim still un-rerunnable).
    """
    arrangements: list[PlatePositions] = []
    tally: collections.Counter = collections.Counter()
    for path in sorted(corpus_dir.glob("*.course")):
        data = path.read_bytes()
        version = int.from_bytes(data[16:20], "little")
        if version in UNSUPPORTED_VERSIONS:
            tally[f"skipped(v{version})"] += 1
            continue
        try:
            course = parse_course(data)
        except Exception as exc:  # skip-and-record; never invent an arrangement
            tally[f"skipped({type(exc).__name__})"] += 1
            continue
        tally["parsed"] += 1
        arrangements.append(plate_positions(course))
        kinds_here = {layer.layer_kind for layer in course.layer_construction_data}
        for kind in kinds_here:
            tally[f"courses_with_kind={kind.name}"] += 1
        for layer in course.layer_construction_data:
            tally[f"layers_of_kind={layer.layer_kind.name}"] += 1
            if layer.layer_kind is not LayerKind.BASE_LAYER_PIECE:
                continue
            tally["plates_total"] += 1
            if not layer.cell_construction_datas:
                tally["plates_empty"] += 1
            tally[f"height={round(layer.layer_height, 4)}"] += 1
    return arrangements, tally


def report(arrangements: list[PlatePositions], tally: collections.Counter) -> None:
    """Print the measured distribution, the modal arrangement, and the constant."""
    print(f"tally: {dict(tally)}\n")

    counts = collections.Counter(len(a) for a in arrangements)
    multi = sum(n for size, n in counts.items() if size >= 2)
    print(f"=== plates per course (n={len(arrangements)}) ===")
    for size in sorted(counts):
        print(f"    {size:>3} plates: {counts[size]:>4} courses")
    print(f"    -> multi-plate: {multi} of {len(arrangements)}\n")

    collisions = sum(1 for a in arrangements if footprint_collisions(a))
    print("=== footprint overlap between plates of one course ===")
    print(f"    courses with any collision: {collisions} of {len(arrangements)}")
    print("    (zero means `world + local` is a coherent global frame)\n")

    deltas = collections.Counter()
    for arrangement in arrangements:
        deltas.update(pairwise_deltas(arrangement))
    print(f"=== pairwise plate deltas: {len(deltas)} distinct, top 8 ===")
    for delta, n in deltas.most_common(8):
        print(f"    {delta!s:>12}: {n:>6}")
    print()

    sets = collections.Counter(tuple(sorted(a)) for a in arrangements if len(a) == 4)
    print(f"=== four-plate arrangements: {len(sets)} distinct sets ===")
    for positions, n in sets.most_common(4):
        print(f"    {n:>4}x  {list(positions)}")
    if sets:
        modal_shape = normalised(sets.most_common(1)[0][0])
        same_shape = sum(1 for s in sets if normalised(s) == modal_shape)
        print(
            f"    of the {len(sets)} distinct sets, {same_shape} are the modal "
            f"shape translated and {len(sets) - same_shape} are not"
        )
    print()

    print("=== per-plate tallies (cited by traxgen/layout.py) ===")
    print(f"    plates total: {tally['plates_total']}")
    print(f"    plates with zero cells: {tally['plates_empty']}")
    for key in sorted(k for k in tally if k.startswith("height=")):
        print(f"    {key}: {tally[key]}")
    print()

    # Counted over every layer, empty ones included -- which is the whole point:
    # the claim this produces is about an empty BASE_LAYER, and a cell-driven
    # tally cannot see one. Cited by traxgen/graph.py.
    print("=== layer kinds across the corpus (cited by traxgen/graph.py) ===")
    print(f"    courses parsed: {tally['parsed']}")
    for key in sorted(k for k in tally if k.startswith("courses_with_kind=")):
        print(f"    {key.split('=')[1]}: in {tally[key]} courses, "
              f"{tally['layers_of_kind=' + key.split('=')[1]]} layers")
    print()

    if sets:
        modal, modal_n = sets.most_common(1)[0]
        print("=== paste into traxgen/plates.py ===")
        print(f"# STANDARD_SQUARE: {modal_n} of {sum(sets.values())} four-plate courses")
        print("STANDARD_SQUARE: tuple[tuple[int, int], ...] = (")
        for position in modal:
            print(f"    {position},")
        print(")")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "corpus_dir",
        type=Path,
        help="directory of .course files (outside the repo, per the corpus policy)",
    )
    args = parser.parse_args(argv)
    if not args.corpus_dir.is_dir():
        print(f"error: {args.corpus_dir} is not a directory", file=sys.stderr)
        return 1
    arrangements, tally = scan(args.corpus_dir)
    if not arrangements:
        print(f"error: no parseable courses in {args.corpus_dir}", file=sys.stderr)
        return 1
    report(arrangements, tally)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
