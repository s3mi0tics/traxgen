"""M6.b: test the parity model's predictions instead of fitting another rule.

The 2026-08-08 starter-rotation sweep established that the starter's
`hex_rotation` moves which directions connect: E rot 1 is active at starter
rotations 0, 2 and 4 and dead at 1, 3 and 5, while NE rot 2 -- dead at every
rotation on 2026-08-07 -- goes active at s=1.

One model fits all 51 measurements taken so far, with no exceptions:

    the starter's exit pair is {E, NW} at even rotations and {NE, W} at odd
    ones, and the goal rotation rule g = (d + 1) % 6 never changes.

Under it, `rot = (d + 1) % 6` was never a partial function. It is a clean
goal-side rule -- the goal points its integrated rail back at the starter --
and what is restricted is the *direction set*, which is a starter-side
property. The 2026-08-07 sweep could not separate the two because the starter
never moved.

Why this script exists
----------------------
That model was fitted to the data, not tested against it, and a model fitted
to every point it was built from explains nothing until it sticks its neck
out. So this script does not sweep: it renders four cells whose verdicts the
model *predicts in advance*, and reports whether each prediction held. The
predictions are declared in `build_cells()` below, before the first render,
and `classify()` compares outcome to prediction rather than deriving a rule
from outcomes.

Note in particular that the starter-rotation sweep's own printed verdict
asserted a mechanism ("connectable directions are {s, s+2} mod 6") that its
own data refutes -- at s=2 that set excludes E, yet E connected. The
pre-declared *trigger* was sound; the explanation attached to it was not.
Comparing against predictions closes that gap: there is no free-text
mechanism claim for the run to get wrong.

The four predictions
--------------------
  s=1, NW rot 3 -> INACTIVE   The app-certified geometry (FLW4TMLP5V) with the
                              starter turned one step. NW leaves the exit pair
                              at odd rotations, so the course the app blessed
                              should stop working. The most counterintuitive
                              prediction here, and the one most worth being
                              wrong about: if it stays active, starter rotation
                              only ever *adds* exits and the parity model dies.
  s=1, E rot 4  -> INACTIVE   Discriminates parity from the rival model in
                              which the direction set is fixed and the goal
                              rotation shifts, g = (d + 1 + 3s) % 6. That rival
                              also explains the even/odd pattern at E rot 1,
                              but it predicts E connects at rot 4 when s=1.
                              Parity says E is simply not an exit at odd s.
  s=1, W rot 4  -> ACTIVE     Completes the odd-parity pair. NE is confirmed;
                              W is the other half and has never been active in
                              any run.
  s=2, NW rot 3 -> ACTIVE     Period-2, not translation. A rotating exit set
                              would send {E, NW} to {NW, SW} at s=2 and leave
                              NW connectable but E dead -- yet E was active at
                              s=2. Parity says s=2 restores the s=0 pair
                              exactly, so the certified geometry should work
                              again.

No early abort on a missed prediction (a departure from the sweep scripts):
each cell tests a different clause, so a miss on one leaves the others
informative. The harness control still aborts, and still brackets the run at
both ends per decisions.md (2026-08-07).

Re-running is cheap: the upload endpoint dedups by content hash, so identical
payloads return identical share codes.

Usage:

    uv run python -m scripts.sweep_parity_model --dry-run
    uv run python -m scripts.sweep_parity_model --no-render
    uv run python -m scripts.sweep_parity_model

Path: traxgen/scripts/sweep_parity_model.py
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.sweep_starter_rotation import (
    DIR_E,
    DIR_NW,
    DIR_W,
    build_variant,
    direction_position,
)
from traxgen.android import (
    AndroidAutomationError,
    assert_emulator_ready,
    render_course,
    resolve_context,
)
from traxgen.generator import generate_minimal
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.serializer import serialize_course
from traxgen.uploader import UploadError, upload_course
from traxgen.validator import validate_strict

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "screenshots" / "parity_model"

DIRECTION_NAMES = ("E", "NE", "NW", "W", "SW", "SE")

# The parity model, as code rather than prose. `EVEN_EXITS` is the pair
# observed at s=0; `ODD_EXITS` is the pair the model claims replaces it.
EVEN_EXITS: frozenset[int] = frozenset({DIR_E, DIR_NW})
ODD_EXITS: frozenset[int] = frozenset({1, DIR_W})  # {NE, W}


def predicted_exits(starter_rot: int) -> frozenset[int]:
    """The directions the parity model says connect at this starter rotation."""
    return EVEN_EXITS if starter_rot % 2 == 0 else ODD_EXITS


def goal_rotation_for(direction: int) -> int:
    """The goal-side rule, unchanged since 2026-08-07: point the rail back."""
    return (direction + 1) % 6


def parity_model_says_active(starter_rot: int, direction: int, goal_rot: int) -> bool:
    """The model's verdict for one cell: right exit, right goal rotation."""
    return direction in predicted_exits(starter_rot) and goal_rot == goal_rotation_for(
        direction
    )


