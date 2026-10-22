"""render_course loads by share link and, when asked, reads the finish (s43-t1).

The device is faked: these pin the order of the adb calls render_course makes
and what it returns, not the app's behaviour. A fake serves one scripted frame
per screencap, so the play-watch loop's exits are exercised directly.

Path: traxgen/tests/test_render_finish.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import scripts.render_course as script
from tests.test_android_foreground import (
    IS_FOREGROUND_CHECK,
    IS_SCREENCAP,
    IS_TAP,
    FakeAdb,
    ctx_with,
)
from tests.test_refused_screens import DEAD_FRAME
from traxgen.android import (
    COORDS,
    FINISH_BURST_MIN_PIXELS,
    PLAY_BUTTON_SAMPLE_CENTER,
    PLAY_MAX_FRAMES,
    PLAY_START_FRAMES,
    SHARE_LINK,
    STOP_SQUARE_CORNER,
    STOP_SQUARE_MIN_BLUE,
    WAITS,
    AdbContext,
    AndroidAutomationError,
    FinishReading,
    FinishStatus,
    RefusedScreenError,
    RenderResult,
    judge_finish,
    render_course,
    watch_play_run,
)

CODE = "KN6F459ZR3"
IS_LINK = lambda c: "android.intent.action.VIEW" in c  # noqa: E731
IS_TYPING = lambda c: "input text" in c  # noqa: E731
PLAY_TAP = "input tap {} {}".format(*PLAY_BUTTON_SAMPLE_CENTER)
IS_PLAY = lambda c: PLAY_TAP in c  # noqa: E731
TYPED_TAPS = ["input tap {} {}".format(*xy) for xy in ((265, 970), (1200, 630))]
IS_TYPED_TAP = lambda c: any(t in c for t in TYPED_TAPS)  # noqa: E731
LOAD_CONFIRM_TAP = "input tap {} {}".format(*COORDS["load_track_button"])
IS_LOAD_CONFIRM = lambda c: LOAD_CONFIRM_TAP in c  # noqa: E731


def frame(*, stop: bool = False, sparkles: int = 0) -> bytes:
    """A dark board, the play button's corner (stop or idle), and `sparkles` white pixels."""
    img = Image.new("RGB", (2400, 1080), (20, 110, 170))
    draw = ImageDraw.Draw(img)
    draw.rectangle(STOP_SQUARE_CORNER, fill=(221, 232, 161) if stop else (180, 204, 50))
    for i in range(sparkles):
        draw.point((1400 + i % 50, 300 + i // 50), fill=(250, 250, 250))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


IDLE = frame()
# rendered screenshot, before play, the run with its burst, then a still screen
FINISHING_RUN = [IDLE, IDLE, frame(stop=True), frame(stop=True, sparkles=500)] + [IDLE] * 4


def indices(fake: FakeAdb, predicate) -> list[int]:
    return [i for i, argv in enumerate(fake.calls) if predicate(" ".join(argv))]


# --- loading -----------------------------------------------------------------


def test_the_link_route_opens_the_share_link_and_types_nothing(tmp_path: Path) -> None:
    fake = FakeAdb()
    render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False, by_link=True)
    [link] = indices(fake, IS_LINK)
    argv = fake.calls[link]
    assert SHARE_LINK.format(code=CODE) in argv
    assert argv[-1] == ctx_with(fake).package  # named, so no browser can take the link
    assert not fake.has(IS_TYPING)
    assert not fake.has(IS_TYPED_TAP)  # rules out both routes running
    assert indices(fake, IS_FOREGROUND_CHECK)[0] < link < indices(fake, IS_TAP)[0]
    # the load-confirm dialog the link opens is confirmed
    assert indices(fake, IS_LOAD_CONFIRM)[0] > link


def test_the_link_route_waits_for_the_dialog(tmp_path: Path) -> None:
    fake = FakeAdb()
    slept: list[float] = []
    ctx = AdbContext(adb_path=Path("/nonexistent/adb"), runner=fake, sleep=slept.append)
    render_course(CODE, ctx=ctx, screenshot_dir=tmp_path, cleanup=False, by_link=True)
    assert WAITS["after_link"] in slept


def test_the_library_default_is_still_the_typed_route(tmp_path: Path) -> None:
    """Opt-in, so the campaign scripts keep the route their records were measured on."""
    fake = FakeAdb()
    render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False)
    assert fake.has(IS_TYPING)
    assert fake.has(IS_TYPED_TAP)
    assert not fake.has(IS_LINK)


