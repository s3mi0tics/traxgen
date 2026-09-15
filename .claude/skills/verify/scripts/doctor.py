#!/usr/bin/env python3
"""Read-only: is this checkout worth driving the verification chain on?

    uv run python .claude/skills/verify/scripts/doctor.py

Checks and prints, never repairs, never starts or kills anything. Always
prints every line: this is the script you run when something is already
broken, so no single failure may take the report down.

  repo      the git checkout this script lives in, and its HEAD. FAILs when
            git is missing or the script is not inside a checkout. Notes
            modified tracked files (the run would judge uncommitted code).
  import    traxgen imports, and from this checkout rather than another one
  network   TCP to the upload host on 443 (the upload stage needs it)
  render    adb present; whether an emulator is already running. `--render`
            uses `--fresh`, which KILLS any running emulator: if one is up and
            you did not start it, do not pass --render.

Exit 0 when repo, import and network pass. The render line is information:
most runs do not render.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

UPLOAD_HOST = "gravitrax.link.ravensburger.com"
HERE = Path(__file__).resolve().parent


def _run(*cmd: str) -> str | None:
    """stdout of `cmd` run from this script's directory; None when it failed or is missing."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def check_repo() -> Path | None:
    top = _run("git", "rev-parse", "--show-toplevel")
    head = _run("git", "rev-parse", "--short", "HEAD")
    if not top or not head:
        print(f"FAIL repo git missing, or {HERE} is not inside a git checkout")
        return None
    dirty = bool(_run("git", "status", "--porcelain", "--untracked-files=no"))
    print(f"PASS repo {top} head {head}{' (tracked files modified)' if dirty else ''}")
    return Path(top)


def check_import(root: Path | None) -> bool:
    try:
        import traxgen
    except Exception as exc:  # any import failure is the finding
        print(f"FAIL import traxgen: {type(exc).__name__}: {exc} (run `uv sync`, then use `uv run`)")
        return False
    where = Path(traxgen.__file__).resolve()
    if root is None or root not in where.parents:
        print(f"FAIL import traxgen resolves to {where}, not inside {root or 'a checkout'}")
        return False
    print(f"PASS import {where}")
    return True


def check_network() -> bool:
    try:
        socket.create_connection((UPLOAD_HOST, 443), timeout=5).close()
    except OSError as exc:
        print(f"FAIL network {UPLOAD_HOST}:443: {exc} (use --no-upload)")
        return False
    print(f"PASS network {UPLOAD_HOST}:443 reachable")
    return True


def report_render() -> None:
    sdk = os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))
    adb = Path(sdk) / "platform-tools/adb"
    running = bool(shutil.which("pgrep")) and bool(_run("pgrep", "-f", "qemu-system"))
    print(f"INFO render adb {'present' if adb.exists() else 'MISSING'}; "
          f"emulator {'RUNNING (--render would kill it)' if running else 'not running'}")


def main() -> int:
    root = check_repo()
    results = [root is not None, check_import(root), check_network()]
    report_render()
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
