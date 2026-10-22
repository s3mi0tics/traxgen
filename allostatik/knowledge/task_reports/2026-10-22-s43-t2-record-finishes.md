# s43-t2 — which of the record's placements finish

**Status:** OPEN

**In one paragraph:** _written at close_

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
