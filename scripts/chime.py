# scripts/chime.py
"""A sound when a long command finishes, because the terminal gives no signal.

    from scripts.chime import chime
    chime(ok=True)                 # Glass  -- it worked
    chime(ok=False)                # Basso  -- it did not
    chime(ok=True, enabled=False)  # silence, for queues and CI

Why this exists at all. A cold boot is ~25s, a render ~90s, and a campaign runs
past ten minutes. Nothing on this machine says when one ends, so the human waits
by watching -- which is the cheapest thing in the flow to automate and the last
thing anyone thinks to. Two sounds rather than one: a run that *failed* is the
one most worth hearing about from the next room, and a single "done" tone makes
the two outcomes sound identical.

Degrades quietly, in this order: `afplay` with a macOS system sound, then the
terminal bell, then nothing. It is a convenience, so it never raises and never
changes an exit code -- a harness that died because its notification failed
would be a worse trade than no notification.

macOS-only in practice. `afplay` does not exist on Linux, which is why the
lookup is a file check plus a caught `OSError` rather than a platform string:
the tests run in a Linux VM, and a check written against `sys.platform` would
pass there while telling us nothing about the Mac.

Path: traxgen/scripts/chime.py
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

SOUNDS_DIR = Path("/System/Library/Sounds")
DONE_SOUND = "Glass.aiff"
FAILED_SOUND = "Basso.aiff"
# `afplay` blocks for the length of the clip. That is deliberate: detaching it
# races the interpreter's own exit, and a sound that plays half the time is
# worse than one that costs a second.
PLAY_TIMEOUT = 10.0


def _bell(text: str) -> None:
    print(text, end="", file=sys.stderr, flush=True)


def chime(
    ok: bool,
    *,
    enabled: bool = True,
    runner: Callable[..., object] = subprocess.run,
    out: Callable[[str], None] = _bell,
    sounds_dir: Path = SOUNDS_DIR,
) -> str:
    """Make a noise appropriate to `ok`. Returns what it actually did.

    The return value is the seam the tests read: `"Glass.aiff"`, `"Basso.aiff"`,
    `"bell"` or `"off"`. Saying which fallback fired is the difference between
    "the chime ran" and "the chime made a sound", and only the second is what
    was asked for.
    """
    if not enabled:
        return "off"
    sound = DONE_SOUND if ok else FAILED_SOUND
    path = sounds_dir / sound
    if path.is_file():
        try:
            runner(["afplay", str(path)], check=False, capture_output=True, timeout=PLAY_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            pass
        else:
            return sound
    out("\a")
    return "bell"
