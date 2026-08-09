"""M6.b: sweep the STARTER's hex_rotation against a *known-active* goal cell.

Open unknown #14: `rot = (d + 1) % 6` is the sole affine rule fitting the two
observed connections (E rot 1, NW rot 3), but it predicts connections at NE,
W, SW and SE where the app says none exist. The starter's `hex_rotation` was
pinned at 0 for all 42 cells of the 2026-08-07 goal-rotation sweep and is the
leading suspect: if the mapping is really `(starter_rot, d) -> goal_rot`, that
sweep measured a single slice of a six-times-larger space.

Why this sweeps a known-ACTIVE cell, not the predicted-but-dead one
-------------------------------------------------------------------
The obvious experiment holds the goal at the mispredicted NE rot 2 and sweeps
the starter. It is the wrong experiment, because its null result cannot
discriminate. If the coupling is `(starter_rot, d) -> goal_rot`, then changing
the starter changes *which goal rotation should connect*, so pinning the goal
at rot 2 tests only the diagonal where `f(s, NE) == 2`. Six inactives would be
equally consistent with "NE is unreachable" and with "the coupling is real but
never yields rot 2 at NE" -- exactly the ambiguity the sweep exists to remove.

Holding a known-active cell (E rot 1) inverts that. `f` is constant in `s` iff
E rot 1 survives every starter rotation, so both outcomes carry information:

  * active at all six -> `s` does not move the mapping. #14 resolves toward a
    partial function with genuinely unreachable directions, and M5.c can use
    `rot = (d + 1) % 6` on the directions where it holds.
  * inactive at some  -> the coupling is real, and *which* rotations kill it
    constrains the follow-up instead of merely motivating one.

Two extra cells earn their renders
----------------------------------
`EXIT_PROBE` (starter rot 1, goal NE rot 2) tests the hypothesis that best
fits the 2026-08-07 data. Read that sweep by *direction* rather than by
rotation and the pattern is not four arbitrary holes: the two live directions
are E (0) and NW (2), and the four dead ones are exactly the rest. A starter
with two exits, two directions apart, predicts precisely that -- and it
reframes `rot = (d + 1) % 6` as a goal-side rule (the goal points its rail
back at the starter) that was never partial at all. What is restricted is the
*direction set*, not the rotation rule.

If those exits turn with `hex_rotation`, the connectable set at starter
rotation `s` is `{s, s + 2} (mod 6)`, with the goal rotation rule unchanged.
At s=1 that is `{NE, W}`: E rot 1 should die and NE rot 2 should light up.
That is the probe. A hit makes the rule *total* -- every direction reachable
by choosing the starter's rotation -- which is a materially better input to
M5.c than a partial function. Note that a probe hit *alongside* six active
sweep cells is a third outcome, not a contradiction: it would mean rotation
adds exits without removing them.

`BACKFILL` (starter rot 0, goal NW rot 0) is the one cell of the 2026-08-07
sweep's 42 with no verdict: its upload hit HTTP 520 and the retry produced a
false `active` from a splash screen, since cleared. It is not optional --
if NW connects at rot 0 as well as rot 3, the one-rotation-per-direction model
underpinning the derived rule is wrong.

Pre-declared falsification (design decision, before the first render)
----------------------------------------------------------------------
  STARTER_ROTATION_IRRELEVANT  E rot 1 active at all six starter rotations and
                               the probe inactive. `f` is constant in
                               `s`; unreachable directions are real.
  EXIT_SET_ROTATES             E rot 1 dies at s=1 while the probe goes active
                               -- the exit set turns with the starter
                               (`d in {s, s + 2} mod 6`), so every direction is
                               reachable and the rule is total, not partial.
  STARTER_UNLOCKS_DIRECTIONS   all six sweep cells active AND the probe active
                               -- rotation opens directions without closing E.
                               Directly unblocks reaching the dead directions.
  STARTER_ROTATION_MATTERS     any other mixed pattern. The coupling is real
                               but not one of the two modelled shapes.
  MODEL_WRONG                  the backfill cell is active: NW connects at both
                               rot 0 and rot 3, so rotation is not the sole
                               determinant and the derived rule rests on a
                               false premise.
  REPLICATION_FAILED           the s=0 sweep cell -- byte-distinct from, but
                               geometrically identical to, the cell measured
                               active on 2026-08-07 -- reads inactive. Nothing
                               above it is trustworthy; hard abort.
  HARNESS_SUSPECT              the app-certified positive control is inactive
                               at either end of the run.

Controls at both ends (decisions.md, 2026-08-07)
-------------------------------------------------
The app-certified geometry renders FIRST and again AFTER the last cell. A
non-active closing bracket overrides the run's verdict regardless of what the
data said -- an opening control proves the harness worked at render 1 and says
nothing about render 10.

Usage:

    # Dry run: build and hash every variant, run the preconditions. No network.
    uv run python -m scripts.sweep_starter_rotation --dry-run

    # Upload only -- collect share codes, skip the emulator.
    uv run python -m scripts.sweep_starter_rotation --no-render

    # Full sweep (emulator booted, GraviTrax at the main menu).
    uv run python -m scripts.sweep_starter_rotation

    # Resume after an abort.
    uv run python -m scripts.sweep_starter_rotation \
        --resume screenshots/starter_rotation_sweep/results.json

Path: traxgen/scripts/sweep_starter_rotation.py
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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "screenshots" / "starter_rotation_sweep"

DIRECTION_NAMES = ("E", "NE", "NW", "W", "SW", "SE")

DIR_E, DIR_NE, DIR_NW, DIR_W = 0, 1, 2, 3


def direction_position(direction: int) -> HexVector:
    """The adjacent hex in `direction`, as the wire-format (y, x) axial vector."""
    dy, dx = HEX_DIRECTIONS[direction]
    return HexVector(y=dy, x=dx)


# The app-certified geometry (share code FLW4TMLP5V) -- rendered at both ends.
CONTROL_STARTER_ROT = 0
CONTROL_GOAL_POS = direction_position(DIR_NW)
CONTROL_GOAL_ROT = 3

# The held target: a cell measured ACTIVE on 2026-08-07 with the starter at 0.
HELD_GOAL_POS = direction_position(DIR_E)
HELD_GOAL_ROT = 1

STARTER_ROTATIONS: tuple[int, ...] = (0, 1, 2, 3, 4, 5)

# The rotating-exit-set hypothesis: at s=1 the connectable set {E, NW} becomes
# {NE, W}, so NE takes the goal rotation the unchanged rule gives it, (1+1)%6.
PROBE_STARTER_ROT = 1
PROBE_GOAL_POS = direction_position(DIR_NE)
PROBE_GOAL_ROT = 2

# Verdicts that mean the sweep measured something usable. Enumerated rather
# than pattern-matched on the name: a prefix test would silently reclassify a
# renamed verdict, which is the "a check can pass while asserting something
# false" shape (observation #12).
INFORMATIVE_VERDICTS: frozenset[str] = frozenset(
    {
        "STARTER_ROTATION_IRRELEVANT",
        "EXIT_SET_ROTATES",
        "STARTER_UNLOCKS_DIRECTIONS",
        "STARTER_ROTATION_MATTERS",
    }
)

# The 2026-08-07 sweep's one cell with no verdict.
BACKFILL_STARTER_ROT = 0
BACKFILL_GOAL_POS = direction_position(DIR_NW)
BACKFILL_GOAL_ROT = 0


@dataclass
class StarterCell:
    """One (starter rotation, goal position, goal rotation) cell and its observations."""

    kind: str  # 'control' | 'sweep' | 'probe' | 'backfill'
    starter_rot: int
    y: int
    x: int
    goal_rot: int
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
        return f"s{self.starter_rot}_goal_y{self.y}x{self.x}_rot{self.goal_rot}"

    @property
    def goal_pos(self) -> HexVector:
        """The goal's local hex position."""
        return HexVector(y=self.y, x=self.x)

    @property
    def key(self) -> tuple[int, int, int, int]:
        """Identity of the geometry this cell measures."""
        return (self.starter_rot, self.y, self.x, self.goal_rot)


