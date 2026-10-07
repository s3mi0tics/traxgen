# tests/test_main_menu_wait.py
"""Offline tests for `wait_for_main_menu` -- the harness's first positive screen test.

Every guard before this one recognised a screen the flow had been burned by.
This one recognises the screen the flow needs to *start* from, and the tests
here pin the two things that make that safe: the signature separates the menu
from every neighbour it has (measured, as fixtures), and the wait is bounded
and says which of two failures it hit.

The frames are real captures from the 2026-09-07 cold boot (app 2.8), reduced
to the signature geometry: the t=50s menu is the shipped reference, the t=120s
menu is an *independent* capture of the same screen 70s of animation later, and
the splash, the blank frame before it and the Load-track dialog are the three
non-menu screens the flow can be looking at. So the separation test compares
two captures, not a frame against itself.

The polling tests inject a clock whose `sleep` advances it -- the same seam
`test_emulator.py` uses -- so a 90s ceiling is exercised in microseconds and
the elapsed figure the wait reports is deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_android_foreground import LAUNCHER_DUMP, FakeAdb, FakeClock
from traxgen.android import (
    KNOWN_SCREEN_DISTANCE,
    AdbContext,
    FrameUnreadableError,
    MenuArrival,
    UiConditionTimeout,
    WrongForegroundAppError,
    load_known_screen,
    main_menu_signature,
    reset_to_main_menu,
    screen_distance,
    wait_for_main_menu,
)

FRAMES = Path(__file__).parent / "fixtures" / "frames"
MENU_T120 = (FRAMES / "main_menu_t120.png").read_bytes()
SPLASH = (FRAMES / "splash.png").read_bytes()
BLANK_WHITE = (FRAMES / "blank_white.png").read_bytes()
LOAD_TRACK_DIALOG = (FRAMES / "load_track_dialog.png").read_bytes()
# A menu frame cut off before its IEND chunk -- the shape s36 lost at poll 8.
TRUNCATED_MENU = MENU_T120[:-12]
BUILD_TUTORIAL = (
    Path(__file__).parent.parent / "traxgen" / "data" / "refused_screens" / "build_tutorial.png"
).read_bytes()


def ctx_on_clock(fake: FakeAdb, clock: FakeClock) -> AdbContext:
    return AdbContext(adb_path=Path("/nonexistent/adb"), runner=fake, sleep=clock.sleep)


def test_signature_separates_the_menu_from_every_neighbour() -> None:
    """The measured table from android.py, as a check rather than a comment."""
    menu = main_menu_signature()
    assert screen_distance(MENU_T120, menu) < KNOWN_SCREEN_DISTANCE / 3
    for name, frame in [
        ("splash", SPLASH),
        ("blank_white", BLANK_WHITE),
        ("load_track_dialog", LOAD_TRACK_DIALOG),
        ("build_tutorial", BUILD_TUTORIAL),
    ]:
        assert screen_distance(frame, menu) > 2 * KNOWN_SCREEN_DISTANCE, name


def test_shipped_signature_is_the_fixture_it_claims_to_be() -> None:
    menu = load_known_screen("main_menu")
    assert (menu.name, menu.width, menu.height) == ("main_menu", 150, 67)
    assert main_menu_signature() == menu


def test_wait_returns_when_the_splash_clears() -> None:
    """Blank, splash, splash, menu: four polls, three intervals, and the report says so."""
    fake = FakeAdb(screencap_pngs=[BLANK_WHITE, SPLASH, SPLASH, MENU_T120])
    clock = FakeClock()
    arrival = wait_for_main_menu(ctx_on_clock(fake, clock), interval=2.0, clock=clock)
    assert isinstance(arrival, MenuArrival)
    assert arrival.polls == 4
    assert arrival.elapsed == pytest.approx(6.0)
    assert arrival.distance < KNOWN_SCREEN_DISTANCE
    assert fake.screencaps_served == 4


def test_wait_times_out_naming_the_distance_when_the_app_is_up() -> None:
    """A splash that never clears, with the app in front, is a timeout that carries
    the last distance -- so a redesigned menu (stale fixture) reads differently
    from an app that never got past its splash."""
    fake = FakeAdb(screencap_pngs=[SPLASH])
    clock = FakeClock()
    with pytest.raises(UiConditionTimeout) as exc:
        wait_for_main_menu(ctx_on_clock(fake, clock), timeout=10.0, interval=2.0, clock=clock)
    message = str(exc.value)
    assert "22.0" in message and "main_menu" in message
    assert clock.now >= 10.0
    assert fake.screencaps_served == 6  # t = 0, 2, 4, 6, 8, 10


def test_wait_names_a_relaunch_that_did_not_take() -> None:
    fake = FakeAdb(screencap_pngs=[SPLASH], foreground_dump=LAUNCHER_DUMP)
    clock = FakeClock()
    with pytest.raises(WrongForegroundAppError, match="is in the foreground, not"):
        wait_for_main_menu(ctx_on_clock(fake, clock), timeout=0.0, clock=clock)


def test_an_app_that_left_the_front_keeps_what_the_wait_saw() -> None:
    """Launcher in front at the ceiling is `WrongForegroundAppError`, as before, now
    with the wait's polls and skipped frames as a note (s37: a live run ended with
    the launcher in front and nothing said what the wait had seen)."""
    fake = FakeAdb(
        screencap_pngs=[SPLASH, TRUNCATED_MENU, SPLASH], foreground_dump=LAUNCHER_DUMP
    )
    clock = FakeClock()
    with pytest.raises(WrongForegroundAppError) as exc:
        wait_for_main_menu(ctx_on_clock(fake, clock), timeout=10.0, interval=2.0, clock=clock)
    [note] = exc.value.__notes__
    assert "(6 polls)" in note
    assert "1 of 6 frames unreadable" in note


def test_reset_to_main_menu_stops_launches_then_polls() -> None:
    fake = FakeAdb(screencap_pngs=[SPLASH, MENU_T120])
    clock = FakeClock()
    arrival = reset_to_main_menu(ctx_on_clock(fake, clock), clock=clock)
    stop = fake.index_of(lambda c: "force-stop" in c)
    launch = fake.index_of(lambda c: "monkey" in c)
    poll = fake.index_of(lambda c: "screencap" in c)
    assert stop < launch < poll
    assert arrival.polls == 2


def test_default_ctx_sleep_paces_the_polls() -> None:
    """The wait sleeps through `ctx.sleep`, the injectable seam -- never `time.sleep`."""
    slept: list[float] = []
    fake = FakeAdb(screencap_pngs=[SPLASH, SPLASH, MENU_T120])
    ctx = AdbContext(adb_path=Path("/nonexistent/adb"), runner=fake, sleep=slept.append)
    wait_for_main_menu(ctx, interval=2.0, clock=FakeClock())
    assert slept == [2.0, 2.0]


# --- An unreadable frame is a missed look (s37, plan item 17(d)) -------------


def test_a_lost_frame_is_skipped_counted_and_reported() -> None:
    """s36's failure replayed: splash, a truncated frame, splash, menu. The wait
    keeps going past the lost frame and says which poll it lost and how."""
    fake = FakeAdb(screencap_pngs=[SPLASH, TRUNCATED_MENU, SPLASH, MENU_T120])
    clock = FakeClock()
    arrival = wait_for_main_menu(ctx_on_clock(fake, clock), interval=2.0, clock=clock)
    assert arrival.polls == 4
    assert len(arrival.unreadable) == 1
    assert "main-menu poll 2" in arrival.unreadable[0]
    assert "no IEND chunk" in arrival.unreadable[0]
    assert "unreadable frames skipped: 1 (main-menu poll 2" in arrival.line()


def test_a_clean_wait_reports_zero_skipped() -> None:
    """Zero is reported, not omitted: plan #20 needs the boots that lost nothing."""
    fake = FakeAdb(screencap_pngs=[SPLASH, MENU_T120])
    clock = FakeClock()
    arrival = wait_for_main_menu(ctx_on_clock(fake, clock), interval=2.0, clock=clock)
    assert arrival.unreadable == ()
    assert arrival.line().endswith("unreadable frames skipped: 0")


