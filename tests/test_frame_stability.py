"""Tests for the pixel-stability predicate -- the Unity-surface synchronization.

All offline, and deliberately so. The two waits this exists for (`after_load`,
`after_render_load`) sit in front of a Unity game surface that `uiautomator`
cannot see, so `wait_for_node` is blind to them and only the pixels can answer.
The frames below are *synthesised*, not captured, which bounds what these tests
can prove: they grade the **sequencing logic** -- how many consecutive quiet
samples are required, what resets the streak, what a timeout does -- and they
prove nothing about what a real GraviTrax frame's noise floor is. That number is
unmeasured (see `FRAME_STABILITY_TOLERANCE`) and the first live run calibrates
it. Saying so here rather than dressing a synthetic fixture as evidence is the
same discipline as `observations.md` #24.

`wait_until` takes injectable `clock` and `sleep_fn`, so none of this costs real
elapsed time. That injection seam is what makes a timing test a unit test: the
code under test asks its collaborator for the time instead of calling
`time.monotonic()` itself, so a test can hand it a clock that only moves when
someone sleeps on it. Playwright's `toHaveScreenshot` does the same thing this
predicate does -- retry the capture until consecutive frames agree before
asserting -- which is the real parallel; the tool doesn't travel here, the idea
does.

Path: traxgen/tests/test_frame_stability.py
"""

from __future__ import annotations

import io

import pytest

from traxgen.android import (
    FRAME_STABILITY_REQUIRED_SAMPLES,
    FrameStability,
    FrameUnreadableError,
    UiConditionTimeout,
    frame_difference,
    frame_fingerprint,
    wait_for_stable_frame,
)


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


def png(*, fill: int, size: tuple[int, int] = (16, 12)) -> bytes:
    """A solid-grey PNG. `fill` is the channel value, so frames differ by |a-b|."""
    return png_rgb(colour=(fill, fill, fill), size=size)


