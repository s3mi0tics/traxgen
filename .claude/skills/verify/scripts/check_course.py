#!/usr/bin/env python3
"""Judge a .course file offline: byte round trip, then the full validator.

    uv run python .claude/skills/verify/scripts/check_course.py COURSE [--set vertical-starter]

Prints one line per finding and a PASS/FAIL line per check:

    PASS round_trip 177 bytes, parse -> serialize is byte-identical
    WARNING START_GOAL_CONNECTED: ...
    PASS validator 0 errors, 1 warnings
    claim: CONNECTED

Exit codes: 0 both checks pass; 1 a check failed; 2 usage.

Why both, and why not the CLI's own validation: `python -m traxgen generate`
runs `validate_strict`, which raises on ERRORs and discards WARNINGs, and it
never parses its own output. This reads the bytes back the way the app would,
so a serializer bug that the in-memory Course hides shows up here.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from traxgen.__main__ import SETS
from traxgen.graph import start_goal_status
from traxgen.parser import parse_course
from traxgen.serializer import serialize_course
from traxgen.validator import Severity, validate


def _first_difference(a: bytes, b: bytes) -> int:
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_course")
    parser.add_argument("course_file", type=Path)
    parser.add_argument("--set", default="vertical-starter", choices=sorted(SETS))
    args = parser.parse_args(argv)

    original = args.course_file.read_bytes()
    print(f"file {args.course_file} {len(original)} bytes "
          f"sha256:{hashlib.sha256(original).hexdigest()}")

    try:
        course = parse_course(original)
    except Exception as exc:  # any parse failure is the finding
        print(f"FAIL round_trip parse raised {type(exc).__name__}: {exc}")
        return 1

    reserialized = serialize_course(course)
    if reserialized != original:
        at = _first_difference(original, reserialized)
        print(f"FAIL round_trip {len(original)} -> {len(reserialized)} bytes, "
              f"first difference at offset {at}")
        return 1
    print(f"PASS round_trip {len(original)} bytes, parse -> serialize is byte-identical")

    violations = validate(course, SETS[args.set])
    for v in violations:
        print(f"{v.severity.name} {v.rule.name}: {v.message}")
    errors = sum(v.severity is Severity.ERROR for v in violations)
    warnings = len(violations) - errors
    verdict = "FAIL" if errors else "PASS"
    print(f"{verdict} validator {errors} errors, {warnings} warnings")

    status = start_goal_status(course)
    print(f"claim: {'none' if status is None else status.name}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
