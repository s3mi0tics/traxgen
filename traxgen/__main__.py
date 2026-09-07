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
2 usage.

Path: traxgen/traxgen/__main__.py
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

from traxgen.domain import Course
from traxgen.generator import generate_minimal
from traxgen.inventory import PRO_VERTICAL_STARTER_SET, Inventory
from traxgen.serializer import serialize_course
from traxgen.validator import ValidationError, validate_strict

Generator = Callable[[Inventory], Course]

# Only sets the generator has been certified against in the app appear here. Adding a
# set is one entry -- after a render through the harness says the app accepts it.
SETS: Mapping[str, Inventory] = {
    "vertical-starter": PRO_VERTICAL_STARTER_SET,
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
        "--no-validate",
        action="store_true",
        help="skip strict validation before writing (for probing the validator itself)",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    generate: Generator = generate_minimal,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = build_parser().parse_args(argv)

    inventory = SETS[args.set]
    out: Path = args.out if args.out is not None else Path(f"{args.set}.course")

    course = generate(inventory)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
