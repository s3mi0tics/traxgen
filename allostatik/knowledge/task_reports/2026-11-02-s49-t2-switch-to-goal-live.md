# s49-t2 — a launch pad, a switch and a goal, played live and read by the sparkle count

**Status:** STOPPED — needs Colby: A (`DLYQPCH46H`) never loaded in two sessions, both times the first load after a cold boot. One more session with B played first as a warm-up and A second, or stop here with B's result?

**In one paragraph:** Half done. The twin B (`8B3RSYR8XW`, `SWITCH_RIGHT`) played as the checker said: its marble ran into the switch and stopped against the lever. The finish check read it not finished, 0 sparkles, while the lever's white added 273 new white pixels, which the old pixel rule would have called a finish. So item 23's bug was seen live and the fix held. A (`DLYQPCH46H`, the VALID course) never played. In both sessions it was the first code, its first load landed on the build tutorial (refused, as designed), and the retry's `am force-stop` failed on the phone: `fork failed: Out of memory`, then a 10 s timeout. The phone was not short of memory (1,071 MB free, status normal). Google services were being killed for not responding while the app started, which is #21's first-launch trouble.

## Open (written before the work)

- **Goal:** play one course whose only route runs launch pad -> switch -> goal rail, which `track_graph.check_course` calls VALID, and confirm s49-t1's finish check reads it as finished; play its twin, which swaps in the other switch kind so the checker calls it a dead end, as the miss beside it.
- **Scope:** none in the repo. The builder is a scratch script (tiles below); frames go to `screenshots/finish_frames/` (gitignored).
- **Budget:** 2 uploads; at most 2 probe sessions; 30 minutes of device time.
- **The two courses** (standard square, world cells (y, x), rotation), found by searching every rotation around the pad for VALID courses whose goal is not reachable with the switch removed:
  - **A:** `STARTER` (-3, 2) r0, `SWITCH_LEFT` (-3, 3) r3, `GOAL_RAIL` (-2, 3) r0. Checker: VALID. With the switch removed: not VALID.
  - **B (twin):** the same, with `SWITCH_RIGHT` at (-3, 3) r3. Checker: INVALID, "SWITCH_RIGHT has no way on" (the marble is held).
- **Done check:**
  1. *Step:* build and upload A and B; play both by link in one probe session (`probe_finish_frames --link A B`); judge each run from its `frames.json`.
  2. *True after:* a run of a VALID switch course that settled, with frames on disk, read FINISHED by `judge_finish`; and its twin, read NOT_FINISHED.
  3. *Miss cases:* A reads finished from a lever's white (it can't now, but only the sparkle peak shows that); A finishes by a route that skips the switch (the search excluded it; the trail shows it); the load lands on a courseless screen; the run never settles and is UNJUDGED.
  4. *Reads:* each code's `frames.json` (`finish`, `finish_sparkles`, `finish_peak`, `settled`, error); `before.png` and the last frame, looked at.
  5. *Check:* A's `frames.json` says `finished` with `finish_sparkles` >= 6 and `settled` true, and its last frame shows a trail through the switch into the goal rail; B's says `not_finished` with `finish_sparkles` <= 2.
- **Outcomes declared before any live run:**
  - A: a marble loads, passes the switch, and finishes on the goal rail. Read FINISHED, peak sparkles in the finishes' range (18 to 102), and the lever has swung in the last frame.
  - B: a marble loads and stops against the switch's lever. NOT_FINISHED, sparkles 0 to 2.
  - If A does not finish, either the switch rule in `track_graph` or the goal rail's placement beside a switch is wrong, and the frames say which. That would be a finding about D103/D104, not about the finish check, unless the trail ends in the goal and the reading still says not finished.
  - If B finishes, the switch rule is wrong (D103).

## Close

- **What happened:** uploaded A `DLYQPCH46H` and B `8B3RSYR8XW` (286 bytes each; manifest `screenshots/ring_board/s49_switch_goal.json`). Session 1 (`--link A B`): A attempt 1 refused as the build tutorial (distance 2.329), attempt 2 `fork failed: Out of memory` on `am force-stop`; B loaded first try and played. Session 2 (`--link A`): A attempt 1 the build tutorial again (1.880), attempt 2 an adb timeout on `am force-stop`. Both boots passed every device check on Metal; the emulator was down after each (`PASS emulator_down`).
- **What changed:** nothing in the repo. Frames under `screenshots/finish_frames/8B3RSYR8XW/`; A's failed attempts under `DLYQPCH46H/` and `DLYQPCH46H/run_1/`.
- **Evidence:**
  - B `frames.json`: `validity: active`, `finish: not_finished`, `finish_sparkles: 0`, `finish_peak: 273`, `settled: true`, 15 frames, 1.07 s median interval.
  - B `after_14.png`, looked at: a short pink trail from the launch pad into the switch, ending at the lever; nothing past it; the goal rail untouched.
  - Phone evidence: `screenshots/device_evidence/20261102-162924.txt`, `-162937.txt`, `-163455.txt`. Total RAM 2,025,912K, free 1,071,221K, status normal; `am_kill ... bg anr` on `com.google.android.as` and `com.google.android.gms` during app start in both boots.
- **Declared outcomes against what happened:**
  - B: held at the lever, not finished, sparkles 0 to 2. Held: 0 sparkles.
  - A: unmeasured.
- **Decisions made inside the task:** reran A alone rather than A after B, to keep the first session's order. That repeated the exact condition that failed: first load after a cold boot.
- **For the record:**
  - Item 23: the fix seen live on a miss. A switch course whose lever adds 273 white pixels reads not finished at 0 sparkles. The finished half is still unmeasured.
  - D104 and D103: the checker's INVALID on B ("SWITCH_RIGHT has no way on") matched the run.
  - #21: 2 boots, 4 load attempts, 1 good. Both failures were the first load after boot (build tutorial), then a dead `force-stop` on the retry. The phone had memory to spare; Google services were ANR-killed during app start.
  - Colby, watching live: "the switch only works if the marble runs a certain way through the switch". Consistent with D103: one side holds, and which one depends on the lever.
- **Friction:** the retry after a refused load runs `am force-stop` on a phone that is still struggling, and dies there. Retrying in the same boot used to work (s43, s46, s48); here it didn't, twice.
- **Next:** Colby's call: one more session with B first as a warm-up, then A; or stop with B's half.
