"""Tests for the foreground guard: does the harness know what's in front of it?

All offline. No emulator, no renders. The adb layer is replaced by a fake that
records the argv of every invocation and answers from a scripted table, which
is what makes the *ordering* assertions below possible -- several of these
tests care not just that the guard runs but that it runs **before the first
tap**, and a fake that only returned canned strings could not tell the
difference.

WHY THIS MODULE EXISTS (2026-08-21, s21). `render_course()` opens by tapping a
blind coordinate. It never launched the app, and `assert_emulator_ready()`
checks that the *emulator* is booted -- not what is in front of it. Against a
booted emulator with GraviTrax closed, every tap landed on the Android
launcher and the play-button oracle sampled wallpaper. Dark wallpaper sits in
the same brightness range as a real render, so the near-white frame guard
passed it, and the harness returned a confident `inactive`.

That is the worst possible direction for that run, because the probe it was
serving *predicted* its discriminating cells dark: a harness aimed at the
launcher returns exactly the all-inactive result that reads as a flawless
confirmation of the hypothesis under test (observations #17, third firing).

THE FIXTURES ARE REAL. Every `dumpsys_*.txt` here is a literal capture from
AVD `traxgen_m6c` (API 34) taken 2026-08-23 -- the launcher one in precisely
the state that fooled the s21 run. They are not reconstructions of the format.
A parser tested against an invented sample grades the author's memory of adb
against itself, which is observation #12's shape and is how a green suite ends
up meaning nothing.

WHAT THIS GUARD DOES NOT DO. `_t3s` and `_t33s` are the same app sampled ~3s
after launch (splash) and again after a 30s settle (main menu). They are
byte-identical, which `test_splash_and_main_menu_are_indistinguishable` below
asserts rather than asking you to take on trust. So this guard can answer "is
GraviTrax in front" and cannot answer "which screen is showing" -- the Unity
surface is opaque here just as it is to `uiautomator`.

The s21 failure (tapping the launcher) is closed. The 2026-08-07 failure
(tapping a splash) is not, and plan.md's sequenced item 3 does not close it
either: that item wires in `wait_for_node`, which reads uiautomator and is
blind to this same surface. A pixel-stability predicate through `wait_until`
is the route plan.md's triggered review already names.

Path: traxgen/tests/test_android_foreground.py
"""

from __future__ import annotations

import io
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from traxgen.android import (
    DEFAULT_PACKAGE,
    AdbContext,
    ForegroundUnreadableError,
    WrongForegroundAppError,
    assert_app_in_foreground,
    parse_foreground_package,
    read_foreground_package,
    render_course,
)

FIXTURES = Path(__file__).parent / "fixtures"
LAUNCHER_DUMP = (FIXTURES / "dumpsys_window_launcher.txt").read_text()
SPLASH_DUMP = (FIXTURES / "dumpsys_window_gravitrax_t3s.txt").read_text()
MENU_DUMP = (FIXTURES / "dumpsys_window_gravitrax_t33s.txt").read_text()
GRAVITRAX_DUMP = MENU_DUMP
ACTIVITIES_LAUNCHER_DUMP = (FIXTURES / "dumpsys_activities_launcher.txt").read_text()

LAUNCHER_PKG = "com.google.android.apps.nexuslauncher"

# A real PNG at the AVD's frame geometry. It was a 1x1 until 2026-08-25, which
# was fine while nothing looked at the pixels and stopped being fine when the
# refused-screen guard started resampling the frame to a reference's size -- a
# 1x1 is smaller than any reference, which the guard refuses outright. Device
# geometry rather than "big enough" so these tests exercise the same downscale
# a live render does. Solid fill: these tests are about the foreground checks,
# and the only property they need from the frame is that it is not one of the
# refused screens. A test that cares about pixel content must build its own
# (see tests/test_refused_screens.py, and observations #26 on solid fills).
def _solid_png(width: int, height: int, colour: tuple[int, int, int]) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_FRAME = _solid_png(2400, 1080, (40, 44, 52))


# --- The fake adb ----------------------------------------------------------


