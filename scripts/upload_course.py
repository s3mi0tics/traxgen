"""CLI wrapper around traxgen.uploader: upload a .course binary and print the share code.

Usage:

    uv run python -m scripts.upload_course path/to/course.course
    uv run python -m scripts.upload_course path/to/course.course --timeout 60

Output convention:

    - stdout: the share code only, newline-terminated. Suitable for
      `code=$(uv run python -m scripts.upload_course foo.course)`.
    - stderr: human-readable context (source path, byte count, upload URL,
      "share code:" label on success, error details on failure).

Exit codes:

    0  success
    1  usage / file error (argparse already uses 2 for argparse-level errors)
    2  reserved by argparse
    3  upload failed (UploadError or subclass)

Path: traxgen/scripts/upload_course.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from traxgen.uploader import UPLOAD_URL, UploadError, upload_course


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the upload command."""
    parser = argparse.ArgumentParser(
        prog="upload_course",
        description=(
            "Upload a GraviTrax .course binary to Ravensburger's share-code "
            "endpoint and print the assigned 10-character code."
        ),
    )
    parser.add_argument(
        "course_file",
        type=Path,
        help="Path to a POWER_2022 .course binary.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30.0).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = _parse_args(argv)
    path: Path = args.course_file

    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    try:
        binary = path.read_bytes()
    except OSError as exc:
        print(f"error: could not read {path}: {exc}", file=sys.stderr)
        return 1

    print(f"uploading {path.name} ({len(binary)} bytes) to {UPLOAD_URL}", file=sys.stderr)

    try:
        code = upload_course(binary, timeout=args.timeout)
    except UploadError as exc:
        print(f"upload failed: {exc}", file=sys.stderr)
        return 3

    print(f"share code: {code}", file=sys.stderr)
    print(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
