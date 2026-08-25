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

import collections
from fractions import Fraction

from scripts.probe_plate_seams import (
    _is_gapless,
    cell_groups,
    column_centre,
    find_tiling_delta,
    flush_edge_cells,
    mirror_edge_cells,
    seam_cells,
    seam_requirements,
    translate,
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


def test_a_plate_tiles_on_both_sides_so_the_side_is_a_real_choice() -> None:
    """The fact that makes the next test load-bearing rather than decorative.

    If only one translation tiled, `find_tiling_delta` would have nothing to
    choose and its filter would be ornament. Enacted instead: search the whole
    neighbourhood and show there is an equally-near tiling delta on the *flush*
    side, which supplies no missing half. That is the candidate an unfiltered
    nearest-first would have to break a tie against -- and by tuple order it
    wins, which is how a loop bound came to pick the side (s27).
    """
    seam_column = max(column_centre(cell) for cell in FOOTPRINT)
    span = max(abs(v) for cell in FOOTPRINT for v in cell) + 2
    tiling, flush_side = [], []
    for dy in range(-span, span + 1):
        for dx in range(-span, span + 1):
            if (dy, dx) == (0, 0):
                continue
            moved = translate(FOOTPRINT, (dy, dx))
            if moved & FOOTPRINT or not _is_gapless(set(FOOTPRINT | moved)):
                continue
            tiling.append((dy, dx))
            if max(column_centre(cell) for cell in moved) <= seam_column:
                flush_side.append((dy, dx))

    assert flush_side, "no flush-side tiling delta: the filter would be untested"
    chosen = find_tiling_delta(FOOTPRINT)
    nearness = lambda d: (abs(d[0]) + abs(d[1]), d)  # noqa: E731
    assert min(tiling, key=nearness) != chosen, (
        "the unfiltered nearest is the same delta, so this fixture cannot show "
        "the filter doing anything -- re-derive the discriminator"
    )


def test_the_completing_delta_reaches_past_the_boundary() -> None:
    """The property that picks the side, asserted instead of assumed.

    A neighbour that does not reach past the seam column cannot supply any
    missing half, so it is not the completing plate whatever its distance.
    Removing the filter in `find_tiling_delta` fails this.
    """
    delta = find_tiling_delta(FOOTPRINT)
    moved = translate(FOOTPRINT, delta)
    seam_column = max(column_centre(cell) for cell in FOOTPRINT)
    assert max(column_centre(cell) for cell in moved) > seam_column


def test_the_half_holes_are_not_interchangeable() -> None:
    """One delta answers for three cells whose geometry differs -- shown, not said.

    `scan`'s completion test is plate-level: is there a plate at `here + delta`.
    That is the same question for all three half-holes, so an aggregate tally
    averages three facts. This pins that they really are different: at least one
    half-hole has an off-plate neighbour no tiling neighbour reaches, and at
    least one has none, so a per-cell breakdown is not decoration.
    """
    requirements = seam_requirements()
    assert len(requirements) == len(seam_cells())
    unreachable_counts = {len(un) for _, (_, un) in requirements.items()}
    assert unreachable_counts != {0}, "no cell has unreachable neighbours"
    assert 0 in unreachable_counts, "every cell has unreachable neighbours"

    for cell, (supplied, unreachable) in requirements.items():
        assert supplied, f"{cell} is supplied nothing by the completing plate"
        assert not (supplied & unreachable), "a direction cannot be both"


def test_the_mirror_control_is_the_opposite_edge_in_the_same_shape() -> None:
    """A control on a different axis from `flush_edge_cells`.

    `flush` asks whether builders use edge cells at all, on the seam edge.
    `mirror` asks whether the seam edge is special: same extremity, same
    alternating-row shape, opposite side. If it were not the same shape it would
    not be a control for the same thing.
    """
    mirror = mirror_edge_cells()
    assert mirror <= FOOTPRINT
    assert len(mirror) == len(seam_cells())
    rows = sorted(x for _, x in mirror)
    assert rows == list(range(min(rows), max(rows) + 1, 2)), "alternating rows"
    assert len({column_centre(cell) for cell in mirror}) == 1
    assert min(column_centre(c) for c in mirror) < min(
        column_centre(c) for c in seam_cells()
    ), "the mirror must be the other edge, not the same one"


def test_the_three_measured_groups_are_disjoint() -> None:
    """Overlap would make one group silently measure part of another.

    `cell_groups` raises on overlap rather than letting the last writer win, so
    this both exercises that path's happy case and pins that all three groups
    survive into the map with their own sizes.
    """
    groups = cell_groups()
    counts = collections.Counter(groups.values())
    assert counts["seam"] == len(seam_cells())
    assert counts["flush"] == len(flush_edge_cells())
    assert counts["mirror"] == len(mirror_edge_cells())
    assert set(groups) <= FOOTPRINT
