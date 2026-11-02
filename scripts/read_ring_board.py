"""Read a played ring board goal by goal: which finish line did each ring's marble reach? (s46-t3)

    uv run python -m scripts.read_ring_board CURVE
    uv run python -m scripts.read_ring_board CURVE --without-goals <frames>/<code>/run_1

Reads, all already on disk:
  screenshots/ring_board/<KIND>.json and <KIND>-nogoals.json   (ring_board.py)
  screenshots/finish_frames/<code>/before.png, after_NN.png    (probe_finish_frames.py --link)

How. The goals' pixels are where the board's before-play frame differs from the
same board's goal-less frame (s42-t4: removing a goal leaves the camera still).
Those pixels clump into one group per ring. A least-squares fit from the rings'
world centres to the groups' centres, tried over every pairing of rings to
groups, gives the screen position of any world cell; its residual is printed,
because a wrong pairing fits badly. Around each ring's centre, the six sides
point in six screen directions, so every pixel near a ring belongs to the side
whose direction is nearest. The marble's trail stays on screen after the run,
so the side holding the most new trail pixels in the settled last frame is the
side the marble left by.

Not the finish burst: on a board with several rings the app throws one
celebration burst over the middle of the board, nowhere near any goal (s46-t3),
so the burst can say that something finished and never which goal. Reading
trails was Colby's suggestion.

A goal whose pixels are mostly missing -- under the toolbar -- reads HIDDEN,
never "no finish".

Path: traxgen/scripts/read_ring_board.py
"""

from __future__ import annotations

import argparse
import io
import json
import math
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path

from traxgen.android import DEFAULT_SCREENSHOT_DIR
from traxgen.hex import HexVector
from traxgen.track_graph import CURVE_TRACKS

RING_DIR = DEFAULT_SCREENSHOT_DIR / "ring_board"
FRAME_DIR = DEFAULT_SCREENSHOT_DIR / "finish_frames"

# Board area, as in `android.FINISH_BURST_BOARD`, and the downscale the reader works at.
BOARD = (200, 0, 2400, 880)
SCALE = 4
# A pixel counts as part of a goal when some channel moved this much between the frames.
GOAL_DIFF_MIN = 40
# Ring groups smaller than this many (downscaled) pixels are noise.
MIN_GROUP = 40
# A goal is HIDDEN when its visible pixels are under this share of the median goal's.
HIDDEN_SHARE = 0.5
STARTER_SIDE = 5
# A trail pixel: changed this much between the frame before play and the settled last frame.
TRAIL_DIFF_MIN = 60
# A side holds the trail when this many full-frame pixels changed there. Provisional (s46-t3):
# the weakest real trail read 57, the largest spill into a wrong side 176 -- so the reading
# is the side with the MOST, and this floor only separates a trail from none.
TRAIL_MIN_PIXELS = 30

Pixel = tuple[float, float]
Affine = tuple[tuple[float, float, float], tuple[float, float, float]]


