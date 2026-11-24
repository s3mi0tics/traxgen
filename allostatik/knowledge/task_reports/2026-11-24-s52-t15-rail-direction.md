# s52-t15 — which way the marble travels through each piece's sides, from rail heights (#7)

**Status:** DONE

**In one paragraph:** A rail's two ends have heights, and passive track only runs downhill, so the higher end is where the marble enters the rail -- the piece there is sending it out. A rail end's absolute height is layer height + h x 0.36 + y: with 0.36 per small stacker, STARTER's end is the higher one on 333 rails and the lower on none (30 level); every other unit tried inverts some. On that footing, in each piece's own frame: CURVE and CROSS are used both ways on every open side, as passive two-way pieces; STARTER only sends out, on 0, 2 and 4; ELEVATOR takes in on 5 and sends out on 0, no exceptions in 276; THREEWAY merges 1, 2, 3 into 5; THREE_ENTRANCE_FUNNEL, DROP and FINISH_ARENA only take in; and both switches are almost always built with the marble coming in on side 2 and leaving by 0 or 4 -- the branch-to-stem passes D103 measured (0 to 2, 4 to 2) are physically real but almost never built. CATCH is not an in-only piece: its rail side 2 sends out (340 of 347 directional). 22% of rails are level, and their direction is unknown.

## Open (written before the work)

- **Goal:** fold a background corpus reader's direction-of-travel tables into the record, after re-running its calibration and table.
- **Scope:** none beyond the ledger and this report (the per-side table is appended).
- **Budget:** 10 minutes, no renders.
- **Done check:**
  1. *Step:* re-run `conv.py` (height unit calibration) and `sides.py` (per-side table) and diff the table.
  2. *True after:* the convention and the table come from runs in this task.
  3. *Miss cases:* a unit chosen because it looks tidy rather than because out-only and in-only pieces calibrate on it; level rails counted as either direction.
  4. *Reads:* the reader's `rails.jsonl` (16,097 rails with both ends on layer cells, from `mine_ports` helpers).
  5. *Check:* the report quotes the STARTER and GOAL_BASIN calibration lines for each candidate unit and the diff is empty.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** re-run here from the reader's folder. `conv.py`: `clean rails 16097 Counter({3: 7291, 4: 4670, 5: 4040, 7: 96})`; STARTER higher/lower/level at u=0: 10/16/337; u=0.18: 320/15/28; u=0.36: 333/0/30; u=0.72: 330/5/28. GOAL_BASIN at u=0.36: lower 116, higher 5, level 94. v7 baseplate offset 0 or -0.2 changed nothing. `sides.py` regenerated `sides_out.md` identical to the reader's.
- **What changed:** this report and the ledger only.
- **Evidence:** the calibration lines above; the table below.
- **Decisions made inside the task:** none.
- **For the record:**
  - `plan.md` #7 / item 1: rail heights give direction of travel per side (convention above); combined with s52-t13's port sets, the corpus now proposes in/out per side for most pieces. Use it to choose which side of a ring board gets the launch pad.
  - `plan.md` #27 and the switch (D103, D104): corpus builders feed switches by side 2 (LEFT 158 in vs 5 out; RIGHT 114 vs 4) and take marbles out by 0 and 4. D103's rule already covers 2-in; the generator's first switch courses should use that direction, the one real courses use.
  - Candidate for the generator's goal list (s52-t14): FINISH_ARENA is in-only on its one rail side (20 in, 0 out); CATCH is not a goal.
  - CANNON: side 5 is mostly the way in (674 in vs 42 out); side 2 is evenly split.
- **Friction:** the reader's scripts open `rails.jsonl` by relative path, so they run from their own folder (`uv run --project <repo>`).
- **Next:** the close.

## Appendix — per-side direction table (out = the marble leaves the piece; in = enters; L = level), re-run output verbatim

drop distribution (top): [(0.36, 4986), (0.0, 3543), (0.72, 2590), (1.08, 971), (1.44, 753), (2.52, 716), (2.16, 529), (1.8, 426), (0.52, 229), (0.2, 206), (2.36, 181), (0.16, 149)]

