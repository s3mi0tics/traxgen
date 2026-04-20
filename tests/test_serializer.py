"""
Byte-compare round-trip tests for the serializer.

Parses a real .course file, serializes the result, asserts the bytes match
exactly. Any drift means the serializer is not a true inverse of the parser —
on mismatch we report the first differing byte offset so it can be mapped
back to a field via the parser's cursor logic.

Path: traxgen/tests/test_serializer.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traxgen.parser import parse_course
from traxgen.serializer import serialize_course

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _first_diff_offset(a: bytes, b: bytes) -> int:
    """Offset of first differing byte, or len(shorter) if one is a prefix of the other."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))


@pytest.mark.parametrize("code", ["GDZJZA3J3T"])
def test_serialize_round_trip_byte_compare(code: str) -> None:
    """serialize(parse(bytes)) == bytes for a real POWER_2022 course."""
    course_bytes = (FIXTURES_DIR / f"{code}.course").read_bytes()
    course = parse_course(course_bytes)
    result = serialize_course(course)
    if result != course_bytes:
        offset = _first_diff_offset(result, course_bytes)
        expected_ctx = course_bytes[max(0, offset - 8) : offset + 8].hex(" ")
        actual_ctx = result[max(0, offset - 8) : offset + 8].hex(" ")
        raise AssertionError(
            f"byte-compare mismatch for {code}:\n"
            f"  result   = {len(result)} bytes\n"
            f"  original = {len(course_bytes)} bytes\n"
            f"  first diff at offset {offset}\n"
            f"  expected [offset-8..offset+8]: {expected_ctx}\n"
            f"  actual   [offset-8..offset+8]: {actual_ctx}"
        )