# --- finish ------------------------------------------------------------------


def test_without_detect_finish_play_is_never_pressed(tmp_path: Path) -> None:
    fake = FakeAdb()
    result = render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False)
    assert not fake.has(IS_PLAY)
    assert result.finish is None


def test_a_finishing_run_is_read_and_play_comes_after_both_guards(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_pngs=FINISHING_RUN)
    result = render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, detect_finish=True)
    assert isinstance(result.finish, FinishReading)
    assert result.finish.status is FinishStatus.FINISHED
    assert result.finish.peak_new_white == 500

    [play] = indices(fake, IS_PLAY)
    checks = indices(fake, IS_FOREGROUND_CHECK)
    shots = indices(fake, IS_SCREENCAP)
    # rendered frame, then its closing check, then the before-play frame, then play
    assert shots[0] < checks[1] < shots[1] < play
    # the app is checked again after the run and before the four cleanup taps
    taps = indices(fake, IS_TAP)
    assert checks[-1] > shots[-1]
    assert [t for t in taps if t > checks[-1]] == taps[-4:]


def test_the_before_frame_is_captured_after_the_screenshot_not_reused(tmp_path: Path) -> None:
    """The burst is counted against the screen just before play, not the screenshot.

    The screenshot carries the same white pixels as the burst, so a `before`
    reused from it would cancel the burst out and read NOT_FINISHED.
    """
    sparkly_screenshot = [frame(sparkles=500), IDLE, frame(stop=True, sparkles=500)] + [IDLE] * 4
    fake = FakeAdb(screencap_pngs=sparkly_screenshot)
    result = render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, detect_finish=True)
    assert result.finish is not None
    assert result.finish.status is FinishStatus.FINISHED


def test_a_run_that_never_plays_is_unjudged_not_a_miss(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_png=IDLE)
    result = render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, detect_finish=True)
    assert result.finish is not None
    assert result.finish.status is FinishStatus.UNJUDGED
    assert result.finish.reason == "the stop square never showed"


def test_a_refused_screen_is_never_played(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_png=DEAD_FRAME)
    with pytest.raises(RefusedScreenError):
        render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, detect_finish=True)
    assert not fake.has(IS_PLAY)


# --- the watch loop's exits ----------------------------------------------------


def test_the_watch_stops_once_the_run_is_over_and_the_screen_is_still() -> None:
    fake = FakeAdb(screencap_pngs=[IDLE, frame(stop=True), IDLE, IDLE, IDLE, IDLE, IDLE])
    before, frames = watch_play_run(ctx_with(fake))
    assert before == IDLE
    assert len(frames) == 4  # the stop frame, then three still idle frames


def test_a_marble_that_never_stops_is_bounded_and_unjudged() -> None:
    """The stop square never clears and the clock never moves: the frame cap ends it."""
    fake = FakeAdb(screencap_pngs=[IDLE, frame(stop=True)])
    before, frames = watch_play_run(ctx_with(fake))
    assert len(frames) == PLAY_MAX_FRAMES
    assert judge_finish(before, frames).status is FinishStatus.UNJUDGED


def test_the_time_bound_ends_a_run_on_a_moving_clock() -> None:
    """Each adb call costs a second of fake time, so 10 s runs out long before the cap."""
    fake = FakeAdb(screencap_pngs=[IDLE, frame(stop=True)])
    now = [0.0]

    def tick() -> float:
        now[0] += 1.0
        return now[0]

    ctx = AdbContext(
        adb_path=Path("/nonexistent/adb"), runner=fake, sleep=lambda _: None, clock=tick
    )
    _, frames = watch_play_run(ctx, max_seconds=10.0)
    assert 0 < len(frames) < 10


def test_a_slow_start_does_not_end_the_watch() -> None:
    """Still frames before the stop square first shows are not the end of a run."""
    slow = [IDLE, IDLE, IDLE, IDLE, frame(stop=True), IDLE, IDLE, IDLE, IDLE]
    fake = FakeAdb(screencap_pngs=slow)
    before, frames = watch_play_run(ctx_with(fake))
    assert len(frames) == 7  # three idle, the stop frame, three idle
    assert judge_finish(before, frames).status is FinishStatus.NOT_FINISHED