def build_variant(
    base: Course, *, starter_rot: int, goal_pos: HexVector, goal_rot: int
) -> Course:
    """Return a copy of `base` with the STARTER re-rotated and the GOAL_RAIL moved."""
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
    starter_cell = CellConstructionData(
        local_hex_position=starters[0].local_hex_position,
        tree_node_data=TileTowerTreeNodeData(
            index=0,
            construction_data=TileTowerConstructionData(
                kind=TileKind.STARTER,
                height_in_small_stacker=0,
                hex_rotation=starter_rot,
            ),
            children=(),
        ),
    )
    goal_cell = CellConstructionData(
        local_hex_position=goal_pos,
        tree_node_data=TileTowerTreeNodeData(
            index=0,
            construction_data=TileTowerConstructionData(
                kind=TileKind.GOAL_RAIL,
                height_in_small_stacker=0,
                hex_rotation=goal_rot,
            ),
            children=(),
        ),
    )
    new_layer = dataclasses.replace(
        layer, cell_construction_datas=(starter_cell, goal_cell)
    )
    return dataclasses.replace(base, layer_construction_data=(new_layer,))


def _assert_control_matches_generator(base: Course) -> None:
    """The control variant must serialize byte-identically to `generate_minimal()`.

    This guards the *variant builder*, and only that: it proves `build_variant`
    rebuilds the starter and goal cells the way the generator does. It cannot
    detect generator-vs-app drift -- both sides share an origin, which is the
    shape observation #12 names. That separate question was settled on
    2026-08-07 by diffing `generate_minimal()` against FLW4TMLP5V's raw bytes.
    """
    control = build_variant(
        base,
        starter_rot=CONTROL_STARTER_ROT,
        goal_pos=CONTROL_GOAL_POS,
        goal_rot=CONTROL_GOAL_ROT,
    )
    if serialize_course(control) != serialize_course(base):
        raise RuntimeError(
            "control variant is not byte-identical to generate_minimal(); this "
            "script's variant builder differs from the generator, so the sweep "
            "would not be measuring the app-certified geometry"
        )


