"""Tests for the inventory module.

Covers piece catalog, Core Starter-Set composition, inventory helpers,
structural inventory types, and the flat rail map.

Path: traxgen/tests/test_inventory.py
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from traxgen.inventory import (
    CORE_STARTER_SET,
    EMPTY_STRUCTURAL,
    NO_PHYSICS,
    PIECE_CATALOG,
    PILLAR_KIND_TO_TILE_KIND,
    PRO_VERTICAL_STARTER_SET,
    STRAIGHT_RAIL_SPECS,
    EnergyProfile,
    Inventory,
    PieceSpec,
    PillarKind,
    RailLength,
    StructuralInventory,
    WallKind,
    get_piece_spec,
)
from traxgen.types import RailKind, TileKind

# --- EnergyProfile --------------------------------------------------------

class TestEnergyProfile:
    def test_default_profile_has_sensible_zeros(self) -> None:
        p = EnergyProfile()
        assert p.path_length_mm == 0.0
        assert p.height_change_mm == 0.0
        assert p.energy_input_j == 0.0
        assert p.expected_time_ms == 0.0
        assert p.time_variance_ms == 0.0

    def test_no_physics_is_a_default_profile(self) -> None:
        assert EnergyProfile() == NO_PHYSICS


# --- Piece catalog --------------------------------------------------------

class TestPieceCatalog:
    def test_catalog_contains_starter_piece(self) -> None:
        assert TileKind.STARTER in PIECE_CATALOG

    def test_catalog_contains_curve(self) -> None:
        assert TileKind.CURVE in PIECE_CATALOG

    def test_catalog_contains_goal_basin(self) -> None:
        assert TileKind.GOAL_BASIN in PIECE_CATALOG

    def test_catalog_contains_goal_rail(self) -> None:
        assert TileKind.GOAL_RAIL in PIECE_CATALOG

    def test_catalog_contains_cannon(self) -> None:
        assert TileKind.CANNON in PIECE_CATALOG

    def test_catalog_contains_both_switches(self) -> None:
        assert TileKind.SWITCH_LEFT in PIECE_CATALOG
        assert TileKind.SWITCH_RIGHT in PIECE_CATALOG

    def test_catalog_contains_cross(self) -> None:
        """PRO Vertical introduces CROSS; must be cataloged."""
        assert TileKind.CROSS in PIECE_CATALOG

    def test_catalog_contains_three_entrance_funnel(self) -> None:
        """The 3-in-1 / 3-way merge tile. Best-guess TileKind mapping."""
        assert TileKind.THREE_ENTRANCE_FUNNEL in PIECE_CATALOG

    def test_every_tile_in_core_inventory_has_a_spec(self) -> None:
        for kind in CORE_STARTER_SET.tiles:
            assert kind in PIECE_CATALOG, f"No PieceSpec for {kind!r}"

    def test_get_piece_spec_returns_correct_spec(self) -> None:
        spec = get_piece_spec(TileKind.CURVE)
        assert spec.kind is TileKind.CURVE
        assert isinstance(spec, PieceSpec)

    def test_get_piece_spec_raises_for_unknown_kind(self) -> None:
        with pytest.raises(KeyError):
            get_piece_spec(TileKind.VOLCANO)  # not cataloged


# --- PieceSpec properties -------------------------------------------------

class TestPieceSpecProperties:
    def test_starter_is_marked_as_starter(self) -> None:
        assert get_piece_spec(TileKind.STARTER).is_starter is True

    def test_cannon_is_not_a_starter(self) -> None:
        """The Magnetic Cannon is an energy injector, not a starter.

        A ball must arrive at the cannon (via gravity from elsewhere) for
        the cannon to do anything — it can't initiate a run. Its role is
        modeled via energy_profile.energy_input_j, not is_starter.
        """
        assert get_piece_spec(TileKind.CANNON).is_starter is False

    def test_goal_basin_is_marked_as_goal(self) -> None:
        assert get_piece_spec(TileKind.GOAL_BASIN).is_goal is True

    def test_goal_rail_is_marked_as_goal(self) -> None:
        assert get_piece_spec(TileKind.GOAL_RAIL).is_goal is True

    def test_curve_is_neither_starter_nor_goal(self) -> None:
        spec = get_piece_spec(TileKind.CURVE)
        assert spec.is_starter is False
        assert spec.is_goal is False

    def test_small_stacker_is_one_unit_tall(self) -> None:
        assert get_piece_spec(TileKind.STACKER_SMALL).height_in_small_stackers == 1

    def test_large_stacker_is_exactly_double_small(self) -> None:
        """Confirmed from wiki: 'full height' = 2x 'half height'."""
        large = get_piece_spec(TileKind.STACKER).height_in_small_stackers
        small = get_piece_spec(TileKind.STACKER_SMALL).height_in_small_stackers
        assert large == 2 * small

    def test_vortex_has_high_time_variance(self) -> None:
        spec = get_piece_spec(TileKind.SPIRAL)
        assert spec.energy_profile.time_variance_ms > 0

    def test_cannon_has_energy_input(self) -> None:
        spec = get_piece_spec(TileKind.CANNON)
        assert spec.energy_profile.energy_input_j > 0


# --- Core Starter-Set composition -----------------------------------------

class TestCoreStarterSet:
    def test_has_one_starter(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.STARTER) == 1

    def test_has_twenty_one_curves(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.CURVE) == 21

    def test_has_three_threeway_junctions(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.THREEWAY) == 3

    def test_has_one_three_entrance_funnel(self) -> None:
        """The '3-in-1' is now cataloged as THREE_ENTRANCE_FUNNEL."""
        assert CORE_STARTER_SET.tile_count(TileKind.THREE_ENTRANCE_FUNNEL) == 1

    def test_has_two_of_each_switch_direction(self) -> None:
        """Switches are a pool of 2 physical pieces, encoded as 2 of each TileKind.

        See the comment in inventory.py CORE_STARTER_SET — the TileKind encoding
        assumption is unverified and needs empirical testing.
        """
        assert CORE_STARTER_SET.tile_count(TileKind.SWITCH_LEFT) == 2
        assert CORE_STARTER_SET.tile_count(TileKind.SWITCH_RIGHT) == 2

    def test_has_forty_large_stackers(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.STACKER) == 40

    def test_has_twelve_small_stackers(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.STACKER_SMALL) == 12

    def test_has_one_cannon(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.CANNON) == 1

    def test_has_one_splash(self) -> None:
        """Core includes a SPLASH insert (unlike 26832 which has none)."""
        assert CORE_STARTER_SET.tile_count(TileKind.SPLASH) == 1

    def test_has_one_goal_basin(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.GOAL_BASIN) == 1

    def test_has_one_goal_rail(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.GOAL_RAIL) == 1

    def test_has_two_catchers(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.CATCH) == 2

    def test_has_one_drop(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.DROP) == 1

    def test_has_one_vortex(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.SPIRAL) == 1

    def test_has_four_baseplates(self) -> None:
        assert CORE_STARTER_SET.baseplates == 4

    def test_has_two_transparent_levels(self) -> None:
        assert CORE_STARTER_SET.transparent_levels == 2

    def test_has_six_marbles(self) -> None:
        assert CORE_STARTER_SET.marbles == 6

    def test_has_four_basic_tile_frames(self) -> None:
        """4 frames hold 4 of the 5 inserts at a time."""
        assert CORE_STARTER_SET.basic_tile_frames == 4

    def test_rails_are_straight_only(self) -> None:
        """Core has only STRAIGHT rails; no Bernoullis."""
        assert RailKind.STRAIGHT in CORE_STARTER_SET.rails
        for kind in (
            RailKind.BERNOULLI_SMALL_LEFT,
            RailKind.BERNOULLI_SMALL_RIGHT,
            RailKind.BERNOULLI_SMALL_STRAIGHT,
        ):
            assert CORE_STARTER_SET.rail_count(kind) == 0

    def test_rails_total_eighteen(self) -> None:
        """9 short + 6 medium + 3 long = 18 straight rails."""
        assert CORE_STARTER_SET.total_rails() == 18

    def test_straight_rail_limits(self) -> None:
        limits = CORE_STARTER_SET.straight_rail_limits
        assert limits[RailLength.SHORT] == 9
        assert limits[RailLength.MEDIUM] == 6
        assert limits[RailLength.LONG] == 3

    def test_straight_rail_limits_total_matches_rail_pool(self) -> None:
        """Sum of per-length limits equals the STRAIGHT rail pool size."""
        pool = CORE_STARTER_SET.rail_count(RailKind.STRAIGHT)
        limits_total = sum(CORE_STARTER_SET.straight_rail_limits.values())
        assert pool == limits_total


# --- Inventory helpers ----------------------------------------------------

class TestInventoryHelpers:
    def test_has_tile_true_for_present_kind(self) -> None:
        assert CORE_STARTER_SET.has_tile(TileKind.CURVE) is True

    def test_has_tile_false_for_absent_kind(self) -> None:
        assert CORE_STARTER_SET.has_tile(TileKind.VOLCANO) is False

    def test_tile_count_zero_for_absent_kind(self) -> None:
        assert CORE_STARTER_SET.tile_count(TileKind.VOLCANO) == 0

    def test_total_tiles_matches_sum_of_parts(self) -> None:
        total = CORE_STARTER_SET.total_tiles()
        manual = sum(CORE_STARTER_SET.tiles.values())
        assert total == manual

    def test_rail_count_zero_for_absent_kind(self) -> None:
        assert CORE_STARTER_SET.rail_count(RailKind.U_TURN) == 0


# --- Rail length specs ----------------------------------------------------

class TestStraightRailSpecs:
    def test_short_rail_max_hex_distance(self) -> None:
        assert STRAIGHT_RAIL_SPECS[RailLength.SHORT].max_hex_distance == 1

    def test_medium_rail_max_hex_distance(self) -> None:
        assert STRAIGHT_RAIL_SPECS[RailLength.MEDIUM].max_hex_distance == 2

    def test_long_rail_max_hex_distance(self) -> None:
        assert STRAIGHT_RAIL_SPECS[RailLength.LONG].max_hex_distance == 3

    def test_short_rail_max_delta(self) -> None:
        """Physical manual + test: short handles 2 full + 1 half = 5 small-stacker units."""
        assert STRAIGHT_RAIL_SPECS[RailLength.SHORT].max_delta_small_stacker == 5

    def test_medium_rail_max_delta(self) -> None:
        """Physical manual + test: medium handles 3 full + 1 half = 7 small-stacker units."""
        assert STRAIGHT_RAIL_SPECS[RailLength.MEDIUM].max_delta_small_stacker == 7

    def test_long_rail_max_delta(self) -> None:
        """Physical manual + test: long handles 4 full = 8 small-stacker units.

        Contradicts the GraviTrax Fandom wiki which lists 3.5 full-tiles.
        The manufacturer manual and physical testing both confirm 4 full.
        """
        assert STRAIGHT_RAIL_SPECS[RailLength.LONG].max_delta_small_stacker == 8


# --- Rail inventory immutability ------------------------------------------

class TestRailInventory:
    def test_empty_inventory_has_zero_rail_total(self) -> None:
        inv = Inventory(
            name="empty",
            tiles={},
            rails={},
            straight_rail_limits={},
            baseplates=0,
            transparent_levels=0,
            marbles=0,
        )
        assert inv.total_rails() == 0

    def test_inventory_is_immutable(self) -> None:
        """Frozen dataclass — attempting to mutate should raise."""
        with pytest.raises(FrozenInstanceError):
            CORE_STARTER_SET.baseplates = 99  # type: ignore[misc]


# --- Structural inventory -------------------------------------------------

class TestStructuralInventory:
    def test_pillar_kind_values(self) -> None:
        assert PillarKind.CLOSED == 0
        assert PillarKind.OPENED == 1

    def test_wall_kind_values(self) -> None:
        assert WallKind.SHORT == 0
        assert WallKind.MEDIUM == 1
        assert WallKind.LONG == 2

    def test_pillar_kind_to_tile_kind_mapping(self) -> None:
        assert PILLAR_KIND_TO_TILE_KIND[PillarKind.CLOSED] is TileKind.STACKER_TOWER_CLOSED
        assert PILLAR_KIND_TO_TILE_KIND[PillarKind.OPENED] is TileKind.STACKER_TOWER_OPENED

    def test_empty_structural_is_empty(self) -> None:
        assert EMPTY_STRUCTURAL.total_pillars == 0
        assert EMPTY_STRUCTURAL.total_walls == 0
        assert EMPTY_STRUCTURAL.single_balconies == 0
        assert EMPTY_STRUCTURAL.double_balconies == 0
        assert EMPTY_STRUCTURAL.pillar_count(PillarKind.CLOSED) == 0
        assert EMPTY_STRUCTURAL.wall_count(WallKind.SHORT) == 0

    def test_structural_inventory_counting(self) -> None:
        s = StructuralInventory(
            pillars={PillarKind.CLOSED: 8, PillarKind.OPENED: 4},
            walls={WallKind.SHORT: 1, WallKind.MEDIUM: 2, WallKind.LONG: 2},
            single_balconies=16,
            double_balconies=4,
        )
        assert s.total_pillars == 12
        assert s.total_walls == 5
        assert s.pillar_count(PillarKind.CLOSED) == 8
        assert s.pillar_count(PillarKind.OPENED) == 4
        assert s.wall_count(WallKind.LONG) == 2
        assert s.single_balconies == 16
        assert s.double_balconies == 4

    def test_core_starter_set_has_empty_structural(self) -> None:
        assert CORE_STARTER_SET.structural is EMPTY_STRUCTURAL

    def test_pro_vertical_name_no_longer_placeholder(self) -> None:
        """Step 2 replaced placeholder counts with confirmed values."""
        assert "PLACEHOLDER" not in PRO_VERTICAL_STARTER_SET.name
        assert PRO_VERTICAL_STARTER_SET.name == "PRO Vertical Starter-Set (26832)"

    def test_pro_vertical_rail_counts(self) -> None:
        assert PRO_VERTICAL_STARTER_SET.rail_count(RailKind.STRAIGHT) == 18
        assert PRO_VERTICAL_STARTER_SET.rail_count(RailKind.BERNOULLI_SMALL_LEFT) == 3
        assert PRO_VERTICAL_STARTER_SET.rail_count(RailKind.BERNOULLI_SMALL_RIGHT) == 3
        assert PRO_VERTICAL_STARTER_SET.rail_count(RailKind.BERNOULLI_SMALL_STRAIGHT) == 2
        assert PRO_VERTICAL_STARTER_SET.total_rails() == 26

    def test_pro_vertical_standalone_tile_counts(self) -> None:
        inv = PRO_VERTICAL_STARTER_SET
        assert inv.tile_count(TileKind.STARTER) == 1
        assert inv.tile_count(TileKind.CURVE) == 28
        assert inv.tile_count(TileKind.CROSS) == 4
        assert inv.tile_count(TileKind.SPIRAL) == 1
        assert inv.tile_count(TileKind.CANNON) == 1
        assert inv.tile_count(TileKind.GOAL_RAIL) == 1
        assert inv.tile_count(TileKind.THREE_ENTRANCE_FUNNEL) == 1

    def test_pro_vertical_insert_counts(self) -> None:
        inv = PRO_VERTICAL_STARTER_SET
        assert inv.tile_count(TileKind.CATCH) == 2
        assert inv.tile_count(TileKind.DROP) == 1
        assert inv.tile_count(TileKind.THREEWAY) == 1
        assert inv.tile_count(TileKind.GOAL_BASIN) == 1

    def test_pro_vertical_has_no_splash(self) -> None:
        """26832 does NOT include SPLASH — unlike Core Starter-Set."""
        assert PRO_VERTICAL_STARTER_SET.tile_count(TileKind.SPLASH) == 0

    def test_pro_vertical_switch_pool(self) -> None:
        """Switches encoded as 2 of each TileKind (pool of 2 physical pieces)."""
        inv = PRO_VERTICAL_STARTER_SET
        assert inv.tile_count(TileKind.SWITCH_LEFT) == 2
        assert inv.tile_count(TileKind.SWITCH_RIGHT) == 2

    def test_pro_vertical_stacker_counts(self) -> None:
        inv = PRO_VERTICAL_STARTER_SET
        assert inv.tile_count(TileKind.STACKER) == 20
        assert inv.tile_count(TileKind.STACKER_SMALL) == 9

    def test_pro_vertical_pillars(self) -> None:
        s = PRO_VERTICAL_STARTER_SET.structural
        assert s.pillar_count(PillarKind.CLOSED) == 8
        assert s.pillar_count(PillarKind.OPENED) == 4
        assert s.total_pillars == 12

    def test_pro_vertical_walls(self) -> None:
        s = PRO_VERTICAL_STARTER_SET.structural
        assert s.wall_count(WallKind.SHORT) == 1
        assert s.wall_count(WallKind.MEDIUM) == 2
        assert s.wall_count(WallKind.LONG) == 2
        assert s.total_walls == 5

    def test_pro_vertical_balconies(self) -> None:
        s = PRO_VERTICAL_STARTER_SET.structural
        assert s.single_balconies == 16
        assert s.double_balconies == 4

    def test_pro_vertical_scalars(self) -> None:
        inv = PRO_VERTICAL_STARTER_SET
        assert inv.baseplates == 4
        assert inv.transparent_levels == 1
        assert inv.marbles == 6
        assert inv.basic_tile_frames == 3

    def test_pro_vertical_every_tile_has_catalog_entry(self) -> None:
        """Every TileKind in 26832 inventory must have a cataloged PieceSpec."""
        for kind in PRO_VERTICAL_STARTER_SET.tiles:
            assert kind in PIECE_CATALOG, f"No PieceSpec for {kind!r}"

    def test_pro_vertical_total_tile_count_including_pool_overcounting(self) -> None:
        """Sum of tiles map.

        Note: SWITCH_LEFT+SWITCH_RIGHT are both set to 2 (pool semantics), so this
        sum over-counts. The real physical switch count is 2, not 4. The "pool"
        constraint is enforced by the validator, not by the inventory shape.
        """
        inv = PRO_VERTICAL_STARTER_SET
        # 1+28+4+1+1+1+1 + 2+1+1+1 + 2+2 + 20+9 = 75
        assert inv.total_tiles() == 75


# --- Total piece count sanity check ---------------------------------------

def test_core_starter_set_total_tile_count() -> None:
    """Core total tiles, accounting for switch pool over-counting.

    Switches are encoded as 2 of each TileKind (pool semantics) so this sum
    over-counts the physical 2 switches as 4 in the map. That's fine —
    inventory shape holds the encoded values; the pool constraint is
    enforced by the validator, not by the tile-count sum.

    Breakdown: 34 non-switch non-stacker + 4 switches (pool-encoded) +
    52 stacker + 1 THREE_ENTRANCE_FUNNEL = 91.
    Wait: 35 non-stacker in previous version minus 2 old switches + 4 new switches = 37.
    37 + 52 stackers + 1 THREE_ENTRANCE_FUNNEL (already in 37? or separate?) ...

    Re-deriving cleanly from CORE_STARTER_SET.tiles:
      1 starter + 21 curve + 3 threeway + 2+2 switch + 1 spiral + 1 cannon +
      1 goal_rail + 40 stacker + 12 stacker_small + 2 catch + 1 drop +
      1 splash + 1 goal_basin + 1 three_entrance_funnel = 90.
    """
    assert CORE_STARTER_SET.total_tiles() == 90
