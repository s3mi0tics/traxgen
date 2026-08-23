"""Drive the GraviTrax Android app via adb to render a course from a share code.

The flow this module automates was mapped manually during the M6.c session
(2026-04-25). The tap coordinates assume the AVD `traxgen_m6c` is running
at its default 2400x1080 landscape resolution. Coordinates may need to be
re-measured if the device profile changes.

Path: traxgen/traxgen/android.py
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

# --- Configuration ---------------------------------------------------------

DEFAULT_ANDROID_HOME = Path.home() / "Library" / "Android" / "sdk"
DEFAULT_PACKAGE = "com.ravensburger.gravitrax"
DEFAULT_SCREENSHOT_DIR = Path.home() / "Desktop" / "Hub" / "Projects" / "traxgen" / "screenshots"

# Tap coordinates in 2400x1080 device space. Mapped manually; document any
# changes in docs/refs/android-automation.md.
COORDS = {
    "share_code_hex": (265, 970),
    "load_track_now": (1450, 800),
    "code_input_field": (1200, 630),
    "ime_ok": (2270, 305),
    "load_track_button": (1200, 800),
    "loaded_track_hex": (1200, 540),
    "back_save_icon": (180, 60),
    "dont_save": (950, 800),
    "trash_icon": (1530, 280),
    "delete_confirm": (1200, 800),
}

# Wait durations (seconds). Tuned during M6.c manual mapping (2026-04-25) against a
# warm emulator.
#
# Bumped 2026-08-07 after the goal-rotation sweep's positive control failed: on a
# cold-booted AVD the fullscreen extract-mode IME had not finished laying out when
# `ime_ok` fired, so the share code was never submitted and every later step ran
# against a keyboard -- the play-button oracle sampled key pixels and returned
# 'inactive'. The tap coordinate was verified correct against the uiautomator bounds
# ([2216,252][2384,378] contains (2270,305)), so this is a timing failure, not a
# geometry one.
#
# These are still fixed sleeps and they still assert nothing: too short is flaky,
# too long is slow, and the right value moves with machine load. See plan.md's
# triggered review for the polling-based replacement this is a stopgap for.
WAITS = {
    "after_tap": 0.8,
    "after_text": 1.5,
    "after_load": 4.0,
    "after_render_load": 5.0,
    "after_back": 1.0,
    "after_delete": 1.5,
}

# How long the Unity app needs after a force-stop-and-relaunch before it will
# drive. Measured during the 2026-08-10 queue work; a cold splash needs real
# time and 8s was demonstrably not enough (2026-08-07).
#
# Defined in `scripts/run_sweep_queue.py` from 2026-08-10, and imported from
# there by `scripts/probe_plate_membership.py` as of ba41b2f (s21, 2026-08-21).
# That put a fact about the *app* inside a script, and left the library-level
# `reset_first` below unable to reach it without traxgen importing from scripts
# -- the dependency arrow backwards. Moved here 2026-08-23 (s23); both scripts
# now import it from the library.
SETTLE_SECONDS = 35.0


# --- Exceptions ------------------------------------------------------------

class AndroidAutomationError(Exception):
    """Base for every failure mode of the android automation module."""


class AdbNotFoundError(AndroidAutomationError):
    """ANDROID_HOME doesnt point to a valid SDK with adb."""


class AdbCommandFailedError(AndroidAutomationError):
    """An adb invocation returned non-zero or otherwise failed."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"adb failed (rc={returncode}): {' '.join(cmd)}\n  stderr: {stderr[:200]}"
        )


class EmulatorNotReadyError(AndroidAutomationError):
    """The emulator is not running, not visible to adb, or not booted."""


class UiConditionTimeout(AndroidAutomationError):
    """A polled UI condition did not become true within its timeout."""


class OracleFrameError(AndroidAutomationError):
    """The screencap does not look like a rendered course, so it wasn't classified."""


class WrongForegroundAppError(AndroidAutomationError):
    """A different app is in front, so taps would land on it.

    Deliberately neither subclasses the other: they are siblings under
    `AndroidAutomationError`, so one `except` still catches both, but neither
    can be caught *as* the other. "The launcher is
    up" and "adb exited 0 saying nothing I could parse" are different findings
    that send a human looking in different places.

    Note the third case is a different class again: if adb itself fails, exits
    non-zero, or times out, `_run_adb` raises `AdbCommandFailedError` and
    neither of these is reached.
    """

    def __init__(self, *, expected: str, found: str) -> None:
        self.expected = expected
        self.found = found
        super().__init__(
            f"{found!r} is in the foreground, not {expected!r}. Taps would land on "
            "the wrong app and the oracle would sample it. Launch the app (or pass "
            "reset_first=True) before rendering."
        )