def _load(path: Path):  # a PIL image
    from PIL import Image

    img = Image.open(io.BytesIO(path.read_bytes())).convert("RGB").crop(BOARD)
    return img.resize((img.width // SCALE, img.height // SCALE))


def goal_pixels(with_goals: Path, without_goals: Path) -> set[tuple[int, int]]:
    """Downscaled board pixels that the goals change."""
    from PIL import ImageChops

    a, b = _load(with_goals), _load(without_goals)
    diff = ImageChops.difference(a, b)
    r, g, bl = diff.split()
    biggest = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    w = biggest.width
    return {(i % w, i // w) for i, v in enumerate(biggest.tobytes()) if v >= GOAL_DIFF_MIN}


def groups(pixels: set[tuple[int, int]], gap: int = 8) -> list[set[tuple[int, int]]]:
    """Pixels clumped by distance `gap`: a ring's thin goals sit a few pixels apart, rings a cell.

    8 (downscaled) is the gap that gave exactly six groups on the curve board; 3 gave 22.
    """
    left = set(pixels)
    found = []
    while left:
        seed = left.pop()
        group, frontier = {seed}, [seed]
        while frontier:
            x, y = frontier.pop()
            for dx in range(-gap, gap + 1):
                for dy in range(-gap, gap + 1):
                    p = (x + dx, y + dy)
                    if p in left:
                        left.remove(p)
                        group.add(p)
                        frontier.append(p)
        if len(group) >= MIN_GROUP:
            found.append(group)
    return found


def centroid(points: set[tuple[int, int]]) -> Pixel:
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def fit_affine(world: list[HexVector], screen: list[Pixel]) -> tuple[Affine, float]:
    """Least-squares screen = A * (y, x, 1); returns the map and the RMS residual in pixels."""
    rows = [(w.y, w.x, 1.0) for w in world]
    coeffs = []
    for k in range(2):
        target = [s[k] for s in screen]
        coeffs.append(_solve3(rows, target))
    residual = 0.0
    for w, s in zip(world, screen, strict=True):
        px = apply((coeffs[0], coeffs[1]), w)
        residual += (px[0] - s[0]) ** 2 + (px[1] - s[1]) ** 2
    return (coeffs[0], coeffs[1]), math.sqrt(residual / len(world))


def _solve3(
    rows: list[tuple[float, float, float]], target: list[float]
) -> tuple[float, float, float]:
    """Normal equations for a 3-parameter least squares, by Cramer's rule."""
    m = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
    v = [sum(r[i] * t for r, t in zip(rows, target, strict=True)) for i in range(3)]

    def det(a: list[list[float]]) -> float:
        return (
            a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
        )

    d = det(m)
    out = []
    for c in range(3):
        mc = [[*row[:c], v[i], *row[c + 1 :]] for i, row in enumerate(m)]
        out.append(det(mc) / d)
    return (out[0], out[1], out[2])


def apply(a: Affine, w: HexVector) -> Pixel:
    return (
        a[0][0] * w.y + a[0][1] * w.x + a[0][2],
        a[1][0] * w.y + a[1][1] * w.x + a[1][2],
    )


def best_fit(centres: list[HexVector], found: list[Pixel]) -> tuple[Affine, float, list[int]]:
    """Every pairing of rings to groups; the one with the smallest residual."""
    best = None
    for order in permutations(range(len(found)), len(centres)):
        affine, residual = fit_affine(centres, [found[i] for i in order])
        if best is None or residual < best[1]:
            best = (affine, residual, list(order))
    assert best is not None
    return best


def side_of(affine: Affine, centre: HexVector, pixel: Pixel) -> int:
    """The side of `centre` whose screen direction is nearest the direction to `pixel`."""
    c = apply(affine, centre)
    angle = math.atan2(pixel[1] - c[1], pixel[0] - c[0])

    def gap(d: int) -> float:
        n = apply(affine, centre.neighbor(d))
        a = math.atan2(n[1] - c[1], n[0] - c[0])
        return abs(math.remainder(angle - a, math.tau))

    return min(range(6), key=gap)


@dataclass(frozen=True)
class RingReading:
    rotation: int
    finished_side: int | None
    peaks: dict[int, int]
    hidden: frozenset[int]


def read(
    kind: str, with_dir: Path | None = None, without_dir: Path | None = None
) -> tuple[list[RingReading], float]:
    """`with_dir`/`without_dir` default to each board's frame folder under `FRAME_DIR`."""
    full = json.loads((RING_DIR / f"{kind}.json").read_text())
    bare = json.loads((RING_DIR / f"{kind}-nogoals.json").read_text())
    with_dir = with_dir or FRAME_DIR / full["code"]
    without_dir = without_dir or FRAME_DIR / bare["code"]
    pixels = goal_pixels(with_dir / "before.png", without_dir / "before.png")
    found = sorted(groups(pixels), key=len, reverse=True)[: len(full["rings"])]
    centres = [HexVector(*r["centre"]) for r in full["rings"]]
    affine, residual, order = best_fit(centres, [centroid(g) for g in found])
    # A ring half under the toolbar shows only its top half, so its group's centre
    # sits off its ring's and drags the fit by about half a cell (3.2 px against
    # 0.3 px without it, on the curve board). Refit without the smallest group.
    smallest = min(range(len(found)), key=lambda i: len(found[i]))
    keep = [k for k in range(len(centres)) if order[k] != smallest]
    affine, residual = fit_affine(
        [centres[k] for k in keep], [centroid(found[order[k]]) for k in keep]
    )

    by_ring_side: dict[tuple[int, int], int] = {}
    for k in range(len(centres)):
        for p in found[order[k]]:
            key = (k, side_of(affine, centres[k], p))
            by_ring_side[key] = by_ring_side.get(key, 0) + 1
    sizes = sorted(v for (_, side), v in by_ring_side.items() if side != STARTER_SIDE)
    median = sizes[len(sizes) // 2]

    # The trail stays on screen after the run (s40), so the settled last frame
    # holds every ring's path. Counted at full resolution: the trail is a thin
    # line, and the downscale that suits the goals erases it. Only pixels
    # between 0.35 and 1.3 cells out from a ring's centre count: inside, the
    # trail crosses the piece at every angle; beyond, it is between rings.
    last = sorted(with_dir.glob("after_*.png"))[-1]
    moved = changed_full(with_dir / "before.png", last)
    cell = _cell(affine) * SCALE
    counts: dict[tuple[int, int], int] = {}
    for k, centre in enumerate(centres):
        cx, cy = to_full(apply(affine, centre))
        for y in range(int(cy - 1.3 * cell), int(cy + 1.3 * cell) + 1):
            for x in range(int(cx - 1.3 * cell), int(cx + 1.3 * cell) + 1):
                if (x, y) not in moved or not 0.35 * cell <= math.dist(
                    (x, y), (cx, cy)
                ) <= 1.3 * cell:
                    continue
                key = (k, side_of(affine, centre, to_board((x, y))))
                counts[key] = counts.get(key, 0) + 1
    peaks = counts

    readings = []
    for k, ring in enumerate(full["rings"]):
        ring_peaks = {d: peaks.get((k, d), 0) for d in range(6) if d != STARTER_SIDE}
        hidden = frozenset(
            d for d in ring_peaks if by_ring_side.get((k, d), 0) < HIDDEN_SHARE * median
        )
        top = max(ring_peaks, key=lambda d: ring_peaks[d])
        finished = top if ring_peaks[top] >= TRAIL_MIN_PIXELS else None
        readings.append(RingReading(ring["rotation"], finished, ring_peaks, hidden))
    return readings, residual


def to_full(p: Pixel) -> Pixel:
    """A downscaled board pixel as a full-frame pixel."""
    return (p[0] * SCALE + BOARD[0], p[1] * SCALE + BOARD[1])


def to_board(p: Pixel) -> Pixel:
    """A full-frame pixel as a downscaled board pixel."""
    return ((p[0] - BOARD[0]) / SCALE, (p[1] - BOARD[1]) / SCALE)


def changed_full(before: Path, after: Path) -> set[tuple[int, int]]:
    """Full-frame pixels where some channel moved by `TRAIL_DIFF_MIN` or more."""
    from PIL import Image, ImageChops

    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    r, g, bl = ImageChops.difference(a, b).split()
    biggest = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    w = biggest.width
    return {(i % w, i // w) for i, v in enumerate(biggest.tobytes()) if v >= TRAIL_DIFF_MIN}


def _cell(affine: Affine) -> float:
    """Screen length of one cell step, in downscaled pixels."""
    o = HexVector(0, 0)
    return math.dist(apply(affine, o), apply(affine, o.neighbor(0)))


def rule_side(rotation: int) -> int | None:
    """The curve rule's world exit side for a ring at `rotation`, or None (no marble loads)."""
    entered = (STARTER_SIDE - rotation) % 6
    if entered not in CURVE_TRACKS:
        return None
    return (CURVE_TRACKS[entered] + rotation) % 6


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", nargs="?", default="CURVE")
    parser.add_argument("--with-goals", type=Path, help="frame folder of the board with goals")
    parser.add_argument("--without-goals", type=Path, help="frame folder of the goal-less board")
    args = parser.parse_args(argv)
    kind = args.kind
    readings, residual = read(kind, args.with_goals, args.without_goals)
    print(f"fit residual: {residual:.2f} px (downscaled x{SCALE}; the smallest group left out)")
    disagreements = 0
    for r in sorted(readings, key=lambda r: r.rotation):
        expected = rule_side(r.rotation) if kind == "CURVE" else None
        if r.finished_side is None and expected in r.hidden:
            verdict = "hidden"
        elif r.finished_side == expected:
            verdict = "agree"
        else:
            verdict = "DISAGREE"
            disagreements += 1
        peaks = " ".join(f"{d}:{v}" for d, v in sorted(r.peaks.items()))
        hid = f" hidden={sorted(r.hidden)}" if r.hidden else ""
        print(
            f"rotation {r.rotation}: left by side {r.finished_side}, rule says {expected}"
            f" -- {verdict}  [peaks {peaks}]{hid}"
        )
    return 1 if disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())
