"""Tests for the starter-rotation sweep's offline logic.

The sweep needs a live upload endpoint and a booted emulator; none of that is
tested here. What IS tested is everything that decides what the sweep
*concluded* -- the enumeration, the variant builder, the resume key, and every
branch of `classify()`. A sweep whose classifier is wrong produces a confident,
well-formatted, false answer, which is the failure shape observation #12 names.

Four tests carry more weight than the rest:

  * `test_control_variant_is_byte_identical_to_generator` -- the precondition.
    If `build_variant` diverges from `generate_minimal()`, the sweep measures a
    course the app never certified while looking perfectly healthy.
  * `test_each_starter_rotation_produces_distinct_bytes` -- if the starter's
    `hex_rotation` never reaches the wire, all six sweep cells are the same
    course, the endpoint dedups them to one share code, and six identical
    `active` verdicts would read as "starter rotation is irrelevant". That is
    the finding this sweep is most likely to fake.
  * `test_probe_is_the_cell_the_rotating_exit_set_predicts` -- encodes *why*
    the probe sits at (NE, rot 2) rather than anywhere else, and pins the
    reading of the 2026-08-07 data that motivates the whole sweep.
  * `test_resume_key_separates_cells_that_differ_only_in_starter_rotation` --
    the goal sweep keyed cells on (y, x, rot); this sweep varies a fourth
    field, and a stale three-field key would silently copy one cell's verdict
    onto five others.

Path: traxgen/tests/test_sweep_starter_rotation.py
"""

from __future__ import annotations

import json

import pytest

from scripts.sweep_starter_rotation import (
    BACKFILL_GOAL_ROT,
    CONTROL_GOAL_POS,
    CONTROL_GOAL_ROT,
    DIR_E,
    DIR_NE,
    DIR_NW,
    HELD_GOAL_POS,
    HELD_GOAL_ROT,
    INFORMATIVE_VERDICTS,
    PROBE_GOAL_POS,
    PROBE_GOAL_ROT,
    PROBE_STARTER_ROT,
    STARTER_ROTATIONS,
    StarterCell,
    _assert_control_matches_generator,
    _load_resume,
    _render_order,
    build_variant,
    _write_sidecar,
    build_cells,
    classify,
    direction_position,
)
from traxgen.generator import generate_minimal
from traxgen.hex import ORIGIN, HexVector
from traxgen.serializer import serialize_course
from traxgen.types import TileKind

# The rule derived on 2026-08-07 from the two observed connections.
DERIVED_RULE = lambda d: (d + 1) % 6  # noqa: E731


def _rendered(
    *,
    control: str = "active",
    sweep: dict[int, str] | None = None,
    probe: str = "inactive",
    backfill: str = "inactive",
) -> list[StarterCell]:
    """A fully-rendered cell list with the given verdicts, for classify() tests."""
    if sweep is None:
        sweep = {s: "active" for s in STARTER_ROTATIONS}
    cells = build_cells()
    for cell in cells:
        match cell.kind:
            case "control":
                cell.validity = control
            case "sweep":
                cell.validity = sweep[cell.starter_rot]
            case "probe":
                cell.validity = probe
            case "backfill":
                cell.validity = backfill
    return cells


# --- Enumeration -----------------------------------------------------------


def test_build_cells_is_the_control_six_sweep_cells_a_probe_and_the_backfill() -> None:
    """Nine renders total, one of each supporting role."""
    cells = build_cells()
    kinds = [c.kind for c in cells]
    assert kinds.count("control") == 1
    assert kinds.count("sweep") == 6
    assert kinds.count("probe") == 1
    assert kinds.count("backfill") == 1
    assert len(cells) == 9


def test_every_goal_position_is_adjacent_to_the_starter() -> None:
    """Adjacency is the established connection mechanism; nothing here tests distance."""
    for cell in build_cells():
        assert ORIGIN.distance_to(HexVector(y=cell.y, x=cell.x)) == 1


