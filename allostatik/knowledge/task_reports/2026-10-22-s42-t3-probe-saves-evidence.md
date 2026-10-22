# s42-t3 — the probe saves the phone's evidence when an attempt fails

**Status:** DONE

**In one paragraph:** When a probe attempt fails, the probe now saves the phone's memory report and log at once, before the next attempt resets the app. The attempt's record names the file. If the save itself fails, the record says so and the run carries on. Checked offline with fakes in place of the phone; no renders.

## Open (written before the work)

- **Goal:** When a probe attempt raises, save the phone's memory report and log before the next attempt, so a failure like s42-t1's leaves something to read (Colby's note, 2026-10-22).
- **Scope:** `scripts/probe_finish_frames.py`.
- **Budget:** 20 minutes, no renders.
- **Done check:**
  1. *Step:* the per-attempt `except` calls `emulator.save_device_evidence` with the error as the reason, and the attempt's record carries the file's path; a failure to save is recorded, not raised.
  2. *True after:* a failed attempt leaves a file under `screenshots/device_evidence/` whose `why:` line names the error, and `frames.json` names that file.
  3. *Miss cases:* the save is called after the next attempt has already reset the app, so the log no longer shows the failure; the save itself raises and costs the other courses their runs; the path is saved but not written into the record.
  4. *Reads:* the probe's source, and the output of one offline call that stubs out `load_by_link` to raise and `save_device_evidence` to return a path.
  5. *Check:* the offline call's record holds `evidence` equal to the stub's path, with the stub called once per failed attempt and before the next attempt; a second run whose stub raises shows `evidence` naming the failure and the loop carrying on.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** Added `keep_evidence` to the probe, which calls `scripts.emulator.save_device_evidence` and never raises. The per-attempt `except` calls it and stores the path under `evidence`. Colby's note asked for this before the rerun, but it arrived after s42-t2 had already run clean.
- **What changed:** `scripts/probe_finish_frames.py`.
- **Evidence:**
  - `task_check`: in scope (the line is in the commit's terminal output).
  - `ruff`: all checks passed.
  - Offline check (scratchpad `t3_check.py`; fakes for `session`, `load_by_link` and `save_device_evidence`): with a saver that works, calls ran `load, save, load, save, load, save, load, save` and each record's `evidence` was the fake's path, exit 3. With a saver that raises, all four loads still ran and each record's `evidence` read `NOT saved: OSError: no fork`. Done check met.
- **Decisions made inside the task:** No unit test added. The probe is a one-off script with no test file, and the check above is recorded here instead.
- **For the record:** The probe's `frames.json` keeps only the last attempt's record, so a first attempt's evidence path appears only in the terminal. It was already like that; noted, not fixed.
- **Friction:** none.
- **Next:** t4, the finish detector, once Colby picks how to find the goal on screen.
