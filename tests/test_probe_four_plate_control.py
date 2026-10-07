"""Offline tests for `scripts.probe_four_plate_control`.

The campaign has not yet produced a measurement: both 2026-10-06 (c1) runs
and the 2026-10-07 (c2) run were HARNESS_SUSPECT, and their sidecars are
committed so that claim rests on files rather than on the session's account.
These tests grade the script's builders against what the runs uploaded, and
its verdict ordering against the locked rules (D027 before D039 before the arm under test).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.probe_four_plate_control import (
    EXPECTED_CODE,
    build_arm_course,
    build_arms,
    classify,
)
from traxgen.generator import generate_multi_plate
from traxgen.graph import ConnectionStatus, start_goal_status
from traxgen.serializer import serialize_course

FIXTURES = Path(__file__).parent / "fixtures"
VOID_RUNS = sorted(FIXTURES.glob("four_plate_control_void_run*_2026-10-*.json"))


def test_the_arm_under_test_is_the_generators_course_byte_for_byte() -> None:
    (under,) = [a for a in build_arms() if a.role == "under_test"]
    assert serialize_course(build_arm_course(under)) == serialize_course(generate_multi_plate())


def test_the_run_opens_and_closes_on_the_certified_control() -> None:
    arms = build_arms()
    assert [a.role for a in arms] == [
        "certified_control",
        "local_control",
        "under_test",
        "certified_control",
    ]


def test_the_local_control_is_on_the_starters_plate_and_still_unmeasured() -> None:
    """Same board and starter as the arm under test; only the goal's plate differs."""
    (local,) = [a for a in build_arms() if a.role == "local_control"]
    assert local.goal_plate_index == 0
    assert start_goal_status(build_arm_course(local)) is ConnectionStatus.UNMEASURED


@pytest.mark.parametrize("sidecar", VOID_RUNS, ids=lambda p: p.stem)
def test_the_void_runs_rendered_these_bytes_and_measured_nothing(sidecar: Path) -> None:
    record = json.loads(sidecar.read_text())
    arms = build_arms()
    assert [a.label for a in arms] == [r["label"] for r in record["arms"]]
    for arm, recorded in zip(arms, record["arms"], strict=True):
        digest = hashlib.sha256(serialize_course(build_arm_course(arm))).hexdigest()
        assert digest == recorded["payload_sha256"], arm.label
        arm.code, arm.validity = recorded["code"], recorded["validity"]
    assert record["arms"][2]["code"] == EXPECTED_CODE
    assert classify(arms) == (record["verdict"], record["reason"])
    assert record["verdict"] == "HARNESS_SUSPECT"


def test_there_are_three_void_runs() -> None:
    assert len(VOID_RUNS) == 3


def test_c2s_dark_local_control_is_void_not_a_measurement() -> None:
    """c2's local control reads `inactive`, and that reading is not evidence.

    Its frame (committed downscaled beside the sidecar) is the Load track
    dialog with `M7RIC9EURH` typed in: the course never loaded, and the oracle
    graded a dialog. The opening control's timeout already voids the run
    (D027), so `classify` must say HARNESS_SUSPECT, never SETUP_SUSPECT.
    """
    record = json.loads((FIXTURES / "four_plate_control_void_run3_2026-10-07.json").read_text())
    assert [a["validity"] for a in record["arms"]] == [None, "inactive", "active", "active"]
    assert record["verdict"] == "HARNESS_SUSPECT"


def _arms_with(*validities: str | None, code: str = EXPECTED_CODE):
    arms = build_arms()
    for arm, validity in zip(arms, validities, strict=True):
        arm.validity = validity
        arm.code = code if arm.role == "under_test" else "XXXXXXXXXX"
    return arms


@pytest.mark.parametrize(
    ("validities", "code", "verdict"),
    [
        (("active", "active", "active", "active"), EXPECTED_CODE, "CONNECTED"),
        (("active", "active", "inactive", "active"), EXPECTED_CODE, "DISCONNECTED"),
        (("active", "inactive", "active", "active"), EXPECTED_CODE, "SETUP_SUSPECT"),
        (("active", "active", "active", "inactive"), EXPECTED_CODE, "HARNESS_SUSPECT"),
        (("inactive", "inactive", "inactive", "active"), EXPECTED_CODE, "HARNESS_SUSPECT"),
        (("active", "active", "active", "active"), "ZZZZZZZZZZ", "WRONG_COURSE"),
        (("active", "active", None, "active"), EXPECTED_CODE, "INCOMPLETE"),
    ],
)
def test_classify_puts_the_harness_and_the_setup_ahead_of_the_arm(
    validities: tuple[str | None, ...], code: str, verdict: str
) -> None:
    assert classify(_arms_with(*validities, code=code))[0] == verdict
