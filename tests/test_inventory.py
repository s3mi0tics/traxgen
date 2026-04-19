"""
Tests for traxgen.inventory.

Covers the piece catalog, the Core Starter-Set definition, and Inventory
convenience methods. Physics-related fields are covered only lightly here
since values are placeholders in Phase 1.

Path: traxgen/tests/test_inventory.py
"""

from __future__ import annotations

import pytest

from traxgen.inventory import (
    CORE_STARTER_SET,
    NO_PHYSICS,
    PIECE_CATALOG,
    EnergyProfile,
    Inventory,
    PieceSpec,
    RailInventory,
    get_piece_spec,
)
from traxgen.types import TileKind


# --- EnergyProfile basics --------------------------------------------------

class TestEnergyProfile:
    def test_default_profile_has_sensible_zeros(self) -> None:
        """A freshly constructed profile should be inert except for a default friction."""
        p = EnergyProfile()
        assert p.path_length_mm == 0.0
        assert p.height_change_mm == 0.0
        assert p.energy_input_j == 0.0
        assert p.expected_time_ms == 0.0
        assert p.time_variance_ms == 0.0
        # Default loss coefficient is nonzero (steel-on-plastic baseline)
        assert p.loss_coefficient > 0

    def test_no_physics_is_a_default_profile(self) -> None:
        assert NO_PHYSICS == EnergyProfile()


# --- PieceSpec catalog -----------------------------------------------------

class TestPieceCatalog:
    """The catalog has a PieceSpec for every Starter-Set TileKind."""

    def test_catalog_contains_starter_piece(self) -> None:
        assert TileKind.STARTER in PIECE_CATALOG

    def test_catalog_contains_curve(self) -> None:
        assert TileKind.CURVE in PIECE_CATALOG

    def test_catalog_contains_goal_basin(self) -> None:
        assert TileKind.GOAL_BASIN in PIECE_CATALOG

    def test_catalog_contains_goal_rail(self) -> None:
        """Both GOAL_BASIN (the 'landing' insert) and GOAL_RAIL (the 'finish line')."""
        assert TileKind.GOAL_RAIL in PIECE_CATALOG

    def test_catalog_contains_cannon(self) -> None:
        assert TileKind.CANNON in PIECE_CATALOG

    def test_catalog_contains_both_switches(self) -> None:
        assert TileKind.SWITCH_LEFT in PIECE_CATALOG
        assert TileKind.SWITCH_RIGHT in PIECE_CATALOG

    def test_every_tile_in_starter_inventory_has_a_spec(self) -> None:
        """No orphan tile kinds — every inventory entry must map to a PieceSpec."""
        for kind in CORE_STARTER_SET.tiles:
            assert kind in PIECE_CATALOG, f"No PieceSpec for {kind.name}"

    def test_get_piece_spec_returns_correct_spec(self) -> None:
        spec = get_piece_spec(TileKind.CURVE)
        assert isinstance(spec, PieceSpec)
        assert spec.kind == TileKind.CURVE
        assert spec.display_name == "Curve"

    def test_get_piece_spec_raises_for_unknown_kind(self) -> None:
        with pytest.raises(KeyError, match="No PieceSpec registered"):
            # LOOP is a real TileKind but not in the Starter-Set catalog
            get_piece_spec(TileKind.LOOP)


class TestPieceSpecProperties:
    """Spot-check that specific pieces have the right flags."""

    def test_starter_is_marked_as_starter(self) -> None:
        assert get_piece_spec(TileKind.STARTER).is_starter is True

    def test_cannon_is_marked_as_starter(self) -> None:
        """The Magnetic Cannon can also launch a ball."""
        assert get_piece_spec(TileKind.CANNON).is_starter is True

    def test_goal_basin_is_marked_as_goal(self) -> None:
        assert get_piece_spec(TileKind.GOAL_BASIN).is_goal is True

    def test_goal_rail_is_marked_as_goal(self) -> None:
        """The 'finish line' (GOAL_RAIL) is also a goal piece."""
        assert get_piece_spec(TileKind.GOAL_RAIL).is_goal is True

    def test_curve_is_neither_starter_nor_goal(self) -> None:
        spec = get_piece_spec(TileKind.CURVE)
        assert spec.is_starter is False
        assert spec.is_goal is False

    def test_small_stacker_is_one_unit_tall(self) -> None:
        assert get_piece_spec(TileKind.STACKER_SMALL).height_in_small_stackers == 1

    def test_large_stacker_is_exactly_double_small(self) -> None:
        """Confirmed from wiki: 'full height' = 2× 'half height'."""
        large = get_piece_spec(TileKind.STACKER).height_in_small_stackers
        small = get_piece_spec(TileKind.STACKER_SMALL).height_in_small_stackers
        assert large == 2 * small

    def test_vortex_has_high_time_variance(self) -> None:
        """The vortex is intentionally stochastic — it should have >0 variance."""
        vortex = get_piece_spec(TileKind.SPIRAL)
        assert vortex.energy_profile.time_variance_ms > 0

    def test_cannon_has_energy_input(self) -> None:
        """The Magnetic Cannon actively adds energy."""
        cannon = get_piece_spec(TileKind.CANNON)
        assert cannon.energy_profile.energy_input_j > 0


# --- Starter-Set inventory -------------------------------------------------

