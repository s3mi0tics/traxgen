# scripts/preflight.py
"""Five checks before a render campaign spends anything -- each has broken one.

    uv run python -m scripts.preflight            # from the repo root
    uv run python -m scripts.preflight --log /tmp/emulator.log --package com.ravensburger.gravitrax

Exit 0 only when all five pass. Every line prints what was **measured** and
nothing else; the trailing "->" on a failure points at the recorded prior
instance of that signature, which is a place to look, not a diagnosis of this
one (observations #34: measured and inferred in separate sentences, and only
the measured one in a file).

The five, in the order they were hand-written during the 2026-08-25 evening
that lost two campaigns to the environment (`docs/refs/testing-against-a-live-app.md`):

1. **device attached** -- `adb devices` lists an `emulator-*` in state `device`.
2. **boot complete** -- `getprop sys.boot_completed` is `1`.
3. **zero graphics errors since boot** -- `bad color buffer` does not occur in
   the emulator log. This is the one line that would have caught the second
   2026-08-25 failure before seven uploads. "Since boot" holds only when the
   emulator was launched with `environment.md`'s command, which truncates the
   log; a missing log is a failure here, not a pass, because a check that
   cannot measure must not report clean.
4. **app in foreground** -- `dumpsys window` names `ctx.package`. The
   2026-08-21 launcher failure, as a pre-flight rather than a mid-run raise.
5. **screencap geometry equals the tap space** -- a capture is `2400x1080`,
   the space every `android.COORDS` entry is written in (pinned by a test).
   Checked *after* the foreground check on purpose: the phone launcher is
   portrait-locked, so a reading taken with it in front measures the launcher.

What this does not do, stated rather than implied: it does not launch the app,
reset it, or repair anything -- a pre-flight that silently fixes what it finds
makes the precondition invisible again, which is how the launcher failure was
lost the first time (`decisions.md`, s23). And it is a signature check like
every guard in `android.py`: it knows five ways the environment has broken and
is blind to the sixth.

`run_all` takes an `AdbContext`, so the offline tests drive every check through
the same `FakeAdb` the foreground guard's tests use -- the adb calls are real
argv, recorded, and answered from a script. Only `main` touches a real adb.
"""

from __future__ import annotations

import argparse
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from traxgen.android import (
    DEFAULT_PACKAGE,
    AdbCommandFailedError,
    AdbContext,
    AdbNotFoundError,
    _run_adb,
    _run_adb_binary,
    read_foreground_package,
    resolve_context,
)

# Width, height of the space `android.COORDS` is written in. Measured 2026-08-25:
# GraviTrax takes landscape itself and `screencap` returns (2400, 1080) with
# nothing touched (`environment.md`). A test asserts every COORDS entry lies
# inside it, so this constant and the tap table cannot drift apart silently.
TAP_SPACE: tuple[int, int] = (2400, 1080)
DEFAULT_EMULATOR_LOG = Path("/tmp/emulator.log")
GRAPHICS_ERROR_SIGNATURE = "bad color buffer"

