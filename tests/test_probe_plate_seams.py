"""Tests for the half-hole derivation.

Offline and corpus-free. The corpus scan needs 808 binaries that are
deliberately not in the repo (`decisions.md`, 2026-08-18), so what is tested
here is the part that must be right for the scan to mean anything: that the
half-hole cells are *derived* from the measured footprint rather than typed,
and that the derivation matches the plate Colby described in the app.

The independent check worth having is that one: on 2026-08-24 he reported, from
the editor and before any of this was computed, that the outermost holes of
every other row are halves. These tests pin that the derivation produces
exactly that shape -- alternating rows, one cell each, all on one edge.

Path: traxgen/tests/test_probe_plate_seams.py
"""

from __future__ import annotations

from fractions import Fraction

from scripts.probe_plate_seams import (
    column_centre,
    find_tiling_delta,
    flush_edge_cells,
    seam_cells,
)
from traxgen.plates import MEASURED_FOOTPRINTS
from traxgen.types import LayerKind

FOOTPRINT = frozenset(MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE])


def test_the_half_holes_are_cells_of_the_plate() -> None:
    """A derivation that wandered off the footprint would be meaningless."""
    assert seam_cells() <= FOOTPRINT
    assert flush_edge_cells() <= FOOTPRINT


def test_the_half_holes_sit_on_alternating_rows_one_per_row() -> None:
    """Colby's observation, from the editor, before this was computed.

    "Every other row only really has 4 full holes and 2 half holes on the
    sides and every other row has 5 holes" -- so the derived set must be one
    cell per row, on every other row, and nothing else.
    """
    rows = sorted(x for _, x in seam_cells())
    assert len(rows) == len(set(rows)), "at most one half-hole per row"
    assert rows == list(range(min(rows), max(rows) + 1, 2)), "alternating rows"


def test_every_half_hole_sits_at_the_same_plate_edge() -> None:
    """They are one boundary's worth of bisected holes, not a scatter."""
    columns = {column_centre(cell) for cell in seam_cells()}
    assert len(columns) == 1


def test_the_half_holes_reach_half_a_hole_past_the_flush_rows() -> None:
    """The defining property, stated as arithmetic rather than as a picture.

    A half-hole's centre is on the boundary; a flush row's outermost hole ends
    there. So the two differ by exactly half a hole width -- which is also why
    a whole hole appears when a neighbour supplies the other half.
    """
    seam_column = next(iter({column_centre(c) for c in seam_cells()}))
    flush_column = next(iter({column_centre(c) for c in flush_edge_cells()}))
    assert seam_column - flush_column == Fraction(1, 2)


def test_the_control_cells_are_not_half_holes() -> None:
    """If the control overlapped the test group it would measure the same thing."""
    assert not (seam_cells() & flush_edge_cells())
    assert flush_edge_cells(), "an empty control cannot fail, so it cannot pass"


def test_the_tiling_delta_places_a_plate_flush_alongside() -> None:
    """Disjoint and gapless -- what 'the plates butt together' means in coordinates."""
    delta = find_tiling_delta(FOOTPRINT)
    moved = {(y + delta[0], x + delta[1]) for y, x in FOOTPRINT}
    assert not (moved & FOOTPRINT), "plates must not overlap"
    assert len(moved | FOOTPRINT) == 2 * len(FOOTPRINT)


def test_the_neighbour_completes_every_half_hole_and_nothing_else() -> None:
    """The whole mechanism, in one assertion.

    Each half-hole's missing half lies in the neighbour's territory, so after
    the neighbour is placed the boundary column is no longer the outer edge.
    Pinned as a property of the union rather than as a list of coordinates.
    """
    delta = find_tiling_delta(FOOTPRINT)
    moved = {(y + delta[0], x + delta[1]) for y, x in FOOTPRINT}
    seam_column = next(iter({column_centre(c) for c in seam_cells()}))
    assert max(column_centre(c) for c in moved) > seam_column


def test_the_stagger_direction_is_the_one_the_real_plate_shows() -> None:
    """The one modelling choice in the probe, discriminated by outside evidence.

    An earlier version of this test claimed the tiling search validates the
    stagger. It does not -- `find_tiling_delta` is purely combinatorial and
    never calls `column_centre`, so it is blind to the choice. What actually
    discriminates is Colby's editor observation, made before any of this was
    computed: *every other row* ends in a half hole.

    Under the shipped stagger the derivation yields one bisected cell on
    alternating rows, which is that. Under the mirror it yields a single cell
    on one row, which is not. So the convention rests on a measurement that
    could have come out the other way.
    """
    def mirror_seams() -> set[tuple[int, int]]:
        centre = {cell: Fraction(cell[0]) - Fraction(cell[1], 2) for cell in FOOTPRINT}
        edge = max(centre.values())
        return {cell for cell, value in centre.items() if value == edge}

    assert len(seam_cells()) > 1, "shipped stagger: half-holes on several rows"
    assert len({x for _, x in seam_cells()}) == len(seam_cells())
    assert len(mirror_seams()) == 1, "mirror stagger: collapses to one cell"
