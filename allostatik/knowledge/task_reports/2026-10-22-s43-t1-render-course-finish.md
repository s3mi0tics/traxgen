# s43-t1 — render_course loads by link and reads the finish

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** `render_course` opens a course by share link (the typed route kept as an option), and, when asked, presses play and returns `judge_finish`'s reading next to the placement reading; `scripts/render_course.py` prints both.
- **Scope:** `traxgen/android.py`, `scripts/render_course.py`, `scripts/probe_finish_frames.py`, `tests/test_render_finish.py` (new), `tests/test_android_foreground.py`, `tests/test_refused_screens.py`, `tests/test_render_course_script.py`.
- **Budget:** 90 minutes; 1 emulator session, at most 3 renders.
- **Done check:**
  1. *Step:* move the probe's link load and play-watch into `android.py`; wire them into `render_course` behind `by_link` (default on) and `detect_finish` (default off); add `finish` to `RenderResult`; the CLI gains `--detect-finish` and `--typed`.
  2. *True after:* (a) the default route sends `am start ... VIEW -d <link> <package>` and types nothing; (b) `--typed` keeps the old tap-and-type route; (c) with `detect_finish`, play is pressed only after the closing foreground check and the refused-screen check pass, the app is re-checked before cleanup, and the result carries a `FinishReading`; (d) without it, no play tap happens and `finish` is `None`; (e) a live `--fresh --detect-validity --detect-finish` run on `KN6F459ZR3` prints `play button: active` and `finish: finished`.
  3. *Miss cases:* the link route still taps the code field (both routes ran); play is pressed on a refused screen; the play frames are judged against a "before" frame taken before the course loaded; a run that never played comes back NOT_FINISHED instead of UNJUDGED; the fakes only ever serve one frame, so the watch loop's exit is never exercised; the live run passes on the typed route because the flag didn't reach the library.
  4. *Reads:* the suite's output; the fake adb's recorded calls in the new tests; the live run's stderr.
  5. *Check:* the suite passes with new tests that assert the recorded calls for (a)-(d), and the live run's stderr shows the `am start` link line and `finish: finished` for `KN6F459ZR3`.
- **Outcomes declared before any live run:** `KN6F459ZR3` by link: placement `active`, finish `finished`, peak above 30. Anything else stops the task.
