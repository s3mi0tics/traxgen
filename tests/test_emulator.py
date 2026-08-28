# tests/test_emulator.py
"""Offline tests for `scripts/emulator.py` -- the session's boot and kill.

Nothing here touches an emulator. Four seams make that possible, and each is a
real default overridden per call site rather than a patch: `AdbContext.runner`
(the argv adb would have run), `popen` (the launch), `run` (`pgrep`), and an
injected clock whose `sleep` advances it, so a five-minute timeout is exercised
in microseconds and deterministically.

What these tests can and cannot prove is worth stating, because the fakes are
assumptions wearing costumes (`docs/refs/testing-against-a-live-app.md`). They
prove the *logic*: that the wait is bounded, that what adb last said survives
into the timeout message, that teardown is asked for through `adb emu kill` and
then confirmed by `pgrep`, and that an interrupted boot tears down exactly once
on each of three paths. They cannot prove that a live AVD answers in these
shapes -- the `getprop` and `pgrep` shapes are the ones this project has driven
since April, and the live gate is the first real boot.
"""

from __future__ import annotations

import signal
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts.emulator import (
    DEFAULT_AVD,
    QEMU_PATTERN,
    AlreadyRunningError,
    BootTimeoutError,
    EmulatorNotFoundError,
    TeardownGuard,
    boot,
    guarded,
    kill_emulator,
    resolve_emulator_binary,
    running_emulator_pids,
    spawn_emulator,
    wait_for_boot,
)
from tests.test_android_foreground import GRAVITRAX_DUMP
from traxgen.android import AdbContext

# --- fakes -----------------------------------------------------------------


class FakeClock:
    """A monotonic clock that only moves when something sleeps on it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class ScriptedAdb:
    """Records argv and scripts one answer per `getprop` call.

    `boot_answers` entries are either a string (stdout) or a `(returncode,
    stderr)` pair, which lets a test drive the real `_run_adb` into raising
    rather than faking the exception itself. The last entry repeats forever.
    """

    def __init__(
        self,
        boot_answers: Sequence[object] = ("1",),
        *,
        emu_kill: tuple[int, str] | None = None,
    ) -> None:
        self.boot_answers = list(boot_answers)
        self.emu_kill = emu_kill
        self.calls: list[list[str]] = []
        self._boot_index = 0

    def __call__(self, cmd: Sequence[str], **_: object) -> subprocess.CompletedProcess:
        argv = [str(part) for part in cmd]
        self.calls.append(argv)
        joined = " ".join(argv)

        if "sys.boot_completed" in joined:
            index = min(self._boot_index, len(self.boot_answers) - 1)
            self._boot_index += 1
            answer = self.boot_answers[index]
            if isinstance(answer, tuple):
                code, stderr = answer
                return subprocess.CompletedProcess(argv, code, "", stderr)
            return subprocess.CompletedProcess(argv, 0, f"{answer}\n", "")

        if argv[1:3] == ["emu", "kill"]:
            if self.emu_kill is not None:
                code, stderr = self.emu_kill
                return subprocess.CompletedProcess(argv, code, "", stderr)
            return subprocess.CompletedProcess(argv, 0, "", "")

        if argv[1:2] == ["devices"]:
            return subprocess.CompletedProcess(
                argv, 0, "List of devices attached\nemulator-5554\tdevice\n\n", ""
            )
        if "dumpsys window" in joined:
            return subprocess.CompletedProcess(argv, 0, GRAVITRAX_DUMP, "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def ran(self, needle: str) -> bool:
        return any(needle in " ".join(argv) for argv in self.calls)


class FakePgrep:
    """`subprocess.run` stand-in for `pgrep -f qemu-system`.

    Scripted as a sequence of pid-tuples, one per call, last repeating -- so a
    test can say "up, up, gone" without any timing.
    """

    def __init__(self, sequence: Sequence[Sequence[str]] = ((),)) -> None:
        self.sequence = [tuple(item) for item in sequence]
        self.calls: list[list[str]] = []
        self._index = 0

    def __call__(self, cmd: Sequence[str], **_: object) -> subprocess.CompletedProcess:
        argv = [str(part) for part in cmd]
        self.calls.append(argv)
        pids = self.sequence[min(self._index, len(self.sequence) - 1)]
        self._index += 1
        return subprocess.CompletedProcess(argv, 0 if pids else 1, "\n".join(pids), "")


class FakePopen:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, argv: Sequence[str], **kwargs: object) -> object:
        self.calls.append(([str(part) for part in argv], dict(kwargs)))
        return object()


def ctx_with(adb: ScriptedAdb) -> AdbContext:
    return AdbContext(adb_path=Path("/nonexistent/adb"), runner=adb, sleep=lambda _s: None)


def make_sdk(tmp_path: Path) -> Path:
    binary = tmp_path / "emulator" / "emulator"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n")
    return tmp_path


# --- resolving the binary (environment.md's $ANDROID_HOME gotcha) ----------


def test_resolves_the_emulator_under_an_explicit_android_home(tmp_path: Path) -> None:
    home = make_sdk(tmp_path)
    assert resolve_emulator_binary(home) == home / "emulator" / "emulator"


def test_missing_emulator_names_the_path_it_looked_at(tmp_path: Path) -> None:
    with pytest.raises(EmulatorNotFoundError) as caught:
        resolve_emulator_binary(tmp_path)
    assert str(tmp_path / "emulator" / "emulator") in str(caught.value)


def test_android_home_env_var_is_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole of the gotcha: a bare `$ANDROID_HOME` expands to nothing in a
    default shell, so resolution has to read the variable itself and fall back."""
    home = make_sdk(tmp_path)
    monkeypatch.setenv("ANDROID_HOME", str(home))
    assert resolve_emulator_binary() == home / "emulator" / "emulator"


