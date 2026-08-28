# scripts/emulator.py
"""Boot and kill the render AVD -- the two ends of a working session.

    uv run python -m scripts.emulator boot   # session open, only if this session will render
    uv run python -m scripts.emulator kill   # session close, first step

Session scope is a locked decision (`decisions.md`, 2026-08-26): cold at open,
dead at close, nothing per-campaign. What per-session cycling does *not* buy is
recorded there rather than implied -- it does nothing about drift *within* a
session, which is what running `scripts/preflight.py` before every campaign is
for.

Three things here were each paid for by a failure:

1. **The boot wait is bounded and never suppresses stderr.** Observations #25
   is an unbounded `until` loop with `2>/dev/null` wrapped around a bare `adb`:
   "command not found" went to /dev/null and the loop spun forever, presenting
   as a hang with no output. A timeout here exits non-zero and prints the last
   thing adb actually said.

2. **Teardown asks the emulator to quit, then confirms the process died.**
   `adb emu kill` rather than signalling `qemu-system` directly, because a
   direct kill can strand the AVD's lock file and make the *next* boot fail as
   something unrelated.

3. **An interrupted boot kills what it launched.** The emulator is spawned in
   its own session and outlives this process by design, so a wait abandoned
   partway leaves a 2 GB orphan that is neither cold nor known-good -- and it
   quietly breaks the `bad color buffer`-starts-at-0 invariant that makes a
   nonzero count later in the session unambiguous. `finally` alone does not
   survive SIGTERM (#32 rule (d), learned when an interrupted mutation battery
   stranded a mutation on disk), so the guard is the three layers that battery
   ended up with: the normal path, signal handlers, and an `atexit` backstop.

**Scope, stated rather than implied.** `boot` confirms the *device* -- attached,
booted, zero graphics errors -- by running preflight's first three checks. It
deliberately does not run the last two. Right after a cold boot the phone
launcher is in front rather than GraviTrax, and a geometry reading taken
against the launcher measures the launcher (`environment.md`, Gotchas). Those
two are campaign-time checks; run the whole of `scripts/preflight.py` before
each campaign.
"""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from scripts.preflight import (
    DEFAULT_EMULATOR_LOG,
    Check,
    check_boot_complete,
    check_device_attached,
    check_graphics_errors,
)
from traxgen.android import (
    DEFAULT_ANDROID_HOME,
    DEFAULT_PACKAGE,
    AdbCommandFailedError,
    AdbContext,
    AdbNotFoundError,
    _run_adb,
    resolve_context,
)

DEFAULT_AVD = "traxgen_m6c"

# What `pgrep -f` is matched against. The emulator process is `qemu-system-aarch64`
# on this Mac; the prefix is used so an SDK update that renames the suffix does not
# silently turn the teardown confirmation into "nothing was running".
QEMU_PATTERN = "qemu-system"

BOOT_TIMEOUT = 300.0
BOOT_POLL_INTERVAL = 2.0
KILL_TIMEOUT = 60.0
KILL_POLL_INTERVAL = 1.0


class EmulatorLifecycleError(Exception):
    """A boot or kill failed in a way worth naming rather than swallowing."""


class EmulatorNotFoundError(EmulatorLifecycleError):
    """The emulator binary is not where ANDROID_HOME says it is."""


class BootTimeoutError(EmulatorLifecycleError):
    """`sys.boot_completed` never reached 1 inside the bound."""


class AlreadyRunningError(EmulatorLifecycleError):
    """An emulator is already up, and a cold boot means nothing is."""


def resolve_emulator_binary(android_home: Path | None = None) -> Path:
    """Locate the emulator binary the way `android.resolve_context` locates adb.

    `$ANDROID_HOME` is not exported in a default shell, so a command written as
    `$ANDROID_HOME/emulator/emulator` expands to `/emulator/emulator` -- and
    because the documented invocation redirects into a log, it fails *silently*
    while appearing to background successfully (`environment.md`, Gotchas).
    """
    home = android_home or Path(os.environ.get("ANDROID_HOME", DEFAULT_ANDROID_HOME))
    binary = home / "emulator" / "emulator"
    if not binary.is_file():
        raise EmulatorNotFoundError(
            f"emulator not found at {binary}. Set ANDROID_HOME or pass android_home."
        )
    return binary


def running_emulator_pids(*, run: Callable[..., object] = subprocess.run) -> tuple[str, ...]:
    """PIDs of running `qemu-system*` processes.

    `pgrep` exits 1 when nothing matches, which is the expected case at open and
    the success case at close -- so a non-zero exit here is data, not an error.
    """
    result = run(["pgrep", "-f", QEMU_PATTERN], capture_output=True, text=True, check=False)
    return tuple(pid for pid in result.stdout.split() if pid.strip())


