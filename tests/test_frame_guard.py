"""Tests for the play-button oracle's frame guard.

The oracle samples a 12x12 box and calls the frame 'active' when it is bright
enough. That is a brightness test wearing a validity test's clothes: on
2026-08-07 it returned 'active' for a GraviTrax splash screen and manufactured
a second active rotation in the goal-rotation sweep, which by that sweep's
pre-declared conditions read as `MODEL_WRONG`.

Worth being precise about why this is the dangerous direction. The morning's
IME failure made the oracle return `inactive` for a keyboard -- a null result,
which reads as "no finding". This one returned `active` for a loading screen --
a *positive* result, which reads as a discovery. Guards are cheapest to justify
against the failure that invents data rather than the one that loses it.

Frames are synthesised here rather than committed: the real screencaps live
under `screenshots/`, which .gitignore excludes, so tests depending on them
would pass locally and fail on a fresh clone. The measured values they produced
are pinned in `test_threshold_sits_between_the_measured_clusters` instead, so
the calibration decision itself is checked even though the images aren't
shipped.

Path: traxgen/tests/test_frame_guard.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from traxgen.android import (
    FRAME_MAX_WHITE_FRACTION,
    FRAME_WHITE_MIN_CHANNEL,
    OracleFrameError,
    detect_play_button_state,
    frame_white_fraction,
)

# The device frame the oracle's sample coordinates assume.
FRAME_SIZE = (2400, 1080)

# Measured 2026-08-07 via scripts/calibrate_frame_guard.py on the four screencaps
# that survived the sweep. These are the numbers the threshold was chosen from.
MEASURED_SPLASH_WHITE_FRAC = 0.942
MEASURED_RENDER_WHITE_FRAC = 0.014


def _frame(tmp_path: Path, name: str, colour: tuple[int, int, int]) -> Path:
    """Write a uniform frame of the given colour at device resolution."""
    path = tmp_path / name
    Image.new("RGB", FRAME_SIZE, colour).save(path)
    return path


def _frame_with_bright_sample(tmp_path: Path, name: str) -> Path:
    """A dark frame with a white patch exactly where the oracle samples.

    This is the shape that matters: a frame the guard should let through, whose
    sampled box then reads 'active' on its own merits.
    """
    path = tmp_path / name
    img = Image.new("RGB", FRAME_SIZE, (20, 30, 40))
    for x in range(2150, 2231):
        for y in range(940, 1021):
            img.putpixel((x, y), (250, 252, 240))
    img.save(path)
    return path


# --- The metric ------------------------------------------------------------


def test_uniform_white_frame_is_almost_entirely_white(tmp_path) -> None:
    """A splash screen is near-uniform; the metric must say so."""
    path = _frame(tmp_path, "white.png", (255, 255, 255))
    assert frame_white_fraction(path) == pytest.approx(1.0)


def test_dark_frame_has_no_white(tmp_path) -> None:
    """A rendered course is mostly board and chrome, not white."""
    path = _frame(tmp_path, "dark.png", (30, 60, 90))
    assert frame_white_fraction(path) == pytest.approx(0.0)


def test_metric_uses_the_dimmest_channel_not_brightness(tmp_path) -> None:
    """A saturated colour can be bright without being white.

    GraviTrax's play button discriminates on the blue channel for exactly this
    reason, and the guard has to agree with it: pale green is not white.
    """
    path = _frame(tmp_path, "yellow.png", (255, 255, 100))
    assert frame_white_fraction(path) == pytest.approx(0.0)


def test_threshold_is_below_the_channel_ceiling() -> None:
    """A sanity bound on the constants themselves."""
    assert 0 < FRAME_WHITE_MIN_CHANNEL <= 255
    assert 0.0 < FRAME_MAX_WHITE_FRACTION < 1.0


def test_threshold_sits_between_the_measured_clusters() -> None:
    """The calibration decision, pinned.

    Real renders measured 0.013-0.014 and the splash measured 0.942 -- about 70x
    of daylight. If someone later tightens the threshold toward the render
    cluster, or loosens it toward the splash, this fails and says why.
    """
    assert MEASURED_RENDER_WHITE_FRAC < FRAME_MAX_WHITE_FRACTION
    assert FRAME_MAX_WHITE_FRACTION < MEASURED_SPLASH_WHITE_FRAC
    # Insist on real margin, not a threshold parked next to a measurement.
    assert FRAME_MAX_WHITE_FRACTION > MEASURED_RENDER_WHITE_FRAC * 10
    assert FRAME_MAX_WHITE_FRACTION < MEASURED_SPLASH_WHITE_FRAC / 1.5


# --- The guard -------------------------------------------------------------


def test_splash_like_frame_is_refused_rather_than_classified(tmp_path) -> None:
    """The 2026-08-07 regression: a near-white frame must not yield a verdict.

    Before the guard this returned 'active' and became a finding.
    """
    path = _frame(tmp_path, "splash.png", (250, 250, 250))
    with pytest.raises(OracleFrameError, match="near-white"):
        detect_play_button_state(path)


def test_refusal_is_an_error_not_a_verdict(tmp_path) -> None:
    """`OracleFrameError` must be catchable as an automation error.

    That's what routes it into the sweeps' `render_error` field instead of
    their `validity` field -- error and failure stay distinct.
    """
    from traxgen.android import AndroidAutomationError

    path = _frame(tmp_path, "splash2.png", (255, 255, 255))
    with pytest.raises(AndroidAutomationError):
        detect_play_button_state(path)


def test_guard_can_be_disabled_for_calibration(tmp_path) -> None:
    """Calibration needs to classify known-bad frames on purpose."""
    path = _frame(tmp_path, "splash3.png", (255, 255, 255))
    assert detect_play_button_state(path, guard_frame=False) == "active"


def test_a_real_looking_frame_passes_the_guard_and_gets_classified(tmp_path) -> None:
    """The guard must not block the frames the oracle exists to read."""
    path = _frame_with_bright_sample(tmp_path, "render.png")
    assert frame_white_fraction(path) < FRAME_MAX_WHITE_FRACTION
    assert detect_play_button_state(path) == "active"


def test_dark_sample_on_a_real_looking_frame_reads_inactive(tmp_path) -> None:
    """An 'inactive' verdict is still reachable with the guard in place."""
    path = _frame(tmp_path, "dark_all.png", (30, 60, 90))
    assert detect_play_button_state(path) == "inactive"
