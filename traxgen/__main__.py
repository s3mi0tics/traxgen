"""traxgen's command-line entry point: ``python -m traxgen`` and the ``traxgen`` script.

Phase 1's definition of done names one command --

    python -m traxgen generate --set vertical-starter

-- and until this file existed that command could not run: ``pyproject.toml`` declared
``traxgen = "traxgen.__main__:main"`` from the first commit, and nothing ever placed the
module. The library behind it had been app-certified since 2026-08-07 (share code
``FLW4TMLP5V``); the gap was the wrapper.

This module owns argument parsing and process exit codes and nothing else. Generation
is `traxgen.generator`, validation is `traxgen.validator`, bytes are
`traxgen.serializer`. ``main`` takes its generator as a keyword so a test can hand it
one that returns a known-bad course and exercise the failure path without touching the
real generator -- the same seam `scripts/emulator.py` uses for ``adb``.

Exit codes: 0 wrote a course; 1 the course failed strict validation (nothing written);
2 usage; 3 the generator refused to propose a placement (nothing written) -- distinct
from 1 because there is no course to have been invalid.

Path: traxgen/traxgen/__main__.py
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import TextIO

from traxgen.domain import Course
from traxgen.generator import (
    NoBuildablePlacementError,
    UnmodelledGoalKindError,
    generate_minimal,
    generate_multi_plate,
)
from traxgen.graph import ConnectionStatus, start_goal_status
from traxgen.inventory import PRO_VERTICAL_STARTER_SET, Inventory
from traxgen.plates import STANDARD_SQUARE
from traxgen.serializer import serialize_course
from traxgen.validator import ValidationError, validate_strict

Generator = Callable[[Inventory], Course]

# Only sets the generator has been certified against in the app appear here. Adding a
# set is one entry -- after a render through the harness says the app accepts it.
SETS: Mapping[str, Inventory] = {
    "vertical-starter": PRO_VERTICAL_STARTER_SET,
}

# The board a course is generated onto: the plate world positions, or None for
# `generate_minimal`'s hardcoded single plate. Adding a board is one entry,
# same as `SETS` -- and same rule: it belongs here once the app has accepted a
# course built on it. `single-plate` stays the default so Phase 1's definition
# of done keeps producing the bytes it closed on.
BOARDS: Mapping[str, tuple[tuple[int, int], ...] | None] = {
    "single-plate": None,
    "standard-square": STANDARD_SQUARE,
}

# What each claim means, in one clause, for the line the command prints beside
# its output. The status itself comes from `graph.start_goal_status` -- the
# claim surface -- so the command reports the record rather than forming a
# second opinion about its own course.
CLAIM_NOTES: Mapping[ConnectionStatus, str] = {
    ConnectionStatus.CONNECTED: "this placement is in the rendered record",
    ConnectionStatus.DISCONNECTED: "the record says this placement does not connect",
    ConnectionStatus.UNMEASURED: (
        "no render has tested this placement; render it to find out"
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="traxgen",
        description="Generate GraviTrax .course files the official app accepts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a .course file for a piece set")
    gen.add_argument(
        "--set",
        required=True,
        choices=sorted(SETS),
        help="the piece set to generate for",
    )
    gen.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output path (default: <set>.course in the current directory)",
    )
    gen.add_argument(
        "--board",
        default="single-plate",
        choices=sorted(BOARDS),
        help="the baseplate arrangement to generate onto (default: single-plate)",
    )
    gen.add_argument(
        "--measured-only",
        action="store_true",
        help=(
            "refuse any placement the rendered record has not measured CONNECTED, "
            "instead of proposing one the connection model predicts"
        ),
    )
    gen.add_argument(
        "--no-validate",
        action="store_true",
        help="skip strict validation before writing (for probing the validator itself)",
    )
    return parser


def _board_generator(board: str, *, measured_only: bool) -> Generator:
    """The generator for `board`, with the run's flags already bound."""
    plate_offsets = BOARDS[board]
    if plate_offsets is None:
        return generate_minimal
    return partial(
        generate_multi_plate,
        plate_offsets=plate_offsets,
        measured_only=measured_only,
    )


def main(
    argv: list[str] | None = None,
    *,
    generate: Generator | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = build_parser().parse_args(argv)

    inventory = SETS[args.set]
    out: Path = args.out if args.out is not None else Path(f"{args.set}.course")

    # An injected generator wins over `--board`, which is what lets a test hand
    # in a known-bad course without also having to name a board.
    chosen = generate or _board_generator(
        args.board, measured_only=args.measured_only
    )
    try:
        course = chosen(inventory)
    except (NoBuildablePlacementError, UnmodelledGoalKindError) as exc:
        print(f"refusing to write {out}: {exc}", file=stderr)
        return 3
    if not args.no_validate:
        try:
            validate_strict(course, inventory)
        except ValidationError as exc:
            print(f"refusing to write {out}: {len(exc.violations)} validation error(s)",
                  file=stderr)
            for v in exc.violations:
                print(f"  {v.rule.name}: {v.message}", file=stderr)
            return 1

    payload = serialize_course(course)
    out.write_bytes(payload)
    print(f"wrote {len(payload)} bytes to {out}", file=stdout)
    status = start_goal_status(course)
    claim = "none (no starter/goal pair)" if status is None else (
        f"{status.name} ({CLAIM_NOTES[status]})"
    )
    print(f"claim: {claim}", file=stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