## Highlighted
| kind | ends | side0 | side1 | side2 | side3 | side4 | side5 |
|---|---|---|---|---|---|---|---|
| CURVE | 17641 | 2331o/2425i/1637L | - | 2384o/2458i/1583L | 1098o/862i/427L | 1132o/893i/411L | - |
| CROSS | 2253 | - | 205o/148i/114L | 274o/226i/162L | - | 181o/171i/138L | 219o/236i/179L |
| CANNON | 1183 | - | - | 106o/114i/122L | - | - | 42o/674i/125L |
| SWITCH_LEFT | 443 | 94o/11i/24L | - | 5o/158i/22L | - | 98o/2i/29L | - |
| SWITCH_RIGHT | 343 | 60o/2i/15L | - | 4o/114i/12L | - | 112o/12i/12L | - |
| THREE_ENTRANCE_FUNNEL | 31 | 0o/3i/0L | - | 0o/16i/2L IN-only | - | 0o/10i/0L IN-only | - |
| GOAL_BASIN | 215 | 2o/32i/29L | - | 2o/53i/27L | - | 1o/31i/38L | - |
| CATCH | 427 | - | - | 340o/7i/80L | - | - | - |
| DROP | 41 | - | - | 0o/27i/14L IN-only | - | - | - |
| SPIRAL | 83 | - | - | 0o/20i/16L IN-only | - | - | 1o/39i/7L |
| THREEWAY | 1260 | - | 15o/138i/41L | 59o/294i/63L | 10o/182i/38L | - | 272o/48i/100L |
| ELEVATOR | 276 | 193o/0i/1L OUT-only | - | - | - | - | 0o/76i/6L IN-only |
| CASCADE | 243 | - | - | 39o/99i/105L | - | - | - |
| STARTER | 363 | 110o/0i/8L OUT-only | - | 123o/0i/13L OUT-only | - | 100o/0i/9L OUT-only | - |
| DOME_STARTER | 48 | - | - | 37o/2i/9L | - | - | - |
| FINISH_TRIGGER | 80 | - | - | 19o/7i/9L | - | - | 3o/35i/7L |
| FINISH_ARENA | 31 | - | - | - | - | - | 0o/20i/11L IN-only |

