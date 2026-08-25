"""Tests for the refused-screen guard: is this frame a screen we know isn't a render?

All offline. The frames are real captures from the 2026-08-25 #17 2x2 run,
downscaled to 150x67 -- the geometry at which the separation still measures
11.4x (see `android.py`'s refused-screens section for the table across six
downscales).

WHY THIS MODULE EXISTS. Two of that run's seven renders never loaded their
course. The `loaded_track_hex` tap fired after a fixed `WAITS["after_load"]`,
landed on an empty slot because the shared course had not appeared yet, and
opened a NEW EMPTY COURSE in the editor -- the "Drag a launch pad onto the base
plate" build tutorial. All three existing guards pass on that screen:
GraviTrax is in the foreground, the frame is dark rather than near-white, and
the picture is perfectly still. The play-button oracle then sampled the greyed
button of an empty editor and returned a well-formed `inactive`.

One of the two was the closing certified control, which is the only reason the
run was voided rather than believed -- the 2026-08-07 both-ends lock catching a
failure nobody had imagined, for the second time (observations #17). The other
was `arm1_E_on_completer`, an experimental arm, and its `inactive` would have
been read as a measurement.

THE FIXTURES ARE REAL, AND THE REFERENCE IS NOT ONE OF THE FRAMES IT CATCHES.
`traxgen/data/refused_screens/build_tutorial.png` is the *closing control's*
frame; `arm1_E_on_completer.png` here is the *other* failure. So the test that
matters below compares two independent captures rather than a frame against
itself, which is the difference between a check and observations #12's shape.

WHAT THIS GUARD DOES NOT DO, restated because the module says it and a test
module is where someone looks second: it recognises **known** dead screens by
signature. An unknown still, dark, GraviTrax-owned non-render passes it exactly
as it passed the other three. There is no test here for that, because there is
nothing to test -- it is a stated limit, not a behaviour.

Path: traxgen/tests/test_refused_screens.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from tests.test_android_foreground import IS_TAP, FakeAdb, ctx_with
from traxgen.android import (
    REFUSED_SCREEN_DISTANCE,
    RefusedScreen,
    RefusedScreenError,
    default_refused_screens,
    load_refused_screens,
    match_refused_screen,
    render_course,
    screen_distance,
)

FRAMES = Path(__file__).parent / "fixtures" / "frames"

# The other failure from the same run: the same build-tutorial screen, captured
# four renders earlier under a different share code and a different course.
DEAD_FRAME = (FRAMES / "arm1_E_on_completer.png").read_bytes()

# The three that actually rendered. `certified_open` is the run's opening
# control (active); `arm1_SW_on_completer` is a real two-plate render with the
# goal attached; `arm2_E_on_home` is a real render whose goal the app dropped.
# Three different pictures, so "far from the reference" is not one accident.
LIVE_FRAMES = {
    name: (FRAMES / f"{name}.png").read_bytes()
    for name in ("certified_open", "arm1_SW_on_completer", "arm2_E_on_home")
}


def _solid_png(width: int, height: int, colour: tuple[int, int, int]) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


# --- The shipped set -------------------------------------------------------


def test_the_shipped_set_loads_and_names_its_screens() -> None:
    screens = default_refused_screens()
    assert [s.name for s in screens] == ["build_tutorial"]
    assert (screens[0].width, screens[0].height) == (150, 67)
    assert len(screens[0].channels) == 150 * 67 * 3


def test_the_shipped_set_is_decoded_once() -> None:
    """The cache is not decoration: every render compares against this."""
    assert default_refused_screens() is default_refused_screens()


def test_screens_load_in_name_order_rather_than_filesystem_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """observations #30 -- a collection's order is part of its content.

    `match_refused_screen` reports the *nearest* match, so order does not decide
    the verdict. It decides ties, and a tie reported as the wrong screen name
    sends a human to the wrong diagnosis.

    `glob` is patched rather than trusted. Creating three files and asserting
    the output is sorted proved nothing: mutation showed that dropping
    `sorted()` left this green, because this filesystem happened to hand them
    back in creation order. The fixture was agreeing with the code for a reason
    unrelated to the code (observations #12).
    """
    from PIL import Image

    for name in ("zebra", "alpha", "middle"):
        Image.new("RGB", (4, 4), (1, 2, 3)).save(tmp_path / f"{name}.png")

    shuffled = [tmp_path / "zebra.png", tmp_path / "middle.png", tmp_path / "alpha.png"]
    monkeypatch.setattr(Path, "glob", lambda self, pattern: iter(shuffled))

    assert [s.name for s in load_refused_screens(tmp_path)] == ["alpha", "middle", "zebra"]


# --- The measurement the threshold rests on --------------------------------


def test_the_measured_separation_that_set_the_threshold() -> None:
    """The calibration table, as an instrument rather than a comment.

    observations #24's third rung: a cited number needs something in the repo
    that can regenerate it. These four distances are the entire evidence for
    `REFUSED_SCREEN_DISTANCE`, so they live here as an assertion and not only
    as prose in `android.py`.

    Tolerances are loose (0.05) on purpose -- the claim is the *gap*, an order
    of magnitude wide, not the third decimal of a Pillow resample.
    """
    reference = default_refused_screens()[0]

    dead = screen_distance(DEAD_FRAME, reference)
    assert dead == pytest.approx(2.262, abs=0.05)

    live = {name: screen_distance(png, reference) for name, png in LIVE_FRAMES.items()}
    assert live["certified_open"] == pytest.approx(25.890, abs=0.05)
    assert live["arm2_E_on_home"] == pytest.approx(26.542, abs=0.05)
    assert live["arm1_SW_on_completer"] == pytest.approx(26.585, abs=0.05)

    assert min(live.values()) / dead > 11.0


def test_the_threshold_sits_inside_the_measured_gap() -> None:
    """The constant is declared; this pins that it was declared inside the data.

    What this can and cannot say, stated precisely because the loose version
    would be wrong. It proves 10.0 separates *these five frames*. It does not
    prove 10.0 is right, because n=2 for the refused class -- one pair barely
    samples its spread, and the next dead frame could sit further from the
    reference than either of these. A change to the constant that leaves the
    gap intact passes this test, which is the honest limit of an offline check.
    """
    reference = default_refused_screens()[0]
    dead = screen_distance(DEAD_FRAME, reference)
    nearest_live = min(screen_distance(png, reference) for png in LIVE_FRAMES.values())

    assert dead < REFUSED_SCREEN_DISTANCE < nearest_live


def test_the_frame_that_would_have_been_believed_is_caught() -> None:
    """`arm1_E_on_completer` is the experimental arm whose `inactive` was data."""
    match = match_refused_screen(DEAD_FRAME, default_refused_screens())
    assert match is not None
    screen, distance = match
    assert screen.name == "build_tutorial"
    assert distance < REFUSED_SCREEN_DISTANCE


@pytest.mark.parametrize("name", sorted(LIVE_FRAMES))
def test_a_real_render_is_not_refused(name: str) -> None:
    assert match_refused_screen(LIVE_FRAMES[name], default_refused_screens()) is None


# --- The comparison itself -------------------------------------------------


def test_an_oversized_frame_is_measured_through_the_resize_path() -> None:
    """The resize branch is where a live frame goes, and it needs a real fixture.

    Found by mutation: `BOX` -> `NEAREST` survived the whole suite, because
    every other frame in this module is *already* at the reference geometry, so
    the resize branch never executed once (observations #26 -- one coincidence
    shared by the whole fixture set). `arm1_E_on_completer_300x135.png` is the
    same capture at 300x135, so this call actually downscales.

    The distance is asserted rather than only the verdict, because at 300x135
    both filters still land under the threshold; only the number separates
    them. BOX 4.685, NEAREST 8.109.
    """
    reference = default_refused_screens()[0]
    oversized = (FRAMES / "arm1_E_on_completer_300x135.png").read_bytes()

    assert screen_distance(oversized, reference) == pytest.approx(4.685, abs=0.05)
    assert match_refused_screen(oversized, default_refused_screens()) is not None


def test_the_resampling_filter_is_load_bearing_and_the_worst_case_is_not_committable() -> None:
    """Measured on the real 2400x1080 captures, and this one is not a style point.

    Downscaling the dead frame to the reference geometry:

        BOX      2.262   <- what the code does
        BICUBIC  3.929   <- Pillow's silent default
        BILINEAR 4.114
        NEAREST 10.298   <- ABOVE the 10.0 threshold: the guard MISSES

    So the filter and the threshold are coupled, and `NEAREST` would have let
    through the exact frame this guard was built from. Same direction as the
    `frame_fingerprint` finding one section up in `android.py`, arriving in a
    different function.

    CONCEDED, in writing rather than papered over: that 10.298 cannot be
    reproduced offline. It needs the 2400x1080 capture, and render screenshots
    are not committed (`plan.md` deferred cleanup). The committed 300x135
    fixture demonstrates the filter *matters* (4.685 vs 8.109) and cannot
    demonstrate that it breaks the guard. This test asserts only what it can
    see: that the two filters disagree by more than measurement noise.
    """
    from PIL import Image

    reference = default_refused_screens()[0]
    oversized = Image.open(FRAMES / "arm1_E_on_completer_300x135.png").convert("RGB")

    def distance_via(filter_: Image.Resampling) -> float:
        small = oversized.resize((reference.width, reference.height), filter_)
        return sum(
            abs(a - b) for a, b in zip(small.tobytes(), reference.channels, strict=True)
        ) / len(reference.channels)

    assert distance_via(Image.Resampling.NEAREST) - distance_via(Image.Resampling.BOX) > 2.0


def test_a_frame_smaller_than_the_reference_is_refused_rather_than_upscaled() -> None:
    """A frame this small means the device profile changed.

    Every tap coordinate in `android.py` is in 2400x1080 device space, so the
    honest response is to shout rather than to answer "no match" -- which would
    silently retire the guard at the moment the harness most needs questioning
    (observations #17: guard the direction that invents).
    """
    reference = default_refused_screens()[0]
    with pytest.raises(ValueError, match="device profile has changed"):
        screen_distance(_solid_png(10, 10, (0, 0, 0)), reference)


def test_the_nearest_reference_wins_rather_than_the_first(tmp_path: Path) -> None:
    """With several references, first-under-threshold would depend on load order.

    Built as two synthetic greys either side of the frame under test, so the
    nearer one is the *second* in name order -- a first-match implementation
    returns the wrong name and this fails.
    """
    from PIL import Image

    Image.new("RGB", (8, 8), (100, 100, 100)).save(tmp_path / "a_far.png")
    Image.new("RGB", (8, 8), (118, 118, 118)).save(tmp_path / "b_near.png")
    references = load_refused_screens(tmp_path)

    match = match_refused_screen(_solid_png(8, 8, (120, 120, 120)), references, threshold=30.0)
    assert match is not None
    assert match[0].name == "b_near"
    assert match[1] == pytest.approx(2.0)


def test_a_reference_beyond_the_threshold_is_no_match() -> None:
    reference = RefusedScreen("synthetic", 4, 4, bytes([0]) * 48)
    assert match_refused_screen(_solid_png(4, 4, (255, 255, 255)), [reference]) is None


# --- The threshold as a value ----------------------------------------------
#
# Every test above uses the default threshold against frames an order of
# magnitude away from it, which is one coincidence explaining two mutation
# survivors at once (observations #26): `<=` weakened to `<`, and
# `render_course` ignoring its own `refused_screen_distance` argument. Both
# need the threshold exercised *as a number* rather than as a constant that
# happens to be far from everything.


def test_a_distance_exactly_at_the_threshold_matches() -> None:
    """The boundary is inclusive, and nothing else in the suite stands on it.

    A solid black reference against a solid (10,10,10) frame is a mean absolute
    difference of exactly 10.0, so `<` instead of `<=` flips this and nothing
    else.
    """
    reference = RefusedScreen("synthetic", 4, 4, bytes([0]) * 48)
    match = match_refused_screen(_solid_png(4, 4, (10, 10, 10)), [reference], threshold=10.0)
    assert match is not None
    assert match[1] == pytest.approx(10.0)


def test_render_course_honours_a_caller_supplied_threshold(tmp_path: Path) -> None:
    """A calibration run needs to widen or narrow this without editing the module."""
    lenient = FakeAdb(screencap_png=DEAD_FRAME)
    result = render_course(
        "KN6F459ZR3",
        ctx=ctx_with(lenient),
        screenshot_dir=tmp_path,
        refused_screen_distance=1.0,
    )
    assert result.screenshot.exists()

    strict = FakeAdb(screencap_png=LIVE_FRAMES["certified_open"])
    with pytest.raises(RefusedScreenError) as caught:
        render_course(
            "KN6F459ZR3",
            ctx=ctx_with(strict),
            screenshot_dir=tmp_path,
            refused_screen_distance=30.0,
        )
    assert caught.value.threshold == 30.0


# --- The wiring ------------------------------------------------------------


def test_render_course_raises_on_a_refused_screen(tmp_path: Path) -> None:
    fake = FakeAdb(screencap_png=DEAD_FRAME)
    with pytest.raises(RefusedScreenError) as caught:
        render_course("KN6F459ZR3", ctx=ctx_with(fake), screenshot_dir=tmp_path)

    error = caught.value
    assert error.screen == "build_tutorial"
    assert error.distance == pytest.approx(2.262, abs=0.05)
    assert error.threshold == REFUSED_SCREEN_DISTANCE
    assert error.path.name == "rendered_KN6F459ZR3.png"


def test_the_error_carries_the_distance_because_that_is_the_calibration_data() -> None:
    """Same argument as `FrameStability.differences`.

    The threshold is declared against n=2. Every refusal in the field is a new
    observation of the refused class, and swallowing it is what would leave the
    constant permanently unexamined.
    """
    assert "distance" in RefusedScreenError.__init__.__annotations__


def test_cleanup_still_runs_when_the_frame_is_refused(tmp_path: Path) -> None:
    """The raise comes AFTER cleanup, and that ordering is the whole design.

    Measured rather than assumed: in the 2026-08-25 run the two tutorial frames
    were followed by renders that succeeded, so this tap sequence does return to
    the main menu from the empty editor. Raising first would leave a course open
    and turn one bad render into a cascade -- the caller's retry would start
    from the wrong screen, which is exactly the failure being guarded.
    """
    clean = FakeAdb()
    render_course("KN6F459ZR3", ctx=ctx_with(clean), screenshot_dir=tmp_path)
    taps_when_clean = sum(1 for argv in clean.calls if IS_TAP(" ".join(argv)))

    dead = FakeAdb(screencap_png=DEAD_FRAME)
    with pytest.raises(RefusedScreenError):
        render_course("KN6F459ZR3", ctx=ctx_with(dead), screenshot_dir=tmp_path)
    taps_when_refused = sum(1 for argv in dead.calls if IS_TAP(" ".join(argv)))

    assert taps_when_refused == taps_when_clean


def test_cleanup_can_still_be_skipped_when_the_frame_is_refused(tmp_path: Path) -> None:
    """`cleanup=False` is not overridden by the refusal path."""
    fake = FakeAdb(screencap_png=DEAD_FRAME)
    with pytest.raises(RefusedScreenError):
        render_course(
            "KN6F459ZR3", ctx=ctx_with(fake), screenshot_dir=tmp_path, cleanup=False
        )
    assert not fake.has(lambda c: "input tap 180 60" in c)


def test_the_oracle_is_not_consulted_on_a_refused_frame(tmp_path: Path) -> None:
    """The greyed play button of an empty editor reads exactly like a dark course.

    So the oracle's answer here is well-formed and wrong, which is why the guard
    sits above it rather than beside it. Enacted rather than asserted about: the
    oracle is replaced with one that records being called.
    """
    from traxgen import android

    called: list[Path] = []

    def spy(path: Path, **_kwargs: object) -> str:
        called.append(path)
        return "inactive"

    original = android.detect_play_button_state
    android.detect_play_button_state = spy  # type: ignore[assignment]
    try:
        fake = FakeAdb(screencap_png=DEAD_FRAME)
        with pytest.raises(RefusedScreenError):
            render_course(
                "KN6F459ZR3",
                ctx=ctx_with(fake),
                screenshot_dir=tmp_path,
                detect_validity=True,
            )
        assert called == []

        live = FakeAdb(screencap_png=LIVE_FRAMES["certified_open"])
        result = render_course(
            "KN6F459ZR3",
            ctx=ctx_with(live),
            screenshot_dir=tmp_path,
            detect_validity=True,
        )
        assert result.validity == "inactive"
        assert len(called) == 1
    finally:
        android.detect_play_button_state = original  # type: ignore[assignment]


def test_the_guard_can_be_pointed_at_a_different_set(tmp_path: Path) -> None:
    """`refused_screens=()` disables it, which a calibration run needs.

    Not a convenience: a run whose *purpose* is to capture what an unknown dead
    screen looks like must be able to get the frame back rather than an
    exception.
    """
    fake = FakeAdb(screencap_png=DEAD_FRAME)
    result = render_course(
        "KN6F459ZR3", ctx=ctx_with(fake), screenshot_dir=tmp_path, refused_screens=()
    )
    assert result.screenshot.exists()


def test_a_clean_render_is_unaffected_by_the_guard(tmp_path: Path) -> None:
    """The nine campaigns in MEASURED_RUNS predate this guard.

    If a real render tripped it, every historical result would be in question.
    """
    for name, png in LIVE_FRAMES.items():
        fake = FakeAdb(screencap_png=png)
        result = render_course(f"CODE{name[:6]}", ctx=ctx_with(fake), screenshot_dir=tmp_path)
        assert result.screenshot.exists()
