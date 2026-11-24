# s52-t4 — where each trail ends, read from the last frame (item 24 (b))

**Status:** DONE

**In one paragraph:** `scripts/read_trail_ends.py` reads, for each launch pad of a standard-square course, where its trails end on the last frame and how far each end is from the nearest goal. On the runs whose layout is on disk it agrees with what is known: OGIVHBFRK7 run 2, six trails, all in goals (3 to 35 px); DLYQPCH46H, finished, 31 px; 8B3RSYR8XW, marble held in the switch, 60 px, not in goal. On OGIVHBFRK7 run 1, which the sparkle count called not finished with frames 2 s apart, it finds four of the six trails, all four in goals -- the disagreement item 24 (b) exists to flag. On the curve ring board (TKLKNFJGT3) the rings with no trail are rotations 0 and 4, whose marbles enter by sides 5 and 1, the curve's two closed sides (D097), and the other four end in goals; one of them is claimed by two pads, so close pads double-count. The in-goal cut (45 px) is fitted to these same runs.

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

## Close

- **What happened:** prototype in the scratchpad before the open (recorded in the open half), then the script and four synthetic tests. The first attempt seeded from the pad's own pixels and found nothing: the launch pad's raised top hides each trail's first stretch, so a trail now belongs to a pad when any of its pixels is within 140 px of the pad's centre (the overlay of `screen_position` on `OGIVHBFRK7/run_2`'s last frame put every pad and goal on its piece).
- **What changed:** `scripts/read_trail_ends.py`, `tests/test_read_trail_ends.py`.
- **Evidence:** `uv run pytest -q tests/test_read_trail_ends.py` 4 passed; full suite 1242 passed, 1 deselected; ruff clean on both files. Readings:

  | run | sparkle verdict | trails, end to nearest goal |
  |---|---|---|
  | OGIVHBFRK7/run_2 | finished (167) | 6.3, 22.9, 3.4, 24.2, 35.2, 30.8 px -- all in goal |
  | OGIVHBFRK7/run_1 | not finished (0, frames 2.06 s apart) | 11.2, 24.3, 5.1, 32.2 px -- 4 of 6 found, all in goal |
  | DLYQPCH46H/run_4 | finished (32) | 30.8 px, in goal |
  | 8B3RSYR8XW | not finished (0) | 59.9 px, not in goal (held in the switch) |
  | TKLKNFJGT3 (curve ring board) | finished (102) | rot0 none, rot1 61.4 and 33.3, rot2 22.9, rot3 13.4, rot4 none, rot5 13.3 |

- **Decisions made inside the task:** a script, not a library module, until a check depends on it; the cut at 45 px, between the largest in-goal end seen (35.2) and the held marble (59.9), named in the code as fitted and untested elsewhere.
- **For the record:**
  - `plan.md` item 24 (b): built offline as `scripts/read_trail_ends.py` (s52-t4). On the four standard-square runs with known layouts it matches every known outcome, and on `OGIVHBFRK7/run_1` it reads 4 of 6 trails in goals where the sparkle count read not finished. Limits: standard square only; close pads (two cells) claim each other's trails; two of run 1's six trails were not found; the cut is fitted, not tested. Next: run it beside `judge_finish` on the next live batch, and treat a disagreement as UNJUDGED.
  - `plan.md` *What is true now*: a trail's first stretch is hidden under the launch pad's top, so trails are found near a pad, not on it.
- **Friction:** zsh does not word-split `$a` in a `for` loop, so `set -- $a` passed one argument; the batch ran under `bash -c`.
- **Next:** live work if the Mac has memory; otherwise s52-t5.