## All others >=20
| kind | ends | side0 | side1 | side2 | side3 | side4 | side5 |
|---|---|---|---|---|---|---|---|
| CURVE_TUNNEL | 860 | 166o/149i/127L | - | 156o/142i/120L | - | - | - |
| STRAIGHT_TUNNEL | 637 | - | - | 136o/123i/66L | - | - | 128o/109i/75L |
| DOUBLE_SMALL_CURVE | 452 | 7o/7i/6L | 65o/74i/38L | 8o/3i/5L | 4o/5i/9L | 81o/77i/43L | 8o/6i/6L |
| VOLCANO | 369 | - | 37o/2i/17L | 1o/115i/18L | 76o/0i/10L OUT-only | - | 61o/0i/32L OUT-only |
| TWO_WAY | 338 | 3o/93i/12L | - | 101o/5i/15L | - | 2o/95i/12L | - |
| TWO_IN_ONE_SMALL_CURVE_A | 289 | 2o/71i/10L | - | 77o/5i/17L | 5o/0i/3L OUT-only | 1o/6i/1L | 12o/71i/8L |
| DOUBLE_BIG_CURVE | 247 | 18o/23i/18L | 23o/28i/20L | - | 27o/19i/11L | 21o/19i/20L | - |
| HAMMER | 246 | - | - | 10o/69i/59L | - | - | 11o/57i/40L |
| RIBBON_CURVE | 239 | 48o/58i/14L | - | - | - | - | 44o/62i/13L |
| TWO_IN_ONE_SMALL_CURVE_B | 225 | - | 0o/52i/12L IN-only | 6o/57i/10L | 0o/4i/1L | 5o/0i/0L OUT-only | 64o/5i/9L |
| SWITCH_TUNNEL | 190 | 69o/0i/0L OUT-only | - | 0o/72i/1L IN-only | - | 48o/0i/0L OUT-only | - |
| SCREW_MEDIUM | 173 | 23o/49i/22L | - | - | - | - | 42o/7i/30L |
| CURVE_CROSSING | 170 | 21o/12i/7L | 18o/21i/1L | 3o/10i/0L | 8o/6i/1L | 10o/23i/1L | 6o/19i/3L |
| QUEUE | 162 | 1o/33i/6L | - | 14o/3i/8L | - | 2o/26i/6L | 5o/46i/12L |
| STRAIGHT_CURVE_CROSSING | 150 | 15o/9i/7L | - | 31o/18i/4L | - | 7o/13i/5L | 7o/18i/16L |
| TURNTABLE | 144 | 11o/14i/1L | 19o/1i/0L | 8o/5i/2L | 18o/7i/1L | 10o/11i/0L | 24o/9i/3L |
| MULTI_JUNCTION | 137 | 8o/11i/5L | 5o/11i/8L | 12o/7i/3L | 9o/10i/4L | 9o/5i/4L | 4o/17i/5L |
| SPINNER | 135 | 19o/0i/2L OUT-only | 16o/0i/2L OUT-only | 24o/1i/3L | 23o/0i/3L OUT-only | 18o/0i/1L OUT-only | 21o/1i/1L |
| HELIX | 130 | 10o/7i/0L | 8o/11i/7L | 13o/5i/5L | 9o/11i/3L | 11o/7i/0L | 12o/7i/4L |
| SPLASH | 122 | 32o/11i/0L | - | 36o/2i/1L | - | 35o/3i/2L | - |
| JUMPER | 120 | - | - | 24o/0i/5L OUT-only | - | - | 23o/45i/23L |
| SPLITTER | 119 | 5o/9i/1L | 6o/11i/1L | 28o/0i/1L OUT-only | 2o/9i/1L | 3o/11i/2L | 24o/2i/3L |
| SCREW_SMALL | 117 | - | - | 6o/46i/4L | - | - | 45o/4i/12L |
| TRIGGER | 102 | - | - | 10o/31i/12L | - | - | 27o/19i/3L |
| CATAPULT | 100 | - | - | 0o/13i/87L IN-only | - | - | - |
| DROPDOWN_SWITCH_LEFT | 99 | - | 26o/3i/6L | - | 22o/5i/4L | - | 2o/28i/3L |
| FLIP | 97 | - | - | 17o/20i/60L | - | - | - |
| LEVER | 93 | - | - | - | - | - | 3o/78i/12L |
| LOOP | 86 | - | - | 12o/33i/3L | - | - | 9o/24i/5L |
| TIP_TUBE | 79 | - | 0o/31i/8L IN-only | 31o/0i/9L OUT-only | - | - | - |
| LIFT_SMALL | 78 | - | - | 1o/16i/8L | - | - | 53o/0i/0L OUT-only |
| MIXER_OFFSET_EXITS | 78 | 4o/4i/1L | 18o/0i/1L OUT-only | 0o/1i/1L | 21o/0i/2L OUT-only | 0o/7i/0L IN-only | 16o/0i/2L OUT-only |
| BRIDGE | 75 | - | - | - | - | - | 8o/62i/5L |
| LIFT_LARGE | 69 | - | - | 0o/20i/10L IN-only | - | - | 38o/0i/1L OUT-only |
| TRIPLE_SMALL_CURVE | 66 | 3o/3i/5L | 6o/3i/1L | 8o/3i/5L | 3o/4i/0L | 1o/7i/3L | 7o/2i/2L |
| SCREW_LARGE | 60 | - | - | 8o/22i/3L | - | - | 14o/4i/9L |
| CAROUSEL_SAME_EXITS | 59 | 0o/9i/1L IN-only | 10o/0i/1L OUT-only | 0o/10i/0L IN-only | 11o/0i/0L OUT-only | 3o/7i/0L | 7o/0i/0L OUT-only |
| DROPDOWN_SWITCH_RIGHT | 50 | - | 14o/2i/3L | - | 14o/0i/4L OUT-only | - | 3o/6i/4L |
| MIXER_SAME_EXITS | 50 | - | 7o/9i/0L | - | 9o/7i/1L | - | 7o/7i/3L |
| RELEASER_1 | 32 | 0o/6i/0L IN-only | - | 1o/5i/3L | - | 0o/2i/0L | 10o/5i/0L |
| FLEXIBLE_TWO_IN_ONE_B | 27 | 1o/8i/1L | - | 1o/3i/0L | 0o/3i/0L | - | 5o/1i/4L |
| CAROUSEL_OFFSET_EXITS | 26 | 2o/3i/0L | 1o/4i/0L | 2o/4i/0L | 1o/4i/0L | 2o/0i/0L | 2o/1i/0L |
| COLOR_SWAP_PRELOADED | 24 | - | - | 7o/6i/0L | - | - | 3o/8i/0L |
| FLEXIBLE_TWO_IN_ONE_A | 20 | - | 0o/1i/0L | 5o/1i/0L | - | 0o/5i/0L IN-only | 1o/7i/0L |

