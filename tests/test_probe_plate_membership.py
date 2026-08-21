"""Tests for the plate-membership probe (open unknown #15's mechanism).

These run offline. The probe's value is entirely in its design -- it spends
renders to separate rival models, and that is only worth doing if the models
actually disagree about the cells it renders. So the heavyweight tests are
`test_edge_run_separates_...` and `test_interior_run_separates_...`: if a later
edit made the rivals agree, the probe would still run, still print a verdict,
and silently stop being evidence. That is the failure shape observation #19
names, and `build_cells` refuses to start rather than allow it.

`test_the_2026_08_21_edge_measurement_refutes_port_only_and_table` replays the
run that actually happened. Unlike a replay of a *fitted* record, that one is
evidence: the predictions were declared in code before the renders, and two of
three rivals died. It is here so a later change to the models has to keep
explaining a real measurement.

The composed-model replay at the corner (`test_model_reproduces_...`) is the
opposite -- a regression guard, NOT evidence, because the model was built from
that table and explains it by construction (observation #20).

Path: traxgen/tests/test_probe_plate_membership.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.probe_plate_membership import (
    CERTIFIED_GOAL_POS,
    CORNER_STARTER_POS,
    EDGE_STARTER_POS,
    INTERIOR_STARTER_POS,
    MODELS,
    PLATE_FOOTPRINT,
    STARTER_INTRINSIC_PORTS,
    TABLE_CLAIM_2026_08_10,
    ProbeCell,
    build_cells,
    classify,
    on_plate,
    plate_model_says_active,
    port_model_says_active,
    starter_world_ports,
    table_model_says_active,
)
from traxgen.graph import MEASURED_LIVE_DIRECTIONS, goal_rotation_for, predict_connection
from traxgen.hex import HexVector
from traxgen.parser import parse_course
from traxgen.types import LayerKind

DIR_E, DIR_NE, DIR_NW, DIR_W, DIR_SW, DIR_SE = range(6)


# --- the corpus-measured inputs --------------------------------------------


def test_plate_footprint_is_the_thirty_cells_the_corpus_showed():
    """Guards the transcription of a measurement, not the measurement itself."""
    assert len(PLATE_FOOTPRINT) == 30
    assert all(-6 <= y <= 0 and 0 <= x <= 5 for y, x in PLATE_FOOTPRINT)


@pytest.mark.integration
def test_no_committed_fixture_uses_a_cell_outside_the_footprint():
    """The one check on PLATE_FOOTPRINT that runs offline against committed data.

    The constant came from a corpus that deliberately lives outside the repo, so
    the suite cannot re-derive it. What it can do is falsify it: GDZJZA3J3T
    carries 15 BASE_LAYER_PIECE layers (plates are addable, and this is what
    that looks like on the wire), and one cell outside the footprint would prove
    the constant wrong. Zero is not proof it is right.
    """
    fixture = Path(__file__).parent / "fixtures" / "GDZJZA3J3T.course"
    course = parse_course(fixture.read_bytes())
    plates = [
        layer
        for layer in course.layer_construction_data
        if layer.layer_kind.name == "BASE_LAYER_PIECE"
    ]
    assert plates, "fixture carries no BASE_LAYER_PIECE layers; the guard is vacuous"
    outside = {
        (cell.local_hex_position.y, cell.local_hex_position.x)
        for layer in plates
        for cell in layer.cell_construction_datas
    } - PLATE_FOOTPRINT
    assert not outside, f"cells outside the measured footprint: {sorted(outside)}"


def test_the_three_named_starters_have_the_boundaries_they_claim():
    """Corner, edge and interior must differ in exactly the way the design uses."""
    corner_off = {d for d in range(6) if not on_plate(CORNER_STARTER_POS.neighbor(d))}
    edge_off = {d for d in range(6) if not on_plate(EDGE_STARTER_POS.neighbor(d))}
    interior_off = {d for d in range(6) if not on_plate(INTERIOR_STARTER_POS.neighbor(d))}
    assert corner_off == {DIR_W, DIR_SW, DIR_SE}
    assert edge_off == {DIR_E, DIR_SW, DIR_SE}
    assert interior_off == set()
    for pos in (CORNER_STARTER_POS, EDGE_STARTER_POS, INTERIOR_STARTER_POS):
        assert on_plate(pos)


def test_starter_ports_flip_parity_with_rotation():
    """Even-only intrinsic ports present all-even world edges at even rotations."""
    assert {0, 2, 4} == STARTER_INTRINSIC_PORTS
    for rot in range(6):
        edges = starter_world_ports(rot)
        assert len(edges) == 3
        assert all(e % 2 == rot % 2 for e in edges)


@pytest.mark.parametrize("bad", [-1, 6, 7])
def test_starter_world_ports_refuses_out_of_range_rotations(bad):
    with pytest.raises(ValueError):
        starter_world_ports(bad)


# --- the rivals -------------------------------------------------------------


def test_model_reproduces_the_measured_table_at_the_corner():
    """Regression guard only -- the model was built from this table (observation #20).

    Green here is NOT evidence the model is right. It is evidence that a later
    edit has not silently broken agreement with what six exhaustive sweeps
    measured at starter (0,0).
    """
    for starter_rot, measured in MEASURED_LIVE_DIRECTIONS.items():
        predicted = {
            d
            for d in range(6)
            if plate_model_says_active(
                CORNER_STARTER_POS, starter_rot, d, goal_rotation_for(d)
            )
        }
        assert predicted == set(measured), (
            f"s={starter_rot}: model says {sorted(predicted)}, "
            f"sweeps measured {sorted(measured)}"
        )


def test_the_port_only_model_cannot_reproduce_the_measured_table():
    """The rival's failure is why the plate term was introduced at all.

    Without plate membership the model predicts three live directions in every
    row; the sweeps measured two and one. If this ever passes, two rivals have
    collapsed into one.
    """
    for starter_rot, measured in MEASURED_LIVE_DIRECTIONS.items():
        predicted = {
            d
            for d in range(6)
            if port_model_says_active(
                CORNER_STARTER_POS, starter_rot, d, goal_rotation_for(d)
            )
        }
        assert len(predicted) == 3
        assert predicted != set(measured)


def test_the_frozen_table_claim_is_transcribed_correctly():
    """Literal against literal: the quotation matches the historical record.

    The predecessor of this test compared the rival against graph.py's
    MEASURED_LIVE_DIRECTIONS -- which is the same data the rival then read, so
    the test could not fail (proven by mutation in the s22 panel review: a
    corrupted record left it green). Two independent transcriptions of the
    same historical claim can disagree only through a typo, which is exactly
    what this version catches -- and, unlike its predecessor, it must NOT
    track graph.py: if a future re-measurement changes the corner table, the
    quotation of what was claimed in August 2026 stays put.
    """
    assert dict(TABLE_CLAIM_2026_08_10) == {
        0: {0, 2},
        1: {1},
        2: {0, 2},
        3: {1},
        4: {0, 2},
        5: {1},
    }


def test_the_frozen_claim_coincides_with_the_corner_record_today():
    """The quotation and the record agree *now* -- documented as coincidence.

    graph.py's corner table and the frozen claim are equal today because the
    claim was a faithful (if position-blind) reading of that table. This test
    states the coincidence so that if the record ever moves, the failure names
    what happened -- the record changed, the quotation deliberately did not --
    instead of leaving a silent divergence for an auditor to puzzle over.
    """
    assert dict(TABLE_CLAIM_2026_08_10) == {
        s: set(dirs) for s, dirs in MEASURED_LIVE_DIRECTIONS.items()
    }


def test_the_table_model_ignores_position_which_is_the_claim_under_test():
    """The frozen claim keys on rotation alone; at the edge that was falsifiable."""
    for pos in (CORNER_STARTER_POS, EDGE_STARTER_POS, INTERIOR_STARTER_POS):
        assert table_model_says_active(pos, 0, DIR_E, goal_rotation_for(DIR_E)) is True


def test_goal_rotation_rule_is_the_one_graph_py_locked():
    """The probe renders one rotation per direction; it must be graph.py's rule."""
    for direction in range(6):
        assert goal_rotation_for(direction) == (direction + 1) % 6


# --- the probe's design -----------------------------------------------------


def _by_direction(cells: list[ProbeCell]) -> dict[int, ProbeCell]:
    return {c.direction: c for c in cells if c.kind == "probe"}


def test_edge_run_separates_plate_from_both_rivals():
    """At (0,1) the models split on E and SW, which is why that run was worth eight renders."""
    cells = build_cells(EDGE_STARTER_POS, 0)
    by_dir = _by_direction(cells)
    assert {d for d, c in by_dir.items() if c.role == "discriminator"} == {DIR_E, DIR_SW}
    assert by_dir[DIR_E].separates() == {("plate", "port_only"), ("plate", "table")}
    assert by_dir[DIR_SW].separates() == {("plate", "port_only"), ("port_only", "table")}
    assert by_dir[DIR_NW].role == "local_control"


def test_interior_run_separates_plate_from_the_table():
    """At (-3,2) the plate term stops biting, so the live rival is graph.py's table.

    SW carries the whole run: the composed model says a direction dark in six
    exhaustive sweeps lights up once the starter leaves the corner.
    """
    cells = build_cells(INTERIOR_STARTER_POS, 0)
    by_dir = _by_direction(cells)
    assert {d for d, c in by_dir.items() if c.role == "discriminator"} == {DIR_SW}
    assert by_dir[DIR_SW].predictions["plate"] == "active"
    assert by_dir[DIR_SW].predictions["table"] == "inactive"
    assert {d for d, c in by_dir.items() if c.role == "local_control"} == {DIR_E, DIR_NW}


def test_interior_at_odd_rotation_also_discriminates():
    """The odd-parity row is a second independent test of the same mechanism."""
    cells = build_cells(INTERIOR_STARTER_POS, 1)
    by_dir = _by_direction(cells)
    discriminators = {d for d, c in by_dir.items() if c.role == "discriminator"}
    assert discriminators, "odd rotation must still separate a rival"
    assert any(c.role == "local_control" for c in by_dir.values())


def test_every_run_carries_a_cell_every_rival_calls_active():
    """An all-inactive run must be distinguishable from a broken setup (#21)."""
    for pos in (EDGE_STARTER_POS, INTERIOR_STARTER_POS):
        cells = build_cells(pos, 0)
        assert any(c.role == "local_control" for c in cells if c.kind == "probe")


def test_build_cells_refuses_an_off_plate_starter():
    with pytest.raises(RuntimeError, match="off-plate"):
        build_cells(HexVector(y=0, x=2), 0)


def test_build_cells_refuses_the_corner_because_a_cell_would_be_the_control():
    """At (0,0) rot 0 the NW cell IS the certified geometry.

    Identical bytes dedup to one share code, so the run would render a single
    course while believing it rendered two -- the same hazard main()'s payload
    check catches, caught here at design time instead. The corner is also the
    position six exhaustive sweeps already measured, so there is nothing to
    learn there anyway.
    """
    with pytest.raises(RuntimeError, match="certified control's own geometry"):
        build_cells(CORNER_STARTER_POS, 0)


def test_build_cells_refuses_a_run_that_cannot_discriminate(monkeypatch):
    """With one rival there is nothing to separate, and the run must not start."""
    monkeypatch.setattr(
        "scripts.probe_plate_membership.MODELS", {"plate": plate_model_says_active}
    )
    with pytest.raises(RuntimeError, match="separates any two rivals"):
        build_cells(EDGE_STARTER_POS, 0)


def test_certified_control_is_the_app_certified_geometry():
    control = next(c for c in build_cells() if c.role == "certified_control")
    assert (control.starter_y, control.starter_x) == (0, 0)
    assert (control.y, control.x) == (CERTIFIED_GOAL_POS.y, CERTIFIED_GOAL_POS.x)
    assert control.rot == 3


def test_every_probe_cell_is_a_distinct_geometry():
    for pos in (EDGE_STARTER_POS, INTERIOR_STARTER_POS):
        cells = build_cells(pos, 0)
        keys = {(c.starter_y, c.starter_x, c.starter_rot, c.y, c.x, c.rot) for c in cells}
        assert len(keys) == len(cells)


# --- the measurement that actually happened ---------------------------------

# The 2026-08-21 run at starter (0,1), rotation 0. Play-button verdicts as
# rendered, both harness brackets active, no aborts.
EDGE_RUN_2026_08_21: dict[int, str] = {
    DIR_E: "inactive",
    DIR_NE: "inactive",
    DIR_NW: "active",
    DIR_W: "inactive",
    DIR_SW: "inactive",
    DIR_SE: "inactive",
}


def _replay_edge_run() -> list[ProbeCell]:
    cells = build_cells(EDGE_STARTER_POS, 0)
    for cell in cells:
        cell.validity = (
            "active" if cell.direction is None else EDGE_RUN_2026_08_21[cell.direction]
        )
    return cells


def test_the_2026_08_21_edge_measurement_refutes_port_only_and_table():
    """Real evidence, not a fit: predictions were in code before these renders.

    Two rivals died in one run of eight renders -- `port_only` on both off-plate
    cells, and `table` on E, which shipped code at the time called live at
    rotation 0 regardless of where the starter sat (fixed in s22).
    """
    verdict, explanation = classify(_replay_edge_run(), final_control_validity="active")
    assert verdict == "MODEL_SURVIVES:plate"
    assert "port_only" in explanation
    assert "table" in explanation


def test_the_edge_measurement_is_what_makes_graph_py_wrong():
    """E rendered inactive where graph.py's position-blind table says CONNECTED."""
    cells = _by_direction(_replay_edge_run())
    assert cells[DIR_E].predictions["table"] == "active"
    assert cells[DIR_E].validity == "inactive"


# The 2026-08-21 interior run at starter (-3,2), rotation 0. SW rendered active
# after being dark in all six exhaustive corner sweeps -- the prediction that
# refuted graph.py's position-blind table.
INTERIOR_RUN_2026_08_21: dict[int, str] = {
    DIR_E: "active",
    DIR_NE: "inactive",
    DIR_NW: "active",
    DIR_W: "inactive",
    DIR_SW: "active",
    DIR_SE: "inactive",
}


def _replay_interior_run() -> list[ProbeCell]:
    cells = build_cells(INTERIOR_STARTER_POS, 0)
    for cell in cells:
        cell.validity = (
            "active" if cell.direction is None else INTERIOR_RUN_2026_08_21[cell.direction]
        )
    return cells


def test_the_interior_run_refutes_the_position_blind_table():
    """SW active at an interior cell is what kills graph.py's table.

    Real evidence: SW was declared active in code before the render, and it had
    rendered inactive in every one of six exhaustive sweeps at the corner.
    """
    cells = _by_direction(_replay_interior_run())
    assert cells[DIR_SW].predictions["table"] == "inactive"
    assert cells[DIR_SW].predictions["plate"] == "active"
    assert cells[DIR_SW].validity == "active"


def test_interior_survivors_are_reported_as_equivalent_not_as_a_failed_run():
    """Two survivors is the designed outcome here, not a shortfall.

    `plate` and `port_only` make identical predictions when every neighbour is
    on-plate, so no cell at (-3,2) can separate them. The first version of
    classify() demanded a single survivor and called this clean result
    UNDISCRIMINATING -- asserting more than `build_cells` ever guaranteed
    (observation #19).
    """
    verdict, why = classify(_replay_interior_run(), final_control_validity="active")
    assert verdict == "MODEL_SURVIVES:plate+port_only"
    assert "equivalent at this starter position" in why
    assert "table" in why


@pytest.mark.parametrize(
    ("starter", "rot"),
    [(EDGE_STARTER_POS, 0), (INTERIOR_STARTER_POS, 0), (INTERIOR_STARTER_POS, 1)],
)
def test_surviving_rivals_are_always_ones_no_cell_could_separate(starter, rot):
    """The invariant that makes 'multiple survivors' a clean result, not a failure.

    Surviving means matching every rendered cell; separating means differing on
    some cell. So two survivors *entails* that nothing in the run separated
    them -- there is no case where a separable pair both survive. This is why
    classify() has no 'the run failed to discriminate' branch: it would be
    unreachable, and an unreachable check is one whose passing carries no
    information (observation #12).
    """
    cells = build_cells(starter, rot)
    separable = {pair for c in cells if c.kind == "probe" for pair in c.separates()}
    for outcome in ("plate", "port_only", "table"):
        for cell in cells:
            cell.validity = (
                "active" if cell.direction is None else cell.predictions[outcome]
            )
        survivors = sorted(
            name
            for name in MODELS
            if all(
                c.predictions[name] == c.validity for c in cells if c.kind == "probe"
            )
        )
        pairs = {
            (a, b) for i, a in enumerate(survivors) for b in survivors[i + 1 :]
        }
        assert not (pairs & separable), (
            f"{outcome}: survivors {survivors} include a pair this run separates"
        )


def test_the_two_runs_together_leave_exactly_one_model_standing():
    """Neither run alone refutes both rivals; together they do.

    This is the session's actual conclusion, and no single-run verdict can see
    it -- the edge run killed `port_only`, the interior run killed `table`, and
    only `plate` explains all fourteen cells.
    """
    survivors = set(MODELS)
    for cells in (_replay_edge_run(), _replay_interior_run()):
        for name in list(survivors):
            if any(
                c.predictions[name] != c.validity for c in cells if c.kind == "probe"
            ):
                survivors.discard(name)
    assert survivors == {"plate"}


# --- classify() -------------------------------------------------------------


def _rendered(role_verdicts: dict[str, str]) -> list[ProbeCell]:
    """Stamp every cell with a validity chosen by its role."""
    cells = build_cells(EDGE_STARTER_POS, 0)
    for cell in cells:
        cell.validity = role_verdicts.get(cell.role)
    return cells


def test_classify_refuses_to_read_anything_when_the_certified_control_is_dark():
    cells = _rendered(
        {
            "certified_control": "inactive",
            "local_control": "active",
            "discriminator": "inactive",
            "shared_negative": "inactive",
        }
    )
    verdict, why = classify(cells, final_control_validity="active")
    assert verdict == "HARNESS_SUSPECT"
    assert "control" in why


def test_classify_refuses_when_the_closing_bracket_is_dark():
    """A run that looked clean until the last render still measured nothing."""
    cells = _rendered(
        {
            "certified_control": "active",
            "local_control": "active",
            "discriminator": "inactive",
            "shared_negative": "inactive",
        }
    )
    verdict, _ = classify(cells, final_control_validity="inactive")
    assert verdict == "HARNESS_SUSPECT"


def test_an_all_inactive_run_is_setup_suspect_not_a_confirmation():
    """The failure this probe most needs to refuse: everything dark reads as a
    confirmation of the plate model to a careless reader, and it is not."""
    cells = _rendered(
        {
            "certified_control": "active",
            "local_control": "inactive",
            "discriminator": "inactive",
            "shared_negative": "inactive",
        }
    )
    verdict, why = classify(cells, final_control_validity="active")
    assert verdict == "SETUP_SUSPECT"
    assert "NOT evidence" in why


def test_classify_reports_all_refuted_when_no_rival_explains_the_run():
    cells = _rendered(
        {
            "certified_control": "active",
            "local_control": "active",
            "discriminator": "inactive",
            "shared_negative": "active",
        }
    )
    verdict, why = classify(cells, final_control_validity="active")
    assert verdict == "ALL_REFUTED"
    assert "plate" in why


def test_classify_reports_incomplete_when_a_cell_never_rendered():
    cells = _rendered(
        {
            "certified_control": "active",
            "local_control": "active",
            "shared_negative": "inactive",
        }
    )
    verdict, _ = classify(cells, final_control_validity="active")
    assert verdict == "INCOMPLETE"


def test_classify_scores_every_rival_by_the_same_rule():
    """No branch privileges the model the probe was built to support.

    Feed it the run port_only would have predicted -- both off-plate cells live
    -- and port_only must win on exactly the same arithmetic that let plate win
    on the real data.
    """
    cells = build_cells(EDGE_STARTER_POS, 0)
    for cell in cells:
        cell.validity = (
            "active"
            if cell.direction is None
            else cell.predictions["port_only"]
        )
    verdict, _ = classify(cells, final_control_validity="active")
    assert verdict == "MODEL_SURVIVES:port_only"


# --- the live-audit property the panel found and pinned (s22) ----------------


def test_the_plate_rival_is_extensionally_graph_pys_live_model():
    """The probe already audits shipped code -- through the winner, not the loser.

    The s22 panel review verified that `plate_model_says_active` and graph.py's
    `predict_connection` agree on every one of the 6,480 cells reachable on the
    baseplate (30 footprint positions x 6 rotations x 6 directions x 6 goal
    rotations). That equivalence is the honest version of "the probe races what
    the library claims": the *model surface* is shared, while the *claim
    surface* (`connection_status`) stays out of the race because it contains
    the probe's own renders. Nothing pinned the equivalence, so drift would
    have ended the audit silently -- this sweep is the pin, over the whole
    class rather than sampled cells.
    """
    for y, x in sorted(PLATE_FOOTPRINT):
        pos = HexVector(y=y, x=x)
        for starter_rot in range(6):
            for direction in range(6):
                for goal_rot in range(6):
                    assert plate_model_says_active(
                        pos, starter_rot, direction, goal_rot
                    ) == predict_connection(
                        starter_rot,
                        direction,
                        goal_rot,
                        layer_kind=LayerKind.BASE_LAYER_PIECE,
                        starter_local_pos=pos,
                    ), f"diverged at pos={pos} s={starter_rot} d={direction} g={goal_rot}"
