"""Tests for the capture guard -- every live screencap is checked whole before use.

Path: traxgen/tests/test_screencap_guard.py

Why this file exists. `adb exec-out screencap` exits 0 on a dying device, so
nothing above it notices until something tries to decode the bytes. s35 hit both
shapes in one session: an empty buffer, and a PNG cut off mid-stream that Pillow
accepted at the header and then refused at `load()` with `image file is
truncated`, thirty lines into a traceback that named an image library rather than
a device. `capture_png` turns both into one named harness error.

The truncated fixture is a **real** device frame with its tail removed, and the
first test asserts that Pillow still parses its header -- because a fixture that
failed at the header would be testing a case the guard's first check already
catches, and the whole point of the trailer check is the case that gets past it.

Everything here is offline: the runner seam is a fake that returns whatever bytes
the test says the device produced.
"""

from __future__ import annotations

import io
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from PIL import Image

from traxgen.android import (
    AdbContext,
    FrameUnreadableError,
    capture_png,
    screencap,
    wait_for_stable_frame,
)

ADB = Path("/sdk/platform-tools/adb")

# A real frame off the device, committed as the main-menu signature.
WHOLE_PNG = (
    Path(__file__).parent.parent / "traxgen" / "data" / "known_screens" / "main_menu.png"
).read_bytes()
# Cut mid-stream: header intact, IEND gone. This is the s35 shape.
TRUNCATED_PNG = WHOLE_PNG[: len(WHOLE_PNG) // 2]


class FakeCapture:
    """Stands in for `subprocess.run`, returning the bytes a test says adb produced."""

    def __init__(self, stdout: bytes, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.calls: list[list[str]] = []

    def __call__(
        self, cmd: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess:
        argv = [str(part) for part in cmd]
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, b"")


def _ctx(stdout: bytes) -> tuple[AdbContext, FakeCapture]:
    fake = FakeCapture(stdout)
    ctx = AdbContext(adb_path=ADB, runner=fake, sleep=lambda _: None)
    return ctx, fake


def test_the_truncated_fixture_is_the_case_a_header_check_would_miss() -> None:
    """Pillow parses its header and fails only on decode -- s35's actual failure."""
    image = Image.open(io.BytesIO(TRUNCATED_PNG))
    assert image.size == Image.open(io.BytesIO(WHOLE_PNG)).size
    with pytest.raises(OSError, match="truncated"):
        image.load()


def test_a_whole_frame_passes_through_byte_for_byte() -> None:
    ctx, fake = _ctx(WHOLE_PNG)
    assert capture_png(ctx) == WHOLE_PNG
    assert fake.calls == [[str(ADB), "exec-out", "screencap", "-p"]]


def test_an_empty_capture_is_named_rather_than_decoded() -> None:
    ctx, _ = _ctx(b"")
    with pytest.raises(FrameUnreadableError, match="0 bytes"):
        capture_png(ctx)


def test_bytes_that_are_not_a_png_report_what_arrived_and_where() -> None:
    ctx, _ = _ctx(b"error: device offline\n")
    with pytest.raises(FrameUnreadableError) as exc:
        capture_png(ctx, what="main-menu poll 7")
    message = str(exc.value)
    assert "not a PNG" in message
    assert "main-menu poll 7" in message
    assert "22 bytes" in message


def test_a_truncated_frame_is_refused_on_its_missing_trailer() -> None:
    ctx, _ = _ctx(TRUNCATED_PNG)
    with pytest.raises(FrameUnreadableError, match="truncated"):
        capture_png(ctx)


def test_a_refused_capture_writes_no_file(tmp_path: Path) -> None:
    """The old path wrote the bad bytes to disk first, leaving a corrupt artifact."""
    ctx, _ = _ctx(TRUNCATED_PNG)
    dest = tmp_path / "frame.png"
    with pytest.raises(FrameUnreadableError):
        screencap(ctx, dest)
    assert not dest.exists()


def test_an_injected_sampler_is_not_subject_to_the_guard() -> None:
    """Deliberate scoping: a fake's bytes are the test's business, not the device's.

    `wait_for_stable_frame` takes a `sample_fn` seam that offline tests feed
    synthetic frames through. Putting the PNG guard inside the sampling loop
    rather than in the live capture would have broken every one of them, and
    would have been checking the test's fixtures rather than the device.
    """
    frames = iter([WHOLE_PNG, WHOLE_PNG, WHOLE_PNG, WHOLE_PNG])
    stability = wait_for_stable_frame(
        sample_fn=lambda: next(frames),
        required=3,
        interval=0.0,
        sleep_fn=lambda _: None,
        clock=iter([0.0] * 20).__next__,
    )
    assert stability.required == 3
