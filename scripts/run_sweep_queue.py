"""Run goal-rotation sweeps back-to-back, unattended: the plan-and-walk-away layer.

Within one sweep the harness already runs itself -- controls at both ends,
budget enforcement, resume after a hole (observations #15). What still needed
a human between sweeps was mechanical: reset the app, wait out the Unity
splash, launch the next rotation, judge the outcome, repeat. This script owns
exactly that chain. `sweep_goal_rotation.py` stays the unit of measurement;
this is the unit of campaign.

Gates (pre-declared)
--------------------
CONTINUE  a sweep that ends INCOMPLETE with no abort gets exactly one
          auto-resume -- the 520-shaped hole is mechanical and so is its
          repair -- and if it is still incomplete, the gap is recorded and the
          NEXT rotation runs anyway: a hole in s=3 says nothing about s=4.
          MODEL_WRONG also continues: it questions the model, not the harness,
          so later rotations remain honest measurements.
STOP      any abort (`harness`, `model`, `budget`), a HARNESS_SUSPECT verdict
          (closing-bracket drift), a sweep that dies without writing results,
          or an unexpected exception. Every later sweep shares the same
          harness and the same conditions, so whatever tripped one would
          silently taint the rest. These are decisions; they stay human.

The queue rewrites `queue_results.json` after every rotation, so a crash or a
stop still leaves a machine-readable account of the campaign so far.

Usage:

    # The remaining unswept rotations, ~18 min each, one launch:
    caffeinate -i uv run python -m scripts.run_sweep_queue 2 3 4 5

Preconditions: emulator booted (each sweep fails fast if not). The app does
NOT need to be at the main menu -- the queue resets it before every sweep,
which also guarantees each sweep's first render meets a fresh app session
whose disclaimer is actually on screen for the unconditional disclaimer tap.

Path: traxgen/scripts/run_sweep_queue.py
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.sweep_goal_rotation import default_output_dir
from scripts.sweep_goal_rotation import main as sweep_main
from traxgen.android import AndroidAutomationError, reset_to_main_menu

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE_DIR = REPO_ROOT / "screenshots" / "sweep_queue"

# reset_to_main_menu() force-stops and relaunches the app; a Unity splash needs
# ~30s before the UI will drive (knowledge/environment.md, learned 2026-08-07
# the hard way).
SETTLE_SECONDS = 35.0

# Sweep verdicts that count as a completed, trustworthy characterization.
OK_VERDICTS = frozenset({"CLEAN_RULE", "LOOKUP_TABLE", "PARTIAL_FUNCTION"})


@dataclass
class RotationOutcome:
    """Everything the queue observed about one rotation's sweep."""

    starter_rot: int
    exit_code: int | None = None
    verdict: str | None = None
    detail: str | None = None
    aborted: str | None = None
    auto_resumed: bool = False
    error: str | None = None
    results_json: str | None = None

    @property
    def ok(self) -> bool:
        """True when this rotation ended with a trustworthy classification."""
        return self.verdict in OK_VERDICTS


def read_verdict(sidecar: Path) -> tuple[str | None, str | None, str | None]:
    """(verdict, detail, aborted) from a sweep sidecar; all None if it is missing."""
    if not sidecar.is_file():
        return (None, None, None)
    meta = json.loads(sidecar.read_text())
    return (meta.get("verdict"), meta.get("verdict_detail"), meta.get("aborted"))


def _write_summary(
    path: Path,
    rotations: Sequence[int],
    outcomes: list[RotationOutcome],
    stopped: str | None,
) -> None:
    """Rewrite the queue sidecar. Called after every rotation so a crash loses nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "rotations": list(rotations),
                "stopped": stopped,
                "outcomes": [dataclasses.asdict(o) for o in outcomes],
            },
            indent=2,
        )
    )


def _judge(outcome: RotationOutcome) -> str | None:
    """The queue's stop rule for one finished rotation; None means keep going."""
    s = outcome.starter_rot
    if outcome.aborted is not None:
        return (
            f"s={s}: sweep aborted ({outcome.aborted}) -- "
            f"{outcome.detail or 'see the sweep output above'}"
        )
    if outcome.verdict == "HARNESS_SUSPECT":
        return f"s={s}: {outcome.detail or 'closing-bracket drift'}"
    if outcome.exit_code != 0 and outcome.verdict is None:
        return f"s={s}: sweep exited {outcome.exit_code} without writing results"
    return None


