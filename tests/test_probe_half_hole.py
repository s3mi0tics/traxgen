# tests/test_probe_half_hole.py
"""Offline tests for `scripts/probe_half_hole.py` -- the half-hole experiment.

No emulator and no upload. Two things carry the weight. First, the experiment's
whole claim is that it moves **one** factor: the goal's address is identical
across the lone/completed/null arms and only the board around it changes -- so a
test builds all three courses and reads the goal back through the production
parse path, asserting the address is byte-for-byte the same. Second, `classify`
turns render validities into a verdict, and it is graded on synthetic arms for
every branch, because on the day the renders come back it is the only thing
standing between a dark frame and a canonical claim.

Geometry is derived, so the tests assert the *properties* the derivation must
have (a solid starter reaching two seams and a solid cell; a completer that
supports both seams; a null that supports neither) rather than hardcoded cells,
which would be a second typed copy of the thing the script derives (#24).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.probe_half_hole import (
    DIRECTION_NAMES,
    Arm,
    Geometry,
    Target,
    _supports,
    build_arm_course,
    build_arms,
    classify,
    derive_geometry,
)
from scripts.probe_plate_seams import seam_cells
from traxgen.generator import generate_minimal
from traxgen.graph import GOAL_KINDS, STARTER_KINDS, placed_tiles
from traxgen.hex import HexVector
from traxgen.layout import CERTIFIED_LAYER_HEIGHT
from traxgen.plates import plate_footprint
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind

PLATE = LayerKind.BASE_LAYER_PIECE


# -- geometry ------------------------------------------------------------------


def test_geometry_is_a_solid_starter_reaching_two_seams_and_a_solid_cell() -> None:
    g = derive_geometry()
    footprint = plate_footprint(PLATE)
    seams = seam_cells(PLATE)
    assert g.starter_local in footprint and g.starter_local not in seams
    assert len(g.targets) == 2
    for target in g.targets:
        assert target.seam_local in seams, "each tested goal is a half-hole"
    assert g.control_local in (footprint - seams), "the local control is a solid cell"
    assert {t.seam_local for t in g.targets} != {g.control_local}


def test_the_completer_supports_both_seams_and_the_null_supports_neither() -> None:
    """The single-factor guarantee, at the geometry level and by hole-adjacency."""
    g = derive_geometry()
    footprint = plate_footprint(PLATE)
    for target in g.targets:
        assert _supports(g.completer_delta, target.seam_local, footprint), (
            f"completer {g.completer_delta} must complete {target.seam_local}"
        )
        assert not _supports(g.null_delta, target.seam_local, footprint), (
            f"null {g.null_delta} must leave {target.seam_local} unsupported"
        )
    assert g.completer_delta != g.null_delta


def test_geometry_is_deterministic() -> None:
    """No set-iteration nondeterminism in the derivation (the s28 .pyc lesson's
    cousin: a search over a set that returns 'first match' can vary by hash)."""
    first = derive_geometry()
    for _ in range(3):
        assert derive_geometry() == first


# -- arms and the single-factor address ---------------------------------------


def test_the_run_is_ten_renders_bracketed_by_certified_controls() -> None:
    arms = build_arms(derive_geometry())
    assert len(arms) == 10
    assert arms[0].role == "certified_control"
    assert arms[-1].role == "certified_control"
    roles = [a.role for a in arms]
    assert roles.count("lone") == 2
    assert roles.count("completed") == 2
    assert roles.count("null") == 2
    assert roles.count("local_control") == 1
    assert roles.count("negative_control") == 1


def test_certified_controls_are_generate_minimal_bytes() -> None:
    g = derive_geometry()
    control = next(a for a in build_arms(g) if a.role == "certified_control")
    built = build_arm_course(control, g, CERTIFIED_LAYER_HEIGHT)
    assert serialize_course(built) == serialize_course(generate_minimal())


def _goal_address(course) -> tuple:
    (goal,) = [t for t in placed_tiles(course) if t.kind in GOAL_KINDS]
    return (goal.layer_kind, (goal.local_pos.y, goal.local_pos.x), goal.hex_rotation)


def test_the_goal_address_is_identical_across_lone_completed_and_null() -> None:
    """The experiment's core claim: only the board moves, not the goal.

    For each tested direction the three arms are built for real and the goal is
    read back through `placed_tiles`. Its owning-plate kind, local `(y, x)` and
    rotation must be byte-identical -- if they are not, the arms differ in more
    than support and the run measures a confound rather than a factor.
    """
    g = derive_geometry()
    arms = build_arms(g)
    for direction_name in ("E", "SW"):
        trio = [
            a
            for a in arms
            if a.role in ("lone", "completed", "null")
            and DIRECTION_NAMES[a.direction] == direction_name
        ]
        assert len(trio) == 3
        addresses = {
            _goal_address(build_arm_course(a, g, CERTIFIED_LAYER_HEIGHT)) for a in trio
        }
        assert len(addresses) == 1, f"{direction_name}: goal address moved across arms"


def test_the_starter_address_is_identical_across_all_test_arms() -> None:
    g = derive_geometry()
    starters = set()
    for a in build_arms(g):
        if a.role in ("lone", "completed", "null", "local_control", "negative_control"):
            course = build_arm_course(a, g, CERTIFIED_LAYER_HEIGHT)
            (starter,) = [t for t in placed_tiles(course) if t.kind in STARTER_KINDS]
            starters.add(((starter.local_pos.y, starter.local_pos.x), starter.hex_rotation))
    assert starters == {(g.starter_local, g.starter_rot)}


def test_every_non_control_arm_has_a_distinct_payload() -> None:
    """Upload dedups by content hash, so two arms with equal bytes would collapse
    into one render. Lone/completed/null share a goal address but differ in plate
    layout, so their payloads must differ -- checked, since the run depends on it."""
    g = derive_geometry()
    digests = [
        hashlib.sha256(serialize_course(build_arm_course(a, g, CERTIFIED_LAYER_HEIGHT))).hexdigest()
        for a in build_arms(g)
        if a.role != "certified_control"
    ]
    assert len(set(digests)) == len(digests)


# -- classify ------------------------------------------------------------------


def _arm(role: str, validity: str | None, direction: int | None = None) -> Arm:
    return Arm(
        role=role,
        label=f"{role}_{direction}",
        direction=direction,
        plate_deltas=((0, 0),),
        goal_local=None,
        goal_rot=None,
        predicted="active",
        why="synthetic",
        validity=validity,
    )


def _run(*, controls="active", local="active", negative="inactive", e=None, sw=None) -> list[Arm]:
    arms = [_arm("certified_control", controls, None)]
    arms.append(_arm("local_control", local, 0))
    arms.append(_arm("negative_control", negative, 0))
    for direction, spec in ((0, e), (4, sw)):
        if spec is None:
            continue
        for role in ("lone", "completed", "null"):
            arms.append(_arm(role, spec[role], direction))
    arms.append(_arm("certified_control", controls, None))
    return arms


ALL_ACTIVE = {"lone": "active", "completed": "active", "null": "active"}
SUPPORTED = {"lone": "inactive", "completed": "active", "null": "inactive"}


def test_the_negative_control_is_the_tested_cell_at_a_wrong_rotation() -> None:
    """Single-factor from an arm the same run renders active: same plate, same
    cell, only the goal rotation differs from `g = (d + 1) % 6`."""
    g = derive_geometry()
    assert g.negative_local == g.targets[0].seam_local
    assert g.negative_direction == g.targets[0].direction
    assert g.negative_rot != g.targets[0].goal_rot
    arm = next(a for a in build_arms(g) if a.role == "negative_control")
    assert arm.predicted == "inactive", "the only arm the model calls dark"
    assert arm.plate_deltas == ((0, 0),)


def test_the_shipped_model_agrees_the_negative_control_is_dark() -> None:
    """Graded against `predict_connection` rather than against this file's own
    expectation -- the rotation is wrong, so the model returns False."""
    from traxgen.graph import predict_connection

    g = derive_geometry()
    assert not predict_connection(
        g.starter_rot,
        g.negative_direction,
        g.negative_rot,
        layer_kind=g.kind,
        starter_local_pos=HexVector(*g.starter_local),
        goal_plate_offset=None,
    )
    assert predict_connection(
        g.starter_rot,
        g.targets[0].direction,
        g.targets[0].goal_rot,
        layer_kind=g.kind,
        starter_local_pos=HexVector(*g.starter_local),
        goal_plate_offset=None,
    ), "the same cell at the RIGHT rotation is the arm this contrasts with"


def test_an_active_negative_control_voids_the_run() -> None:
    """If the oracle says active for a geometry the record calls dark, an
    all-active campaign proves nothing -- the s27 false-active shape."""
    verdict, reason = classify(_run(negative="active", e=ALL_ACTIVE, sw=ALL_ACTIVE))
    assert verdict == "ORACLE_SUSPECT"
    assert "discriminate" in reason


def test_a_dead_certified_control_is_harness_suspect() -> None:
    verdict, _ = classify(_run(controls="inactive", e=ALL_ACTIVE))
    assert verdict == "HARNESS_SUSPECT"


def test_a_dead_local_control_is_setup_suspect() -> None:
    verdict, _ = classify(_run(local="inactive", e=SUPPORTED))
    assert verdict == "SETUP_SUSPECT"


def test_lone_disagreeing_with_null_is_confounded() -> None:
    """The predicted null failing: adding a non-completing plate changed the result."""
    verdict, reason = classify(
        _run(e={"lone": "inactive", "completed": "active", "null": "active"})
    )
    assert verdict == "CONFOUNDED"
    assert "null" in reason


def test_all_active_is_window_only() -> None:
    both = {"lone": "active", "completed": "active", "null": "active"}
    verdict, _ = classify(_run(e=both, sw=both))
    assert verdict == "WINDOW_ONLY"


def test_dark_alone_lit_completed_is_support_gates() -> None:
    both = {"lone": "inactive", "completed": "active", "null": "inactive"}
    verdict, _ = classify(_run(e=both, sw=both))
    assert verdict == "SUPPORT_GATES"


def test_directions_disagreeing_is_its_own_verdict() -> None:
    verdict, _ = classify(
        _run(
            e={"lone": "active", "completed": "active", "null": "active"},
            sw={"lone": "inactive", "completed": "active", "null": "inactive"},
        )
    )
    assert verdict == "DIRECTIONS_DISAGREE"


def test_an_incomplete_arm_is_incomplete_not_a_reading() -> None:
    verdict, _ = classify(_run(e={"lone": None, "completed": "active", "null": "inactive"}))
    assert verdict == "INCOMPLETE"


def test_a_mismatched_pair_that_is_not_the_null_is_indeterminate() -> None:
    """lone active, completed dark -- neither window-only nor support-gates."""
    verdict, _ = classify(_run(e={"lone": "active", "completed": "inactive", "null": "active"}))
    assert verdict == "INDETERMINATE"


def test_classify_types_hold_together() -> None:
    """A smoke check that Geometry/Target/Arm compose as the run uses them."""
    g = Geometry(
        kind=PLATE,
        starter_local=(-2, 4),
        starter_rot=0,
        completer_delta=(5, 0),
        null_delta=(-5, 0),
        control_direction=2,
        control_local=(-3, 4),
        control_rot=3,
        negative_direction=0,
        negative_local=(-2, 5),
        negative_rot=4,
        targets=(Target(0, (-2, 5), 1), Target(4, (-1, 3), 5)),
    )
    assert build_arm_course(build_arms(g)[0], g, CERTIFIED_LAYER_HEIGHT) is not None
    assert HexVector(*g.starter_local) == HexVector(-2, 4)


# -- the run itself, graded against its committed sidecars ---------------------
#
# Everything above grades the *design*: derived geometry, a single moved factor,
# and `classify` on synthetic arms. Nothing above has ever seen the campaign.
# What follows closes that gap the way s28 closed it for the 2x2 -- the run's
# sidecars are gitignored under `screenshots/`, so they are copied into
# `tests/fixtures/` and the claims rest on committed files (#24).
#
# Two campaigns, deliberately kept apart. The nine-arm run and the ten-arm
# re-run with the negative control added are different runs of one experiment,
# and #37 is the record of what happens when their figures get welded together:
# each number stays true of the run nobody is talking about any more. So every
# assertion below is written over one sidecar at a time, and one test exists
# purely to make the two non-interchangeable.

FIXTURES = Path(__file__).parent / "fixtures"
SIDECAR_9ARM = FIXTURES / "half_hole_results_9arm_2026-08-26.json"
SIDECAR_10ARM = FIXTURES / "half_hole_results_10arm_2026-08-26.json"
SIDECARS = [SIDECAR_9ARM, SIDECAR_10ARM]

CONTROL_ROLES = {"certified_control", "local_control", "negative_control"}


def load(sidecar: Path) -> dict:
    return json.loads(sidecar.read_text())


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.stem)
def test_every_arm_rebuilds_to_the_course_that_rendered(sidecar: Path) -> None:
    """The #24 claim, and the reason the sidecars are committed at all.

    Every arm is rebuilt through the probe's own builder and required to hash to
    the `payload_sha256` the run uploaded -- so the courses these tests reason
    about are, byte for byte, the courses the app rendered. Without it the
    sidecar is a table of verdicts about courses nobody can reconstruct, and a
    later edit to `build_arm_course` would silently retitle the experiment.
    """
    record = load(sidecar)
    geometry = derive_geometry()
    arms = {arm.label: arm for arm in build_arms(geometry)}
    for entry in record["arms"]:
        course = build_arm_course(arms[entry["label"]], geometry, record["layer_height"])
        digest = hashlib.sha256(serialize_course(course)).hexdigest()
        assert digest == entry["payload_sha256"], entry["label"]


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.stem)
def test_the_campaign_returned_window_only(sidecar: Path) -> None:
    record = load(sidecar)
    assert record["verdict"] == "WINDOW_ONLY"


def replay(sidecar: Path) -> tuple[str, str]:
    """Re-run today's `classify` over the validities the campaign recorded."""
    record = load(sidecar)
    by_label = {arm.label: arm for arm in build_arms(derive_geometry())}
    replayed = []
    for entry in record["arms"]:
        arm = by_label[entry["label"]]
        arm.validity = entry["validity"]
        replayed.append(arm)
    return classify(replayed)


