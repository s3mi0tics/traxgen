# Path: traxgen/tests/test_layout.py
"""Tests for explicit-layout course building (traxgen/layout.py).

The load-bearing test here is `test_single_plate_layout_is_byte_identical_to_
generate_minimal`. It pins the new write path to `generate_minimal()`'s current
output, and only that. FLW4TMLP5V's own bytes are **not** in this repo and no
test compares anything to them -- the certified link runs through a one-time
2026-08-07 diff recorded in `decisions.md`, which nothing re-checks. The same
honest wording already lives in `scripts/sweep_starter_rotation.py`'s
`_assert_control_matches_generator`; this docstring previously inverted it.

What the test does establish is real and was verified by mutation: the two
builders do not share a code path (`generate_minimal()` constructs its layer
inline, `build_course()` builds from a placement list), so a transcription
error in either shows up as a byte difference rather than cancelling out
(observations #12).
"""

from __future__ import annotations

import pytest

from traxgen.generator import generate_minimal
from traxgen.hex import HexVector
from traxgen.layout import (
    CERTIFIED_LAYER_HEIGHT,
    FIRST_LAYER_ID,
    TilePlacement,
    build_course,
    owning_plate,
    world_position,
)
from traxgen.plates import MEASURED_FOOTPRINTS
from traxgen.plates import STANDARD_SQUARE as PLATES_STANDARD_SQUARE
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind, TileKind

MINIMAL_TILES = (
    TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
    TilePlacement(TileKind.GOAL_RAIL, 0, HexVector(y=-1, x=0), 3),
)

# Derived from the generated constant rather than re-typed: a second typed copy
# of a measured set is the same untested claim one file over.
STANDARD_SQUARE = tuple(HexVector(y=y, x=x) for y, x in PLATES_STANDARD_SQUARE)


def _se_owner() -> tuple[int, HexVector]:
    """The plate that owns the SE world cell, and its local address there.

    Looked up rather than typed. A hardcoded `plate_index` here is the exact
    bug `owning_plate` was added to prevent, and reordering STANDARD_SQUARE --
    same set, different order -- moved this goal to a different world cell with
    the whole suite green.
    """
    owner = owning_plate(STANDARD_SQUARE, HexVector(y=1, x=0))
    assert owner is not None, "the standard square must put a plate under SE"
    return owner


def test_single_plate_layout_is_byte_identical_to_generate_minimal() -> None:
    """One plate, two tiles, the certified geometry -- same bytes as the oracle."""
    built = build_course(
        plate_world_positions=(HexVector(y=0, x=0),), tiles=MINIMAL_TILES
    )
    assert serialize_course(built) == serialize_course(generate_minimal())


def test_extra_plates_do_not_disturb_the_first_plate() -> None:
    """Adding plates leaves plate 0's id, height, position and cells unchanged."""
    one = build_course(plate_world_positions=(HexVector(y=0, x=0),), tiles=MINIMAL_TILES)
    four = build_course(plate_world_positions=STANDARD_SQUARE, tiles=MINIMAL_TILES)
    assert four.layer_construction_data[0] == one.layer_construction_data[0]


def test_plate_count_and_ids_follow_the_layout() -> None:
    """Every plate is emitted, in order, with unique consecutive layer ids."""
    course = build_course(plate_world_positions=STANDARD_SQUARE, tiles=MINIMAL_TILES)
    layers = course.layer_construction_data
    assert len(layers) == len(STANDARD_SQUARE)
    assert [layer.world_hex_position for layer in layers] == list(STANDARD_SQUARE)
    ids = [layer.layer_id for layer in layers]
    assert ids == [FIRST_LAYER_ID + i for i in range(len(STANDARD_SQUARE))]
    assert len(set(ids)) == len(ids), "LAYER_ID_COLLISION requires uniqueness"
    assert all(layer.layer_kind is LayerKind.BASE_LAYER_PIECE for layer in layers)
    assert all(layer.layer_height == CERTIFIED_LAYER_HEIGHT for layer in layers)


def test_a_plate_with_no_tiles_is_emitted_empty() -> None:
    """563 of 4,599 corpus plates carry zero cells, so empty is ordinary."""
    course = build_course(plate_world_positions=STANDARD_SQUARE, tiles=MINIMAL_TILES)
    assert len(course.layer_construction_data[0].cell_construction_datas) == 2
    for layer in course.layer_construction_data[1:]:
        assert layer.cell_construction_datas == ()


