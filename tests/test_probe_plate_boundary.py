"""Offline tests for the #17 2x2 probe (scripts/probe_plate_boundary.py).

No emulator, no network, no corpus. What has to be right *before* renders are
spent is the geometry and the verdict map: that the two arms of a target really
address the same world cell, that the controls bracket the run, and that every
branch of `classify` can fire.

The first of those is the experiment. If arm 1 and arm 2 land on different world
cells the run is not a 2x2 at all -- it is two unrelated renders, and every
verdict below would be describing something that never happened.

Path: traxgen/tests/test_probe_plate_boundary.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.probe_plate_boundary import (
    RENDER_ATTEMPTS,
    STARTER_LOCAL,
    STARTER_ROT,
    Arm,
    build_arm_course,
    build_arms,
    classify,
    derive_geometry,
    plate_positions,
    render_arm,
)
from tests.test_android_foreground import LAUNCHER_DUMP, FakeAdb, ctx_with
from traxgen.graph import STARTER_PLATE_ONLY, measured_live_directions
from traxgen.hex import HEX_DIRECTIONS
from traxgen.layout import CERTIFIED_LAYER_HEIGHT
from traxgen.plates import MEASURED_FOOTPRINTS
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind

PLATE = LayerKind.BASE_LAYER_PIECE
FOOTPRINT = frozenset(MEASURED_FOOTPRINTS[PLATE])
GEOMETRY = derive_geometry()

_FRAMES = Path(__file__).parent / "fixtures" / "frames"
DEAD_FRAME = (_FRAMES / "arm1_E_on_completer.png").read_bytes()
LIVE_FRAME = (_FRAMES / "arm1_SW_on_completer.png").read_bytes()


def _world(plate: tuple[int, int], local: tuple[int, int]) -> tuple[int, int]:
    return (plate[0] + local[0], plate[1] + local[1])


# --- The experiment's central invariant --------------------------------------


def _goal_world_cell(arm: Arm) -> tuple[int, int]:
    """Where the goal actually ends up, read out of the built course.

    Not computed from the Geometry -- read from the course the probe would
    upload, via the same `placed_tiles` the library uses to position tiles in
    world coordinates.
    """
    from traxgen.graph import placed_tiles
    from traxgen.types import TileKind

    course = build_arm_course(arm, GEOMETRY, CERTIFIED_LAYER_HEIGHT)
    goals = [t for t in placed_tiles(course) if t.kind is TileKind.GOAL_RAIL]
    assert len(goals) == 1, f"{arm.label} should carry exactly one goal"
    return (goals[0].world_pos.y, goals[0].world_pos.x)


def test_both_arms_of_a_target_address_the_same_world_cell() -> None:
    """The 2x2 is one cell rendered two ways. If it is two cells it is not a 2x2.

    Arm 1 addresses the cell in the completing plate's local frame; arm 2
    addresses it in the home plate's, off that plate's own footprint. Both must
    resolve to one world position, or arm 1 vs arm 2 stops isolating addressing
    and starts comparing two different places.

    **Read out of the built courses, not computed from the Geometry.** An
    earlier version of this test compared `target.home_local` against
    `target.completer_local` plus the delta -- arithmetic on the same two numbers
    the builder is *supposed* to use, which says nothing about whether it does.
    Mutating `build_arms` to address arm 1 on the home plate rather than the
    owning one left that version green while moving arm 1's goal five cells away
    (observations #12: the check and the claim shared an origin). This version
    fails that mutation.
    """
    arms = build_arms(GEOMETRY)
    by_target: dict[str, dict[str, Arm]] = {}
    for arm in arms:
        if arm.target_name:
            by_target.setdefault(arm.target_name, {})[arm.role] = arm

    assert by_target, "no targets means no experiment"
    for name, pair in by_target.items():
        one = _goal_world_cell(pair["arm1_owning_plate"])
        two = _goal_world_cell(pair["arm2_home_plate"])
        assert one == two, (
            f"target {name}: arm 1's goal lands at {one} and arm 2's at {two}. "
            "The arms must render one world cell two ways, or the comparison "
            "between them isolates nothing"
        )


def test_each_arm_addresses_its_cell_on_the_plate_it_claims_to() -> None:
    """The other half: same world cell is necessary, not sufficient.

    Arm 1 is only an *in-window* address if it is addressed on the plate whose
    footprint covers the cell; arm 2 is only *out-of-window* if it is addressed
    on the home plate where the footprint does not. Pinned as plate index plus
    footprint membership, so neither arm can quietly become the other.
    """
    arms = build_arms(GEOMETRY)
    for arm in arms:
        if arm.role == "arm1_owning_plate":
            assert arm.goal_plate_index == 1, "arm 1 addresses the completing plate"
            assert arm.goal_local in FOOTPRINT, "and does so in-window"
        elif arm.role == "arm2_home_plate":
            assert arm.goal_plate_index == 0, "arm 2 addresses the home plate"
            assert arm.goal_local not in FOOTPRINT, "and does so out-of-window"


def test_each_target_is_off_the_home_plate_and_on_the_completing_one() -> None:
    """Both halves matter, and each is what makes one arm the arm it is.

    Off the home footprint is what makes arm 2 an *out-of-window* address; on the
    completing footprint is what makes arm 1 an *in-window* one. A target failing
    either would leave the pair testing nothing.
    """
    assert GEOMETRY.targets, "no target means no experiment"
    for target in GEOMETRY.targets:
        assert target.home_local not in FOOTPRINT, f"{target.name} is on the home plate"
        assert target.completer_local in FOOTPRINT, (
            f"{target.name} is not covered by the completing plate either, so adding "
            "that plate changes nothing about this cell"
        )


def test_the_local_control_comes_from_the_rendered_record() -> None:
    """A control the model merely likes is not a control.

    It has to be a cell the *record* already calls active at this exact starter
    placement, so that a dark one implicates the two-plate family rather than the
    hypothesis under test (decisions.md, 2026-08-21).
    """
    live = measured_live_directions(
        STARTER_ROT,
        layer_kind=PLATE,
        starter_local_pos=STARTER_LOCAL,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=PLATE,
        goal_plate_offset=None,
    )
    assert live is not None and GEOMETRY.control_direction in live
    assert GEOMETRY.control_home_local in FOOTPRINT, (
        "the control must be on the home plate, or it tests what the arms test"
    )
    dy, dx = HEX_DIRECTIONS[GEOMETRY.control_direction]
    assert GEOMETRY.control_home_local == (STARTER_LOCAL.y + dy, STARTER_LOCAL.x + dx)


def test_the_control_is_not_one_of_the_targets() -> None:
    """Overlap would make the bracket and the measurement the same cell."""
    assert GEOMETRY.control_direction not in {t.direction for t in GEOMETRY.targets}


# --- The run's shape ---------------------------------------------------------


def test_the_run_opens_and_closes_on_a_certified_control() -> None:
    """The 2026-08-07 both-ends lock, as a property of the built list."""
    arms = build_arms(GEOMETRY)
    assert arms[0].role == "certified_control"
    assert arms[-1].role == "certified_control"
    assert sum(a.role == "certified_control" for a in arms) == 2


def test_every_target_gets_both_arms_and_nothing_else_does() -> None:
    arms = build_arms(GEOMETRY)
    ones = {a.target_name for a in arms if a.role == "arm1_owning_plate"}
    twos = {a.target_name for a in arms if a.role == "arm2_home_plate"}
    names = {t.name for t in GEOMETRY.targets}
    assert ones == twos == names
    assert len(arms) == 2 * len(names) + 3, "two arms per target, plus three controls"


def test_the_arms_carry_the_models_verdict_rather_than_a_typed_one() -> None:
    """Pre-declaration is only evidence if the declaration is the model's.

    The conjunction has no plate-set term, so it calls every target dead on any
    layout -- which is what makes a light a refutation rather than a surprise
    (observations #20). Typing "inactive" in by hand would look identical here
    and mean nothing.
    """
    arms = build_arms(GEOMETRY)
    for arm in arms:
        if arm.role in {"arm1_owning_plate", "arm2_home_plate"}:
            assert arm.predicted == "inactive"
        else:
            assert arm.predicted == "active"


def test_the_two_arms_of_a_target_are_different_courses() -> None:
    """Same world cell, different bytes -- or upload dedup collapses the pair.

    Content-hash dedup means two identical payloads return one share code and
    one render. The arms differ only in which layer the goal is addressed on, so
    this is exactly the pair most at risk of serialising the same.
    """
    arms = build_arms(GEOMETRY)
    by_target: dict[str, list[Arm]] = {}
    for arm in arms:
        if arm.target_name:
            by_target.setdefault(arm.target_name, []).append(arm)
    for name, pair in by_target.items():
        payloads = {
            serialize_course(build_arm_course(a, GEOMETRY, CERTIFIED_LAYER_HEIGHT))
            for a in pair
        }
        assert len(payloads) == 2, f"target {name}'s arms serialise identically"


def test_the_certified_controls_are_the_generators_own_output() -> None:
    """Not a rebuild of it -- the frozen quotation, byte for byte."""
    from traxgen.generator import generate_minimal

    arms = build_arms(GEOMETRY)
    expected = serialize_course(generate_minimal())
    for arm in arms:
        if arm.role == "certified_control":
            assert (
                serialize_course(build_arm_course(arm, GEOMETRY, CERTIFIED_LAYER_HEIGHT))
                == expected
            )


def test_the_two_plate_arms_really_carry_two_plates() -> None:
    """The manipulation itself. A one-plate arm would be s21 again, not arm 2."""
    from traxgen.graph import course_plate_positions

    arms = build_arms(GEOMETRY)
    for arm in arms:
        course = build_arm_course(arm, GEOMETRY, CERTIFIED_LAYER_HEIGHT)
        expected = 2 if arm.two_plate else 1
        assert len(course_plate_positions(course)) == expected, arm.label


def test_plate_positions_puts_the_completer_at_the_derived_delta() -> None:
    home, completer = plate_positions(GEOMETRY)
    assert (home.y, home.x) == (0, 0)
    assert (completer.y, completer.x) == GEOMETRY.completer_delta


# --- The verdict map ---------------------------------------------------------


def _run(**validity: str) -> list[Arm]:
    """A finished run with each arm's validity set by role/target key."""
    arms = build_arms(GEOMETRY)
    for arm in arms:
        if arm.role == "certified_control":
            arm.validity = validity.get("certified", "active")
        elif arm.role == "local_control":
            arm.validity = validity.get("local", "active")
        else:
            key = f"{'one' if arm.role == 'arm1_owning_plate' else 'two'}_{arm.target_name}"
            arm.validity = validity.get(key, validity.get(
                "one" if arm.role == "arm1_owning_plate" else "two", "inactive"
            ))
    return arms


def test_a_dark_certified_control_overrides_everything() -> None:
    """Even a run whose arms both lit. The instrument is in doubt, so there is
    no finding to report (decisions.md, 2026-08-07)."""
    verdict, _ = classify(_run(certified="inactive", one="active", two="active"))
    assert verdict == "HARNESS_SUSPECT"


def test_a_dark_local_control_aborts_before_any_arm_is_read() -> None:
    """Without it, "the family does not render" and "the model is right" are the
    same all-dark run (decisions.md, 2026-08-21)."""
    verdict, reason = classify(_run(local="inactive"))
    assert verdict == "SETUP_SUSPECT"
    assert "-0.2" in reason, "the reason must name the first thing to try"


def test_lit_on_the_owning_plate_only_means_addressing() -> None:
    verdict, _ = classify(_run(one="active", two="inactive"))
    assert verdict == "ADDRESSING_MATTERS"


def test_lit_under_both_addressings_means_plate_presence() -> None:
    verdict, _ = classify(_run(one="active", two="active"))
    assert verdict == "PLATE_PRESENCE_MATTERS"


def test_both_arms_dark_is_a_result_rather_than_a_failure() -> None:
    """The local control is what makes this branch mean something (#21)."""
    verdict, _ = classify(_run())
    assert verdict == "NEITHER_ARM_LIT"


def test_arm_two_lit_alone_is_named_rather_than_explained() -> None:
    verdict, reason = classify(_run(one="inactive", two="active"))
    assert verdict == "UNEXPECTED_ORDERING"
    assert "not theorise" in reason


def test_targets_disagreeing_is_its_own_verdict() -> None:
    """Not averaged into one of the others.

    This project has measured direction-specific behaviour before -- SW rendered
    active at an interior cell after six exhaustive sweeps called it dark -- so
    two targets behaving differently is a real possibility with a real meaning,
    and collapsing it would report a mechanism the run did not establish.
    """
    names = [t.name for t in GEOMETRY.targets]
    assert len(names) >= 2, "this test needs the run to carry more than one target"
    first, second = names[0], names[1]
    verdict, reason = classify(
        _run(
            **{
                f"one_{first}": "active",
                f"two_{first}": "inactive",
                f"one_{second}": "inactive",
                f"two_{second}": "inactive",
            }
        )
    )
    assert verdict == "TARGETS_DISAGREE"
    assert first in reason and second in reason


def test_a_missing_verdict_is_incomplete_rather_than_a_finding() -> None:
    """A hole in the run must not classify as a measurement."""
    arms = _run()
    for arm in arms:
        if arm.role == "arm1_owning_plate":
            arm.validity = None
            break
    verdict, _ = classify(arms)
    assert verdict == "INCOMPLETE"


@pytest.mark.parametrize("role", ["certified_control", "local_control"])
def test_a_control_that_never_rendered_is_not_treated_as_active(role: str) -> None:
    """`None` is not `active`. A control with no verdict is a suspect run."""
    arms = _run()
    for arm in arms:
        if arm.role == role:
            arm.validity = None
    verdict, _ = classify(arms)
    assert verdict in {"HARNESS_SUSPECT", "SETUP_SUSPECT"}


# --- The render retry ---------------------------------------------------------
#
# Added 2026-08-25 (s27) after the first run of this probe lost two of seven
# renders to the app's build-tutorial screen -- an empty editor the flow reaches
# when `loaded_track_hex` is tapped before the shared course has appeared. One
# of the two was the closing certified control, so the run was voided rather
# than believed. `traxgen.android` now recognises that screen and raises; this
# is the probe's half, which is to try again once and to record what happened
# rather than to swallow it.


class _ScriptedAdb(FakeAdb):
    """A fake whose screencap output changes per call, so a retry can succeed.

    The base fake returns one frame forever, which cannot express "refused, then
    fine" -- and that sequence is the entire behaviour under test.
    """

    def __init__(self, frames: list[bytes]) -> None:
        super().__init__()
        self._frames = frames
        self.screencaps = 0

    def __call__(self, cmd, **kwargs):  # type: ignore[no-untyped-def]
        if "screencap" in " ".join(str(part) for part in cmd):
            index = min(self.screencaps, len(self._frames) - 1)
            self.screencap_png = self._frames[index]
            self.screencaps += 1
        return super().__call__(cmd, **kwargs)


def _arm() -> Arm:
    arm = build_arms(GEOMETRY)[0]
    arm.code = "KN6F459ZR3"
    return arm


def test_a_refused_screen_is_retried_once_and_can_recover(tmp_path) -> None:
    fake = _ScriptedAdb([DEAD_FRAME, LIVE_FRAME])
    arm = _arm()

    render_arm(ctx_with(fake), arm, tmp_path)

    assert arm.render_attempts == 2
    assert arm.refused_screens == ["build_tutorial@2.262"]
    assert arm.render_error is None, "a recovered arm must not carry the first failure"
    assert arm.validity is not None


def test_two_refusals_in_a_row_stop_and_stay_recorded(tmp_path) -> None:
    """A refusal that repeats is a finding, not bad luck -- so it is not retried on."""
    fake = _ScriptedAdb([DEAD_FRAME])
    arm = _arm()

    render_arm(ctx_with(fake), arm, tmp_path)

    assert arm.render_attempts == RENDER_ATTEMPTS
    assert len(arm.refused_screens) == RENDER_ATTEMPTS
    assert arm.validity is None
    assert "RefusedScreenError" in (arm.render_error or "")


def test_a_non_refusal_harness_failure_is_not_retried(tmp_path) -> None:
    """Exception-class discipline, same as the s23 upload retry.

    A wrong foreground app will be just as wrong on a second attempt, so
    retrying spends a render to buy a slower no.
    """
    fake = FakeAdb(foreground_dump=LAUNCHER_DUMP)
    arm = _arm()

    render_arm(ctx_with(fake), arm, tmp_path)

    assert arm.render_attempts == 1
    assert arm.refused_screens == []
    assert "WrongForegroundAppError" in (arm.render_error or "")


def test_the_screenshot_is_not_named_png_png(tmp_path) -> None:
    """`render_course` appends the extension; the caller passing one produced
    `arm1_E_on_completer.png.png`, which is how the 2026-08-25 forensics started
    by hunting for files nobody had named."""
    fake = _ScriptedAdb([LIVE_FRAME])
    arm = _arm()

    render_arm(ctx_with(fake), arm, tmp_path)

    assert arm.screenshot is not None
    assert not arm.screenshot.endswith(".png.png")
    assert Path(arm.screenshot).name == f"{arm.label}_try1.png"


def test_each_attempt_writes_its_own_frame(tmp_path) -> None:
    """The refused frame must survive on disk: it is the diagnosis (s21's lesson),
    and its distance is a new observation of the refused class."""
    fake = _ScriptedAdb([DEAD_FRAME, LIVE_FRAME])
    arm = _arm()

    render_arm(ctx_with(fake), arm, tmp_path)

    written = sorted(p.name for p in tmp_path.glob("*.png"))
    assert written == [f"{arm.label}_try1.png", f"{arm.label}_try2.png"]
