"""The finish check: judge a play run by the app's sparkle burst (item 19, s42-t5).

Path: traxgen/tests/test_finish_burst.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from traxgen.android import (
    DEFAULT_SCREENSHOT_DIR,
    FINISH_BURST_MIN_PIXELS,
    STOP_SQUARE_CORNER,
    FinishStatus,
    button_shows_stop,
    judge_finish,
    new_white_pixels,
)

BLUE = (20, 110, 170)
STOP_BLUE = (221, 232, 161)  # the stop square's corner while a marble runs (s41-t1)
IDLE_GREEN = (180, 204, 50)  # the same corner before and after a run


def frame(*, stop: bool = False, sparkles: int = 0, at: tuple[int, int] = (1400, 300)) -> bytes:
    """A 2400x1080 screen: blue board, the play button's corner, and `sparkles` white pixels."""
    img = Image.new("RGB", (2400, 1080), BLUE)
    draw = ImageDraw.Draw(img)
    draw.rectangle(STOP_SQUARE_CORNER, fill=STOP_BLUE if stop else IDLE_GREEN)
    x, y = at
    for i in range(sparkles):
        draw.point((x + i % 50, y + i // 50), fill=(250, 250, 250))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


BEFORE = frame()


def test_button_shows_stop_reads_the_corner():
    assert button_shows_stop(frame(stop=True))
    assert not button_shows_stop(frame(stop=False))


def test_new_white_pixels_counts_only_what_play_added():
    assert new_white_pixels(BEFORE, frame(sparkles=100)) == 100
    already_white = frame(sparkles=100)
    assert new_white_pixels(already_white, frame(sparkles=100)) == 0


def test_new_white_pixels_ignores_the_toolbar_and_back_icon():
    assert new_white_pixels(BEFORE, frame(sparkles=100, at=(1000, 950))) == 0
    assert new_white_pixels(BEFORE, frame(sparkles=100, at=(50, 50))) == 0


def test_a_burst_during_the_run_is_a_finish():
    frames = [frame(stop=True), frame(stop=True, sparkles=500), frame()]
    reading = judge_finish(BEFORE, frames)
    assert reading.status is FinishStatus.FINISHED
    assert reading.peak_new_white == 500


def test_no_burst_is_not_a_finish():
    frames = [frame(stop=True), frame(stop=True, sparkles=11), frame()]
    assert judge_finish(BEFORE, frames).status is FinishStatus.NOT_FINISHED


def test_the_threshold_is_inclusive():
    at = [frame(stop=True, sparkles=FINISH_BURST_MIN_PIXELS), frame()]
    below = [frame(stop=True, sparkles=FINISH_BURST_MIN_PIXELS - 1), frame()]
    assert judge_finish(BEFORE, at).status is FinishStatus.FINISHED
    assert judge_finish(BEFORE, below).status is FinishStatus.NOT_FINISHED


def test_a_run_that_never_played_is_unjudged_not_a_miss():
    reading = judge_finish(BEFORE, [frame(), frame(), frame()])
    assert reading.status is FinishStatus.UNJUDGED
    assert "never showed" in reading.reason


def test_a_run_that_had_not_ended_is_unjudged_even_with_a_burst():
    reading = judge_finish(BEFORE, [frame(stop=True, sparkles=500), frame(stop=True)])
    assert reading.status is FinishStatus.UNJUDGED
    assert "not ended" in reading.reason


def test_no_frames_is_unjudged():
    assert judge_finish(BEFORE, []).status is FinishStatus.UNJUDGED


# --- The labelled runs on this machine --------------------------------------
#
# Frames are gitignored (the probe regenerates them), so this skips where they
# are absent. Labels: s41-t5, s42-t2, s42-t4. Only the frames `frames.json`
# counts are read -- a reused folder can hold a longer earlier run's extras.

FRAMES = DEFAULT_SCREENSHOT_DIR / "finish_frames"
LABELLED = {
    "PROBOOK12": FinishStatus.FINISHED,
    "THIIEUH35Z": FinishStatus.FINISHED,
    "KN6F459ZR3": FinishStatus.FINISHED,
    "KN6F459ZR3_s41": FinishStatus.FINISHED,
    "W8IEN7MG92": FinishStatus.NOT_FINISHED,
    "STXT6WF9VB": FinishStatus.NOT_FINISHED,
    "I4BA3N5V6Y": FinishStatus.NOT_FINISHED,
    "8I8EVU4NCU": FinishStatus.NOT_FINISHED,
    **{f"{c}/run_{k}": FinishStatus.NOT_FINISHED
       for c in ("I4BA3N5V6Y", "8I8EVU4NCU") for k in (1, 2, 3)},
    "4DLUQKGRKN": FinishStatus.UNJUDGED,  # no goal: play does nothing
}


def counted_frames(folder: Path) -> list[bytes]:
    n = json.loads((folder / "frames.json").read_text())["frames"]
    return [(folder / f"after_{i:02d}.png").read_bytes() for i in range(n)]


@pytest.mark.parametrize("run", sorted(LABELLED))
def test_labelled_run(run: str):
    folder = FRAMES / run
    if not (folder / "frames.json").exists():
        pytest.skip(f"no saved frames for {run}")
    reading = judge_finish((folder / "before.png").read_bytes(), counted_frames(folder))
    assert reading.status is LABELLED[run], reading