# --- pgrep -----------------------------------------------------------------


def test_no_match_is_data_not_an_error() -> None:
    assert running_emulator_pids(run=FakePgrep([()])) == ()


def test_reports_every_running_pid() -> None:
    pgrep = FakePgrep([("501", "502")])
    assert running_emulator_pids(run=pgrep) == ("501", "502")
    assert pgrep.calls[0] == ["pgrep", "-f", QEMU_PATTERN]


# --- launching -------------------------------------------------------------


def test_launch_is_cold_detached_and_truncates_the_log(tmp_path: Path) -> None:
    log = tmp_path / "emulator.log"
    log.write_text("bad color buffer handle\n" * 5)
    popen = FakePopen()

    spawn_emulator(Path("/sdk/emulator/emulator"), DEFAULT_AVD, log, popen=popen)

    argv, kwargs = popen.calls[0]
    assert argv == ["/sdk/emulator/emulator", "-avd", DEFAULT_AVD, "-no-snapshot-load"]
    assert kwargs["start_new_session"] is True
    # preflight's "zero graphics errors *since boot*" is only honest if the log
    # starts empty; five stale hits would otherwise fail the next boot's check.
    assert log.read_text() == ""


# --- the bounded wait (observations #25) -----------------------------------


def test_wait_returns_once_boot_completed_reads_one() -> None:
    clock = FakeClock()
    adb = ScriptedAdb(["", "", "1"])
    elapsed = wait_for_boot(ctx_with(adb), interval=2.0, clock=clock, sleep=clock.sleep)
    assert elapsed == pytest.approx(4.0)
    assert clock.slept == [2.0, 2.0]


def test_a_zero_is_not_a_completed_boot() -> None:
    """`getprop` answers `0` while the device is coming up, not just an empty
    string, so the predicate has to be equality with `1` rather than truthiness."""
    clock = FakeClock()
    adb = ScriptedAdb(["0", "0", "1"])
    # two sleeps, not three: the third poll reads "1" and returns without sleeping
    assert wait_for_boot(ctx_with(adb), interval=1.0, clock=clock, sleep=clock.sleep) == 2.0


def test_adb_failing_while_the_device_comes_up_is_not_fatal() -> None:
    clock = FakeClock()
    adb = ScriptedAdb([(1, "error: no devices/emulators found"), "1"])
    assert wait_for_boot(ctx_with(adb), interval=1.0, clock=clock, sleep=clock.sleep) > 0


def test_the_wait_is_bounded() -> None:
    clock = FakeClock()
    with pytest.raises(BootTimeoutError):
        wait_for_boot(ctx_with(ScriptedAdb([""])), timeout=10.0, interval=2.0,
                      clock=clock, sleep=clock.sleep)


def test_the_timeout_message_carries_what_adb_last_said() -> None:
    """#25 in one assertion: the loop that spun forever had `2>/dev/null` around
    a bare `adb`, so `command not found` -- the one line that named the cause --
    was discarded. Whatever adb last said has to survive into the failure."""
    clock = FakeClock()
    adb = ScriptedAdb([(127, "adb: command not found")])
    with pytest.raises(BootTimeoutError) as caught:
        wait_for_boot(ctx_with(adb), timeout=4.0, interval=2.0, clock=clock, sleep=clock.sleep)
    assert "command not found" in str(caught.value)


def test_an_unfinished_boot_reports_the_property_it_read() -> None:
    clock = FakeClock()
    with pytest.raises(BootTimeoutError) as caught:
        wait_for_boot(ctx_with(ScriptedAdb([""])), timeout=4.0, interval=2.0,
                      clock=clock, sleep=clock.sleep)
    assert "sys.boot_completed" in str(caught.value)