class ForegroundUnreadableError(AndroidAutomationError):
    """adb answered, but nothing in the dump named a foreground package."""

    def __init__(self, dump: str) -> None:
        self.dump = dump
        excerpt = dump.strip()[:200] or "<empty>"
        super().__init__(
            "could not read the foreground package from `dumpsys window`; refusing "
            f"to proceed blind. Output was:\n  {excerpt}"
        )


# --- adb wrapper -----------------------------------------------------------

@dataclass(frozen=True)
class AdbContext:
    """Resolved paths and configuration for adb invocations.

    `runner` and `sleep` are the seams that make the automation flow testable
    without an emulator. Both default to the real thing (`subprocess.run`,
    `time.sleep`), and tests pass fakes -- one that records the argv the code
    actually built, one that costs no elapsed time. Same shape as the injected
    callables in `scripts/run_sweep_queue.py`: a real default, overridable per
    call site, so production behaviour is unchanged by the seam existing.

    `sleep` is injectable for a concrete reason, not symmetry. The flow spends
    22.5s of fixed `WAITS` per render on the default path, 15.3s with
    `cleanup=False`; with only `runner` faked, the offline tests in
    tests/test_android_foreground.py took 63s against a 12s suite. A slow
    offline test is one that stops being run.
    """

    adb_path: Path
    package: str = DEFAULT_PACKAGE
    runner: Callable[..., subprocess.CompletedProcess[Any]] = field(
        default=subprocess.run, repr=False, compare=False
    )
    sleep: Callable[[float], None] = field(
        default=time.sleep, repr=False, compare=False
    )


def resolve_context(android_home: Path | None = None, package: str = DEFAULT_PACKAGE) -> AdbContext:
    """Locate adb based on ANDROID_HOME or env var. Validate that it exists."""
    home = android_home or Path(os.environ.get("ANDROID_HOME", DEFAULT_ANDROID_HOME))
    adb = home / "platform-tools" / "adb"
    if not adb.is_file():
        raise AdbNotFoundError(
            f"adb not found at {adb}. Set ANDROID_HOME or pass android_home."
        )
    return AdbContext(adb_path=adb, package=package)


