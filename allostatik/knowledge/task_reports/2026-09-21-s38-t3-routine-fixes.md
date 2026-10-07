# s38-t3 — the routine, fixed where its first run caught on it

**Status:** DONE

**In one paragraph:** the routine's first user, s38-t2's agent, found eight places where the text was unclear, missing or wrong. Each now has an answer in the text. The rule that only the session close writes the shared record is now enforced by `task_check`, not just asked for: a task that changes `plan.md` or another session-close file fails its close, even if it declared the file.

## Open (written before the work)

- **Goal:** fix the eight places where s38-t2's agent found the routine unclear, missing or wrong, and make "only the session close writes the shared record" something `task_check` enforces instead of something the text asks for.
- **Scope:** `allostatik/workflow.md` (the *Task routine* section only), `scripts/task_check.py`, `tests/test_task_check.py`, and the template in this folder.
- **Budget:** 25 minutes, two full test runs.
- **Done check:**
  1. *Step:* revise the routine, the template and `task_check`.
  2. *True after:* (a) each of the eight friction items in s38-t2's reply has an answer in the text; (b) `task_check` says no when a task changes a session-close file, even one it declared; (c) part1 still matches its stamp, and the full suite passes.
  3. *Miss cases:* (a) an item gets a fix that the Runner's next read would still trip on, for example the example ledger line still naming a stale base; (b) a task that declares `allostatik/plan.md` and edits it passes; (c) the edit strays into Part 1, or breaks a test.
  4. *Reads:* s38-t2's friction list, in its reply as relayed in this session and summarised in this report's close; `tests/test_task_check.py`, which will hold a test that declares `plan.md` and changes it; the part1 stamp; the suite's summary line.
  5. *Check:* the close lists all eight items, each with the sentence that now answers it; that test passes and fails when the close-only rule is removed; part1 matches its stamp; the suite reports zero failures.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** revised the *Task routine* section, the template and `task_check`. Here are the eight friction items from s38-t2, each with the text that now answers it:
  1. *"Before any work" conflicted with naming the scope first.* The heading is now "Open, before the first edit", and reading to work out the scope comes first.
  2. *The example ledger line had a stale `base`.* It's now s38-t2's real line, and says that 91828b6 was HEAD when that task opened.
  3. *Was a pending live proof STOPPED or DONE?* "A done check that can only pass on the Mac stops the task, with the command to run there as the question." Also: "`STOPPED` ends the task, and his answer starts a new task."
  4. *The chime came before the commit.* It now comes after the close, commit included, so the sound means everything is saved.
  5. *A report can't name its own commit.* The template now says "the commit is the one that adds this report".
  6. *`knowledge/task_reports/` lacked its `allostatik/` prefix.* Fixed in both places.
  7. *AGENTS.md's first-reply rule vs tasks.* "A task runs inside a session that is already open, so it doesn't run the session open again."
  8. *May a task edit `environment.md`?* No. It's on the session-close list now, and `task_check` enforces that.
- **What changed:** the *Task routine* section of `allostatik/workflow.md`, the template, `scripts/task_check.py`, `tests/test_task_check.py`, this report and the ledger. The commit is the one that adds this report.
- **Evidence:** `s38-t3: in scope -- 6 files changed since ca2841b, all declared`. 973 passed, 1 deselected. part1 matches its stamp. With the close-only rule removed, the new test fails (1 failed, 10 passed), and it passes with the rule in place.
- **Decisions made inside the task:**
  - The session-close list includes `knowledge/environment.md` and `knowledge/resources.md`, because they're shared the same way the record is.
  - `STOPPED` is final for the task, and follow-up work opens as a new task, so the ledger stays append-only.
- **For the record:** `observations.md` should say that the routine's first user, an agent with no other context, found eight defects in a text its author had just checked, and that each was provable from the words. This is the s123 finding repeated on a new routine: the author reads generously.
- **Next:** an independent reader, running on a different model, grades the routine's checks and both task reports.
