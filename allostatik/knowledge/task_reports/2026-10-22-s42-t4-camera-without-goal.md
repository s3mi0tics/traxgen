# s42-t4 — does the camera stay put when the goal is removed?

**Status:** DONE — and its side finding needs Colby before t5: the app shows a sparkle burst when the marble reaches the goal, which may make options B and C unnecessary.

**In one paragraph:** The camera held. Removing the goal changed only the goal's own pixels on both courses, plus, on the Phase 1 course, the play button, which turns pale with no goal. So option C works and gives a clean outline of the goal. The bigger result is a side finding: when the marble reaches the goal, the app throws a burst of sparkles for about a second. Every finish run on record shows one (62 to 1,176 new near-white pixels in one frame), and no miss, rim stop or no-goal run does (11 or fewer). s41-t5 missed it because it compared only the before-play frame with the last frame, and by then the sparkles are gone. One more surprise: this time the Phase 1 course's run left no trail at all, where s41's left one.

## Open (written before the work)

- **Goal:** Test the one thing that could break option C (Colby, 2026-10-22: "C first and then B"). Render a course with its goal and without it; if the camera holds, the pixels that change mark the goal on screen.
- **Scope:** `scripts/make_no_goal.py` (new: remove every goal piece, prove nothing else changed, upload), and `scripts/probe_finish_frames.py` if the run needs it.
- **Budget:** 45 minutes, 2 uploads, 1 emulator session (4 renders).
- **Done check:**
  1. *Step:* build and upload PROBOOK12 and the Phase 1 course (`generate --set vertical-starter`) without their goal pieces; render those two plus `THIIEUH35Z` and `KN6F459ZR3` in one `--fresh` session by link.
  2. *True after:* for each pair, the rendered frame with the goal and without it differ only around where the goal sits. The board's outline and everything far from the goal are pixel-identical.
  3. *Miss cases:* the no-goal file differs from the source by more than the goal (a stray edit would also change pixels); the Phase 1 rebuild is not the course `KN6F459ZR3` names (a different course would differ everywhere); a no-goal course fails to load and the "render" is a dialog; the camera moves by a pixel or two, which a loose threshold would hide.
  4. *Reads:* the script's own asserts (only goal tiles removed, rails unchanged, round-trip); the upload's returned codes (the Phase 1 rebuild must come back as `KN6F459ZR3`, since uploads are deduplicated by content); the four `rendered.png`.
  5. *Check:* per pair, the bounding box of pixels whose RGB moved by more than 30 in total, its area as a share of the frame, and whether it contains the goal's spot (s42 crops: PROBOOK12 near x 1250-1650 y 240-560; KN6 near x 780-1100 y 440-660); plus the count of changed pixels outside that box, which is 0 if the camera held.
- **Outcomes declared before any live run:** the camera frames the plates, not the pieces, so for both pairs every changed pixel sits inside the goal's area and the count outside is 0. If the camera moves, the whole frame changes and C needs a different removal: replace the goal with a piece that keeps the outline, or fall back to B.

## Close

- **What happened:** `make_no_goal` removed `GOAL_RAIL@(-1,0)` from the Phase 1 course (177 -> 153 bytes) and `GOAL_RAIL@(-6,4)` from PROBOOK12 (1559 -> 1537), its asserts passing (only goal tiles gone, rails and layers unchanged, round-trip). Uploads: the Phase 1 rebuild came back `KN6F459ZR3` (dedup proves it is the same course), its no-goal version `4DLUQKGRKN`; PROBOOK12's source came back `PROBOOK12`, its no-goal version `STXT6WF9VB`. One `--fresh` session (boot 25.8 s), all four by link, attempt 1 each. `4DLUQKGRKN` read `inactive` and play never ran (`stop_square` all false). The rest read `active` and settled. s41's `KN6F459ZR3` frames were moved to `KN6F459ZR3_s41` first, so this run didn't overwrite them.
- **What changed:** `scripts/make_no_goal.py` (new). Files under `screenshots/finish_frames/nogoal/` (gitignored).
- **Evidence:**
  - `task_check`: in scope.
  - Camera (pixels whose RGB moved by more than 30 in total, `rendered.png` with goal vs without):
    - PROBOOK12: 1,310 px, bbox x 1399-1443 y 309-369, all inside the goal area, 0 outside.
    - Phase 1: 1,715 px above the toolbar, bbox x 892-999 y 542-619, all in the goal area. 2,516 px in the toolbar, bbox x 2143-2236 y 939-1031, which is the play button.
    - The masks are the goal rail's outline (looked at). The Phase 1 mask also holds a small blob on the waiting marble in the launch pad, which isn't drawn when there is no goal.
  - Done check: met. Declared outcome (camera holds, 0 changed pixels outside the goal area): met for PROBOOK12; for the Phase 1 course, met apart from the play button.
  - Sparkles (pixels with every channel above 235 that weren't in `before.png`, x > 200, y < 880, per after-frame):
    - Finish: PROBOOK12 max 1,000; `THIIEUH35Z` max 62; `KN6F459ZR3` max 1,176; `KN6F459ZR3_s41` max 830.
    - Rim stop `W8IEN7MG92`: max 11.
    - Misses, eight runs: max 11.
    - No goal: `STXT6WF9VB` max 10, `4DLUQKGRKN` max 0.
  - The sampling is one frame a second, so `THIIEUH35Z`'s 62 probably caught only the tail of the burst.
  - `KN6F459ZR3` this run: no pink at all in any after-frame (s41's run had 358 px). Light beams and sparkles show in after_00 and after_01 (looked at), and the last frame equals the before-play frame (`first_vs_last` 0.0).
- **Decisions made inside the task:** Rendered PROBOOK12's own code, not `THIIEUH35Z`, because the no-goal file was made from exactly those bytes.
- **For the record:**
  - `plan.md` *What is true now* and item 19: **a finish has its own on-screen signal, a sparkle burst near the goal lasting about a second.** It is in every finish on record and in no miss, rim stop or no-goal run. This corrects s41-t5's "nothing but the trail marks a finish", which looked only at the last frame.
  - #22: a course with no goal piece shows a pale play button, and play does nothing. So the triangle checks that a goal exists, as well as placement.
  - Item 19, option C: works; the camera frames the plates, not the pieces.
  - New open question: why `KN6F459ZR3` left no trail this run (by link, 2026-10-22) when it left one in s41 (typed, 2026-10-08).
  - Hazard: re-running into an existing frames folder leaves the older run's extra `after_NN.png` behind (seen in `I4BA3N5V6Y/run_1`, after_06 to 09 from s42-t1). Anything reading frames must stop at `frames.json`'s count, or the probe should clear the folder first.
- **Friction:** none in the routine. This task's goal was the camera test, and the sparkle result came as a side finding; it changes the shape of the session's goal, which is stop reason 2.
- **Next:** Colby decides: build the detector on the sparkle burst (no goal location needed), keep C/B, or use both.
