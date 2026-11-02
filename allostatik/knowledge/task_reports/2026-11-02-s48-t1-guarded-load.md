# s48-t1 — one guarded load, for render_course and the probe

**Status:** OPEN

**In one paragraph:** _written at close_

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
