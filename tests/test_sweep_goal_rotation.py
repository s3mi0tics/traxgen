"""Tests for the M6.b goal-rotation sweep's offline logic.

The sweep itself needs a live upload endpoint and a booted emulator, so none
of that is tested here. What IS tested is everything that decides what the
sweep *concluded* — the enumeration, the variant builder, the affine-rule
fitter, and `classify()`. That split matters: a sweep whose classifier is
wrong produces a confident, well-formatted, false answer, which is exactly
the failure shape observation #12 names.

Two tests carry more weight than the rest:

  * `test_positive_control_variant_is_byte_identical_to_generator` — the
    sweep's core precondition. If this script's variant builder diverges
    from `generate_minimal()`, the sweep measures a course the app never
    certified while looking perfectly healthy.
  * `test_single_observation_does_not_determine_the_rule` — encodes *why*
    the sweep exists. The one known data point (NW, rot 3) is satisfied by
    both chiralities, so it constrains nothing on its own.

Path: traxgen/tests/test_sweep_goal_rotation.py
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.sweep_goal_rotation import (
    FAR_CONTROL_POS,
    POSITIVE_CONTROL_POS,
    POSITIVE_CONTROL_ROT,
    ROTATIONS,
    SweepCell,
    _load_resume,
    _render_order,
    build_cells,
    classify,
    fit_affine_rules,
)
from scripts.sweep_starter_rotation import build_variant
from traxgen.generator import generate_minimal
from traxgen.hex import ORIGIN, HexVector
from traxgen.serializer import serialize_course
from traxgen.types import TileKind

# The direction index of the app-certified geometry: GOAL_RAIL at (-1,0) is
# HEX_DIRECTIONS[2] (NW) from the starter, carrying rotation 3.
CONTROL_DIRECTION = 2


# --- Enumeration -----------------------------------------------------------


def test_build_cells_covers_adjacency_and_one_far_control() -> None:
    """36 adjacency cells (6 directions x 6 rotations) plus 6 distance-2 controls."""
    cells = build_cells()
    adjacent = [c for c in cells if c.kind == "adjacent"]
    far = [c for c in cells if c.kind == "control_far"]
    assert len(adjacent) == 36
    assert len(far) == 6
    assert len(cells) == 42


def test_every_adjacent_position_is_distance_one_and_every_rotation_is_swept() -> None:
    """Each of the 6 neighbours appears exactly once per rotation."""
    cells = build_cells()
    seen: dict[int, set[int]] = {d: set() for d in range(6)}
    for cell in cells:
        if cell.kind != "adjacent":
            continue
        assert cell.direction is not None
        assert ORIGIN.distance_to(HexVector(y=cell.y, x=cell.x)) == 1
        seen[cell.direction].add(cell.rot)
    assert all(rots == set(ROTATIONS) for rots in seen.values())


def test_far_control_is_out_of_adjacency_range() -> None:
    """The negative control must be far enough that adjacency cannot explain a hit."""
    assert ORIGIN.distance_to(FAR_CONTROL_POS) == 2


def test_exactly_one_positive_control_at_the_certified_geometry() -> None:
    """The app-certified cell must be present exactly once and flagged."""
    controls = [c for c in build_cells() if c.is_positive_control]
    assert len(controls) == 1
    assert (controls[0].y, controls[0].x) == (POSITIVE_CONTROL_POS.y, POSITIVE_CONTROL_POS.x)
    assert controls[0].rot == POSITIVE_CONTROL_ROT


def test_render_order_puts_the_controls_first() -> None:
    """A lying harness must cost 1 render, and a wrong model 7 — not 42."""
    ordered = _render_order(build_cells())
    assert ordered[0].is_positive_control
    assert all(c.kind == "control_far" for c in ordered[1:7])


# --- Variant builder -------------------------------------------------------


def test_positive_control_variant_is_byte_identical_to_generator() -> None:
    """The sweep's core precondition: the control cell IS the app-certified course.

    `generate_minimal()` produced the bytes uploaded as FLW4TMLP5V. If
    rebuilding that same geometry through `build_variant` yields different
    bytes, the sweep is measuring something the app never blessed — and
    every downstream verdict is uninterpretable while still looking clean.
    """
    base = generate_minimal()
    rebuilt = build_variant(
        base, starter_rot=0, goal_pos=POSITIVE_CONTROL_POS, goal_rot=POSITIVE_CONTROL_ROT
    )
    assert serialize_course(rebuilt) == serialize_course(base)


def test_variant_moves_the_goal_and_preserves_the_rest_of_the_shape() -> None:
    """Only the goal cell's position and rotation change; no rail is introduced."""
    base = generate_minimal()
    variant = build_variant(base, starter_rot=0, goal_pos=HexVector(y=0, x=1), goal_rot=5)

    assert len(variant.layer_construction_data) == 1
    assert len(variant.rail_construction_data) == 0
    assert len(variant.pillar_construction_data) == 0
    assert len(variant.wall_construction_data) == 0

    cells = variant.layer_construction_data[0].cell_construction_datas
    assert len(cells) == 2
    by_kind = {c.tree_node_data.construction_data.kind: c for c in cells}
    assert by_kind[TileKind.STARTER].local_hex_position == HexVector(y=0, x=0)
    goal = by_kind[TileKind.GOAL_RAIL]
    assert goal.local_hex_position == HexVector(y=0, x=1)
    assert goal.tree_node_data.construction_data.hex_rotation == 5


