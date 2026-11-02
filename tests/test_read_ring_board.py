"""The ring-board reader's geometry, on made-up screens where the answer is known (s46-t3).

Path: traxgen/tests/test_read_ring_board.py
"""

from __future__ import annotations

import math

from scripts.read_ring_board import apply, best_fit, fit_affine, groups, rule_side, side_of
from traxgen.hex import HexVector

# A made-up camera: an affine map from world cells to screen pixels, skewed like an isometric view.
CAMERA = ((-16.0, 4.0, 300.0), (-8.0, -12.0, 90.0))
CENTRES = [
    HexVector(-5, 4),
    HexVector(-3, 0),
    HexVector(-1, -4),
    HexVector(-1, 2),
    HexVector(1, -2),
]


def test_the_fit_recovers_a_known_camera() -> None:
    affine, residual = fit_affine(CENTRES, [apply(CAMERA, c) for c in CENTRES])
    assert residual < 1e-6
    for got, want in zip(affine, CAMERA, strict=True):
        assert all(math.isclose(g, w, abs_tol=1e-6) for g, w in zip(got, want, strict=True))


def test_the_best_pairing_is_found_when_groups_come_shuffled() -> None:
    shuffled = [apply(CAMERA, CENTRES[i]) for i in (3, 0, 4, 1, 2)]
    _affine, residual, order = best_fit(CENTRES, shuffled)
    assert residual < 1e-6
    assert order == [1, 3, 4, 0, 2]  # ring k is group order[k]


def test_each_neighbour_reads_as_its_own_side() -> None:
    centre = HexVector(-1, 2)
    for d in range(6):
        assert side_of(CAMERA, centre, apply(CAMERA, centre.neighbor(d))) == d


def test_groups_split_where_there_is_a_gap_and_drop_specks() -> None:
    blob_a = {(x, y) for x in range(10) for y in range(10)}
    blob_b = {(x + 30, y) for x in range(10) for y in range(10)}
    speck = {(60, 60)}
    found = groups(blob_a | blob_b | speck, gap=3)
    assert sorted(len(g) for g in found) == [100, 100]


def test_the_rule_side_is_the_curve_measurement() -> None:
    assert {r: rule_side(r) for r in range(6)} == {0: None, 1: 4, 2: 0, 3: 3, 4: None, 5: 1}