def test_sweep_holds_one_goal_cell_and_varies_only_the_starter() -> None:
    """The sweep's whole design: one held target, six starter rotations."""
    sweep = [c for c in build_cells() if c.kind == "sweep"]
    assert {c.starter_rot for c in sweep} == set(STARTER_ROTATIONS)
    assert {(c.y, c.x, c.goal_rot) for c in sweep} == {
        (HELD_GOAL_POS.y, HELD_GOAL_POS.x, HELD_GOAL_ROT)
    }


def test_the_held_goal_is_a_known_active_cell_not_a_predicted_one() -> None:
    """E rot 1 was measured active on 2026-08-07; that is why it is the target.

    Holding a mispredicted cell instead would make a null result ambiguous
    between "the direction is unreachable" and "the coupling exists but never
    yields this rotation here" -- see the module docstring.
    """
    assert HELD_GOAL_POS == direction_position(DIR_E)
    assert HELD_GOAL_ROT == DERIVED_RULE(DIR_E) == 1


def test_every_cell_measures_a_distinct_geometry() -> None:
    """Two cells sharing a geometry would dedup to one share code on upload."""
    cells = build_cells()
    assert len({c.key for c in cells}) == len(cells)


def test_render_order_front_loads_the_two_known_actives() -> None:
    """A harness problem must cost 2 renders, not 9."""
    ordered = _render_order(build_cells())
    assert ordered[0].kind == "control"
    assert ordered[1].kind == "sweep" and ordered[1].starter_rot == 0
    assert [c.starter_rot for c in ordered[2:7]] == [1, 2, 3, 4, 5]
    assert {c.kind for c in ordered[7:]} == {"probe", "backfill"}


# --- Variant builder -------------------------------------------------------


def test_control_variant_is_byte_identical_to_generator() -> None:
    """The sweep's core precondition, asserted the way the script asserts it."""
    base = generate_minimal()
    _assert_control_matches_generator(base)  # raises if it diverges
    rebuilt = build_variant(
        base, starter_rot=0, goal_pos=CONTROL_GOAL_POS, goal_rot=CONTROL_GOAL_ROT
    )
    assert serialize_course(rebuilt) == serialize_course(base)


@pytest.mark.parametrize("starter_rot", STARTER_ROTATIONS)
def test_variant_sets_the_starter_rotation_and_leaves_it_at_the_origin(
    starter_rot: int,
) -> None:
    """The starter moves in rotation only -- never in position."""
    course = build_variant(
        generate_minimal(),
        starter_rot=starter_rot,
        goal_pos=HELD_GOAL_POS,
        goal_rot=HELD_GOAL_ROT,
    )
    cells = course.layer_construction_data[0].cell_construction_datas
    starter = next(
        c
        for c in cells
        if c.tree_node_data.construction_data.kind is TileKind.STARTER
    )
    assert starter.local_hex_position == ORIGIN
    assert starter.tree_node_data.construction_data.hex_rotation == starter_rot


def test_variant_moves_the_goal_and_introduces_no_rail() -> None:
    """Two tiles, zero rails -- the shape the app certified."""
    course = build_variant(
        generate_minimal(), starter_rot=3, goal_pos=PROBE_GOAL_POS, goal_rot=PROBE_GOAL_ROT
    )
    cells = course.layer_construction_data[0].cell_construction_datas
    assert len(cells) == 2
    goal = next(
        c
        for c in cells
        if c.tree_node_data.construction_data.kind is TileKind.GOAL_RAIL
    )
    assert goal.local_hex_position == PROBE_GOAL_POS
    assert goal.tree_node_data.construction_data.hex_rotation == PROBE_GOAL_ROT
    assert course.rail_construction_data == ()


