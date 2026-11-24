# s52-t2 — does a frame that catches only the burst's tail still read as a finish? (item 23's leftover, item 24's sampling worry)

**Status:** DONE

**In one paragraph:** Five runs on disk are real finishes, and in every one the burst is in at most two frames, always the last one or two frames that still show the stop square; the frame after it has 0 sparkles. So the burst is the end of the run, lasting roughly one to two seconds, and there is no slow tail to catch: a frame either lands in it or sees nothing. Frames 1 or 1.5 s apart caught every finish at every phase; 2 s missed 1 of 9 phases, 2.5 s missed 5 of 13. The prediction held. Four runs whose `frames.json` still says `finished` (54TI3KWGTH, 8D9CU5AEY3, 8WL7RXS9H4, Q7AE2SM7MC) were labelled under the old pixel rule; by sparkles they peak at 0 to 2 and are s48's switch boards, so their saved labels are stale.

## Open (written before the work)

- **Goal:** from the finishing runs on disk, measure how many sparkles each frame after play carries, and say how often frames 1 s and 2 s apart would miss every frame with 6 or more.
- **Scope:** none beyond the ledger and this report; the analysis script stays in the session scratchpad and is quoted here.
- **Budget:** 25 minutes, no renders.
- **Done check:**
  1. *Step:* run `new_sparkles(before, frame)` over every frame of every run on disk whose `frames.json` says `finished`, plus `OGIVHBFRK7/run_1` (read not finished at 2.06 s spacing with all six trails in goals).
  2. *True after:* a per-frame sparkle profile for each finishing run, the number of frames at or above 6 in each, and a miss rate for evenly spaced subsamples at 1 s and 2 s.
  3. *Miss cases:* a profile computed with a different counter than `judge_finish` uses; subsamples that always include frame 0 or the peak frame; frame times assumed without saying so.
  4. *Reads:* `screenshots/finish_frames/*/frames.json`, `before.png`, `after_NN.png`; `traxgen.android.new_sparkles` at HEAD.
  5. *Check:* the report lists every finishing run with its per-frame counts, says frame times are `i x seconds/(frames-1)` (no per-frame clock is saved), and gives each miss rate over every phase offset.
- **Outcomes declared before any live run:** none, because there is no live run. Prediction, declared before counting: frames at or above 6 come in runs of one or two per finish, so 2 s spacing misses some finishes and 1 s spacing misses few.

## Close

- **What happened:** `new_sparkles(before, after_NN)` over every frame of the 9 runs whose `frames.json` says `finished`, plus `OGIVHBFRK7/run_1`. Frame times are `i x seconds/(frames-1)`; no per-frame clock is saved. Per-frame counts (S = stop square showing):

  | run | spacing | sparkles per frame | stop square | frames >= 6 |
  |---|---|---|---|---|
  | DLYQPCH46H/run_4 | 0.98 s | 0 0 1 22 32 0 0 0 0 0 | SSSSSS.... | 2 |
  | KN6F459ZR3 | 0.70 s | 0 0 1 1 0 16 33 0 0 0 0 | SSSSSSSS... | 2 |
  | OGIVHBFRK7/run_2 | 1.03 s | 0 0 2 1 56 167 0 0 0 0 | SSSSSS.... | 2 |
  | THIIEUH35Z | 1.50 s | 0 0 0 0 0 0 0 18 0 0 0 0 | SSSSSSSS.... | 1 |
  | TKLKNFJGT3 | 1.43 s | 0 0 0 102 0 0 0 0 | SSSS.... | 1 |
  | OGIVHBFRK7/run_1 | 2.55 s | 0 0 0 0 0 | SSS.. | 0 (all six trails in goals, s50) |
  | 54TI3KWGTH | 0.83 s | 1 x18, then 0 | | 0 (stale label) |
  | 8D9CU5AEY3 | 1.44 s | all 0 | | 0 (stale label) |
  | 8WL7RXS9H4 | 0.95 s | all 0 | | 0 (stale label) |
  | Q7AE2SM7MC | 1.51 s | 1 2 2 2 2 2 0 0 0 0 | | 0 (stale label) |

  Burst frames counted back from the last stop-square frame: -2,-1; -2,-1; -1,0; 0; 0. Subsampling every k-th frame (k = round(spacing / run's dt)) over every phase offset: 1.0 s 0/5 missed, 1.5 s 0/7, 2.0 s 1/9 (KN6F459ZR3, one of three phases), 2.5 s 5/13. The two 1.5 s-spaced runs are step 1 at 1.0 to 2.0 s by construction, so the 2 s figure understates misses; the 2.5 s run on disk (`OGIVHBFRK7/run_1`) missed outright.
- **What changed:** this report and the ledger only; the script is `scratchpad/burst_profile.py` and the inline subsampler, not committed.
- **Evidence:** the table above; `uv run python <scratchpad>/burst_profile.py`.
- **Decisions made inside the task:** treat the four stale-labelled runs as non-finishes from their sparkle counts, not their saved labels, since D105 superseded the pixel rule they were labelled by.
- **For the record:**
  - `plan.md` item 23: its "Left" is answered -- there is no tail to catch; the burst is in the last one or two stop-square frames and the next frame is empty (s52-t2). Item 23 can close.
  - `plan.md` item 24: the sampling worry is now a number. A `not_finished` is evidence when frames were 1.5 s apart or closer (0 of 12 phases missed); at 2 s about 1 in 9 finishes is missed, and at 2.5 s about 2 in 5. Proposed, not built (it changes the harness, Colby's call): `judge_finish` returns UNJUDGED rather than NOT_FINISHED when the gap between the last stop-square frame and the first clear frame exceeds 1.5 s. That needs per-frame capture times, which `probe_finish_frames` does not save today.
  - `observations.md` candidate: saved verdicts outlive the rule that made them -- four `frames.json` files still say `finished` under the pixel rule D105 replaced. Re-judge saved runs when a judging rule changes, or stamp each saved verdict with the rule that made it.
- **Friction:** none.
- **Next:** s52-t3, the trail-end reading and the red hexagon (item 24 (b), (c); #30), from frames on disk.
