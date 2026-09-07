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