@dataclass
class ParityCell:
    """One cell, its pre-declared prediction, and what a miss would mean."""

    label: str
    kind: str  # 'control' | 'prediction'
    starter_rot: int
    direction: int
    goal_rot: int
    predicted: str  # 'active' | 'inactive'
    tests: str  # the clause this cell puts at risk
    if_wrong: str  # what a missed prediction would imply
    payload_sha256: str | None = None
    payload_bytes: int | None = None
    validator: str | None = None
    code: str | None = None
    upload_error: str | None = None
    validity: str | None = None
    render_error: str | None = None
    screenshot: str | None = None

    @property
    def goal_pos(self) -> HexVector:
        """The goal's local hex position."""
        return direction_position(self.direction)

    @property
    def name(self) -> str:
        """Short filesystem-safe identifier."""
        pos = self.goal_pos
        return f"s{self.starter_rot}_goal_y{pos.y}x{pos.x}_rot{self.goal_rot}"

    @property
    def met(self) -> bool | None:
        """Did the render match the prediction? None until it has rendered."""
        return None if self.validity is None else self.validity == self.predicted


def build_cells() -> list[ParityCell]:
    """The control plus the four predictions, declared before any render."""
    cells = [
        ParityCell(
            label="control",
            kind="control",
            starter_rot=0,
            direction=DIR_NW,
            goal_rot=3,
            predicted="active",
            tests="the harness itself",
            if_wrong="the oracle is not measuring what it should; nothing else counts",
        ),
        ParityCell(
            label="certified_geometry_breaks",
            kind="prediction",
            starter_rot=1,
            direction=DIR_NW,
            goal_rot=3,
            predicted="inactive",
            tests="NW leaves the exit pair at odd starter rotations",
            if_wrong=(
                "starter rotation only ADDS exits and never removes them -- the "
                "parity model is wrong and the exit set grows rather than flips"
            ),
        ),
        ParityCell(
            label="no_goal_rotation_shift",
            kind="prediction",
            starter_rot=1,
            direction=DIR_E,
            goal_rot=4,
            predicted="inactive",
            tests="the goal rule is g = (d + 1) % 6 with no starter term",
            if_wrong=(
                "the rival model holds instead: the direction set is fixed and the "
                "goal rotation shifts, g = (d + 1 + 3s) % 6"
            ),
        ),
        ParityCell(
            label="odd_pair_includes_w",
            kind="prediction",
            starter_rot=1,
            direction=DIR_W,
            goal_rot=4,
            predicted="active",
            tests="the odd-parity exit pair is {NE, W}",
            if_wrong=(
                "the odd pair is not {NE, W}; NE alone was never enough to pin it, "
                "so the exit set has a different shape at odd rotations"
            ),
        ),
        ParityCell(
            label="period_two_not_translation",
            kind="prediction",
            starter_rot=2,
            direction=DIR_NW,
            goal_rot=3,
            predicted="active",
            tests="s=2 restores the s=0 exit pair exactly",
            if_wrong=(
                "rotation is not period-2 in its effect on the exit set, so the "
                "even/odd framing is a coincidence of the cells measured so far"
            ),
        ),
    ]
    # Every prediction must be the model's own verdict -- no hand-entered guesses.
    for cell in cells:
        expected = (
            "active"
            if parity_model_says_active(cell.starter_rot, cell.direction, cell.goal_rot)
            else "inactive"
        )
        if cell.predicted != expected:
            raise RuntimeError(
                f"{cell.label}: declared prediction {cell.predicted!r} disagrees with "
                f"the model's own verdict {expected!r} -- the prediction table and "
                "the model have drifted apart"
            )
    if len({(c.starter_rot, c.direction, c.goal_rot) for c in cells}) != len(cells):
        raise RuntimeError("duplicate geometries in the enumeration")
    return cells