def spawn_emulator(
    binary: Path,
    avd: str,
    log_path: Path,
    *,
    popen: Callable[..., object] = subprocess.Popen,
) -> object:
    """Launch the AVD cold and detached, with its log truncated.

    Truncating the log is what makes preflight's "zero graphics errors *since
    boot*" an honest sentence rather than a count over every session this
    machine has ever run.

    `start_new_session=True` puts the emulator in its own process group, so a
    Ctrl-C in this terminal does not reach it. That is deliberate rather than
    tidy: teardown here goes through `adb emu kill`, and an implicit SIGINT
    arriving first is exactly the direct signal that can strand the AVD lock.
    """
    with log_path.open("wb") as log:
        return popen(
            [str(binary), "-avd", avd, "-no-snapshot-load"],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def wait_for_boot(
    ctx: AdbContext,
    *,
    timeout: float = BOOT_TIMEOUT,
    interval: float = BOOT_POLL_INTERVAL,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Poll `sys.boot_completed` until it reads 1. Return the elapsed seconds.

    Bounded, and the last thing adb actually said is carried into the timeout
    message rather than discarded. Observations #25 is the version of this loop
    that had neither property.
    """
    start = clock()
    last = "adb was never reached"
    while True:
        try:
            value = _run_adb(ctx, "shell", "getprop", "sys.boot_completed").strip()
        except AdbCommandFailedError as exc:
            last = (exc.stderr or "").strip() or f"adb exited {exc.returncode}"
        else:
            if value == "1":
                return clock() - start
            last = f"sys.boot_completed={value!r}"
        elapsed = clock() - start
        if elapsed >= timeout:
            raise BootTimeoutError(
                f"sys.boot_completed did not reach 1 within {timeout:.0f}s "
                f"({elapsed:.1f}s elapsed); last: {last}"
            )
        sleep(interval)


@dataclass
class TeardownGuard:
    """Run `teardown` exactly once, unless it is disarmed first.

    Idempotence is the point, not an optimisation: three layers fire this and
    two of them can fire in the same process, so without it a single interrupt
    would tear down twice and report two contradictory outcomes.
    """

    teardown: Callable[[], None]
    spent: bool = False

    def fire(self) -> bool:
        """Run the teardown unless it already ran or was disarmed."""
        if self.spent:
            return False
        self.spent = True
        self.teardown()
        return True

    def disarm(self) -> None:
        """The guarded thing succeeded -- leave the emulator up."""
        self.spent = True


@contextmanager
def guarded(
    teardown: Callable[[], None],
    *,
    set_handler: Callable[..., object] = signal.signal,
    get_handler: Callable[[int], object] = signal.getsignal,
    register_atexit: Callable[..., object] = atexit.register,
    unregister_atexit: Callable[..., object] = atexit.unregister,
    resignal: Callable[[int], None] = signal.raise_signal,
) -> Iterator[TeardownGuard]:
    """Wire a `TeardownGuard` to all three exit paths for the duration of the block.

    Each layer covers what the one before it cannot:

    * the ``finally`` covers every ordinary exit that is not an explicit
      ``disarm()`` -- an exception, a Ctrl-C Python turned into
      ``KeyboardInterrupt``, or a plain early ``return``;
    * the signal handlers cover **SIGTERM**, which never becomes an exception at
      all -- no ``finally`` in this process would ever run;
    * ``atexit`` covers an interpreter shutdown neither of the above observed.

    The handlers are why this is a context manager rather than a ``try/finally``:
    they must be installed around the block and the *previous* handler restored
    afterwards, not assumed to have been the default. After firing, the handler
    restores the previous disposition and re-raises the same signal, so the
    process still dies of what it was sent rather than exiting 0.
    """
    guard = TeardownGuard(teardown)
    previous: dict[int, object] = {}

    def handler(signum: int, _frame: object) -> None:
        guard.fire()
        set_handler(signum, previous.get(signum, signal.SIG_DFL))
        resignal(signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = get_handler(sig)
            set_handler(sig, handler)
        except ValueError:
            # Not the main thread. Two layers instead of three, rather than a crash.
            previous.pop(sig, None)

    register_atexit(guard.fire)
    try:
        yield guard
    finally:
        # Commit-or-rollback, not try/except: leaving this block *without* having
        # disarmed is a teardown, whatever the exit route. An earlier version
        # fired only on an exception, which made `disarm()` decorative -- a
        # normal exit tore nothing down either way -- and would have leaked the
        # emulator on any early `return` a later refactor added. The mutation
        # battery found that; no test did, because both paths looked identical.
        guard.fire()
        for sig, prev in previous.items():
            set_handler(sig, prev)
        unregister_atexit(guard.fire)


@dataclass(frozen=True, slots=True)
class KillOutcome:
    """What the teardown asked for and what it then measured."""

    requested: bool
    died: bool
    elapsed: float
    survivors: tuple[str, ...]
    detail: str

    def line(self) -> str:
        status = "PASS" if self.died else "FAIL"
        if not self.requested:
            measured = self.detail
        elif self.died:
            measured = f"{self.detail}; process gone after {self.elapsed:.1f}s"
        else:
            measured = f"{self.detail}; survivors {' '.join(self.survivors)}"
        return f"{status} {'emulator_down':<20} measured: {measured}"


def kill_emulator(
    ctx: AdbContext,
    *,
    timeout: float = KILL_TIMEOUT,
    interval: float = KILL_POLL_INTERVAL,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    run: Callable[..., object] = subprocess.run,
) -> KillOutcome:
    """Ask the emulator to quit, then confirm `qemu-system` is actually gone.

    A failed `adb emu kill` is reported and then *waited out* rather than
    raised: the command failing and the emulator staying up are different
    claims, and only `pgrep` can settle the second one.
    """
    start = clock()
    if not running_emulator_pids(run=run):
        return KillOutcome(False, True, 0.0, (), "no qemu-system process was running")

    detail = "adb emu kill accepted"
    try:
        _run_adb(ctx, "emu", "kill")
    except AdbCommandFailedError as exc:
        said = (exc.stderr or "").strip()[:120] or f"exit {exc.returncode}"
        detail = f"adb emu kill failed ({said}); waited on pgrep anyway"

    while True:
        survivors = running_emulator_pids(run=run)
        elapsed = clock() - start
        if not survivors:
            return KillOutcome(True, True, elapsed, (), detail)
        if elapsed >= timeout:
            return KillOutcome(
                True, False, elapsed, survivors, f"{detail}; still up after {timeout:.0f}s"
            )
        sleep(interval)


def boot(
    *,
    avd: str = DEFAULT_AVD,
    android_home: Path | None = None,
    log_path: Path = DEFAULT_EMULATOR_LOG,
    package: str = DEFAULT_PACKAGE,
    timeout: float = BOOT_TIMEOUT,
    interval: float = BOOT_POLL_INTERVAL,
    ctx: AdbContext | None = None,
    out: Callable[[str], None] = print,
    popen: Callable[..., object] = subprocess.Popen,
    run: Callable[..., object] = subprocess.run,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Check]:
    """Cold-boot the AVD, time it, and confirm the device is up.

    Returns preflight's three device-level checks. The elapsed boot time is
    printed because `decisions.md` declares the cold-boot cost at ~2 minutes and
    says outright it has never been measured on this AVD -- if it is much
    cheaper, per-campaign cycling deserves the second look that row names.
    """
    binary = resolve_emulator_binary(android_home)
    # A real default, overridable per call site -- the same shape as `AdbContext`'s
    # own seams, so the whole flow runs offline without patching resolution.
    ctx = ctx or resolve_context(android_home=android_home, package=package)

    already = running_emulator_pids(run=run)
    if already:
        raise AlreadyRunningError(
            f"qemu-system already running (pid {' '.join(already)}), and a cold boot means "
            "nothing is. Run `kill` first, or leave the existing one if it is this session's."
        )

    out(f"booting {avd} cold; log -> {log_path}")
    spawn_emulator(binary, avd, log_path, popen=popen)

    def teardown() -> None:
        out("interrupted before boot completed -- tearing down what was launched")
        out(kill_emulator(ctx, clock=clock, sleep=sleep, run=run).line())

    with guarded(teardown) as guard:
        elapsed = wait_for_boot(ctx, timeout=timeout, interval=interval, clock=clock, sleep=sleep)
        guard.disarm()

    out(f"boot_completed in {elapsed:.1f}s")
    checks = [
        check_device_attached(ctx),
        check_boot_complete(ctx),
        check_graphics_errors(log_path),
    ]
    for check in checks:
        out(check.line())
    passed = all(check.ok for check in checks)
    out("boot: " + ("device checks passed" if passed else "DEVICE CHECKS FAILED"))
    out(
        "preflight's app_in_foreground and screencap_geometry are campaign-time checks "
        "(the launcher is in front on a cold boot) -- run scripts/preflight.py before each campaign"
    )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    boot_parser = sub.add_parser("boot", help="cold-boot the AVD and confirm the device is up")
    boot_parser.add_argument("--avd", default=DEFAULT_AVD)
    boot_parser.add_argument("--log", type=Path, default=DEFAULT_EMULATOR_LOG)
    boot_parser.add_argument("--package", default=DEFAULT_PACKAGE)
    boot_parser.add_argument("--timeout", type=float, default=BOOT_TIMEOUT)

    kill_parser = sub.add_parser("kill", help="ask the AVD to quit and confirm the process died")
    kill_parser.add_argument("--package", default=DEFAULT_PACKAGE)
    kill_parser.add_argument("--timeout", type=float, default=KILL_TIMEOUT)

    args = parser.parse_args(argv)
    try:
        if args.command == "boot":
            checks = boot(
                avd=args.avd, log_path=args.log, package=args.package, timeout=args.timeout
            )
            return 0 if all(check.ok for check in checks) else 1
        outcome = kill_emulator(resolve_context(package=args.package), timeout=args.timeout)
        print(outcome.line())
        return 0 if outcome.died else 1
    except (EmulatorLifecycleError, AdbNotFoundError) as exc:
        print(f"FAIL {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