# --- the three-layer teardown (#32 rule (d)) -------------------------------


def test_the_guard_fires_once_however_many_layers_reach_it() -> None:
    fired: list[int] = []
    guard = TeardownGuard(lambda: fired.append(1))
    assert guard.fire() is True
    assert guard.fire() is False
    assert fired == [1]


def test_a_disarmed_guard_leaves_the_emulator_up() -> None:
    fired: list[int] = []
    guard = TeardownGuard(lambda: fired.append(1))
    guard.disarm()
    assert guard.fire() is False
    assert fired == []


class FakeSignals:
    """Captures handler installation so the SIGTERM path can be driven directly."""

    def __init__(self) -> None:
        self.installed: dict[int, object] = {}
        self.original = {signal.SIGINT: "orig-int", signal.SIGTERM: "orig-term"}
        self.history: list[tuple[int, object]] = []
        self.raised: list[tuple[int, object]] = []
        self.registered: list[object] = []
        self.unregistered: list[object] = []

    def get(self, signum: int) -> object:
        return self.original[signum]

    def set(self, signum: int, handler: object) -> object:
        self.installed[signum] = handler
        self.history.append((signum, handler))
        return handler

    def resignal(self, signum: int) -> None:
        # snapshot the disposition *at raise time* -- the ordering is the claim
        self.raised.append((signum, self.installed.get(signum)))


def run_guarded(signals: FakeSignals, teardown, body) -> None:
    with guarded(
        teardown,
        set_handler=signals.set,
        get_handler=signals.get,
        register_atexit=signals.registered.append,
        unregister_atexit=signals.unregistered.append,
        resignal=signals.resignal,
    ) as guard:
        body(guard, signals)


def test_a_completed_boot_restores_the_handlers_and_leaves_nothing_registered() -> None:
    signals, fired = FakeSignals(), []
    run_guarded(signals, lambda: fired.append(1), lambda guard, _s: guard.disarm())
    assert fired == []
    assert signals.installed[signal.SIGTERM] == "orig-term"
    assert signals.installed[signal.SIGINT] == "orig-int"
    assert signals.unregistered == signals.registered


def test_an_exception_in_the_block_tears_down_and_still_propagates() -> None:
    signals, fired = FakeSignals(), []

    def body(_guard, _signals):
        raise BootTimeoutError("bounded out")

    with pytest.raises(BootTimeoutError):
        run_guarded(signals, lambda: fired.append(1), body)
    assert fired == [1]


def test_sigterm_tears_down_where_no_finally_would_have_run() -> None:
    """The layer that earns the whole shape. SIGTERM never becomes an exception,
    so a `try/finally` around the wait would not run at all -- the handler is the
    only thing between an interrupt and a 2 GB orphan."""
    signals, fired = FakeSignals(), []

    def body(_guard, live: FakeSignals) -> None:
        handler = live.installed[signal.SIGTERM]
        handler(signal.SIGTERM, None)

    run_guarded(signals, lambda: fired.append(1), body)
    assert fired == [1]
    # restored *before* the signal is re-raised, so the process dies of what it
    # was sent rather than re-entering this handler or exiting 0
    assert signals.raised == [(signal.SIGTERM, "orig-term")]


def test_the_signal_and_exception_layers_do_not_tear_down_twice() -> None:
    signals, fired = FakeSignals(), []

    def body(_guard, live: FakeSignals) -> None:
        live.installed[signal.SIGINT](signal.SIGINT, None)
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_guarded(signals, lambda: fired.append(1), body)
    assert fired == [1]


# --- teardown --------------------------------------------------------------


def test_nothing_running_asks_adb_for_nothing() -> None:
    adb = ScriptedAdb()
    outcome = kill_emulator(ctx_with(adb), run=FakePgrep([()]))
    assert (outcome.requested, outcome.died) == (False, True)
    assert not adb.ran("emu kill")


def test_teardown_asks_then_confirms_the_process_died() -> None:
    clock, adb = FakeClock(), ScriptedAdb()
    pgrep = FakePgrep([("501",), ("501",), ()])
    outcome = kill_emulator(ctx_with(adb), clock=clock, sleep=clock.sleep, run=pgrep, interval=1.0)
    assert outcome.died is True
    assert adb.ran("emu kill")


def test_teardown_never_signals_qemu_directly() -> None:
    """Killing `qemu-system` directly can strand the AVD's lock file and make the
    *next* boot fail as something unrelated, so the only route out is `emu kill`."""
    clock, adb = FakeClock(), ScriptedAdb()
    pgrep = FakePgrep([("501",), ()])
    kill_emulator(ctx_with(adb), clock=clock, sleep=clock.sleep, run=pgrep, interval=1.0)
    assert all(argv[0] == "pgrep" for argv in pgrep.calls)
    assert not any(argv[1:2] == ["kill"] for argv in adb.calls)


