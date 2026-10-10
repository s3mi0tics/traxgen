"""Probe: what the screen shows after play is pressed, for courses that finish and that miss.

Item 19 (s41-t1). One cold emulator session; for each share code: render it,
leave it open, save the frame before play, tap play, then save a frame every
second until the screen stops changing (or a bound runs out), then clean up.
Nothing is classified here -- the frames are the raw material the finish check
is written from.

    uv run python -m scripts.probe_finish_frames KN6F459ZR3 THIIEUH35Z W8IEN7MG92

Output: screenshots/finish_frames/<code>/before.png, after_NN.png, frames.json.

Path: traxgen/scripts/probe_finish_frames.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from traxgen.android import (
    DEFAULT_SCREENSHOT_DIR,
    PLAY_BUTTON_SAMPLE_CENTER,
    WAITS,
    AdbContext,
    capture_png,
    frame_difference,
    frame_fingerprint,
    render_course,
    tap,
)

OUT = DEFAULT_SCREENSHOT_DIR / "finish_frames"
INTERVAL = 1.0  # seconds between frames after play
QUIET_FRAMES = 3  # this many unchanged frames in a row counts as settled
QUIET_LIMIT = 0.05  # mean channel difference (0-255) below which two frames are "unchanged"
MAX_SECONDS = 60.0  # bound on the wait; a marble that rolls forever must not hang the probe
# A corner of the stop square the play triangle does not cover (s41-t1): mean RGB here
# read [221, 232, 161] while the marble ran and [180, 204, 50] before and after.
STOP_CORNER = (2200, 964, 2212, 976)


def button_shows_stop(png: bytes) -> bool:
    """True while the play button is the stop square, i.e. the marble is still running."""
    import io

    from PIL import Image, ImageStat

    corner = Image.open(io.BytesIO(png)).convert("RGB").crop(STOP_CORNER)
    return ImageStat.Stat(corner).mean[2] > 105  # blue: 161 on the square, 50 off it


def watch(ctx: AdbContext, folder: Path) -> dict[str, object]:
    """Tap play, then save frames until the screen settles or the bound runs out."""
    before = capture_png(ctx, what="before play")
    (folder / "before.png").write_bytes(before)
    tap(ctx, PLAY_BUTTON_SAMPLE_CENTER)
    start = time.monotonic()
    last = frame_fingerprint(before)
    diffs: list[float] = []
    stop: list[bool] = []
    quiet = 0
    n = 0
    while time.monotonic() - start < MAX_SECONDS:
        time.sleep(INTERVAL)
        png = capture_png(ctx, what=f"after play {n}")
        (folder / f"after_{n:02d}.png").write_bytes(png)
        stop.append(button_shows_stop(png))
        fp = frame_fingerprint(png)
        d = frame_difference(last, fp)
        diffs.append(round(d, 4))
        last = fp
        n += 1
        quiet = quiet + 1 if d < QUIET_LIMIT else 0
        if quiet >= QUIET_FRAMES and not stop[-1]:  # still AND the run has ended
            break
    return {
        "settled": quiet >= QUIET_FRAMES and not stop[-1],
        "frames": n,
        "seconds": round(time.monotonic() - start, 1),
        "diffs": diffs,
        "stop_square": stop,
        "first_vs_last": round(frame_difference(frame_fingerprint(before), last), 4),
    }


def clean_up(ctx: AdbContext) -> None:
    """The same taps render_course's own cleanup makes: back, don't save, delete the track."""
    tap(ctx, "back_save_icon")
    ctx.sleep(WAITS["after_back"])
    tap(ctx, "dont_save")
    tap(ctx, "trash_icon")
    ctx.sleep(WAITS["after_delete"])
    tap(ctx, "delete_confirm")
    ctx.sleep(WAITS["after_delete"])


def main(codes: list[str]) -> int:
    from scripts.emulator import session

    results: dict[str, object] = {}
    with session(out=lambda line: print(line, file=sys.stderr)) as ctx:
        for code in codes:
            folder = OUT / code
            folder.mkdir(parents=True, exist_ok=True)
            # Two tries in the same boot: the first launch after a cold boot has died
            # in every s41 session so far, and the next launch in that boot has not (#21).
            for attempt in (1, 2):
                print(f"{code}: rendering, attempt {attempt}", file=sys.stderr)
                try:
                    render = render_course(
                        code, ctx=ctx, screenshot_dir=folder, screenshot_name="rendered",
                        cleanup=False, detect_validity=True, reset_first=True,
                        on_menu=lambda a: print(a.line(), file=sys.stderr),
                    )
                    record = {"attempt": attempt, "validity": render.validity,
                              **watch(ctx, folder)}
                    clean_up(ctx)
                    break
                except Exception as exc:  # one bad course must not cost the others' frames
                    notes = " | ".join(getattr(exc, "__notes__", ()))
                    record = {"attempt": attempt, "error": f"{type(exc).__name__}: {exc}",
                              "notes": notes}
                    print(f"{code}: attempt {attempt} failed: {record}", file=sys.stderr)
            (folder / "frames.json").write_text(json.dumps(record, indent=2))
            print(f"{code}: {json.dumps(record)}", file=sys.stderr)
            results[code] = record
    print(json.dumps(results, indent=2))
    return 0 if all("error" not in r for r in results.values()) else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