WEDGE_HINT = (
    "an adb shell timeout with `adb devices` still healthy was the 2026-08-25 signature of "
    "the graphics backend losing its buffers after the window was rotated/resized; a cold "
    "boot cleared it then (environment.md, Gotchas)"
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    measured: str
    on_fail: str = ""

    def line(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        tail = f"  -> {self.on_fail}" if (not self.ok and self.on_fail) else ""
        return f"{status} {self.name:<20} measured: {self.measured}{tail}"


def _adb_failure(name: str, exc: AdbCommandFailedError) -> Check:
    stderr = (exc.stderr or "").strip()
    timed_out = stderr.startswith("timeout")
    return Check(
        name,
        False,
        f"adb command failed ({stderr[:120] or 'no stderr'})",
        WEDGE_HINT if timed_out else "adb itself failed; nothing below it was measured",
    )


def check_device_attached(ctx: AdbContext) -> Check:
    try:
        out = _run_adb(ctx, "devices")
    except AdbCommandFailedError as exc:
        return _adb_failure("device_attached", exc)
    rows = [line.split("\t") for line in out.splitlines() if "\t" in line]
    emulators = [(serial, state) for serial, state in rows if serial.startswith("emulator-")]
    ready = [serial for serial, state in emulators if state == "device"]
    measured = ", ".join(f"{s} {st}" for s, st in emulators) or "no emulator listed"
    return Check(
        "device_attached",
        bool(ready),
        measured,
        "boot the AVD with environment.md's command; an `offline` state is not attached",
    )


def check_boot_complete(ctx: AdbContext) -> Check:
    try:
        boot = _run_adb(ctx, "shell", "getprop", "sys.boot_completed").strip()
    except AdbCommandFailedError as exc:
        return _adb_failure("boot_complete", exc)
    return Check(
        "boot_complete",
        boot == "1",
        f"sys.boot_completed={boot!r}",
        "a cold-booted AVD needs real time before it drives (environment.md, Gotchas)",
    )


def check_graphics_errors(log_path: Path) -> Check:
    if not log_path.is_file():
        return Check(
            "graphics_errors",
            False,
            f"no emulator log at {log_path}",
            "the documented boot command redirects into that path; without the log this "
            "check cannot measure, and a check that cannot measure does not pass",
        )
    count = log_path.read_text(encoding="utf-8", errors="replace").count(GRAPHICS_ERROR_SIGNATURE)
    return Check(
        "graphics_errors",
        count == 0,
        f"{count} x {GRAPHICS_ERROR_SIGNATURE!r} in {log_path}",
        "stop, do not retry: a climbing count preceded every adb timeout on 2026-08-25, "
        "and only a cold boot cleared it (environment.md, Gotchas)",
    )


def check_app_in_foreground(ctx: AdbContext) -> Check:
    try:
        found = read_foreground_package(ctx)
    except AdbCommandFailedError as exc:
        return _adb_failure("app_in_foreground", exc)
    measured = f"foreground package: {found or 'unreadable from dumpsys window'}"
    return Check(
        "app_in_foreground",
        found == ctx.package,
        measured,
        f"expected {ctx.package}; `reset_to_main_menu()` establishes it, this check does not",
    )


def check_screencap_geometry(ctx: AdbContext) -> Check:
    try:
        png = _run_adb_binary(ctx, "exec-out", "screencap", "-p")
    except AdbCommandFailedError as exc:
        return _adb_failure("screencap_geometry", exc)
    try:
        size = Image.open(io.BytesIO(png)).size
    except Exception as exc:  # PIL's error types are not a stable surface to name
        return Check(
            "screencap_geometry",
            False,
            f"screencap returned {len(png)} bytes that PIL could not open ({exc})",
            "the capture itself is broken; nothing about geometry was measured",
        )
    return Check(
        "screencap_geometry",
        size == TAP_SPACE,
        f"screencap {size[0]}x{size[1]}, tap space {TAP_SPACE[0]}x{TAP_SPACE[1]}",
        "if the app was not in front, this measured the launcher, which is portrait-locked; "
        "if it was, every tap in android.COORDS would land off-target",
    )


def run_all(ctx: AdbContext, log_path: Path = DEFAULT_EMULATOR_LOG) -> list[Check]:
    """All five, always, in the documented order. Nothing is skipped on failure:
    a wedged device costs one adb timeout per check and prints the signature
    each time, which is the measurement worth having."""
    return [
        check_device_attached(ctx),
        check_boot_complete(ctx),
        check_graphics_errors(log_path),
        check_app_in_foreground(ctx),
        check_screencap_geometry(ctx),
    ]


def report(checks: list[Check], out: Callable[[str], None] = print) -> bool:
    out(datetime.now(UTC).strftime("preflight %Y-%m-%d %H:%M:%SZ"))
    for check in checks:
        out(check.line())
    failed = [c.name for c in checks if not c.ok]
    out("preflight: " + ("all five passed" if not failed else f"FAILED {failed}"))
    return not failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, default=DEFAULT_EMULATOR_LOG)
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    args = parser.parse_args(argv)
    try:
        ctx = resolve_context(package=args.package)
    except AdbNotFoundError as exc:
        print(f"FAIL adb_resolved         measured: {exc}")
        return 1
    return 0 if report(run_all(ctx, args.log)) else 1


if __name__ == "__main__":
    raise SystemExit(main())

