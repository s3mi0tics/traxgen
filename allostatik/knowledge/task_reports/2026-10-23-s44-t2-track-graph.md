# s44-t2 — the graph checker, first build

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Build `traxgen/track_graph.py` to the design agreed in s44-t1, and test it against the record.
- **Scope:** `traxgen/track_graph.py` (new), `tests/test_track_graph.py` (new).
- **Budget:** 90 minutes. No renders.
- **Done check:**
  1. *Step:* write the module (doorway nodes with direction, piece rules for STARTER and GOAL_RAIL, joins, the walk, a three-valued answer) and its tests.
  2. *True after:* (a) every `MEASURED_FINISHES` entry, rebuilt to its recorded sha256, reads VALID when it finished and INVALID when it missed; (b) no placement-dark cell of any `MEASURED_RUNS` row reads VALID; (c) a hand-made loop and a hand-made dead end read INVALID, naming the doorway; (d) a course holding any piece with no rule reads UNMEASURED; (e) the full suite passes and the new files lint clean.
  3. *Miss cases:*
     - The test builds a different course from the one that was played, and agrees with the wrong course.
     - The checker reads VALID for everything, and the misses pass because the test only checks finishes.
     - The loop test passes because the walk stops early, not because it detects a loop.
     - The rules are tuned until the 20 pass, and nothing outside the 20 is checked.
  4. *Reads:* `graph.MEASURED_FINISHES` (and each entry's `course_sha256`), `graph.MEASURED_RUNS`, `graph.connection_status`, and the pytest and ruff output.
  5. *Check:* `uv run pytest -q` passes, with tests that assert the rebuilt sha256 before the verdict, that assert both VALID and INVALID counts (17 and 3), that sweep every probed dark cell of every row, and that name the loop's doorway; and `uv run ruff check` on the two new files reports nothing.
- **Outcomes declared before any live run:** none, because there is no live run. Declared before the tests run: 17 VALID and 3 INVALID on the finishes, zero VALID on the dark cells.
