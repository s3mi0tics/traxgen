"""M6.b diagnostic: sweep a rail's `side_hex_rot` and read the validity oracle.

Open unknown #2 (PLAN.md): which of the 6 hex edges `side_hex_rot` identifies
is unverified, and the minimal STARTER + STRAIGHT + GOAL_RAIL course renders
both tiles but no connecting rail. This script runs the planned diagnostic:
hold one rail exit fixed, sweep the other exit's `side_hex_rot` across 0..5,
and use the app's play-button validity oracle to find which value makes the
rail actually connect (button goes 'active' = app sees a starter->goal path).

Flow per variant:
    generate_minimal -> replace one exit's side_hex_rot -> validate_strict
    -> serialize -> upload -> render on emulator -> classify play button.

Uploads happen first (fast, network-only, distinct bytes => distinct codes,
no dedup collision), then renders (slow, ~25s each, needs the emulator). That
ordering means a mid-sweep emulator failure still leaves every share code
captured so the renders can be resumed by hand.

Usage:

    # Planned diagnostic: sweep exit_1 over 0..5, exit_2 left as generated.
    uv run python -m scripts.sweep_side_hex_rot

    # Sweep exit_2 instead, or a custom value set.
    uv run python -m scripts.sweep_side_hex_rot --exit 2
    uv run python -m scripts.sweep_side_hex_rot --values 0,1,2

    # Upload only (collect codes, skip the emulator).
    uv run python -m scripts.sweep_side_hex_rot --no-render

Preconditions for rendering:
    - Android emulator (AVD: traxgen_m6c) running and booted
    - GraviTrax app launched and showing the main menu

Output:
    - stderr: per-variant progress
    - stdout: a results table (rot, code, validity, screenshot)
    - a JSON sidecar `sweep_side_hex_rot_results.json` in the screenshot dir

Path: traxgen/scripts/sweep_side_hex_rot.py
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from traxgen.android import (
    AndroidAutomationError,
    DEFAULT_SCREENSHOT_DIR,
    assert_emulator_ready,
    render_course,
    resolve_context,
)
from traxgen.domain import Course
from traxgen.generator import generate_minimal
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.serializer import serialize_course
from traxgen.uploader import UploadError, upload_course
from traxgen.validator import validate_strict


def _variant(base: Course, *, exit_num: int, rot: int) -> Course:
    """Return a copy of `base` with one rail exit's side_hex_rot set to `rot`."""
    rail = base.rail_construction_data[0]
    field = "exit_1_identifier" if exit_num == 1 else "exit_2_identifier"
    new_exit = dataclasses.replace(getattr(rail, field), side_hex_rot=rot)
    new_rail = dataclasses.replace(rail, **{field: new_exit})
    return dataclasses.replace(base, rail_construction_data=(new_rail,))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the sweep."""
    parser = argparse.ArgumentParser(
        prog="sweep_side_hex_rot",
        description=(
            "Sweep a rail's side_hex_rot across values, upload each variant, "
            "render it on the emulator, and report the validity oracle's verdict."
        ),
    )
    parser.add_argument(
        "--exit",
        type=int,
        choices=(1, 2),
        default=1,
        dest="exit_num",
        help="Which rail exit to sweep (the other is left as generate_minimal sets it). Default: 1.",
    )
    parser.add_argument(
        "--values",
        default="0,1,2,3,4,5",
        help="Comma-separated side_hex_rot values to test (default: 0,1,2,3,4,5).",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=DEFAULT_SCREENSHOT_DIR,
        help=f"Output directory for screenshots + results JSON (default: {DEFAULT_SCREENSHOT_DIR}).",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Upload variants and print their codes, but skip the emulator render pass.",
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

    try:
        rots = [int(v) for v in args.values.split(",") if v.strip() != ""]
    except ValueError:
        print(f"error: --values must be comma-separated ints, got {args.values!r}", file=sys.stderr)
        return 1
    if not rots:
        print("error: --values produced no values", file=sys.stderr)
        return 1
    if any(r < 0 or r > 5 for r in rots):
        print(f"error: side_hex_rot values must be in [0, 5], got {rots}", file=sys.stderr)
        return 1

    base = generate_minimal()
    other = 2 if args.exit_num == 1 else 1
    other_rot = getattr(
        base.rail_construction_data[0],
        "exit_1_identifier" if other == 1 else "exit_2_identifier",
    ).side_hex_rot
    print(
        f"sweeping exit_{args.exit_num} side_hex_rot over {rots} "
        f"(exit_{other} fixed at {other_rot})",
        file=sys.stderr,
    )

    # If we plan to render, fail fast before spending uploads on a dead emulator.
    ctx = None
    if not args.no_render:
        try:
            ctx = resolve_context()
            assert_emulator_ready(ctx)
        except AndroidAutomationError as exc:
            print(f"error: emulator not ready: {exc}", file=sys.stderr)
            print("       (re-run with --no-render to upload without rendering)", file=sys.stderr)
            return 1

    # Phase 1: build, validate, serialize, upload every variant.
    results: list[dict] = []
    for rot in rots:
        course = _variant(base, exit_num=args.exit_num, rot=rot)
        try:
            validate_strict(course, PRO_VERTICAL_STARTER_SET)
        except Exception as exc:  # validator raises ValidationError; guard broadly
            print(f"  rot={rot}: WARNING variant failed validate_strict: {exc}", file=sys.stderr)
        binary = serialize_course(course)
        try:
            code = upload_course(binary, timeout=args.timeout)
        except UploadError as exc:
            print(f"  rot={rot}: upload failed: {exc}", file=sys.stderr)
            results.append({"rot": rot, "code": None, "validity": None, "screenshot": None})
            continue
        print(f"  rot={rot}: uploaded -> {code} ({len(binary)} bytes)", file=sys.stderr)
        results.append({"rot": rot, "code": code, "validity": None, "screenshot": None})

    # Phase 2: render each uploaded variant and classify the play button.
    if not args.no_render:
        first_render = True
        for entry in results:
            if entry["code"] is None:
                continue
            code = entry["code"]
            name = f"sweep_e{args.exit_num}rot{entry['rot']}_{code}"
            print(f"  rendering rot={entry['rot']} ({code})...", file=sys.stderr)
            try:
                rr = render_course(
                    code,
                    ctx=ctx,
                    screenshot_dir=args.screenshot_dir,
                    screenshot_name=name,
                    cleanup=True,
                    # Disclaimer only appears on the first load of an app session.
                    expect_disclaimer=first_render,
                    detect_validity=True,
                )
            except AndroidAutomationError as exc:
                print(f"  rot={entry['rot']}: render failed: {exc}", file=sys.stderr)
                continue
            first_render = False
            entry["validity"] = rr.validity
            entry["screenshot"] = str(rr.screenshot)
            print(f"  rot={entry['rot']}: play button = {rr.validity}", file=sys.stderr)

    # Persist results sidecar.
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)
    sidecar = args.screenshot_dir / "sweep_side_hex_rot_results.json"
    sidecar.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "swept_exit": args.exit_num,
                "fixed_exit": other,
                "fixed_exit_side_hex_rot": other_rot,
                "results": results,
            },
            indent=2,
        )
    )

    # Summary table to stdout.
    print(f"\nsweep results (exit_{args.exit_num}, exit_{other} fixed at {other_rot}):")
    print(f"{'rot':>4}  {'code':<12}  {'validity':<9}  screenshot")
    for entry in results:
        print(
            f"{entry['rot']:>4}  "
            f"{(entry['code'] or '-'):<12}  "
            f"{(entry['validity'] or '-'):<9}  "
            f"{entry['screenshot'] or '-'}"
        )

    active = [e for e in results if e["validity"] == "active"]
    if active:
        vals = ", ".join(str(e["rot"]) for e in active)
        print(f"\n=> side_hex_rot {vals} produced an ACTIVE play button (rail connects).")
    elif not args.no_render:
        print(
            "\n=> no value activated the play button. "
            f"exit_{other}={other_rot} is likely also wrong — try sweeping --exit {other}, "
            "or a 2D sweep.",
        )
    print(f"\nresults JSON: {sidecar}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
