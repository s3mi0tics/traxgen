"""Probe: which GOAL_BASIN rotations catch a marble from the East? (s52-t17)

    uv run python -m scripts.probe_goal_basin --build-only   # build and check, no upload
    uv run python -m scripts.probe_goal_basin                # build, upload, print the code

One standard-square board, six tests: a launch pad at rotation 0 and, on its
East side, a GOAL_BASIN at rotation 0 to 5. The marble travels East into the
basin's world side 3, which is piece side `(3 - rotation) % 6`. The corpus puts
the basin's rail entrances on piece sides 0, 2, 4 (s52-t13), so rotations 1, 3,
5 should catch and 0, 2, 4 should leave their pad with no valid connection, no
marble loaded (s44). Read the run with `probe_finish_frames --link <code>` and
`read_trail_ends <frames> screenshots/ring_board/goal_basin.json`.

Path: traxgen/scripts/probe_goal_basin.py
"""

from __future__ import annotations

import argparse
import hashlib
import json

from scripts.probe_two_marbles import placements
from scripts.ring_board import OUT_DIR
from traxgen.hex import HexVector
from traxgen.layout import build_course
from traxgen.plates import STANDARD_SQUARE
from traxgen.ring_board import hex_distance, is_buildable, under_toolbar
from traxgen.serializer import serialize_course
from traxgen.types import TileKind

EAST = 0
SPACING = 3  # between tiles of different tests: two empty cells
CORPUS_ENTRANCES = frozenset({0, 2, 4})  # GOAL_BASIN piece sides, s52-t13

Placed = list[tuple[TileKind, HexVector, int]]


def entered_side(rotation: int) -> int:
    """The basin's piece side a marble travelling East enters by."""
    return (EAST + 3 - rotation) % 6


def predicted_catch(rotation: int) -> bool:
    return entered_side(rotation) in CORPUS_ENTRANCES


def tiles_for(pad: HexVector, rotation: int) -> Placed:
    return [(TileKind.STARTER, pad, 0), (TileKind.GOAL_BASIN, pad.neighbor(EAST), rotation)]


def layout(plates: tuple[HexVector, ...]) -> list[tuple[int, Placed]]:
    """One test per rotation, placed greedily: every tile buildable, on screen, and apart."""
    candidates = sorted(
        {p + HexVector(y=y, x=x) for p in plates for y in range(-6, 1) for x in range(6)},
        key=lambda c: (c.y, c.x),
    )
    out: list[tuple[int, Placed]] = []
    for pad in candidates:
        rotation = len(out)
        if rotation == 6:
            break
        placed = tiles_for(pad, rotation)
        if not all(is_buildable(plates, c) and not under_toolbar(c) for _, c, _ in placed):
            continue
        taken = [c for _, other in out for _, c, _ in other]
        if any(hex_distance(c, t) < SPACING for _, c, _ in placed for t in taken):
            continue
        out.append((rotation, placed))
    if len(out) < 6:
        raise ValueError(f"only {len(out)} of 6 tests fit")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-only", action="store_true", help="no upload")
    args = parser.parse_args(argv)

    plates = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)
    tests = layout(plates)
    tiles = [t for _, placed in tests for t in placements(plates, placed)]
    data = serialize_course(
        build_course(plate_world_positions=plates, tiles=tiles, title="traxgen-goal-basin")
    )
    manifest: dict[str, object] = {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "tests": [
            {
                "name": f"rot{rotation}",
                "entered_side": entered_side(rotation),
                "predicted_catch": predicted_catch(rotation),
                "tiles": [[kind.name, [c.y, c.x], r] for kind, c, r in placed],
            }
            for rotation, placed in tests
        ],
    }
    if not args.build_only:
        from traxgen.uploader import upload_course_with_retry

        manifest["code"], _attempts = upload_course_with_retry(data)
    for test in manifest["tests"]:  # type: ignore[union-attr]
        print(test)
    print(f"bytes={manifest['bytes']} code={manifest.get('code')}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "goal_basin.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
