# s48-t5 — the switch in the checker, for one marble per switch

**Status:** OPEN

**In one paragraph:** _written at close_

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
