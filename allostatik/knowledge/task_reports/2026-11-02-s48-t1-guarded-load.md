# s48-t1 — one guarded load, for render_course and the probe

**Status:** FAILED — check (d) only: two tests in `tests/test_android_foreground.py`, outside the declared scope, used the main-menu picture as a rendered frame, which the load now refuses as near-white. s48-t2 declares that file and fixes them.

**In one paragraph:** The load steps now live once, in `android.load_course`, and both `render_course` and the probe's link load call it. It refuses the launcher (before the first action and after the capture), a loading screen, and the build tutorial, whatever reading the caller wants. Before this, the probe had its own copy with none of those checks, which is how it recorded the build tutorial as `inactive` in s47 (#68). One behaviour change: `render_course` now refuses a near-white frame even when no placement reading is asked for, so a finish-only render can no longer press play on a loading screen.

## Open (written before the work)

- **Goal:** the load steps (open or type the code, the two taps, the waits, the screencap) live in one function in `traxgen/android.py` that refuses a screen with no course on it, and both `render_course` and `probe_finish_frames`' link load call it.
- **Scope:** `traxgen/android.py`, `scripts/probe_finish_frames.py`, `tests/test_load_course.py` (new), `tests/test_probe_finish_frames.py`, `tests/test_refused_screens.py`, `tests/test_frame_guard.py`, `tests/test_render_finish.py`. The last three only if a guard's move changes what an existing test asserts.
- **Budget:** 90 minutes, no device.
- **Done check:**
  1. *Step:* extract the load into `load_course`; route both callers through it.
  2. *True after:* (a) `load_course` raises `RefusedScreenError` on the build-tutorial frame, `OracleFrameError` on a near-white frame, and `WrongForegroundAppError` with the launcher in front, whether or not the caller asked for a placement reading; (b) the probe's link load raises the same three, after leaving the editor for the refused screen; (c) the probe has no load steps of its own (no `open_share_link`, `load_track_button` or `loaded_track_hex` in `scripts/probe_finish_frames.py`); (d) the full suite passes.
  3. *Miss cases:* the probe still has its own copy that happens to call one guard; the near-white check still runs only when `detect_validity=True`; a test feeds the probe a frame no guard looks at and passes because nothing raised for an unrelated reason; a guard is tested on `render_course` only.
  4. *Reads:* `tests/test_load_course.py`'s six tests (three screens x two callers), the grep in (c), the pytest summary.
  5. *Check:* the six named tests pass and each fails when its guard is removed from `load_course` (one mutation per guard, run with `PYTHONDONTWRITEBYTECODE=1`), the grep in (c) prints nothing, and the suite summary reports 0 failed.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** `load_course` written; `render_course` calls it and still cleans up before re-raising a refused screen; the probe's `load_by_link` calls it and cleans up on a refused screen too. A shared `assert_not_near_white` replaces the oracle's inline check. Eight tests in `tests/test_load_course.py`: the three screens on each caller, plus a control on each.
- **What changed:** `traxgen/android.py`, `scripts/probe_finish_frames.py`, `tests/test_load_course.py` (new).
- **Evidence:**
  - `s48-t1: in scope -- 3 files changed since open commit a0c7067, all declared`.
  - Mutations, one per guard, `PYTHONDONTWRITEBYTECODE=1`: no refused-screen raise fails both tutorial tests; no near-white check fails both loading-screen tests; no opening foreground check fails the `load_course` launcher test; no closing foreground check fails the probe's launcher test. The first near-white run showed the probe's test survived through the oracle's own check, so the test now asserts the oracle is never reached.
  - Grep (c): no `open_share_link`, `load_track_button` or `loaded_track_hex` in the probe.
  - Full suite: `2 failed, 1189 passed` -- the two are `test_reset_first_establishes_state_then_verifies_it` and `test_reset_first_reports_the_menu_arrival_before_the_first_tap`, both feeding `MAIN_MENU_PNG` as the course frame.
  - ruff: one finding left in these files, `N818` at `android.py:175`, there before the task.
- **Decisions made inside the task:**
  - `load_course` raises all three; `render_course` catches only `RefusedScreenError`, to clean up first, as before. A near-white or launcher frame raises without cleanup, as before.
  - The near-white check moved from the placement reading into the load, so it runs on every load. The reading keeps its own copy through the shared helper, for callers that read a frame directly.
  - A load that lands back on the main menu is now refused (the menu is 68% near-white). That is correct, and it is what broke the two tests.
- **For the record:**
  - plan item 18: the probe's link load is covered (#68's fix); `load_course` is the one load path. Still open in item 18: the control hash, `inactive` on the control as a failure, and the "Load track" / "Track not found" dialogs, which no guard recognises.
  - observations: s47's "grep tests for exact-argv asserts before declaring scope" fired again in a new form -- grep tests for every fixture that feeds the changed path, not only argv asserts.
- **Friction:** the routine has no status for "work done, a test outside scope needs a fixture change". FAILED with the reason, then a task that declares the file, is what this did.
- **Next:** s48-t2, the two fixtures in `tests/test_android_foreground.py`.