def build_cells() -> list[StarterCell]:
    """Enumerate the control, the six sweep cells, the exit probe, and the backfill."""
    if ORIGIN.distance_to(HELD_GOAL_POS) != 1:
        raise RuntimeError(f"held goal {HELD_GOAL_POS} is not adjacent to the starter")
    cells = [
        StarterCell(
            kind="control",
            starter_rot=CONTROL_STARTER_ROT,
            y=CONTROL_GOAL_POS.y,
            x=CONTROL_GOAL_POS.x,
            goal_rot=CONTROL_GOAL_ROT,
        )
    ]
    cells += [
        StarterCell(
            kind="sweep",
            starter_rot=s,
            y=HELD_GOAL_POS.y,
            x=HELD_GOAL_POS.x,
            goal_rot=HELD_GOAL_ROT,
        )
        for s in STARTER_ROTATIONS
    ]
    cells.append(
        StarterCell(
            kind="probe",
            starter_rot=PROBE_STARTER_ROT,
            y=PROBE_GOAL_POS.y,
            x=PROBE_GOAL_POS.x,
            goal_rot=PROBE_GOAL_ROT,
        )
    )
    cells.append(
        StarterCell(
            kind="backfill",
            starter_rot=BACKFILL_STARTER_ROT,
            y=BACKFILL_GOAL_POS.y,
            x=BACKFILL_GOAL_POS.x,
            goal_rot=BACKFILL_GOAL_ROT,
        )
    )
    if len({c.key for c in cells}) != len(cells):
        raise RuntimeError("enumeration contains duplicate geometries")
    return cells


def _render_order(cells: list[StarterCell]) -> list[StarterCell]:
    """Control first, then the s=0 replication, then the rest of the sweep, probe, backfill."""
    control = [c for c in cells if c.kind == "control"]
    replication = [c for c in cells if c.kind == "sweep" and c.starter_rot == 0]
    rest_sweep = sorted(
        (c for c in cells if c.kind == "sweep" and c.starter_rot != 0),
        key=lambda c: c.starter_rot,
    )
    tail = [c for c in cells if c.kind in ("probe", "backfill")]
    return control + replication + rest_sweep + tail


