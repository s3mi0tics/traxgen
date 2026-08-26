# scripts/mutation_battery.py
"""Apply each declared mutation to production code, run the suite, restore, report.

The committed home for what s25, s26 and s27 each hand-wrote from scratch
(observations #32; Colby's "more than twice becomes a committed script"). Run it
as `uv run python -m scripts.mutation_battery <spec.py>` from the repo root.

A spec is a Python module defining two names:

    CONTROL = {"label": ..., "file": ..., "old": ..., "new": ...}
    MUTATIONS = [{"label": ..., "file": ..., "old": ..., "new": ..., "expect": ...}, ...]

`file` is repo-relative; `old` must occur exactly once in it (observations #8);
`expect` is "caught" (default) or "survive" -- the latter for a mutation whose
*survival* is the claim under test, e.g. a filter clause asserted to be dead.

The rules #32 earned, all structural rather than advisory:

- **(a) A run with no test-summary line aborts the battery** rather than being
  scored. In s25 a bad pytest flag collected nothing, printed no `FAILED`, and
  every mutation was scored "survived"; in s27 the same guard caught its own
  author's regex against `pytest -q`, which prints no `====` banner. Both
  banner-less and bannered summaries parse here; nothing else does.
- **(b) The control's survival halts before any row prints.** A human reading
  twenty rows will not notice that row one is wrong; the script that prints the
  table is the thing that should refuse to.
- **(c) The tree must be at baseline before anything runs**: the suite is green
  and every mutation's `old` matches exactly once. A stranded mutation from an
  interrupted run fails the second check by name, which is what the s27 grep
  over five of eighteen strings failed to do (observations #12, *Classes*).
- **Restoration is three-layered**, because a `finally` does not survive
  `SIGTERM` (s27): the original bytes are held in memory and restored in
  `finally`, on SIGINT/SIGTERM, and checked once more at exit by re-reading the
  file. A restore that does not read back identical is reported, not assumed.

The suite runner is a seam: `Battery(runner=...)` takes any callable returning
the run's combined output, so the offline tests drive it with canned text and
never spawn pytest. That is a *fake* in the test-double sense -- a stand-in the
test controls, the way a Playwright `page.route()` handler stands in for the
real server -- and it is what makes rules (a) and (b) testable in milliseconds.
"""

from __future__ import annotations

import atexit
import os
import re
import runpy
import signal
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Runner = Callable[[], str]

SUMMARY_RE = re.compile(
    r"(?:^|\s)(?:(?P<failed>\d+) failed|(?P<passed>\d+) passed|(?P<errors>\d+) errors?)\b"
)


class BatteryError(RuntimeError):
    """The battery refused to run or to score -- never a mutation result."""


@dataclass(frozen=True, slots=True)
class Mutation:
    label: str
    file: str
    old: str
    new: str
    expect: str = "caught"  # or "survive"

    def __post_init__(self) -> None:
        if self.expect not in ("caught", "survive"):
            raise BatteryError(f"{self.label}: expect must be 'caught' or 'survive'")
        if self.old == self.new:
            raise BatteryError(f"{self.label}: old and new are identical")


@dataclass(frozen=True, slots=True)
class Summary:
    passed: int
    failed: int
    errors: int

    @property
    def caught(self) -> bool:
        return self.failed > 0 or self.errors > 0

    @property
    def ran(self) -> bool:
        """Whether any test executed. `errors` with nothing passed or failed is a
        collection abort: pytest saw an import-time exception and ran nothing."""
        return self.passed > 0 or self.failed > 0


@dataclass(frozen=True, slots=True)
class Result:
    mutation: Mutation
    summary: Summary

    @property
    def outcome(self) -> str:
        """`caught`, `survived`, or `collapsed` -- the last when no test ran at all.

        A collection abort is red on screen and proves nothing about the tests:
        an import-time exception made pytest run zero of them (s28, where a key
        mutation broke a module-level `derive_geometry()` and the whole suite
        was skipped). It is reported under its own name and never counts as a
        catch, so that a row cannot read as coverage it does not have.
        """
        if not self.summary.ran:
            return "collapsed"
        return "caught" if self.summary.caught else "survived"

    @property
    def as_expected(self) -> bool:
        return self.outcome == ("caught" if self.mutation.expect == "caught" else "survived")


