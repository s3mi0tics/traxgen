"""The corpus miner's piece-relative side, in `track_graph`'s frame (s52-t9).

Path: traxgen/tests/test_mine_ports.py
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from scripts.mine_ports import mine, piece_side
from traxgen.track_graph import CROSS_TRACKS, STARTER_INTRINSIC_PORTS

FIXTURE = Path(__file__).parent / "fixtures" / "GDZJZA3J3T.course"


def test_a_rail_on_a_cross_lands_on_one_of_its_tracks() -> None:
    # The fixture's three single-tile CROSS rail ends. D099 measured sides 0 and 3
    # closed on the emulator; the pre-s52 formula put two of these on 0 and one on 3.
    port_obs: dict = defaultdict(list)
    records: list = []
    assert mine(FIXTURE, port_obs, records, verbose=False) == "mined"
    sides = [
        piece_side(r["side_hex_rot"], r["tile_hex_rotation"])
        for r in records
        if r["tile_kind"] == "CROSS" and r["tower_size"] == 1
    ]
    assert len(sides) == 3
    assert set(sides) <= set(CROSS_TRACKS)


def test_piece_side_inverts_track_graphs_world_side() -> None:
    # track_graph: world side = (piece side + hex_rotation) % 6; the format's edge
    # index is the mirror of the world side, s = (2 - world) % 6.
    for rotation in range(6):
        for side in range(6):
            world = (side + rotation) % 6
            assert piece_side((2 - world) % 6, rotation) == side


def test_the_starter_ports_are_the_same_set_in_either_frame() -> None:
    # Why s20's STARTER calibration passed with the mirrored frame: {0, 2, 4} maps onto itself.
    mirrored = {(2 - p) % 6 for p in STARTER_INTRINSIC_PORTS}
    assert mirrored == set(STARTER_INTRINSIC_PORTS)