def test_each_starter_rotation_produces_distinct_bytes() -> None:
    """If starter rotation never reaches the wire, the sweep measures one course six times.

    The endpoint dedups by content hash, so six identical payloads would return
    one share code and six identical `active` verdicts -- which classify() would
    read as STARTER_ROTATION_IRRELEVANT. That is a fabricated finding, not a
    null result, so it is guarded here as well as in the script's phase 0.
    """
    base = generate_minimal()
    digests = {
        serialize_course(
            build_variant(
                base, starter_rot=s, goal_pos=HELD_GOAL_POS, goal_rot=HELD_GOAL_ROT
            )
        )
        for s in STARTER_ROTATIONS
    }
    assert len(digests) == len(STARTER_ROTATIONS)


def test_the_two_live_directions_are_two_apart() -> None:
    """The reading that motivates the sweep: E (0) and NW (2) are the 2026-08-07 actives.

    Four "unreachable" directions look arbitrary until you notice the two live
    ones sit exactly two apart -- the signature of a starter with two exits.
    That reframes the derived rule as goal-side and total, with the *direction
    set* restricted rather than the rotation mapping.
    """
    live = {DIR_E, DIR_NW}
    assert (DIR_NW - DIR_E) % 6 == 2
    assert {d for d in range(6) if d not in live} == {1, 3, 4, 5}


def test_probe_is_the_cell_the_rotating_exit_set_predicts() -> None:
    """At s=1 the exit set {E, NW} becomes {NE, W}; NE takes goal rotation (d+1)%6."""
    s = PROBE_STARTER_ROT
    exits_at_s = {(DIR_E + s) % 6, (DIR_NW + s) % 6}
    assert exits_at_s == {DIR_NE, 3}
    assert PROBE_GOAL_POS == direction_position(DIR_NE)
    assert PROBE_GOAL_ROT == DERIVED_RULE(DIR_NE) == 2
    # And the held cell must die at s=1 under the same hypothesis.
    assert DIR_E not in exits_at_s


# --- classify(): every pre-declared condition -------------------------------


def test_inactive_control_is_harness_suspect_whatever_the_data_said() -> None:
    """A lying oracle outranks every reading taken through it."""
    verdict, _ = classify(_rendered(control="inactive"))
    assert verdict == "HARNESS_SUSPECT"


def test_inactive_s0_cell_is_a_replication_failure() -> None:
    """s=0 reproduces a 2026-08-07 measurement; disagreement invalidates the run."""
    sweep = {s: "active" for s in STARTER_ROTATIONS} | {0: "inactive"}
    verdict, detail = classify(_rendered(sweep=sweep))
    assert verdict == "REPLICATION_FAILED"
    assert "2026-08-07" in detail


def test_active_backfill_cell_is_model_wrong() -> None:
    """NW connecting at rot 0 as well as rot 3 breaks one-rotation-per-direction."""
    verdict, detail = classify(_rendered(backfill="active"))
    assert verdict == "MODEL_WRONG"
    assert "NW" in detail


def test_model_wrong_outranks_a_clean_sweep_result() -> None:
    """The backfill can falsify the premise the sweep's own reading rests on."""
    verdict, _ = classify(_rendered(backfill="active", probe="inactive"))
    assert verdict == "MODEL_WRONG"


def test_all_six_active_with_a_dead_probe_means_starter_rotation_is_irrelevant() -> None:
    """The outcome that resolves #14 toward a partial function and unblocks M5.c."""
    verdict, detail = classify(_rendered())
    assert verdict == "STARTER_ROTATION_IRRELEVANT"
    assert "genuinely unreachable" in detail


def test_all_six_active_with_a_live_probe_means_rotation_unlocks_directions() -> None:
    """Not a contradiction: a starter already connects in two directions at s=0."""
    verdict, _ = classify(_rendered(probe="active"))
    assert verdict == "STARTER_UNLOCKS_DIRECTIONS"


def test_dead_s1_with_a_live_probe_means_the_exit_set_rotates() -> None:
    """The held cell dies exactly where a rotating exit set says it should."""
    sweep = {s: "active" for s in STARTER_ROTATIONS} | {1: "inactive"}
    verdict, detail = classify(_rendered(sweep=sweep, probe="active"))
    assert verdict == "EXIT_SET_ROTATES"
    assert "total, not partial" in detail


