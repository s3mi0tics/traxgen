# s38-t4 — what the independent reader found

**Status:** DONE

**In one paragraph:** the independent reader failed three of the five things it graded, and each failure went in the generous direction, the same pattern allostatik-dev's check sweep found. Two are fixed in code. A task must now commit its declaration before its first edit, and `task_check` refuses one that didn't, so a scope can't be declared after the fact. `task_check --unclosed` finds a task left open. Friction now has a line in the template, so the next task reads it from a record rather than a conversation. The phone-evidence file no longer overwrites itself. One finding stays open and recorded rather than fixed: three of the four stop reasons have never fired.

## Open (written before the work)

- **Goal:** fix what the independent reader (a different model, with no stake in the routine) found in s38-t1 to t3: prove the declaration came before the work, make a task left open findable by a script, keep a task's friction as a record, and stop a second failed render in the same second from overwriting the first one's evidence.
- **Scope:** the *Task routine* section of `allostatik/workflow.md`, `scripts/task_check.py`, `tests/test_task_check.py`, `scripts/emulator.py` (the evidence file's name only), `tests/test_emulator_session.py`, and the template in this folder.
- **Budget:** 40 minutes, three full test runs.
- **Done check:**
  1. *Step:* apply the reader's findings 1 to 4.
  2. *True after:* (a) `task_check` says no to a task whose `TASK-OPEN` line was never committed, whose open commit carried work, or whose open commit's parent isn't its `base`; (b) `task_check --unclosed` names a task with no `TASK-CLOSED`; (c) the template has a *Friction* line; (d) two evidence captures in the same second keep both files; (e) the suite passes and part1 matches its stamp.
  3. *Miss cases:* (a) a task edits first, commits the open line with its work, and passes; (b) an orphaned `TASK-OPEN` is only found if someone remembers to look; (c) friction lives only in a conversation reply again; (d) the second capture overwrites the first; (e) something else broke.
  4. *Reads:* the reader's findings in this report's close, copied verbatim from its reply before any fix was made; `tests/test_task_check.py` and `tests/test_emulator_session.py`, which will hold a test per miss case; this task's own open commit, which `task_check s38-t4` must pass under the new rule; the part1 stamp; the suite's summary line.
  5. *Check:* each of (a), (b) and (d) has a test that fails when its fix is removed; the template's close lists *Friction*; `task_check s38-t4` passes using its own open commit; the suite reports zero failures, and part1 matches its stamp.
- **Outcomes declared before any live run:** none, because there is no live run.

## The reader's findings, verbatim (recorded before any fix)

1. **Backdating gap.** "the ledger has no clock, so a `TASK-OPEN` line written after the work would still pass." Miss case: edit first, declare a scope matching the diff, pass. Fix: commit the open half before work.
2. **Self-attested Reads.** t3's Reads names "s38-t2's friction list, in its reply as relayed in this session." Miss case: any task can invent or embellish the complaint it's fixing, since nothing else records it. Fix: the friction list belongs in t2's own report.
3. **Continuity is unenforced.** Miss case: an orphaned `TASK-OPEN` is only caught if an agent remembers to look. Fix: a `task_check` mode listing unclosed `TASK-OPEN`s, run at session open.
4. **Filename collision.** `save_device_evidence` names the file to the second and opens it with `"wb"`, so two failures in the same second silently overwrite the first.
5. **Stop reasons 2 to 4 never exercised.** Only reason 1 has fired across all three reports.

Grades: scope check FAIL (1), done-check Reads FAIL (2), continuity, ordering and one-writer FAIL (3), stop reasons PASS, t2's code PASS with finding 4.

## Close

- **What happened:** opened with its own open commit (d4d9e4b), making this the first task under the rule it adds. Then `task_check` gained the open-commit test (the commit that added the `TASK-OPEN` line must sit on `base` and carry only the ledger and reports) and the `--unclosed` mode. The routine and template were updated to match. `save_device_evidence` now creates its file exclusively and names a same-second second capture `-2`.
- **What changed:** the *Task routine* section of `allostatik/workflow.md`, the template, `scripts/task_check.py`, `tests/test_task_check.py`, `scripts/emulator.py` (the evidence file's name only), `tests/test_emulator_session.py`, this report and the ledger. The commit is the one that adds this report's close.
- **Evidence:**
  - `s38-t4: in scope -- 6 files changed since open commit d4d9e4b, all declared`.
  - Under the new rule, `task_check s38-t2` reports `OUT OF ORDER -- open commit ca2841b also changed scripts/emulator.py, ...`, which is the true verdict on a task that predates it.
  - `--unclosed` named `s38-t4` while it was open.
  - 981 passed, 1 deselected. part1 matches its stamp.
  - Deliberately broken versions, each against a passing control: open commit not checked, 5 tests failed; work allowed in the open commit, 1 failed; `--unclosed` never clearing, 2 failed; evidence file overwritten, 1 failed.
- **Decisions made inside the task:**
  - A provable ordering violation exits 1 (fail), and a missing record exits 2 (can't check).
  - s38-t1 to t3 stay as written. They're history, and `task_check` reporting them out of order is the honest record, not something to paper over.
  - Finding 2 isn't fixed after the fact: t3's *Reads* stays a failure. The *Friction* line stops it happening again.
  - Finding 5 waits for real firings, because no test can make a stop reason fire honestly.
- **For the record:**
  - `decisions.md`: tasks commit their declaration before their first edit (the open commit), `task_check` enforces it, and `--unclosed` runs at the session open and close.
  - `observations.md`: an independent reader on a different model overturned three of five self-graded passes, every one in the generous direction, and each provable from the text.
  - `knowledge/environment.md`: run deliberately broken versions of the code with `PYTHONDONTWRITEBYTECODE=1`. A broken file the same size as the original, restored within the same second, kept the broken version's bytecode and produced a false failure here.
- **Friction:** the routine says nothing about how to run deliberately broken versions of the code, and the bytecode trap above cost one confusing red run. It belongs in `environment.md` rather than the routine.
- **Next:** the session close. An agent that wrote none of this folds the four reports into the record, and `task_check` holds that fold to the session-close files.
