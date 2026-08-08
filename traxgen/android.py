"""Drive the GraviTrax Android app via adb to render a course from a share code.

The flow this module automates was mapped manually during the M6.c session
(2026-04-25). The tap coordinates assume the AVD `traxgen_m6c` is running
at its default 2400x1080 landscape resolution. Coordinates may need to be
re-measured if the device profile changes.

Path: traxgen/traxgen/android.py
"""

from __future__ import annotations

import os
import subprocess
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

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


# --- adb wrapper -----------------------------------------------------------

@dataclass(frozen=True)
class AdbContext:
    """Resolved paths and configuration for adb invocations."""

    adb_path: Path
    package: str = DEFAULT_PACKAGE


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
        result = subprocess.run(
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
        result = subprocess.run(
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
    """Verify an emulator is connected and booted."""
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
    time.sleep(WAITS["after_tap"])


def type_text(ctx: AdbContext, text: str) -> None:
    """Inject text via the native IME."""
    _run_adb(ctx, "shell", "input", "text", text)
    time.sleep(WAITS["after_text"])


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
) -> RenderResult:
    """Drive the app: main menu -> render share code -> screenshot."""
    ctx = ctx or resolve_context()
    assert_emulator_ready(ctx)

    name = screenshot_name or f"rendered_{code}"
    out_path = screenshot_dir / f"{name}.png"

    tap(ctx, "share_code_hex")
    if expect_disclaimer:
        tap(ctx, "load_track_now")
    tap(ctx, "code_input_field")
    type_text(ctx, code)
    tap(ctx, "ime_ok")
    tap(ctx, "load_track_button")
    time.sleep(WAITS["after_load"])
    tap(ctx, "loaded_track_hex")
    time.sleep(WAITS["after_render_load"])
    screencap(ctx, out_path)

    validity = detect_play_button_state(out_path) if detect_validity else None

    if cleanup:
        tap(ctx, "back_save_icon")
        time.sleep(WAITS["after_back"])
        tap(ctx, "dont_save")
        tap(ctx, "trash_icon")
        time.sleep(WAITS["after_delete"])
        tap(ctx, "delete_confirm")
        time.sleep(WAITS["after_delete"])

    return RenderResult(screenshot=out_path, validity=validity)


def reset_to_main_menu(ctx: AdbContext | None = None) -> None:
    """Force-stop and relaunch the app."""
    ctx = ctx or resolve_context()
    force_stop(ctx)
    time.sleep(1.0)
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
