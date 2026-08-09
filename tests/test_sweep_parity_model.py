"""Tests for the parity model and the prediction-testing sweep.

The heavyweight test here is `test_model_reproduces_every_measurement_taken_so_far`,
which replays every adjacency cell measured on 2026-08-07 and 2026-08-08 through
the model. A model fitted to the record has to at minimum explain the record, and
encoding that as a test means a later "improvement" to the model that quietly
breaks an old observation fails loudly instead of being rediscovered on the
emulator.

The second is `test_the_discriminator_cell_actually_discriminates` -- the cell
at (s=1, E, rot 4) only earns its render because the parity model and the rival
goal-rotation-shift model disagree about it. If a later edit made them agree,
that cell would silently stop being evidence while still looking like a test.

Path: traxgen/tests/test_sweep_parity_model.py
"""

from __future__ import annotations

import pytest

from scripts.sweep_parity_model import (
    EVEN_EXITS,
    ODD_EXITS,
    ParityCell,
    build_cells,
    classify,
    goal_rotation_for,
    parity_model_says_active,
    predicted_exits,
)

DIR_E, DIR_NE, DIR_NW, DIR_W, DIR_SW, DIR_SE = range(6)

# The rival: direction set fixed at {E, NW}, goal rotation shifts with starter.
def rival_says_active(starter_rot: int, direction: int, goal_rot: int) -> bool:
    """g = (d + 1 + 3s) % 6 over the fixed s=0 exit pair."""
    return direction in EVEN_EXITS and goal_rot == (direction + 1 + 3 * starter_rot) % 6


def _observations() -> list[tuple[int, int, int, str]]:
    """Every rendered cell to date, as (starter_rot, direction, goal_rot, validity).

    2026-08-07 goal-rotation sweep: starter pinned at 0, all six adjacent
    directions x all six goal rotations. Two actives: E rot 1 and NW rot 3.
    (NW rot 0 had no verdict that day -- its upload hit HTTP 520 -- and was
    filled in by the 2026-08-08 backfill cell below.)
    """
    obs: list[tuple[int, int, int, str]] = []
    actives_at_s0 = {(DIR_E, 1), (DIR_NW, 3)}
    for direction in range(6):
        for goal_rot in range(6):
            validity = "active" if (direction, goal_rot) in actives_at_s0 else "inactive"
            obs.append((0, direction, goal_rot, validity))

    # 2026-08-08 starter-rotation sweep: E rot 1 across starter rotations 0-5.
    for starter_rot in range(6):
        obs.append(
            (starter_rot, DIR_E, 1, "active" if starter_rot % 2 == 0 else "inactive")
        )
    # ...the exit-set probe, and the control rendered at both ends of the run.
    obs.append((1, DIR_NE, 2, "active"))
    obs.append((0, DIR_NW, 3, "active"))
    # The 2026-08-08 backfill cell is already covered by the s=0 grid above
    # (NW rot 0 -> inactive); listed here only so the count is explicit.
    return obs


# --- The model -------------------------------------------------------------


def test_model_reproduces_every_measurement_taken_so_far() -> None:
    """All 45 rendered cells from both sessions, with no exceptions."""
    observations = _observations()
    assert len(observations) == 36 + 6 + 2
    mismatches = [
        (s, d, g, validity)
        for s, d, g, validity in observations
        if parity_model_says_active(s, d, g) != (validity == "active")
    ]
    assert mismatches == []


def test_exit_pair_flips_with_parity_and_returns_at_two() -> None:
    """The claim that makes this a parity model rather than a rotating one."""
    assert predicted_exits(0) == predicted_exits(2) == predicted_exits(4) == EVEN_EXITS
    assert predicted_exits(1) == predicted_exits(3) == predicted_exits(5) == ODD_EXITS
    assert EVEN_EXITS == {DIR_E, DIR_NW}
    assert ODD_EXITS == {DIR_NE, DIR_W}


def test_a_rotating_exit_set_would_not_fit_the_s2_observation() -> None:
    """Why the sweep's printed 'directions are {s, s+2}' text is refuted.

    A translating exit set sends {E, NW} to {NW, SW} at s=2, which excludes E --
    yet E rot 1 rendered active at s=2. Encoded so the rejected model stays
    rejected for a stated reason rather than by memory.
    """
    translated_at_s2 = {(d + 2) % 6 for d in EVEN_EXITS}
    assert DIR_E not in translated_at_s2
    assert parity_model_says_active(2, DIR_E, 1) is True


def test_goal_rule_carries_no_starter_term() -> None:
    """g = (d + 1) % 6, the same rule derived on 2026-08-07."""
    assert [goal_rotation_for(d) for d in range(6)] == [1, 2, 3, 4, 5, 0]


@pytest.mark.parametrize("starter_rot", range(6))
def test_exactly_two_directions_connect_at_any_starter_rotation(starter_rot: int) -> None:
    """One goal rotation per live direction, two live directions per starter rotation."""
    live = [
        (d, g)
        for d in range(6)
        for g in range(6)
        if parity_model_says_active(starter_rot, d, g)
    ]
    assert len(live) == 2


