"""Build a ring test board for one piece, upload it, and write which ring is where (s46-t2).

    uv run python -m scripts.ring_board CURVE --build-only   # build and print, no upload
    uv run python -m scripts.ring_board CURVE                # build, upload, print the code
    uv run python -m scripts.ring_board CURVE --no-goals     # the same board, goals removed

Output: screenshots/ring_board/<KIND>.json (or <KIND>-nogoals.json) -- the share code, the course's
sha256, and per ring its rotation and the world cell of its piece, launch pad
and each goal by side. A per-goal finish reader needs that to say which goal a
burst came from.

Path: traxgen/scripts/ring_board.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from traxgen.android import DEFAULT_SCREENSHOT_DIR
from traxgen.ring_board import ring_board
from traxgen.serializer import serialize_course
from traxgen.types import TileKind

OUT_DIR = Path(DEFAULT_SCREENSHOT_DIR) / "ring_board"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", help="a TileKind name, e.g. CURVE")
    parser.add_argument("--build-only", action="store_true", help="no upload")
    parser.add_argument("--no-goals", action="store_true", help="the same board without its goals")
    args = parser.parse_args(argv)

    board = ring_board(TileKind[args.kind], goals=not args.no_goals)
    data = serialize_course(board.course)
    manifest: dict[str, object] = {
        "kind": board.kind.name,
        "goals": not args.no_goals,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "plates": [[p.y, p.x] for p in board.plates],
        "rings": [
            {
                "rotation": r.rotation,
                "centre": [r.centre.y, r.centre.x],
                "starter": [r.starter.y, r.starter.x],
                "goals": {str(side): [c.y, c.x] for side, c in r.goals.items()},
            }
            for r in board.rings
        ],
    }
    for ring in manifest["rings"]:  # type: ignore[union-attr]
        print(f"rotation {ring['rotation']}: piece at {ring['centre']}")
    if not args.build_only:
        from traxgen.uploader import upload_course_with_retry

        code, _attempts = upload_course_with_retry(data)
        manifest["code"] = code
        print(f"code: {code}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{board.kind.name}{'' if not args.no_goals else '-nogoals'}.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
