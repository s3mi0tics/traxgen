# Path: traxgen/tests/test_plates.py
"""Baseplate footprints: the world-fixed half of the connection conjunction.

These pin a *measurement* -- `scripts/probe_plate_footprint.py` over 640 parsed
courses -- so a change that silently edits the footprint has to argue with the
corpus rather than with an opinion. The corner asymmetry these tests record is
what explained open unknown #15 (`decisions.md` 2026-08-21).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from traxgen.hex import HexVector
from traxgen.plates import (
    MEASURED_FOOTPRINTS,
    UnmeasuredLayerKindError,
    is_on_plate,
    plate_available_directions,
    plate_footprint,
)
from traxgen.types import LayerKind

PLATE = LayerKind.BASE_LAYER_PIECE
CORNER = HexVector(y=0, x=0)
EDGE = HexVector(y=0, x=1)
INTERIOR = HexVector(y=-3, x=2)

E, NE, NW, W, SW, SE = range(6)


# --- what the corpus measured ----------------------------------------------


@pytest.mark.parametrize(
    ("kind", "cells"),
    [
        (LayerKind.BASE_LAYER_PIECE, 30),
        (LayerKind.LARGE_LAYER, 19),
        (LayerKind.SMALL_LAYER, 7),
    ],
)
def test_each_measured_footprint_has_the_size_the_corpus_showed(
    kind: LayerKind, cells: int
) -> None:
    """28,494 / 12,668 / 2,959 placements resolve to exactly these cell counts."""
    assert len(plate_footprint(kind)) == cells


def test_the_baseplate_spans_the_measured_coordinate_window() -> None:
    positions = plate_footprint(PLATE)
    assert {y for y, _ in positions} == set(range(-6, 1))
    assert {x for _, x in positions} == set(range(0, 6))


@given(st.integers(min_value=-9, max_value=9), st.integers(min_value=-9, max_value=9))
def test_membership_agrees_with_the_footprint_set(y: int, x: int) -> None:
    """Property: `is_on_plate` is exactly set membership, for every kind's frame."""
    assert is_on_plate(PLATE, HexVector(y=y, x=x)) == ((y, x) in plate_footprint(PLATE))


# --- the corner, which is the whole point ----------------------------------


def test_the_baseplate_origin_is_a_corner() -> None:
    """W, SW and SE are unobserved in 28,494 placements -- the missing coordinate.

    Every sweep through 2026-08-10 pinned the STARTER here, so half of every
    36-cell sweep was spent on cells that were dead by construction and the
    table recorded the rotation while absorbing the position.
    """
    assert plate_available_directions(PLATE, CORNER) == frozenset({E, NE, NW})


@pytest.mark.parametrize(
    ("pos", "expected"),
    [
        (CORNER, frozenset({E, NE, NW})),
        (EDGE, frozenset({NE, NW, W})),
        (INTERIOR, frozenset(range(6))),
    ],
)
def test_the_three_probed_positions_have_the_availability_the_probe_used(
    pos: HexVector, expected: frozenset[int]
) -> None:
    """The plate term as the 2026-08-21 runs consumed it, position by position."""
    assert plate_available_directions(PLATE, pos) == expected


@pytest.mark.parametrize("kind", [LayerKind.LARGE_LAYER, LayerKind.SMALL_LAYER])
def test_the_stacked_layers_are_centred_hexagons_unlike_the_baseplate(
    kind: LayerKind,
) -> None:
    """Contrast that makes the corner legible: these have all six neighbours.

    `LARGE_LAYER` (19 cells) and `SMALL_LAYER` (7) are hexagons centred on their
    local origin, so a starter at their (0,0) is unconstrained by the plate term.
    `BASE_LAYER_PIECE` is not, and that difference is the finding.
    """
    assert plate_available_directions(kind, HexVector(y=0, x=0)) == frozenset(range(6))


# --- invisible is not absent ------------------------------------------------


@pytest.mark.parametrize("kind", [LayerKind.BASE_LAYER, LayerKind.LARGE_GHOST_LAYER])
def test_an_unobserved_layer_kind_refuses_rather_than_reporting_an_empty_plate(
    kind: LayerKind,
) -> None:
    """Zero corpus observations means invisible, not absent (`decisions.md` 2026-08-21).

    Returning `False` for every cell would turn a gap in the record into a claim
    about the layer -- the same failure the three-valued ConnectionStatus exists
    to prevent one level up. GOAL_RAIL's zero port records are the counterexample
    that scoped that rule.
    """
    with pytest.raises(UnmeasuredLayerKindError):
        plate_footprint(kind)
    with pytest.raises(UnmeasuredLayerKindError):
        is_on_plate(kind, HexVector(y=0, x=0))
    with pytest.raises(UnmeasuredLayerKindError):
        plate_available_directions(kind, HexVector(y=0, x=0))


def test_the_refusal_names_what_would_fix_it() -> None:
    with pytest.raises(UnmeasuredLayerKindError) as excinfo:
        plate_footprint(LayerKind.BASE_LAYER)
    message = str(excinfo.value)
    assert "invisible, not absent" in message
    assert "probe_plate_footprint" in message


def test_only_observed_kinds_are_in_the_table() -> None:
    """The footprint table claims exactly the three kinds the corpus showed."""
    assert set(MEASURED_FOOTPRINTS) == {
        LayerKind.BASE_LAYER_PIECE,
        LayerKind.LARGE_LAYER,
        LayerKind.SMALL_LAYER,
    }