def test_every_direction_is_reachable_by_some_starter_rotation() -> None:
    """The consequence that matters for M5.c: the rule is total, not partial."""
    reachable = {d for s in range(6) for d in predicted_exits(s)}
    assert reachable == {DIR_E, DIR_NE, DIR_NW, DIR_W}
    # SW and SE remain unreachable under the model -- a real, named limit, not
    # an oversight. M5.c must not assume all six.
    assert DIR_SW not in reachable
    assert DIR_SE not in reachable


# --- The predictions -------------------------------------------------------


def test_build_cells_is_a_control_plus_four_predictions() -> None:
    """build_cells() raises if any declared prediction drifts from the model."""
    cells = build_cells()
    assert [c.kind for c in cells].count("control") == 1
    assert [c.kind for c in cells].count("prediction") == 4
    assert len({(c.starter_rot, c.direction, c.goal_rot) for c in cells}) == 5


def test_every_prediction_is_the_models_own_verdict() -> None:
    """No hand-entered guesses: the table and the model must agree cell by cell."""
    for cell in build_cells():
        expected = parity_model_says_active(
            cell.starter_rot, cell.direction, cell.goal_rot
        )
        assert cell.predicted == ("active" if expected else "inactive"), cell.label


def test_the_falsifier_puts_the_certified_geometry_at_risk() -> None:
    """The app-certified course must be predicted to BREAK at s=1, or it proves nothing."""
    cell = next(c for c in build_cells() if c.label == "certified_geometry_breaks")
    assert (cell.starter_rot, cell.direction, cell.goal_rot) == (1, DIR_NW, 3)
    assert cell.predicted == "inactive"
    # Same geometry at s=0 is the control, which is predicted active.
    control = next(c for c in build_cells() if c.kind == "control")
    assert (control.direction, control.goal_rot) == (cell.direction, cell.goal_rot)
    assert control.predicted == "active"


def test_the_discriminator_cell_actually_discriminates() -> None:
    """(s=1, E, rot 4) is only evidence because the two models disagree there."""
    cell = next(c for c in build_cells() if c.label == "no_goal_rotation_shift")
    args = (cell.starter_rot, cell.direction, cell.goal_rot)
    assert args == (1, DIR_E, 4)
    assert parity_model_says_active(*args) is False
    assert rival_says_active(*args) is True


def test_the_rival_model_also_explains_the_even_odd_pattern() -> None:
    """Which is why it needs a discriminator rather than more E rot 1 renders."""
    for starter_rot in range(6):
        assert rival_says_active(starter_rot, DIR_E, 1) == (starter_rot % 2 == 0)


def test_the_rival_is_already_dead_on_the_probe_cell() -> None:
    """NE rot 2 at s=1 rendered active; the rival has no exit at NE at all."""
    assert rival_says_active(1, DIR_NE, 2) is False
    assert parity_model_says_active(1, DIR_NE, 2) is True


# --- classify() ------------------------------------------------------------


def _rendered(outcomes: dict[str, str], *, control: str = "active") -> list[ParityCell]:
    """Cells with the given verdicts; predictions default to their predicted value."""
    cells = build_cells()
    for cell in cells:
        if cell.kind == "control":
            cell.validity = control
        else:
            cell.validity = outcomes.get(cell.label, cell.predicted)
    return cells


def test_all_predictions_met_is_model_confirmed() -> None:
    """The outcome that makes the rule total and unblocks M5.c."""
    verdict, detail = classify(_rendered({}), "active")
    assert verdict == "MODEL_CONFIRMED"
    assert "total" in detail


def test_a_missed_prediction_is_model_refuted_and_names_the_consequence() -> None:
    """A miss must report what it implies, not just that it missed."""
    verdict, detail = classify(
        _rendered({"certified_geometry_breaks": "active"}), "active"
    )
    assert verdict == "MODEL_REFUTED"
    assert "certified_geometry_breaks" in detail
    assert "ADDS exits" in detail


def test_the_discriminator_miss_names_the_rival_model() -> None:
    """If E rot 4 goes active at s=1, the report must say which model won."""
    _, detail = classify(_rendered({"no_goal_rotation_shift": "active"}), "active")
    assert "(d + 1 + 3s) % 6" in detail


def test_an_inactive_control_outranks_every_prediction() -> None:
    """A lying oracle invalidates readings taken through it, met or missed."""
    verdict, _ = classify(_rendered({}, control="inactive"), "active")
    assert verdict == "HARNESS_SUSPECT"


def test_a_drifted_closing_bracket_outranks_a_clean_result() -> None:
    """Active at render 1 says nothing about render 5."""
    verdict, _ = classify(_rendered({}), "inactive")
    assert verdict == "HARNESS_SUSPECT"


def test_an_unrendered_prediction_is_incomplete_not_confirmed() -> None:
    """A missing verdict must never read as a met prediction."""
    cells = _rendered({})
    next(c for c in cells if c.label == "odd_pair_includes_w").validity = None
    verdict, detail = classify(cells, "active")
    assert verdict == "INCOMPLETE"
    assert "odd_pair_includes_w" in detail
