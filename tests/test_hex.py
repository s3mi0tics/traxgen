"""
Tests for traxgen.hex.

Demonstrates three testing styles:
  1. Plain unit tests (arrange / act / assert)
  2. Parametrized tests (same test, many inputs)
  3. Property-based tests via Hypothesis (check invariants for any input)

Path: traxgen/tests/test_hex.py
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from traxgen.hex import HEX_DIRECTIONS, ORIGIN, CubeVector, HexVector

# --- Hypothesis strategies -------------------------------------------------

# Small coords keep test cases readable and avoid integer overflow edge cases.
# Range of ±50 is well beyond any realistic GraviTrax baseplate layout.
SMALL_INT = st.integers(min_value=-50, max_value=50)
hex_vectors = st.builds(HexVector, y=SMALL_INT, x=SMALL_INT)


# --- Plain unit tests ------------------------------------------------------

class TestHexVectorBasics:
    """Basic construction, equality, conversion."""

    def test_origin_is_zero_zero(self) -> None:
        assert ORIGIN == HexVector(0, 0)

    def test_hex_vectors_are_equal_when_coords_match(self) -> None:
        assert HexVector(1, 2) == HexVector(1, 2)

    def test_hex_vectors_are_hashable(self) -> None:
        """Frozen dataclasses are hashable — we'll want hexes as dict keys."""
        d = {HexVector(0, 0): "origin", HexVector(1, 2): "somewhere"}
        assert d[HexVector(0, 0)] == "origin"

    def test_axial_stores_y_before_x(self) -> None:
        """Matches the binary wire format. Order matters for serialization."""
        h = HexVector(y=3, x=7)
        assert h.y == 3
        assert h.x == 7


class TestCubeVectorBasics:
    """Cube coords have the q + r + s = 0 invariant."""

    def test_valid_cube_coords_construct_fine(self) -> None:
        c = CubeVector(1, -2, 1)  # 1 + -2 + 1 = 0
        assert c.q == 1
        assert c.r == -2
        assert c.s == 1

    def test_invalid_cube_coords_raise(self) -> None:
        with pytest.raises(ValueError, match="q \\+ r \\+ s = 0"):
            CubeVector(1, 2, 3)  # sum is 6, not 0


# --- Parametrized tests ----------------------------------------------------

class TestNeighbors:
    """The 6 neighbor directions."""

    @pytest.mark.parametrize(
        "direction,expected",
        [
            (0, HexVector(0, 1)),    # E
            (1, HexVector(-1, 1)),   # NE
            (2, HexVector(-1, 0)),   # NW
            (3, HexVector(0, -1)),   # W
            (4, HexVector(1, -1)),   # SW
            (5, HexVector(1, 0)),    # SE
        ],
    )
    def test_neighbor_from_origin(self, direction: int, expected: HexVector) -> None:
        assert ORIGIN.neighbor(direction) == expected

    def test_neighbors_returns_all_six(self) -> None:
        ns = ORIGIN.neighbors()
        assert len(ns) == 6
        assert len(set(ns)) == 6  # all distinct

    @pytest.mark.parametrize("bad_direction", [-1, 6, 100])
    def test_invalid_direction_raises(self, bad_direction: int) -> None:
        with pytest.raises(ValueError, match="direction must be 0..5"):
            ORIGIN.neighbor(bad_direction)


class TestDistance:
    """Hex distance: number of steps between two cells."""

    @pytest.mark.parametrize(
        "a,b,expected",
        [
            (HexVector(0, 0), HexVector(0, 0), 0),       # same cell
            (HexVector(0, 0), HexVector(0, 1), 1),       # adjacent (E)
            (HexVector(0, 0), HexVector(-1, 1), 1),      # adjacent (NE)
            (HexVector(0, 0), HexVector(0, 5), 5),       # straight east
            (HexVector(0, 0), HexVector(-3, 3), 3),      # straight NE
            (HexVector(0, 0), HexVector(2, 2), 4),       # diagonal-ish
        ],
    )
    def test_distance_matches_expected(
        self, a: HexVector, b: HexVector, expected: int
    ) -> None:
        assert a.distance_to(b) == expected


