# Path: traxgen/scripts/probe_plate_footprint.py
"""Measure each LayerKind's cell footprint from the course corpus (open unknown #3).

`probe_plate_membership.py` bakes the BASE_LAYER_PIECE footprint into a constant
so the probe can run without the corpus attached. This script is where that
constant comes from, and re-running it is how the constant gets checked: per the
2026-08-18 corpus policy, the binaries stay out of the repo and reproducibility
comes from committed scripts pointing at the source.

Positive evidence only. The output is the set of local_hex_positions the corpus
actually shows occupied on each layer kind. A position absent from that set has
never been observed in hundreds of courses -- which is strong, and is still not
a proof that the app forbids it. Turning "never observed" into "rejected" takes
a render; that is what `probe_plate_membership.py` spends eight of them on.

Skips are by declared version and are recorded rather than swallowed: v1/v2 are
a separate schema family (murmelbahn `ziplineadded2019.rs`) that the v4-path
reader misparses into garbage, and v7 (SkyTrax) needs the parser that is
sequenced as plan.md item 5.

Run:
    uv run python -m scripts.probe_plate_footprint ~/Claude/Projects/traxgen-corpus/raw

Path: traxgen/scripts/probe_plate_footprint.py
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

from traxgen.hex import HEX_DIRECTIONS
from traxgen.parser import parse_course

DIRECTION_NAMES = ("E", "NE", "NW", "W", "SW", "SE")

# Version families this reader cannot parse, skipped by declared version rather
# than by catching the garbage they would otherwise produce.
UNSUPPORTED_VERSIONS = frozenset({1, 2, 7})


def scan(corpus_dir: Path) -> tuple[dict[str, collections.Counter], collections.Counter]:
    """Return (positions used per LayerKind, a tally of parsed/skipped courses)."""
    by_kind: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    tally: collections.Counter = collections.Counter()
    for path in sorted(corpus_dir.glob("*.course")):
        data = path.read_bytes()
        version = int.from_bytes(data[16:20], "little")
        if version in UNSUPPORTED_VERSIONS:
            tally[f"skipped(v{version})"] += 1
            continue
        try:
            course = parse_course(data)
        except Exception as exc:  # skip-and-record; never invent a footprint
            tally[f"skipped({type(exc).__name__})"] += 1
            continue
        tally["parsed"] += 1
        for layer in course.layer_construction_data:
            for cell in layer.cell_construction_datas:
                pos = cell.local_hex_position
                by_kind[layer.layer_kind.name][(pos.y, pos.x)] += 1
    return by_kind, tally


def report(by_kind: dict[str, collections.Counter], tally: collections.Counter) -> None:
    """Print the footprint of each layer kind and the neighbours of its local origin."""
    print(f"tally: {dict(tally)}\n")
    for kind, counter in sorted(by_kind.items(), key=lambda kv: -sum(kv[1].values())):
        positions = sorted(counter)
        ys = [y for y, _ in positions]
        xs = [x for _, x in positions]
        print(
            f"=== {kind}: {len(positions)} distinct positions, "
            f"{sum(counter.values())} placements, "
            f"y {min(ys)}..{max(ys)}  x {min(xs)}..{max(xs)} ==="
        )
        for pos in positions:
            print(f"    {pos}: {counter[pos]}")
        print()

    print("=== neighbours of local (0,0) ===")
    print("    a zero here is a cell the corpus never shows occupied")
    for kind, counter in sorted(by_kind.items(), key=lambda kv: -sum(kv[1].values())):
        cells = "  ".join(
            f"{d}:{DIRECTION_NAMES[d]}={counter.get((dy, dx), 0)}"
            for d, (dy, dx) in enumerate(HEX_DIRECTIONS)
        )
        print(f"  {kind}: origin={counter.get((0, 0), 0)} | {cells}")


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
    by_kind, tally = scan(args.corpus_dir)
    if not by_kind:
        print(f"error: no parseable courses in {args.corpus_dir}", file=sys.stderr)
        return 1
    report(by_kind, tally)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
