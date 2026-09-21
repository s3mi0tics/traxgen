# tests/test_render_course_script.py
"""The render script reports what the main-menu wait measured (s37, plan item 17(d)).

Plan #20 asks how often a cold boot loses a frame, and until renders write
sidecars (plan item 16) the script's stderr is the only place a `--fresh` run
leaves the count -- so it has to come out even when the render fails later.
The render itself is faked: this pins the wiring, not the wait.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import scripts.render_course as script
from traxgen.android import MenuArrival, RenderResult, WrongForegroundAppError

ARRIVAL = MenuArrival(
    elapsed=47.2,
    polls=24,
    distance=0.012,
    unreadable=("main-menu poll 8: screencap returned a truncated PNG",),
)


def quiet(ok: bool, **_: object) -> str:
    return "quiet"


def fake_render(*, arrive: bool, error: Exception | None = None) -> Callable[..., RenderResult]:
    def render(
        code: str, *, on_menu: Callable[[MenuArrival], None], **_: object
    ) -> RenderResult:
        if arrive:
            on_menu(ARRIVAL)
        if error is not None:
            raise error
        return RenderResult(Path("s.png"), None)

    return render


def run(monkeypatch: pytest.MonkeyPatch, render: Callable[..., RenderResult]) -> int:
    monkeypatch.setattr(script, "resolve_context", lambda: object())
    monkeypatch.setattr(script, "render_course", render)
    return script.main(["ABC1234567", "--reset-first"], chime_fn=quiet)


def wrong_app() -> WrongForegroundAppError:
    return WrongForegroundAppError(expected="com.ravensburger.gravitrax", found="launcher")


def test_the_menu_line_prints_on_a_passing_render(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(monkeypatch, fake_render(arrive=True)) == 0
    err = capsys.readouterr().err
    assert "main menu after 47.2s (24 polls, distance 0.012)" in err
    assert "unreadable frames skipped: 1 (main-menu poll 8:" in err


def test_the_menu_line_survives_a_render_that_fails_after_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A later step failing must not take the line with it (s37: a live run ended
    with the launcher in front and said nothing about the wait)."""
    assert run(monkeypatch, fake_render(arrive=True, error=wrong_app())) == 3
    err = capsys.readouterr().err
    assert err.index("main menu after") < err.index("render failed")


def test_a_failure_prints_its_notes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = wrong_app()
    error.add_note("main-menu wait: timed out after 90.0s (45 polls)")
    assert run(monkeypatch, fake_render(arrive=False, error=error)) == 3
    assert "\n  main-menu wait: timed out after 90.0s (45 polls)" in capsys.readouterr().err