def png_rgb(*, colour: tuple[int, int, int], size: tuple[int, int] = (16, 12)) -> bytes:
    """A solid PNG of an arbitrary colour."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def png_regions(
    *, background: int, regions: list[tuple[tuple[int, int, int, int], int]]
) -> bytes:
    """A PNG with grey patches painted onto a grey background.

    The solid frames above share a coincidence that hid three real gaps: a
    fingerprint reduced to a single number (a mean, or a max, or a greyscale
    value) is indistinguishable from the real one when every pixel is the same
    achromatic value. Anything asserting that the fingerprint keeps *where* the
    pixels are, or *what colour* they are, needs a frame that varies.
    """
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (16, 12), (background,) * 3)
    draw = ImageDraw.Draw(image)
    for box, fill in regions:
        draw.rectangle(box, fill=(fill,) * 3)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# --- The comparable form ---------------------------------------------------


def test_two_identical_frames_have_zero_difference() -> None:
    assert frame_difference(frame_fingerprint(png(fill=40)), frame_fingerprint(png(fill=40))) == 0.0


def test_the_difference_is_the_mean_absolute_channel_gap() -> None:
    """Solid frames make the expected value arithmetic rather than a guess."""
    quiet = frame_fingerprint(png(fill=40))
    louder = frame_fingerprint(png(fill=52))
    assert frame_difference(quiet, louder) == pytest.approx(12.0)


def test_frames_of_different_geometry_are_infinitely_different() -> None:
    """A resolution change is never 'the same picture', and must not average out.

    Without this, two frames of different size would either raise deep inside a
    poll or be silently compared elementwise past the shorter one -- and the
    second reads as stability, which is the direction that invents data.
    """
    assert frame_difference(
        frame_fingerprint(png(fill=40, size=(16, 12))),
        frame_fingerprint(png(fill=40, size=(20, 12))),
    ) == float("inf")


def test_the_fingerprint_keeps_where_the_pixels_are() -> None:
    """Two frames with the SAME mean and different layout are not the same frame.

    A fingerprint reduced to one number per frame -- a mean, a histogram total,
    an average brightness -- passes every solid-fill test in this file while
    being blind to a course sliding across the screen. Mirrored halves hold the
    mean fixed and move every pixel, so only a layout-preserving fingerprint
    can tell them apart.
    """
    left_bright = png_regions(background=0, regions=[((0, 0, 7, 11), 80)])
    right_bright = png_regions(background=0, regions=[((8, 0, 15, 11), 80)])

    assert frame_difference(
        frame_fingerprint(left_bright), frame_fingerprint(right_bright)
    ) == pytest.approx(80.0)


def test_the_difference_is_a_mean_and_not_a_worst_pixel() -> None:
    """A few blown-out pixels must not read as a whole screen in motion.

    `max` and `mean` agree on every solid frame, so this is the only shape that
    separates them. It matters in the honest direction: a `max` would refuse to
    ever call a frame stable if one pixel flickers, and the cost of never
    settling is a timed-out campaign.

    Doubles as the filter's own guard. A 16x12 frame downscales to 4x3, so each
    output pixel area-averages a 4x4 block; the bright row fills one of those
    four rows, giving 255/4 = 63.75 -> 64 after PIL's rounding, across the 4
    top-row output pixels of 12. Under `NEAREST` the row lands between sample
    points and the difference is 0.000 -- a moving feature rendered invisible.
    """
    dark = png_regions(background=0, regions=[])
    one_bright_row = png_regions(background=0, regions=[((0, 0, 15, 0), 255)])

    difference = frame_difference(frame_fingerprint(dark), frame_fingerprint(one_bright_row))
    assert difference == pytest.approx(64.0 * 4 / 12)
    assert difference < 255.0


def test_the_fingerprint_keeps_colour_rather_than_luminance() -> None:
    """Equal-brightness colour changes are still changes.

    Grey (100,100,100) and green (0,170,0) land within a channel step of each
    other in luminance -- asserted here from PIL rather than claimed -- so a
    greyscale fingerprint calls them identical. Missing a change is the
    direction that invents stability (observations #17), so RGB it is.
    """
    from PIL import Image

    grey, green = (100, 100, 100), (0, 170, 0)
    luminance = [
        Image.new("RGB", (1, 1), colour).convert("L").getpixel((0, 0)) for colour in (grey, green)
    ]
    assert abs(luminance[0] - luminance[1]) <= 1, f"precondition failed: {luminance}"

    assert frame_difference(
        frame_fingerprint(png_rgb(colour=grey)), frame_fingerprint(png_rgb(colour=green))
    ) == pytest.approx((100 + 70 + 100) / 3)


# --- The predicate ---------------------------------------------------------


def test_one_quiet_pair_is_not_yet_stable() -> None:
    """A single matching pair happens by luck mid-animation; the streak is the point."""
    predicate = FrameStability(required=3, tolerance=0.0)
    assert predicate(frame_fingerprint(png(fill=40))) is False
    assert predicate(frame_fingerprint(png(fill=40))) is False


def test_the_streak_length_is_the_parameter_it_claims_to_be() -> None:
    """Pinned at two values so a hardcoded 3 cannot pass this."""
    lenient = FrameStability(required=2, tolerance=0.0)
    assert [lenient(frame_fingerprint(png(fill=40))) for _ in range(2)] == [False, True]

    strict = FrameStability(required=4, tolerance=0.0)
    assert [strict(frame_fingerprint(png(fill=40))) for _ in range(4)] == [
        False,
        False,
        False,
        True,
    ]


def test_a_change_resets_the_streak_rather_than_delaying_it() -> None:
    """Two quiet samples, then motion, must need a full fresh run of quiet ones.

    The bug this forbids is a counter that only ever increments: it would treat
    'quiet, quiet, MOVED, quiet' as three-of-four and call a moving screen still.
    """
    predicate = FrameStability(required=3, tolerance=0.0)
    predicate(frame_fingerprint(png(fill=40)))
    predicate(frame_fingerprint(png(fill=40)))
    assert predicate(frame_fingerprint(png(fill=90))) is False  # motion
    assert predicate(frame_fingerprint(png(fill=90))) is False
    assert predicate(frame_fingerprint(png(fill=90))) is True


def test_the_tolerance_is_inclusive_at_its_own_boundary() -> None:
    """Pinned either side of the edge, so a `<` / `<=` slip fails here."""
    inside = FrameStability(required=2, tolerance=12.0)
    inside(frame_fingerprint(png(fill=40)))
    assert inside(frame_fingerprint(png(fill=52))) is True  # difference exactly 12.0

    outside = FrameStability(required=2, tolerance=11.0)
    outside(frame_fingerprint(png(fill=40)))
    assert outside(frame_fingerprint(png(fill=52))) is False


def test_every_observed_difference_is_recorded_for_calibration() -> None:
    """The predicate is also the instrument that measures its own threshold.

    `FRAME_STABILITY_TOLERANCE` is a pre-declared guess, not a measurement. This
    is what lets the first live run replace it with the real noise floor instead
    of the number surviving because nobody looked (observations #18).
    """
    predicate = FrameStability(required=3, tolerance=0.0)
    for fill in (40, 40, 52, 52):
        predicate(frame_fingerprint(png(fill=fill)))
    assert predicate.differences == [0.0, pytest.approx(12.0), 0.0]


def test_the_shipped_default_never_settles_on_a_single_quiet_pair() -> None:
    """Pins the property, not the number -- the number is an unmeasured guess.

    Every other test here passes `required=` explicitly, so the constant that
    production actually runs on was exercised by nothing. What is worth pinning
    is not "3" but "more than one pair": at 2 a single coincidental match ends
    the wait, and one pair happens by luck whenever a poll straddles a pause in
    an animation. Raising the default is fine; dropping it to 2 is the defect.
    """
    assert FRAME_STABILITY_REQUIRED_SAMPLES >= 3

    predicate = FrameStability()
    assert predicate(frame_fingerprint(png(fill=40))) is False
    assert predicate(frame_fingerprint(png(fill=40))) is False


# --- The wait --------------------------------------------------------------


def test_the_wait_returns_once_the_screen_settles() -> None:
    clock = FakeClock()
    frames = [png(fill=10), png(fill=90), png(fill=40), png(fill=40), png(fill=40)]

    result = wait_for_stable_frame(
        None,
        required=3,
        tolerance=0.0,
        sample_fn=lambda: frames.pop(0),
        clock=clock,
        sleep_fn=clock.sleep,
    )
    assert frames == []
    assert result.differences == [80.0, 50.0, 0.0, 0.0]


def test_a_screen_that_never_settles_times_out_rather_than_guessing() -> None:
    """Losing a run is the acceptable failure; inventing a 'ready' is not."""
    clock = FakeClock()
    fills = iter(range(0, 255, 7))

    with pytest.raises(UiConditionTimeout) as excinfo:
        wait_for_stable_frame(
            None,
            timeout=1.0,
            interval=0.25,
            sample_fn=lambda: png(fill=next(fills)),
            clock=clock,
            sleep_fn=clock.sleep,
        )
    assert "stop changing" in str(excinfo.value)


def test_an_unreadable_frame_raises_rather_than_bridging_the_streak() -> None:
    """The one place this must differ from `wait_until`'s uiautomator contract.

    `dump_ui` returns None for 'not readable yet' because a hierarchy dump fails
    *while a view animates* -- which is normal. `screencap` has no such state: a
    failure there is a real failure. And because `wait_until` skips the predicate
    on a None sample, a silently-tolerated gap would let the frame before it and
    the frame after it count as consecutive -- stitching a streak across an
    interval nobody observed.
    """
    clock = FakeClock()
    with pytest.raises(FrameUnreadableError):
        wait_for_stable_frame(
            None,
            sample_fn=lambda: None,
            clock=clock,
            sleep_fn=clock.sleep,
        )
