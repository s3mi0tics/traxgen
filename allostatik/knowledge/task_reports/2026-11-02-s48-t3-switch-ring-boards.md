# s48-t3 — the switch on goal-less ring boards, both kinds, played on the emulator

**Status:** DONE, with one deviation: the per-side pixel counts don't meet the check's "every other side under 30", so the 12 readings were made by eye on the last frames, and the counts' largest side agrees with every one

**In one paragraph:** Both switch kinds load a marble at the same three rotations (1, 3, 5) and none at the other three, so their open sides are the same three even sides of the piece: 0, 2 and 4. With one marble each, from the starting state, the two kinds turn opposite ways. Entering by the launch pad's world side 5, `SWITCH_LEFT` sent the marble out world side 1 and `SWITCH_RIGHT` out world side 3, at both rotations where it left. At the third loading rotation of each kind, the marble went in and stopped against the lever, with no trail out. In the piece's own frame: `SWITCH_LEFT` 0→2, 2→4, 4→stops; `SWITCH_RIGHT` 4→2, 2→0, 0→stops. The two tables are mirror images (side k ↔ 4−k). A second finding: the lever flips as a marble passes and uncovers white plastic, and `judge_finish` reads that as a finish burst (peaks 976 and 801 on boards with no goal).

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

## Close

- **What happened:** uploaded `Q7AE2SM7MC` (`SWITCH_LEFT`, no goals) and `54TI3KWGTH` (`SWITCH_RIGHT`, no goals); played both in one probe session. LEFT's attempt 1 was refused at the menu wait (launcher in front after 90 s, evidence `screenshots/device_evidence/20261102-112627.txt`); attempt 2 loaded. RIGHT loaded on attempt 1. Both runs settled with the stop square cleared; both boots passed every device check; the emulator was down at the end (`PASS emulator_down`).
- **What changed:** nothing in the repo. Frames under `screenshots/finish_frames/Q7AE2SM7MC/` and `54TI3KWGTH/`, manifests `screenshots/ring_board/SWITCH_*-nogoals.json`.
- **Evidence:**
  - `before.png` on both boards shows six rings, each a launch pad beside a switch.
  - By eye, last frames (`after_09`, `after_21`): LEFT rotations 5 (blue) and 3 (green) run screen-right, slightly up, which is world side 1 on `STANDARD_SQUARE_SCREEN` (−11°); rotation 1 (red) ends inside the switch. RIGHT rotations 1 (red) and 3 (green) run screen-down, which is world side 3 (106°); rotation 5 (blue) ends inside the switch, and the mid-run frame `after_04` shows its marble resting against the lever. Rotations 0, 2 and 4 show no trail on either board.
  - Trail pixels in the 0.35–1.3-cell annulus (s47-t4's method; the reader reproduced s47-t4's CROSS counts exactly first): LEFT r1 `{5: 429}`, r3 `{0: 122, 1: 432, 5: 347}`, r5 `{0: 153, 1: 460, 5: 206}`; RIGHT r1 `{3: 387, 4: 330, 5: 224}`, r3 `{3: 452, 4: 208, 5: 324}`, r5 `{0: 7, 5: 146}`; the other six rings 0 on every side. The largest side matches every eye reading, but the launch pad's side and its neighbour carry trail too, which CROSS's never did, so the declared "every other side under 30" fails.
  - New near-white pixels per frame after play: LEFT `[752, 970, 970, 974, 836, 976, 0, 0, 0, 0]`, RIGHT 448 to 801 over the run then 0; the CROSS goal-less run `[0, 0, 0, 0, 0]`. In the frames, the levers that a marble passed have swung to the other side.
- **Declared outcomes against what happened:**
  - "Every ring that loads leaves by exactly one side": no. One ring per kind loaded and never left.
  - "Same loading rotations": held (1, 3, 5 for both).
  - "Different sides at every such rotation": held where both left (r3: 1 vs 3). At r1 and r5 one kind stopped.
  - s48-t1's first live use: one refusal, for the launcher in front, caught at the menu wait before any load.
- **Decisions made inside the task:** read by eye after the pixel check failed its own threshold. Each reading is a trail that is plain in the frame, and the counts' largest side agrees with all six.
- **For the record:**
  - Switch, first marble from the starting state, flat on a baseplate: `SWITCH_LEFT` 0→2, 2→4, 4→stops; `SWITCH_RIGHT` 4→2, 2→0, 0→stops; odd sides take no marble. Each entry measured once. Whether this is one piece in two lever states or two mirrored pieces (#1), these readings can't tell apart: a mirror and a lever flip predict the same tables.
  - The lever flips as a marble passes. What the second marble does is unmeasured (#27).
  - `judge_finish` reads a lever flip as a finish (#57's family; D093 was measured on the goal rail only). A finish reading on a course with a switch is not evidence until the burst is told apart from the lever.
  - #21: 2 load attempts, 1 good, the bad one the launcher in front at the menu wait.
- **Friction:** the check named a pixel threshold from one piece (CROSS) for a different piece, which is #63's shape again: the threshold was a guess about the new piece's trails, not a measured fact.
- **Next:** the rule, gated on Colby: how a piece with a lever enters `track_graph`.