def run_queue(
    rotations: Sequence[int],
    *,
    run_sweep: Callable[[list[str]], int] = sweep_main,
    reset: Callable[[], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    out_dir_for: Callable[[int], Path] = default_output_dir,
    queue_dir: Path = DEFAULT_QUEUE_DIR,
) -> tuple[list[RotationOutcome], str | None]:
    """Run one sweep per rotation. Returns (outcomes, stop reason or None).

    The keyword seams exist for the offline tests: a scripted fake replaces
    `run_sweep`, recorders replace `reset` and `sleep`, and `out_dir_for`
    redirects sidecars into a tmp dir -- the logic runs for real, the world is
    a test double.
    """
    if reset is None:
        reset = reset_to_main_menu  # resolves its own adb context per call
    outcomes = [RotationOutcome(starter_rot=s) for s in rotations]
    summary = queue_dir / "queue_results.json"
    stopped: str | None = None
    for outcome in outcomes:
        s = outcome.starter_rot
        sidecar = out_dir_for(s) / "results.json"
        outcome.results_json = str(sidecar)
        try:
            print(f"\n=== s={s}: reset + {SETTLE_SECONDS:.0f}s settle ===", file=sys.stderr)
            reset()
            sleep(SETTLE_SECONDS)
            outcome.exit_code = run_sweep(["--starter-rot", str(s)])
            outcome.verdict, outcome.detail, outcome.aborted = read_verdict(sidecar)
            if outcome.verdict == "INCOMPLETE" and outcome.aborted is None:
                # A hole without an abort is mechanical (a 520, a flaky render);
                # so is its repair: one resume pass, then judge honestly.
                print(f"=== s={s}: INCOMPLETE, no abort -- one auto-resume ===", file=sys.stderr)
                outcome.auto_resumed = True
                reset()
                sleep(SETTLE_SECONDS)
                outcome.exit_code = run_sweep(
                    ["--starter-rot", str(s), "--resume", str(sidecar)]
                )
                outcome.verdict, outcome.detail, outcome.aborted = read_verdict(sidecar)
        except AndroidAutomationError as exc:
            outcome.error = f"{type(exc).__name__}: {exc}"
            stopped = f"s={s}: automation error: {exc}"
        except Exception as exc:  # unmodeled failure -> human judgment, not a retry
            outcome.error = f"{type(exc).__name__}: {exc}"
            stopped = f"s={s}: unexpected {type(exc).__name__}: {exc}"
        if stopped is None:
            stopped = _judge(outcome)
        _write_summary(summary, rotations, outcomes, stopped)
        if stopped is not None:
            break
    return outcomes, stopped


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the queue."""
    parser = argparse.ArgumentParser(
        prog="run_sweep_queue",
        description=(
            "Run sweep_goal_rotation for each listed starter rotation, back-to-back, "
            "with a reset + settle before every sweep, one auto-resume for mechanical "
            "holes, and a hard stop on anything that questions the harness."
        ),
    )
    parser.add_argument(
        "rotations",
        type=int,
        nargs="+",
        choices=range(6),
        help="Starter rotations to sweep, in order (e.g. 2 3 4 5).",
    )
    parser.add_argument(
        "--queue-dir",
        type=Path,
        default=DEFAULT_QUEUE_DIR,
        help=f"Where queue_results.json is written (default: {DEFAULT_QUEUE_DIR}).",
    )
    args = parser.parse_args(argv)
    if len(set(args.rotations)) != len(args.rotations):
        parser.error("the same rotation appears twice in the plan")
    return args


def main(
    argv: list[str] | None = None,
    *,
    run_sweep: Callable[[list[str]], int] = sweep_main,
    reset: Callable[[], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    out_dir_for: Callable[[int], Path] = default_output_dir,
) -> int:
    """Entry point. Returns a process exit code."""
    args = _parse_args(argv)
    outcomes, stopped = run_queue(
        args.rotations,
        run_sweep=run_sweep,
        reset=reset,
        sleep=sleep,
        out_dir_for=out_dir_for,
        queue_dir=args.queue_dir,
    )

    print("\nqueue summary:")
    print(f"{'s':>2}  {'verdict':<16} {'resumed':<8} note")
    for o in outcomes:
        note = o.error or o.detail or ""
        print(
            f"{o.starter_rot:>2}  {(o.verdict or '-'):<16} "
            f"{('yes' if o.auto_resumed else '-'):<8} {note}"
        )
    print(f"queue sidecar: {args.queue_dir / 'queue_results.json'}")

    if stopped is not None:
        print(f"\n=> QUEUE STOPPED: {stopped}")
        print(
            "   Rotations after the stop were not run: the stop conditions all question\n"
            "   the shared harness or conditions, so continuing would spend renders on\n"
            "   measurements a human has not yet decided to trust."
        )
        return 1
    gaps = [o for o in outcomes if not o.ok]
    if gaps:
        print(f"\n=> QUEUE DONE WITH GAPS: {', '.join(f's={o.starter_rot}' for o in gaps)}")
        return 1
    print(f"\n=> QUEUE COMPLETE: {len(outcomes)}/{len(outcomes)} rotations classified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
