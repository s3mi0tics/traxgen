# s42-t5 — the finish check reads the app's sparkle burst

**Status:** DONE

**In one paragraph:** The harness can now tell whether the marble finished. `judge_finish` reads the app's sparkle burst. Its three answers are finished, not finished, and can't judge (play never ran, or the run hadn't ended). It judges all 15 labelled runs on disk as labelled. In one live session with frames taken back to back, it judged all four codes as labelled. The Phase 1 course `KN6F459ZR3` finished, with a peak of 1,115 against a threshold of 30, so Phase 1's clause (4) is now measured, not read off the placement button. Faster frames caught `THIIEUH35Z`'s burst at 581, where the old sampling caught only its 62-pixel tail. It's measured on the goal rail only.

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

- **What happened:** Added the finish check to `traxgen/android.py` and tests for it. The probe now captures with no sleep, clears old frames, and records the judgement and the median time between frames. One `--fresh` session (boot 24.6 s), four codes by link, each attempt 1.
- **What changed:** `traxgen/android.py` (new section *Finish check*: `FINISH_BURST_MIN_PIXELS = 30`, `FINISH_BURST_BOARD`, `STOP_SQUARE_CORNER`, `button_shows_stop`, `new_white_pixels`, `FinishStatus`, `FinishReading`, `judge_finish`); `tests/test_finish_burst.py` (new); `scripts/probe_finish_frames.py` (uses the library's stop reading and `judge_finish`, `INTERVAL` 0, clears `after_*.png` first, records `finish`, `finish_peak`, `finish_reason`, `median_interval`).
- **Evidence:**
  - `task_check`: in scope.
  - Suite: `1073 passed, 1 deselected`. `tests/test_finish_burst.py`: 9 synthetic tests plus 15 labelled-run tests, all pass.
  - Offline peaks:
    - Finish: `KN6F459ZR3` (s42-t4) 1176, `KN6F459ZR3_s41` 830, PROBOOK12 1000, `THIIEUH35Z` (s41) 62.
    - Not finished: rim 11; misses 7-11; no-goal `STXT6WF9VB` 10.
    - Unjudged: `4DLUQKGRKN`, 0 (the stop square never showed).
  - Live (finish, peak, median interval, frames, stop squares):
    - `THIIEUH35Z`: finished, 581, 1.25 s, 12 frames, `SSSSSSSS....`
    - `KN6F459ZR3`: finished, 1115, 0.47 s, 11 frames, `SSSSSSSS...`
    - `W8IEN7MG92`: not finished, 10, 0.77 s, 11 frames, `SSSSSSSSSS.`
    - `I4BA3N5V6Y`: not finished, 8, 0.81 s, 14 frames, `SSSSSSSSSS....`
  - All placement readings `active`.
  - Declared outcomes: all met (`THIIEUH35Z` above 200; the others as labelled).
  - Done check: met. Every median interval is under 1.5 s. Margin at the threshold: highest non-finish ever 11, lowest finish at the new sampling 581 (62 at the old).
- **Decisions made inside the task:**
  - Threshold 30, set before the live run from the s42-t4 data, and not moved after it.
  - The board area excludes x < 200 and y >= 880 (the back icon and toolbar).
  - A run that never played, or hadn't ended, is UNJUDGED, never a miss.
  - The judgement is a pure function over PNG bytes, so it can be tested without a device. It is not yet wired into `render_course`; that needs loading by link there first (plan order, step 3).
- **For the record:**
  - `plan.md` *What is true now*: the harness checks the finish by the app's sparkle burst (`traxgen.android.judge_finish`). The Phase 1 course `KN6F459ZR3` **finished** (2026-10-22, peak 1,115 vs threshold 30), so Phase 1's clause (4) is measured, the first time any course's finish has been.
  - Item 19: the detector exists. Left: wiring it into `render_course` with loading by link, and measuring the other three goal pieces.
  - D092, reworded at the close: a finish is the app's finish burst. It agrees with Colby's trail rule on all 15 labelled runs.
  - `MEASURED_RUNS`: its rows are still placement claims. Which ones finish is now cheap to measure, one run each.
- **Friction:** none.
- **Next:** the close (s42 has run long), or loading by link in `render_course` with `judge_finish` wired in, Colby's call.
