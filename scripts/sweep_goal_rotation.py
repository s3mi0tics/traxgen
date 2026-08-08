"""M6.b: sweep GOAL_RAIL position x rotation and read the app's validity oracle.

Generalizes the one app-certified geometry (STARTER@(0,0) rot 0 +
GOAL_RAIL@(-1,0) rot 3, `rail_count = 0`, share code FLW4TMLP5V) into a
general relative-position -> required-goal-rotation mapping. That mapping
feeds M5.c connection rules, closes the rest of M6.b, and bears on open
unknown #7.

Why one observation isn't enough
--------------------------------
The goal sits at HEX_DIRECTIONS[2] (NW) from the starter and carries
rotation 3. Both of these fit that single data point and disagree
everywhere else:

    rot = (d + 1) % 6     ->  2 + 1 = 3
    rot = (5 - d) % 6     ->  5 - 2 = 3

The general clean-rule family is `rot = (a*d + b) % 6` with a in {+1, -1}:
twelve candidates. Six observations -- one per adjacent direction -- pin it
to at most one.

Enumeration domain (design decision, pre-declared)
--------------------------------------------------
Six adjacent positions x six rotations = 36 cells. Distance-2 positions are
deliberately NOT swept as part of the main body: the established mechanism
is tile adjacency plus goal rotation at `rail_count = 0`, so at distance 2
no rotation should connect. Sweeping it would test a different hypothesis
(that GOAL_RAIL's integrated rail spans two hexes) and triple the cost.

Two controls guard against measuring the wrong thing (observations #12):

  * positive control -- the app-certified cell (-1,0) rot 3, which is
    asserted byte-identical to `generate_minimal()` before anything is
    uploaded, and is rendered FIRST. If it comes back inactive the harness
    is lying and the run aborts before spending 41 renders.
  * negative control -- one distance-2 position x six rotations, expected
    all-inactive. If any goes active, the adjacency model itself is wrong
    and the run aborts.

Pre-declared falsification (design decision)
--------------------------------------------
  CLEAN_RULE       exactly one active rotation per direction, and the six
                   fit a single (a, b) affine rule.
  LOOKUP_TABLE     exactly one active per direction, no affine fit.
  PARTIAL_FUNCTION some directions have zero active rotations. A legitimate
                   outcome, not a failure: GraviTrax has vertical structure
                   and the starter ejects in a specific direction, so a goal
                   uphill of the starter may simply be unreachable.
  MODEL_WRONG      any direction has more than one active rotation (rotation
                   is not the sole determinant), or the distance-2 control
                   goes active.
  HARNESS_SUSPECT  the positive control is inactive.

Pre-declared time budget (observation #4): 90 minutes wall clock, enforced
between renders via --budget-minutes. Re-running after an abort is cheap --
the upload endpoint dedups by content hash, so identical payloads return
identical share codes -- and --resume skips cells already rendered.

Recording (design decision)
---------------------------
Results are text: one JSON sidecar rewritten after every render, so a crash
or a budget abort still leaves everything observed so far. `inactive` and
`render_error` are recorded as distinct states rather than collapsed.
Screenshots are pruned at the end to failures, the positive control, and any
active cell (plan.md's deferred "record outcomes as text" item);
--keep-all-screenshots overrides.

Note: this script does NOT use `android.DEFAULT_SCREENSHOT_DIR`, which still
hardcodes the deleted ~/Desktop/Hub checkout and silently recreates it (a
known deferred cleanup item). It defaults to a repo-relative `screenshots/`
subdirectory, which .gitignore already covers.

Usage:

    # Dry run: print the plan and run the byte-identity precondition, no network.
    uv run python -m scripts.sweep_goal_rotation --dry-run

    # Upload only -- collect share codes, skip the emulator.
    uv run python -m scripts.sweep_goal_rotation --no-render

    # Full sweep (emulator must be booted, GraviTrax at the main menu).
    uv run python -m scripts.sweep_goal_rotation

    # Resume after an abort, reusing prior renders.
    uv run python -m scripts.sweep_goal_rotation --resume screenshots/goal_rotation_sweep/results.json

Preconditions for rendering:
    - Android emulator (AVD: traxgen_m6c) running and booted
    - GraviTrax app launched and showing the main menu

Path: traxgen/scripts/sweep_goal_rotation.py
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

from traxgen.android import (
    AndroidAutomationError,
    assert_emulator_ready,
    render_course,
    resolve_context,
)
from traxgen.domain import (
    CellConstructionData,
    Course,
    TileTowerConstructionData,
    TileTowerTreeNodeData,
)
from traxgen.generator import generate_minimal
from traxgen.hex import HEX_DIRECTIONS, ORIGIN, HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.serializer import serialize_course
from traxgen.types import TileKind
from traxgen.uploader import UploadError, upload_course
from traxgen.validator import validate_strict

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "screenshots" / "goal_rotation_sweep"

# The app-certified geometry (share code FLW4TMLP5V). Doubles as the harness
# sanity check: if this cell renders inactive, nothing else in the run means
# anything.
POSITIVE_CONTROL_POS = HexVector(y=-1, x=0)
POSITIVE_CONTROL_ROT = 3

# A distance-2 position (East, East). Under the adjacency model no rotation
# here should connect; if one does, the model is wrong.
FAR_CONTROL_POS = HexVector(y=0, x=2)

ROTATIONS: tuple[int, ...] = (0, 1, 2, 3, 4, 5)

DIRECTION_NAMES = ("E", "NE", "NW", "W", "SW", "SE")


@dataclass
class SweepCell:
    """One (goal position, goal rotation) cell and everything observed about it."""

    kind: str  # 'adjacent' | 'control_far'
    direction: int | None  # HEX_DIRECTIONS index; None for the far control
    y: int
    x: int
    rot: int
    is_positive_control: bool = False
    payload_sha256: str | None = None
    payload_bytes: int | None = None
    validator: str | None = None  # 'ok' or the validator's error text
    code: str | None = None
    upload_error: str | None = None
    validity: str | None = None  # 'active' | 'inactive'
    render_error: str | None = None  # distinct from an 'inactive' verdict
    screenshot: str | None = None

    @property
    def label(self) -> str:
        """Short filesystem-safe identifier: no parens, commas, or spaces."""
        return f"goal_y{self.y}x{self.x}_rot{self.rot}"


def _goal_variant(base: Course, *, pos: HexVector, rot: int) -> Course:
    """Return a copy of `base` with its GOAL_RAIL cell moved to `pos` at rotation `rot`."""
    layer = base.layer_construction_data[0]
    starters = [
        cell
        for cell in layer.cell_construction_datas
        if cell.tree_node_data.construction_data.kind is TileKind.STARTER
    ]
    if len(starters) != 1:
        raise RuntimeError(
            f"expected exactly 1 STARTER cell in the base course, found {len(starters)}"
        )
    goal_cell = CellConstructionData(
        local_hex_position=pos,
        tree_node_data=TileTowerTreeNodeData(
            index=0,
            construction_data=TileTowerConstructionData(
                kind=TileKind.GOAL_RAIL,
                height_in_small_stacker=0,
                hex_rotation=rot,
            ),
            children=(),
        ),
    )
    new_layer = dataclasses.replace(
        layer, cell_construction_datas=(starters[0], goal_cell)
    )
    return dataclasses.replace(base, layer_construction_data=(new_layer,))


def _assert_control_matches_generator(base: Course) -> None:
    """The positive-control variant must serialize byte-identically to generate_minimal()."""
    control = _goal_variant(base, pos=POSITIVE_CONTROL_POS, rot=POSITIVE_CONTROL_ROT)
    if serialize_course(control) != serialize_course(base):
        raise RuntimeError(
            "positive-control variant is not byte-identical to generate_minimal(); "
            "this script's variant builder differs from the generator, so the sweep "
            "would not be measuring the app-certified geometry"
        )


def build_cells() -> list[SweepCell]:
    """Enumerate the 36 adjacency cells plus the 6 distance-2 control cells."""
    if ORIGIN.distance_to(FAR_CONTROL_POS) != 2:
        raise RuntimeError(
            f"FAR_CONTROL_POS {FAR_CONTROL_POS} is not at hex distance 2 from the starter"
        )
    cells: list[SweepCell] = []
    for direction, (dy, dx) in enumerate(HEX_DIRECTIONS):
        pos = HexVector(y=dy, x=dx)
        for rot in ROTATIONS:
            cells.append(
                SweepCell(
                    kind="adjacent",
                    direction=direction,
                    y=pos.y,
                    x=pos.x,
                    rot=rot,
                    is_positive_control=(
                        pos == POSITIVE_CONTROL_POS and rot == POSITIVE_CONTROL_ROT
                    ),
                )
            )
    for rot in ROTATIONS:
        cells.append(
            SweepCell(
                kind="control_far",
                direction=None,
                y=FAR_CONTROL_POS.y,
                x=FAR_CONTROL_POS.x,
                rot=rot,
            )
        )
    if sum(1 for c in cells if c.is_positive_control) != 1:
        raise RuntimeError("the positive-control cell is missing from the enumeration")
    return cells


def _render_order(cells: list[SweepCell]) -> list[SweepCell]:
    """Positive control first, then the distance-2 control, then the rest."""
    positive = [c for c in cells if c.is_positive_control]
    far = [c for c in cells if c.kind == "control_far"]
    rest = [c for c in cells if not c.is_positive_control and c.kind != "control_far"]
    return positive + far + rest


def fit_affine_rules(observed: dict[int, int]) -> list[tuple[int, int]]:
    """Return every (a, b) with rot == (a*d + b) % 6 for all observed direction->rotation pairs."""
    # a = 5 is -1 mod 6; the two chiralities are the only clean-rule candidates.
    return [
        (a, b)
        for a in (1, 5)
        for b in range(6)
        if all((a * d + b) % 6 == rot for d, rot in observed.items())
    ]


def classify(cells: list[SweepCell]) -> tuple[str, str]:
    """Apply the pre-declared falsification conditions. Returns (verdict, detail)."""
    control = next(c for c in cells if c.is_positive_control)
    if control.validity != "active":
        return (
            "HARNESS_SUSPECT",
            f"positive control ({control.label}) rendered {control.validity!r}, expected 'active'",
        )

    far_active = [c for c in cells if c.kind == "control_far" and c.validity == "active"]
    if far_active:
        return (
            "MODEL_WRONG",
            "distance-2 control went active at rotation(s) "
            f"{', '.join(str(c.rot) for c in far_active)} -- adjacency is not the mechanism",
        )

    by_direction: dict[int, list[int]] = {d: [] for d in range(6)}
    for cell in cells:
        if cell.kind == "adjacent" and cell.validity == "active":
            assert cell.direction is not None
            by_direction[cell.direction].append(cell.rot)

    multi = {d: rots for d, rots in by_direction.items() if len(rots) > 1}
    if multi:
        detail = "; ".join(
            f"{DIRECTION_NAMES[d]} active at {sorted(rots)}" for d, rots in multi.items()
        )
        return ("MODEL_WRONG", f"more than one rotation active per direction -- {detail}")

    observed = {d: rots[0] for d, rots in by_direction.items() if len(rots) == 1}
    missing = [DIRECTION_NAMES[d] for d in range(6) if not by_direction[d]]
    fits = fit_affine_rules(observed)

    def _rule_text(a: int, b: int) -> str:
        sign = "+" if a == 1 else "-"
        return f"rot = ({sign}d + {b}) % 6"

    if missing:
        note = f"no rotation connects from {', '.join(missing)}"
        if fits:
            note += "; observed directions are consistent with " + ", ".join(
                _rule_text(a, b) for a, b in fits
            )
        return ("PARTIAL_FUNCTION", note)
    if len(fits) == 1:
        a, b = fits[0]
        return ("CLEAN_RULE", _rule_text(a, b))
    if not fits:
        return (
            "LOOKUP_TABLE",
            "one rotation per direction, but no affine rule fits: "
            + ", ".join(f"{DIRECTION_NAMES[d]}->{r}" for d, r in sorted(observed.items())),
        )
    return (
        "AMBIGUOUS",
        "multiple affine rules fit -- " + ", ".join(_rule_text(a, b) for a, b in fits),
    )


def _write_sidecar(path: Path, cells: list[SweepCell], meta: dict) -> None:
    """Rewrite the results JSON. Called after every render so an abort loses nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {**meta, "cells": [dataclasses.asdict(c) for c in cells]},
            indent=2,
        )
    )


