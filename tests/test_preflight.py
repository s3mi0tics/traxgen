# tests/test_preflight.py
"""Offline tests for `scripts/preflight.py`.

Every check is driven through `FakeAdb` from `tests/test_android_foreground.py`
-- the same fake the foreground guard is graded with -- so the argv each check
builds is real and recorded, and only the device's answers are scripted. What
this proves is that each of the five checks *reads its evidence correctly*:
given `adb` saying X, preflight reports X and passes or fails on it. What it
cannot prove is that a live emulator says X in that shape; the two `dumpsys`
fixtures are real captures, and the `adb devices` / `getprop` shapes are the
ones the library has driven since April.

One test is not about preflight's behaviour at all:
`test_every_tap_coordinate_lies_inside_the_tap_space` pins the claim
`environment.md` makes in prose -- that every tap in `android.COORDS` is in
2400x1080 space -- to the constant the geometry check compares against.
"""

from __future__ import annotations

import io
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from PIL import Image

from scripts.preflight import (
    TAP_SPACE,
    Check,
    check_app_in_foreground,
    check_boot_complete,
    check_device_attached,
    check_graphics_errors,
    check_screencap_geometry,
    report,
    run_all,
)
from tests.test_android_foreground import (
    LAUNCHER_DUMP,
    LAUNCHER_PKG,
    FakeAdb,
    ctx_with,
)
from traxgen.android import COORDS, DEFAULT_PACKAGE


def png(size: tuple[int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (40, 44, 52)).save(buffer, format="PNG")
    return buffer.getvalue()


LANDSCAPE = png(TAP_SPACE)
PORTRAIT = png((TAP_SPACE[1], TAP_SPACE[0]))


def clean_log(tmp_path: Path, *lines: str) -> Path:
    log = tmp_path / "emulator.log"
    log.write_text("\n".join(("emulator: INFO: boot completed", *lines)) + "\n")
    return log


# -- the healthy path ------------------------------------------------------------


def test_all_five_pass_on_a_healthy_emulator(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_png=LANDSCAPE)
    checks = run_all(ctx_with(fake), clean_log(tmp_path))
    assert [c.name for c in checks] == [
        "device_attached",
        "boot_complete",
        "graphics_errors",
        "app_in_foreground",
        "screencap_geometry",
    ]
    assert all(c.ok for c in checks), [c.line() for c in checks if not c.ok]
    lines: list[str] = []
    assert report(checks, lines.append) is True
    assert lines[0].startswith("preflight 20") and lines[0].endswith("Z")
    assert lines[-1] == "preflight: all five passed"


def test_the_measured_text_says_what_was_read_not_what_it_means(tmp_path: Path) -> None:
    """Observations #34, as an output contract: each line carries the reading."""
    fake = FakeAdb(screencap_png=LANDSCAPE)
    by_name = {c.name: c for c in run_all(ctx_with(fake), clean_log(tmp_path))}
    assert by_name["device_attached"].measured == "emulator-5554 device"
    assert by_name["boot_complete"].measured == "sys.boot_completed='1'"
    assert by_name["graphics_errors"].measured.startswith("0 x 'bad color buffer' in ")
    assert by_name["app_in_foreground"].measured == f"foreground package: {DEFAULT_PACKAGE}"
    assert by_name["screencap_geometry"].measured == "screencap 2400x1080, tap space 2400x1080"


# -- each check's failure, one at a time ----------------------------------------


@pytest.mark.parametrize(
    ("devices", "measured"),
    [
        ("List of devices attached\n\n", "no emulator listed"),
        ("List of devices attached\nemulator-5554\toffline\n\n", "emulator-5554 offline"),
        ("List of devices attached\nR58M12345\tdevice\n\n", "no emulator listed"),
    ],
)
def test_a_missing_or_offline_emulator_fails_the_device_check(
    devices: str, measured: str
) -> None:
    check = check_device_attached(ctx_with(FakeAdb(devices=devices)))
    assert not check.ok
    assert check.measured == measured


def test_an_unbooted_device_fails_the_boot_check() -> None:
    check = check_boot_complete(ctx_with(FakeAdb(boot_completed="")))
    assert not check.ok
    assert check.measured == "sys.boot_completed=''"


def test_graphics_errors_are_counted_not_just_detected(tmp_path: Path) -> None:
    """Five of them on 2026-08-25; the count is the reading a human compares."""
    log = clean_log(tmp_path, *(["E0825 bad color buffer handle 0x7f"] * 5))
    check = check_graphics_errors(log)
    assert not check.ok
    assert check.measured.startswith("5 x 'bad color buffer' in ")
    assert "cold boot" in check.on_fail


def test_a_missing_emulator_log_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    """A check that cannot measure must not report clean."""
    check = check_graphics_errors(tmp_path / "absent.log")
    assert not check.ok
    assert check.measured.startswith("no emulator log at ")


def test_the_launcher_in_front_fails_the_foreground_check() -> None:
    """The 2026-08-21 failure, caught before a render rather than after one."""
    check = check_app_in_foreground(ctx_with(FakeAdb(foreground_dump=LAUNCHER_DUMP)))
    assert not check.ok
    assert check.measured == f"foreground package: {LAUNCHER_PKG}"


def test_an_unreadable_foreground_dump_fails_rather_than_passes() -> None:
    check = check_app_in_foreground(ctx_with(FakeAdb(foreground_dump="nothing useful\n")))
    assert not check.ok
    assert check.measured == "foreground package: unreadable from dumpsys window"


def test_a_portrait_screencap_fails_the_geometry_check() -> None:
    """The reading that was over-read as 'the device is portrait' on 2026-08-25.
    Here it is reported as what it is -- a 1080x2400 capture -- and fails."""
    check = check_screencap_geometry(ctx_with(FakeAdb(screencap_png=PORTRAIT)))
    assert not check.ok
    assert check.measured == "screencap 1080x2400, tap space 2400x1080"
    assert "launcher" in check.on_fail


def test_a_capture_that_is_not_a_png_fails_without_claiming_a_geometry() -> None:
    check = check_screencap_geometry(ctx_with(FakeAdb(screencap_png=b"not a png")))
    assert not check.ok
    assert check.measured.startswith("screencap returned 9 bytes that PIL could not open")


# -- the wedge signature ----------------------------------------------------------


class HangingShell(FakeAdb):
    """`adb devices` answers; every `adb shell` and `exec-out` times out.

    This is the 2026-08-25 shape exactly: `adb devices` reported `device` while
    WindowManager was wedged and every shell call queued behind it to its 10s
    ceiling. The fake raises what `subprocess.run` raises, so `_run_adb`'s own
    timeout handling is what converts it -- nothing here short-circuits it.
    """

    def __call__(self, cmd: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess:
        argv = [str(part) for part in cmd]
        if argv[1:2] in (["shell"], ["exec-out"]):
            self.calls.append(argv)
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 10.0))
        return super().__call__(cmd, **kwargs)


