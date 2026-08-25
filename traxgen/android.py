"""Drive the GraviTrax Android app via adb to render a course from a share code.

The flow this module automates was mapped manually during the M6.c session
(2026-04-25). The tap coordinates assume the AVD `traxgen_m6c` is running
at its default 2400x1080 landscape resolution. Coordinates may need to be
re-measured if the device profile changes.

Path: traxgen/traxgen/android.py
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
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


class FrameUnreadableError(AndroidAutomationError):
    """A frame sample came back empty during a pixel-stability wait.

    Deliberately NOT the frame equivalent of `dump_ui` returning None.
    `uiautomator dump` fails *while a view animates*, which is exactly when a
    poller runs, so None there means "not ready yet". `screencap` has no such
    state: it returns a frame or it fails. Tolerating a gap here would be worse
    than useless, because `wait_until` skips the predicate on a None sample --
    so the frame before the gap and the frame after it would count as
    consecutive, stitching a quiet streak across an interval nobody observed.
    """


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


class RefusedScreenError(AndroidAutomationError):
    """The captured frame matches a screen known not to be a render.

    A sibling of `OracleFrameError` rather than a subclass, for the same reason
    `WrongForegroundAppError` and `ForegroundUnreadableError` are siblings: the
    two send a human to different places. Near-white means the app was still
    loading and the fix is time. This means the app was showing a *finished*
    screen that is not the course -- the tap sequence went somewhere else -- and
    the fix is the tap, or a retry.

    Carries `distance` because that number is the calibration data for
    `REFUSED_SCREEN_DISTANCE`. Swallowing it is what would leave the threshold
    permanently declared, the same argument as `FrameStability.differences`.
    """

    def __init__(self, *, screen: str, distance: float, threshold: float, path: Path) -> None:
        self.screen = screen
        self.distance = distance
        self.threshold = threshold
        self.path = path
        super().__init__(
            f"{path.name} matches the refused screen {screen!r} "
            f"(distance {distance:.3f} <= {threshold}); refusing to classify it as a "
            "render. The share code was not loaded -- the flow ended somewhere else."
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


def wait_until[Sample](
    dump_fn: Callable[[], Sample | None],
    predicate: Callable[[Sample], bool],
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

    Generic over the sample type, and the generalisation is typing only -- the
    body is byte-for-byte what it was when the sample was always a uiautomator
    hierarchy string. `wait_for_stable_frame` polls frames rather than XML, and
    the alternative was a second copy of this deadline loop.

    Note for stateful predicates (`FrameStability` is one): the predicate is
    NOT called when `dump_fn` returns None, so a predicate that compares
    successive samples never learns that a sample was skipped. A caller whose
    samples cannot legitimately be None should refuse None at the source rather
    than rely on this loop to notice.
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


# --- Pixel stability (the Unity-surface wait) ------------------------------
#
# `wait_for_node` reads `uiautomator`, and the Unity game surface is opaque to
# it -- the same blindness `assert_app_in_foreground` hit one layer up. So the
# two waits in front of that surface (`after_load`, `after_render_load`) cannot
# be polled by hierarchy, and pixels are the only channel left. On 2026-08-23
# the opening certified control was refused at white_frac 0.660 -- a loading
# screen the fixed sleep had expired into -- and `probe_plate_membership.py`
# has no resume path, so that cost the whole campaign.
#
# SCOPE, stated because the obvious reading is wrong: "the picture stopped
# moving" is NOT "the course has loaded". A splash screen is perfectly still.
# This answers a *necessary* condition, never a sufficient one, and it earns
# its place by composing with the two guards that already exist rather than by
# replacing either:
#
#   assert_app_in_foreground  -- is the right APPLICATION in front?   (s23)
#   frame_white_fraction      -- is this a near-white splash?         (2026-08-07)
#   FrameStability            -- has the surface stopped ANIMATING?   (here)
#
# Three axes, and what remains uncovered is the intersection none of them sees:
# a still, non-near-white screen owned by GraviTrax that is not the render.
# Named rather than left to look like coverage.
#
# THE THREE NUMBERS BELOW ARE DECLARED, NOT MEASURED. No frame-to-frame delta
# of a real loaded GraviTrax course has ever been recorded, so the noise floor
# of a "still" Unity surface is unknown -- it may not be exactly zero (temporal
# antialiasing and dithering both jitter). Rather than pick a plausible number
# and let it survive because nobody looked (observations #18), the defaults are
# the strict end and `FrameStability` records every difference it observes, so
# the first live run reports the real distribution and the constants get set
# from it -- the same route `scripts/calibrate_frame_guard.py` took for the
# frame guard. Strictness is the right side to start on per observations #17:
# a premature "stable" renders a loading screen and can invent a verdict, while
# a timeout costs a re-run and invents nothing.

FRAME_STABILITY_DOWNSCALE = 4

# The resampling filter is NOT a taste choice, and the default is wrong here.
# Measured on a 16x12 frame downscaled to 4x3, comparing a dark frame against
# the same frame with one bright row (the honest area-average is 21.33), and
# mirrored bright halves (the honest answer is 80.0):
#
#   NEAREST    halves 80.000   one-row  0.000   <- the moving row VANISHES
#   BOX        halves 80.000   one-row 21.333   <- exact area average
#   BILINEAR   halves 70.000   one-row 15.333
#   BICUBIC    halves 74.500   one-row 16.667   <- Pillow's default
#   LANCZOS    halves 75.500   one-row 18.000
#
# Every filter but BOX *attenuates* motion, and BICUBIC -- what `Image.resize`
# picks when nobody says otherwise -- under-reports a real change by 22%. An
# attenuated difference is a difference that slips under the tolerance, i.e. a
# moving screen called still, which is the direction that invents data
# (observations #17). BOX is the only filter whose output is the mean of the
# pixels it covers, which is the one property this comparison rests on.
#
# Broken window, named rather than fixed: `frame_white_fraction` above does the
# same `.resize()` with the same silent default. It is a global brightness
# statistic rather than a difference, so the attenuation matters far less --
# but its 0.942-vs-0.014 calibration was measured through BICUBIC, and changing
# the filter would invalidate those numbers. It belongs with the frame guard's
# own calibration, not smuggled into this change.
#
# Deliberately not a module constant: it is a correctness choice rather than a
# tuning knob (unlike the three below), and naming it here as a bare int would
# be one more claim about PIL's enum that nothing checks. It is read off
# `Image.Resampling.BOX` at the point of use, where `Image` is already in scope.
FRAME_STABILITY_REQUIRED_SAMPLES = 3
FRAME_STABILITY_TOLERANCE = 0.0
FRAME_STABILITY_TIMEOUT = 30.0
FRAME_STABILITY_INTERVAL = 0.5


class FrameFingerprint(NamedTuple):
    """A frame reduced to the form two frames are compared in."""

    width: int
    height: int
    channels: bytes


def frame_fingerprint(png_bytes: bytes) -> FrameFingerprint:
    """Reduce a screencap PNG to downscaled RGB channel data.

    RGB rather than greyscale on purpose: a luminance-preserving colour change
    is invisible to greyscale, and missing a change is the direction that
    invents stability. The downscale is for cost -- a full 2400x1080 frame is
    7.8M channel values per comparison, which does not fit inside a poll.

    What the tests do and do not say about the downscale, stated precisely
    because the loose version was wrong. Changing or removing it DOES fail the
    suite: `test_the_difference_is_a_mean_and_not_a_worst_pixel` computes its
    expected value through the 4x4 block this factor produces, so 4 is pinned.
    But pinned is not validated -- that test shows only that the constant is
    the one currently in force, never that it is the right one. Nothing here
    measures how small a moving region may get before area-averaging hides it,
    because that depends on a real frame and no real frame has been sampled.
    The number is a cost-versus-sensitivity guess awaiting the first live run,
    and a change-detector test is the most an offline suite can honestly be.
    """
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if FRAME_STABILITY_DOWNSCALE > 1:
        image = image.resize(
            (
                max(1, image.width // FRAME_STABILITY_DOWNSCALE),
                max(1, image.height // FRAME_STABILITY_DOWNSCALE),
            ),
            Image.Resampling.BOX,
        )
    return FrameFingerprint(image.width, image.height, image.tobytes())


def frame_difference(before: FrameFingerprint, after: FrameFingerprint) -> float:
    """Mean absolute channel difference between two frames, 0.0 to 255.0.

    Frames of different geometry are infinitely different rather than compared
    elementwise: a resolution change is never "the same picture", and averaging
    past the shorter buffer would read as stability.
    """
    if (before.width, before.height) != (after.width, after.height):
        return float("inf")
    total = sum(abs(a - b) for a, b in zip(before.channels, after.channels, strict=True))
    return total / float(len(before.channels))


class FrameStability:
    """Stateful predicate: true once N consecutive samples differ by <= tolerance.

    Stateful by necessity, not by taste. Stability is a property of a *sequence*
    and `wait_until`'s predicate only ever sees one sample, so the history has
    to live somewhere. Build a fresh one per wait -- reusing one carries the
    previous wait's streak into the next.

    Also the instrument that calibrates its own threshold: `differences` holds
    every delta observed, so a live run reports the noise floor rather than the
    declared constant standing unexamined.
    """

    def __init__(
        self,
        *,
        required: int = FRAME_STABILITY_REQUIRED_SAMPLES,
        tolerance: float = FRAME_STABILITY_TOLERANCE,
    ) -> None:
        if required < 2:
            raise ValueError("required must be at least 2 -- one sample is not a comparison")
        if tolerance < 0.0:
            raise ValueError("tolerance must not be negative")
        self.required = required
        self.tolerance = tolerance
        self.differences: list[float] = []
        self._previous: FrameFingerprint | None = None
        self._quiet = 0

    def __call__(self, sample: FrameFingerprint) -> bool:
        if self._previous is None:
            self._previous = sample
            self._quiet = 1
            return False
        difference = frame_difference(self._previous, sample)
        self.differences.append(difference)
        self._previous = sample
        # Reset rather than decrement: 'quiet, quiet, MOVED, quiet' must not
        # count as three of four. A run of motion restarts the streak at the
        # sample that moved.
        self._quiet = self._quiet + 1 if difference <= self.tolerance else 1
        return self._quiet >= self.required


def wait_for_stable_frame(
    ctx: AdbContext | None = None,
    *,
    timeout: float = FRAME_STABILITY_TIMEOUT,
    interval: float = FRAME_STABILITY_INTERVAL,
    required: int = FRAME_STABILITY_REQUIRED_SAMPLES,
    tolerance: float = FRAME_STABILITY_TOLERANCE,
    sample_fn: Callable[[], bytes | None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> FrameStability:
    """Poll the screen until it stops changing; return the predicate that watched it.

    Returns rather than discards the `FrameStability` so the caller can record
    `differences` -- that list is the calibration data for the constants above,
    and dropping it is what would leave them permanently declared.

    Raises `UiConditionTimeout` if the screen never settles, and
    `FrameUnreadableError` if a sample comes back empty (see that exception for
    why a gap is refused rather than tolerated).
    """
    if sample_fn is None:
        if ctx is None:
            raise ValueError("wait_for_stable_frame needs an AdbContext or a sample_fn")
        bound_ctx = ctx
        sample_fn = lambda: _run_adb_binary(bound_ctx, "exec-out", "screencap", "-p")  # noqa: E731
    grab = sample_fn
    stability = FrameStability(required=required, tolerance=tolerance)

    def sample() -> FrameFingerprint:
        raw = grab()
        if not raw:
            raise FrameUnreadableError(
                "frame sample came back empty; screencap has no 'not readable yet' state"
            )
        return frame_fingerprint(raw)

    wait_until(
        sample,
        stability,
        timeout=timeout,
        interval=interval,
        description=(
            f"the screen to stop changing ({required} consecutive samples "
            f"within {tolerance})"
        ),
        sleep_fn=sleep_fn,
        clock=clock,
    )
    return stability


# --- Refused screens: a fourth axis, and a signature rather than a mode ------
#
# The three guards above answer three questions and the module already named
# what none of them sees: "a still, non-near-white screen owned by GraviTrax
# that is not the render." On 2026-08-25 that screen showed up and cost a
# campaign. Two of seven renders in the #17 2x2 ended on the app's **build
# tutorial** -- an empty course in the editor, "Drag a launch pad onto the base
# plate", play button greyed. GraviTrax was in the foreground (guard 1 passes),
# the frame is dark (guard 2 passes), the screen is static (guard 3 would pass),
# and the oracle read the greyed button and returned a well-formed `inactive`
# about a screen that was not the experiment. One of the two was a *control*,
# which is the only reason the run was voided rather than believed -- the
# 2026-08-07 both-ends lock earning its keep against a failure nobody had
# imagined, for the second time (observations #17).
#
# WHAT IS MEASURED, and what is not. Measured: both failed frames show the same
# screen -- 2.262 apart -- despite belonging to a one-plate course and a
# two-plate course, so neither frame reflects its own course and neither course
# was loaded. The app was showing a finished, correctly drawn empty editor.
#
# NOT measured: why. The first version of this comment asserted the mechanism --
# that `loaded_track_hex` was tapped after a fixed `WAITS["after_load"]`, landed
# on an empty slot, and opened a new empty course. That is still the leading
# explanation and it is an explanation, not a finding. It was written as a
# finding, and corrected the same day (observations #12) once the emulator's own
# log showed a second candidate: the graphics backend was shedding colour
# buffers in that window, and the log covering the failed run was truncated by a
# reboot before anyone could check. So the question is not open, it is
# unanswerable for that run.
#
# The guard does not depend on the answer. It recognises the screen.
#
# SCOPE, stated rather than implied, because this is exactly the shape
# observations #17 widened on: THIS IS A SIGNATURE GUARD, NOT A MODE GUARD. It
# recognises the build-tutorial screen. It says nothing about the next
# GraviTrax screen that is still, dark, in the foreground, and not a render.
# The structure concedes that rather than hiding it -- the reference is a *set*
# loaded from files, so the next dead screen discovered is a fixture to add,
# not a function to write. What would close the mode rather than the signature
# is a POSITIVE test ("this frame contains a course"), and no such test exists.
#
# The distance is measured, not declared. Fixture geometry 150x67, BOX, mean
# absolute channel difference, from the seven frames of the 2026-08-25 run:
#
#   build_tutorial vs the run's OTHER tutorial frame     2.262
#   build_tutorial vs certified_open   (real render)    25.890
#   build_tutorial vs arm2_E_on_home   (real render)    26.542
#   build_tutorial vs arm1_SW          (real render)    26.585
#
# The separation is structural, not fine detail: the same ratio (11.4x) holds
# from 1200x540 down to 100x45 and only starts to degrade at 60x27, which is
# why a 13KB fixture can carry it. `tests/fixtures/frames/` holds the other
# four so that table is a re-runnable claim rather than a sentence
# (observations #24).
#
# The RESAMPLING FILTER is load-bearing here too, and more sharply than it is
# for `frame_fingerprint` above -- found by mutation rather than by review.
# Downscaling the real 2400x1080 dead frame to the reference geometry:
#
#   BOX      2.262   <- what this code does
#   BICUBIC  3.929   <- Pillow's silent default
#   BILINEAR 4.114
#   NEAREST 10.298   <- ABOVE the threshold below: the guard MISSES
#
# So the filter and the threshold are coupled, and the careless default would
# have let through the exact frame this guard was built from. The committed
# 300x135 fixture demonstrates that the filters disagree; it cannot demonstrate
# the 10.298, because that needs the full capture and render screenshots are
# not committed. Conceded in the test docstring rather than papered over.
#
# The THRESHOLD is declared, inside a measured gap: 10.0 sits 4.4x above the
# observed dead-to-dead maximum and 2.6x below the observed dead-to-real
# minimum. It is a declaration because n=2 for the refused class -- one pair
# barely samples its spread. Erring high is the right side per observations
# #17: too high refuses a real render, which costs a re-run and invents
# nothing; too low passes a dead screen to the oracle, which invents a verdict.
# Every comparison's distance is reported (on the exception, and by
# `match_refused_screen`'s return) so the distribution grows with every render.

REFUSED_SCREEN_DIR = Path(__file__).parent / "data" / "refused_screens"
REFUSED_SCREEN_DISTANCE = 10.0


class RefusedScreen(NamedTuple):
    """A screen known not to be a render, reduced to comparison form.

    Carries its own geometry rather than trusting a module constant. The live
    frame is resampled to *this* size at comparison time, so the fixture file
    is self-describing and replacing it with a different size needs no code
    change -- unlike `FRAME_STABILITY_DOWNSCALE`, where the constant and the
    data have to agree and nothing but a test says so.
    """

    name: str
    width: int
    height: int
    channels: bytes


def load_refused_screens(directory: Path = REFUSED_SCREEN_DIR) -> tuple[RefusedScreen, ...]:
    """Load every PNG in `directory` as a refused screen, named by stem.

    Sorted by name so the order a match is reported in is not a function of the
    filesystem's listing order (observations #30 -- a generated collection's
    order is part of its content).
    """
    from PIL import Image

    screens = []
    for path in sorted(directory.glob("*.png")):
        image = Image.open(path).convert("RGB")
        screens.append(RefusedScreen(path.stem, image.width, image.height, image.tobytes()))
    return tuple(screens)


_REFUSED_SCREENS_CACHE: tuple[RefusedScreen, ...] | None = None


def default_refused_screens() -> tuple[RefusedScreen, ...]:
    """The shipped refused-screen set, decoded once per process."""
    global _REFUSED_SCREENS_CACHE
    if _REFUSED_SCREENS_CACHE is None:
        _REFUSED_SCREENS_CACHE = load_refused_screens()
    return _REFUSED_SCREENS_CACHE


def screen_distance(png_bytes: bytes, reference: RefusedScreen) -> float:
    """Mean absolute channel difference after matching the reference's geometry.

    Raises `ValueError` when the frame is smaller than the reference in either
    axis, rather than upscaling it. A frame that small means the device profile
    changed, and every tap coordinate in this module is wrong too -- answering
    "no match" there would silently retire the guard at exactly the moment the
    harness needs shouting at.
    """
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if image.width < reference.width or image.height < reference.height:
        raise ValueError(
            f"frame is {image.width}x{image.height}, smaller than the refused-screen "
            f"reference {reference.name} at {reference.width}x{reference.height}; the "
            "device profile has changed and the tap coordinates are stale too"
        )
    if (image.width, image.height) != (reference.width, reference.height):
        image = image.resize((reference.width, reference.height), Image.Resampling.BOX)
    live = image.tobytes()
    total = sum(abs(a - b) for a, b in zip(live, reference.channels, strict=True))
    return total / float(len(reference.channels))


def match_refused_screen(
    png_bytes: bytes,
    references: Sequence[RefusedScreen],
    *,
    threshold: float = REFUSED_SCREEN_DISTANCE,
) -> tuple[RefusedScreen, float] | None:
    """The nearest reference within `threshold`, with its distance, or None.

    Nearest rather than first-under-threshold: with several references the
    first match would depend on load order, and reporting the wrong dead screen
    sends a human to the wrong diagnosis.
    """
    best: tuple[RefusedScreen, float] | None = None
    for reference in references:
        distance = screen_distance(png_bytes, reference)
        if distance <= threshold and (best is None or distance < best[1]):
            best = (reference, distance)
    return best


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
    refused_screens: Sequence[RefusedScreen] | None = None,
    refused_screen_distance: float = REFUSED_SCREEN_DISTANCE,
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

    The captured frame is then checked against the refused-screen set and
    `RefusedScreenError` is raised if it matches one -- after cleanup, so the
    app is back at the main menu and the caller can retry. See the
    refused-screens section above for what that closes and, more importantly,
    what it does not: it recognises known dead screens by signature and cannot
    recognise an unknown one.
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

    # The fourth axis. Checked BEFORE the oracle, because on a refused screen
    # the oracle's answer is well-formed and wrong -- the greyed play button of
    # an empty editor reads exactly like a dark course.
    refusal = match_refused_screen(
        out_path.read_bytes(),
        default_refused_screens() if refused_screens is None else refused_screens,
        threshold=refused_screen_distance,
    )

    validity = detect_play_button_state(out_path) if detect_validity and not refusal else None

    # Cleanup runs whether or not the frame was refused, and the raise comes
    # after it. Measured rather than assumed: in the 2026-08-25 run the two
    # renders that landed on the build tutorial were followed by three that
    # rendered normally, so this tap sequence does return to the main menu from
    # the empty editor. Raising before cleanup would leave a course open and
    # turn one bad render into a cascade -- the caller's retry would start from
    # the wrong screen, which is the failure this guard exists to catch.
    if cleanup:
        tap(ctx, "back_save_icon")
        ctx.sleep(WAITS["after_back"])
        tap(ctx, "dont_save")
        tap(ctx, "trash_icon")
        ctx.sleep(WAITS["after_delete"])
        tap(ctx, "delete_confirm")
        ctx.sleep(WAITS["after_delete"])

    if refusal:
        screen, distance = refusal
        raise RefusedScreenError(
            screen=screen.name,
            distance=distance,
            threshold=refused_screen_distance,
            path=out_path,
        )

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