def test_a_device_that_stopped_answering_is_named_not_waited_out() -> None:
    """Three screencaps in a row with no frame in them -- empty, or bytes that are
    not a PNG -- raise on the third, 6s in rather than at the 90s ceiling, and
    the error carries all three."""
    fake = FakeAdb(screencap_pngs=[SPLASH, b"", b"error: device offline\n", b""])
    clock = FakeClock()
    with pytest.raises(FrameUnreadableError, match="came back with no frame") as exc:
        wait_for_main_menu(ctx_on_clock(fake, clock), interval=2.0, clock=clock)
    assert fake.screencaps_served == 4
    assert clock.now == pytest.approx(6.0)
    message = str(exc.value)
    assert message.startswith("3 screencaps in a row")
    assert message.count("returned 0 bytes") == 2
    assert "not a PNG" in message


def test_a_readable_frame_resets_the_run() -> None:
    """Two lost, a splash, two lost, the menu: never three in a row, so it arrives."""
    fake = FakeAdb(screencap_pngs=[b"", b"", SPLASH, b"", b"", MENU_T120])
    clock = FakeClock()
    arrival = wait_for_main_menu(ctx_on_clock(fake, clock), interval=2.0, clock=clock)
    assert arrival.polls == 6
    assert len(arrival.unreadable) == 4


