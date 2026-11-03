# s49-t2 — a launch pad, a switch and a goal, played live and read by the sparkle count

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** play one course whose only route runs launch pad -> switch -> goal rail, which `track_graph.check_course` calls VALID, and confirm s49-t1's finish check reads it as finished; play its twin, which swaps in the other switch kind so the checker calls it a dead end, as the miss beside it.
- **Scope:** none in the repo. The builder is a scratch script (tiles below); frames go to `screenshots/finish_frames/` (gitignored).
- **Budget:** 2 uploads; at most 2 probe sessions; 30 minutes of device time.
- **The two courses** (standard square, world cells (y, x), rotation), found by searching every rotation around the pad for VALID courses whose goal is not reachable with the switch removed:
  - **A:** `STARTER` (-3, 2) r0, `SWITCH_LEFT` (-3, 3) r3, `GOAL_RAIL` (-2, 3) r0. Checker: VALID. With the switch removed: not VALID.
  - **B (twin):** the same, with `SWITCH_RIGHT` at (-3, 3) r3. Checker: INVALID, "SWITCH_RIGHT has no way on" (the marble is held).
- **Done check:**
  1. *Step:* build and upload A and B; play both by link in one probe session (`probe_finish_frames --link A B`); judge each run from its `frames.json`.
  2. *True after:* a run of a VALID switch course that settled, with frames on disk, read FINISHED by `judge_finish`; and its twin, read NOT_FINISHED.
  3. *Miss cases:* A reads finished from a lever's white (it can't now, but only the sparkle peak shows that); A finishes by a route that skips the switch (the search excluded it; the trail shows it); the load lands on a courseless screen; the run never settles and is UNJUDGED.
  4. *Reads:* each code's `frames.json` (`finish`, `finish_sparkles`, `finish_peak`, `settled`, error); `before.png` and the last frame, looked at.
  5. *Check:* A's `frames.json` says `finished` with `finish_sparkles` >= 6 and `settled` true, and its last frame shows a trail through the switch into the goal rail; B's says `not_finished` with `finish_sparkles` <= 2.
- **Outcomes declared before any live run:**
  - A: a marble loads, passes the switch, and finishes on the goal rail. Read FINISHED, peak sparkles in the finishes' range (18 to 102), and the lever has swung in the last frame.
  - B: a marble loads and stops against the switch's lever. NOT_FINISHED, sparkles 0 to 2.
  - If A does not finish, either the switch rule in `track_graph` or the goal rail's placement beside a switch is wrong, and the frames say which. That would be a finding about D103/D104, not about the finish check, unless the trail ends in the goal and the reading still says not finished.
  - If B finishes, the switch rule is wrong (D103).