def test_a_wedged_device_fails_four_checks_and_names_the_signature(tmp_path: Path) -> None:
    fake = HangingShell()
    checks = run_all(ctx_with(fake), clean_log(tmp_path))
    outcomes = {c.name: c.ok for c in checks}
    assert outcomes == {
        "device_attached": True,
        "boot_complete": False,
        "graphics_errors": True,
        "app_in_foreground": False,
        "screencap_geometry": False,
    }
    timed_out = [c for c in checks if not c.ok]
    assert all(c.measured.startswith("adb command failed (timeout:") for c in timed_out)
    assert all("2026-08-25 signature" in c.on_fail for c in timed_out)
    # Nothing was skipped: every adb-backed check ran and recorded its own timeout.
    assert len(fake.calls) == 4


# -- report and the tap-space pin ------------------------------------------------


def test_report_lists_every_failure_by_name_and_returns_false() -> None:
    checks = [
        Check("device_attached", True, "emulator-5554 device"),
        Check("graphics_errors", False, "5 x 'bad color buffer' in /tmp/emulator.log", "stop"),
        Check("app_in_foreground", False, "foreground package: launcher", "expected gravitrax"),
    ]
    lines: list[str] = []
    assert report(checks, lines.append) is False
    assert lines[1] == "PASS device_attached      measured: emulator-5554 device"
    assert lines[2].startswith("FAIL graphics_errors      measured: 5 x")
    assert lines[2].endswith("  -> stop")
    assert lines[-1] == "preflight: FAILED ['graphics_errors', 'app_in_foreground']"


def test_every_tap_coordinate_lies_inside_the_tap_space() -> None:
    """`environment.md` says every tap in `android.COORDS` is in 2400x1080 space.
    Run over the whole table rather than asserted about it (the *Classes*
    discipline): a coordinate outside it would make the geometry check's
    constant and the tap table disagree, silently."""
    width, height = TAP_SPACE
    for name, (x, y) in COORDS.items():
        assert 0 <= x < width and 0 <= y < height, (name, x, y)