def test_truncated_frames_in_a_row_are_skipped_not_fatal() -> None:
    """s37's live failure: polls 5-7 all truncated, each carrying most of an image.
    A frame that started arriving is a device that answered, so the wait skips
    all three and arrives instead of calling the device dead."""
    fake = FakeAdb(screencap_pngs=[SPLASH] * 4 + [TRUNCATED_MENU] * 3 + [SPLASH, MENU_T120])
    clock = FakeClock()
    arrival = wait_for_main_menu(ctx_on_clock(fake, clock), interval=2.0, clock=clock)
    assert arrival.polls == 9
    assert [m.split(":")[0] for m in arrival.unreadable] == [
        "main-menu poll 5",
        "main-menu poll 6",
        "main-menu poll 7",
    ]


def test_a_truncated_frame_breaks_a_run_of_frameless_ones() -> None:
    """Empty, empty, truncated, empty, empty, menu: the truncated frame shows the
    device answering, so the run restarts and the wait arrives."""
    fake = FakeAdb(screencap_pngs=[b"", b"", TRUNCATED_MENU, b"", b"", MENU_T120])
    clock = FakeClock()
    arrival = wait_for_main_menu(ctx_on_clock(fake, clock), interval=2.0, clock=clock)
    assert (arrival.polls, len(arrival.unreadable)) == (6, 5)


def test_a_timeout_counts_the_frames_it_skipped() -> None:
    fake = FakeAdb(screencap_pngs=[SPLASH, TRUNCATED_MENU, SPLASH])
    clock = FakeClock()
    with pytest.raises(UiConditionTimeout, match="1 of 6 frames unreadable"):
        wait_for_main_menu(ctx_on_clock(fake, clock), timeout=10.0, interval=2.0, clock=clock)


def test_a_timeout_with_no_readable_frame_claims_no_distance() -> None:
    """Fewer polls than the run limit, all lost: there is no last distance, and
    the message must not format one (it would have crashed on None before s37)."""
    fake = FakeAdb(screencap_pngs=[b""])
    clock = FakeClock()
    with pytest.raises(UiConditionTimeout, match="no frame was readable; 1 of 1"):
        wait_for_main_menu(ctx_on_clock(fake, clock), timeout=0.0, clock=clock)
