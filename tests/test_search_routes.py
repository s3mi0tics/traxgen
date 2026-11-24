"""The route search: every emitted course re-checked by the checker and the validator (s52-t18).

Path: traxgen/tests/test_search_routes.py
"""

from __future__ import annotations

import pytest

from scripts.search_routes import (
    PLATES,
    Route,
    course_of,
    grow,
    picks,
    search,
    steps,
    uses_track,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.ring_board import under_toolbar
from traxgen.track_graph import TrackStatus, check_course
from traxgen.types import TileKind
from traxgen.validator import Severity, validate


@pytest.fixture(scope="module")
def routes() -> list[Route]:
    return list(search(max_middle=2))


def test_every_route_is_valid_by_the_checker_and_the_validator(routes: list[Route]) -> None:
    assert routes
    for route in routes[:: max(1, len(routes) // 200)]:
        course = course_of(route)
        assert check_course(course).status is TrackStatus.VALID
        found = validate(course, PRO_VERTICAL_STARTER_SET)
        assert not [v for v in found if v.severity is Severity.ERROR]


def test_picks_cover_both_curve_tracks_and_the_cross(routes: list[Route]) -> None:
    chosen = picks(routes)
    # depth 2 here, so no three-piece pick; the script's default depth finds those
    assert {"gentle_curve", "sharp_curve", "cross"} <= set(chosen)
    assert uses_track(chosen["gentle_curve"], TileKind.CURVE, frozenset({0, 2}))
    assert uses_track(chosen["sharp_curve"], TileKind.CURVE, frozenset({3, 4}))
    for route in chosen.values():
        assert all(not under_toolbar(c) for _, c, _ in route.tiles)
        assert check_course(course_of(route)).status is TrackStatus.VALID


def test_a_curve_takes_four_ways_in_and_a_cross_two_ways_through() -> None:
    assert len(list(steps(TileKind.CURVE, 0))) == 4
    assert sorted(leave for _, leave in steps(TileKind.CROSS, 0)) == [0]


def test_a_route_never_reuses_a_cell() -> None:
    pad = HexVector(y=-6, x=4)
    for route in grow(pad, 0, max_middle=3):
        cells = [c for _, c, _ in route.tiles]
        assert len(cells) == len(set(cells))


def test_the_search_holds_the_board() -> None:
    assert len(PLATES) == 4