def _run_adb(ctx: AdbContext, *args: str, timeout: float = 10.0) -> str:
    """Run an adb command and return stdout. Raise on non-zero exit."""
    cmd = [str(ctx.adb_path), *args]
    try:
        result = ctx.runner(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbCommandFailedError(cmd=cmd, returncode=-1, stderr=f"timeout: {exc}") from exc
    if result.returncode != 0:
        raise AdbCommandFailedError(
            cmd=cmd, returncode=result.returncode, stderr=result.stderr
        )
    return result.stdout


def _run_adb_binary(ctx: AdbContext, *args: str, timeout: float = 30.0) -> bytes:
    """Run an adb command that produces binary output."""
    cmd = [str(ctx.adb_path), *args]
    try:
        result = ctx.runner(
            cmd, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbCommandFailedError(cmd=cmd, returncode=-1, stderr=f"timeout: {exc}") from exc
    if result.returncode != 0:
        raise AdbCommandFailedError(
            cmd=cmd,
            returncode=result.returncode,
            stderr=result.stderr.decode("utf-8", errors="replace"),
        )
    return result.stdout


def assert_emulator_ready(ctx: AdbContext) -> None:
    """Verify an emulator is connected and booted.

    Scope, stated because misreading it cost a run. This checks the *emulator*
    and says nothing about what is in front of it: a booted device with the app
    closed passes here. That is what `assert_app_in_foreground` is for, and on
    2026-08-21 the gap between the two produced a confident wrong verdict off a
    screenshot of the Android launcher (observations #17).
    """
    devices_out = _run_adb(ctx, "devices")
    if "emulator-" not in devices_out:
        raise EmulatorNotReadyError(
            f"no emulator detected. adb devices output:\n{devices_out}"
        )
    boot = _run_adb(ctx, "shell", "getprop", "sys.boot_completed").strip()
    if boot != "1":
        raise EmulatorNotReadyError(
            f"emulator not booted (sys.boot_completed={boot!r})"
        )


# --- Primitives ------------------------------------------------------------

def tap(ctx: AdbContext, coord_name_or_xy: str | tuple[int, int]) -> None:
    """Tap a named coordinate or a literal (x, y) tuple."""
    if isinstance(coord_name_or_xy, str):
        if coord_name_or_xy not in COORDS:
            raise ValueError(f"unknown coord name: {coord_name_or_xy}")
        x, y = COORDS[coord_name_or_xy]
    else:
        x, y = coord_name_or_xy
    _run_adb(ctx, "shell", "input", "tap", str(x), str(y))
    ctx.sleep(WAITS["after_tap"])


def type_text(ctx: AdbContext, text: str) -> None:
    """Inject text via the native IME."""
    _run_adb(ctx, "shell", "input", "text", text)
    ctx.sleep(WAITS["after_text"])


def screencap(ctx: AdbContext, dest: Path) -> Path:
    """Capture a screenshot to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    png_bytes = _run_adb_binary(ctx, "exec-out", "screencap", "-p")
    dest.write_bytes(png_bytes)
    return dest


def force_stop(ctx: AdbContext) -> None:
    """Force-stop the GraviTrax app."""
    _run_adb(ctx, "shell", "am", "force-stop", ctx.package)


def launch(ctx: AdbContext) -> None:
    """Launch the GraviTrax app via monkey."""
    _run_adb(
        ctx, "shell", "monkey", "-p", ctx.package,
        "-c", "android.intent.category.LAUNCHER", "1",
    )


# --- Foreground guard ------------------------------------------------------
#
# `render_course()` opens with a blind coordinate tap. On 2026-08-21 it ran
# against a booted emulator with GraviTrax closed: every tap landed on the
# Android launcher, and the oracle sampled dark wallpaper -- which sits in the
# same brightness range as a real render, so the near-white frame guard passed
# it and returned a confident `inactive`. The probe being served *predicted*
# its discriminating cells dark, so the harness produced a flawless-looking
# confirmation of the hypothesis under test (observations #17, third firing).
#
# WHAT THIS CAN AND CANNOT SEE. Captured on AVD `traxgen_m6c` (API 34) on
# 2026-08-23, ~3s after launch (splash) and again after a 30s settle (main
# menu), `dumpsys window` returned byte-identical text. Both captures are
# committed -- tests/fixtures/dumpsys_window_gravitrax_t3s.txt and
# _t33s.txt -- and their identity is asserted by a test, so this is evidence
# rather than a recollection.
#
# So this answers "is the app in front" and cannot answer "which screen is
# showing"; the Unity surface is opaque here exactly as it is to uiautomator.
# The launcher failure is closed. The splash failure (2026-08-07) is not.
# Note it is NOT closed by plan.md's sequenced item 3 either: that item wires
# in `wait_for_node`, which is uiautomator-only and therefore blind to this
# same surface. Per plan.md's triggered review on the two Unity-surface waits,
# a pixel-stability predicate is the only route -- `wait_until` accepts an
# arbitrary dump_fn, so the polling primitive fits; the uiautomator predicate
# does not.

_FOREGROUND_PATTERNS = (
    re.compile(r"mCurrentFocus=Window\{\S+\s+\S+\s+([A-Za-z0-9_.]+)/"),
    re.compile(r"mFocusedApp=ActivityRecord\{\S+\s+\S+\s+([A-Za-z0-9_.]+)/"),
)


def parse_foreground_package(dumpsys_window_output: str) -> str | None:
    """Read the foreground package out of `dumpsys window`, or None if it can't be.

    Tries `mCurrentFocus` first and falls back to `mFocusedApp`, because
    `mCurrentFocus=null` occurs legitimately between windows while
    `mFocusedApp` still names the app. A `mCurrentFocus` naming a system window
    with no package (`StatusBar`) also falls through, by the same rule.

    None means "nothing here named a package" -- deliberately distinct from
    naming the wrong one. Callers must not treat it as an app identity.
    """
    for pattern in _FOREGROUND_PATTERNS:
        match = pattern.search(dumpsys_window_output)
        if match:
            return match.group(1)
    return None


def _dump_foreground(ctx: AdbContext) -> str:
    """Raw `dumpsys window` focus lines, filtered on-device to keep it small.

    `dumpsys activity activities` also names the package -- both were captured
    on the AVD (2026-08-23) and the activities capture is committed alongside.
    Either would work. `dumpsys window` was picked because its unfiltered output
    is the smaller of the two; that comparison was not measured, and the two
    committed captures are both post-grep, so they do not evidence it.
    """
    return _run_adb(
        ctx, "shell", "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"
    )


def read_foreground_package(ctx: AdbContext) -> str | None:
    """Ask the device which package is in front. None if the dump didn't say."""
    return parse_foreground_package(_dump_foreground(ctx))


def assert_app_in_foreground(ctx: AdbContext) -> None:
    """Raise unless `ctx.package` is the foreground app.

    Both failure directions stop the run, because proceeding blind is the
    failure being guarded -- but they raise *different* exceptions, since
    "the launcher is up" and "adb would not say" send a human looking in
    different places.

    The dump is read exactly once and the unreadable error carries *that* text.
    Re-dumping to build the message would quote a different adb call than the
    one that failed, which is a report that can disagree with its own evidence.
    """
    dump = _dump_foreground(ctx)
    found = parse_foreground_package(dump)
    if found is None:
        raise ForegroundUnreadableError(dump)
    if found != ctx.package:
        raise WrongForegroundAppError(expected=ctx.package, found=found)


# --- UI state polling ------------------------------------------------------
#
# Generation-two synchronization for the steps that have something to poll.
# The Unity game surface is opaque to uiautomator; the native dialogs and IME
# are not. See docs/refs/ui-automation-synchronization.md.

class Bounds(NamedTuple):
    """A uiautomator node's pixel bounds in device space."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        """Center point, suitable for passing straight to `tap`."""
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def contains(self, x: int, y: int) -> bool:
        """Whether a point falls inside these bounds."""
        return self.left <= x <= self.right and self.top <= y <= self.bottom


def parse_bounds(raw: str) -> Bounds:
    """Parse uiautomator's `[left,top][right,bottom]` bounds string."""
    try:
        first, second = raw.replace("]", "").split("[")[1:]
        left, top = (int(v) for v in first.split(","))
        right, bottom = (int(v) for v in second.split(","))
    except (ValueError, IndexError) as exc:
        raise ValueError(f"unparseable bounds: {raw!r}") from exc
    return Bounds(left, top, right, bottom)


def find_node(
    hierarchy: str, *, cls: str | None = None, text: str | None = None
) -> Bounds | None:
    """Return the bounds of the first node matching every given attribute, else None."""
    if cls is None and text is None:
        raise ValueError("find_node needs at least one of cls or text")
    try:
        root = ET.fromstring(hierarchy)
    except ET.ParseError:
        return None
    for node in root.iter("node"):
        if cls is not None and node.get("class") != cls:
            continue
        if text is not None and node.get("text") != text:
            continue
        raw = node.get("bounds")
        if raw:
            return parse_bounds(raw)
    return None


def dump_ui(ctx: AdbContext, *, remote_path: str = "/sdcard/window_dump.xml") -> str | None:
    """Return the current uiautomator hierarchy XML, or None if it can't be read.

    Returning None rather than raising is deliberate. `uiautomator dump` fails
    while a view is animating ("could not get idle state"), and to a poller
    that is "not ready yet", not an error. Raising here would reintroduce the
    flakiness polling exists to remove.
    """
    try:
        _run_adb(ctx, "shell", "uiautomator", "dump", remote_path, timeout=15.0)
        out = _run_adb(ctx, "shell", "cat", remote_path, timeout=15.0)
    except AdbCommandFailedError:
        return None
    return out if "<hierarchy" in out else None


def wait_until(
    dump_fn: Callable[[], str | None],
    predicate: Callable[[str], bool],
    *,
    timeout: float = 10.0,
    interval: float = 0.25,
    description: str = "condition",
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Poll `dump_fn` until `predicate` holds; raise `UiConditionTimeout` otherwise.

    A `dump_fn` returning None means "not readable yet" and never satisfies the
    predicate. `sleep_fn` and `clock` are injectable so the polling logic is
    testable without real elapsed time or an emulator.
    """
    deadline = clock() + timeout
    polls = 0
    while True:
        polls += 1
        hierarchy = dump_fn()
        if hierarchy is not None and predicate(hierarchy):
            return
        if clock() >= deadline:
            raise UiConditionTimeout(
                f"timed out after {timeout:.1f}s ({polls} polls) waiting for {description}"
            )
        sleep_fn(interval)


def wait_for_node(
    ctx: AdbContext,
    *,
    cls: str | None = None,
    text: str | None = None,
    present: bool = True,
    timeout: float = 10.0,
    interval: float = 0.25,
) -> None:
    """Wait for a matching node to appear (present=True) or vanish (present=False).

    For present=False an unreadable dump keeps polling rather than counting as
    "gone" -- the conservative reading, since a failed dump is ambiguous.
    """
    goal = "appear" if present else "disappear"
    wait_until(
        lambda: dump_ui(ctx),
        lambda h: (find_node(h, cls=cls, text=text) is not None) is present,
        timeout=timeout,
        interval=interval,
        description=f"node(class={cls!r}, text={text!r}) to {goal}",
    )


# --- High-level flow -------------------------------------------------------

class RenderResult(NamedTuple):
    """Result of a render_course call: screenshot path + optional validity."""

    screenshot: Path
    validity: str | None  # 'active' | 'inactive' | None (when not detected)


def render_course(
    code: str,
    *,
    ctx: AdbContext | None = None,
    screenshot_dir: Path = DEFAULT_SCREENSHOT_DIR,
    screenshot_name: str | None = None,
    cleanup: bool = True,
    expect_disclaimer: bool = True,
    detect_validity: bool = False,
    reset_first: bool = False,
    settle_seconds: float = SETTLE_SECONDS,
) -> RenderResult:
    """Drive the app: main menu -> render share code -> screenshot.

    PRECONDITION, now enforced. This function's first action is a blind
    coordinate tap; it assumes GraviTrax is open and on the main menu. The app
    half of that is checked twice: before the first tap, and again immediately
    after the frame is captured. Same reasoning as the both-ends control locked
    2026-08-07 -- an opening check proves the app was in front at tap one and
    says nothing about 40 seconds later.

    What the second check brackets is the *frame*, not the whole function. On
    the default `cleanup=True` path four more taps follow it (back, dont-save,
    trash, delete-confirm) and nothing re-checks after those. They sit directly
    behind the closing check, so a foreground change would have to land inside
    that window to matter -- but the guarantee is "checked immediately before
    cleanup", not "cleanup is guarded". Two of those taps are destructive,
    which is the reason to state the gap rather than round it off.

    The menu half is *not* checked, because it cannot be: splash and main menu
    are byte-identical to `dumpsys window`. `reset_first=True` **establishes**
    that state by force-stop-and-relaunch plus `settle_seconds`, rather than
    verifying it. Opt-in, so existing callers keep their current cost;
    `run_sweep_queue.py` already resets before every sweep and does not need it.
    """
    ctx = ctx or resolve_context()
    assert_emulator_ready(ctx)

    if reset_first:
        reset_to_main_menu(ctx)
        ctx.sleep(settle_seconds)

    # Before the first tap. After it, the tap has already landed on whatever
    # was in front, and the run is spending renders on the wrong surface.
    assert_app_in_foreground(ctx)

    name = screenshot_name or f"rendered_{code}"
    out_path = screenshot_dir / f"{name}.png"

    tap(ctx, "share_code_hex")
    if expect_disclaimer:
        tap(ctx, "load_track_now")
    tap(ctx, "code_input_field")
    type_text(ctx, code)
    tap(ctx, "ime_ok")
    tap(ctx, "load_track_button")
    ctx.sleep(WAITS["after_load"])
    tap(ctx, "loaded_track_hex")
    ctx.sleep(WAITS["after_render_load"])
    screencap(ctx, out_path)

    # The closing bracket. Capture first, then verify, so a run that fails here
    # still leaves the frame on disk for diagnosis -- the s21 diagnosis was
    # ended by looking at the screenshot. Note precisely what this establishes:
    # the app was in front immediately after the frame was taken. It is not
    # proof of what the frame contains, and nothing here can be.
    assert_app_in_foreground(ctx)

    validity = detect_play_button_state(out_path) if detect_validity else None

    if cleanup:
        tap(ctx, "back_save_icon")
        ctx.sleep(WAITS["after_back"])
        tap(ctx, "dont_save")
        tap(ctx, "trash_icon")
        ctx.sleep(WAITS["after_delete"])
        tap(ctx, "delete_confirm")
        ctx.sleep(WAITS["after_delete"])

    return RenderResult(screenshot=out_path, validity=validity)


def reset_to_main_menu(ctx: AdbContext | None = None) -> None:
    """Force-stop and relaunch the app."""
    ctx = ctx or resolve_context()
    force_stop(ctx)
    ctx.sleep(1.0)
    launch(ctx)


# --- Validity oracle: play-button color sampling ---------------------------

# Sampling region for the play button's interior triangle. Mapped from the
# valid/invalid screenshot pair captured 2026-04-25:
#   valid (white triangle):  R=247 G=250 B=234, min_channel=234
#   invalid (pale-green):    R=207 G=222 B=124, min_channel=124
# Threshold of 220 leaves a wide margin on both sides.
PLAY_BUTTON_SAMPLE_CENTER = (2190, 980)
PLAY_BUTTON_SAMPLE_HALF = 6
PLAY_BUTTON_ACTIVE_MIN_CHANNEL = 220.0

# --- Frame guard -----------------------------------------------------------
#
# The sample above is a BRIGHTNESS test, not a validity test. On 2026-08-07 it
# returned 'active' for a GraviTrax splash screen -- a near-white frame with the
# logo on it -- because the sampled box happened to be white. That manufactured
# a second active rotation in the goal-rotation sweep, which by the sweep's own
# pre-declared conditions read as MODEL_WRONG. A false 'inactive' produces a null
# result; a false 'active' produces a finding, so this is the worse direction.
#
# Guard: refuse to classify a frame that is mostly near-white. Measured on the
# four screencaps that survived the 2026-08-07 run (see
# scripts/calibrate_frame_guard.py):
#
#   splash screen (false 'active')     white_frac 0.942
#   real render, control, active       white_frac 0.014
#   real render, E rot 1, active       white_frac 0.014
#   real render, bracket, inactive     white_frac 0.013
#
# ~70x of daylight, so 0.50 sits mid-gap with ~35x margin either side. `mean`
# separates too (248 vs 124-146); `stddev` does NOT (29.6 vs 41.5-51.7) and was
# rejected for that reason.
FRAME_WHITE_MIN_CHANNEL = 235
FRAME_MAX_WHITE_FRACTION = 0.50
FRAME_GUARD_DOWNSCALE = 8


def frame_white_fraction(screenshot_path: Path) -> float:
    """Fraction of the frame whose dimmest RGB channel clears FRAME_WHITE_MIN_CHANNEL."""
    from PIL import Image, ImageChops

    img = Image.open(screenshot_path).convert("RGB")
    small = img.resize(
        (
            max(1, img.width // FRAME_GUARD_DOWNSCALE),
            max(1, img.height // FRAME_GUARD_DOWNSCALE),
        )
    )
    red, green, blue = small.split()
    min_channel = ImageChops.darker(ImageChops.darker(red, green), blue)
    mask = min_channel.point(lambda v: 255 if v >= FRAME_WHITE_MIN_CHANNEL else 0)
    return mask.histogram()[255] / float(small.width * small.height)


def detect_play_button_state(screenshot_path: Path, *, guard_frame: bool = True) -> str:
    """Sample the play-button triangle and return 'active' or 'inactive'.

    Active (course is valid by app's rules): triangle is white -> all RGB
    channels near 255. Inactive (invalid): triangle is pale-green-tinted
    -> blue channel drops markedly.

    Raises `OracleFrameError` when the frame is mostly near-white, i.e. a splash
    or loading screen rather than a rendered course. Callers that record render
    errors separately from validity verdicts (as the sweeps do) then get "no
    reading" instead of a confident wrong one. Pass guard_frame=False only for
    calibration, where classifying a known-bad frame is the point.

    Importing PIL here (not at module top) keeps Pillow optional for callers
    that only want the automation flow without validity classification.
    """
    from PIL import Image, ImageStat

    if guard_frame:
        white = frame_white_fraction(screenshot_path)
        if white >= FRAME_MAX_WHITE_FRACTION:
            raise OracleFrameError(
                f"{Path(screenshot_path).name}: {white:.3f} of the frame is near-white "
                f"(limit {FRAME_MAX_WHITE_FRACTION}) -- this looks like a splash or "
                "loading screen, not a rendered course; refusing to classify it"
            )

    img = Image.open(screenshot_path).convert("RGB")
    cx, cy = PLAY_BUTTON_SAMPLE_CENTER
    h = PLAY_BUTTON_SAMPLE_HALF
    box = img.crop((cx - h, cy - h, cx + h, cy + h))
    # ImageStat.mean is the per-band mean -- identical arithmetic to the previous
    # hand-rolled sum over getdata(), which Pillow 14 removes.
    avg_r, avg_g, avg_b = ImageStat.Stat(box).mean
    min_channel = min(avg_r, avg_g, avg_b)
    return "active" if min_channel >= PLAY_BUTTON_ACTIVE_MIN_CHANNEL else "inactive"
