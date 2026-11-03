# s49-t3 — course A after a warm-up load

**Status:** OPEN

**In one paragraph:** _written at close_

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
