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
    FINISH_SPARKLES_MIN,
    STOP_SQUARE_CORNER,
    FinishStatus,
    button_shows_stop,
    judge_finish,
    new_sparkles,
    new_white_pixels,
)

BLUE = (20, 110, 170)
STOP_BLUE = (221, 232, 161)  # the stop square's corner while a marble runs (s41-t1)
IDLE_GREEN = (180, 204, 50)  # the same corner before and after a run


WHITE = (250, 250, 250)


def frame(
    *,
    stop: bool = False,
    sparkles: int = 0,
    at: tuple[int, int] = (1400, 300),
    streaks: int = 0,
) -> bytes:
    """A 2400x1080 screen: blue board, the play button's corner, `sparkles` separate
    5x5 white dots (25 px each, 10 px apart), and `streaks` thin 3x120 white lines,
    the shape a switch's lever uncovers."""
    img = Image.new("RGB", (2400, 1080), BLUE)
    draw = ImageDraw.Draw(img)
    draw.rectangle(STOP_SQUARE_CORNER, fill=STOP_BLUE if stop else IDLE_GREEN)
    x, y = at
    for i in range(sparkles):
        dx, dy = x + 10 * (i % 40), y + 10 * (i // 40)
        draw.rectangle((dx, dy, dx + 4, dy + 4), fill=WHITE)
    for i in range(streaks):
        draw.rectangle((400, 500 + 10 * i, 519, 502 + 10 * i), fill=WHITE)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


BEFORE = frame()


def test_button_shows_stop_reads_the_corner():
    assert button_shows_stop(frame(stop=True))
    assert not button_shows_stop(frame(stop=False))


def test_new_white_pixels_counts_only_what_play_added():
    assert new_white_pixels(BEFORE, frame(sparkles=4)) == 100
    already_white = frame(sparkles=4)
    assert new_white_pixels(already_white, frame(sparkles=4)) == 0


def test_new_white_pixels_ignores_the_toolbar_and_back_icon():
    assert new_white_pixels(BEFORE, frame(sparkles=4, at=(1000, 950))) == 0
    assert new_white_pixels(BEFORE, frame(sparkles=4, at=(50, 50))) == 0


def test_new_sparkles_counts_separate_dots_only_once_each():
    assert new_sparkles(BEFORE, frame(sparkles=12)) == 12
    assert new_sparkles(frame(sparkles=12), frame(sparkles=12)) == 0


def test_a_lever_streak_is_white_but_not_a_sparkle():
    """s48: a switch's lever uncovers thin streaks of white plastic, hundreds of pixels."""
    lever = frame(streaks=4)
    assert new_white_pixels(BEFORE, lever) == 4 * 3 * 120
    assert new_sparkles(BEFORE, lever) == 0


def test_a_solid_block_is_not_a_sparkle():
    block = frame(sparkles=0)
    img = Image.open(io.BytesIO(block))
    ImageDraw.Draw(img).rectangle((800, 300, 829, 329), fill=WHITE)  # 900 px, one spot
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    assert new_sparkles(BEFORE, buf.getvalue()) == 0


def test_a_burst_during_the_run_is_a_finish():
    frames = [frame(stop=True), frame(stop=True, sparkles=20), frame()]
    reading = judge_finish(BEFORE, frames)
    assert reading.status is FinishStatus.FINISHED
    assert reading.peak_sparkles == 20
    assert reading.peak_new_white == 500


def test_no_burst_is_not_a_finish():
    frames = [frame(stop=True), frame(stop=True, sparkles=2), frame()]
    assert judge_finish(BEFORE, frames).status is FinishStatus.NOT_FINISHED


def test_a_lever_swing_is_not_a_finish_however_much_white_it_adds():
    """Item 23: goal-less switch boards read 432 to 976 new white pixels and no burst."""
    frames = [frame(stop=True, streaks=4), frame(stop=True, streaks=4), frame()]
    reading = judge_finish(BEFORE, frames)
    assert reading.peak_new_white > 30
    assert reading.status is FinishStatus.NOT_FINISHED


def test_a_burst_beside_a_swung_lever_is_a_finish():
    frames = [frame(stop=True, streaks=4), frame(stop=True, streaks=4, sparkles=20), frame()]
    assert judge_finish(BEFORE, frames).status is FinishStatus.FINISHED


def test_the_threshold_is_inclusive():
    at = [frame(stop=True, sparkles=FINISH_SPARKLES_MIN), frame()]
    below = [frame(stop=True, sparkles=FINISH_SPARKLES_MIN - 1), frame()]
    assert judge_finish(BEFORE, at).status is FinishStatus.FINISHED
    assert judge_finish(BEFORE, below).status is FinishStatus.NOT_FINISHED


def test_a_run_that_never_played_is_unjudged_not_a_miss():
    reading = judge_finish(BEFORE, [frame(), frame(), frame()])
    assert reading.status is FinishStatus.UNJUDGED
    assert "never showed" in reading.reason


def test_a_run_that_had_not_ended_is_unjudged_even_with_a_burst():
    reading = judge_finish(BEFORE, [frame(stop=True, sparkles=20), frame(stop=True)])
    assert reading.status is FinishStatus.UNJUDGED
    assert "not ended" in reading.reason


def test_no_frames_is_unjudged():
    assert judge_finish(BEFORE, []).status is FinishStatus.UNJUDGED


# --- The labelled runs on this machine --------------------------------------
#
# Frames are gitignored (the probe regenerates them), so this skips where they
# are absent. Labels: s41-t5, s42-t2, s42-t4; s46 and s47 (ring boards, by
# their trails); s48 (switch boards, no goals). Only the frames `frames.json`
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
    "TKLKNFJGT3": FinishStatus.FINISHED,  # curve ring board, 30 goals (s46)
    "5H5NQ7HT7D/run_1": FinishStatus.NOT_FINISHED,  # curve ring board, no goals (s46)
    "5H5NQ7HT7D/run_2": FinishStatus.NOT_FINISHED,
    "YFUGDSMDUH/run_1": FinishStatus.NOT_FINISHED,  # cross ring board, no goals (s47)
    # Switch boards, no goals: the lever's white is not a finish (s48, item 23).
    "Q7AE2SM7MC": FinishStatus.NOT_FINISHED,
    "54TI3KWGTH": FinishStatus.NOT_FINISHED,
    "ZJR47DUFFX": FinishStatus.NOT_FINISHED,
    "8D9CU5AEY3": FinishStatus.NOT_FINISHED,
    "8WL7RXS9H4": FinishStatus.NOT_FINISHED,
}
# The four whose saved frames show the lever's white; ZJR47DUFFX's saved run adds none.
LEVER_WHITE = ("Q7AE2SM7MC", "54TI3KWGTH", "8D9CU5AEY3", "8WL7RXS9H4")


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


@pytest.mark.parametrize("run", LEVER_WHITE)
def test_a_switch_board_adds_white_that_a_pixel_count_would_call_a_finish(run: str):
    """Keeps the switch-board labels meaningful: judged on pixels, each would read finished."""
    folder = FRAMES / run
    if not (folder / "frames.json").exists():
        pytest.skip(f"no saved frames for {run}")
    reading = judge_finish((folder / "before.png").read_bytes(), counted_frames(folder))
    assert reading.peak_new_white >= FINISH_BURST_MIN_PIXELS
    assert reading.peak_sparkles < FINISH_SPARKLES_MIN
