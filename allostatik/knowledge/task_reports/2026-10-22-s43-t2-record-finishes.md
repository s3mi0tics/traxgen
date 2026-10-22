# s43-t2 — which of the record's placements finish

**Status:** DONE

**In one paragraph:** Every live cell in the record was rebuilt, uploaded and played once by link. **17 of 20 finish.** The 3 that don't are one placement on three starter rotations: starter at (0,0), goal to the East on (0,1), which is an uncompleted half-hole. All 17 goals off a half-hole finished. So the app passes a goal on an uncompleted half-hole as placed legally (white triangle), but the marble does not finish there. That is D066's rule ("not a usable square until a neighbouring plate completes it") shown in a run, not just in the editor. Both controls were active and finished. The results are now `graph.MEASURED_FINISHES`, one entry per cell, and a test rebuilds every entry's course to its recorded hash.

## Open (written before the work)

- **Goal:** Render one course for each of the 20 live cells in `MEASURED_RUNS` with the finish check, and write each cell's finish into a new per-cell table in `graph.py`.
- **Scope:** `scripts/finish_record.py` (new), `tests/test_finish_record.py` (new), `traxgen/graph.py`.
- **Budget:** 60 minutes of renders; 1 emulator session (2 if the first launch dies, #21); 22 renders plus at most one retry each.
- **Done check:**
  1. *Step:* `scripts/finish_record.py` rebuilds each live cell's course and refuses any that `start_goal_status` does not read as CONNECTED. It uploads them and renders each once by link with `detect_finish`, bracketed by the control `KN6F459ZR3` first and last. It writes `screenshots/finish_record/results.json` after every cell. Then `graph.MEASURED_FINISHES` records one entry per judged cell.
  2. *True after:* (a) all 20 cells have a FINISHED or NOT_FINISHED reading, or are named as unjudged with the reason; (b) `MEASURED_FINISHES` holds exactly the judged cells, each matching a live cell of a `MEASURED_RUNS` row; (c) a test rebuilds each entry's course and gets the recorded sha256.
  3. *Miss cases:*
     - The builder makes a different course from the one the row measured, and the run is about the wrong geometry.
     - A harness failure is recorded as NOT_FINISHED.
     - The control fails and the cells are believed anyway.
     - The table is typed in by hand from the terminal, and a value differs from `results.json`.
     - An entry names a cell no row calls live.
  4. *Reads:* `screenshots/finish_record/results.json`; the run's stderr; the suite's output.
  5. *Check:* the suite passes, with tests that rebuild every entry's sha256 and match it to a live row cell. Both controls in `results.json` read `active` and `finished`. A script compares `MEASURED_FINISHES` to `results.json` field by field and prints no difference.
- **Outcomes declared before any live run:**
  - Both controls (`KN6F459ZR3`, first and last): `active`, `finished`. Either one otherwise voids the run.
  - Cell `r00-d2` is the Phase 1 geometry (STARTER (0,0) rot 0, GOAL_RAIL NW rot 3): `finished`.
  - The other 19: no prediction for each cell. A white triangle says nothing about the path (#57), so any mix of finished and not_finished is a finding, not a failure. Every cell should read `active`; an `inactive` on a live cell contradicts its row and stops the task.
  - An UNJUDGED reading on an `active` cell points at the harness, not the course: retry it once and report it.

## Close

- **What happened:**
  - Wrote `scripts/finish_record.py`. It rebuilds each live cell's course, checks that `start_goal_status` reads CONNECTED, uploads all 20, and renders the control, the 20 cells and the control again in one cold session by link with the finish check.
  - Then generated `MEASURED_FINISHES` in `graph.py` from `results.json` rather than typing it.
- **What changed:** `scripts/finish_record.py` (new), `tests/test_finish_record.py` (new, 8 tests), `traxgen/graph.py` (`MeasuredFinish`, `MEASURED_FINISHES`).
- **Evidence:**
  - `task_check`: in scope, 3 files.
  - Suite: `1102 passed, 1 deselected`.
  - Uploads: 20 of 20 on the first attempt.
  - Renders: the opening control's first attempt died (#21), and its second was active and finished (peak 1116). Every cell succeeded on attempt 1, all `active`. The closing control was active and finished (peak 1071).
  - Finished, with peaks: r00-d2 983, r01-d1 894, r02-d2 1016, r03-d1 1003, r04-d2 1087, r05-d1 1431, r06-d2 964, r07-d0 983, r07-d2 1005, r07-d4 983, r08-d1 1563, r08-d3 1746, r08-d5 937, r09-d2 1156, r10-d0 993, r10-d4 1148, r11-d4 1163.
  - Not finished: r00-d0 10, r02-d0 7, r04-d0 7, all with the goal at (0,1).
  - Margin: highest miss 10, lowest finish 894, against a threshold of 30.
  - Compared `MEASURED_FINISHES` to `results.json` (finished, peak, code, sha256, direction): 20 entries, 0 differences.
  - Declared outcomes: controls met; r00-d2 (Phase 1 geometry) finished, as declared; every cell `active`; no UNJUDGED reading.
- **Decisions made inside the task:**
  - One entry per cell in a new table rather than a field on `MeasuredRun`, because a row covers several cells (Colby: yes at the open).
  - An entry points at its row by object (`MEASURED_RUNS[i]`), and the sha256 test catches a wrong row or direction.
  - Unjudged cells would be left out, never recorded as misses. None occurred.
  - The table was generated from `results.json`, which is gitignored. The table in `graph.py` is the durable copy, and the share codes are in it.
- **For the record:**
  - `plan.md` *What is true now*: 17 of the record's 20 live cells finish. The 3 that don't put the goal on the uncompleted half-hole (0,1). The white triangle passes a goal on an uncompleted half-hole; the marble does not finish there. So `MEASURED_RUNS`' placement claims at starter (0,0), direction E (rows 0, 2, 4) are placements that do not finish.
  - `plan.md` order step (2): done. Item 19: the finish check has now run over the whole record.
  - A model consequence for item 2 (the graph checker) and the generator: `predict_connection`/`predicted_live_directions` call (0,0)→E live at even starter rotations. As a finish, that is wrong; the half-hole rule (D066) already says why. `generate_multi_plate` never offers that placement, so nothing the product emits is affected.
  - D066 gets its first run-level evidence: 3 of 3 goals on an uncompleted half-hole miss, 17 of 17 elsewhere finish.
  - #21, one more firing: the first launch after a cold boot died again (1 of 1 session here; 2 of 3 cold boots in s43).
- **Friction:** none.
- **Next:** the session close.
