# tests/test_load_course.py
"""Every path that opens a course refuses a screen with no course on it (s48-t1).

`load_course` is the one copy of the load steps. Until s48 the probe's link load
had its own copy, which went through none of `render_course`'s guards and
recorded the build tutorial as `inactive` with no error (#68). So each of the
three screens below is tested twice: on `load_course` itself, with no placement
reading asked for, and on the probe's `load_by_link`, the path that failed.

The three screens, and the guard each one meets:
- the build tutorial, an empty editor: the refused-screen signature;
- a loading screen, mostly near-white: the near-white check;
- the launcher in front: the foreground check.

All offline, through the same fake adb as the foreground tests: it records every
call, so a test can say a guard fired *and* that nothing after it ran.
"""

from __future__ import annotations

import io
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts import probe_finish_frames
from tests.test_android_foreground import (
    GRAVITRAX_DUMP,
    IS_SCREENCAP,
    IS_TAP,
    LAUNCHER_DUMP,
    MAIN_MENU_PNG,
    PNG_FRAME,
    FakeAdb,
    ctx_with,
)
from traxgen.android import (
    OracleFrameError,
    RefusedScreenError,
    WrongForegroundAppError,
    load_course,
)

FRAMES = Path(__file__).parent / "fixtures" / "frames"
# A real capture of the build tutorial (2026-08-25), not the shipped reference itself.
TUTORIAL_FRAME = (FRAMES / "arm1_E_on_completer.png").read_bytes()
IS_LINK = lambda c: "android.intent.action.VIEW" in c  # noqa: E731


def _solid_png(colour: tuple[int, int, int]) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (2400, 1080), colour).save(buffer, format="PNG")
    return buffer.getvalue()


# A loading screen at device geometry: every pixel near-white.
LOADING_FRAME = _solid_png((250, 250, 250))


class LauncherAfterCapture(FakeAdb):
    """GraviTrax in front until the course frame is taken, the launcher after it.

    The app has to be in front for the menu wait and the first action, or the
    test would pass on an earlier guard than the one it is about.
    """

    def __init__(self, *, course_screencap: int, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.course_screencap = course_screencap

    def __call__(self, cmd: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess:
        gone = self.screencaps_served >= self.course_screencap
        self.foreground_dump = LAUNCHER_DUMP if gone else GRAVITRAX_DUMP
        return super().__call__(cmd, **kwargs)


def _taps_after_last_screencap(fake: FakeAdb) -> int:
    last = max(i for i, argv in enumerate(fake.calls) if IS_SCREENCAP(" ".join(argv)))
    return sum(1 for argv in fake.calls[last + 1 :] if IS_TAP(" ".join(argv)))


# --- load_course, with no reading asked for --------------------------------


def test_load_course_refuses_the_build_tutorial(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_png=TUTORIAL_FRAME)
    with pytest.raises(RefusedScreenError) as caught:
        load_course(ctx_with(fake), "ABC1234567", tmp_path / "f.png", by_link=True)
    assert caught.value.screen == "build_tutorial"
    assert (tmp_path / "f.png").exists(), "the frame stays on disk for diagnosis"


def test_load_course_refuses_a_loading_screen(tmp_path: Path) -> None:
    """Before s48 this check ran only inside the placement reading, so a finish-only
    render would have pressed play on a loading screen."""
    fake = FakeAdb(screencap_png=LOADING_FRAME)
    with pytest.raises(OracleFrameError, match="near-white"):
        load_course(ctx_with(fake), "ABC1234567", tmp_path / "f.png", by_link=True)


def test_load_course_refuses_the_launcher_before_its_first_action(tmp_path: Path) -> None:
    fake = FakeAdb(foreground_dump=LAUNCHER_DUMP)
    with pytest.raises(WrongForegroundAppError):
        load_course(ctx_with(fake), "ABC1234567", tmp_path / "f.png", by_link=True)
    assert not fake.has(IS_TAP) and not fake.has(IS_LINK)


def test_load_course_passes_a_frame_that_is_none_of_them(tmp_path: Path) -> None:
    """The control for the three above: the same call on a plain dark frame returns."""
    fake = FakeAdb(screencap_png=PNG_FRAME)
    out = load_course(ctx_with(fake), "ABC1234567", tmp_path / "f.png", by_link=True)
    assert out.read_bytes() == PNG_FRAME
    assert fake.index_of(IS_LINK) < fake.index_of(IS_SCREENCAP)


# --- the probe's link load: the path that recorded the tutorial (#68) ------


def test_the_probe_refuses_the_build_tutorial_and_leaves_the_editor(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_pngs=(MAIN_MENU_PNG, TUTORIAL_FRAME))
    with pytest.raises(RefusedScreenError):
        probe_finish_frames.load_by_link(ctx_with(fake), "ABC1234567", tmp_path)
    assert _taps_after_last_screencap(fake) == 4, "back, don't save, trash, delete"


def test_the_probe_refuses_a_loading_screen_at_the_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At the load, not at the placement reading: that reading has its own near-white
    check, and a probe that stops taking it must still refuse the frame."""
    read: list[Path] = []
    monkeypatch.setattr(probe_finish_frames, "detect_play_button_state", read.append)
    fake = FakeAdb(screencap_pngs=(MAIN_MENU_PNG, LOADING_FRAME))
    with pytest.raises(OracleFrameError, match="near-white"):
        probe_finish_frames.load_by_link(ctx_with(fake), "ABC1234567", tmp_path)
    assert read == []


def test_the_probe_refuses_the_launcher_after_the_capture(tmp_path: Path) -> None:
    """The menu wait takes screencap 1 and the course frame is screencap 2."""
    fake = LauncherAfterCapture(course_screencap=2, screencap_pngs=(MAIN_MENU_PNG, PNG_FRAME))
    with pytest.raises(WrongForegroundAppError):
        probe_finish_frames.load_by_link(ctx_with(fake), "ABC1234567", tmp_path)
    assert fake.screencaps_served == 2


def test_the_probe_reads_a_frame_that_is_none_of_them(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_pngs=(MAIN_MENU_PNG, PNG_FRAME))
    assert probe_finish_frames.load_by_link(ctx_with(fake), "ABC1234567", tmp_path) == "inactive"
    assert fake.has(IS_LINK)
