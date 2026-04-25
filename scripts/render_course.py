"""CLI: drive the GraviTrax app to render a share code and screenshot the result.

Usage:

    uv run python -m scripts.render_course X3WEQ6F296
    uv run python -m scripts.render_course MT756NLLMI --name invalid_disconnected_rail
    uv run python -m scripts.render_course HKN3ZZYUI7 --no-cleanup --no-disclaimer

Preconditions:
    - Android emulator (AVD: traxgen_m6c) is running and booted
    - GraviTrax app is launched and showing the main menu

Output:
    - stdout: the screenshot path, newline-terminated
    - stderr: progress messages

Exit codes:
    0  success
    1  bad arguments / missing emulator
    2  reserved by argparse
    3  automation failure during the render flow

Path: traxgen/scripts/render_course.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from traxgen.android import (
    AndroidAutomationError,
    DEFAULT_SCREENSHOT_DIR,
    render_course,
    resolve_context,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="render_course",
        description=(
            "Drive the Android emulator's GraviTrax app to render a share code "
            "and capture a screenshot. Requires the emulator to be running with "
            "the app at the main menu."
        ),
    )
    parser.add_argument(
        "code",
        help="10-character GraviTrax share code (e.g., HKN3ZZYUI7).",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Screenshot filename stem (no extension). Defaults to rendered_<code>.",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=DEFAULT_SCREENSHOT_DIR,
        help=f"Output directory (default: {DEFAULT_SCREENSHOT_DIR}).",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip the back-out + delete-track cleanup. Leaves app at render screen.",
    )
    parser.add_argument(
        "--no-disclaimer",
        action="store_true",
        help="Skip the Load tracks disclaimer tap. Use after dismissed in current session.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = _parse_args(argv)

    code = args.code.strip()
    if len(code) != 10 or not code.isalnum():
        print(
            f"error: expected 10-char alphanumeric code, got {args.code!r}",
            file=sys.stderr,
        )
        return 1

    print(f"rendering {code} via emulator...", file=sys.stderr)

    try:
        ctx = resolve_context()
        out_path = render_course(
            code,
            ctx=ctx,
            screenshot_dir=args.screenshot_dir,
            screenshot_name=args.name,
            cleanup=not args.no_cleanup,
            expect_disclaimer=not args.no_disclaimer,
        )
    except AndroidAutomationError as exc:
        print(f"render failed: {exc}", file=sys.stderr)
        return 3

    print(f"screenshot saved: {out_path}", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