def test_classify_reproduces_the_ten_arm_verdict_from_its_recorded_validities() -> None:
    """`classify` is graded on synthetic arms above; here it is graded on the run.

    A synthetic battery proves every branch is reachable. It cannot prove that
    the branch the *real* validities land in is the one the sidecar recorded,
    which is the claim the canonical files actually rest on.
    """
    verdict, _reason = replay(SIDECAR_10ARM)
    assert verdict == load(SIDECAR_10ARM)["verdict"] == "WINDOW_ONLY"


def test_todays_classifier_refuses_to_score_the_nine_arm_run_at_all() -> None:
    """A frozen quotation, and the reason the re-run exists (`decisions.md`, s22).

    The nine-arm campaign recorded `WINDOW_ONLY`. Replayed through the
    classifier that ships today it comes back **ORACLE_SUSPECT**, because it has
    no negative control and `classify` now refuses an all-active run that has
    not shown the oracle can still say `inactive` on that boot -- the s27
    false-active failure mode. The verdict in that sidecar is therefore a
    verdict from a superseded guard, not a second independent confirmation.

    Nothing about the conclusion changes: the ten-arm re-run carries its own
    negative control and stands alone. What changes is what may be *said*. "The
    campaign returned WINDOW_ONLY twice" reads as two confirmations, and at
    today's bar it is one confirmation plus one run the shipped classifier would
    decline to score. This test exists so that sentence cannot drift back in
    without something failing.
    """
    verdict, reason = replay(SIDECAR_9ARM)
    assert verdict == "ORACLE_SUSPECT"
    assert "negative control" in reason
    assert load(SIDECAR_9ARM)["verdict"] == "WINDOW_ONLY", "as recorded at the time"
    assert "negative_control" not in {e["label"] for e in load(SIDECAR_9ARM)["arms"]}


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.stem)
def test_the_brackets_and_the_local_control_held(sidecar: Path) -> None:
    """Both certified controls active, and the same course at both ends.

    The bracket only means something if the closing arm is the *same* geometry
    as the opening one; two different courses that both rendered would prove the
    harness worked twice on different things rather than that it was still
    working at the end (`decisions.md`, 2026-08-07).
    """
    arms = {entry["label"]: entry for entry in load(sidecar)["arms"]}
    assert arms["certified_open"]["validity"] == "active"
    assert arms["certified_close"]["validity"] == "active"
    assert arms["certified_open"]["payload_sha256"] == arms["certified_close"]["payload_sha256"]
    assert arms["local_control"]["validity"] == "active"


