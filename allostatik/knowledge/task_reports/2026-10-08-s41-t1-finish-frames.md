# s41-t1 — what a finished run and a missed run look like on screen

**Status:** STOPPED — needs Colby: may I upload two PROBOOK12 variants with only the goal rail turned (1 -> 0 and 1 -> 2, titled "traxgen finish test goal N") to Ravensburger's server, so the frames include a run that misses?

**In one paragraph:** Three courses rendered, play pressed, frames saved every second. All three end with the trail in the goal, Phase 1's `KN6F459ZR3` included, by Claude's eye on the frames. Two findings shape item 19: the play button shows a stop square for exactly as long as the marble runs, so the end of a run is one pixel sample, not a guess from a still screen; and the first app launch after a cold boot died in all three emulator sessions while every later launch in the same boot worked (#21). The done check is not met, because nothing captured is a miss, and making one needs an upload.

## Open (written before the work)

- **Goal:** Save the frames the app shows after play is pressed, for courses that finish and courses that miss, so item 19's finish check is written from real screens rather than guessed.
- **Scope:** `scripts/probe_finish_frames.py` (new). Frames land in `screenshots/finish_frames/`, which git ignores.
- **Budget:** 45 minutes, 2 emulator sessions, no uploads without Colby's yes.
- **Done check:**
  1. *Step:* render each course, press play, take a frame every second until the screen stops changing, save every frame.
  2. *True after:* for each course, a folder holds the frame before play and the frames after it, ending in a settled frame, plus a `frames.json` saying when it settled or that it never did.
  3. *Miss cases:* the render landed on the wrong screen (tutorial, launcher, loading) and the frames show no course; play was never pressed, so nothing moved; the run was cut off while the marble was still moving; only finishing courses were captured, so there is nothing to tell a miss apart from.
  4. *Reads:* the saved PNGs and `frames.json` under `screenshots/finish_frames/`.
  5. *Check:* for each course, `frames.json` reports `settled: true`, the first and last frames differ (play did something), and Claude has looked at the last frame and seen a course with a trail; plus at least one course whose trail visibly misses the goal.
- **Outcomes declared before any live run:** `THIIEUH35Z` (PROBOOK12 as built) and `W8IEN7MG92` (goal turned 1 -> 4) end with the trail in the goal, per Colby's s40 look. `KN6F459ZR3` is unknown: a two-tile course, starter beside goal; if its trail is too short to see at the default camera, that is itself a finding for item 19. If none of these misses, a miss course needs an upload, which is Colby's call.

## Close

- **What happened:** Session 1 (`KN6F459ZR3`, `THIIEUH35Z`, `W8IEN7MG92`): the first render died during the main-menu wait with the launcher in front; the other two rendered `active`, ran, and settled. Session 2 (`KN6F459ZR3` alone): the same first-launch death. Session 3, with one retry added inside the same boot: attempt 1 died the same way (`timed out after 90.0s (29 polls) ... 3 of 29 frames unreadable`, launcher in front), attempt 2 reached the menu in 15.4s, rendered `active`, ran and settled. Frames are in `screenshots/finish_frames/<code>/` (gitignored).
- **What changed:** `scripts/probe_finish_frames.py` (new).
- **Evidence:**
  - Play-button corner, mean RGB over x 2200-2211, y 964-975: `[180, 204, 50]` on every frame before play and after the run ended; `[221, 232, 161]` (stop square) on every frame while the marble moved. The run ended at after_06 (THIIEUH35Z), after_04 (W8IEN7MG92), after_02 (KN6F459ZR3), and never flipped back mid-run.
  - Before-vs-last frame difference: 0.6188, 0.6155, 0.018. The Phase 1 trail is short: launch pad to goal rail, about 100 px across at the default camera.
  - Claude's read of each final frame: THIIEUH35Z and W8IEN7MG92, trail ends in the goal rail (as declared); KN6F459ZR3, trail runs from the launch pad onto the goal rail and stops on it. Eye reads, not a check.
  - First launch after a cold boot: died 3 of 3 sessions; later launches in the same boot: 3 of 3 fine.
  - Done check: not met. No miss captured.
  - `task_check s41-t1`: `OUT OF SCOPE -- 1 of 3 changed files are not this task's: Claude outputs/traxgen-handoff-2026-09-21-s37-to-s38.md`. That file is dated 2026-09-21 and was untracked before this task opened; the other two changed files are this task's. Left in place: it is Colby's, and handoffs stay local by convention.
- **Decisions made inside the task:** Tap play at `PLAY_BUTTON_SAMPLE_CENTER`, the same point the oracle samples, rather than adding a coordinate to `android.py`. Retry a course once within the same boot rather than cold-booting again, because the second launch is the one that works.
- **For the record:**
  - `plan.md` *What is true now*: the play button shows a stop square while the marble runs and returns to the triangle when the run ends; one pixel sample tells a finished run from a running one.
  - `plan.md` #21: the first app launch after a cold boot died in 3 of 3 sessions on 2026-10-08 and every later launch in the same boot worked (3 of 3), so a same-boot retry is a working repair until the cause is known. This sharpens #21 from "non-deterministic" towards "first launch".
  - `plan.md` item 19 / Phase 1 clause (4): by eye, `KN6F459ZR3`'s trail ends on its goal rail. Not yet a check; t2's detector must confirm before the record claims it.
- **Friction:** The probe printed only the exception's message, and `WrongForegroundAppError`'s message is the tap-guard wording, so the real cause (a menu-wait timeout, in `__notes__`) took one extra run to see. Callers that log errors should print notes; `render_course.py` already does. This is the "stale hint" carried since s39, now costing a run.
- **Friction (2):** `task_check` counts untracked files, so a handoff left in `Claude outputs/` (where handoffs go, uncommitted by convention) fails every task's close. Candidate fix, for Colby: add `Claude outputs/` to `.gitignore`, which matches the handoff convention.
- **Next:** on a yes, upload the two goal variants and run the probe on them (new task); then t2, the finish detector, from these frames. On a no, Colby makes a miss by hand in the editor, or t2 starts with finish frames only and the miss case waits.
