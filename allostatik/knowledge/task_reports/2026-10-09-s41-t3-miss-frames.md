# s41-t3 — frames of runs that miss the goal

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Upload PROBOOK12 with only its goal rail turned (1 -> 0 and 1 -> 2), render both, press play and save the frames, so item 19's detector has runs that miss beside s41-t1's runs that finish.
- **Scope:** `scripts/make_goal_variants.py` (new), `scripts/probe_finish_frames.py`. Course files and frames land under `screenshots/finish_frames/`, which git ignores.
- **Budget:** 30 minutes, 2 uploads (Colby said yes, 2026-10-09), 1 emulator session.
- **Done check:**
  1. *Step:* build the two variants, prove each differs from PROBOOK12 in the goal rail's rotation only, upload, run the probe on both codes.
  2. *True after:* two share codes exist, each with a frames folder whose `frames.json` has no error, plus a reading of the play-button corner on every frame.
  3. *Miss cases:* a variant changed more than the goal's rotation, so a miss could come from the stray edit; the upload returned one code twice; a render landed on the wrong screen; the marble finished anyway, so there is still no miss.
  4. *Reads:* the builder's own assertions and printed lines; the two codes; `frames.json` and the PNGs; the corner samples.
  5. *Check:* the builder prints "nothing else" for both; the two codes differ; both `frames.json` have no `error`; and Claude's look at each final frame says where the trail ends, with at least one not in the goal.
- **Outcomes declared before any live run:** from Colby's s40 look ("turned other ways, it made the marble hit its side and roll along"), both variants miss: the triangle stays white, the trail ends off the goal rail. Unknown, and the point of the run: whether a miss also flips the button back to the triangle, and within the 60 s bound. If the marble rolls forever, the button stays a square and `settled` may still read true because the screen goes still. That is why the corner sample is the reading that counts.

## Close
