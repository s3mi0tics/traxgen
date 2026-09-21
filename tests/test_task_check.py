# tests/test_task_check.py
"""Offline tests for `scripts.task_check`, the scope check behind the task routine (s38).

The check's five slots are in `allostatik/workflow.md`, Part 2, *Task routine*. Each
miss case there has a test here: a changed file outside the declared scope, tracked
or not, and a task with no usable `TASK-OPEN` line. git is faked through the
injected `run`, the same seam the harness uses for adb.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from scripts.task_check import (
    TaskCheckError,
    covers,
    main,
    outside_scope,
    parse_task_open,
)

LEDGER = (
    "OPENED s38 2026-09-21\n"
    "TASK-OPEN s38-t2 base=aaa1111 scope=scripts/emulator.py\n"
    "TASK-CLOSED s38-t2 FAILED\n"
    "TASK-OPEN s38-t2 base=abc1234 scope=scripts/emulator.py,tests/\n"
)


def fake_git(
    diff: Sequence[str] = (), untracked: Sequence[str] = (), returncode: int = 0
) -> Callable[..., subprocess.CompletedProcess[str]]:
    calls: list[list[str]] = []

    def run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        lines = untracked if "ls-files" in cmd else diff
        stderr = "fatal: bad revision" if returncode else ""
        return subprocess.CompletedProcess(cmd, returncode, "\n".join(lines) + "\n", stderr)

    run.calls = calls  # type: ignore[attr-defined]
    return run


def check(
    tmp_path: Path, run: Callable[..., subprocess.CompletedProcess[str]], task: str = "s38-t2"
) -> int:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(LEDGER)
    return main([task], run=run, ledger=ledger)


def test_the_last_open_line_for_a_task_is_the_one_read() -> None:
    opened = parse_task_open(LEDGER, "s38-t2")
    assert (opened.base, opened.scope) == ("abc1234", ("scripts/emulator.py", "tests/"))


def test_a_task_with_no_open_line_is_refused() -> None:
    with pytest.raises(TaskCheckError, match="no TASK-OPEN line for s38-t9"):
        parse_task_open(LEDGER, "s38-t9")


def test_an_open_line_without_a_scope_is_refused() -> None:
    with pytest.raises(TaskCheckError, match="lacks base= or scope="):
        parse_task_open("TASK-OPEN s38-t3 base=abc1234\n", "s38-t3")


def test_a_folder_entry_covers_its_contents_and_a_file_entry_only_itself() -> None:
    assert covers("tests/", "tests/test_emulator.py")
    assert not covers("tests/", "tests_old/x.py")
    assert covers("scripts/emulator.py", "scripts/emulator.py")
    assert not covers("scripts/emulator.py", "scripts/emulator.py.bak")


def test_the_ledger_and_the_reports_never_need_declaring() -> None:
    changed = [
        "allostatik/session-ledger.md",
        "allostatik/knowledge/task_reports/2026-09-21-s38-t2-x.md",
    ]
    assert outside_scope(changed, ()) == []


def test_work_inside_the_scope_passes_and_says_how_much(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = fake_git(
        diff=["scripts/emulator.py", "allostatik/session-ledger.md"],
        untracked=["tests/test_new.py"],
    )
    assert check(tmp_path, run) == 0
    assert "in scope -- 3 files changed since abc1234" in capsys.readouterr().out
    assert run.calls[0][:3] == ["git", "--no-optional-locks", "diff"]  # type: ignore[attr-defined]


def test_an_undeclared_record_file_fails_the_close_and_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The likeliest miss: a task edits `plan.md`, which only the session close writes."""
    assert check(tmp_path, fake_git(diff=["scripts/emulator.py", "allostatik/plan.md"])) == 1
    assert "OUT OF SCOPE -- 1 of 2 changed files not declared: allostatik/plan.md" in (
        capsys.readouterr().out
    )


def test_an_untracked_file_outside_the_scope_is_caught_too(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check(tmp_path, fake_git(untracked=["traxgen/new_module.py"])) == 1
    assert "traxgen/new_module.py" in capsys.readouterr().out


def test_no_open_line_cannot_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check(tmp_path, fake_git(), task="s38-t9") == 2
    assert "CANNOT CHECK" in capsys.readouterr().out


def test_a_git_failure_cannot_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check(tmp_path, fake_git(returncode=128)) == 2
    assert "fatal: bad revision" in capsys.readouterr().out
