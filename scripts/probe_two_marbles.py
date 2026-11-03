"""Probe: how many marbles does a two-connection launch pad load, and in what order? (s50)

    uv run python -m scripts.probe_two_marbles --build-only   # build and print, no upload
    uv run python -m scripts.probe_two_marbles                # build, upload, print the code

The app loads a marble only where the launch pad has a valid connection
(Colby, s44), and the checker refuses a two-connection pad on a course with a
switch because nobody has measured how many marbles load or which leaves first
(D104, #27). Here each test is one launch pad at rotation 0 using two of its
three ports, {0,2}, {2,4} or {0,4}; the third faces an empty cell. Each used
port runs through the same number of straight X-intersections (D099) into its
own goal rail, so travel time is the same on both routes: in a frame where one
trail is longer than the other, that marble left first. One test per port pair,
so an order that follows the port would show as a pattern across the three.

The board is read from trails through `STANDARD_SQUARE_SCREEN` (D100).
Output: screenshots/ring_board/two_marbles_run<N>.json -- the code and every test's cells.

Path: traxgen/scripts/probe_two_marbles.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass

from scripts.ring_board import OUT_DIR
from traxgen.graph import goal_rotation_for
from traxgen.hex import HexVector
from traxgen.layout import TilePlacement, build_course, owning_plate
from traxgen.plates import STANDARD_SQUARE
from traxgen.ring_board import hex_distance, is_buildable, under_toolbar
from traxgen.serializer import serialize_course
from traxgen.track_graph import CROSS_TRACKS
from traxgen.types import TileKind

STARTER_PORTS = (0, 2, 4)  # at rotation 0 (#15)
SPACING = 3  # between any two tiles of different tests: two empty cells

Placed = list[tuple[TileKind, HexVector, int]]


@dataclass(frozen=True)
class PadTest:
    name: str
    ports: tuple[int, int]  # the launch pad's two used ports, as world sides


TESTS = (
    PadTest("ports_0_2", (0, 2)),
    PadTest("ports_2_4", (2, 4)),
    PadTest("ports_0_4", (0, 4)),
)


def cross_rotation_along(side: int) -> int:
    """The lowest X-intersection rotation with a measured track along `side` and `side + 3`."""
    return min(r for r in range(6) if CROSS_TRACKS.get((side + 3 - r) % 6) == (side - r) % 6)


def tiles_for(test: PadTest, pad: HexVector, run: int) -> Placed:
    """The pad at rotation 0, then for each used port `run` X-intersections and a goal rail."""
    placed: Placed = [(TileKind.STARTER, pad, 0)]
    for side in test.ports:
        cell = pad
        for _ in range(run):
            cell = cell.neighbor(side)
            placed.append((TileKind.CROSS, cell, cross_rotation_along(side)))
        placed.append((TileKind.GOAL_RAIL, cell.neighbor(side), goal_rotation_for(side)))
    return placed


def layout(
    plates: tuple[HexVector, ...], run: int, wanted: tuple[PadTest, ...] = TESTS
) -> list[tuple[PadTest, Placed]]:
    """Place the tests greedily, each cell taking the first unplaced test that fits there:
    every tile buildable, on screen, and apart. Returned in `wanted`'s order."""
    candidates = sorted(
        {p + HexVector(y=y, x=x) for p in plates for y in range(-6, 1) for x in range(6)},
        key=lambda c: (c.y, c.x),
    )
    out: list[tuple[PadTest, Placed]] = []
    for pad in candidates:
        for test in wanted:
            if any(test is done for done, _ in out):
                continue
            placed = tiles_for(test, pad, run)
            if not all(is_buildable(plates, c) and not under_toolbar(c) for _, c, _ in placed):
                continue
            taken = [c for _, other in out for _, c, _ in other]
            if any(hex_distance(c, t) < SPACING for _, c, _ in placed for t in taken):
                continue
            out.append((test, placed))
            break
    if len(out) < len(wanted):
        raise ValueError(f"only {len(out)} of {len(wanted)} tests fit with a run of {run}")
    return sorted(out, key=lambda tp: wanted.index(tp[0]))


def placements(plates: tuple[HexVector, ...], placed: Placed) -> list[TilePlacement]:
    """World cells to plate-local placements, each on the plate that owns it."""
    tiles = []
    for kind, cell, rotation in placed:
        owner = owning_plate(plates, cell)
        assert owner is not None
        tiles.append(TilePlacement(kind, owner[0], owner[1], rotation))
    return tiles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-only", action="store_true", help="no upload")
    parser.add_argument(
        "--run", type=int, default=2, help="X-intersections per route (3 fits one test)"
    )
    args = parser.parse_args(argv)

    plates = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)
    tests = layout(plates, args.run)
    tiles = [t for _, placed in tests for t in placements(plates, placed)]
    data = serialize_course(
        build_course(plate_world_positions=plates, tiles=tiles, title="traxgen-two-marbles")
    )
    manifest: dict[str, object] = {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "run": args.run,
        "tests": [
            {
                "name": test.name,
                "ports": list(test.ports),
                "tiles": [[kind.name, [c.y, c.x], r] for kind, c, r in placed],
            }
            for test, placed in tests
        ],
    }
    for test, placed in tests:
        print(f"{test.name}: " + ", ".join(f"{k.name}@({c.y},{c.x}) r{r}" for k, c, r in placed))
    if not args.build_only:
        from traxgen.uploader import upload_course_with_retry

        code, _attempts = upload_course_with_retry(data)
        manifest["code"] = code
        print(f"code: {code}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"two_marbles_run{args.run}.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
