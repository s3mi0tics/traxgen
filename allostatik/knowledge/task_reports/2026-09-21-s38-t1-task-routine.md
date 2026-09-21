# s38-t1 — the task routine

**Status:** DONE

**In one paragraph:** traxgen now has a routine for single tasks, alongside the one for sessions. Each task declares, before any work, which files it may change. It writes a report Colby can read, and it stops for him only for four named reasons. A small script, `task_check`, reads the declared scope from the ledger and git's list of changed files, and says whether the task stayed inside it. The session close is the only writer of the shared record, which is what will let tasks run side by side later.

## Open (written before the work)

- **Goal:** give traxgen a per-task routine, with an open and a close for each task, a committed report, a scope each task declares and a check that holds it to that scope, and a short list of reasons to stop and ask Colby.
- **Scope:** `allostatik/workflow.md` (a new Part 2 section, nothing in Part 1), `scripts/task_check.py`, `tests/test_task_check.py`, and this folder. The `TASK-OPEN s38-t1` ledger line is the record.
- **Budget:** 30 minutes, two full test runs.
- **Done check:**
  1. *Step:* write the routine, the report template and the scope check.
  2. *True after:* (a) `workflow.md` Part 2 has the task routine and Part 1 still hashes to its stamp; (b) `task_check` says no when a changed file is outside the declared scope, and yes when all are inside; (c) the full suite passes.
  3. *Miss cases:* (a) the routine was added inside the stamped Part 1, so the stamp check fails; (b) `task_check` passes a task that edited an undeclared file, or passes when the `TASK-OPEN` line is missing; (c) the new tests pass but something else broke.
  4. *Reads:* the part1 stamp on the `BEGIN` marker line (written upstream, before this task); the tests in `tests/test_task_check.py`, which feed `task_check` a ledger line and a list of changed files; the suite's own summary line.
  5. *Check:* the stamp check reports `part1` matching its stamp; `test_task_check.py` holds one test for each miss case in (b) and they pass; the full suite reports zero failures.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** wrote the *Task routine* section into `workflow.md` Part 2 (open, work, the four stop reasons, close, who writes the shared record, continuity, and the scope check in five slots). Wrote the report template in this folder's `README.md`, and `scripts/task_check.py` with ten offline tests. This task was then closed by its own check.
- **What changed:** `allostatik/workflow.md`, `allostatik/knowledge/task_reports/README.md`, this report, `scripts/task_check.py`, `tests/test_task_check.py`, and the ledger; one commit.
- **Evidence:** `s38-t1: in scope -- 6 files changed since 453197d, all declared`. 964 passed, 1 deselected. part1 still matches its stamp. Ruff is clean on both new files.
- **Decisions made inside the task:**
  - The scope takes exact paths and folder prefixes, not glob patterns, because two forms cover every case so far.
  - `task_check` passes `--no-optional-locks` so it never writes the index (#38).
  - The ledger's missing clock is stated as a limit rather than fixed with a second commit per task.
- **For the record:**
  - `decisions.md`: a row saying tasks run under the *Task routine*: each declares its scope in a `TASK-OPEN` line before work, `task_check` holds it there at close, only the session close writes the shared record, and the four stop reasons are the only ones.
  - `plan.md`: the routine exists; the parallel form (worktrees, scopes that don't overlap) waits for a trigger, which is the first time two independent tasks are both ready.
- **Next:** s38-t2, a task run by an agent working only from this routine.
