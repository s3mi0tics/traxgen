#!/usr/bin/env python3
"""Read-only: is this checkout worth driving the verification chain on?

    uv run python .claude/skills/verify/scripts/doctor.py

Checks and prints, never repairs, never starts or kills anything:
  repo      HEAD and whether the working tree is dirty (a dirty tree means the
            run judges uncommitted code; say so in any report)
  import    traxgen imports from this checkout, not another one
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


def _run(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def main() -> int:
    ok = True
    root = Path(_run("git", "rev-parse", "--show-toplevel"))
    dirty = bool(_run("git", "status", "--porcelain", "--untracked-files=no"))
    print(f"PASS repo {root} head {_run('git', 'rev-parse', '--short', 'HEAD')}"
          f"{' (tracked files modified)' if dirty else ''}")

    import traxgen

    where = Path(traxgen.__file__).resolve()
    if root in where.parents:
        print(f"PASS import {where}")
    else:
        print(f"FAIL import traxgen resolves to {where}, outside {root}")
        ok = False

    try:
        socket.create_connection((UPLOAD_HOST, 443), timeout=5).close()
        print(f"PASS network {UPLOAD_HOST}:443 reachable")
    except OSError as exc:
        print(f"FAIL network {UPLOAD_HOST}:443: {exc} (use --no-upload)")
        ok = False

    sdk = os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))
    adb = Path(sdk) / "platform-tools/adb"
    running = bool(shutil.which("pgrep")) and bool(_run("pgrep", "-f", "qemu-system"))
    print(f"INFO render adb {'present' if adb.exists() else 'MISSING'}; "
          f"emulator {'RUNNING (--render would kill it)' if running else 'not running'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
