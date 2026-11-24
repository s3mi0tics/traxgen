"""The trail-end reader on drawn frames: a trail into a goal, one short of it, and none (s52-t4).

Path: traxgen/tests/test_read_trail_ends.py
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from scripts.read_trail_ends import IN_GOAL_PX, NEAR_PX, read
from traxgen.hex import HexVector
from traxgen.ring_board import screen_position

PAD = (-3, 2)  # DLYQPCH46H's launch pad and goal, s49-t5
GOAL = (-2, 3)
FRAME = (2400, 1080)


def _px(cell: tuple[int, int]) -> tuple[float, float]:
    return screen_position(HexVector(y=cell[0], x=cell[1]))


def _frames(stop_fraction: float | None) -> tuple[Image.Image, Image.Image]:
    """A blank board, and the same board with a trail from beside the pad toward the goal."""
    before = Image.new("RGB", FRAME, (40, 140, 190))
    last = before.copy()
    if stop_fraction is not None:
        (sx, sy), (gx, gy) = _px(PAD), _px(GOAL)
        # the pad's top hides the first stretch: start 40% of the way, inside NEAR_PX
        a = (sx + 0.4 * (gx - sx), sy + 0.4 * (gy - sy))
        b = (sx + stop_fraction * (gx - sx), sy + stop_fraction * (gy - sy))
        ImageDraw.Draw(last).line([a, b], fill=(230, 40, 140), width=5)
    return before, last


def test_a_trail_into_the_goal_ends_in_goal() -> None:
    [t] = read(*_frames(1.0), [("A", PAD)], [GOAL])
    assert t.goal == GOAL and t.in_goal and t.distance_px is not None and t.distance_px < 5


def test_a_trail_that_stops_short_of_the_goal_is_not_in_goal() -> None:
    [t] = read(*_frames(0.5), [("A", PAD)], [GOAL])
    assert t.end is not None and not t.in_goal and t.distance_px is not None
    assert t.distance_px > IN_GOAL_PX


def test_no_trail_near_the_pad_reads_no_trail() -> None:
    [t] = read(*_frames(None), [("A", PAD)], [GOAL])
    assert t.end is None and t.pixels == 0 and not t.in_goal


def test_the_trail_starts_within_reach_of_its_pad() -> None:
    # guards the fixture: a start outside NEAR_PX would make the first test pass for no reason
    (sx, sy), (gx, gy) = _px(PAD), _px(GOAL)
    start = (sx + 0.4 * (gx - sx), sy + 0.4 * (gy - sy))
    assert ((start[0] - sx) ** 2 + (start[1] - sy) ** 2) ** 0.5 < NEAR_PX
