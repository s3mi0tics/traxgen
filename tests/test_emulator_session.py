# tests/test_emulator_session.py
"""Offline tests for `scripts.emulator.session` -- one cold emulator per run.

`session` is a context manager, and what a context manager promises is what
happens on the way *out*: the teardown runs on a clean exit, on an exception
and on a Ctrl-C, or it is not a lifecycle. These tests hand it a fake `boot_fn`,
`kill_fn` and `evidence_fn` that record the order they were called in, and read
the promise back from that record. Playwright's fixture teardown is the same
contract (`page` is closed after the test whatever the test did); here the
resource is an emulator process instead of a browser page.

A *failed* run makes one more promise on the way out (s38, plan #20): the
phone's memory report and log are saved before the kill wipes them. Order is
the whole point, so the same record reads it: `evidence` has to land between
the failure and the last `kill`. The capture itself, `save_device_evidence`, is
driven by `Phone`, a fake adb that answers in bytes, and writes into pytest's
`tmp_path` -- a fresh empty directory per test, much as Playwright gives each
test a fresh browser context, so no test can see another's files.

Nothing here touches adb or qemu. The real `boot` and `kill_emulator` are
tested in `test_emulator.py`; this file tests the wrapper's ordering, its
refusals and the evidence it keeps, which is all the wrapper adds.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from scripts.emulator import EmulatorLifecycleError, KillOutcome, save_device_evidence, session
from scripts.preflight import Check
from traxgen.android import AdbContext

CTX = AdbContext(adb_path=Path("/nonexistent/adb"))
# Never written: wherever this is passed, the recording fake stands in for the capture.
EVIDENCE_DIR = Path("/nonexistent/evidence")


def outcome(died: bool = True, detail: str = "no qemu-system process was running") -> KillOutcome:
    return KillOutcome(
        requested=not died or detail != "no qemu-system process was running",
        died=died,
        elapsed=0.0,
        survivors=() if died else ("4242",),
        detail=detail,
    )


class Lifecycle:
    """Records every boot, kill and evidence capture in the order they happened."""

    def __init__(
        self,
        *,
        kills: list[KillOutcome] | None = None,
        boot_ok: bool = True,
        evidence_error: Exception | None = None,
    ) -> None:
        self.events: list[str] = []
        self.kills = list(kills or [])
        self.boot_ok = boot_ok
        self.evidence_error = evidence_error
        self.reasons: list[str] = []
        self.lines: list[str] = []

    def kill(self, ctx: AdbContext, **_: object) -> KillOutcome:
        self.events.append("kill")
        return self.kills.pop(0) if self.kills else outcome()

    def boot(self, **kwargs: object) -> list[Check]:
        self.events.append("boot")
        return [Check("device_attached", self.boot_ok, "emulator-5554 device")]

    def evidence(self, ctx: AdbContext, directory: Path, *, reason: str) -> Path:
        self.events.append("evidence")
        self.reasons.append(reason)
        if self.evidence_error is not None:
            raise self.evidence_error
        return directory / "20260921-143012.txt"

    def out(self, line: str) -> None:
        self.lines.append(line)


def run_session(life: Lifecycle):
    return session(
        ctx=CTX,
        out=life.out,
        boot_fn=life.boot,
        kill_fn=life.kill,
        evidence_dir=EVIDENCE_DIR,
        evidence_fn=life.evidence,
    )


def test_kill_boot_body_kill_on_a_clean_run() -> None:
    """The exact list is also the no-evidence check: a clean run saves nothing."""
    life = Lifecycle()
    with run_session(life) as ctx:
        life.events.append("body")
        assert ctx is CTX
    assert life.events == ["kill", "boot", "body", "kill"]


def test_teardown_runs_when_the_body_raises_and_the_error_propagates() -> None:
    """The evidence comes before the teardown kill, which would wipe the phone's log."""
    life = Lifecycle()
    with pytest.raises(RuntimeError, match="render blew up"), run_session(life):
        raise RuntimeError("render blew up")
    assert life.events == ["kill", "boot", "evidence", "kill"]


