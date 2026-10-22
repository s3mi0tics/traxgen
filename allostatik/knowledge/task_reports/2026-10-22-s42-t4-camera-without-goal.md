# s42-t4 — does the camera stay put when the goal is removed?

**Status:** OPEN

**In one paragraph:** _written at close_

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

- **What happened:** _plain words_
- **What changed:** _files_
- **Evidence:** _task_check line, run lines_
- **Decisions made inside the task:** _one sentence each_
- **For the record:** _what the close folds in_
- **Friction:** _quoted, with what the task did_
- **Next:** _next task_