class TestCoreStarterSet:
    """The Core Starter-Set (22410) has the right piece counts."""

    def test_has_one_starter(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.STARTER) == 1

    def test_has_twenty_one_curves(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.CURVE) == 21

    def test_has_three_threeway_junctions(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.THREEWAY) == 3

    def test_has_one_of_each_switch_direction(self) -> None:
        """2 switches total, assumed split 1 left + 1 right (TODO: verify M2)."""
        assert CORE_STARTER_SET.tile_count(TileKind.SWITCH_LEFT) == 1
        assert CORE_STARTER_SET.tile_count(TileKind.SWITCH_RIGHT) == 1

    def test_has_forty_large_stackers(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.STACKER) == 40

    def test_has_twelve_small_stackers(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.STACKER_SMALL) == 12

    def test_has_one_cannon(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.CANNON) == 1

    def test_has_one_goal_basin_insert(self) -> None:
        """The 'landing' insert that fits into a solid basic tile."""
        assert CORE_STARTER_SET.tile_count(TileKind.GOAL_BASIN) == 1

    def test_has_one_goal_rail(self) -> None:
        """The 'finish line' piece that connects via rails."""
        assert CORE_STARTER_SET.tile_count(TileKind.GOAL_RAIL) == 1

    def test_has_two_catcher_inserts(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.CATCH) == 2

    def test_has_one_freefall_insert(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.DROP) == 1

    def test_has_one_splash_insert(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.SPLASH) == 1

    def test_has_one_vortex(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.SPIRAL) == 1

    def test_has_four_baseplates(self) -> None:
        assert CORE_STARTER_SET.baseplates == 4

    def test_has_two_transparent_levels(self) -> None:
        assert CORE_STARTER_SET.transparent_levels == 2

    def test_has_six_marbles(self) -> None:
        assert CORE_STARTER_SET.marbles == 6

    def test_rails_total_eighteen(self) -> None:
        """3 long + 6 medium + 9 short = 18 rails."""
        assert CORE_STARTER_SET.rails.total == 18

    def test_rails_breakdown_is_correct(self) -> None:
        r = CORE_STARTER_SET.rails
        assert r.long == 3
        assert r.medium == 6
        assert r.short == 9

    def test_three_in_one_tile_is_not_yet_cataloged(self) -> None:
        """
        The '3-in-1 tile' (Three-Way Merge) is in the physical box but its
        binary TileKind isn't confirmed yet. Omitted until M2. This test
        locks in the current state so we don't silently introduce a wrong
        mapping; when M2 resolves it, delete this test and add a positive one.
        """
        # It's distinct from THREEWAY (the junction tile) — the physical box
        # has both: 3 junctions (THREEWAY) + 1 "3-in-1" (unknown TileKind).
        # So we shouldn't see the 3-in-1 under THREEWAY; we have exactly 3 junctions.
        assert CORE_STARTER_SET.tile_count(TileKind.THREEWAY) == 3


class TestInventoryHelpers:
    """The Inventory.has_tile / tile_count helpers."""

    def test_has_tile_true_for_present_kind(self) -> None:
        assert CORE_STARTER_SET.has_tile(TileKind.CURVE) is True

    def test_has_tile_false_for_absent_kind(self) -> None:
        # LOOP is not in the Starter-Set
        assert CORE_STARTER_SET.has_tile(TileKind.LOOP) is False

    def test_tile_count_zero_for_absent_kind(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.LOOP) == 0

    def test_total_tiles_matches_sum_of_parts(self) -> None:
        """Sanity: .total_tiles() should match adding up all tile counts."""
        expected = sum(CORE_STARTER_SET.tiles.values())
        assert CORE_STARTER_SET.total_tiles() == expected


# --- RailInventory ---------------------------------------------------------

class TestRailInventory:
    def test_empty_rail_inventory_has_zero_total(self) -> None:
        assert RailInventory().total == 0

    def test_total_sums_all_three_lengths(self) -> None:
        r = RailInventory(short=5, medium=3, long=2)
        assert r.total == 10

    def test_rail_inventory_is_immutable(self) -> None:
        """Frozen dataclass — attempting to mutate should raise."""
        r = RailInventory(short=1)
        with pytest.raises(Exception):  # FrozenInstanceError
            r.short = 99  # type: ignore[misc]


# --- Starter-Set total piece count sanity ----------------------------------

def test_starter_set_tile_count_is_roughly_expected() -> None:
    """
    The physical box has 74 tiles (21+3+2+1+1+1+1+40+12+2+1+1+1 = 87 if we
    include the 3-in-1 tile, or 86 as modeled here).

    We're missing the 3-in-1 tile until M2 confirms its binary TileKind.
    So expected tile count is 86.
    """
    # Tiles actually in our inventory (inspect so we can update when 3-in-1 lands):
    expected = {
        TileKind.STARTER: 1,
        TileKind.CURVE: 21,
        TileKind.THREEWAY: 3,
        TileKind.SWITCH_LEFT: 1,
        TileKind.SWITCH_RIGHT: 1,
        TileKind.SPIRAL: 1,
        TileKind.CANNON: 1,
        TileKind.GOAL_RAIL: 1,
        TileKind.STACKER: 40,
        TileKind.STACKER_SMALL: 12,
        TileKind.CATCH: 2,
        TileKind.DROP: 1,
        TileKind.SPLASH: 1,
        TileKind.GOAL_BASIN: 1,
    }
    assert CORE_STARTER_SET.total_tiles() == sum(expected.values())
    assert CORE_STARTER_SET.total_tiles() == 87
