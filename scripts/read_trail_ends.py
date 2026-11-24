"""Where each marble's trail ends, read from the frame before play and the last frame (s52-t4).

Path: traxgen/scripts/read_trail_ends.py

Plan item 24 (b): a second finish reading beside the sparkle count, for runs
whose frames were too far apart to catch the burst (s52-t2). Standard square
only: cells reach the screen through `ring_board.screen_position` (D100).

A trail is pixels that changed between `before.png` and the last frame, split
into 8-connected pieces. The launch pad's raised top hides a trail's first
stretch, so a piece belongs to a pad when any of its pixels is within NEAR_PX of
the pad's centre, and its end is its pixel farthest from that centre. Pads less
than about two cells apart can claim each other's trails (s52-t4, ring boards).

    uv run python -m scripts.read_trail_ends <frames dir> <manifest.json> [<key>]

The manifest is any `screenshots/ring_board/*.json` this project writes: tiles
as [kind, [y, x], rotation], under `tests`, `rings`, or the named key.
"""

from __future__ import annotations

import glob
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from traxgen.hex import HexVector
from traxgen.ring_board import TOOLBAR_RECTS, screen_position

DIFF_MIN = 60  # summed |RGB| change, before -> last, that counts as trail
MIN_PIECE_PX = 40
NEAR_PX = 140.0
# In-goal cut, fitted on s52-t4's four runs (ends in goals 3-35 px; held in a
# switch one cell short, 60 px). Not yet tested on runs it was not fitted to.
IN_GOAL_PX = 45.0

Pixel = tuple[int, int]
Cell = tuple[int, int]


@dataclass(frozen=True)
class TrailEnd:
    pad: str
    end: Pixel | None
    goal: Cell | None
    distance_px: float | None
    pixels: int

    @property
    def in_goal(self) -> bool:
        return self.distance_px is not None and self.distance_px <= IN_GOAL_PX


def trail_mask(before: Image.Image, last: Image.Image) -> Image.Image:
    """1 where the frame changed enough to be trail, 0 elsewhere and under the toolbar."""
    r, g, b = ImageChops.difference(before.convert("RGB"), last.convert("RGB")).split()
    mask = ImageChops.add(ImageChops.add(r, g), b).point(lambda v: 1 if v > DIFF_MIN else 0)
    for rect in TOOLBAR_RECTS:
        mask.paste(0, rect)
    return mask


def pieces(mask: Image.Image) -> list[list[Pixel]]:
    """The mask's 8-connected pieces of at least MIN_PIECE_PX pixels."""
    w = mask.width
    on = {(i % w, i // w) for i, v in enumerate(mask.tobytes()) if v}
    out: list[list[Pixel]] = []
    while on:
        stack = [on.pop()]
        piece: list[Pixel] = []
        while stack:
            x, y = stack.pop()
            piece.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if n in on:
                        on.remove(n)
                        stack.append(n)
        if len(piece) >= MIN_PIECE_PX:
            out.append(piece)
    return out


def read(
    before: Image.Image, last: Image.Image, pads: list[tuple[str, Cell]], goals: list[Cell]
) -> list[TrailEnd]:
    """Every trail near each pad, with its end and the nearest goal; `no trail` as end None."""
    found = pieces(trail_mask(before, last))
    goal_px = [(screen_position(HexVector(y=y, x=x)), (y, x)) for y, x in goals]
    out: list[TrailEnd] = []
    for name, (py, px) in pads:
        centre = screen_position(HexVector(y=py, x=px))
        mine = [p for p in found if min(math.dist(q, centre) for q in p) < NEAR_PX]
        if not mine:
            out.append(TrailEnd(name, None, None, None, 0))
            continue
        for piece in mine:
            end = max(piece, key=lambda q: math.dist(q, centre))
            if goal_px:
                d, goal = min((math.dist(end, gp), cell) for gp, cell in goal_px)
                out.append(TrailEnd(name, end, goal, round(d, 1), len(piece)))
            else:
                out.append(TrailEnd(name, end, None, None, len(piece)))
    return out


def _layout(manifest: Any, key: str | None) -> tuple[list[tuple[str, Cell]], list[Cell]]:
    node = manifest[key] if key else manifest
    if "rings" in node:
        pads = [(f"rot{r['rotation']}", tuple(r["starter"])) for r in node["rings"]]
        goals = [tuple(g) for r in node["rings"] for g in r["goals"].values()]
        return pads, goals  # type: ignore[return-value]
    single = [{"name": key or "course", "tiles": node.get("tiles", [])}]
    groups = node.get("tests", single)
    pads = [(t["name"], tuple(c)) for t in groups for k, c, _ in t["tiles"] if k == "STARTER"]
    goals = [tuple(c) for t in groups for k, c, _ in t["tiles"] if k == "GOAL_RAIL"]
    return pads, goals  # type: ignore[return-value]


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    frames, manifest = Path(argv[0]), json.loads(Path(argv[1]).read_text())
    pads, goals = _layout(manifest, argv[2] if len(argv) == 3 else None)
    after = sorted(glob.glob(str(frames / "after_*.png")))
    if not after:
        print(f"no after_*.png in {frames}")
        return 2
    for t in read(Image.open(frames / "before.png"), Image.open(after[-1]), pads, goals):
        where = (
            "no trail" if t.end is None else f"end {t.end} -> goal {t.goal} at {t.distance_px} px"
        )
        verdict = "" if t.end is None else ("  IN GOAL" if t.in_goal else "  not in goal")
        print(f"{t.pad:12s} {where} ({t.pixels} px){verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
