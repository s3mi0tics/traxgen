# s42-t3 — the probe saves the phone's evidence when an attempt fails

**Status:** OPEN

**In one paragraph:** _written at close_

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

- **What happened:** _plain words_
- **What changed:** _files_
- **Evidence:** _task_check line, check output_
- **Decisions made inside the task:** _one sentence each_
- **For the record:** _what the close folds in_
- **Friction:** _quoted, with what the task did_
- **Next:** _next task_
