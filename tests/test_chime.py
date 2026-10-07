# tests/test_chime.py
"""Offline tests for the completion chime.

These run on Linux -- in the Cowork bridge VM and anywhere else -- where
`afplay` does not exist and `/System/Library/Sounds` is not there. So the
fallback paths are what actually execute, and the `afplay` path is driven
through an injected runner against a temp directory of stand-in files.

What they prove is the *decision*: which sound goes with which outcome, and what
happens as each layer underneath goes missing. What they cannot prove is that
`afplay` makes an audible noise on the Mac -- that is one real run away, and it
is the reason `chime` returns the name of what it played rather than None.

Path: traxgen/tests/test_chime.py
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.chime import DONE_SOUND, FAILED_SOUND, chime


class FakePlayer:
    """Records the argv a play would have run, and can fail the way a real one does."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[list[str]] = []

    def __call__(self, cmd: Sequence[str], **_: object) -> object:
        self.calls.append([str(part) for part in cmd])
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(list(cmd), 0)


def sounds(tmp_path: Path) -> Path:
    for name in (DONE_SOUND, FAILED_SOUND):
        (tmp_path / name).write_bytes(b"stand-in for a system sound")
    return tmp_path


def test_a_pass_and_a_failure_do_not_sound_the_same(tmp_path: Path) -> None:
    """A single 'done' tone would make a rendered course and a dead device identical."""
    player = FakePlayer()
    where = sounds(tmp_path)
    assert chime(True, runner=player, sounds_dir=where, out=lambda _t: None) == DONE_SOUND
    assert chime(False, runner=player, sounds_dir=where, out=lambda _t: None) == FAILED_SOUND
    assert [call[0] for call in player.calls] == ["afplay", "afplay"]
    assert [call[1] for call in player.calls] == [
        str(where / DONE_SOUND),
        str(where / FAILED_SOUND),
    ]


def test_disabled_makes_no_sound_at_all_not_even_the_bell() -> None:
    rung: list[str] = []
    player = FakePlayer()
    assert chime(True, enabled=False, runner=player, out=rung.append) == "off"
    assert player.calls == []
    assert rung == []


def test_a_missing_sound_file_falls_back_to_the_terminal_bell(tmp_path: Path) -> None:
    rung: list[str] = []
    player = FakePlayer()
    assert chime(True, runner=player, sounds_dir=tmp_path, out=rung.append) == "bell"
    assert player.calls == [], "there was nothing to play, so nothing should have been run"
    assert rung == ["\a"]


def test_a_missing_afplay_falls_back_rather_than_raising(tmp_path: Path) -> None:
    """A harness that died because its notification failed is the worse trade."""
    rung: list[str] = []
    player = FakePlayer(error=FileNotFoundError("afplay"))
    assert chime(False, runner=player, sounds_dir=sounds(tmp_path), out=rung.append) == "bell"
    assert player.calls, "it should have tried before falling back"
    assert rung == ["\a"]


def test_a_player_that_hangs_falls_back_too(tmp_path: Path) -> None:
    rung: list[str] = []
    player = FakePlayer(error=subprocess.TimeoutExpired(["afplay"], 10.0))
    assert chime(True, runner=player, sounds_dir=sounds(tmp_path), out=rung.append) == "bell"
    assert rung == ["\a"]


def test_render_course_chimes_even_when_the_run_never_started() -> None:
    """The wiring, not the sound: a refusal exits before any render and still sounds.

    Driven through the one failure that needs no emulator -- a malformed code --
    so this is a real end-to-end call of `main`, not a stub of it.
    """
    from scripts.render_course import main

    heard: list[tuple[bool, bool]] = []

    def recorder(ok: bool, *, enabled: bool = True, **_: object) -> str:
        heard.append((ok, enabled))
        return "recorded"

    assert main(["TOOSHORT"], chime_fn=recorder) == 1
    assert heard == [(False, True)]
