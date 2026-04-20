"""
Round-trip tests for the binary .course parser.

Tests parse a fixture .course file, convert the result to the dict shape
murmelbahn's /dump endpoint produces, and compare against the checked-in
dump.txt oracle using a structural diff. This is the key M2 exit criterion:
the parser is correct iff the diff comes back empty.

Path: traxgen/tests/test_parser.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traxgen._diff import diff_structures
from traxgen._dump_format import course_to_dump_dict
from traxgen.parser import parse_course

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _format_diffs(diffs: list) -> str:
    return "round-trip diff found mismatches:\n" + "\n".join(str(d) for d in diffs)


@pytest.mark.parametrize("code", ["GDZJZA3J3T"])
def test_parse_matches_dump(code: str) -> None:
    """Parsing a .course file produces a dict structurally identical to murmelbahn's /dump output."""
    course_bytes = (FIXTURES_DIR / f"{code}.course").read_bytes()
    expected = json.loads((FIXTURES_DIR / f"{code}.dump.txt").read_text())

    parsed = course_to_dump_dict(parse_course(course_bytes))

    diffs = diff_structures(parsed, expected)
    assert not diffs, _format_diffs(diffs)


def test_parse_consumes_all_bytes() -> None:
    """Parser raises if the binary contains leftover bytes after the course body."""
    course_bytes = (FIXTURES_DIR / "GDZJZA3J3T.course").read_bytes()
    # Should parse cleanly.
    parse_course(course_bytes)
    # Append a byte, expect failure.
    with pytest.raises(ValueError, match="bytes left over"):
        parse_course(course_bytes + b"\x00")
