# s41-t1 — what a finished run and a missed run look like on screen

**Status:** OPEN

**In one paragraph:** _written at close_

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

- **What happened:**
- **What changed:**
- **Evidence:**
- **Decisions made inside the task:**
- **For the record:**
- **Friction:**
- **Next:**
