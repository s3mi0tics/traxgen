# s52-t2 — does a frame that catches only the burst's tail still read as a finish? (item 23's leftover, item 24's sampling worry)

**Status:** OPEN

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
