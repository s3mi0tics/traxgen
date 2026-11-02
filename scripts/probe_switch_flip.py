"""Probe: does a marble passing a switch flip its lever for the next marble? (s48-t4)

    uv run python -m scripts.probe_switch_flip --build-only   # build and print, no upload
    uv run python -m scripts.probe_switch_flip                # build, upload, print the code

s48-t3 measured each switch with one marble: `SWITCH_LEFT` passes a marble
entering piece side 0 out side 2 and stops one entering side 4; `SWITCH_RIGHT`
is the mirror (4 passes, 0 stops). Here each switch sits at rotation 0, so piece
sides are world sides, and gets two launch pads: one on the side that passes,
next to the switch, and one on the side that stops, at the end of a straight
run of X-intersections, so its marble arrives second. If the first marble flips
the lever, the second one passes too and both leave by side 2. Each kind also gets a control with the
stopping pad alone, which should stop as in s48-t3.

No goals: the board is read from trails through `STANDARD_SQUARE_SCREEN` (D100).
Output: screenshots/ring_board/switch_flip_run<N>.json -- the code and every test's cells.

Path: traxgen/scripts/probe_switch_flip.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass

from scripts.ring_board import OUT_DIR
from traxgen.hex import HexVector
from traxgen.layout import TilePlacement, build_course, owning_plate
from traxgen.plates import STANDARD_SQUARE
from traxgen.ring_board import hex_distance, is_buildable, under_toolbar
from traxgen.serializer import serialize_course
from traxgen.track_graph import CROSS_TRACKS
from traxgen.types import TileKind

STARTER_PORTS = (0, 2, 4)  # at rotation 0; a rotation r adds r (#15)
SPACING = 3  # between any two tiles of different tests: two empty cells


@dataclass(frozen=True)
class Test:
    name: str
    kind: TileKind
    pass_side: int | None  # the switch side whose pad sits next to it, or None (control)
    stop_side: int  # the switch side reached through a curve


TESTS = (
    Test("left_pair", TileKind.SWITCH_LEFT, 0, 4),
    Test("left_stop_only", TileKind.SWITCH_LEFT, None, 4),
    Test("right_pair", TileKind.SWITCH_RIGHT, 4, 0),
    Test("right_stop_only", TileKind.SWITCH_RIGHT, None, 0),
)


def starter_rotation_facing(direction: int) -> int:
    """A launch pad rotation with a port in `direction`: 0 for even, 1 for odd."""
    return direction % 2


def tiles_for(test: Test, centre: HexVector, run: int) -> list[tuple[TileKind, HexVector, int]]:
    """The switch at rotation 0, its pads, and `run` straight X-intersections on the stopping
    side, so that pad's marble arrives later (Colby, s48: one curve was too short a delay)."""
    placed = [(test.kind, centre, 0)]
    if test.pass_side is not None:
        pad = centre.neighbor(test.pass_side)
        placed.append((TileKind.STARTER, pad, starter_rotation_facing(pad.direction_to(centre))))
    side = test.stop_side
    # The lowest rotation at which one of the X-intersection's measured straight tracks
    # (D099) lies along world sides `side` and `side + 3`.
    cross_rotation = min(
        r for r in range(6) if CROSS_TRACKS.get((side - r) % 6) == (side + 3 - r) % 6
    )
    cell = centre
    for _ in range(run):
        cell = cell.neighbor(side)
        placed.append((TileKind.CROSS, cell, cross_rotation))
    pad = cell.neighbor(side)
    placed.append((TileKind.STARTER, pad, starter_rotation_facing(pad.direction_to(cell))))
    return placed


def check_pads(placed: list[tuple[TileKind, HexVector, int]]) -> None:
    """Every launch pad port faces an empty cell except the one it feeds: one marble, one route."""
    cells = {cell: kind for kind, cell, _ in placed}
    for kind, cell, rotation in placed:
        if kind is not TileKind.STARTER:
            continue
        facing = [cell.neighbor((p + rotation) % 6) for p in STARTER_PORTS]
        occupied = [c for c in facing if c in cells]
        assert len(occupied) == 1, f"pad at {cell} faces {occupied}"


def layout(
    plates: tuple[HexVector, ...], run: int, wanted: tuple[Test, ...] = TESTS
) -> list[tuple[Test, HexVector, list]]:
    candidates = sorted(
        {p + HexVector(y=y, x=x) for p in plates for y in range(-6, 1) for x in range(6)},
        key=lambda c: (c.y, c.x),
    )
    out: list[tuple[Test, HexVector, list]] = []
    for centre in candidates:
        if len(out) == len(wanted):
            break
        test = wanted[len(out)]
        placed = tiles_for(test, centre, run)
        if not all(is_buildable(plates, c) and not under_toolbar(c) for _, c, _ in placed):
            continue
        taken = [c for _, _, other in out for _, c, _ in other]
        if any(hex_distance(c, t) < SPACING for _, c, _ in placed for t in taken):
            continue
        check_pads(placed)
        out.append((test, centre, placed))
    if len(out) < len(wanted):
        raise ValueError(f"only {len(out)} of {len(wanted)} tests fit with a run of {run}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-only", action="store_true", help="no upload")
    parser.add_argument("--pairs-only", action="store_true", help="drop the stop-only controls")
    parser.add_argument("--run", type=int, default=4, help="X-intersections before the far pad")
    args = parser.parse_args(argv)

    plates = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)
    wanted = tuple(t for t in TESTS if t.pass_side is not None or not args.pairs_only)
    tests = layout(plates, args.run, wanted)
    tiles = []
    for _, _, placed in tests:
        for kind, cell, rotation in placed:
            owner = owning_plate(plates, cell)
            assert owner is not None
            tiles.append(TilePlacement(kind, owner[0], owner[1], rotation))
    data = serialize_course(
        build_course(plate_world_positions=plates, tiles=tiles, title="traxgen-switch-flip")
    )
    manifest: dict[str, object] = {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "run": args.run,
        "tests": [
            {
                "name": test.name,
                "kind": test.kind.name,
                "centre": [centre.y, centre.x],
                "tiles": [[kind.name, [c.y, c.x], r] for kind, c, r in placed],
            }
            for test, centre, placed in tests
        ],
    }
    for test, centre, placed in tests:
        print(f"{test.name}: switch at ({centre.y}, {centre.x}); "
              + ", ".join(f"{k.name}@({c.y},{c.x}) r{r}" for k, c, r in placed[1:]))
    if not args.build_only:
        from traxgen.uploader import upload_course_with_retry

        code, _attempts = upload_course_with_retry(data)
        manifest["code"] = code
        print(f"code: {code}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"switch_flip_run{args.run}.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
