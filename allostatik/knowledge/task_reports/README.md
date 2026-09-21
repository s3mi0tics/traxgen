# Task reports

This folder holds one file per task, written by the task routine in `allostatik/workflow.md` (Part 2, *Task routine*). Files are named `YYYY-MM-DD-sNN-tN-short-title.md`, so a folder listing reads in order.

A report is history. It is written at the task's open and close, and never edited after the close. Current state lives in `plan.md`, and the session close folds these reports into the record.

## Template

Copy everything below the line. Replace every line in italics.

---

# sNN-tN — _short title_

**Status:** _OPEN while the task runs; then DONE, or STOPPED — needs Colby: the question, or FAILED — why_

**In one paragraph:** _what the task did and what it means, in plain words — written at close_

## Open (written before the work)

- **Goal:** _one sentence_
- **Scope:** _every file or folder the task may change; the `TASK-OPEN` ledger line is the record_
- **Budget:** _minutes, renders or attempts_
- **Done check:**
  1. *Step:* _the task_
  2. *True after:* _each thing that is true after the task and was not before_
  3. *Miss cases:* _for each, a finished-looking task where it is still not true_
  4. *Reads:* _records that exist before the check runs, which someone else could read again_
  5. *Check:* _one sentence that names what Reads names, says no in every miss case, and reports the value where it can_
- **Outcomes declared before any live run:** _or "none, because there is no live run"_

## Close

- **What happened:** _plain words_
- **What changed:** _the files; the commit is the one that adds this report_
- **Evidence:** _the `task_check` line, the test summary, any render lines; a passing check is one line_
- **Decisions made inside the task:** _one sentence each_
- **For the record:** _what `plan.md`, `decisions.md` or `observations.md` should say; the session close folds it in_
- **Next:** _the next task, or what the stop is waiting on_