def test_a_tile_can_be_placed_on_a_later_plate() -> None:
    """The goal goes on plate 2, addressed in *that* plate's local frame."""
    course = build_course(
        plate_world_positions=STANDARD_SQUARE,
        tiles=(
            TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
            TilePlacement(TileKind.GOAL_RAIL, *_se_owner(), 4),
        ),
    )
    first_cell = course.layer_construction_data[0].cell_construction_datas[0]
    assert first_cell.tree_node_data.construction_data.kind is TileKind.STARTER
    assert course.layer_construction_data[1].cell_construction_datas == ()
    plate_index, local = _se_owner()
    assert plate_index == 2, "SE's owner is plate 2 in the current ordering"
    goal_cells = course.layer_construction_data[plate_index].cell_construction_datas
    assert len(goal_cells) == 1
    assert goal_cells[0].local_hex_position == local
    assert goal_cells[0].tree_node_data.construction_data.hex_rotation == 4


def test_the_two_addressings_of_the_w_cell_resolve_to_one_world_cell() -> None:
    """The probe's discriminator: same world cell, in-window and out-of-window.

    Arm 1 addresses world (0,-1) as an *in-window* local on the plate that owns
    it; arm 2 addresses the identical world cell as an *out-of-window* local on
    the home plate. If these ever stopped naming the same cell the experiment
    would be measuring two different geometries, so it is pinned here.
    """
    w_cell = HexVector(y=0, x=-1)
    owner = owning_plate(STANDARD_SQUARE, w_cell)
    assert owner is not None, "the standard square must put a plate under W"
    plate_index, local = owner
    arm1 = TilePlacement(TileKind.GOAL_RAIL, plate_index, local, 4)
    arm2 = TilePlacement(TileKind.GOAL_RAIL, 0, w_cell, 4)
    assert world_position(STANDARD_SQUARE, arm1) == w_cell
    assert world_position(STANDARD_SQUARE, arm2) == w_cell
    assert plate_index != 0, "arm 1 must land on a plate other than the starter's"


def test_the_two_addressings_differ_exactly_in_window_membership() -> None:
    """Arm 1's local is on the footprint; arm 2's is not. That is the variable."""
    footprint = MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]
    owner = owning_plate(STANDARD_SQUARE, HexVector(y=0, x=-1))
    assert owner is not None
    _, local = owner
    assert (local.y, local.x) in footprint, "arm 1 must be an in-window address"
    assert (0, -1) not in footprint, "arm 2 must be the out-of-window address"


def test_an_out_of_window_local_is_allowed() -> None:
    """Refusing it would encode the hypothesis under test -- see the module docstring."""
    course = build_course(
        plate_world_positions=STANDARD_SQUARE,
        tiles=(
            TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
            TilePlacement(TileKind.GOAL_RAIL, 0, HexVector(y=0, x=-1), 4),
        ),
    )
    cells = course.layer_construction_data[0].cell_construction_datas
    assert HexVector(y=0, x=-1) in [cell.local_hex_position for cell in cells]


def test_duplicate_plate_positions_are_refused() -> None:
    with pytest.raises(ValueError, match="duplicate plate world position"):
        build_course(
            plate_world_positions=(HexVector(y=0, x=0), HexVector(y=0, x=0)),
            tiles=MINIMAL_TILES,
        )


def test_out_of_range_plate_index_is_refused() -> None:
    with pytest.raises(ValueError, match="plate_index 1 out of range"):
        build_course(
            plate_world_positions=(HexVector(y=0, x=0),),
            tiles=(TilePlacement(TileKind.STARTER, 1, HexVector(y=0, x=0), 0),),
        )


def test_two_tiles_in_one_cell_are_refused() -> None:
    with pytest.raises(ValueError, match="two tiles addressed to plate 0 cell"):
        build_course(
            plate_world_positions=(HexVector(y=0, x=0),),
            tiles=(
                TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
                TilePlacement(TileKind.GOAL_RAIL, 0, HexVector(y=0, x=0), 3),
            ),
        )


def test_an_empty_layout_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one plate"):
        build_course(plate_world_positions=(), tiles=())


def test_the_standard_square_tiles_without_overlap() -> None:
    """What the corpus shows for every real course, asserted for our replica."""
    footprint = MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]
    cells = [
        (plate.y + fy, plate.x + fx)
        for plate in STANDARD_SQUARE
        for fy, fx in footprint
    ]
    assert len(set(cells)) == len(cells) == len(STANDARD_SQUARE) * len(footprint)