def parse_summary(output: str) -> Summary:
    """The counts from pytest's final summary line, or raise (rule a).

    Scans the last lines only, so a `FAILED` word in a traceback cannot pass as
    a summary. Accepts `732 passed, 1 deselected in 9.85s` (what `-q` prints)
    and the `==== 3 failed, 700 passed in 1.2s ====` banner alike.
    """
    for line in reversed(output.strip().splitlines()[-5:]):
        counts = {"passed": 0, "failed": 0, "errors": 0}
        seen = False
        for match in SUMMARY_RE.finditer(line):
            for key in counts:
                if match.group(key) is not None:
                    counts[key] = int(match.group(key))
                    seen = True
        if seen and re.search(r"\bin \d+(\.\d+)?s\b", line):
            return Summary(**counts)
    raise BatteryError(
        "no pytest summary line in the run's output -- a run that cannot be read "
        "is not scored (observations #32, rule a). Last lines were:\n"
        + "\n".join(output.strip().splitlines()[-5:])
    )


def default_runner(pytest_args: tuple[str, ...]) -> Runner:
    """The real thing: pytest in a subprocess, stdout and stderr combined.

    `PYTHONDONTWRITEBYTECODE` is set for a measured reason, not caution. Without
    it the subprocess compiles the *mutated* source to a `.pyc`, and when the
    battery restores the source in the same clock second the two share an mtime
    -- so CPython's mtime-based `.pyc` invalidation does not fire and every later
    interpreter (the next mutation's run, or a plain `pytest` afterward) imports
    the mutated bytecode while the source reads clean. Found in s28 when the
    suite went red against a byte-perfect `graph.py`; the restore was correct and
    the cache was poisoned. No bytecode written means nothing to go stale.
    """

    def run() -> str:
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *pytest_args],
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"},
        )
        return completed.stdout + completed.stderr

    return run


