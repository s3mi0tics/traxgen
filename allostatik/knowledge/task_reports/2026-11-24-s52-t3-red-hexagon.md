# s52-t3 — the red hexagon (#30, item 24 (c)), from frames on disk

**Status:** OPEN

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
