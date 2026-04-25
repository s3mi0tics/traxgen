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

# Wait durations (seconds). Tuned during M6.c manual mapping.
WAITS = {
    "after_tap": 0.5,
    "after_text": 0.3,
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


def detect_play_button_state(screenshot_path: Path) -> str:
    """Sample the play-button triangle and return 'active' or 'inactive'.

    Active (course is valid by app's rules): triangle is white -> all RGB
    channels near 255. Inactive (invalid): triangle is pale-green-tinted
    -> blue channel drops markedly.

    Importing PIL here (not at module top) keeps Pillow optional for callers
    that only want the automation flow without validity classification.
    """
    from PIL import Image

    img = Image.open(screenshot_path).convert("RGB")
    cx, cy = PLAY_BUTTON_SAMPLE_CENTER
    h = PLAY_BUTTON_SAMPLE_HALF
    box = img.crop((cx - h, cy - h, cx + h, cy + h))
    pixels = list(box.getdata())
    n = len(pixels)
    avg_r = sum(p[0] for p in pixels) / n
    avg_g = sum(p[1] for p in pixels) / n
    avg_b = sum(p[2] for p in pixels) / n
    min_channel = min(avg_r, avg_g, avg_b)
    return "active" if min_channel >= PLAY_BUTTON_ACTIVE_MIN_CHANNEL else "inactive"