@dataclass
class Battery:
    root: Path
    control: Mutation
    mutations: tuple[Mutation, ...]
    runner: Runner
    report: Callable[[str], None] = print
    # Off in the offline tests: installing SIGINT/SIGTERM handlers and an
    # `atexit` hook inside the pytest process that is testing this class would
    # replace pytest's own handling. The restore logic they call is tested
    # directly instead.
    install_signal_handlers: bool = True
    _originals: dict[Path, str] = field(default_factory=dict, init=False)

    # -- restoration -----------------------------------------------------

    def _hold(self, path: Path) -> str:
        if path not in self._originals:
            self._originals[path] = path.read_text(encoding="utf-8")
        return self._originals[path]

    @staticmethod
    def _purge_bytecode(path: Path) -> None:
        """Remove any compiled `.pyc` for `path`, so a restore cannot be shadowed.

        `default_runner` already prevents the write; this is the second layer, for
        a caller that supplies a runner which does compile. It removes the file's
        `__pycache__/<stem>.*.pyc` entries -- absent is fine, the loop is empty.
        """
        cache = path.parent / "__pycache__"
        for pyc in cache.glob(f"{path.stem}.*.pyc"):
            pyc.unlink()

    def restore_all(self) -> list[str]:
        """Put every held file back, purge its bytecode, and re-read it; return the
        files that did not read back identical."""
        mismatched: list[str] = []
        for path, original in self._originals.items():
            path.write_text(original, encoding="utf-8")
            self._purge_bytecode(path)
            if path.read_text(encoding="utf-8") != original:
                mismatched.append(str(path))
        return mismatched

    def _install_signal_restore(self) -> None:
        def handler(signum: int, _frame: Any) -> None:
            mismatched = self.restore_all()
            self.report(f"signal {signum}: restored {len(self._originals)} file(s)")
            if mismatched:
                self.report(f"RESTORE MISMATCH: {mismatched}")
            sys.exit(128 + signum)

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, handler)
        atexit.register(self._verify_restored_at_exit)

    def _verify_restored_at_exit(self) -> None:
        stranded = [
            str(p) for p, o in self._originals.items() if p.read_text(encoding="utf-8") != o
        ]
        if stranded:
            self.report(f"AT EXIT: mutation still on disk in {stranded} -- restoring")
            self.restore_all()

    # -- the run ---------------------------------------------------------

    def preflight(self) -> None:
        """Rule (c): every `old` matches exactly once, and the baseline is green."""
        for mutation in (self.control, *self.mutations):
            text = (self.root / mutation.file).read_text(encoding="utf-8")
            count = text.count(mutation.old)
            if count != 1:
                raise BatteryError(
                    f"preflight: {mutation.label!r} -- `old` matches {count} times in "
                    f"{mutation.file}, expected exactly one. Either a mutation is stranded "
                    "on disk from an interrupted run or the spec is stale."
                )
        baseline = parse_summary(self.runner())
        if baseline.caught:
            raise BatteryError(
                f"preflight: baseline is red ({baseline.failed} failed, {baseline.errors} "
                "errors) -- nothing is scored against a red tree"
            )

    def _score(self, mutation: Mutation) -> Result:
        path = self.root / mutation.file
        original = self._hold(path)
        if original.count(mutation.old) != 1:
            raise BatteryError(f"{mutation.label!r}: `old` no longer matches exactly once")
        path.write_text(original.replace(mutation.old, mutation.new), encoding="utf-8")
        try:
            summary = parse_summary(self.runner())
        finally:
            path.write_text(original, encoding="utf-8")
            self._purge_bytecode(path)
            if path.read_text(encoding="utf-8") != original:
                raise BatteryError(f"{mutation.label!r}: restore did not read back identical")
        return Result(mutation, summary)

    def run(self) -> list[Result]:
        """Preflight, control, then every mutation. Raises rather than mis-scoring."""
        if self.install_signal_handlers:
            self._install_signal_restore()
        self.preflight()
        control = self._score(self.control)
        if control.outcome == "collapsed":
            raise BatteryError(
                f"CONTROL COLLAPSED THE SUITE: {self.control.label!r} produced a collection "
                f"error and no test ran ({control.summary.errors} errors, 0 passed). That "
                "proves the import broke, not that a test catches the mutation -- pick a "
                "control a named test is known to fail on."
            )
        if control.outcome != "caught":
            raise BatteryError(
                f"CONTROL SURVIVED: {self.control.label!r} was not caught "
                f"({control.summary.passed} passed, 0 failed). The battery cannot tell a "
                "caught mutation from a survived one, so no row is scored (observations "
                "#32, rule b)."
            )
        self.report(f"control {self.control.label!r}: caught ({control.summary.failed} failed)")
        results: list[Result] = []
        for mutation in self.mutations:
            result = self._score(mutation)
            flag = "" if result.as_expected else "   <-- UNEXPECTED"
            self.report(
                f"{result.outcome:<9} {mutation.label:<48} expected {mutation.expect:<8}"
                f"({result.summary.failed} failed, {result.summary.errors} errors){flag}"
            )
            results.append(result)
        caught = sum(1 for r in results if r.outcome == "caught")
        collapsed = sum(1 for r in results if r.outcome == "collapsed")
        unexpected = [r.mutation.label for r in results if not r.as_expected]
        self.report("")
        self.report(
            f"{caught} of {len(results)} caught"
            + (f", {collapsed} collapsed the suite" if collapsed else "")
            + f"; unexpected: {unexpected or 'none'}"
        )
        return results


def load_spec(spec_path: Path) -> tuple[Mutation, tuple[Mutation, ...]]:
    namespace = runpy.run_path(str(spec_path))
    control = Mutation(**namespace["CONTROL"])
    mutations = tuple(Mutation(**m) for m in namespace["MUTATIONS"])
    return control, mutations


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    spec_path = Path(args[0])
    pytest_args = tuple(args[2:]) if len(args) > 1 and args[1] == "--" else tuple(args[1:])
    root = Path.cwd()
    control, mutations = load_spec(spec_path)
    battery = Battery(
        root=root, control=control, mutations=mutations, runner=default_runner(pytest_args)
    )
    try:
        results = battery.run()
    except BatteryError as err:
        print(f"ABORT: {err}", file=sys.stderr)
        return 1
    return 0 if all(r.as_expected for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