def test_variant_builder_refuses_a_base_without_exactly_one_starter() -> None:
    """Guard against silently rebuilding the wrong course if the generator changes."""
    base = generate_minimal()
    layer = base.layer_construction_data[0]
    goal_only = layer.cell_construction_datas[1]
    broken_layer = dataclasses.replace(layer, cell_construction_datas=(goal_only,))
    broken = dataclasses.replace(base, layer_construction_data=(broken_layer,))
    with pytest.raises(RuntimeError, match="STARTER"):
        build_variant(
            broken,
            starter_rot=0,
            goal_pos=POSITIVE_CONTROL_POS,
            goal_rot=POSITIVE_CONTROL_ROT,
        )


def test_all_42_cells_produce_distinct_payloads() -> None:
    """The upload endpoint dedups by content hash — colliding cells stop being cells."""
    base = generate_minimal()
    digests = {
        hashlib.sha256(
            serialize_course(
                build_variant(
                    base,
                    starter_rot=c.starter_rot,
                    goal_pos=HexVector(y=c.y, x=c.x),
                    goal_rot=c.rot,
                )
            )
        ).hexdigest()
        for c in build_cells()
    }
    assert len(digests) == 42


# --- Affine rule fitting ---------------------------------------------------


def test_single_observation_does_not_determine_the_rule() -> None:
    """The premise of the whole sweep: one data point leaves both chiralities alive.

    Goal NW of the starter (direction 2) at rotation 3 is satisfied by
    `rot = (d + 1) % 6` and by `rot = (5 - d) % 6` alike -- (1, 1) and (5, 5)
    in (a, b) form. They diverge at every other direction, which is what the
    other 30 cells are for.

    Exactly two rules survive, always: one observation determines `b` uniquely
    for each of the two chiralities, and constrains nothing else.
    """
    fits = fit_affine_rules({CONTROL_DIRECTION: POSITIVE_CONTROL_ROT})
    assert fits == [(1, 1), (5, 5)]


def test_full_clean_rule_resolves_to_exactly_one_fit() -> None:
    """Six observations pin the affine family down to a single rule."""
    assert fit_affine_rules({d: (d + 1) % 6 for d in range(6)}) == [(1, 1)]


def test_mirror_rule_resolves_to_the_other_chirality() -> None:
    """`rot = (5 - d) % 6` is the a = -1 branch, i.e. (5, 5) in mod-6 terms."""
    assert fit_affine_rules({d: (5 - d) % 6 for d in range(6)}) == [(5, 5)]


def test_no_rule_fits_a_scrambled_mapping() -> None:
    """A lookup-table result must produce zero affine fits, not a spurious one."""
    assert fit_affine_rules({0: 0, 1: 1, 2: 3, 3: 3, 4: 4, 5: 5}) == []