def test_the_negative_control_came_back_dark_on_the_same_boot() -> None:
    """What makes an all-active run a measurement rather than a stuck oracle.

    It is the ten-arm re-run's whole reason for existing, and it is asserted
    only there: the nine-arm run has no such arm, and a test written over both
    would have to soften into "if present", which is how a missing control stops
    being noticed.
    """
    arms = {entry["label"]: entry for entry in load(SIDECAR_10ARM)["arms"]}
    negative = arms["negative_control"]
    assert negative["validity"] == "inactive"
    assert negative["goal_local"] == arms["lone_E"]["goal_local"], "same cell as lone_E"
    assert negative["goal_rot"] != arms["lone_E"]["goal_rot"], "at the wrong rotation"


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.stem)
def test_the_predicted_null_held_on_both_directions(sidecar: Path) -> None:
    """`lone` == `null` == active is what excludes the one-plate-vs-two confound.

    Adding the non-completing plate changes the physical support of *zero* of
    this plate's cells, so that arm must show no change; a difference there
    would refute the reading rather than support it. Written over the directions
    the sidecar records rather than over `E` and `SW` by name, so a redesigned
    geometry is graded rather than skipped.
    """
    arms = {entry["label"]: entry for entry in load(sidecar)["arms"]}
    directions = sorted({DIRECTION_NAMES[e["direction"]] for e in arms.values()
                         if e["role"] in {"lone", "completed", "null"}})
    assert len(directions) == 2, directions
    for name in directions:
        lone = arms[f"lone_{name}"]["validity"]
        null = arms[f"null_{name}"]["validity"]
        completed = arms[f"completed_{name}"]["validity"]
        assert lone == null == completed == "active", name


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.stem)
def test_nothing_deduped_every_non_control_arm_got_its_own_share_code(sidecar: Path) -> None:
    """Counted off the record rather than typed.

    Seven of seven in the nine-arm run and eight of eight in the ten-arm is the
    sentence in `plan.md`; typing either number here would make this test a copy
    of the claim instead of a check on it (#12), and would have to be edited by
    hand the next time the design gains an arm.
    """
    tested = [e for e in load(sidecar)["arms"] if e["role"] not in CONTROL_ROLES]
    codes = {e["code"] for e in tested}
    assert len(codes) == len(tested) > 0
    assert all(code for code in codes), "every tested arm uploaded"


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.stem)
def test_both_campaigns_ran_clean(sidecar: Path) -> None:
    """No retries and no refused screens, which is why the guards are unspent
    insurance here rather than something that carried the run."""
    for entry in load(sidecar)["arms"]:
        assert entry["upload_attempts"] == 1, entry["label"]
        assert entry["render_attempts"] == 1, entry["label"]
        assert entry["refused_screens"] == [], entry["label"]
        assert entry["render_error"] is None and entry["upload_error"] is None, entry["label"]


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.stem)
def test_the_shipped_model_predicted_every_arm_the_run_rendered(sidecar: Path) -> None:
    """Prediction against measurement, arm by arm, off the record itself.

    The sidecar carries what the model said *before* the render, so this is the
    honest form of the claim in the run's own `reason` -- that the model is
    right here -- rather than a model refitted to the outcome (#20).
    """
    for entry in load(sidecar)["arms"]:
        assert entry["predicted"] == entry["validity"], entry["label"]


def test_the_two_campaigns_rendered_the_same_courses_where_they_overlap() -> None:
    """What makes the ten-arm run a *re-run* rather than a second experiment."""
    nine = {e["label"]: e["payload_sha256"] for e in load(SIDECAR_9ARM)["arms"]}
    ten = {e["label"]: e["payload_sha256"] for e in load(SIDECAR_10ARM)["arms"]}
    shared = nine.keys() & ten.keys()
    assert len(shared) == 9
    for label in shared:
        assert nine[label] == ten[label], label


def test_the_two_campaigns_are_not_interchangeable() -> None:
    """#37, made mechanical.

    The close that welded `ten renders ... at 589.3s` did it because both
    numbers were true of *a* run. Nothing structural stopped it. This pins that
    the two sidecars differ in both arm count and duration, so any figure quoted
    from one is checkably not a figure from the other.
    """
    nine, ten = load(SIDECAR_9ARM), load(SIDECAR_10ARM)
    assert len(nine["arms"]) != len(ten["arms"])
    assert nine["elapsed_seconds"] != ten["elapsed_seconds"]
    assert "negative_control" not in {e["label"] for e in nine["arms"]}