class TestRotation:
    """Rotation around the origin."""

    def test_zero_steps_is_identity(self) -> None:
        h = HexVector(2, -1)
        assert h.rotate(0) == h

    def test_six_steps_is_identity(self) -> None:
        h = HexVector(2, -1)
        assert h.rotate(6) == h

    def test_rotating_east_neighbor_by_one_step_gives_ne_neighbor(self) -> None:
        east = ORIGIN.neighbor(0)
        ne = ORIGIN.neighbor(1)
        assert east.rotate(1) == ne

    def test_rotating_east_neighbor_six_times_visits_all_neighbors(self) -> None:
        """Rotating a neighbor by 0..5 steps should produce all 6 neighbors."""
        east = ORIGIN.neighbor(0)
        rotated = {east.rotate(s) for s in range(6)}
        assert rotated == set(ORIGIN.neighbors())


# --- Property-based tests --------------------------------------------------

class TestHexProperties:
    """
    Properties that must hold for ANY hex coordinate.

    Hypothesis generates random inputs; these tests should pass for all of them.
    If one fails, Hypothesis shrinks the counterexample to the simplest input
    that breaks the property.
    """

    @given(hex_vectors)
    def test_axial_to_cube_and_back_is_identity(self, h: HexVector) -> None:
        """Round-trip conversion preserves the coordinate."""
        assert h.to_cube().to_axial() == h

    @given(hex_vectors)
    def test_cube_coords_always_sum_to_zero(self, h: HexVector) -> None:
        """The defining invariant of cube coordinates."""
        c = h.to_cube()
        assert c.q + c.r + c.s == 0

    @given(hex_vectors)
    def test_distance_to_self_is_zero(self, h: HexVector) -> None:
        assert h.distance_to(h) == 0

    @given(hex_vectors, hex_vectors)
    def test_distance_is_symmetric(self, a: HexVector, b: HexVector) -> None:
        assert a.distance_to(b) == b.distance_to(a)

    @given(hex_vectors)
    def test_all_neighbors_are_distance_one(self, h: HexVector) -> None:
        for n in h.neighbors():
            assert h.distance_to(n) == 1

    @given(hex_vectors, st.integers(min_value=-20, max_value=20))
    def test_rotation_by_six_is_identity(self, h: HexVector, k: int) -> None:
        """
        Rotating by any multiple of 6 steps returns to the original position.
        (Since each step is 60° and 6 × 60° = 360°.)
        """
        assert h.rotate(6 * k) == h

    @given(hex_vectors, st.integers(min_value=-20, max_value=20))
    def test_rotation_preserves_distance_from_origin(
        self, h: HexVector, steps: int
    ) -> None:
        """Rotation is a rigid motion — it preserves distances."""
        assert h.rotate(steps).distance_to(ORIGIN) == h.distance_to(ORIGIN)

    @given(hex_vectors, hex_vectors)
    def test_addition_is_commutative(self, a: HexVector, b: HexVector) -> None:
        assert a + b == b + a

    @given(hex_vectors)
    def test_subtracting_self_is_origin(self, h: HexVector) -> None:
        assert h - h == ORIGIN


# --- Sanity check on module-level constants --------------------------------

def test_hex_directions_has_six_entries() -> None:
    assert len(HEX_DIRECTIONS) == 6

def test_hex_directions_are_all_distinct() -> None:
    assert len(set(HEX_DIRECTIONS)) == 6

def test_hex_directions_are_all_unit_distance_from_origin() -> None:
    for dy, dx in HEX_DIRECTIONS:
        h = HexVector(dy, dx)
        assert h.distance_to(ORIGIN) == 1