def classify(cells: list[StarterCell]) -> tuple[str, str]:
    """Apply the pre-declared falsification conditions. Returns (verdict, detail)."""
    control = next(c for c in cells if c.kind == "control")
    if control.validity != "active":
        return (
            "HARNESS_SUSPECT",
            f"the app-certified control ({control.label}) rendered "
            f"{control.validity!r}, expected 'active'",
        )

    sweep = {c.starter_rot: c for c in cells if c.kind == "sweep"}
    replication = sweep[0]
    if replication.validity != "active":
        return (
            "REPLICATION_FAILED",
            f"the s=0 cell ({replication.label}) rendered {replication.validity!r}; "
            "this geometry was measured active on 2026-08-07, so the disagreement "
            "invalidates the run rather than teaching anything",
        )

    backfill = next(c for c in cells if c.kind == "backfill")
    if backfill.validity == "active":
        return (
            "MODEL_WRONG",
            f"{backfill.label} is active: NW connects at rot 0 as well as rot 3, so "
            "rotation is not the sole determinant and the derived rule rests on a "
            "false premise",
        )

    probe = next(c for c in cells if c.kind == "probe")
    probe_active = probe.validity == "active"
    active = sorted(s for s, c in sweep.items() if c.validity == "active")
    dead = sorted(s for s, c in sweep.items() if c.validity == "inactive")
    survives = f"E rot 1 active at starter rotations {active}, inactive at {dead}"

    if len(active) == len(STARTER_ROTATIONS):
        if probe_active:
            return (
                "STARTER_UNLOCKS_DIRECTIONS",
                "E rot 1 survives every starter rotation AND the probe "
                f"({probe.label}) is active -- rotating the starter adds exits "
                "without removing them, so the four dead directions are reachable "
                "after all",
            )
        return (
            "STARTER_ROTATION_IRRELEVANT",
            "E rot 1 active at all six starter rotations and the probe "
            f"({probe.label}) inactive -- the starter's exit set is fixed at "
            "{E, NW} regardless of its rotation, so the four dead directions are "
            "genuinely unreachable and rot = (d + 1) % 6 holds only where an "
            "exit exists",
        )

    if probe_active and 1 in dead:
        return (
            "EXIT_SET_ROTATES",
            f"{survives}; the probe ({probe.label}) is active, so the starter's "
            "exit set turns with its rotation -- connectable directions are "
            "{s, s + 2} mod 6 with goal_rot = (d + 1) % 6 unchanged. Every "
            "direction is reachable: the rule is total, not partial",
        )

    return (
        "STARTER_ROTATION_MATTERS",
        f"{survives}; probe ({probe.label}) "
        f"{'active' if probe_active else 'inactive'} -- the coupling is real but "
        "matches neither modelled shape",
    )