@given(a=st.sampled_from((1, 5)), b=st.integers(min_value=0, max_value=5))
def test_any_affine_rule_is_recovered_from_its_own_full_mapping(a: int, b: int) -> None:
    """Property: generate a mapping from a rule, and the fitter finds that rule.

    Round-tripping the fitter against every rule in the family it searches is
    cheaper and stricter than hand-picking examples — it fails on any (a, b)
    the implementation happens to miss.
    """
    observed = {d: (a * d + b) % 6 for d in range(6)}
    assert fit_affine_rules(observed) == [(a, b)]


# --- Classification --------------------------------------------------------


def _classified(
    active: dict[int, int] | None = None,
    *,
    control_active: bool = True,
    far_active: tuple[int, ...] = (),
    extra_active: tuple[tuple[int, int], ...] = (),
) -> tuple[str, str]:
    """Build a fully-rendered cell list with the given actives and classify it.

    `active` maps direction -> the one rotation that activated. `extra_active`
    adds additional (direction, rotation) actives, for the multi-active case.
    """
    active = dict(active or {})
    cells = build_cells()
    for cell in cells:
        cell.validity = "inactive"
        # The control's state is set solely by `control_active` — never also by
        # `active`, or a test asking for an inactive control would silently get
        # an active one and stop testing what it claims to.
        if cell.is_positive_control:
            cell.validity = "active" if control_active else "inactive"
        elif cell.kind == "control_far" and cell.rot in far_active:
            cell.validity = "active"
        elif cell.kind == "adjacent" and active.get(cell.direction) == cell.rot:
            cell.validity = "active"
        elif cell.kind == "adjacent" and (cell.direction, cell.rot) in extra_active:
            cell.validity = "active"
    return classify(cells)


def test_classify_reports_a_clean_rule() -> None:
    """One active per direction, all six fitting one rule."""
    verdict, detail = _classified({d: (d + 1) % 6 for d in range(6)})
    assert verdict == "CLEAN_RULE"
    assert "+d + 1" in detail


def test_classify_reports_a_lookup_table() -> None:
    """One active per direction, but no affine rule fits them."""
    verdict, _ = _classified({0: 0, 1: 1, 2: 3, 3: 3, 4: 4, 5: 5})
    assert verdict == "LOOKUP_TABLE"


def test_classify_reports_a_partial_function_and_names_the_dead_directions() -> None:
    """Zero actives in some directions is a legitimate finding, not a failure."""
    verdict, detail = _classified({CONTROL_DIRECTION: 3, 3: 4})
    assert verdict == "PARTIAL_FUNCTION"
    assert "E" in detail and "NE" in detail
    # Still reports which rules the surviving observations are consistent with.
    assert "consistent with" in detail


def test_classify_flags_multiple_actives_per_direction_as_model_wrong() -> None:
    """If two rotations both connect, rotation is not the sole determinant."""
    verdict, detail = _classified(
        {d: (d + 1) % 6 for d in range(6)}, extra_active=((0, 4),)
    )
    assert verdict == "MODEL_WRONG"
    assert "more than one rotation" in detail


def test_classify_flags_an_active_distance_two_control_as_model_wrong() -> None:
    """A hit at distance 2 falsifies adjacency as the connection mechanism."""
    verdict, detail = _classified({d: (d + 1) % 6 for d in range(6)}, far_active=(0,))
    assert verdict == "MODEL_WRONG"
    assert "distance-2" in detail


def test_classify_flags_an_inactive_positive_control_as_harness_suspect() -> None:
    """A failed control means the oracle is lying; nothing else in the run counts."""
    verdict, detail = _classified(
        {d: (d + 1) % 6 for d in range(6)}, control_active=False
    )
    assert verdict == "HARNESS_SUSPECT"
    assert "positive control" in detail


def test_harness_suspect_takes_precedence_over_every_other_verdict() -> None:
    """Control first: a broken oracle must not be reported as a finding."""
    verdict, _ = _classified({}, control_active=False, far_active=(0, 1, 2))
    assert verdict == "HARNESS_SUSPECT"


