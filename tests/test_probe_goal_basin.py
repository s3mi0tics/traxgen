"""The GOAL_BASIN board: six rotations, each pad apart and on screen (s52-t17).

Path: traxgen/tests/test_probe_goal_basin.py
"""

from __future__ import annotations

from scripts.probe_goal_basin import entered_side, layout, predicted_catch
from traxgen.graph import placed_tiles
from traxgen.hex import HexVector
from traxgen.layout import build_course
from traxgen.plates import STANDARD_SQUARE
from traxgen.ring_board import hex_distance, under_toolbar
from traxgen.types import TileKind

PLATES = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)


def test_six_tests_one_per_rotation() -> None:
    tests = layout(PLATES)
    assert [r for r, _ in tests] == list(range(6))
    for rotation, placed in tests:
        (k1, pad, r1), (k2, basin, r2) = placed
        assert (k1, r1, k2, r2) == (TileKind.STARTER, 0, TileKind.GOAL_BASIN, rotation)
        assert basin == pad.neighbor(0)
        assert not under_toolbar(pad) and not under_toolbar(basin)


def test_tests_are_apart() -> None:
    cells = [[c for _, c, _ in placed] for _, placed in layout(PLATES)]
    for i, a in enumerate(cells):
        for b in cells[i + 1 :]:
            assert min(hex_distance(x, y) for x in a for y in b) >= 3


def test_prediction_splits_three_and_three() -> None:
    assert [predicted_catch(r) for r in range(6)] == [False, True, False, True, False, True]
    assert entered_side(0) == 3 and entered_side(3) == 0


def test_the_board_builds_with_every_tile_on_it() -> None:
    from scripts.probe_two_marbles import placements

    tiles = [t for _, placed in layout(PLATES) for t in placements(PLATES, placed)]
    course = build_course(plate_world_positions=PLATES, tiles=tiles, title="t")
    assert len(list(placed_tiles(course))) == 12
