# s52-t19 — play the GOAL_BASIN board (resumes s52-t17, stopped on memory)

**Status:** OPEN

## Open (written before the work)

- **Goal:** play `6ZX7WEFRTJ` once by link and score it against s52-t17's declared outcomes.
- **Scope:** none beyond the ledger and this report (frames go to `screenshots/`, gitignored).
- **Budget:** two attempts, 15 minutes.
- **Done check:**
  1. *Step:* `probe_finish_frames --link 6ZX7WEFRTJ`, then `read_trail_ends` against `screenshots/ring_board/goal_basin.json`, and a look at the frames.
  2. *True after:* per rotation, marble loaded or not and where its trail ends; the board's finish verdict.
  3. *Miss cases:* the load lands on a non-course screen and is read (D102's check refuses those); a trail claimed by the wrong pad.
  4. *Reads:* the run's frames and `frames.json`.
  5. *Check:* the report scores all six rotations against "1, 3, 5 catch; 0, 2, 4 load no marble" (s52-t17).
- **Outcomes declared before any live run:** as s52-t17: rotations 1, 3, 5 catch; 0, 2, 4 load no marble.
