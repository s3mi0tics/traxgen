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
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from scripts import probe_plate_seams
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


def lattice_basis_from(
    deltas: Iterable[tuple[int, int]],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Two generators of the lattice `deltas` lie on, or a refusal.

    "The plate positions form a lattice" is a structural claim about *observed*
    arrangements, and this is the check for it: take the two shortest
    independent observed deltas and verify every other observed delta is an
    integer combination of them. If one is not, the observations do not form a
    rank-2 lattice with that basis and the function raises rather than returning
    a basis most of the data happens to satisfy.

    Derived from the corpus rather than from the footprint, and that was the
    second attempt. The first derived it from `probe_plate_seams.tiling_deltas`
    -- and refused to generate, because the gapless test there is one-axis and
    admits 116 translations including `(-4,-2)` and `(0,±6)`, which are off the
    lattice real courses use. The refusal was correct and it is why that
    function's docstring now says what it actually enumerates (s27). The basis
    named in `plan.md` and `vision.md` was prose with no instrument behind it
    until this existed (observations #24).
    """
    ordered = sorted(set(deltas), key=lambda d: (abs(d[0]) + abs(d[1]), d))
    ordered = [d for d in ordered if d != (0, 0)]
    if not ordered:
        raise ValueError("no non-zero deltas: nothing to derive a lattice from")
    first = ordered[0]
    second = next(
        (d for d in ordered if first[0] * d[1] - first[1] * d[0] != 0), None
    )
    if second is None:
        raise ValueError(f"every delta is collinear with {first}: rank 1, not a lattice")
    for delta in ordered:
        if not on_lattice(delta, (first, second)):
            raise ValueError(
                f"observed delta {delta} is not generated by {first} and {second} -- "
                "these arrangements do not form a lattice with that basis"
            )
    return first, second


def on_lattice(
    delta: tuple[int, int], basis: tuple[tuple[int, int], tuple[int, int]]
) -> bool:
    """Is `delta` an integer combination of the two basis vectors?

    Cramer's rule with exact integer division: a delta is on the lattice iff
    both coefficients come out whole. Float division would make a near-miss
    read as a hit, which is the direction that invents agreement.
    """
    (uy, ux), (vy, vx) = basis
    det = uy * vx - ux * vy
    if det == 0:
        raise ValueError(f"basis {basis} is degenerate")
    a_num = delta[0] * vx - delta[1] * vy
    b_num = uy * delta[1] - ux * delta[0]
    return a_num % det == 0 and b_num % det == 0


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

    print("=== do the observed arrangements form a lattice? ===")
    try:
        basis = lattice_basis_from(deltas)
    except ValueError as exc:
        print(f"    NO: {exc}")
    else:
        print(f"    YES, basis {basis} -- every one of the {len(deltas)} distinct")
        print("    observed deltas is an integer combination of those two.")
        completing = probe_plate_seams.find_tiling_delta(
            frozenset(MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE])
        )
        mark = "on" if on_lattice(completing, basis) else "OFF"
        print(f"    the footprint's completing delta {completing} is {mark} it")
        print("    (two independent derivations from the same corpus: the lattice")
        print("     from arrangement counts, the completing delta from cell geometry)")
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
