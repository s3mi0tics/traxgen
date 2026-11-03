# s49-t1 — the finish check counts sparkles, not white pixels

**Status:** DONE

**In one paragraph:** The finish check now counts sparkles instead of white pixels. The app's finish burst is dozens of small round dots; a switch's lever, when it swings, uncovers a few thin streaks of white plastic. Counted as separate spots of the right size and shape, finishes on disk peak at 18 to 102 sparkles, and the five goal-less switch boards at 0 to 2, with a threshold of 6. All five switch boards now read not finished, and every run labelled before reads as it did. Timing could not have done it: on `8WL7RXS9H4` the lever's white lasts one frame, as a burst does, because the second marble swings it back.

## Open (written before the work)

- **Goal:** `judge_finish` decides a finish by how many separate sparkle-sized white spots appear after play, so a switch's lever, which uncovers a few large streaks of white plastic, no longer reads as a finish (plan item 23).
- **Scope:** `traxgen/android.py`, `tests/test_finish_burst.py`, `tests/test_render_finish.py`, `tests/test_probe_finish_frames.py`, `scripts/render_course.py`, `scripts/probe_finish_frames.py`, `scripts/finish_record.py`. Grepped first for every test and script that builds or reads a finish reading (#69): `test_finish_record.py` reads only `graph.MEASURED_FINISHES`' recorded peaks, which this does not change.
- **Budget:** 60 minutes; no device.
- **Measured before the open** (read-only, on the frames on disk; scratch script): new near-white pixels split into 8-connected spots; a *sparkle* is a spot of 15 to 80 px, at least half its bounding box, no more than 2:1. Most sparkles in any frame after play: finishes `KN6F459ZR3` 33, `KN6F459ZR3_s41` 24, `PROBOOK12` 30, `THIIEUH35Z` 18, `TKLKNFJGT3` (30 goals) 102; every miss, no-goal run and switch board 0, except `Q7AE2SM7MC` 2 and `54TI3KWGTH` 1. The lever's white is 3 to 5 spots of 100 to 330 px, thin streaks. Timing alone fails: `8WL7RXS9H4` is white for one frame only (`[432, 0, ...]`), as a burst is, because the second marble swings the lever back.
- **Done check:**
  1. *Step:* add a sparkle count to `android.py` (Pillow only, no new dependency), judge the finish on its peak with a threshold of 6, keep `peak_new_white` reported beside it; label the s48 switch boards and the other runs on disk in `test_finish_burst.py`; synthetic frames draw separate dots.
  2. *True after:* `judge_finish` reads `Q7AE2SM7MC`, `54TI3KWGTH`, `ZJR47DUFFX`, `8D9CU5AEY3`, `8WL7RXS9H4` as not finished, and every run labelled before as it was.
  3. *Miss cases:* the labelled-run tests skip because the frames are missing, and pass vacuously; the synthetic tests pass because the dot helper and the rule share a bug (both count blocks); a lever streak broken into small pieces counts as sparkles on some frame not on disk.
  4. *Reads:* `tests/test_finish_burst.py`'s labelled runs against `screenshots/finish_frames/`; the full suite's summary line.
  5. *Check:* `uv run pytest tests/test_finish_burst.py -v` shows every labelled run, the five switch boards included, as PASSED (not SKIPPED), and the full suite passes; a mutant that judges on pixels again fails at least one switch-board test.
- **Outcomes declared before any live run:** none, there is no live run.

## Close

- **What happened:** measured first, read-only, on every run on disk (see *Open*), then built the rule to match. `android.new_sparkles` and `_count_sparkles` (Pillow and the standard library, no new dependency) split the new white into 8-connected spots and count those of 15 to 80 px, at least half their bounding box, at most 2:1. `judge_finish` decides on the peak sparkle count (`FINISH_SPARKLES_MIN = 6`); `FinishReading` gains `peak_sparkles`, and `peak_new_white` is still reported. The render CLI prints both; the probe's `frames.json` and `finish_record`'s sidecar gain `finish_sparkles`.
- **What changed:** `traxgen/android.py`, `tests/test_finish_burst.py`, `tests/test_render_finish.py`, `scripts/render_course.py`, `scripts/probe_finish_frames.py`, `scripts/finish_record.py`.
- **Evidence:**
  - `s49-t1: in scope -- 6 files changed since open commit 9bc28d0, all declared`.
  - Full suite: 1226 passed, 1 deselected (was 1208).
  - `tests/test_finish_burst.py -v`: 24 labelled runs PASSED, 0 SKIPPED. New labels: the five switch boards (not finished), `TKLKNFJGT3` (finished, 102 sparkles), `5H5NQ7HT7D/run_1`, `run_2`, `YFUGDSMDUH/run_1` (not finished).
  - Peak sparkles from the Pillow count equal the scratch scipy count on all ten runs compared: 33, 24, 30, 18, 102; 2, 1, 0, 0, 0.
  - Mutants, run with `PYTHONDONTWRITEBYTECODE=1`: judging on pixels again fails 8 tests (four switch boards among them); dropping the shape filter fails 10 (the lever streak, the solid block, and the switch boards).
  - ruff: clean on every changed file except `android.py`'s `N818` on `UiConditionTimeout`, which predates this change.
- **Decisions made inside the task:**
  - Kept `FINISH_BURST_MIN_PIXELS` and `peak_new_white`, reported only, so the recorded peaks in `graph.MEASURED_FINISHES` and old `frames.json` files still mean what they said.
  - Threshold 6, the geometric middle between the highest non-finish (2) and the lowest finish on disk (18).
  - Dropped `ZJR47DUFFX` from the "pixels would have fooled it" test: its saved run adds no white, so it is labelled but can't show the lever.
- **For the record:**
  - D093 amended (D-row candidate): a finish is a burst of at least 6 sparkles in some frame after play; the white-pixel count is reported, not judged on. Why: the lever adds 432 to 976 white pixels and at most 2 sparkles.
  - Item 23: the offline half is done. Left: one live run of a course with a switch that reaches a goal, read as finished (s49-t2).
  - #66 (third reading): the fix is shape, not place. Counting only near a goal would have failed the 30-goal board, whose burst rises over the middle of the board.
  - Untested risk: a frame that catches only the burst's tail. The 62-pixel tail run (THIIEUH35Z, 1 s sampling) was overwritten in s42-t5, so whether a tail still shows 6 sparkles is unknown. Frames are captured back to back now, which makes it less likely.
- **Friction:** none in the routine. Measuring before declaring the threshold is what #63 asked for, and it changed the design: timing, the handoff's second idea, fails on `8WL7RXS9H4`.
- **Next:** s49-t2, a live course with a launch pad, a switch and a goal, read as finished.
