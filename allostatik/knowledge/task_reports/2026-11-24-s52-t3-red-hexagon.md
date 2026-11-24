# s52-t3 — the red hexagon (#30, item 24 (c)), from frames on disk

**Status:** DONE

**In one paragraph:** The red hexagon is the app marking a lost marble: the marble turns solid red and a red hexagon outline flashes around it where it comes to rest off the track (`GXR7RV5NA6/after_03`, on the floor past the plate; the frame before shows a silver marble at the same spot). It lasts about one frame at 0.4 to 0.8 s spacing. Counted as red that is present in one frame and in neither neighbour, it never showed on a single-marble finish (5 runs, all 0), and showed on most misses (32 to 345 px) but not all (6 runs at 0 to 6). So a flash means a miss; no flash means nothing. On boards with several marbles, a red marble in motion is counted too, so there the count says nothing without a shape test.

## Open (written before the work)

- **Goal:** say what the red hexagon is and whether it separates misses from finishes on the runs already on disk.
- **Scope:** none beyond the ledger and this report.
- **Budget:** 20 minutes, no renders.
- **Done check:**
  1. *Step:* look at one flash; then count, in every run on disk, red pixels (R > 180, G < 90, B < 90, board area) present in one frame and in neither neighbour.
  2. *True after:* the hexagon is described from a frame, and each run has a one-frame red count beside its sparkle count.
  3. *Miss cases:* the count picks up trails (present across frames) or a red marble in motion and is read as hexagons; misses with no flash are left out.
  4. *Reads:* `screenshots/finish_frames/*`, every run with a `before.png` and two or more frames.
  5. *Check:* the report lists every run, finishes and misses both, and says which counts come from a red marble rather than a hexagon.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** the reading ran before the `TASK-OPEN` line (it was scope-finding; no file was edited). Per run, max one-frame red pixels / max sparkles:
  - **Single-marble finishes:** KN6F459ZR3 0 / 33, KN6F459ZR3_s41 0 / 24, THIIEUH35Z 0 / 18, DLYQPCH46H/run_4 0 / 32, PROBOOK12 0 / 30.
  - **Single-marble misses:** GXR7RV5NA6 345, VVM6SAOXDQ 297, NWU82O8GRJ 217, I4BA3N5V6Y/run_3 200, FU7DXC9T56 199, 8I8EVU4NCU/run_3 189, I4BA3N5V6Y 142, XX9AWVHQZO 98, 8I8EVU4NCU 74, APLTUT69RU 32, W8IEN7MG92 17, SCP9H7XYEX 6, VNK2IQ37MU 0, I4BA3N5V6Y/run_1 0, run_2 0, 8I8EVU4NCU/run_1 0, run_2 0 (all 0 sparkles). W8IEN7MG92's marble stops on the goal rail's near end, on track, so 17 may not be a hexagon.
  - **Multi-marble boards (counts include red marbles moving):** OGIVHBFRK7/run_2 196 (finished, 167 sparkles), TKLKNFJGT3 36 (finished, 102), OGIVHBFRK7/run_1 177, 5H5NQ7HT7D/run_2 1,645, 8D9CU5AEY3 756, 8WL7RXS9H4 350, Q7AE2SM7MC 333, YFUGDSMDUH/run_1 163, ZJR47DUFFX 144, 5H5NQ7HT7D/run_1 128, 54TI3KWGTH 118.
- **What changed:** this report and the ledger only.
- **Evidence:** the counts above; `GXR7RV5NA6` crops `after_02` (silver marble) and `after_03` (red marble, hexagon outline) looked at.
- **Decisions made inside the task:** call a count a hexagon only on single-marble runs, since a multi-marble board's marbles are coloured and one may be red.
- **For the record:**
  - `plan.md` #30: answered s52-t3 -- the red hexagon marks a lost marble where it comes to rest; it lasts about one frame, so it is a positive miss signal that is caught on about two of three single-marble misses at 0.4 to 0.8 s spacing and never on a finish (5 of 5). Not a negative signal, and not usable on multi-marble boards without a shape test.
  - `plan.md` item 24 (c): measured offline; worth wiring only beside the sparkle count, as a miss confirmation, and only for one-marble courses.
- **Friction:** the routine says reading to work out the scope comes first; here the reading answered the question before the task was opened. Recorded so the open commit is not read as preceding the work.
- **Next:** s52-t4, item 24 (b), the trail-end reading -- or renders, if the Mac's memory is freed.