def _render_order(cells: list[ParityCell]) -> list[ParityCell]:
    """Control first, then the falsifier, then the rest as declared."""
    control = [c for c in cells if c.kind == "control"]
    rest = [c for c in cells if c.kind != "control"]
    return control + rest


def classify(cells: list[ParityCell], bracket: str | None) -> tuple[str, str]:
    """Compare each outcome to its prediction. Returns (verdict, detail)."""
    control = next(c for c in cells if c.kind == "control")
    if control.validity != "active" or (bracket is not None and bracket != "active"):
        return (
            "HARNESS_SUSPECT",
            f"control rendered {control.validity!r} at the start and {bracket!r} at "
            "the end; every verdict between them is suspect",
        )

    predictions = [c for c in cells if c.kind == "prediction"]
    unrendered = [c for c in predictions if c.validity is None]
    if unrendered:
        return (
            "INCOMPLETE",
            f"{len(unrendered)} prediction(s) never rendered: "
            + ", ".join(c.label for c in unrendered),
        )

    missed = [c for c in predictions if not c.met]
    if not missed:
        return (
            "MODEL_CONFIRMED",
            f"all {len(predictions)} predictions held -- the exit pair is {{E, NW}} at "
            "even starter rotations and {NE, W} at odd ones, with "
            "g = (d + 1) % 6 unchanged. The rule is total: every direction is "
            "reachable by choosing the starter's rotation",
        )
    return (
        "MODEL_REFUTED",
        f"{len(missed)}/{len(predictions)} predictions missed -- "
        + "; ".join(
            f"{c.label} (predicted {c.predicted}, got {c.validity}): {c.if_wrong}"
            for c in missed
        ),
    )


