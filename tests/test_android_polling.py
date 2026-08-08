"""Tests for the harness's UI-state polling (generation-two synchronization).

All offline. The fixture is a real `uiautomator dump` captured from the AVD on
2026-08-07, at the exact moment the goal-rotation sweep's positive control
failed -- the fullscreen extract-mode IME with the share code typed and the OK
button never tapped. Because that hierarchy is just text, everything below runs
with no emulator, and `wait_until` takes injectable clock and sleep functions so
the polling logic costs no real elapsed time either.

The case worth caring about most is `dump_fn` returning None. `uiautomator
dump` fails while a view is animating, which is precisely when a poller is
running, and mistaking that for an error would reintroduce the flakiness
polling exists to remove.

Path: traxgen/tests/test_android_polling.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traxgen.android import (
    COORDS,
    Bounds,
    UiConditionTimeout,
    find_node,
    parse_bounds,
    wait_until,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "uiautomator_ime_extract_view.xml"
).read_text()

OK_BUTTON = "android.widget.Button"
EDIT_TEXT = "android.widget.EditText"


class FakeClock:
    """A clock that only advances when someone sleeps on it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


# --- Bounds parsing --------------------------------------------------------


def test_parse_bounds_reads_uiautomator_format() -> None:
    """`[left,top][right,bottom]` -> Bounds."""
    assert parse_bounds("[2216,252][2384,378]") == Bounds(2216, 252, 2384, 378)


def test_parse_bounds_handles_negative_and_zero_origins() -> None:
    """Bounds can start at the screen edge, or off it when a view is part-scrolled."""
    assert parse_bounds("[0,0][2400,1080]") == Bounds(0, 0, 2400, 1080)
    assert parse_bounds("[-48,-12][120,60]") == Bounds(-48, -12, 120, 60)


def test_parse_bounds_rejects_garbage() -> None:
    """A malformed bounds string is a bug, not a soft failure."""
    with pytest.raises(ValueError, match="unparseable bounds"):
        parse_bounds("not-bounds")


def test_bounds_center_and_containment() -> None:
    """Center is tap-ready; contains answers 'would this tap land here'."""
    b = Bounds(2216, 252, 2384, 378)
    assert b.center == (2300, 315)
    assert b.contains(2300, 315)
    assert not b.contains(2215, 315)
    assert not b.contains(2300, 251)


# --- Node lookup against the captured hierarchy ----------------------------


def test_finds_the_ok_button_in_the_real_dump() -> None:
    """The fixture's OK button is where the live dump said it was."""
    assert find_node(FIXTURE, cls=OK_BUTTON, text="OK") == Bounds(2216, 252, 2384, 378)


def test_calibrated_ime_ok_coordinate_falls_inside_the_real_button() -> None:
    """Regression for 2026-08-07: that failure was timing, not geometry.

    When `ime_ok` stopped working the obvious suspect was a stale tap
    coordinate. It wasn't -- the calibrated point sits inside the button's
    real bounds. Pinning that here means the next person to see this step
    fail doesn't re-derive it, and it fails loudly if the app's layout
    genuinely does move.
    """
    bounds = find_node(FIXTURE, cls=OK_BUTTON, text="OK")
    assert bounds is not None
    assert bounds.contains(*COORDS["ime_ok"])


def test_finds_a_node_by_text_alone() -> None:
    """The typed share code identifies the edit field without a class filter."""
    assert find_node(FIXTURE, text="KN6F459ZR3") == Bounds(144, 264, 2216, 366)


def test_finds_a_node_by_class_alone() -> None:
    """Class-only lookup returns the first match in document order."""
    assert find_node(FIXTURE, cls=EDIT_TEXT) == Bounds(144, 264, 2216, 366)


def test_absent_node_is_none_not_an_error() -> None:
    """'Not there' is a normal answer -- it's how disappearance is detected."""
    assert find_node(FIXTURE, cls=OK_BUTTON, text="Cancel") is None


def test_malformed_xml_is_none_not_an_exception() -> None:
    """A truncated dump reads as 'nothing found', so a poller just polls again."""
    assert find_node("<hierarchy><node bounds=", cls=OK_BUTTON) is None


def test_find_node_requires_a_criterion() -> None:
    """Matching on nothing would return the root and silently succeed forever."""
    with pytest.raises(ValueError, match="at least one"):
        find_node(FIXTURE)


# --- Polling loop ----------------------------------------------------------


def test_returns_without_sleeping_when_the_condition_already_holds() -> None:
    """The fast path costs one poll and no wait."""
    clock = FakeClock()
    calls = []

    def dump() -> str:
        calls.append(1)
        return FIXTURE

    wait_until(
        dump,
        lambda h: find_node(h, cls=OK_BUTTON) is not None,
        clock=clock,
        sleep_fn=clock.sleep,
    )
    assert len(calls) == 1
    assert clock.sleeps == []


def test_unreadable_dumps_are_not_ready_rather_than_errors() -> None:
    """The case this whole design exists for.

    `uiautomator dump` fails while a view animates. Two failures then a good
    read must resolve to success, not to an exception and not to a false
    'condition met'.
    """
    clock = FakeClock()
    responses: list[str | None] = [None, None, FIXTURE]

    wait_until(
        lambda: responses.pop(0),
        lambda h: find_node(h, cls=OK_BUTTON) is not None,
        clock=clock,
        sleep_fn=clock.sleep,
    )
    assert responses == []
    assert clock.sleeps == [0.25, 0.25]


def test_predicate_is_never_called_with_none() -> None:
    """Guards the branch above: a None dump must short-circuit before the predicate."""
    clock = FakeClock()
    responses: list[str | None] = [None, FIXTURE]

    def predicate(hierarchy: str) -> bool:
        assert hierarchy is not None
        return True

    wait_until(
        lambda: responses.pop(0), predicate, clock=clock, sleep_fn=clock.sleep
    )


def test_timeout_raises_with_the_poll_count_and_description() -> None:
    """A timeout must say what it was waiting for -- that's the whole gain over a sleep."""
    clock = FakeClock()
    with pytest.raises(UiConditionTimeout) as excinfo:
        wait_until(
            lambda: None,
            lambda h: True,
            timeout=1.0,
            interval=0.25,
            description="the OK button to appear",
            clock=clock,
            sleep_fn=clock.sleep,
        )
    message = str(excinfo.value)
    assert "the OK button to appear" in message
    assert "5 polls" in message


def test_a_condition_that_never_holds_still_times_out() -> None:
    """Readable dumps that never satisfy the predicate must not loop forever."""
    clock = FakeClock()
    with pytest.raises(UiConditionTimeout):
        wait_until(
            lambda: FIXTURE,
            lambda h: find_node(h, text="Nonexistent") is not None,
            timeout=0.5,
            clock=clock,
            sleep_fn=clock.sleep,
        )
