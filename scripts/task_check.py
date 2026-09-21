# scripts/task_check.py
"""Did a task stay inside the scope it declared, and declare it first? (s38, *Task routine*.)

Reads records that exist before this runs: the task's `TASK-OPEN` line in
`allostatik/session-ledger.md`; the *open commit* that added that line, whose
parent must be the line's `base` and which may change only the ledger and task
reports, so git's history shows the declaration came before any work; and git's
list of files changed since the open commit, untracked files included. It never
reads the task's report, which is the checked party's own account.

    uv run python -m scripts.task_check s38-t4
    uv run python -m scripts.task_check --unclosed

Prints one line. Exit 0: in scope (with --unclosed: no task left open). Exit 1: a
file outside the scope, an open commit out of order, or a task left open. Exit 2:
a record is missing or git could not answer -- un-runnable, which is not a pass.
"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

LEDGER = Path("allostatik/session-ledger.md")

# Every task writes these, so no task has to declare them.
ALWAYS_IN_SCOPE: tuple[str, ...] = (
    "allostatik/session-ledger.md",
    "allostatik/knowledge/task_reports/",
)

# Only the session close writes these, so no task may change them, declared or not.
# One writer for shared files is what lets tasks run side by side later.
CLOSE_ONLY: tuple[str, ...] = (
    "allostatik/plan.md",
    "allostatik/log.md",
    "allostatik/decisions.md",
    "allostatik/observations.md",
    "allostatik/decisions-and-observations-index.md",
    "allostatik/knowledge/environment.md",
    "allostatik/knowledge/resources.md",
)

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class TaskCheckError(Exception):
    """A record the check reads is missing or unreadable: un-runnable, not a pass."""


class OpenOrderError(Exception):
    """The records show the declaration did not come before the work."""


@dataclass(frozen=True)
class TaskOpen:
    """A task's `TASK-OPEN` ledger line: its base commit, declared scope and exact text."""

    task: str
    base: str
    scope: tuple[str, ...]
    line: str


def parse_task_open(ledger_text: str, task: str) -> TaskOpen:
    """The last `TASK-OPEN` line for `task`; raise if there is none or it lacks a field."""
    for line in reversed(ledger_text.splitlines()):
        parts = line.split()
        if parts[:2] != ["TASK-OPEN", task]:
            continue
        fields = dict(part.split("=", 1) for part in parts[2:] if "=" in part)
        if not fields.get("base") or "scope" not in fields:
            raise TaskCheckError(f"TASK-OPEN {task} lacks base= or scope=: {line!r}")
        scope = tuple(entry for entry in fields["scope"].split(",") if entry)
        return TaskOpen(task=task, base=fields["base"], scope=scope, line=line)
    raise TaskCheckError(f"no TASK-OPEN line for {task} in the ledger")


def unclosed(ledger_text: str) -> list[str]:
    """Task ids with a `TASK-OPEN` line and no `TASK-CLOSED` after it, in ledger order."""
    still_open: list[str] = []
    for line in ledger_text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0] == "TASK-OPEN":
            still_open.append(parts[1])
        elif parts[0] == "TASK-CLOSED" and parts[1] in still_open:
            still_open.remove(parts[1])
    return still_open


def covers(entry: str, path: str) -> bool:
    """An entry covers a path exactly, or as a folder when the entry ends in `/`."""
    return path.startswith(entry) if entry.endswith("/") else path == entry


def outside_scope(changed: Sequence[str], scope: Sequence[str]) -> list[str]:
    """The changed paths that are not this task's: session-close files, or ones no entry covers."""
    entries = (*scope, *ALWAYS_IN_SCOPE)
    return [
        path
        for path in changed
        if path in CLOSE_ONLY or not any(covers(entry, path) for entry in entries)
    ]


def git_lines(run: Runner, *args: str) -> list[str]:
    """One git call's output lines. `--no-optional-locks` keeps it a pure read (#38)."""
    result = run(["git", "--no-optional-locks", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise TaskCheckError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def find_open_commit(opened: TaskOpen, run: Runner, ledger: Path = LEDGER) -> str:
    """The commit that added the task's `TASK-OPEN` line, held to being a clean open commit."""
    adding = git_lines(run, "log", "--format=%H", "-S", opened.line, "--", ledger.as_posix())
    if not adding:
        raise TaskCheckError(
            f"the TASK-OPEN line for {opened.task} is in no commit -- "
            "commit the open before the first edit"
        )
    sha = adding[-1]  # `git log` lists newest first; the oldest is the one that added it
    parent = git_lines(run, "rev-parse", f"{sha}^")[0]
    if not parent.startswith(opened.base):
        raise OpenOrderError(f"open commit {sha[:7]} sits on {parent[:7]}, not base={opened.base}")
    carried = [
        path
        for path in git_lines(run, "show", "--name-only", "--format=", sha)
        if not any(covers(entry, path) for entry in ALWAYS_IN_SCOPE)
    ]
    if carried:
        raise OpenOrderError(
            f"open commit {sha[:7]} also changed {', '.join(carried)} -- work before the open"
        )
    return sha


def changed_since(commit: str, run: Runner) -> list[str]:
    """Files that differ from `commit` in the working tree, plus untracked files."""
    tracked = git_lines(run, "diff", "--name-only", commit)
    untracked = git_lines(run, "ls-files", "--others", "--exclude-standard")
    return sorted({*tracked, *untracked})


def main(
    argv: Sequence[str] | None = None,
    *,
    run: Runner = subprocess.run,
    ledger: Path = LEDGER,
) -> int:
    """Check one task, or list the tasks left open. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        description="Did a task stay inside its declared scope, and declare it first?"
    )
    parser.add_argument("task", nargs="?", help="the task id, e.g. s38-t4")
    parser.add_argument("--unclosed", action="store_true", help="list tasks never closed")
    args = parser.parse_args(argv)
    try:
        text = ledger.read_text()
    except OSError as exc:
        print(f"CANNOT CHECK -- {exc}")
        return 2
    if args.unclosed:
        left = unclosed(text)
        if left:
            print(f"left open: {', '.join(left)} -- resume or close each before new work")
            return 1
        print("no task left open")
        return 0
    if not args.task:
        parser.error("name a task, or pass --unclosed")
    try:
        opened = parse_task_open(text, args.task)
        sha = find_open_commit(opened, run, ledger)
        changed = changed_since(sha, run)
    except TaskCheckError as exc:
        print(f"{args.task}: CANNOT CHECK -- {exc}")
        return 2
    except OpenOrderError as exc:
        print(f"{args.task}: OUT OF ORDER -- {exc}")
        return 1
    stray = outside_scope(changed, opened.scope)
    if stray:
        named = [f"{path} (session close only)" if path in CLOSE_ONLY else path for path in stray]
        print(
            f"{args.task}: OUT OF SCOPE -- {len(stray)} of {len(changed)} changed files "
            f"are not this task's: {', '.join(named)}"
        )
        return 1
    print(
        f"{args.task}: in scope -- {len(changed)} files changed since open commit "
        f"{sha[:7]}, all declared"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
