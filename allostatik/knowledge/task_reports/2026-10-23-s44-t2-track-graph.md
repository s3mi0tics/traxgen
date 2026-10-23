# s44-t2 — the graph checker, first build

**Status:** DONE

**In one paragraph:** `traxgen/track_graph.py` checks a course as a graph of doorways. Each node is the marble crossing into a cell by one side. It walks every route from the starter and answers VALID, INVALID (naming the dead end or loop) or UNMEASURED (a piece or feature it has no rule for). On the record, it reads all 17 finishes VALID and all 3 misses INVALID, each on the exact course that was played. No placement-dark cell of any recorded row reads VALID. It knows two pieces, STARTER and GOAL_RAIL. Mid-task, Colby pointed out that which way a starter's marbles leave depends on where they sit in it. The format as parsed carries no marble placement, so with two or more pieces attached the answer is UNMEASURED.

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

## Close

- **What happened:**
  - Wrote the module and 16 tests.
  - The first loop test failed on its expectation, not the code. The marble re-enters the ring's first cell by a *different* side, so the first doorway crossed twice the same way is the second cell. That's the direction-of-travel point from t1, seen in practice. The expectation was corrected and explained in the test.
  - Ran seven deliberate breakages of the module. All seven were caught.
- **What changed:** `traxgen/track_graph.py` (new), `tests/test_track_graph.py` (new).
- **Evidence:**
  - `task_check`: in scope.
  - Suite: `1118 passed, 1 deselected`.
  - `ruff check` and `ruff format --check` on both files: clean.
  - Mutants, each killed (failing tests out of 16): no half-hole term 1; no loop check 1; starter takes every side 12; two attached not refused 1; goal ignores entry side 2; off-footprint goal joins 1; half-hole ignores the completing plate 1.
  - Declared outcomes met: 17 VALID, 3 INVALID, 0 dark cells VALID (over 100 checked).
- **Decisions made inside the task:**
  - Piece rules are injectable (`check_course(course, rules=...)`), so a test can supply a piece the record has not measured. That's how the loop is exercised without claiming anything about curves.
  - INVALID beats UNMEASURED: one measured dead end fails the course whatever the unmeasured routes do.
  - A starter off its footprint, more than one starter, a stacked cell, a raised layer, rails, pillars or balconies all read UNMEASURED.
  - The test rebuilds the finish courses itself rather than importing `scripts.finish_record`, and asserts each sha256 first (plan item 16 wants tests off `scripts/`).
  - The adversarial panel was skipped: nothing calls the module yet, so a clean revert undoes it, which is the working notes' skip case.
- **For the record:**
  - `decisions.md`: the graph checker's shape (doorway nodes with direction of travel, piece rules, joins, a three-valued answer, INVALID over UNMEASURED), as `traxgen/track_graph.py`.
  - `decisions.md` or a D066 note: the finish evidence for half-holes is goal-only (r06's starter on (0,1) finished).
  - `plan.md` *What is true now*: the graph checker exists, reproduces all 20 measured finishes, and knows STARTER and GOAL_RAIL only.
  - `plan.md` open question (Colby, s44): where the marbles sit in the starter decides which way they leave. Does the app let you choose, and does the course file record it? The parsed format has no such field. Until it's known, two pieces on a starter read UNMEASURED.
  - `plan.md` open question: are the 3 misses about the half-hole or about the one placement? Cheap test: goals on (-1,3) and (-2,5) of a lone plate, from a side other than West (Colby: queue it).
  - `plan.md` item 2: first build done. Next, curves, which need a measured curve rule (#7, item 1).
- **Friction:** none.
- **Next:** the session close, or a curve rule.
