# Path: traxgen/tests/test_probe_plate_arrangement.py
"""Offline tests for the plate-arrangement probe (scripts/probe_plate_arrangement.py).

No corpus, no network. The probe's pure functions are exercised against courses
built by `traxgen.layout`, plus the one committed multi-baseplate fixture.

`test_the_superseded_probe_finds_nothing_in_its_own_fixture` is the reason this
module names the old script at all: it pins the defect rather than describing
it, so the claim in the new probe's docstring rests on an executed check
(observations #24 -- a citation whose target does not contain the cited fact
reads as having been checked).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.probe_plate_arrangement import (
    footprint_collisions,
    lattice_basis_from,
    normalised,
    on_lattice,
    pairwise_deltas,
    plate_positions,
    report,
    scan,
)
from traxgen.hex import HexVector
from traxgen.layout import TilePlacement, build_course
from traxgen.parser import parse_course
from traxgen.plates import MEASURED_FOOTPRINTS
from traxgen.plates import STANDARD_SQUARE as PLATES_STANDARD_SQUARE
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind, TileKind

FIXTURE = Path(__file__).parent / "fixtures" / "GDZJZA3J3T.course"

# Derived from the generated constant rather than re-typed: a second typed copy
# of a measured set is the same untested claim one file over.
STANDARD_SQUARE = tuple(HexVector(y=y, x=x) for y, x in PLATES_STANDARD_SQUARE)
STARTER = (TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),)


def test_plate_positions_reads_every_plate_in_order() -> None:
    course = build_course(plate_world_positions=STANDARD_SQUARE, tiles=STARTER)
    assert plate_positions(course) == PLATES_STANDARD_SQUARE


def test_plate_positions_ignores_non_baseplate_layers() -> None:
    """The fixture's LARGE_LAYER and SMALL_LAYER must not be counted as plates."""
    course = parse_course(FIXTURE.read_bytes())
    kinds = [layer.layer_kind for layer in course.layer_construction_data]
    assert LayerKind.LARGE_LAYER in kinds and LayerKind.SMALL_LAYER in kinds
    assert len(plate_positions(course)) == kinds.count(LayerKind.BASE_LAYER_PIECE)
    assert len(plate_positions(course)) < len(kinds)


def test_the_standard_square_has_no_footprint_collisions() -> None:
    assert footprint_collisions(PLATES_STANDARD_SQUARE) == 0


def test_two_plates_at_one_position_collide_on_every_cell() -> None:
    """A degenerate arrangement the builder refuses -- the detector must see it."""
    assert footprint_collisions(((0, 0), (0, 0))) == 30


def test_a_one_cell_shift_collides_on_the_overlap_only() -> None:
    """Sanity that the count is cells-shared, not a boolean in disguise."""
    collisions = footprint_collisions(((0, 0), (0, 1)))
    assert 0 < collisions < 30


def test_the_committed_fixture_tiles_without_overlap() -> None:
    """15 real baseplates, measured -- the check the superseded probe intended."""
    course = parse_course(FIXTURE.read_bytes())
    positions = plate_positions(course)
    assert len(positions) == 15
    assert footprint_collisions(positions) == 0


def test_pairwise_deltas_are_ordered_pairs_and_come_in_opposites() -> None:
    deltas = pairwise_deltas(((0, 0), (5, 0), (3, -6)))
    assert len(deltas) == 6  # 3 plates -> 3*2 ordered pairs
    for delta in deltas:
        assert (-delta[0], -delta[1]) in deltas


def test_a_single_plate_course_has_no_deltas() -> None:
    assert pairwise_deltas(((0, 0),)) == []


