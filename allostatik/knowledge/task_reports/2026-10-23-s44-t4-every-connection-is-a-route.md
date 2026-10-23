# s44-t4 — every valid connection on the starter is a route

**Status:** DONE

**In one paragraph:** Each valid connection on the starter is now its own route, and every one has to end in a goal. Two valid goals read VALID. A valid goal plus a route that runs off the plate reads INVALID, at that route's doorway. Removing the special case left dead state in the walk, and that exposed a false docstring from t2: "INVALID beats UNMEASURED" never held, because an unruled piece anywhere makes the course UNMEASURED before the walk runs. Corrected to say so. Colby then raised what this build can't see: routes can interact. Switches flip as marbles pass, so a later marble's route depends on the switch's starting direction and on marble order.

## Open (written before the work)

- **Goal:** Follow every valid connection on the starter as its own route, per Colby: "once you have two valid connections to the starter there are two pathways you have to measure."
- **Scope:** `traxgen/track_graph.py`, `tests/test_track_graph.py`.
- **Budget:** 15 minutes. No renders.
- **Done check:**
  1. *Step:* remove the starter's more-than-one-connection UNMEASURED case; the walk follows each valid connection.
  2. *True after:* (a) two valid goals on one starter read VALID; (b) one valid goal plus a connection whose route dead-ends reads INVALID at that route's doorway; (c) all earlier tests pass.
  3. *Miss cases:* the walk stops after the first route that ends in a goal, so (b) reads VALID.
  4. *Reads:* pytest and ruff output.
  5. *Check:* `uv run pytest -q` passes with tests for (a) and (b), where (b)'s dead-end route is the second one walked (sides are walked in order, so the goal is on the lower side); ruff clean.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** removed the starter's more-than-one-connection case and the walk state only it set. Fixed the `check_course` docstring. Added two tests. The mutant "walk only the first route" is killed (1 failing test of 20).
- **What changed:** `traxgen/track_graph.py`, `tests/test_track_graph.py`.
- **Evidence:** `task_check` in scope; suite `1122 passed, 1 deselected`; ruff clean.
- **Decisions made inside the task:**
  - UNMEASURED stays decided before the walk. Walking the measured routes first, so a known dead end can fail an otherwise-unmeasured course, waits until a course needs it.
- **For the record:**
  - `decisions.md`, graph-checker row: every valid connection on the starter is a route, and all must end in a goal (Colby, s44). Correct t2's "INVALID beats UNMEASURED": UNMEASURED is decided first.
  - `vision.md`, *The equation*, switches bullet (Colby, s44): routes can interact, not only cross. A switch flips as a marble passes, so the search state is (doorway, every switch's position). The switches' starting directions are an input to the check, and with several marbles their order matters: each runs on the switch states the last one left. When switches arrive, the walk's `done` memory must key on switch state too.
  - Supporting evidence for t3's "the half-hole misses rolled", checked after t3 closed: `screenshots/finish_record/results.json` gives each miss 9 frames. `watch_play_run` stops at 5 when the stop square never shows, so the stop square showed, and the marble ran.
- **Friction:** none.
- **Next:** the session close.