def test_teardown_runs_on_keyboard_interrupt() -> None:
    """A Ctrl-C is someone stopping the run, not a failure to explain: straight to the kill."""
    life = Lifecycle()
    with pytest.raises(KeyboardInterrupt), run_session(life):
        raise KeyboardInterrupt
    assert life.events == ["kill", "boot", "kill"]


def test_refuses_to_boot_over_an_emulator_it_could_not_kill() -> None:
    life = Lifecycle(kills=[outcome(died=False, detail="adb emu kill accepted")])
    with pytest.raises(EmulatorLifecycleError, match="refusing to boot"), run_session(life):
        life.events.append("body")
    assert life.events == ["kill"]


def test_failed_device_checks_tear_down_and_raise_before_the_body() -> None:
    life = Lifecycle(boot_ok=False)
    with pytest.raises(EmulatorLifecycleError, match="device checks failed"), run_session(life):
        life.events.append("body")
    assert life.events == ["kill", "boot", "evidence", "kill"]
    failing = Check("device_attached", False, "emulator-5554 device").line()
    summary = "device checks failed after cold boot: ['device_attached']"
    assert life.reasons == [f"{summary}\n  {failing}"]


def test_every_kill_outcome_is_reported_on_out() -> None:
    life = Lifecycle()
    with run_session(life):
        pass
    assert sum("emulator_down" in line for line in life.lines) == 2


def test_the_evidence_names_the_error_and_its_notes_and_the_path_is_printed() -> None:
    life = Lifecycle()
    error = RuntimeError("render blew up")
    error.add_note("main-menu wait: 3 frameless screencaps in a row")
    with pytest.raises(RuntimeError), run_session(life):
        raise error
    assert life.reasons == [
        "RuntimeError: render blew up\n  main-menu wait: 3 frameless screencaps in a row"
    ]
    saved = life.lines.index(f"device evidence saved: {EVIDENCE_DIR / '20260921-143012.txt'}")
    assert "emulator_down" in life.lines[saved + 1]


def test_a_capture_that_fails_neither_skips_the_kill_nor_replaces_the_error() -> None:
    life = Lifecycle(evidence_error=OSError("No space left on device"))
    with pytest.raises(RuntimeError, match="render blew up"), run_session(life):
        raise RuntimeError("render blew up")
    assert life.events == ["kill", "boot", "evidence", "kill"]
    assert "device evidence NOT saved: OSError: No space left on device" in life.lines


# --- the capture itself ------------------------------------------------------

STAMP = datetime(2026, 9, 21, 14, 30, 12)
MEMINFO = b"Applications Memory Usage (in Kilobytes):\nTotal RAM: 2,014,524K (status normal)\n"
LOGCAT = b"09-21 14:30:05.123   612   612 I lowmemorykiller: Kill 'com.ravensburger.gravitrax'\n"