def test_the_superseded_probe_finds_nothing_in_its_own_fixture(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`probe_baseplate_arrangement.py` filters BASE_LAYER; the fixture has none.

    This **runs the old script** rather than re-implementing its filter. An
    earlier version of this test rebuilt the filter inline and asserted on its
    own copy -- so repairing the real script left the suite green while the
    claim it was supposed to pin became false (observations #12: the two sides
    shared an origin). Verified by enacting that repair.

    If a later session does repair the script, this fails and points at the
    docstring in `probe_plate_arrangement.py` that must be updated with it.
    """
    from scripts import probe_baseplate_arrangement

    monkeypatch.chdir(FIXTURE.parent.parent.parent)
    probe_baseplate_arrangement.main()
    out = capsys.readouterr().out
    assert "Found 0 BASE_LAYER layer(s):" in out
    assert "No overlaps across 0 world-hex positions." in out, (
        "the quoted line in probe_plate_arrangement.py's docstring"
    )
    assert "BASE_LAYER_PIECE: 15 layers" in out, "while the real baseplate count is 15"


def test_scan_reads_a_corpus_directory_and_tallies_what_it_skipped(
    tmp_path: Path,
) -> None:
    """`scan` had no coverage at all, and it produced the committed constant."""
    shutil.copy(FIXTURE, tmp_path / "real.course")
    (tmp_path / "v7.course").write_bytes(_stamped_version(FIXTURE.read_bytes(), 7))
    (tmp_path / "v2.course").write_bytes(_stamped_version(FIXTURE.read_bytes(), 2))
    (tmp_path / "junk.course").write_bytes(b"\x00" * 64)

    arrangements, tally = scan(tmp_path)

    assert tally["parsed"] == 1
    assert tally["skipped(v7)"] == 1 and tally["skipped(v2)"] == 1
    assert sum(v for k, v in tally.items() if k.startswith("skipped(") and "v" not in k[9:11]) >= 0
    assert len(arrangements) == 1
    assert len(arrangements[0]) == 15
    assert tally["plates_total"] == 15
    assert tally["plates_empty"] == sum(
        1
        for layer in parse_course(FIXTURE.read_bytes()).layer_construction_data
        if layer.layer_kind is LayerKind.BASE_LAYER_PIECE
        and not layer.cell_construction_datas
    )
    assert any(k.startswith("height=") for k in tally), "layer_height must be tallied"


def test_scan_records_an_unparseable_file_rather_than_swallowing_it(
    tmp_path: Path,
) -> None:
    """A skip that vanishes silently would inflate every ratio the probe prints."""
    (tmp_path / "junk.course").write_bytes(b"\x00" * 64)
    arrangements, tally = scan(tmp_path)
    assert arrangements == []
    assert tally["parsed"] == 0
    assert sum(tally.values()) == 1, "the file is accounted for, not dropped"


def test_normalised_makes_translated_arrangements_compare_equal() -> None:
    """The check behind the constant's "the rest are this shape translated"."""
    square = tuple(PLATES_STANDARD_SQUARE)
    translated = tuple((y + 5, x - 6) for y, x in square)
    assert normalised(translated) == normalised(square)
    reshaped = (*square[:-1], (99, 99))
    assert normalised(reshaped) != normalised(square)
    assert normalised(()) == ()


def test_report_prints_the_constant_it_is_cited_as_generating(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`report` had no coverage, and its output is committed as fact.

    Two of its lines are the ones `traxgen/plates.py` cites: the zero-collision
    count and the emitted STANDARD_SQUARE. A mutation inverting the collision
    test, and one emitting the *least* common four-plate set, both survived the
    whole suite before this test existed.
    """
    square = tuple(HexVector(y=y, x=x) for y, x in PLATES_STANDARD_SQUARE)
    course = build_course(plate_world_positions=square, tiles=STARTER)
    for i in range(3):
        (tmp_path / f"c{i}.course").write_bytes(serialize_course(course))
    rare = build_course(
        plate_world_positions=tuple(
            HexVector(y=y + 100, x=x) for y, x in PLATES_STANDARD_SQUARE
        ),
        tiles=STARTER,
    )
    (tmp_path / "rare.course").write_bytes(serialize_course(rare))

    arrangements, tally = scan(tmp_path)
    report(arrangements, tally)
    out = capsys.readouterr().out

    assert "courses with any collision: 0 of 4" in out
    assert "-> multi-plate: 4 of 4" in out
    assert "of the 2 distinct sets, 2 are the modal shape translated" in out
    for position in PLATES_STANDARD_SQUARE:
        assert f"    {position}," in out, "the emitted constant must be the modal set"
    assert "(100, 0)" not in out.split("paste into")[-1], "not the rare set"



def _stamped_version(data: bytes, version: int) -> bytes:
    """The same bytes with a different declared save version at offset 16."""
    return data[:16] + version.to_bytes(4, "little") + data[20:]


def test_a_lattice_basis_generates_every_delta_it_was_derived_from() -> None:
    """The generating check is the whole point, so exercise both outcomes.

    `lattice_basis_from` must not return a basis that merely fits most of its
    input. Fed a set that is a real lattice it returns generators; fed the same
    set plus one delta off it, it raises. Without the second half the function
    could ignore its own loop and this test would still pass.
    """
    square = pairwise_deltas(tuple(PLATES_STANDARD_SQUARE))
    basis = lattice_basis_from(square)
    assert all(on_lattice(d, basis) for d in square)

    with pytest.raises(ValueError, match="do not form a lattice"):
        lattice_basis_from([*square, (basis[0][0], basis[0][1] + 1)])


def test_a_lattice_basis_refuses_rank_one_and_empty_input() -> None:
    """Two failure shapes that would otherwise return a degenerate basis.

    All-collinear deltas have no second generator, and `on_lattice` would raise
    a confusing "degenerate basis" from deep inside rather than the caller
    getting told the observations are rank 1.
    """
    with pytest.raises(ValueError, match="rank 1"):
        lattice_basis_from([(5, 0), (10, 0), (-5, 0)])
    with pytest.raises(ValueError, match="nothing to derive"):
        lattice_basis_from([(0, 0)])


def test_on_lattice_accepts_combinations_and_rejects_a_near_miss() -> None:
    """Integer coefficients, not approximate ones.

    The near-miss is the case that matters: a delta one cell off a real lattice
    point must come back False. If this ever used float division a rounding
    error would report agreement, which is the direction that invents a finding
    rather than losing one (observations #17).
    """
    basis = lattice_basis_from(pairwise_deltas(tuple(PLATES_STANDARD_SQUARE)))
    u, v = basis
    assert on_lattice((0, 0), basis)
    assert on_lattice(u, basis) and on_lattice(v, basis)
    assert on_lattice((u[0] + v[0], u[1] + v[1]), basis)
    assert on_lattice((-2 * u[0] + 3 * v[0], -2 * u[1] + 3 * v[1]), basis)
    assert not on_lattice((u[0], u[1] + 1), basis), "a one-cell miss is not on it"


def test_the_completing_delta_lies_on_the_arrangement_lattice() -> None:
    """Two independent derivations from the same corpus, made to agree.

    `STANDARD_SQUARE` came from counting which arrangements people build; the
    completing delta came from tiling the measured cell footprint. Nothing makes
    them agree a priori -- if the plate that completes a half-hole sat off the
    lattice of real arrangements, one of the two derivations is wrong and this
    is where it shows.
    """
    from scripts.probe_plate_seams import find_tiling_delta

    basis = lattice_basis_from(pairwise_deltas(tuple(PLATES_STANDARD_SQUARE)))
    footprint = frozenset(MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE])
    assert on_lattice(find_tiling_delta(footprint), basis)