def _write_sidecar(path: Path, cells: list[ParityCell], meta: dict) -> None:
    """Rewrite the results JSON after every render so an abort loses nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({**meta, "cells": [dataclasses.asdict(c) for c in cells]}, indent=2)
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="sweep_parity_model",
        description="Render four cells whose verdicts the parity model predicts in advance.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and hash every variant and print the prediction table. No network.",
    )
    parser.add_argument(
        "--no-render", action="store_true", help="Upload only; skip the emulator."
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = _parse_args(argv)
    started = time.monotonic()

    base = generate_minimal()
    cells = build_cells()
    print(
        "precondition ok: every declared prediction matches the model's own verdict",
        file=sys.stderr,
    )

    payloads: dict[int, bytes] = {}
    for i, cell in enumerate(cells):
        course = build_variant(
            base,
            starter_rot=cell.starter_rot,
            goal_pos=cell.goal_pos,
            goal_rot=cell.goal_rot,
        )
        try:
            validate_strict(course, PRO_VERTICAL_STARTER_SET)
            cell.validator = "ok"
        except Exception as exc:  # validator raises ValidationError; guard broadly
            cell.validator = f"{type(exc).__name__}: {exc}"
        binary = serialize_course(course)
        payloads[i] = binary
        cell.payload_sha256 = hashlib.sha256(binary).hexdigest()
        cell.payload_bytes = len(binary)

    if len({c.payload_sha256 for c in cells}) != len(cells):
        print("error: payload collision -- cells are not distinct", file=sys.stderr)
        return 1
    print(f"precondition ok: {len(cells)} cells, {len(cells)} distinct payloads",
          file=sys.stderr)

    if serialize_course(
        build_variant(base, starter_rot=0, goal_pos=direction_position(DIR_NW), goal_rot=3)
    ) != serialize_course(base):
        print("error: control is not byte-identical to generate_minimal()", file=sys.stderr)
        return 1
    print("precondition ok: control is byte-identical to generate_minimal()",
          file=sys.stderr)

    if args.dry_run:
        print("\nprediction table (render order):")
        for cell in _render_order(cells):
            print(
                f"  {cell.name:<26} {cell.label:<28} predicts {cell.predicted:<8} "
                f"| {cell.tests}"
            )
        print(f"\n{len(cells)} cells; nothing uploaded or rendered (--dry-run).")
        return 0

    sidecar = args.output_dir / "results.json"
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": {
            "even_exits": sorted(DIRECTION_NAMES[d] for d in EVEN_EXITS),
            "odd_exits": sorted(DIRECTION_NAMES[d] for d in ODD_EXITS),
            "goal_rule": "g = (d + 1) % 6",
        },
    }

    ctx = None
    if not args.no_render:
        try:
            ctx = resolve_context()
            assert_emulator_ready(ctx)
        except AndroidAutomationError as exc:
            print(f"error: emulator not ready: {exc}", file=sys.stderr)
            return 1

    for i, cell in enumerate(cells):
        try:
            cell.code = upload_course(payloads[i], timeout=args.timeout)
        except UploadError as exc:
            cell.upload_error = f"{type(exc).__name__}: {exc}"
            print(f"  {cell.name}: upload failed: {exc}", file=sys.stderr)
            continue
        print(f"  {cell.name}: uploaded -> {cell.code}", file=sys.stderr)

    _write_sidecar(sidecar, cells, meta)
    if args.no_render:
        print(f"\nuploaded; renders skipped. results JSON: {sidecar}")
        return 0

    first_render = True
    for cell in _render_order(cells):
        if cell.code is None:
            continue
        print(f"  rendering {cell.name} ({cell.code})...", file=sys.stderr)
        try:
            result = render_course(
                cell.code,
                ctx=ctx,
                screenshot_dir=args.output_dir,
                screenshot_name=f"{cell.name}_{cell.code}",
                cleanup=True,
                expect_disclaimer=first_render,
                detect_validity=True,
            )
        except AndroidAutomationError as exc:
            cell.render_error = f"{type(exc).__name__}: {exc}"
            print(f"  {cell.name}: render FAILED: {exc}", file=sys.stderr)
            _write_sidecar(sidecar, cells, meta)
            continue
        first_render = False
        cell.validity = result.validity
        cell.screenshot = str(result.screenshot)
        flag = "" if cell.kind == "control" else ("  MET" if cell.met else "  MISSED")
        print(f"  {cell.name}: play button = {cell.validity}{flag}", file=sys.stderr)
        _write_sidecar(sidecar, cells, meta)

        if cell.kind == "control" and cell.validity != "active":
            print(
                "\nHARNESS ABORT: the app-certified control rendered "
                f"{cell.validity!r}. Debug the harness before spending the run.",
                file=sys.stderr,
            )
            _write_sidecar(sidecar, cells, meta)
            print(f"\n=> HARNESS_SUSPECT: control inactive at render 1")
            return 1

    control = next(c for c in cells if c.kind == "control")
    bracket: str | None = None
    if control.code:
        print("  re-rendering the control (closing bracket)...", file=sys.stderr)
        try:
            result = render_course(
                control.code,
                ctx=ctx,
                screenshot_dir=args.output_dir,
                screenshot_name=f"{control.name}_{control.code}_FINAL",
                cleanup=True,
                expect_disclaimer=False,
                detect_validity=True,
            )
            bracket = result.validity
            meta["final_control_validity"] = bracket
            print(f"  closing bracket = {bracket}", file=sys.stderr)
        except AndroidAutomationError as exc:
            meta["final_control_error"] = f"{type(exc).__name__}: {exc}"
            print(f"  closing bracket FAILED: {exc}", file=sys.stderr)

    _write_sidecar(sidecar, cells, meta)

    print("\nprediction results:")
    print(f"{'cell':<26} {'tests':<48} {'predicted':<10} {'got':<10} result")
    for cell in _render_order(cells):
        if cell.kind == "control":
            continue
        got = "RENDER_ERROR" if cell.render_error else (cell.validity or "-")
        outcome = "-" if cell.met is None else ("MET" if cell.met else "MISSED")
        print(
            f"{cell.name:<26} {cell.tests:<48} {cell.predicted:<10} {got:<10} {outcome}"
        )

    verdict, detail = classify(cells, bracket)
    if bracket == "active":
        print("\nharness bracket: control active at both ends of the run")
    print(f"\n=> {verdict}: {detail}")
    print(f"elapsed: {(time.monotonic() - started) / 60:.1f} min")
    print(f"results JSON: {sidecar}")
    return 0 if verdict in ("MODEL_CONFIRMED", "MODEL_REFUTED") else 1


if __name__ == "__main__":
    sys.exit(main())
