# s48-t3 — the switch on goal-less ring boards, both kinds, played on the emulator

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** for each of the six rotations of `SWITCH_LEFT` and of `SWITCH_RIGHT`, measure which side the marble leaves by, or that no marble loads, from the trails on the goal-less ring boards (D100).
- **Scope:** none in the repo. Manifests and frames go to `screenshots/` (gitignored); the report is always in scope.
- **Budget:** 2 uploads; at most 2 probe sessions; 30 minutes of device time.
- **Done check:**
  1. *Step:* upload `SWITCH_LEFT --no-goals` and `SWITCH_RIGHT --no-goals`; play both by link in one probe session (`probe_finish_frames --link`, now through `load_course`); count trail pixels per ring and world side between `before.png` and the last frame, through `STANDARD_SQUARE_SCREEN`.
  2. *True after:* for each of the 12 rings, a measured exit side or "loads no marble", read from frames on disk of a run that settled.
  3. *Miss cases:* the load lands on a screen with no course (now refused, but an unknown dead screen still passes); a ring reads "no marble" because the run had not settled; a trail is counted on the wrong ring.
  4. *Reads:* `screenshots/ring_board/SWITCH_*-nogoals.json`; each run's `frames.json` (no error, settled); the per-ring, per-side pixel counts; one look at `before.png` and the last frame.
  5. *Check:* both `frames.json` show no error, `before.png` shows the board's pieces, and 12 lines print, each either one side with at least 100 px of trail and every other side under 30, or every side under 30 (no marble).
- **Outcomes declared before any live run:**
  - Every ring that loads a marble leaves by exactly one side. One marble shows one of the switch's two ways out, the one its starting state picks.
  - `SWITCH_LEFT` and `SWITCH_RIGHT` load a marble at the same rotations. That's what follows if the two kinds are one piece with its lever set two ways (the set reference's reading). At every such rotation they leave by different sides.
  - If the loading rotations differ, the two kinds are different pieces, not two states, and open question #1 is answered the other way.
  - No prediction of which sides; nothing in the record says.
  - The new load refuses any screen it recognises as courseless, so a probe attempt can fail with `RefusedScreenError` or `OracleFrameError` rather than record one. That's the first live use of s48-t1.
