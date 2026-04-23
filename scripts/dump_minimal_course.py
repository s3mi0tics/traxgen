"""Dump the M5.b-minimal course to a .course file for app sideloading.

Usage: uv run python -m scripts.dump_minimal_course

Writes to /tmp/traxgen-minimal.course by default. This is the M6
handoff point — generate bytes here, sideload into the GraviTrax app,
see if it opens. Any failure is a bug (in the generator, serializer,
or our understanding of the format).

Path: traxgen/scripts/dump_minimal_course.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from traxgen.generator import generate_minimal
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.serializer import serialize_course
from traxgen.validator import validate_strict


def main() -> int:
    """Generate, validate, serialize, write to disk."""
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/traxgen-minimal.course")

    course = generate_minimal()
    validate_strict(course, PRO_VERTICAL_STARTER_SET)
    payload = serialize_course(course)
    out_path.write_bytes(payload)

    print(f"wrote {len(payload)} bytes to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
