# s38-t4 — what the independent reader found

**Status:** OPEN

**In one paragraph:** _written at close._

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

_written at close._