def test_render_errors_are_not_counted_as_activations() -> None:
    """`render_error` and `inactive` are distinct states; neither means 'connected'."""
    cells = build_cells()
    for cell in cells:
        cell.validity = "inactive"
        if cell.is_positive_control:
            cell.validity = "active"
    broken = next(
        c for c in cells if c.kind == "adjacent" and c.direction == 0 and c.rot == 0
    )
    broken.validity = None
    broken.render_error = "AdbCommandFailedError: boom"
    verdict, _ = classify(cells)
    assert verdict == "PARTIAL_FUNCTION"


# --- Resume ----------------------------------------------------------------
#
# A 20-minute render phase against a flaky upload endpoint means partial runs
# are normal, not exceptional. These cover the recovery path.


def _prior_run(tmp_path, entries: list[dict]):
    """Write a minimal prior-results JSON and return its path."""
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"cells": entries}))
    return path


def test_resume_restores_rendered_cells(tmp_path) -> None:
    """A cell with a verdict comes back with its verdict, code and screenshot."""
    cells = build_cells()
    path = _prior_run(
        tmp_path,
        [{"y": -1, "x": 0, "rot": 3, "validity": "active",
          "code": "KN6F459ZR3", "screenshot": "/tmp/shot.png"}],
    )
    assert _load_resume(path, cells) == 1
    control = next(c for c in cells if c.is_positive_control)
    assert control.validity == "active"
    assert control.code == "KN6F459ZR3"
    assert control.screenshot == "/tmp/shot.png"


def test_resume_does_not_restore_a_cell_that_never_uploaded(tmp_path) -> None:
    """The HTTP 520 case: no verdict means no restore, so phase 1 retries the upload.

    This is the whole point of the resume path. A cell whose upload failed has
    `validity: null` in the sidecar; if it were restored with its null verdict
    and a null code, the rerun would skip it and the hole would persist across
    every retry.
    """
    cells = build_cells()
    path = _prior_run(
        tmp_path,
        [{"y": -1, "x": 0, "rot": 0, "validity": None,
          "code": None, "screenshot": None}],
    )
    assert _load_resume(path, cells) == 0
    failed = next(c for c in cells if (c.y, c.x, c.rot) == (-1, 0, 0))
    assert failed.code is None
    assert failed.validity is None


def test_resume_ignores_entries_that_match_no_current_cell(tmp_path) -> None:
    """A sidecar from a differently-shaped sweep must not corrupt this one."""
    cells = build_cells()
    path = _prior_run(
        tmp_path,
        [{"y": 9, "x": 9, "rot": 0, "validity": "active", "code": "ZZZZZZZZZZ"}],
    )
    assert _load_resume(path, cells) == 0
    assert all(c.validity is None for c in cells)


def test_resume_restores_inactive_verdicts_too(tmp_path) -> None:
    """'inactive' is a real result -- re-rendering it would waste 25s per cell."""
    cells = build_cells()
    path = _prior_run(
        tmp_path,
        [{"y": 0, "x": 1, "rot": r, "validity": "inactive", "code": f"CODE{r}"}
         for r in range(6)],
    )
    assert _load_resume(path, cells) == 6


def test_sweep_cell_label_is_filesystem_safe() -> None:
    """Screenshot names must avoid parens and commas (see knowledge/environment.md)."""
    label = SweepCell(kind="adjacent", direction=2, y=-1, x=0, rot=3).label
    assert label == "s0_goal_y-1x0_rot3"
    assert not any(ch in label for ch in "(), ")


# --- Sweeping at a non-zero starter rotation --------------------------------
#
# The 2026-08-08 starter-rotation sweep showed the connectable direction set
# moves with the starter, so a sweep at s=0 measures one slice of a 6x6x6
# space rather than the whole thing. These cover the parameterisation.


def test_a_nonzero_starter_rotation_appends_a_dedicated_control() -> None:
    """The control must stay at the certified rotation, not follow the sweep.

    The app-certified geometry renders INACTIVE at s=1 (measured 2026-08-08),
    so a control that followed `--starter-rot` would abort every run except
    s=0 -- reporting HARNESS_SUSPECT for a harness that is working perfectly.
    """
    cells = build_cells(1)
    assert len(cells) == 43
    controls = [c for c in cells if c.is_positive_control]
    assert len(controls) == 1
    assert controls[0].kind == "control_positive"
    assert controls[0].starter_rot == 0
    assert (controls[0].y, controls[0].x, controls[0].rot) == (
        POSITIVE_CONTROL_POS.y,
        POSITIVE_CONTROL_POS.x,
        POSITIVE_CONTROL_ROT,
    )


