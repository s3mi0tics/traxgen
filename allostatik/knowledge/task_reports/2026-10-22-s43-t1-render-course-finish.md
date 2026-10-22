# s43-t1 — render_course loads by link and reads the finish

**Status:** DONE

**In one paragraph:** `render_course` can now open a course from its share link and, when asked, press play and say whether the marble finished, next to the placement reading. `scripts/render_course.py` loads by link by default and prints both readings. Live, `KN6F459ZR3` read `active` and `finished` three times in three renders by link, and its render is byte-identical to the control frame, so a link load draws the same picture as a typed one. A three-lens review found a failure path that skipped cleanup, a watch that could end before the run started, and nine weak spots in the tests. All are fixed. The library's default stays on the typed route, so the campaign scripts don't change route without a live sweep on links.

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

## Close

- **What happened:**
  - Moved the link load and the play-watch from the probe into `android.py` (`open_share_link`, `watch_play_run`).
  - Wired them into `render_course` behind `by_link` and `detect_finish`, and added `finish` to `RenderResult`.
  - The CLI gained `--detect-finish` and `--typed`, and loads by link by default.
  - One live render passed. Then a three-lens panel ran (epistemics, design, mutation), its findings were fixed, and a second live session rendered twice in one boot, the second time without a reset.
- **What changed:** `traxgen/android.py`, `scripts/render_course.py`, `scripts/probe_finish_frames.py` (uses `open_share_link`; its typed branch passes `by_link=False`), and `tests/test_render_finish.py` (new, 21 tests).
- **Evidence:**
  - `task_check`: in scope, 4 files.
  - Suite: `1094 passed, 1 deselected`.
  - Live 1: `render_course KN6F459ZR3 --fresh --detect-validity --detect-finish` gave `play button: active` and `finish: finished (peak 1063, 8 frames, sparkle burst)`. Boot 22.5 s, menu after 44.1 s. The screenshot's md5 is `6a0e12a33937ef1d1366ab6843e6c9f6`, the control hash.
  - Live 2, one boot:
    - First launch died before the main menu (#21; menu wait timed out, 2 of 30 frames unreadable; evidence `screenshots/device_evidence/20261022-154223.txt`).
    - The next boot's runs: run 1 (reset) active, finished, peak 1104, 13 frames. Run 2 (no reset, straight after run 1's cleanup) active, finished, peak 1228, 13 frames.
  - Declared outcome (`KN6F459ZR3`: active, finished, peak above 30): met all three times.
- **Decisions made inside the task:**
  - The panel ran once, on the finish check and its wiring together (Colby: yes at the open).
  - The library's `by_link` defaults to False; the CLI defaults to the link. Sweeps pass `expect_disclaimer` and don't reset between renders, so a silent switch would have put them on a route never run that way live (design lens).
  - A failure during the play run runs cleanup, then re-raises, as a refused screen does.
  - A watch that ends with the stop square still up taps stop before cleanup.
  - Quiet frames count only after the stop square has shown. A run whose square never shows ends after 5 frames (`PLAY_START_FRAMES`) as UNJUDGED.
  - Play is pressed whatever the placement reading says, since the two readings are separate (#57).
  - All frames stay in memory, up to 150 (design lens's low finding, not fixed).
- **For the record:**
  - `plan.md` *What is true now*: `render_course` reads the finish (`detect_finish=True`, CLI `--detect-finish`), and loading by link is in it (`by_link=True`, the CLI default). A link load renders the control byte-identically (`6a0e12a3...`).
  - `plan.md` order step (1): done. Item 16: `render_course` still writes no sidecar, and `finish` is now one more field a sidecar should carry.
  - New fact: after `render_course`'s cleanup the screen is not the main-menu signature (distance 24.9 and 24.96 against the threshold of 10), yet a link load from there works. Whether this was always true of cleanup is unmeasured. Typed campaigns have rendered after cleanup without a reset for months, so it is probably not new.
  - #21, one more firing: the first launch after a cold boot died in 1 of the 2 sessions here.
  - D093's and the code's sampling note: s42-t4's frames were a 1 s sleep plus the capture, about 1.5 s a frame on disk, not "one frame a second" (epistemics lens). Correct D093's wording at the close.
  - Candidate observation: the done check named a stderr line (the `am start` link line) that the code never printed, so its live half could not be read as written; the epistemics lens caught it. *How to apply:* before declaring a check on output, name a line the code already prints, or add it in the task.
- **Friction:** the done check's slot 5 named an output nobody prints. The CLI now prints `rendering <code> via emulator, opened by share link...`, which reports what the CLI asked for. That the library honours it is proven by the offline tests, not by stderr.
- **Next:** s43-t2: build, upload and render a course for each of the record's 20 live cells, with the finish check, and write the results into a new per-cell table in `graph.py`.