class FakeAdb:
    """Stands in for `subprocess.run`, recording argv and scripting stdout.

    This is a *fake*, not a mock: it has real (if trivial) behaviour and the
    tests assert against the calls it recorded, rather than pre-programming
    expectations into it. Injected through `AdbContext.runner`, so the code
    under test builds its real argv and this records exactly what would have
    been executed.
    """

    def __init__(
        self,
        *,
        foreground_dump: str = GRAVITRAX_DUMP,
        devices: str = "List of devices attached\nemulator-5554\tdevice\n\n",
        boot_completed: str = "1",
        screencap_png: bytes = PNG_FRAME,
    ) -> None:
        self.foreground_dump = foreground_dump
        self.devices = devices
        self.boot_completed = boot_completed
        self.screencap_png = screencap_png
        self.calls: list[list[str]] = []

    def __call__(
        self, cmd: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess:
        argv = [str(part) for part in cmd]
        self.calls.append(argv)
        joined = " ".join(argv)

        if "screencap" in joined:
            return subprocess.CompletedProcess(argv, 0, self.screencap_png, b"")

        if argv[1:2] == ["devices"]:
            out = self.devices
        elif "sys.boot_completed" in joined:
            out = self.boot_completed + "\n"
        elif "dumpsys window" in joined:
            out = self.foreground_dump
        else:
            out = ""
        return subprocess.CompletedProcess(argv, 0, out, "")

    # -- helpers the assertions read through --------------------------------

    def index_of(self, predicate: Callable[[str], bool]) -> int:
        """Position of the first recorded call whose joined argv matches."""
        for i, argv in enumerate(self.calls):
            if predicate(" ".join(argv)):
                return i
        raise AssertionError(
            "no recorded adb call matched. calls were:\n  "
            + "\n  ".join(" ".join(a) for a in self.calls)
        )

    def has(self, predicate: Callable[[str], bool]) -> bool:
        return any(predicate(" ".join(argv)) for argv in self.calls)


def no_sleep(_seconds: float) -> None:
    """Swallow the flow's fixed waits.

    Not a shortcut: with real sleeps these tests took 63s against a 12s suite,
    because `render_course` spends ~14s of `WAITS` per call and nothing here is
    waiting on a real device. The durations themselves are asserted nowhere --
    they are a stopgap for the polling work (plan.md item 3), not behaviour.
    """


def ctx_with(fake: FakeAdb) -> AdbContext:
    """A context wired to the fake. The path is never touched -- nothing execs it."""
    return AdbContext(adb_path=Path("/nonexistent/adb"), runner=fake, sleep=no_sleep)


IS_TAP = lambda c: "input tap" in c  # noqa: E731
IS_FOREGROUND_CHECK = lambda c: "dumpsys window" in c  # noqa: E731
IS_SCREENCAP = lambda c: "screencap" in c  # noqa: E731
IS_FORCE_STOP = lambda c: "force-stop" in c  # noqa: E731
IS_LAUNCH = lambda c: "monkey" in c  # noqa: E731


# --- The parser, against real captured text --------------------------------


def test_parses_the_launcher_capture_that_fooled_s21() -> None:
    """The literal text the harness saw while returning a confident wrong answer."""
    assert parse_foreground_package(LAUNCHER_DUMP) == LAUNCHER_PKG


def test_parses_the_gravitrax_capture() -> None:
    """The passing case, from the same AVD minutes later."""
    assert parse_foreground_package(GRAVITRAX_DUMP) == DEFAULT_PACKAGE


def test_falls_back_to_focused_app_when_current_focus_is_null() -> None:
    """`mCurrentFocus=null` happens between windows; mFocusedApp still names the app."""
    dump = (
        "  mCurrentFocus=null\n"
        "  mFocusedApp=ActivityRecord{7496e4f u0 "
        "com.ravensburger.gravitrax/com.unity3d.player.UnityPlayerActivity t42}\n"
    )
    assert parse_foreground_package(dump) == DEFAULT_PACKAGE


def test_unreadable_dump_is_none_rather_than_a_guess() -> None:
    """Both fields null is 'I cannot tell' -- a distinct answer from 'wrong app'."""
    assert parse_foreground_package("  mCurrentFocus=null\n  mFocusedApp=null\n") is None


def test_empty_and_garbage_are_none() -> None:
    """An adb hiccup must not parse into a package name."""
    assert parse_foreground_package("") is None
    assert parse_foreground_package("error: no devices/emulators found") is None


def test_parser_does_not_read_the_activities_dump_format() -> None:
    """Scope pin, not a wish.

    `dumpsys activity activities` was captured alongside and uses a different
    shape (`ResumedActivity:` rather than `mCurrentFocus=`). The guard reads
    the window dump only. If someone later points it at the activities output,
    this fails and names the reason rather than silently returning None in
    production.
    """
    assert parse_foreground_package(ACTIVITIES_LAUNCHER_DUMP) is None


# --- read_foreground_package: the parser plus the adb call -----------------


def test_read_foreground_issues_a_single_window_dump() -> None:
    """One adb call, and it is the cheap one -- not `dumpsys activity activities`."""
    fake = FakeAdb()
    assert read_foreground_package(ctx_with(fake)) == DEFAULT_PACKAGE
    assert len(fake.calls) == 1
    assert "dumpsys window" in " ".join(fake.calls[0])
    assert "activity activities" not in " ".join(fake.calls[0])


# --- The guard -------------------------------------------------------------


def test_guard_passes_silently_when_the_app_is_in_front() -> None:
    """The happy path returns None and costs exactly one adb call.

    The call count is asserted, not just described. A docstring that names a
    cost its body never measures is #12's shape -- and this module argues
    about #12, which makes it the worst place to commit one.
    """
    fake = FakeAdb(foreground_dump=GRAVITRAX_DUMP)
    assert assert_app_in_foreground(ctx_with(fake)) is None
    assert len(fake.calls) == 1


def test_guard_raises_and_names_both_packages_when_the_launcher_is_in_front() -> None:
    """The s21 state. The message has to name what it found, or diagnosis restarts."""
    fake = FakeAdb(foreground_dump=LAUNCHER_DUMP)
    with pytest.raises(WrongForegroundAppError) as excinfo:
        assert_app_in_foreground(ctx_with(fake))
    message = str(excinfo.value)
    assert LAUNCHER_PKG in message
    assert DEFAULT_PACKAGE in message


def test_unreadable_foreground_is_its_own_error_not_a_wrong_app_claim() -> None:
    """'Something else is in front' and 'I could not read it' are different findings.

    Both stop the run -- proceeding blind is the whole failure being guarded --
    but collapsing them would let an adb hiccup be reported as the launcher
    being up, sending the next diagnosis somewhere false.
    """
    fake = FakeAdb(foreground_dump="  mCurrentFocus=null\n  mFocusedApp=null\n")
    with pytest.raises(ForegroundUnreadableError):
        assert_app_in_foreground(ctx_with(fake))


def test_the_two_foreground_errors_do_not_subclass_each_other() -> None:
    """Guards the distinction above against a later 'tidy-up' collapsing it."""
    assert not issubclass(WrongForegroundAppError, ForegroundUnreadableError)
    assert not issubclass(ForegroundUnreadableError, WrongForegroundAppError)


# --- render_course: where the guard sits -----------------------------------


def test_render_checks_the_foreground_before_the_very_first_tap(tmp_path: Path) -> None:
    """The ordering assertion, and the point of the whole module.

    A guard that runs after the first tap has already lost: the tap has landed
    on whatever was in front. This fails if anyone moves the check down.
    """
    fake = FakeAdb()
    render_course("ABC1234567", ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False)
    assert fake.index_of(IS_FOREGROUND_CHECK) < fake.index_of(IS_TAP)


def test_render_rechecks_the_foreground_around_the_screencap(tmp_path: Path) -> None:
    """Two checks bracket the flow.

    The opening check proves the app was in front when the run started; it says
    nothing about 40 seconds later, when the frame that becomes the verdict is
    taken. Same reasoning as the both-ends control locked 2026-08-07, one layer
    down.
    """
    fake = FakeAdb()
    render_course("ABC1234567", ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False)
    checks = [i for i, a in enumerate(fake.calls) if IS_FOREGROUND_CHECK(" ".join(a))]
    assert len(checks) >= 2, f"expected the flow to be bracketed, got {len(checks)} check(s)"
    assert checks[-1] > fake.index_of(IS_SCREENCAP)


def test_render_against_the_launcher_raises_without_tapping_anything(
    tmp_path: Path,
) -> None:
    """The s21 regression, stated as the behaviour that would have prevented it.

    Not one tap, not one screencap. The old code ran the entire flow here and
    returned a verdict.
    """
    fake = FakeAdb(foreground_dump=LAUNCHER_DUMP)
    with pytest.raises(WrongForegroundAppError):
        render_course("ABC1234567", ctx=ctx_with(fake), screenshot_dir=tmp_path)
    assert not fake.has(IS_TAP)
    assert not fake.has(IS_SCREENCAP)


def test_render_does_not_reset_by_default(tmp_path: Path) -> None:
    """`reset_first` is opt-in. A default reset would change every caller's cost."""
    fake = FakeAdb()
    render_course("ABC1234567", ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False)
    assert not fake.has(IS_FORCE_STOP)


def test_reset_first_establishes_state_then_verifies_it(tmp_path: Path) -> None:
    """Order: force-stop, launch, *then* check -- and the check is before any tap.

    `reset_first` **establishes** main-menu state rather than checking it: the
    Unity surface is opaque, so there is nothing to read. What the guard then
    verifies is the weaker, real claim -- that the relaunch put the app in
    front at all.
    """
    fake = FakeAdb()
    render_course(
        "ABC1234567",
        ctx=ctx_with(fake),
        screenshot_dir=tmp_path,
        cleanup=False,
        reset_first=True,
        settle_seconds=0.0,
    )
    stop = fake.index_of(IS_FORCE_STOP)
    launch = fake.index_of(IS_LAUNCH)
    check = fake.index_of(IS_FOREGROUND_CHECK)
    assert stop < launch < check < fake.index_of(IS_TAP)


def test_reset_first_reports_a_relaunch_that_did_not_take(tmp_path: Path) -> None:
    """If the app fails to come up, that is a loud failure, not a dark screenshot."""
    fake = FakeAdb(foreground_dump=LAUNCHER_DUMP)
    with pytest.raises(WrongForegroundAppError):
        render_course(
            "ABC1234567",
            ctx=ctx_with(fake),
            screenshot_dir=tmp_path,
            reset_first=True,
            settle_seconds=0.0,
        )
    assert not fake.has(IS_TAP)


def test_guard_honours_a_non_default_package(tmp_path: Path) -> None:
    """The context owns the package name; the guard must not hardcode GraviTrax."""
    fake = FakeAdb(foreground_dump=GRAVITRAX_DUMP)
    ctx = AdbContext(
        adb_path=Path("/nonexistent/adb"),
        package="com.example.other",
        runner=fake,
        sleep=no_sleep,
    )
    with pytest.raises(WrongForegroundAppError) as excinfo:
        assert_app_in_foreground(ctx)
    assert "com.example.other" in str(excinfo.value)


# --- Claims that had no test until a panel proved mutants survive them ------


def test_splash_and_main_menu_are_indistinguishable() -> None:
    """The evidence for "this guard cannot see which screen is showing".

    Two captures of the same app on the same AVD, ~3s after launch and after a
    30s settle. If they are byte-identical then the guard provably cannot
    distinguish splash from main menu, and every docstring saying so is backed
    by a file rather than by a memory of having looked.

    Committed because the claim was originally cited to fixtures that did not
    contain it -- the pointer resolved to the launcher/GraviTrax pair, which
    differ. That is observation #24 at the evidence layer: a capture that lives
    only in a conversation is not state.
    """
    assert SPLASH_DUMP == MENU_DUMP
    assert parse_foreground_package(SPLASH_DUMP) == DEFAULT_PACKAGE


def test_the_unreadable_path_dumps_exactly_once(tmp_path: Path) -> None:
    """Kills the mutant that re-dumps to build its own error message.

    `assert_app_in_foreground`'s docstring forbids re-dumping, because the
    second call can return different text than the one that failed -- a report
    that disagrees with its own evidence. Before this test, making that exact
    one-token edit left the whole suite green.
    """
    fake = FakeAdb(foreground_dump="  mCurrentFocus=null\n  mFocusedApp=null\n")
    with pytest.raises(ForegroundUnreadableError):
        assert_app_in_foreground(ctx_with(fake))
    dumps = [a for a in fake.calls if "dumpsys window" in " ".join(a)]
    assert len(dumps) == 1, f"expected one dump, got {len(dumps)}"


def test_the_unreadable_error_carries_the_dump_that_actually_failed() -> None:
    """The other half: the message must quote the text it could not parse."""
    weird = "  mCurrentFocus=SOMETHING-UNPARSEABLE-9f3a\n"
    fake = FakeAdb(foreground_dump=weird)
    with pytest.raises(ForegroundUnreadableError) as excinfo:
        assert_app_in_foreground(ctx_with(fake))
    assert "SOMETHING-UNPARSEABLE-9f3a" in str(excinfo.value)
    assert excinfo.value.dump == weird


def test_the_guard_dumps_once_per_check_not_more(tmp_path: Path) -> None:
    """Kills the mutant that adds a redundant dump on every guard call.

    render_course checks twice, so the flow must cost exactly two dumps. An
    extra dump per check is invisible to every assertion that only looks at
    *ordering*, and the panel showed the suite stayed green with one added.
    """
    fake = FakeAdb()
    render_course("ABC1234567", ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False)
    dumps = [a for a in fake.calls if "dumpsys window" in " ".join(a)]
    assert len(dumps) == 2, f"expected two dumps (open + close), got {len(dumps)}"


def test_the_closing_check_sits_immediately_before_the_cleanup_taps(
    tmp_path: Path,
) -> None:
    """The default path, which the other ordering tests cannot see.

    They pass `cleanup=False`, so the four trailing taps -- back, dont-save,
    trash, delete-confirm -- do not exist in them. Two of those are
    destructive. Nothing re-checks after cleanup (stated as a gap in
    render_course's docstring rather than rounded off), so what is worth
    pinning is that no *unguarded* tap precedes the closing check.
    """
    fake = FakeAdb()
    render_course("ABC1234567", ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=True)
    taps = [i for i, a in enumerate(fake.calls) if IS_TAP(" ".join(a))]
    checks = [i for i, a in enumerate(fake.calls) if IS_FOREGROUND_CHECK(" ".join(a))]
    cleanup_taps = [i for i in taps if i > checks[-1]]
    assert len(cleanup_taps) == 4, (
        f"expected the 4 cleanup taps after the close, got {cleanup_taps}"
    )
    assert checks[-1] == cleanup_taps[0] - 1, (
        "the closing check must be the call immediately before cleanup begins"
    )
