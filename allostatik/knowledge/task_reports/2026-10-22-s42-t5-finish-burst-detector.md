# s42-t5 — the finish check reads the app's sparkle burst

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Build item 19's finish check on the sparkle burst s42-t4 found (Colby: "yeah lets keep going", 2026-10-22). It's a pure judgement in `traxgen/android.py` with three outcomes, tested offline, and the probe uses it with frames captured back to back.
- **Scope:** `traxgen/android.py`, `tests/test_finish_burst.py` (new), `scripts/probe_finish_frames.py`.
- **Budget:** 90 minutes, 1 emulator session (about 5 runs).
- **Done check:**
  1. *Step:* `judge_finish(before, frames)` returns FINISHED, NOT_FINISHED or UNJUDGED with the peak count. The probe captures without the 1 s sleep and records the judgement.
  2. *True after:* (a) every labelled run on disk is judged as labelled; (b) a run whose stop square never showed, or never cleared, is UNJUDGED, never NOT_FINISHED; (c) the live session's judgements match the labels.
  3. *Miss cases:*
     - The threshold sits right on the data, so it passes today's runs by luck. The report states the margin both ways.
     - Stale frames past `frames.json`'s count get read (the s42-t4 hazard). The probe now clears the folder first, and the offline check reads only the counted frames.
     - A run that never played is called a miss.
     - The live session repeats the labelled runs' sampling, so the faster capture is never tested.
  4. *Reads:* the saved runs' frames and `frames.json` (labels as in s42-t2 and t4); the test suite's output; the live session's `frames.json`, including the capture interval it measured.
  5. *Check:* the suite passes. The offline check prints each labelled run's peak and judgement, all matching their labels. The live runs' judgements match their labels, and their median capture interval is under 1.5 s.
- **Outcomes declared before any live run:**
  - `THIIEUH35Z` (finish; 62 at 1 Hz): FINISHED with a peak above 200, since faster frames should catch the burst at its height.
  - `KN6F459ZR3`: FINISHED.
  - `W8IEN7MG92` (rim stop): NOT_FINISHED.
  - `I4BA3N5V6Y`: NOT_FINISHED.
  - A FINISHED reading on any miss or rim stop, or a peak under the threshold on a finish, means the burst isn't the clean signal t4 suggested, and the task stops.

## Close

- **What happened:** _plain words_
- **What changed:** _files_
- **Evidence:** _task_check line, test summary, run lines_
- **Decisions made inside the task:** _one sentence each_
- **For the record:** _what the close folds in_
- **Friction:** _quoted, with what the task did_
- **Next:** _next task_