class Phone:
    """Stands in for `subprocess.run` behind `AdbContext.runner`, answering as a phone would.

    The same kind of fake as `FakeAdb` in `test_android_foreground.py`: it records
    the argv the code really built and answers from a script, rather than being
    told in advance which calls to expect. It answers in bytes, because the
    capture reads through `_run_adb_binary`. `refuse` makes adb exit 1 with the
    given stderr (the phone said no); `raise_on` makes the call itself raise (the
    Mac could not start adb, or someone pressed Ctrl-C).
    """

    def __init__(
        self,
        *,
        refuse: dict[str, str] | None = None,
        raise_on: dict[str, BaseException] | None = None,
    ) -> None:
        self.refuse = refuse or {}
        self.raise_on = raise_on or {}
        self.calls: list[list[str]] = []

    def __call__(self, cmd: Sequence[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        argv = [str(part) for part in cmd]
        self.calls.append(argv)
        joined = " ".join(argv[1:])
        for needle, exc in self.raise_on.items():
            if needle in joined:
                raise exc
        for needle, stderr in self.refuse.items():
            if needle in joined:
                return subprocess.CompletedProcess(argv, 1, b"", stderr.encode())
        answer = MEMINFO if "meminfo" in joined else LOGCAT if "logcat" in joined else b""
        return subprocess.CompletedProcess(argv, 0, answer, b"")

    def index_of(self, word: str) -> int:
        """Position of the first recorded call with `word` as one of its arguments."""
        return next(i for i, argv in enumerate(self.calls) if word in argv)


def phone_ctx(phone: Phone) -> AdbContext:
    return AdbContext(adb_path=Path("/nonexistent/adb"), runner=phone)


def capture(phone: Phone, directory: Path) -> Path:
    return save_device_evidence(
        phone_ctx(phone), directory, reason="RuntimeError: render blew up", now=lambda: STAMP
    )


def test_the_file_holds_the_reason_then_memory_then_the_log(tmp_path: Path) -> None:
    path = capture(Phone(), tmp_path / "device_evidence")
    assert path == tmp_path / "device_evidence" / "20260921-143012.txt"
    text = path.read_text()
    assert text.startswith(
        "device evidence, 2026-09-21 14:30:12\nwhy: RuntimeError: render blew up\n"
    )
    assert text.index("Total RAM") < text.index("lowmemorykiller")


def test_it_waits_for_the_connection_then_reads_memory_then_the_whole_log(tmp_path: Path) -> None:
    """s37's third failure was adb resetting mid-run; asked at that moment, a phone refuses."""
    phone = Phone()
    capture(phone, tmp_path)
    assert phone.index_of("wait-for-device") < phone.index_of("meminfo") < phone.index_of("logcat")
    logcat = phone.calls[phone.index_of("logcat")]
    assert "-d" in logcat  # dump and exit: without it logcat streams until the timeout
    assert logcat[logcat.index("-b") + 1] == "all"  # `events` is where `am_kill` is written


@pytest.mark.parametrize(
    ("phone", "written", "still_read"),
    [
        (
            Phone(refuse={"meminfo": "error: device still authorizing"}),
            "stderr: error: device still authorizing",
            "lowmemorykiller",
        ),
        (
            Phone(raise_on={"logcat": OSError(12, "Cannot allocate memory")}),
            "FAILED: [Errno 12] Cannot allocate memory",
            "Total RAM",
        ),
    ],
    ids=["the-phone-refuses", "the-mac-cannot-start-adb"],
)
def test_a_failed_command_is_written_down_and_the_capture_goes_on(
    tmp_path: Path, phone: Phone, written: str, still_read: str
) -> None:
    text = capture(phone, tmp_path).read_text()
    assert "FAILED: " in text
    assert written in text
    assert still_read in text


def test_a_capture_cut_short_keeps_what_it_had_read(tmp_path: Path) -> None:
    with pytest.raises(KeyboardInterrupt):
        capture(Phone(raise_on={"logcat": KeyboardInterrupt()}), tmp_path)
    assert "Total RAM" in (tmp_path / "20260921-143012.txt").read_text()


def test_a_failed_run_leaves_the_file_behind_before_the_teardown_kill(tmp_path: Path) -> None:
    """The whole path offline: `session`'s own default capture, a phone that answers,
    a body that fails. The live version of this test is a failed render on the Mac."""
    life = Lifecycle()
    files_at_each_kill: list[int] = []

    def kill(ctx: AdbContext, **kwargs: object) -> KillOutcome:
        files_at_each_kill.append(len(list(tmp_path.iterdir())))
        return life.kill(ctx, **kwargs)

    run = session(
        ctx=phone_ctx(Phone()), out=life.out, boot_fn=life.boot, kill_fn=kill, evidence_dir=tmp_path
    )
    with pytest.raises(RuntimeError), run:
        raise RuntimeError("render blew up")
    assert files_at_each_kill == [0, 1]
    (saved,) = tmp_path.iterdir()
    text = saved.read_text()
    assert "why: RuntimeError: render blew up" in text
    assert "Total RAM" in text
    assert "lowmemorykiller" in text
    assert f"device evidence saved: {saved}" in life.lines