def test_a_run_that_never_starts_ends_at_the_start_bound() -> None:
    fake = FakeAdb(screencap_png=IDLE)
    _, frames = watch_play_run(ctx_with(fake))
    assert len(frames) == PLAY_START_FRAMES


def test_a_failure_during_the_watch_still_cleans_up_then_raises(tmp_path: Path) -> None:
    """A course left open would put the next render on the wrong screen."""
    fake = FakeAdb(screencap_pngs=[IDLE, IDLE, frame(stop=True), b"not a png"])
    with pytest.raises(AndroidAutomationError):
        render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, detect_finish=True)
    play = indices(fake, IS_PLAY)[0]
    assert len([t for t in indices(fake, IS_TAP) if t > play]) == 4  # the cleanup taps


def test_a_marble_still_running_is_stopped_before_cleanup(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_pngs=[IDLE, IDLE, frame(stop=True)])
    result = render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, detect_finish=True)
    assert result.finish is not None and result.finish.reason == "the run had not ended"
    plays = indices(fake, IS_PLAY)
    assert len(plays) == 2  # play, then stop
    assert len([t for t in indices(fake, IS_TAP) if t > plays[1]]) == 4


def test_a_finished_run_is_not_tapped_again(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_pngs=FINISHING_RUN)
    render_course(CODE, ctx=ctx_with(fake), screenshot_dir=tmp_path, detect_finish=True)
    assert len(indices(fake, IS_PLAY)) == 1


def test_the_still_screen_alone_does_not_end_a_running_marble() -> None:
    """A still frame with the stop square up means the run is still going."""
    still_running = [IDLE] + [frame(stop=True)] * 5 + [IDLE] * 3
    fake = FakeAdb(screencap_pngs=still_running)
    _, frames = watch_play_run(ctx_with(fake))
    assert len(frames) == 8  # ran through the five stop frames, then three idle


# --- the CLI ------------------------------------------------------------------


def test_the_cli_passes_both_flags_and_prints_the_finish(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, object] = {}

    def render(code: str, **kwargs: object) -> RenderResult:
        seen.update(kwargs)
        reading = FinishReading(FinishStatus.FINISHED, 1115, 11, "sparkle burst")
        return RenderResult(Path("s.png"), "active", reading)

    monkeypatch.setattr(script, "resolve_context", lambda: object())
    monkeypatch.setattr(script, "render_course", render)
    argv = [CODE, "--detect-validity", "--detect-finish"]
    assert script.main(argv, chime_fn=lambda ok, **_: "") == 0
    assert seen["detect_finish"] is True and seen["by_link"] is True
    err = capsys.readouterr().err
    assert "play button: active" in err
    assert "finish: finished (peak 1115, 11 frames, sparkle burst)" in err

    script.main([CODE, "--typed"], chime_fn=lambda ok, **_: "")
    assert seen["by_link"] is False and seen["detect_finish"] is False


# --- pins the mutation lens asked for ------------------------------------------


def test_a_burst_on_the_last_frame_counts() -> None:
    """The burst can land as the stop square clears; the last frame is read too."""
    reading = judge_finish(IDLE, [frame(stop=True), frame(sparkles=500)])
    assert reading.status is FinishStatus.FINISHED


def test_a_changing_screen_after_the_run_keeps_the_watch_going() -> None:
    """Stillness is measured against the previous frame, not assumed."""
    trail_a, trail_b = frame(sparkles=2000), frame(sparkles=4000)
    moving = [IDLE, frame(stop=True), trail_a, trail_b, trail_a, trail_b] + [trail_b] * 3
    fake = FakeAdb(screencap_pngs=moving)
    _, frames = watch_play_run(ctx_with(fake))
    assert len(frames) == 8  # the stop frame, four changing frames, then three still


def test_the_finish_and_stop_thresholds_are_the_recorded_numbers() -> None:
    """Literal, so a moved constant fails here: D093 sets 30; s41-t1 measured 161 vs 50 blue."""
    assert FINISH_BURST_MIN_PIXELS == 30
    assert STOP_SQUARE_MIN_BLUE == 105.0
    def at(n: int) -> FinishStatus:
        return judge_finish(IDLE, [frame(stop=True, sparkles=n), IDLE]).status

    assert at(29) is FinishStatus.NOT_FINISHED
    assert at(30) is FinishStatus.FINISHED