def test_a_failed_emu_kill_is_reported_and_waited_out() -> None:
    """`adb emu kill` failing and the emulator staying up are different claims,
    and only pgrep settles the second one."""
    clock = FakeClock()
    adb = ScriptedAdb(emu_kill=(1, "error: could not connect to TCP port 5554"))
    pgrep = FakePgrep([("501",), ()])
    outcome = kill_emulator(ctx_with(adb), clock=clock, sleep=clock.sleep, run=pgrep, interval=1.0)
    assert outcome.died is True
    assert "adb emu kill failed" in outcome.detail


def test_a_survivor_past_the_bound_fails_and_names_it() -> None:
    clock = FakeClock()
    pgrep = FakePgrep([("501",)])
    outcome = kill_emulator(
        ctx_with(ScriptedAdb()), timeout=5.0, interval=1.0,
        clock=clock, sleep=clock.sleep, run=pgrep,
    )
    assert outcome.died is False
    assert outcome.survivors == ("501",)
    assert "FAIL" in outcome.line()


# --- boot, end to end offline ---------------------------------------------


def boot_offline(tmp_path: Path, adb: ScriptedAdb, pgrep: FakePgrep, popen: FakePopen) -> list[str]:
    printed: list[str] = []
    clock = FakeClock()
    boot(
        android_home=make_sdk(tmp_path),
        log_path=tmp_path / "emulator.log",
        interval=1.0,
        ctx=ctx_with(adb),
        out=printed.append,
        popen=popen,
        run=pgrep,
        clock=clock,
        sleep=clock.sleep,
    )
    return printed


def test_boot_refuses_when_something_is_already_running(tmp_path: Path) -> None:
    """A cold boot means nothing is up. Booting a second AVD on top of a live one
    is how a session ends up measuring a machine it did not start -- and it
    breaks the graphics-error count that makes a later nonzero value mean
    something."""
    popen = FakePopen()
    with pytest.raises(AlreadyRunningError):
        boot(
            android_home=make_sdk(tmp_path),
            log_path=tmp_path / "emulator.log",
            ctx=ctx_with(ScriptedAdb()),
            out=lambda _line: None,
            popen=popen,
            run=FakePgrep([("501",)]),
        )
    assert popen.calls == []


def test_boot_launches_waits_and_reports_the_measured_time(tmp_path: Path) -> None:
    popen = FakePopen()
    printed = boot_offline(tmp_path, ScriptedAdb(["", "", "1"]), FakePgrep([()]), popen)
    assert popen.calls, "the emulator was never launched"
    assert any("boot_completed in 2.0s" in line for line in printed), printed
    # the guard is disarmed on success; a boot that tore down what it just
    # booted would still print a plausible-looking success above this line
    assert not any("tearing down" in line for line in printed), printed


def test_boot_grades_the_device_and_says_which_checks_it_did_not_run(tmp_path: Path) -> None:
    """The scope statement is a claim, so it gets a test. Right after a cold boot
    the launcher is in front, so `app_in_foreground` and `screencap_geometry`
    would measure the launcher -- they are campaign-time checks, and the output
    has to say so rather than let three passes read as five."""
    printed = boot_offline(tmp_path, ScriptedAdb(["1"]), FakePgrep([()]), FakePopen())
    graded = [line for line in printed if line.startswith(("PASS ", "FAIL "))]
    assert len(graded) == 3
    names = " ".join(graded)
    assert "device_attached" in names and "boot_complete" in names and "graphics_errors" in names
    assert "app_in_foreground" not in names and "screencap_geometry" not in names
    assert any("campaign-time" in line for line in printed)


def test_an_interrupted_boot_tears_down_what_it_launched(tmp_path: Path) -> None:
    """The reason the guard exists. The emulator is spawned detached and outlives
    this process, so a wait that never completes must not leave it running."""
    clock = FakeClock()
    adb = ScriptedAdb([""])
    pgrep = FakePgrep([(), ("501",), ()])
    printed: list[str] = []
    with pytest.raises(BootTimeoutError):
        boot(
            android_home=make_sdk(tmp_path),
            log_path=tmp_path / "emulator.log",
            timeout=4.0,
            interval=2.0,
            ctx=ctx_with(adb),
            out=printed.append,
            popen=FakePopen(),
            run=pgrep,
            clock=clock,
            sleep=clock.sleep,
        )
    assert adb.ran("emu kill"), printed
    assert any("tearing down" in line for line in printed)
