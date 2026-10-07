# tests/test_task_check.py
"""Offline tests for `scripts.task_check`, the scope check behind the task routine (s38).

The check's five slots are in `allostatik/workflow.md`, Part 2, *Task routine*. Each
miss case there has a test here: a changed file outside the declared scope, tracked
or not; a session-close file, even declared; a task with no usable `TASK-OPEN`
line; and a declaration that did not come first -- never committed, committed on
another base, or committed together with the work (s38-t4, the reader's finding).
git is faked through the injected `run`, the same seam the harness uses for adb.
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
    unclosed,
)

LEDGER = (
    "OPENED s38 2026-09-21\n"
    "TASK-OPEN s38-t2 base=aaa1111 scope=scripts/emulator.py\n"
    "TASK-CLOSED s38-t2 FAILED\n"
    "TASK-OPEN s38-t2 base=abc1234 scope=scripts/emulator.py,tests/\n"
)
BASE_FULL = "abc1234" + "0" * 33
OPEN_SHA = "d4d9e4b" + "1" * 33
OPEN_FILES = (
    "allostatik/session-ledger.md",
    "allostatik/knowledge/task_reports/2026-09-21-s38-t2-x.md",
)

Run = Callable[..., "subprocess.CompletedProcess[str]"]


def fake_git(
    *,
    diff: Sequence[str] = (),
    untracked: Sequence[str] = (),
    open_commits: Sequence[str] = (OPEN_SHA,),
    parent: str = BASE_FULL,
    open_files: Sequence[str] = OPEN_FILES,
    returncode: int = 0,
) -> Run:
    """Answers each git subcommand the check uses, and records what it was asked."""
    calls: list[list[str]] = []
    answers = {
        "log": open_commits,
        "rev-parse": (parent,),
        "show": open_files,
        "diff": diff,
        "ls-files": untracked,
    }

    def run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        lines = answers[cmd[2]]
        stderr = "fatal: bad revision" if returncode else ""
        return subprocess.CompletedProcess(cmd, returncode, "\n".join(lines) + "\n", stderr)

    run.calls = calls  # type: ignore[attr-defined]
    return run


def check(tmp_path: Path, run: Run, task: str = "s38-t2", text: str = LEDGER) -> int:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(text)
    return main([task], run=run, ledger=ledger)


def test_the_last_open_line_for_a_task_is_the_one_read() -> None:
    opened = parse_task_open(LEDGER, "s38-t2")
    assert (opened.base, opened.scope) == ("abc1234", ("scripts/emulator.py", "tests/"))
    assert opened.line == "TASK-OPEN s38-t2 base=abc1234 scope=scripts/emulator.py,tests/"


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
    assert outside_scope(OPEN_FILES, ()) == []


def test_work_inside_the_scope_passes_and_names_the_open_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = fake_git(
        diff=["scripts/emulator.py", "allostatik/session-ledger.md"],
        untracked=["tests/test_new.py"],
    )
    assert check(tmp_path, run) == 0
    assert "in scope -- 3 files changed since open commit d4d9e4b" in capsys.readouterr().out
    assert all(cmd[:2] == ["git", "--no-optional-locks"] for cmd in run.calls)  # type: ignore[attr-defined]


def test_an_undeclared_record_file_fails_the_close_and_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The likeliest miss: a task edits `plan.md`, which only the session close writes."""
    assert check(tmp_path, fake_git(diff=["scripts/emulator.py", "allostatik/plan.md"])) == 1
    assert "OUT OF SCOPE -- 1 of 2 changed files are not this task's: allostatik/plan.md" in (
        capsys.readouterr().out
    )


def test_a_session_close_file_fails_even_when_declared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One writer for shared files: declaring `plan.md` does not make it a task's to change."""
    text = "TASK-OPEN s38-t4 base=abc1234 scope=allostatik/plan.md,scripts/x.py\n"
    run = fake_git(diff=["allostatik/plan.md", "scripts/x.py"])
    assert check(tmp_path, run, task="s38-t4", text=text) == 1
    assert "allostatik/plan.md (session close only)" in capsys.readouterr().out


def test_an_untracked_file_outside_the_scope_is_caught_too(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check(tmp_path, fake_git(untracked=["traxgen/new_module.py"])) == 1
    assert "traxgen/new_module.py" in capsys.readouterr().out


def test_a_declaration_never_committed_cannot_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without an open commit nothing shows the declaration came before the work."""
    assert check(tmp_path, fake_git(open_commits=())) == 2
    assert "commit the open before the first edit" in capsys.readouterr().out


def test_an_open_commit_that_carried_work_is_out_of_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edit first, then commit the TASK-OPEN line with the work: the reader's backdating case."""
    run = fake_git(open_files=(*OPEN_FILES, "scripts/emulator.py"))
    assert check(tmp_path, run) == 1
    out = capsys.readouterr().out
    assert "OUT OF ORDER" in out and "also changed scripts/emulator.py" in out


def test_an_open_commit_on_another_base_is_out_of_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check(tmp_path, fake_git(parent="fff9999" + "0" * 33)) == 1
    assert "not base=abc1234" in capsys.readouterr().out


def test_the_oldest_commit_carrying_the_line_is_the_open_commit(tmp_path: Path) -> None:
    newer = "eee5555" + "2" * 33
    run = fake_git(open_commits=(newer, OPEN_SHA))
    assert check(tmp_path, run) == 0
    assert ["git", "--no-optional-locks", "rev-parse", f"{OPEN_SHA}^"] in run.calls  # type: ignore[attr-defined]


def test_no_open_line_cannot_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check(tmp_path, fake_git(), task="s38-t9") == 2
    assert "CANNOT CHECK" in capsys.readouterr().out


def test_a_git_failure_cannot_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check(tmp_path, fake_git(returncode=128)) == 2
    assert "fatal: bad revision" in capsys.readouterr().out


def test_a_task_left_open_is_named() -> None:
    text = LEDGER + "TASK-OPEN s38-t3 base=abc1234 scope=x.py\n"
    assert unclosed(text) == ["s38-t2", "s38-t3"]


def test_unclosed_is_quiet_when_every_task_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(LEDGER + "TASK-CLOSED s38-t2 DONE\n")
    assert main(["--unclosed"], ledger=ledger) == 0
    assert capsys.readouterr().out.strip() == "no task left open"


def test_unclosed_fails_on_a_task_left_open(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(LEDGER)
    assert main(["--unclosed"], ledger=ledger) == 1
    assert "left open: s38-t2" in capsys.readouterr().out
