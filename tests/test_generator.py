"""Tests for the M5.b-minimal generator.

Proves the pipeline: generate_minimal() produces a Course that (a) passes
validate_strict against PRO Vertical, and (b) round-trips through the
serializer and parser byte-for-byte. If both hold, the only thing left
to discover in M6 is whether the GraviTrax app accepts our bytes.

Path: traxgen/tests/test_generator.py
"""

from __future__ import annotations

from traxgen.generator import generate_minimal
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.parser import parse_course
from traxgen.serializer import serialize_course
from traxgen.types import TileKind
from traxgen.validator import validate_strict


def test_generate_minimal_passes_validate_strict() -> None:
    """The minimal course must pass every v1 validator rule against PRO Vertical."""
    course = generate_minimal()
    validate_strict(course, PRO_VERTICAL_STARTER_SET)  # raises on failure


def test_generate_minimal_roundtrips() -> None:
    """Serialize -> parse -> serialize produces identical bytes.

    This is the strong correctness claim: every byte we emit is a byte
    our proven parser recognizes as valid POWER_2022.
    """
    course = generate_minimal()
    bytes_1 = serialize_course(course)
    reparsed = parse_course(bytes_1)
    bytes_2 = serialize_course(reparsed)
    assert bytes_1 == bytes_2, "Round-trip byte mismatch"


def test_generate_minimal_has_expected_shape() -> None:
    """Sanity checks on the minimal course's structure.

    The minimal valid course is two adjacent tiles with NO explicit rail:
    the connection is GOAL_RAIL's integrated rail via adjacency. See
    docs/PLAN.md "Rail model breakthrough" (verified active as FLW4TMLP5V).
    """
    course = generate_minimal()

    # One layer, NO explicit rail, no pillars, no walls.
    assert len(course.layer_construction_data) == 1
    assert len(course.rail_construction_data) == 0
    assert len(course.pillar_construction_data) == 0
    assert len(course.wall_construction_data) == 0

    # Layer has exactly two cells.
    layer = course.layer_construction_data[0]
    assert len(layer.cell_construction_datas) == 2

    # Exactly one STARTER and one GOAL_RAIL present.
    cells_by_kind = {
        cell.tree_node_data.construction_data.kind: cell
        for cell in layer.cell_construction_datas
    }
    assert TileKind.STARTER in cells_by_kind
    assert TileKind.GOAL_RAIL in cells_by_kind

    # The two tiles are adjacent (hex distance 1), and the goal is rotated
    # so its integrated rail faces the starter — the proven-valid geometry.
    starter = cells_by_kind[TileKind.STARTER]
    goal = cells_by_kind[TileKind.GOAL_RAIL]
    assert starter.local_hex_position.distance_to(goal.local_hex_position) == 1
    assert goal.tree_node_data.construction_data.hex_rotation == 3