def test_any_other_mixed_pattern_is_starter_rotation_matters() -> None:
    """Real coupling, neither modelled shape -- reported with the surviving rotations."""
    sweep = {s: "active" for s in STARTER_ROTATIONS} | {3: "inactive", 4: "inactive"}
    verdict, detail = classify(_rendered(sweep=sweep))
    assert verdict == "STARTER_ROTATION_MATTERS"
    assert "[3, 4]" in detail


def test_a_live_probe_without_a_dead_s1_is_not_reported_as_exit_set_rotation() -> None:
    """The hypothesis requires the held cell to die at s=1, not merely the probe to live."""
    sweep = {s: "active" for s in STARTER_ROTATIONS} | {2: "inactive"}
    verdict, _ = classify(_rendered(sweep=sweep, probe="active"))
    assert verdict == "STARTER_ROTATION_MATTERS"


def test_informative_verdicts_excludes_every_failure_condition() -> None:
    """Exit code 0 must mean "we learned something", not "the script finished"."""
    for failure in ("HARNESS_SUSPECT", "REPLICATION_FAILED", "MODEL_WRONG", "INCOMPLETE"):
        assert failure not in INFORMATIVE_VERDICTS
    assert INFORMATIVE_VERDICTS == {
        "STARTER_ROTATION_IRRELEVANT",
        "EXIT_SET_ROTATES",
        "STARTER_UNLOCKS_DIRECTIONS",
        "STARTER_ROTATION_MATTERS",
    }


# --- Resume ----------------------------------------------------------------


def test_resume_key_separates_cells_that_differ_only_in_starter_rotation(tmp_path) -> None:
    """A three-field key would copy one sweep cell's verdict onto all six."""
    prior = build_cells()
    for cell in prior:
        if cell.kind == "sweep" and cell.starter_rot == 2:
            cell.validity = "inactive"
            cell.code = "AAAAAAAAAA"
    sidecar = tmp_path / "results.json"
    _write_sidecar(sidecar, prior, {})

    fresh = build_cells()
    restored = _load_resume(sidecar, fresh)
    assert restored == 1
    by_rot = {c.starter_rot: c for c in fresh if c.kind == "sweep"}
    assert by_rot[2].validity == "inactive"
    assert all(by_rot[s].validity is None for s in STARTER_ROTATIONS if s != 2)


def test_resume_ignores_cells_that_never_got_a_verdict(tmp_path) -> None:
    """An upload_error or a render_error must not read back as a measurement."""
    prior = build_cells()
    for cell in prior:
        if cell.kind == "backfill":
            cell.upload_error = "UploadError: HTTP 520"
    sidecar = tmp_path / "results.json"
    _write_sidecar(sidecar, prior, {})

    fresh = build_cells()
    assert _load_resume(sidecar, fresh) == 0
    assert all(c.validity is None for c in fresh)


def test_sidecar_round_trips_every_field_classify_reads(tmp_path) -> None:
    """A crash mid-run must leave a file the resume path can actually use."""
    cells = _rendered()
    sidecar = tmp_path / "results.json"
    _write_sidecar(sidecar, cells, {"timestamp": "2026-08-08T00:00:00+00:00"})
    payload = json.loads(sidecar.read_text())
    assert payload["timestamp"] == "2026-08-08T00:00:00+00:00"
    assert len(payload["cells"]) == len(cells)
    assert {c["validity"] for c in payload["cells"]} == {"active", "inactive"}


def test_backfill_cell_is_the_one_the_goal_sweep_never_measured() -> None:
    """NW rot 0: HTTP 520 on upload, then a false active that was cleared."""
    backfill = next(c for c in build_cells() if c.kind == "backfill")
    assert (backfill.y, backfill.x) == (CONTROL_GOAL_POS.y, CONTROL_GOAL_POS.x)
    assert backfill.goal_rot == BACKFILL_GOAL_ROT == 0
    assert backfill.goal_rot != CONTROL_GOAL_ROT
