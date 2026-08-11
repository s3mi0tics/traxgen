"""Offline tests for the sweep queue runner.

No emulator, no network, no real 35-second sleeps: the queue's collaborators
(`run_sweep`, `reset`, `sleep`, `out_dir_for`) are injected test doubles --
the same pattern as handing a fake transport to an HTTP client. The doubles
are scripted per rotation, so a first run and its auto-resume can behave
differently, which is exactly the behaviour under test.

Path: traxgen/tests/test_run_sweep_queue.py
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.run_sweep_queue import (
    SETTLE_SECONDS,
    RotationOutcome,
    _parse_args,
    main,
    read_verdict,
    run_queue,
)
from traxgen.android import AndroidAutomationError


def _meta(verdict: str, detail: str = "", aborted: str | None = None) -> dict[str, str | None]:
    """A minimal sweep-sidecar meta blob, as the amended sweep now writes it."""
    return {"verdict": verdict, "verdict_detail": detail, "aborted": aborted}


PARTIAL = _meta("PARTIAL_FUNCTION", "no rotation connects from W, SW, SE")
INCOMPLETE = _meta("INCOMPLETE", "not every cell was rendered")


class FakeSweep:
    """Scripted stand-in for sweep_goal_rotation.main.

    `script` maps a starter rotation to the list of (exit_code, meta) results
    its successive invocations produce, so a first run and its resume are
    scripted independently; `meta=None` simulates a sweep that died before
    writing its sidecar. Sidecars land where `out_dir_for` says, because that
    seam is what the queue actually reads.
    """

    def __init__(
        self,
        out_dir_for: Callable[[int], Path],
        script: dict[int, list[tuple[int, dict[str, str | None] | None]]],
    ) -> None:
        self.out_dir_for = out_dir_for
        self.script = {s: list(results) for s, results in script.items()}
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        s = int(argv[argv.index("--starter-rot") + 1])
        exit_code, meta = self.script[s].pop(0)
        if meta is not None:
            sidecar = self.out_dir_for(s) / "results.json"
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(json.dumps(meta))
        return exit_code


def _harness(
    tmp_path: Path, script: dict[int, list[tuple[int, dict[str, str | None] | None]]]
) -> tuple[dict, list[str], FakeSweep]:
    """Wire a queue to test doubles; returns (run_queue kwargs, event log, fake)."""

    def out_dir_for(s: int) -> Path:
        return tmp_path / f"out_s{s}"

    events: list[str] = []
    fake = FakeSweep(out_dir_for, script)

    def run_sweep(argv: list[str]) -> int:
        tag = "sweep:" + argv[argv.index("--starter-rot") + 1]
        events.append(tag + (":resume" if "--resume" in argv else ""))
        return fake(argv)

    kwargs = {
        "run_sweep": run_sweep,
        "reset": lambda: events.append("reset"),
        "sleep": lambda seconds: events.append(f"sleep:{seconds:.0f}"),
        "out_dir_for": out_dir_for,
        "queue_dir": tmp_path / "queue",
    }
    return kwargs, events, fake


# --- The happy path --------------------------------------------------------


def test_happy_path_sweeps_every_rotation_in_order(tmp_path) -> None:
    kwargs, events, _ = _harness(tmp_path, {2: [(0, PARTIAL)], 3: [(0, PARTIAL)]})
    outcomes, stopped = run_queue([2, 3], **kwargs)
    assert stopped is None
    assert [o.verdict for o in outcomes] == ["PARTIAL_FUNCTION", "PARTIAL_FUNCTION"]
    assert all(o.ok for o in outcomes)
    settle = f"sleep:{SETTLE_SECONDS:.0f}"
    assert events == ["reset", settle, "sweep:2", "reset", settle, "sweep:3"]


def test_ok_is_true_only_for_the_three_trustworthy_verdicts() -> None:
    for verdict in ("CLEAN_RULE", "LOOKUP_TABLE", "PARTIAL_FUNCTION"):
        assert RotationOutcome(0, verdict=verdict).ok
    for verdict in ("INCOMPLETE", "HARNESS_SUSPECT", "MODEL_WRONG", "AMBIGUOUS", None):
        assert not RotationOutcome(0, verdict=verdict).ok


# --- The mechanical repair -------------------------------------------------


def test_a_mechanical_hole_gets_exactly_one_auto_resume(tmp_path) -> None:
    """INCOMPLETE with no abort is the 520 shape (observations #15): the hole
    is mechanical, so its repair is too -- one re-run with --resume."""
    kwargs, events, fake = _harness(
        tmp_path, {2: [(1, INCOMPLETE), (0, PARTIAL)], 3: [(0, PARTIAL)]}
    )
    outcomes, stopped = run_queue([2, 3], **kwargs)
    assert stopped is None
    assert outcomes[0].auto_resumed
    assert outcomes[0].verdict == "PARTIAL_FUNCTION"
    resume_call = fake.calls[1]
    assert resume_call[resume_call.index("--resume") + 1].endswith("out_s2/results.json")
    assert events.count("reset") == 3  # one per launch, including the resume


def test_a_hole_that_survives_the_resume_is_recorded_and_the_queue_moves_on(tmp_path) -> None:
    """A persistent gap in s=2 says nothing about s=3, so s=3 still runs; the
    gap surfaces in the exit code instead of blocking the campaign."""
    kwargs, _, fake = _harness(
        tmp_path, {2: [(1, INCOMPLETE), (1, INCOMPLETE)], 3: [(0, PARTIAL)]}
    )
    outcomes, stopped = run_queue([2, 3], **kwargs)
    assert stopped is None
    assert outcomes[0].verdict == "INCOMPLETE" and not outcomes[0].ok
    assert outcomes[1].ok
    assert sum("--resume" in c for c in fake.calls) == 1  # exactly one, never a loop


# --- The human gates -------------------------------------------------------


@pytest.mark.parametrize("reason", ("harness", "model", "budget"))
def test_any_abort_stops_the_queue_before_the_next_rotation(tmp_path, reason: str) -> None:
    kwargs, _, fake = _harness(
        tmp_path,
        {2: [(1, _meta("INCOMPLETE", "aborted mid-run", aborted=reason))], 3: [(0, PARTIAL)]},
    )
    outcomes, stopped = run_queue([2, 3], **kwargs)
    assert stopped is not None and f"({reason})" in stopped
    assert outcomes[1].exit_code is None  # s=3 never launched
    assert len(fake.calls) == 1


def test_an_aborted_incomplete_is_never_auto_resumed(tmp_path) -> None:
    """The resume guard's direction matters (observations #17): resuming a
    harness-aborted run would spend renders on an oracle nobody trusts yet."""
    kwargs, _, fake = _harness(
        tmp_path, {2: [(1, _meta("INCOMPLETE", "control inactive", aborted="harness"))]}
    )
    outcomes, stopped = run_queue([2], **kwargs)
    assert stopped is not None
    assert not outcomes[0].auto_resumed
    assert len(fake.calls) == 1


def test_closing_bracket_drift_stops_the_queue_even_without_an_abort(tmp_path) -> None:
    """A run can complete and still end HARNESS_SUSPECT (the closing bracket
    went inactive after the last cell). Same shared-harness logic: stop."""
    kwargs, _, _ = _harness(
        tmp_path,
        {
            2: [(1, _meta("HARNESS_SUSPECT", "the closing-bracket control rendered 'inactive'"))],
            3: [(0, PARTIAL)],
        },
    )
    outcomes, stopped = run_queue([2, 3], **kwargs)
    assert stopped is not None and "s=2" in stopped
    assert outcomes[1].exit_code is None


def test_model_wrong_is_a_finding_not_a_stop(tmp_path) -> None:
    """MODEL_WRONG questions the model, not the harness -- later rotations are
    still honest measurements, so the queue keeps going and reports the gap."""
    kwargs, _, _ = _harness(
        tmp_path, {2: [(1, _meta("MODEL_WRONG", "NE active at [2, 4]"))], 3: [(0, PARTIAL)]}
    )
    outcomes, stopped = run_queue([2, 3], **kwargs)
    assert stopped is None
    assert not outcomes[0].ok
    assert outcomes[1].ok


def test_a_sweep_that_writes_no_results_stops_the_queue(tmp_path) -> None:
    kwargs, _, _ = _harness(tmp_path, {2: [(1, None)], 3: [(0, PARTIAL)]})
    outcomes, stopped = run_queue([2, 3], **kwargs)
    assert stopped is not None and "without writing results" in stopped
    assert outcomes[0].verdict is None


def test_an_automation_error_during_reset_stops_the_queue(tmp_path) -> None:
    def dead_reset() -> None:
        raise AndroidAutomationError("adb: device offline")

    kwargs, _, fake = _harness(tmp_path, {2: [(0, PARTIAL)]})
    kwargs["reset"] = dead_reset
    outcomes, stopped = run_queue([2], **kwargs)
    assert stopped is not None and "automation error" in stopped
    assert fake.calls == []  # the sweep itself never launched
    assert outcomes[0].error is not None


# --- The campaign record ---------------------------------------------------


def test_the_queue_sidecar_survives_a_mid_queue_stop(tmp_path) -> None:
    kwargs, _, _ = _harness(
        tmp_path, {2: [(1, _meta("INCOMPLETE", "slow", aborted="budget"))], 3: [(0, PARTIAL)]}
    )
    _, stopped = run_queue([2, 3], **kwargs)
    summary = json.loads((tmp_path / "queue" / "queue_results.json").read_text())
    assert summary["stopped"] == stopped
    assert summary["rotations"] == [2, 3]
    assert summary["outcomes"][0]["verdict"] == "INCOMPLETE"
    assert summary["outcomes"][1]["exit_code"] is None


def test_read_verdict_on_a_missing_sidecar_is_all_none(tmp_path) -> None:
    assert read_verdict(tmp_path / "nope.json") == (None, None, None)


# --- The CLI ---------------------------------------------------------------


def test_the_plan_rejects_a_duplicated_rotation() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["2", "2"])


def test_main_returns_zero_only_when_every_rotation_classified(tmp_path) -> None:
    kwargs, _, _ = _harness(tmp_path, {2: [(0, PARTIAL)]})
    queue_dir = kwargs.pop("queue_dir")
    assert main(["2", "--queue-dir", str(queue_dir)], **kwargs) == 0


def test_main_returns_nonzero_when_a_gap_remains(tmp_path) -> None:
    kwargs, _, _ = _harness(tmp_path, {2: [(1, INCOMPLETE), (1, INCOMPLETE)]})
    queue_dir = kwargs.pop("queue_dir")
    assert main(["2", "--queue-dir", str(queue_dir)], **kwargs) == 1