def _load_resume(path: Path, cells: list[SweepCell]) -> int:
    """Copy prior render verdicts onto matching cells. Returns how many were restored."""
    prior = json.loads(path.read_text())
    index = {(c["y"], c["x"], c["rot"]): c for c in prior.get("cells", [])}
    restored = 0
    for cell in cells:
        got = index.get((cell.y, cell.x, cell.rot))
        if got and got.get("validity") in ("active", "inactive"):
            cell.validity = got["validity"]
            cell.screenshot = got.get("screenshot")
            cell.code = got.get("code")
            restored += 1
    return restored


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the sweep."""
    parser = argparse.ArgumentParser(
        prog="sweep_goal_rotation",
        description=(
            "Sweep GOAL_RAIL position x rotation, upload each variant, render it on "
            "the emulator, and classify the result against the pre-declared "
            "falsification conditions."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Screenshots + results JSON (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and hash every variant, run the preconditions, print the plan. No network.",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Upload variants and print their share codes, but skip the emulator pass.",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="A prior results JSON; cells already rendered are skipped.",
    )
    parser.add_argument(
        "--budget-minutes",
        type=float,
        default=90.0,
        help="Pre-declared wall-clock budget, enforced between renders (default: 90).",
    )
    parser.add_argument(
        "--keep-all-screenshots",
        action="store_true",
        help="Skip the end-of-run prune that keeps only failures, the control, and actives.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Upload HTTP timeout in seconds (default: 30.0).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = _parse_args(argv)
    started = time.monotonic()

    base = generate_minimal()
    _assert_control_matches_generator(base)
    print("precondition ok: positive-control variant is byte-identical to generate_minimal()",
          file=sys.stderr)

    cells = build_cells()

    # Phase 0: build, validate and hash every payload. Hash distinctness is
    # checked BEFORE any upload -- the endpoint dedups by content hash, so two
    # cells sharing a payload would silently share a share code and stop being
    # the two things we think they are.
    payloads: dict[int, bytes] = {}
    for i, cell in enumerate(cells):
        course = _goal_variant(base, pos=HexVector(y=cell.y, x=cell.x), rot=cell.rot)
        try:
            validate_strict(course, PRO_VERTICAL_STARTER_SET)
            cell.validator = "ok"
        except Exception as exc:  # validator raises ValidationError; guard broadly
            cell.validator = f"{type(exc).__name__}: {exc}"
        binary = serialize_course(course)
        payloads[i] = binary
        cell.payload_sha256 = hashlib.sha256(binary).hexdigest()
        cell.payload_bytes = len(binary)

    digests = {c.payload_sha256 for c in cells}
    if len(digests) != len(cells):
        print(
            f"error: {len(cells)} cells produced only {len(digests)} distinct payloads. "
            "Upload dedup would collapse them; the sweep would not measure what it claims.",
            file=sys.stderr,
        )
        return 1
    print(f"precondition ok: {len(cells)} cells, {len(digests)} distinct payloads",
          file=sys.stderr)

    rejected = [c for c in cells if c.validator != "ok"]
    if rejected:
        print(
            f"note: {len(rejected)}/{len(cells)} variants fail validate_strict "
            "(uploading anyway -- the app is the oracle, not our validator)",
            file=sys.stderr,
        )

    if args.dry_run:
        print("\nplan (render order):")
        for cell in _render_order(cells):
            tag = " [POSITIVE CONTROL]" if cell.is_positive_control else ""
            tag += " [distance-2 control]" if cell.kind == "control_far" else ""
            print(f"  {cell.label:<22} validator={cell.validator}{tag}")
        print(f"\n{len(cells)} cells; nothing uploaded or rendered (--dry-run).")
        return 0

    sidecar = args.output_dir / "results.json"
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "positive_control": {
            "y": POSITIVE_CONTROL_POS.y,
            "x": POSITIVE_CONTROL_POS.x,
            "rot": POSITIVE_CONTROL_ROT,
        },
        "far_control": {"y": FAR_CONTROL_POS.y, "x": FAR_CONTROL_POS.x},
        "budget_minutes": args.budget_minutes,
    }

    restored = 0
    if args.resume is not None:
        restored = _load_resume(args.resume, cells)
        print(f"resumed {restored} previously rendered cells from {args.resume}",
              file=sys.stderr)

    # Fail fast before spending uploads on a dead emulator.
    ctx = None
    if not args.no_render:
        try:
            ctx = resolve_context()
            assert_emulator_ready(ctx)
        except AndroidAutomationError as exc:
            print(f"error: emulator not ready: {exc}", file=sys.stderr)
            print("       (re-run with --no-render to upload without rendering)",
                  file=sys.stderr)
            return 1

    # Phase 1: upload every variant. Fast, network-only; a mid-render failure
    # still leaves every share code captured.
    for i, cell in enumerate(cells):
        if cell.code:  # restored by --resume; identical bytes dedup to the same code
            continue
        try:
            cell.code = upload_course(payloads[i], timeout=args.timeout)
        except UploadError as exc:
            cell.upload_error = f"{type(exc).__name__}: {exc}"
            print(f"  {cell.label}: upload failed: {exc}", file=sys.stderr)
            continue
        print(f"  {cell.label}: uploaded -> {cell.code} ({cell.payload_bytes} bytes)",
              file=sys.stderr)

    uploaded = [c for c in cells if c.code]
    codes = {c.code for c in uploaded}
    if len(codes) != len(uploaded):
        print(
            f"error: {len(uploaded)} uploads returned only {len(codes)} distinct share "
            "codes despite distinct payloads. Halting -- the cells are not distinct.",
            file=sys.stderr,
        )
        _write_sidecar(sidecar, cells, meta)
        return 1

    _write_sidecar(sidecar, cells, meta)
    if args.no_render:
        print(f"\nuploaded {len(uploaded)}/{len(cells)} cells; renders skipped.")
        print(f"results JSON: {sidecar}")
        return 0

    # Phase 2: render. Positive control first -- a lying harness aborts here,
    # before 41 more renders are spent on it.
    budget_seconds = args.budget_minutes * 60.0
    first_render = True
    aborted: str | None = None
    for cell in _render_order(cells):
        if cell.validity is not None:  # restored by --resume
            continue
        if cell.code is None:
            continue
        elapsed = time.monotonic() - started
        if elapsed > budget_seconds:
            print(
                f"\nBUDGET ABORT: {elapsed / 60:.1f} min exceeds the pre-declared "
                f"{args.budget_minutes:.0f} min. Results so far are in {sidecar}; "
                f"resume with --resume {sidecar}",
                file=sys.stderr,
            )
            aborted = "budget"
            break
        print(f"  rendering {cell.label} ({cell.code})...", file=sys.stderr)
        try:
            result = render_course(
                cell.code,
                ctx=ctx,
                screenshot_dir=args.output_dir,
                screenshot_name=f"{cell.label}_{cell.code}",
                cleanup=True,
                # The disclaimer only appears on the first load of an app session.
                expect_disclaimer=first_render,
                detect_validity=True,
            )
        except AndroidAutomationError as exc:
            cell.render_error = f"{type(exc).__name__}: {exc}"
            print(f"  {cell.label}: render FAILED: {exc}", file=sys.stderr)
            _write_sidecar(sidecar, cells, meta)
            continue
        first_render = False
        cell.validity = result.validity
        cell.screenshot = str(result.screenshot)
        print(f"  {cell.label}: play button = {cell.validity}", file=sys.stderr)
        _write_sidecar(sidecar, cells, meta)

        # Pre-declared hard aborts (observation #9).
        if cell.is_positive_control and cell.validity != "active":
            print(
                "\nHARNESS ABORT: the app-certified control cell rendered "
                f"{cell.validity!r}. The oracle is not measuring what it should; "
                "debug the harness before spending the sweep.",
                file=sys.stderr,
            )
            aborted = "harness"
            break
        if cell.kind == "control_far" and cell.validity == "active":
            print(
                f"\nMODEL ABORT: distance-2 control {cell.label} rendered active. "
                "Adjacency is not the connection mechanism -- stop and rethink the "
                "framing before sweeping the adjacency cells.",
                file=sys.stderr,
            )
            aborted = "model"
            break

    # Closing bracket: re-render the positive control after the last cell. Active at
    # both ends means the harness held for the whole run. The opening control only
    # proves the harness worked at render 1 -- a drift at render 25 would otherwise
    # surface as a page of 'inactive' verdicts that read like findings.
    control = next(c for c in cells if c.is_positive_control)
    if not args.no_render and aborted is None and control.code:
        print("  re-rendering the positive control (closing bracket)...", file=sys.stderr)
        try:
            result = render_course(
                control.code,
                ctx=ctx,
                screenshot_dir=args.output_dir,
                screenshot_name=f"{control.label}_{control.code}_FINAL",
                cleanup=True,
                expect_disclaimer=False,
                detect_validity=True,
            )
            meta["final_control_validity"] = result.validity
            meta["final_control_screenshot"] = str(result.screenshot)
            print(f"  closing bracket = {result.validity}", file=sys.stderr)
        except AndroidAutomationError as exc:
            meta["final_control_error"] = f"{type(exc).__name__}: {exc}"
            print(f"  closing bracket FAILED: {exc}", file=sys.stderr)

    _write_sidecar(sidecar, cells, meta)

    # Summary table.
    print(f"\nsweep results ({len(cells)} cells):")
    print(f"{'direction':<10} {'position':<10} {'rot':>3}  {'code':<12} {'verdict':<12} note")
    for cell in _render_order(cells):
        direction = DIRECTION_NAMES[cell.direction] if cell.direction is not None else "far"
        cell_verdict = "RENDER_ERROR" if cell.render_error else (cell.validity or "-")
        note = ""
        if cell.is_positive_control:
            note = "positive control"
        elif cell.kind == "control_far":
            note = "distance-2 control"
        if cell.upload_error:
            note = (note + " " if note else "") + "upload failed"
        print(
            f"{direction:<10} {f'({cell.y},{cell.x})':<10} {cell.rot:>3}  "
            f"{(cell.code or '-'):<12} {cell_verdict:<12} {note}"
        )

    rendered = [c for c in cells if c.validity is not None]
    if len(rendered) < len(cells):
        print(
            f"\nINCOMPLETE: {len(rendered)}/{len(cells)} cells rendered. "
            f"Resume with --resume {sidecar}"
        )
        verdict, detail = ("INCOMPLETE", "not every cell was rendered")
    else:
        verdict, detail = classify(cells)

    # A drifted closing bracket invalidates everything above it, whatever it said.
    bracket = meta.get("final_control_validity")
    if meta.get("final_control_error") or (bracket is not None and bracket != "active"):
        verdict = "HARNESS_SUSPECT"
        detail = (
            "the closing-bracket control rendered "
            f"{meta.get('final_control_error') or bracket!r} -- the harness drifted "
            "during the run, so every verdict above it is suspect"
        )
    elif bracket == "active":
        print("\nharness bracket: control active at both ends of the run")

    print(f"\n=> {verdict}: {detail}")

    # Prune screenshots: keep failures, the control, and any active cell.
    if not args.keep_all_screenshots:
        pruned = 0
        for cell in cells:
            keep = (
                cell.render_error is not None
                or cell.is_positive_control
                or cell.validity == "active"
            )
            if keep or not cell.screenshot:
                continue
            path = Path(cell.screenshot)
            if path.is_file():
                path.unlink()
                pruned += 1
            cell.screenshot = None
        if pruned:
            print(f"pruned {pruned} screenshots (kept failures, control, and actives)")
        _write_sidecar(sidecar, cells, meta)

    print(f"elapsed: {(time.monotonic() - started) / 60:.1f} min")
    print(f"results JSON: {sidecar}")
    return 0 if verdict in ("CLEAN_RULE", "LOOKUP_TABLE", "PARTIAL_FUNCTION") else 1


if __name__ == "__main__":
    sys.exit(main())
