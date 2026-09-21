# scripts/task_check.py
"""Is a task's work inside the scope it declared at open? (s38, `workflow.md` *Task routine*.)

Reads two records that exist before this runs: the task's `TASK-OPEN` line in
`allostatik/session-ledger.md`, appended before any work, and git's list of files
changed since that line's `base` commit, untracked files included. It never reads
the task's report, which is the checked party's own account.

    uv run python -m scripts.task_check s38-t2

Prints one line. Exit 0: in scope. Exit 1: files outside the scope. Exit 2: no
`TASK-OPEN` line, or git could not answer -- un-runnable, which is not a pass.
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

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class TaskCheckError(Exception):
    """The records the check reads are missing or unreadable."""


@dataclass(frozen=True)
class TaskOpen:
    """A task's `TASK-OPEN` ledger line: its base commit and declared scope."""

    task: str
    base: str
    scope: tuple[str, ...]


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
        return TaskOpen(task=task, base=fields["base"], scope=scope)
    raise TaskCheckError(f"no TASK-OPEN line for {task} in the ledger")


def covers(entry: str, path: str) -> bool:
    """An entry covers a path exactly, or as a folder when the entry ends in `/`."""
    return path.startswith(entry) if entry.endswith("/") else path == entry


def outside_scope(changed: Sequence[str], scope: Sequence[str]) -> list[str]:
    """The changed paths that no declared or always-in-scope entry covers."""
    entries = (*scope, *ALWAYS_IN_SCOPE)
    return [path for path in changed if not any(covers(entry, path) for entry in entries)]


def changed_since(base: str, run: Runner = subprocess.run) -> list[str]:
    """Files that differ from `base` in the working tree, plus untracked files.

    `--no-optional-locks` keeps this a pure read: git may not refresh the index,
    which is what strands `.git/index.lock` on a surface that cannot delete (#38).
    """

    def git(*args: str) -> list[str]:
        result = run(
            ["git", "--no-optional-locks", *args], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise TaskCheckError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return [line for line in result.stdout.splitlines() if line]

    tracked = git("diff", "--name-only", base)
    untracked = git("ls-files", "--others", "--exclude-standard")
    return sorted({*tracked, *untracked})


def main(
    argv: Sequence[str] | None = None,
    *,
    run: Runner = subprocess.run,
    ledger: Path = LEDGER,
) -> int:
    """Check one task's scope. Returns a process exit code."""
    parser = argparse.ArgumentParser(description="Is a task's work inside its declared scope?")
    parser.add_argument("task", help="the task id, e.g. s38-t2")
    args = parser.parse_args(argv)
    try:
        opened = parse_task_open(ledger.read_text(), args.task)
        changed = changed_since(opened.base, run)
    except (OSError, TaskCheckError) as exc:
        print(f"{args.task}: CANNOT CHECK -- {exc}")
        return 2
    stray = outside_scope(changed, opened.scope)
    if stray:
        print(
            f"{args.task}: OUT OF SCOPE -- {len(stray)} of {len(changed)} changed files "
            f"not declared: {', '.join(stray)}"
        )
        return 1
    print(
        f"{args.task}: in scope -- {len(changed)} files changed since {opened.base}, all declared"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