def test_a_multi_plate_course_round_trips_through_the_parser() -> None:
    """Serialize -> parse -> serialize is byte-stable, and the plates survive.

    Asserted on **bytes**, not on domain equality, per the locked correctness
    contract (`decisions.md`: "Byte round-trip, NOT Python-float equality").
    Object equality would pass here only because `layer_height` happens to be
    0.0; at the corpus's own -0.2 the f32 round-trip reads back as
    -0.2000000029... and an object-equality assertion would fail for a reason
    that has nothing to do with plates. Verified by mutation.
    """
    from traxgen.parser import parse_course

    course = build_course(
        plate_world_positions=STANDARD_SQUARE,
        tiles=(
            TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
            TilePlacement(TileKind.GOAL_RAIL, 2, HexVector(y=-4, x=0), 4),
        ),
    )
    raw = serialize_course(course)
    reparsed = parse_course(raw)
    assert serialize_course(reparsed) == raw
    assert [layer.world_hex_position for layer in reparsed.layer_construction_data] == list(
        STANDARD_SQUARE
    )
    assert [layer.layer_id for layer in reparsed.layer_construction_data] == [
        FIRST_LAYER_ID + i for i in range(len(STANDARD_SQUARE))
    ]


def test_a_multi_plate_course_is_never_claimed_disconnected() -> None:
    """The probe's own discriminating arm must not trip START_GOAL_CONNECTED.

    Four plates, starter on the home plate at local (0,0), goal at the
    out-of-window W cell. Before the multi-plate guard in `start_goal_status`
    this classified DISCONNECTED and the validator raised ERROR -- asserting
    one reading of open unknown #17 as a harness finding, on the very course
    built to decide it. Every row in `MEASURED_RUNS` was rendered through a
    single-layer builder, so "one plate" is an unrecorded precondition on all
    of them, and `classify_pair` sends only *cross-layer* pairs to UNMEASURED.
    """
    from traxgen.graph import ConnectionStatus, start_goal_status

    arm = build_course(
        plate_world_positions=STANDARD_SQUARE,
        tiles=(
            TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
            TilePlacement(TileKind.GOAL_RAIL, 0, HexVector(y=0, x=-1), 4),
        ),
    )
    assert start_goal_status(arm) is ConnectionStatus.UNMEASURED


def test_the_single_plate_course_still_answers_from_the_record() -> None:
    """The guard must not blanket-UNMEASURE the measured single-plate space."""
    from traxgen.graph import ConnectionStatus, start_goal_status

    certified = build_course(
        plate_world_positions=(HexVector(y=0, x=0),), tiles=MINIMAL_TILES
    )
    assert start_goal_status(certified) is ConnectionStatus.CONNECTED


# --- Gaps a mutation panel found: parameters and branches nothing exercised. ---


def test_layer_height_is_honoured_and_minus_point_two_survives_as_bytes() -> None:
    """The corpus's own height, which nothing else in the suite ever builds.

    4,598 of 4,599 real BASE_LAYER_PIECE layers carry -0.2 (regenerate with
    `scripts/probe_plate_arrangement.py`); the library defaults to 0.0 so a
    multi-plate course differs from the certified one in plate count alone.
    That makes -0.2 the untested path, and it is exactly where the f32 contract
    bites: object equality fails after a round-trip while bytes stay stable.
    """
    from traxgen.parser import parse_course

    course = build_course(
        plate_world_positions=STANDARD_SQUARE,
        tiles=MINIMAL_TILES,
        layer_height=-0.2,
    )
    assert all(
        layer.layer_height == -0.2 for layer in course.layer_construction_data
    ), "the parameter must reach every layer, not just plate 0"
    raw = serialize_course(course)
    reparsed = parse_course(raw)
    assert serialize_course(reparsed) == raw, "bytes are the promise"
    assert reparsed != course, "floats are not: -0.2 reads back as -0.2000000029..."


def test_title_and_first_layer_id_are_honoured() -> None:
    """Both parameters were ignorable with the whole suite green."""
    course = build_course(
        plate_world_positions=STANDARD_SQUARE,
        tiles=MINIMAL_TILES,
        title="probe-arm-2",
        first_layer_id=500,
    )
    assert course.meta_data.title == "probe-arm-2"
    assert [layer.layer_id for layer in course.layer_construction_data] == [
        500,
        501,
        502,
        503,
    ]


def test_the_same_local_address_on_two_plates_is_allowed() -> None:
    """Legal, and the module exists to build it -- the cell key must be per-plate."""
    course = build_course(
        plate_world_positions=STANDARD_SQUARE,
        tiles=(
            TilePlacement(TileKind.STARTER, 0, HexVector(y=0, x=0), 0),
            TilePlacement(TileKind.GOAL_RAIL, 2, HexVector(y=0, x=0), 3),
        ),
    )
    assert [
        len(layer.cell_construction_datas) for layer in course.layer_construction_data
    ] == [1, 0, 1, 0]


