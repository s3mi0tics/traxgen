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
