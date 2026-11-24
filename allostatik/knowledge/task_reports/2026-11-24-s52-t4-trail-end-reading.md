# s52-t4 — where each trail ends, read from the last frame (item 24 (b))

**Status:** OPEN

## Open (written before the work)

- **Goal:** a committed offline reader that says, for each launch pad on a standard-square course, where its trails end and how far each end is from the nearest goal, run over the runs on disk whose layout is known.
- **Scope:** `scripts/read_trail_ends.py` (new), `tests/test_read_trail_ends.py` (new). No library module: the reader stays a script until a check depends on it.
- **Budget:** 35 minutes, no renders.
- **Done check:**
  1. *Step:* the reader, a synthetic test, and a run over OGIVHBFRK7 runs 1 and 2, DLYQPCH46H/run_4 and 8B3RSYR8XW.
  2. *True after:* each of those runs has, per trail, its end pixel, the nearest goal cell and the distance; the synthetic test passes; the script is committed.
  3. *Miss cases:* the test passes on a mask that has no trail near the pad (reader returns nothing and the test does not notice); a trail from a neighbouring pad is attributed to this one and the report does not say so; the in-goal cut is fitted to the same four runs it is then reported against without saying so.
  4. *Reads:* `screenshots/finish_frames/<code>/{before,after_NN}.png`, `screenshots/ring_board/two_marbles_run2.json`, `s49_switch_goal.json`, `CURVE.json`; `ring_board.screen_position` at HEAD.
  5. *Check:* `uv run pytest tests/test_read_trail_ends.py` passes, including a case with no trail near the pad that must return `no trail`, and the report prints the distances for every trail of the four runs and names the cut as fitted to them.
- **Outcomes declared before any live run:** none, because there is no live run. (The prototype ran in the scratchpad before this open: OGIVHBFRK7/run_2 six ends at 3-35 px, run_1 four at 5-32, DLYQPCH46H 31, 8B3RSYR8XW 60.)
