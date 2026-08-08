"""Measure candidate frame-guard metrics against known-good and known-bad screencaps.

The play-button oracle (`traxgen.android.detect_play_button_state`) samples a
12x12 box at (2190, 980) and calls the frame 'active' when the mean min-channel
clears 220. That is a brightness test, not a validity test: on 2026-08-07 it
returned 'active' for a GraviTrax splash screen, manufacturing a second active
rotation that would have been read as `MODEL_WRONG`.

The fix is a precondition -- refuse to classify a frame that doesn't look like a
rendered course at all. This script exists to pick that threshold from measured
data rather than from a guess, which is the mistake that produced the bug.

Metrics printed per image:
    mean          mean grayscale value over the whole frame
    stddev        standard deviation of grayscale over the whole frame
    white_frac    fraction of pixels whose min RGB channel >= 235
    sample        the oracle's own statistic: mean min-channel in its sample box
    verdict       what the current oracle says today

Usage:

    uv run python -m scripts.calibrate_frame_guard screenshots/goal_rotation_sweep/*.png

Read the output as two clusters. A rendered course carries a colourful board and
UI chrome; a splash or loading screen is close to uniform. Pick a threshold with
daylight on both sides, and record where it came from.

Path: traxgen/scripts/calibrate_frame_guard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from traxgen.android import detect_play_button_state

# Downsample before computing whole-frame statistics. A 2400x1080 PNG is 2.6M
# pixels; the distinction we care about survives aggressively at 1/8 scale and
# the measurement stays fast enough to run inside a render loop.
DOWNSCALE = 8

# A pixel counts as "white" for white_frac when every channel clears this.
WHITE_MIN_CHANNEL = 235


def frame_stats(path: Path) -> dict[str, float]:
    """Return whole-frame statistics for one screencap."""
    from PIL import Image

    img = Image.open(path).convert("RGB")
    small = img.resize((img.width // DOWNSCALE, img.height // DOWNSCALE))
    pixels = list(small.getdata())
    n = len(pixels)

    grays = [(r + g + b) / 3.0 for r, g, b in pixels]
    mean = sum(grays) / n
    variance = sum((g - mean) ** 2 for g in grays) / n
    white = sum(1 for r, g, b in pixels if min(r, g, b) >= WHITE_MIN_CHANNEL)

    return {
        "mean": mean,
        "stddev": variance**0.5,
        "white_frac": white / n,
    }


def sample_stat(path: Path) -> float:
    """Recompute the oracle's own statistic so it sits alongside the others."""
    from PIL import Image

    from traxgen.android import PLAY_BUTTON_SAMPLE_CENTER, PLAY_BUTTON_SAMPLE_HALF

    img = Image.open(path).convert("RGB")
    cx, cy = PLAY_BUTTON_SAMPLE_CENTER
    h = PLAY_BUTTON_SAMPLE_HALF
    box = list(img.crop((cx - h, cy - h, cx + h, cy + h)).getdata())
    n = len(box)
    return min(
        sum(p[0] for p in box) / n,
        sum(p[1] for p in box) / n,
        sum(p[2] for p in box) / n,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    paths = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    paths = [p for p in paths if p.suffix.lower() == ".png"]
    if not paths:
        print("usage: calibrate_frame_guard <screenshot.png> [...]", file=sys.stderr)
        return 1

    print(f"{'image':<46} {'mean':>7} {'stddev':>7} {'white':>7} {'sample':>7}  verdict")
    for path in sorted(paths):
        if not path.is_file():
            print(f"{path.name:<46} MISSING")
            continue
        stats = frame_stats(path)
        print(
            f"{path.name:<46} "
            f"{stats['mean']:>7.1f} "
            f"{stats['stddev']:>7.1f} "
            f"{stats['white_frac']:>7.3f} "
            f"{sample_stat(path):>7.1f}  "
            # guard_frame=False on purpose: classifying known-bad frames is the
            # whole point here, and the guard exists to stop that everywhere else.
            f"{detect_play_button_state(path, guard_frame=False)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
