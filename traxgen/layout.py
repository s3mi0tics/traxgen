# Path: traxgen/traxgen/layout.py
"""Build a course from an explicit baseplate layout (open unknowns #16, #17).

`generator.py` emits one certified course on one plate. This module is the
other half: a course whose plates are *named by the caller*, so an experiment
can put real baseplate under a cell that has only ever been measured dark.

Why it exists as its own module. 599 of the 640 parsed corpus courses carry two
or more `BASE_LAYER_PIECE` layers, so single-plate is the exception in the wild
and `graph.py` honestly answers `UNMEASURED` for nearly all of it. Deciding how
membership composes across plates takes a render, and the render takes a course
the library cannot currently build -- `generate_minimal()` hardcodes one layer
and `scripts/sweep_starter_rotation.build_variant` reads
`layer_construction_data[0]` and returns a 1-tuple. The serializer already
writes `len(...)` and loops, the parser already reads N, and `validator.py`
iterates layers throughout (its `LAYER_ID_COLLISION` rule only means anything
for multi-layer courses), so the write path was the only gap.

**Local positions are not validated against the plate footprint, deliberately.**
`build_course` never checks one, though `plates.is_on_plate` exists and
`owning_plate` below uses it to resolve which plate covers a cell. The 2026-08-21
runs measured cells dark while addressing them as out-of-window locals on the
only plate present, which leaves two readings open (`plan.md` #17): the cell had
no plate under it, or the *address* was malformed and plate membership was never
what mattered. Separating them requires building exactly the course a footprint
check would refuse -- an out-of-window local over a cell that now has plate
beneath it. Refusing to build it here would make the experiment unrunnable and
would encode the very hypothesis under test.

Path: traxgen/traxgen/layout.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from traxgen.domain import (
    CellConstructionData,
    Course,
    CourseMetaData,
    LayerConstructionData,
    SaveDataHeader,
    TileTowerConstructionData,
    TileTowerTreeNodeData,
)
from traxgen.plates import is_on_plate
from traxgen.types import (
    CourseElementGeneration,
    CourseKind,
    CourseSaveDataVersion,
    LayerKind,
    ObjectiveKind,
    TileKind,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from traxgen.hex import HexVector

# The first plate's retainer id, matching `generator._LAYER_ID` so a
# single-plate layout serializes byte-identically to `generate_minimal()`.
# Further plates take consecutive ids; any non-colliding value works
# (`LAYER_ID_COLLISION` requires only uniqueness), and the corpus's own
# standard square uses 129-132 rather than a run starting at 100.
FIRST_LAYER_ID = 100

# `generate_minimal()`'s value, and the one certified by the app as
# FLW4TMLP5V. Note this is *not* what the corpus does: 4,598 of 4,599
# BASE_LAYER_PIECE layers across 640 courses carry -0.2 and exactly one
# carries 0.0. Kept as the default so a layout differs from the certified
# course in plate count alone -- one variable, not two. See `plan.md`.
CERTIFIED_LAYER_HEIGHT = 0.0


@dataclass(frozen=True, slots=True)
class TilePlacement:
    """One tile, addressed by which plate holds it and where on that plate."""

    kind: TileKind
    plate_index: int
    local_pos: HexVector
    hex_rotation: int = 0


def build_course(
    *,
    plate_world_positions: Sequence[HexVector],
    tiles: Sequence[TilePlacement],
    title: str = "traxgen-minimal",
    layer_height: float = CERTIFIED_LAYER_HEIGHT,
    first_layer_id: int = FIRST_LAYER_ID,
) -> Course:
    """Build a course whose `BASE_LAYER_PIECE` plates sit at the given world positions.

    Plates are emitted in the order given; `TilePlacement.plate_index` indexes
    that order. A plate holding no tiles is emitted empty, which the corpus
    shows is ordinary rather than degenerate (563 of 4,599 observed plates
    carry zero cells).

    Raises `ValueError` on a duplicate plate position, an out-of-range
    `plate_index`, two tiles addressed to one plate-local cell, or two tiles
    landing on one *world* cell through different plates -- each of which would
    produce a course whose render says nothing about the geometry intended.
    The world-cell check is not redundant with the local one: this module's
    whole purpose is addressing a single world cell two ways, so colliding
    there is the mistake an experiment using it will actually make.
    Local positions off the plate footprint are *allowed*; see the module
    docstring for why that refusal would defeat the experiment.
    """
    if not plate_world_positions:
        raise ValueError("a course needs at least one plate")

    seen_positions: set[tuple[int, int]] = set()
    for pos in plate_world_positions:
        key = (pos.y, pos.x)
        if key in seen_positions:
            raise ValueError(
                f"duplicate plate world position {key}; two plates at one "
                "position would overlap, which no corpus course does"
            )
        seen_positions.add(key)

    cells_by_plate: dict[int, list[CellConstructionData]] = {}
    occupied: set[tuple[int, int, int]] = set()
    world_occupied: set[tuple[int, int]] = set()
    for tile in tiles:
        if not 0 <= tile.plate_index < len(plate_world_positions):
            raise ValueError(
                f"plate_index {tile.plate_index} out of range for "
                f"{len(plate_world_positions)} plate(s)"
            )
        cell_key = (tile.plate_index, tile.local_pos.y, tile.local_pos.x)
        if cell_key in occupied:
            raise ValueError(
                f"two tiles addressed to plate {tile.plate_index} cell "
                f"({tile.local_pos.y}, {tile.local_pos.x})"
            )
        occupied.add(cell_key)
        world = plate_world_positions[tile.plate_index] + tile.local_pos
        world_key = (world.y, world.x)
        if world_key in world_occupied:
            raise ValueError(
                f"two tiles occupy world cell {world_key}, reached through "
                f"different plates; one is addressed as plate "
                f"{tile.plate_index} local ({tile.local_pos.y}, "
                f"{tile.local_pos.x})"
            )
        world_occupied.add(world_key)
        cells_by_plate.setdefault(tile.plate_index, []).append(
            CellConstructionData(
                local_hex_position=tile.local_pos,
                tree_node_data=TileTowerTreeNodeData(
                    index=0,
                    construction_data=TileTowerConstructionData(
                        kind=tile.kind,
                        height_in_small_stacker=0,
                        hex_rotation=tile.hex_rotation,
                    ),
                    children=(),
                ),
            )
        )

    layers = tuple(
        LayerConstructionData(
            layer_id=first_layer_id + index,
            layer_kind=LayerKind.BASE_LAYER_PIECE,
            layer_height=layer_height,
            world_hex_position=world_pos,
            cell_construction_datas=tuple(cells_by_plate.get(index, ())),
        )
        for index, world_pos in enumerate(plate_world_positions)
    )

    return Course(
        header=SaveDataHeader(guid=0, version=CourseSaveDataVersion.POWER_2022),
        meta_data=CourseMetaData(
            creation_timestamp=0,
            title=title,
            order_number=-1,
            course_kind=CourseKind.CUSTOM,
            objective_kind=ObjectiveKind.NONE,
            difficulty=0,
            completed=False,
        ),
        layer_construction_data=layers,
        rail_construction_data=(),
        pillar_construction_data=(),
        generation=CourseElementGeneration.POWER,
        wall_construction_data=(),
    )


def owning_plate(
    plate_world_positions: Sequence[HexVector], world_cell: HexVector
) -> tuple[int, HexVector] | None:
    """Which plate's footprint covers `world_cell`, and its local address there.

    Returns `(plate_index, local_pos)`, or `None` when no plate covers the cell.
    Raises `ValueError` when two do.

    Real courses never present that case -- applying the measured footprint at
    every `world_hex_position` across all 640 parsed corpus courses produces
    zero collisions. But `build_course` refuses only *duplicate* plate
    positions, not *overlapping* ones (plates one cell apart share 23 world
    cells and are accepted), and this module exists precisely to build
    arrangements the corpus has never contained. Returning the first match
    would answer a genuinely ambiguous question silently.

    This exists so an experiment never has to *assume* which plate owns a cell.
    Indexing a layout by hand is how a hardcoded `plate_index` silently comes to
    name a different plate when the layout's order changes -- caught by test,
    not by render, while wiring up this very module.
    """
    owners = [
        (index, world_cell - plate_pos)
        for index, plate_pos in enumerate(plate_world_positions)
        if is_on_plate(LayerKind.BASE_LAYER_PIECE, world_cell - plate_pos)
    ]
    if len(owners) > 1:
        raise ValueError(
            f"world cell ({world_cell.y}, {world_cell.x}) is covered by "
            f"{len(owners)} plates {[i for i, _ in owners]}; the layout "
            "overlaps, so which plate owns it is not a question with an answer"
        )
    return owners[0] if owners else None


def world_position(
    plate_world_positions: Sequence[HexVector], placement: TilePlacement
) -> HexVector:
    """The world cell `placement` occupies, by the `world + local` addition.

    That addition is what the corpus shows plates actually obey: applying the
    measured 30-cell footprint at every plate's `world_hex_position` across all
    640 parsed courses yields **zero** collisions, so world coordinates are a
    coherent global frame rather than a per-plate convenience.
    """
    return plate_world_positions[placement.plate_index] + placement.local_pos