def _write_sidecar(path: Path, cells: list[StarterCell], meta: dict) -> None:
    """Rewrite the results JSON. Called after every render so an abort loses nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({**meta, "cells": [dataclasses.asdict(c) for c in cells]}, indent=2)
    )


def _load_resume(path: Path, cells: list[StarterCell]) -> int:
    """Copy prior render verdicts onto matching cells. Returns how many were restored."""
    prior = json.loads(path.read_text())
    index = {
        (c["starter_rot"], c["y"], c["x"], c["goal_rot"]): c
        for c in prior.get("cells", [])
    }
    restored = 0
    for cell in cells:
        got = index.get(cell.key)
        if got and got.get("validity") in ("active", "inactive"):
            cell.validity = got["validity"]
            cell.screenshot = got.get("screenshot")
            cell.code = got.get("code")
            restored += 1
    return restored


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the sweep."""
    parser = argparse.ArgumentParser(
        prog="sweep_starter_rotation",
        description=(
            "Hold GOAL_RAIL at a known-active cell, sweep the STARTER's hex_rotation, "
            "and classify the result against the pre-declared falsification conditions."
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
        default=30.0,
        help="Pre-declared wall-clock budget, enforced between renders (default: 30).",
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
    print(
        "precondition ok: control variant is byte-identical to generate_minimal()",
        file=sys.stderr,
    )

    cells = build_cells()

    # Phase 0: build, validate and hash every payload. Hash distinctness is
    # checked BEFORE any upload -- the endpoint dedups by content hash, so two
    # cells sharing a payload would silently share a share code and stop being
    # the two things we think they are. This is also the check that would catch
    # the starter's hex_rotation not reaching the wire at all.
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

    digests = {c.payload_sha256 for c in cells}
    if len(digests) != len(cells):
        print(
            f"error: {len(cells)} cells produced only {len(digests)} distinct payloads. "
            "If the collisions are the sweep cells, the starter's hex_rotation is not "
            "reaching the wire and this sweep cannot measure anything.",
            file=sys.stderr,
        )
        return 1
    print(
        f"precondition ok: {len(cells)} cells, {len(digests)} distinct payloads",
        file=sys.stderr,
    )

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
            print(f"  {cell.label:<26} {cell.kind:<9} validator={cell.validator}")
        print(f"\n{len(cells)} cells; nothing uploaded or rendered (--dry-run).")
        return 0

    sidecar = args.output_dir / "results.json"
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "held_goal": {
            "y": HELD_GOAL_POS.y,
            "x": HELD_GOAL_POS.x,
            "rot": HELD_GOAL_ROT,
            "note": "measured active 2026-08-07 with starter_rot=0",
        },
        "control": {
            "starter_rot": CONTROL_STARTER_ROT,
            "y": CONTROL_GOAL_POS.y,
            "x": CONTROL_GOAL_POS.x,
            "rot": CONTROL_GOAL_ROT,
        },
        "budget_minutes": args.budget_minutes,
    }

    if args.resume is not None:
        restored = _load_resume(args.resume, cells)
        print(
            f"resumed {restored} previously rendered cells from {args.resume}",
            file=sys.stderr,
        )

    # Fail fast before spending uploads on a dead emulator.
    ctx = None
    if not args.no_render:
        try:
            ctx = resolve_context()
            assert_emulator_ready(ctx)
        except AndroidAutomationError as exc:
            print(f"error: emulator not ready: {exc}", file=sys.stderr)
            print(
                "       (re-run with --no-render to upload without rendering)",
                file=sys.stderr,
            )
            return 1

    # Phase 1: upload every variant. Fast, network-only; a mid-render failure
    # still leaves every share code captured (observation #15).
    for i, cell in enumerate(cells):
        if cell.code:  # restored by --resume; identical bytes dedup to the same code
            continue
        try:
            cell.code = upload_course(payloads[i], timeout=args.timeout)
        except UploadError as exc:
            cell.upload_error = f"{type(exc).__name__}: {exc}"
            print(f"  {cell.label}: upload failed: {exc}", file=sys.stderr)
            continue
        print(
            f"  {cell.label}: uploaded -> {cell.code} ({cell.payload_bytes} bytes)",
            file=sys.stderr,
        )

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

    # Phase 2: render. Control first, then the s=0 replication -- both are known
    # actives, so a harness problem costs two renders rather than ten.
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
        if cell.kind == "control" and cell.validity != "active":
            print(
                "\nHARNESS ABORT: the app-certified control rendered "
                f"{cell.validity!r}. The oracle is not measuring what it should; "
                "debug the harness before spending the sweep.",
                file=sys.stderr,
            )
            aborted = "harness"
            break
        if cell.kind == "sweep" and cell.starter_rot == 0 and cell.validity != "active":
            print(
                "\nREPLICATION ABORT: the s=0 cell rendered "
                f"{cell.validity!r}, but this geometry was measured active on "
                "2026-08-07. Either that reading or this one is wrong -- stop and "
                "settle it before sweeping the other five rotations.",
                file=sys.stderr,
            )
            aborted = "replication"
            break

    # Closing bracket: re-render the control after the last cell. Active at both
    # ends means the harness held for the whole run.
    control = next(c for c in cells if c.kind == "control")
    if not args.no_render and aborted is None and control.code:
        print("  re-rendering the control (closing bracket)...", file=sys.stderr)
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
    print(
        f"{'kind':<9} {'starter':>7} {'goal':<9} {'rot':>3}  "
        f"{'code':<12} {'verdict':<12} note"
    )
    for cell in _render_order(cells):
        cell_verdict = "RENDER_ERROR" if cell.render_error else (cell.validity or "-")
        note = ""
        if cell.kind == "control":
            note = "app-certified control"
        elif cell.kind == "sweep" and cell.starter_rot == 0:
            note = "replication of 2026-08-07"
        elif cell.kind == "probe":
            note = "exit-set rotation probe"
        elif cell.kind == "backfill":
            note = "2026-08-07 cell with no verdict"
        if cell.upload_error:
            note = (note + " " if note else "") + "upload failed"
        print(
            f"{cell.kind:<9} {cell.starter_rot:>7} {f'({cell.y},{cell.x})':<9} "
            f"{cell.goal_rot:>3}  {(cell.code or '-'):<12} {cell_verdict:<12} {note}"
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
                or cell.kind == "control"
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
    return 0 if verdict in INFORMATIVE_VERDICTS else 1


if __name__ == "__main__":
    sys.exit(main())
