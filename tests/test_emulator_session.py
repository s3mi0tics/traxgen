# tests/test_emulator_session.py
"""Offline tests for `scripts.emulator.session` -- one cold emulator per run.

`session` is a context manager, and what a context manager promises is what
happens on the way *out*: the teardown runs on a clean exit, on an exception
and on a Ctrl-C, or it is not a lifecycle. These tests hand it a fake `boot_fn`
and `kill_fn` that record the order they were called in, and read the promise
back from that record. Playwright's fixture teardown is the same contract
(`page` is closed after the test whatever the test did); here the resource is
an emulator process instead of a browser page.

Nothing here touches adb or qemu. The real `boot` and `kill_emulator` are
tested in `test_emulator.py`; this file tests the wrapper's ordering and its
refusals, which is all the wrapper adds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.emulator import EmulatorLifecycleError, KillOutcome, session
from scripts.preflight import Check
from traxgen.android import AdbContext

CTX = AdbContext(adb_path=Path("/nonexistent/adb"))


def outcome(died: bool = True, detail: str = "no qemu-system process was running") -> KillOutcome:
    return KillOutcome(
        requested=not died or detail != "no qemu-system process was running",
        died=died,
        elapsed=0.0,
        survivors=() if died else ("4242",),
        detail=detail,
    )


class Lifecycle:
    """Records every boot and kill in the order they happened."""

    def __init__(self, *, kills: list[KillOutcome] | None = None, boot_ok: bool = True) -> None:
        self.events: list[str] = []
        self.kills = list(kills or [])
        self.boot_ok = boot_ok
        self.lines: list[str] = []

    def kill(self, ctx: AdbContext, **_: object) -> KillOutcome:
        self.events.append("kill")
        return self.kills.pop(0) if self.kills else outcome()

    def boot(self, **kwargs: object) -> list[Check]:
        self.events.append("boot")
        return [Check("device_attached", self.boot_ok, "emulator-5554 device")]

    def out(self, line: str) -> None:
        self.lines.append(line)


def run_session(life: Lifecycle):
    return session(ctx=CTX, out=life.out, boot_fn=life.boot, kill_fn=life.kill)


def test_kill_boot_body_kill_on_a_clean_run() -> None:
    life = Lifecycle()
    with run_session(life) as ctx:
        life.events.append("body")
        assert ctx is CTX
    assert life.events == ["kill", "boot", "body", "kill"]


def test_teardown_runs_when_the_body_raises_and_the_error_propagates() -> None:
    life = Lifecycle()
    with pytest.raises(RuntimeError, match="render blew up"), run_session(life):
        raise RuntimeError("render blew up")
    assert life.events == ["kill", "boot", "kill"]


def test_teardown_runs_on_keyboard_interrupt() -> None:
    life = Lifecycle()
    with pytest.raises(KeyboardInterrupt), run_session(life):
        raise KeyboardInterrupt
    assert life.events[-1] == "kill"


def test_refuses_to_boot_over_an_emulator_it_could_not_kill() -> None:
    life = Lifecycle(kills=[outcome(died=False, detail="adb emu kill accepted")])
    with pytest.raises(EmulatorLifecycleError, match="refusing to boot"), run_session(life):
        life.events.append("body")
    assert life.events == ["kill"]


def test_failed_device_checks_tear_down_and_raise_before_the_body() -> None:
    life = Lifecycle(boot_ok=False)
    with pytest.raises(EmulatorLifecycleError, match="device checks failed"), run_session(life):
        life.events.append("body")
    assert life.events == ["kill", "boot", "kill"]


def test_every_kill_outcome_is_reported_on_out() -> None:
    life = Lifecycle()
    with run_session(life):
        pass
    assert sum("emulator_down" in line for line in life.lines) == 2
