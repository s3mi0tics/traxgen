"""Probe: does a share link open a course in the app without typing the code?

s41-t4. One cold emulator session. Records the app's link filter, then for each code
sends https://gravitrax.link.ravensburger.com/code/<CODE> to the app (package named, so
Android cannot hand it to a browser) and saves a frame every 2 s for 30 s, with the
foreground package beside each. Tried twice per code: app not running, then app at
the main menu. Nothing is classified here.

    uv run python -m scripts.probe_share_link W8IEN7MG92 I4BA3N5V6Y

Path: traxgen/scripts/probe_share_link.py
"""

from __future__ import annotations

import json
import sys
import time

from traxgen.android import (
    DEFAULT_SCREENSHOT_DIR,
    AdbContext,
    FrameUnreadableError,
    _run_adb,
    capture_png,
    force_stop,
    read_foreground_package,
    reset_to_main_menu,
)

OUT = DEFAULT_SCREENSHOT_DIR / "share_link"
LINK = "https://gravitrax.link.ravensburger.com/code/{code}"
FRAMES, INTERVAL = 15, 2.0


def open_link(ctx: AdbContext, code: str) -> str:
    """Send the share link to the app; return `am start -W`'s output."""
    return _run_adb(
        ctx, "shell", "am", "start", "-W", "-a", "android.intent.action.VIEW",
        "-d", LINK.format(code=code), ctx.package, timeout=60.0,
    )


def watch(ctx: AdbContext, folder, label: str) -> list[str]:
    """Save FRAMES frames, INTERVAL apart; return the foreground package at each."""
    seen = []
    for n in range(FRAMES):
        time.sleep(INTERVAL)
        try:
            png = capture_png(ctx, what=f"{label} {n}")
        except FrameUnreadableError:  # truncated frames come while the app starts (#20)
            seen.append("frame unreadable")
            continue
        (folder / f"{label}_{n:02d}.png").write_bytes(png)
        seen.append(read_foreground_package(ctx) or "unreadable")
    return seen


def main(codes: list[str]) -> int:
    from scripts.emulator import session

    OUT.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {}
    with session(out=lambda line: print(line, file=sys.stderr)) as ctx:
        dump = _run_adb(ctx, "shell", "dumpsys", "package", ctx.package)
        (OUT / "dumpsys_package.txt").write_text(dump)
        for code in codes:
            folder = OUT / code
            folder.mkdir(parents=True, exist_ok=True)
            for label in ("cold", "from_menu"):
                if label == "cold":
                    force_stop(ctx)
                else:
                    print(reset_to_main_menu(ctx).line(), file=sys.stderr)
                am = open_link(ctx, code)
                seen = watch(ctx, folder, label)
                record[f"{code}/{label}"] = {"am_start": am, "foreground": seen}
                print(f"{code} {label}: {seen[-1]}", file=sys.stderr)
                force_stop(ctx)
    (OUT / "record.json").write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