def test_two_tiles_on_one_world_cell_through_different_plates_are_refused() -> None:
    """The collision an experiment addressing one cell two ways will actually make."""
    w_cell = HexVector(y=0, x=-1)
    plate_index, local = owning_plate(STANDARD_SQUARE, w_cell)  # type: ignore[misc]
    with pytest.raises(ValueError, match="two tiles occupy world cell"):
        build_course(
            plate_world_positions=STANDARD_SQUARE,
            tiles=(
                TilePlacement(TileKind.GOAL_RAIL, 0, w_cell, 4),
                TilePlacement(TileKind.STARTER, plate_index, local, 0),
            ),
        )


def test_a_negative_plate_index_is_refused() -> None:
    """Without the lower bound the tile is silently dropped, not refused."""
    with pytest.raises(ValueError, match="plate_index -1 out of range"):
        build_course(
            plate_world_positions=STANDARD_SQUARE,
            tiles=(TilePlacement(TileKind.STARTER, -1, HexVector(y=0, x=0), 0),),
        )


def test_plates_differing_only_in_x_are_not_duplicates() -> None:
    """The duplicate key must be both coordinates.

    STANDARD_SQUARE's y values are all distinct, so a key of `(y,)` alone
    passes every other test in this module -- fixture luck, not coverage.
    """
    course = build_course(
        plate_world_positions=(HexVector(y=0, x=0), HexVector(y=0, x=6)),
        tiles=(TilePlacement(TileKind.STARTER, 1, HexVector(y=0, x=0), 0),),
    )
    assert len(course.layer_construction_data) == 2


def test_owning_plate_returns_none_for_a_cell_no_plate_covers() -> None:
    """The documented None branch, which no other test reaches."""
    assert owning_plate(STANDARD_SQUARE, HexVector(y=-99, x=-99)) is None


def test_owning_plate_refuses_an_ambiguous_overlapping_layout() -> None:
    """`build_course` refuses duplicate positions, not overlapping ones.

    Plates one cell apart share 23 world cells and are accepted, so "which
    plate owns this" is a question without an answer there -- and answering it
    silently is what a first-match lookup would do.
    """
    overlapping = (HexVector(y=0, x=0), HexVector(y=0, x=1))
    with pytest.raises(ValueError, match="is covered by 2 plates"):
        owning_plate(overlapping, HexVector(y=0, x=1))


def test_the_standard_square_is_one_contiguous_region() -> None:
    """A structural property of the arrangement, and an honest note on its limits.

    This catches a plate flung somewhere disconnected. It does **not** pin the
    coordinates: measured, `(8,-6) -> (9,-6)` and `(5,0) -> (5,1)` both stay
    contiguous *and* collision-free at 120 cells, so no offline test in this
    suite can tell a corrupted STANDARD_SQUARE from the real one. Only
    re-running `scripts/probe_plate_arrangement.py` against the corpus can, and
    that is the point of generating the constant rather than typing it. Claiming
    more here would be inventing an oracle the suite does not have.
    """
    footprint = MEASURED_FOOTPRINTS[LayerKind.BASE_LAYER_PIECE]
    cells = {
        (plate.y + fy, plate.x + fx)
        for plate in STANDARD_SQUARE
        for fy, fx in footprint
    }
    start = next(iter(cells))
    seen, stack = {start}, [start]
    while stack:
        y, x = stack.pop()
        for dy, dx in ((0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1), (1, 0)):
            neighbour = (y + dy, x + dx)
            if neighbour in cells and neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    assert seen == cells, "the four plates must form one connected region"


def test_the_standard_square_covers_every_direction_dead_at_the_corner() -> None:
    """W, SW and SE -- dark in all six exhaustive corner sweeps -- get plate.

    This is the arrangement's whole reason for being chosen, so it is asserted
    rather than left to the prose. Each is owned by a plate other than the
    starter's, which is what makes the two-addressing experiment possible.
    """
    for name, direction in (("W", 3), ("SW", 4), ("SE", 5)):
        cell = HexVector(y=0, x=0).neighbor(direction)
        owner = owning_plate(STANDARD_SQUARE, cell)
        assert owner is not None, f"{name} must have plate under it"
        plate_index, local = owner
        assert plate_index != 0, f"{name}'s plate must not be the starter's"
        assert (local.y, local.x) in MEASURED_FOOTPRINTS[
            LayerKind.BASE_LAYER_PIECE
        ], f"{name} must be an in-window address on its owning plate"
