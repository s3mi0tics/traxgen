"""The half-hole courses: a lone plate, one pad facing one goal on a half-hole (#26, s50-t3).

Path: traxgen/tests/test_probe_half_holes.py
"""

from __future__ import annotations

from scripts.probe_half_holes import CASES, STARTER_PORTS, course_for
from traxgen.graph import placed_tiles
from traxgen.plates import half_hole_cells, is_buildable_on_plate
from traxgen.track_graph import TrackStatus, check_course
from traxgen.types import LayerKind, TileKind

KIND = LayerKind.BASE_LAYER_PIECE


def test_every_half_hole_and_the_control_are_covered() -> None:
    assert {c.goal for c in CASES} == set(half_hole_cells(KIND))
    assert ((0, 1), 0) in {(c.goal, c.travel) for c in CASES}  # the s43 misses' placement
    assert len({(c.goal, c.travel) for c in CASES}) == len(CASES) == 8


def test_each_pad_is_buildable_and_faces_its_goal() -> None:
    for case in CASES:
        assert is_buildable_on_plate(KIND, case.pad_cell), case.name
        ports = {(p + case.pad_rotation) % 6 for p in STARTER_PORTS}
        assert case.travel in ports, case.name
        assert case.pad_cell.neighbor(case.travel) == case.goal_cell, case.name


def test_each_course_is_one_pad_and_one_goal() -> None:
    for case in CASES:
        tiles = list(placed_tiles(course_for(case)))
        assert sorted(t.kind.name for t in tiles) == ["GOAL_RAIL", "STARTER"], case.name
        goal = next(t for t in tiles if t.kind is TileKind.GOAL_RAIL)
        assert (goal.local_pos.y, goal.local_pos.x) == case.goal, case.name


def test_the_checker_predicts_every_case_misses() -> None:
    """The half-hole reading: the goal accepts the marble and does not catch it, a dead end."""
    for case in CASES:
        verdict = check_course(course_for(case))
        assert verdict.status is TrackStatus.INVALID, (case.name, verdict.reason)
        assert "dead end" in verdict.reason, (case.name, verdict.reason)
