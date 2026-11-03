# s49-t3 — course A after a warm-up load

**Status:** FAILED — the app never reached the main menu in four attempts, so neither course loaded; A stays unmeasured

**In one paragraph:** The warm-up didn't happen. In one cold boot, all four attempts (B twice, then A twice) timed out waiting for the main menu after 90 s, with the app in front. B's last frame was 22 from the menu signature, A's 124 to 127, a very different screen. No frame of it was saved. The phone log shows Google services ANR-killed during start-up again, as in both s49-t2 boots. So course A, the VALID switch course, is still unmeasured, and the cause is the device, not the course.

## Open (written before the work)

- **Goal:** answer to s49-t2's stop (Colby: "1"): play B `8B3RSYR8XW` first as a warm-up, then A `DLYQPCH46H`, in one probe session, and read A with the sparkle count.
- **Scope:** none in the repo; frames to `screenshots/finish_frames/` (gitignored).
- **Budget:** 1 probe session, about 5 minutes of device time; no uploads.
- **Done check:**
  1. *Step:* `probe_finish_frames --link 8B3RSYR8XW DLYQPCH46H`.
  2. *True after:* a settled run of A, frames on disk, read by `judge_finish`.
  3. *Miss cases:* A fails to load again (then A stays unmeasured and the session closes with B's half); A reads finished on a route that skips the switch (the last frame shows it); the run never settles.
  4. *Reads:* A's newest `frames.json` (`finish`, `finish_sparkles`, `finish_peak`, `settled`, error); A's last frame, looked at.
  5. *Check:* A's `frames.json` has no error, `settled` true, and `finish: finished` with `finish_sparkles` >= 6; the last frame shows a trail through the switch into the goal rail.
- **Outcomes declared before any live run:** as s49-t2 declared for A: it loads, passes the switch, finishes on the goal rail; FINISHED with peak sparkles in 18 to 102; the lever swung in the last frame. B again holds at the lever, 0 to 2 sparkles. If A loads and does not finish, the frames say whether the switch rule or the goal beside the switch is wrong.

## Close

- **What happened:** one session, `--link 8B3RSYR8XW DLYQPCH46H`. Boot and device checks passed. B attempts 1 and 2: `UiConditionTimeout` at the main-menu wait, 90 s, last distance 22.035. A attempts 1 and 2: the same, last distances 123.982 and 126.791. Emulator down at the end (`PASS emulator_down`).
- **What changed:** nothing in the repo. `screenshots/finish_frames/8B3RSYR8XW/run_1/frames.json` and `DLYQPCH46H/run_2/frames.json` hold the errors; no frames.
- **Evidence:** phone evidence `screenshots/device_evidence/20261102-164355.txt` to `-164955.txt`: `ANR in com.google.android.as` and `com.google.android.gms`, then `am_kill ... bg anr`, during start-up.
- **Declared outcomes against what happened:** none was tested; the miss case "A fails to load again" happened.
- **Decisions made inside the task:** no further retries. The budget was one session, and three boots in a row have failed on the device side.
- **For the record:**
  - #21: today, 3 boots, 8 load attempts, 1 good (B in the first session). The failures moved earlier as the day went on: the build tutorial, a dead `force-stop`, then a main menu never reached. Every boot had Google services ANR-killed during start-up. That is a candidate cause, not yet a finding.
  - The menu-wait timeout saves no frame of the screen it timed out on, so a distance of 124 from the menu can't be looked at. A gap worth closing (item 18's family).
- **Friction:** none in the routine.
- **Next:** the session close. A, the finished half of item 23's live check, carries to the next session.
