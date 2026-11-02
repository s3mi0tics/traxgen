# s48-t5 — the switch in the checker, for one marble per switch

**Status:** DONE

**In one paragraph:** The checker now knows the switch, for the first marble through it. `SWITCH_LEFT` passes 0→2 and 2→4 and stops a marble entering by 4; `SWITCH_RIGHT` is the mirror; the odd sides take no marble. A stopped marble is a dead end, so the course is INVALID, while the launch pad still loads it, as s48-t3's trails showed. Two cases read UNMEASURED, because a second marble's path depends on which arrives first (s48-t4): a launch pad with more than one valid connection on a course with a switch, and one route coming back into a switch it already passed.

## Open (written before the work)

- **Goal:** `track_graph` checks courses with `SWITCH_LEFT` and `SWITCH_RIGHT` from s48-t3's tables, and answers UNMEASURED wherever a switch could see a second marble (s48-t4: the outcome then depends on timing).
- **Scope:** `traxgen/track_graph.py`, `tests/test_track_graph.py`.
- **Budget:** 60 minutes, no device.
- **Done check:**
  1. *Step:* `tracks_rule` takes a side that stops the marble (`None`); `SWITCH_LEFT_TRACKS` {0: 2, 2: 4, 4: stop} and `SWITCH_RIGHT_TRACKS` {4: 2, 2: 0, 0: stop} in `PIECE_RULES`; UNMEASURED when the starter loads more than one marble on a course with a switch, or one route reaches a switch a second time.
  2. *True after:* (a) every s48-t3 ring-board row reproduces: one goal at a time on each free side, VALID only on the measured exit, and the stopping rotation INVALID as a dead end, not as "no marble loads"; (b) the closed rotations read "no marble loads"; (c) a two-marble course with a switch reads UNMEASURED, and the same course with the switch swapped for a goal does not; (d) a route back into its own switch reads UNMEASURED; (e) the suite passes.
  3. *Miss cases:* the tables are world-frame and pass only at rotation 0; the stop side reads "no way in" (the marble would never load, contradicting s48-t3's trails); the second-marble guard is skipped because the walk's memory of finished doorways returns before the switch is reached; a test passes because of a dead end, not the guard.
  4. *Reads:* the new tests in `tests/test_track_graph.py`; the pytest summary.
  5. *Check:* the new tests pass, and each fails under its own mutation (each table shifted one rotation; stop as `accepts=False`; each of the two guards removed), run with `PYTHONDONTWRITEBYTECODE=1`; the suite reports 0 failed.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** `tracks_rule` takes `None` for a side that holds the marble; `SWITCH_LEFT_TRACKS` and `SWITCH_RIGHT_TRACKS` in `PIECE_RULES`, with the measurement in a comment beside them; two guards in the walk, the marble count at launch and the re-entry check before a switch's rule runs (before the walk's memory of finished doorways can skip it, since that memory is only filled after a doorway is left).
- **What changed:** `traxgen/track_graph.py`, `tests/test_track_graph.py` (17 new test cases).
- **Evidence:**
  - `s48-t5: in scope -- 2 files changed since open commit e74b4ab, all declared`.
  - `1208 passed, 1 deselected`; ruff clean on both files.
  - Mutations, `PYTHONDONTWRITEBYTECODE=1`: LEFT table shifted one side, 8 failures; RIGHT shifted, 7; stop read as no way in, 4; LEFT read in the world frame, 6; no marble-count guard, 1 (`test_two_marbles_on_a_course_with_a_switch_are_unmeasured`); no re-entry guard, 1 (`test_a_route_back_into_its_own_switch_is_unmeasured`). With the marble-count guard removed, the two-marble course reads `VALID, every route ends in a goal`, so the test rests on the guard, not on a dead end.
- **Decisions made inside the task:**
  - Any second marble on a course with a switch is UNMEASURED, even if its route never touches the switch. Simpler, and errs toward "not measured"; the trigger to refine it is the first generated course it blocks.
  - The re-entry guard is per route, not per walk: within one marble's route a switch is reached twice only by coming back to it.
  - What a flipped lever does is measured for a branch entry (s48-t4) but the checker does not use it yet; it is in the comment beside the tables.
- **For the record:**
  - `track_graph` knows STARTER, GOAL_RAIL, CURVE, CROSS, SWITCH_LEFT, SWITCH_RIGHT; the switch for one marble per switch (D-row).
  - plan item 2: the switch rule landed for one marble; #27's state search waits for a course that needs two marbles on a switch, and for timing, which the checker cannot see.
- **Friction:** none.
- **Next:** the session close.
