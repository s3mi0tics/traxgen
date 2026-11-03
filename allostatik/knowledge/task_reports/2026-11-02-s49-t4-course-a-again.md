# s49-t4 — course A, one more session, before the close

**Status:** FAILED — the app died to the launcher during the menu wait, and the retry's launch timed out; A stays unmeasured

**In one paragraph:** A did not play, the fourth boot today with no clean first launch. Attempt 1: the main-menu wait timed out after 90 s and the launcher was in front, so the app had died; refused as `WrongForegroundAppError`. Attempt 2: `monkey` launching the app timed out at adb's 10 s. Colby confirmed nobody touched the emulator in s49-t2 to t4, so every bad screen today was the app's own.

## Open (written before the work)

- **Goal:** Colby: "run course a now before the close". Play A `DLYQPCH46H` by link in one fresh probe session and read it with the sparkle count. Colby confirms nobody touched the emulator during s49-t2 and t3, so their far-from-menu screens were the app's own.
- **Scope:** none in the repo; frames to `screenshots/finish_frames/` (gitignored).
- **Budget:** 1 probe session; no uploads.
- **Done check:** as s49-t3's: A's newest `frames.json` has no error, `settled` true, `finish: finished` with `finish_sparkles` >= 6, and the last frame, looked at, shows a trail through the switch into the goal rail.
- **Outcomes declared before any live run:** as s49-t2 declared for A: FINISHED, peak sparkles 18 to 102, the lever swung. If A loads and does not finish, the frames say whether the switch rule or the goal beside the switch is wrong.

## Close

- **What happened:** one session, `--link DLYQPCH46H`; boot and device checks passed; attempts 1 and 2 failed as above; emulator down at the end (`PASS emulator_down`).
- **What changed:** nothing in the repo. `screenshots/finish_frames/DLYQPCH46H/run_3/frames.json` holds the errors.
- **Evidence:** phone evidence `screenshots/device_evidence/20261102-165642.txt`, `screenshots/device_evidence/20261102-165613.txt`.
- **Declared outcomes against what happened:** none tested.
- **Decisions made inside the task:** no retry beyond the probe's two attempts; the budget was one session.
- **For the record:** #21, today: 4 boots, 10 load attempts, 1 good. Failure modes in order: the build tutorial (twice), a dead `force-stop` (out of memory, then a timeout), a main menu never reached (four times), the app dead to the launcher, a launch timeout. The phone had ~1 GB free; Google services were ANR-killed during start-up in every boot read. Colby: no human input on the emulator during any of it.
- **Friction:** none in the routine.
- **Next:** the session close; A carries.