def test_at_zero_the_control_is_still_one_of_the_thirty_six() -> None:
    """The s=0 shape is unchanged -- no extra cell, no extra render."""
    cells = build_cells(0)
    assert len(cells) == 42
    control = next(c for c in cells if c.is_positive_control)
    assert control.kind == "adjacent"


def test_every_swept_cell_carries_the_requested_starter_rotation() -> None:
    """Only the control is exempt."""
    cells = build_cells(4)
    swept = [c for c in cells if not c.is_positive_control]
    assert {c.starter_rot for c in swept} == {4}


def test_the_control_is_not_counted_as_an_observation_of_its_direction() -> None:
    """At s=1 the control is an s=0 course; treating it as NW data would invent a finding."""
    cells = build_cells(1)
    for cell in cells:
        cell.validity = "active" if cell.is_positive_control else "inactive"
    verdict, detail = classify(cells)
    assert verdict == "PARTIAL_FUNCTION"
    # All six directions must read as dead -- including NW, whose only active
    # cell in this list is the s=0 control.
    for name in ("E", "NE", "NW", "W", "SW", "SE"):
        assert name in detail


def test_cells_at_a_nonzero_starter_rotation_are_all_distinct_payloads() -> None:
    """43 cells, 43 courses -- content-hash dedup would silently merge any collision."""
    base = generate_minimal()
    cells = build_cells(1)
    digests = {
        hashlib.sha256(
            serialize_course(
                build_variant(
                    base,
                    starter_rot=c.starter_rot,
                    goal_pos=HexVector(y=c.y, x=c.x),
                    goal_rot=c.rot,
                )
            )
        ).hexdigest()
        for c in cells
    }
    assert len(digests) == len(cells)


@pytest.mark.parametrize("bad", (-1, 6, 7))
def test_build_cells_rejects_an_out_of_range_starter_rotation(bad: int) -> None:
    """hex_rotation is 0..5; anything else is a caller bug, not a sweep."""
    with pytest.raises(ValueError, match="starter_rot"):
        build_cells(bad)


def test_labels_disambiguate_the_same_geometry_at_different_starter_rotations() -> None:
    """Screenshot filenames must not collide across runs at different rotations."""
    a = SweepCell(kind="adjacent", direction=0, y=0, x=1, rot=1, starter_rot=0)
    b = SweepCell(kind="adjacent", direction=0, y=0, x=1, rot=1, starter_rot=1)
    assert a.label != b.label
    assert not any(ch in b.label for ch in "(), ")


def test_resume_from_a_sidecar_written_before_starter_rot_existed(tmp_path) -> None:
    """Pre-2026-08-08 sidecars have no starter_rot; those runs were all at 0."""
    cells = build_cells(0)
    path = _prior_run(
        tmp_path,
        [{"y": -1, "x": 0, "rot": 3, "validity": "active", "code": "KN6F459ZR3"}],
    )
    assert _load_resume(path, cells) == 1
    assert next(c for c in cells if c.is_positive_control).validity == "active"


def test_resume_does_not_carry_a_verdict_across_starter_rotations(tmp_path) -> None:
    """An s=0 result must never be restored onto the same geometry at s=1.

    This is the failure the four-field key exists to prevent: NW rot 3 is
    active at s=0 and inactive at s=1, so a three-field key would restore the
    active verdict onto the s=1 cell and manufacture the exact finding the
    2026-08-08 run disproved.
    """
    cells = build_cells(1)
    path = _prior_run(
        tmp_path,
        [{"starter_rot": 0, "y": -1, "x": 0, "rot": 3, "validity": "active",
          "code": "KN6F459ZR3"}],
    )
    restored = _load_resume(path, cells)
    assert restored == 1  # the s=0 control, which genuinely is that cell
    swept_nw3 = next(
        c for c in cells if c.kind == "adjacent" and (c.y, c.x, c.rot) == (-1, 0, 3)
    )
    assert swept_nw3.starter_rot == 1
    assert swept_nw3.validity is None
