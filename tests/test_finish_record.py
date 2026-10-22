"""The finish-record builder rebuilds exactly the cells the record calls live (s43-t2).

Path: traxgen/tests/test_finish_record.py
"""

from __future__ import annotations

import hashlib

from scripts.finish_record import build_cell_course, checked_bytes, live_cells
from traxgen.android import FINISH_BURST_MIN_PIXELS
from traxgen.generator import generate_minimal
from traxgen.graph import MEASURED_FINISHES, MEASURED_RUNS, ConnectionStatus, start_goal_status
from traxgen.plates import half_hole_cells
from traxgen.types import LayerKind, TileKind


def test_there_is_one_cell_per_live_direction_of_every_row() -> None:
    cells = live_cells()
    assert len(cells) == sum(len(r.live_directions) for r in MEASURED_RUNS) == 20
    assert len({c.label for c in cells}) == len(cells)


def test_every_rebuilt_cell_is_connected_in_the_record() -> None:
    for cell in live_cells():
        assert start_goal_status(build_cell_course(cell)) is ConnectionStatus.CONNECTED, cell.label
        checked_bytes(cell)  # raises if not


def test_the_phase_1_cell_rebuilds_the_phase_1_geometry() -> None:
    """r00-d2: STARTER (0,0) rot 0, GOAL_RAIL to the NW at rot 3 -- generate_minimal's course."""
    [cell] = [c for c in live_cells() if c.label == "r00-d2"]
    built = build_cell_course(cell).layer_construction_data
    minimal = generate_minimal().layer_construction_data
    assert [(lay.world_hex_position, lay.cell_construction_datas) for lay in built] == [
        (lay.world_hex_position, lay.cell_construction_datas) for lay in minimal
    ]


def test_a_dead_direction_is_refused() -> None:
    """The check is not vacuous: a direction the row does not call live does not pass."""
    from dataclasses import replace

    from scripts.finish_record import Cell

    cell = live_cells()[0]
    dead = next(d for d in range(6) if d not in cell.run.live_directions)
    status = start_goal_status(build_cell_course(replace(cell, direction=dead)))
    assert status is not ConnectionStatus.CONNECTED
    assert isinstance(cell, Cell)


# --- MEASURED_FINISHES: the record of which placements finish -----------------


def _goal_local(course):
    for index, layer in enumerate(course.layer_construction_data):
        for cell in layer.cell_construction_datas:
            if cell.tree_node_data.construction_data.kind is TileKind.GOAL_RAIL:
                return index, (cell.local_hex_position.y, cell.local_hex_position.x)
    raise AssertionError("no goal")


def test_every_finish_entry_rebuilds_to_its_recorded_bytes() -> None:
    cells = {(c.run, c.direction): c for c in live_cells()}
    for entry in MEASURED_FINISHES:
        assert entry.direction in entry.run.live_directions
        cell = cells[(entry.run, entry.direction)]
        assert hashlib.sha256(checked_bytes(cell)).hexdigest() == entry.course_sha256, cell.label


def test_each_live_cell_has_at_most_one_finish_entry_and_all_20_are_judged() -> None:
    keys = [(id(e.run), e.direction) for e in MEASURED_FINISHES]
    assert len(keys) == len(set(keys)) == len(live_cells())


def test_the_finish_peaks_agree_with_the_threshold() -> None:
    for entry in MEASURED_FINISHES:
        assert entry.finished == (entry.peak_new_white >= FINISH_BURST_MIN_PIXELS)


def test_the_misses_are_exactly_the_goals_on_an_uncompleted_half_hole() -> None:
    """The claim the record's comment makes, checked against the entries."""
    halves = half_hole_cells(LayerKind.BASE_LAYER_PIECE)
    cells = {(c.run, c.direction): c for c in live_cells()}
    for entry in MEASURED_FINISHES:
        plate, local = _goal_local(build_cell_course(cells[(entry.run, entry.direction)]))
        on_half_hole = plate == 0 and len(entry.run.plate_offsets) == 1 and local in halves
        assert entry.finished is not on_half_hole, (entry.share_code, local)
