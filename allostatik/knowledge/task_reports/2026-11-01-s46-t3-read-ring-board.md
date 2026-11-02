# s46-t3 — the ring board, read per goal on the emulator

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** play the curve's ring board on the emulator and have the harness say which finish line each ring's marble reached, reading the app's finish burst inside each goal's own pixels.
- **Scope:** `traxgen/ring_board.py`, `tests/test_ring_board.py`, `scripts/ring_board.py`, `scripts/read_ring_board.py`, `tests/test_read_ring_board.py`.
- **Budget:** 90 minutes; one cold emulator session, two codes.
- **Method:** the same board without its finish lines is uploaded too. `probe_finish_frames --link` plays both in one session, saving the frame before play and every frame after. The goals' pixels are the difference between the two before-frames (s42-t4: removing a goal leaves the camera still). A fit from world cells to screen pixels says which pixel group is which goal. New near-white pixels after play are then counted inside each goal's group.
- **Done check:**
  1. *Step:* the live run, then `read_ring_board`.
  2. *True after:* a per-goal finish reading exists for the curve board, from frames on disk, with each ring's verdict compared to the curve rule.
  3. *Miss cases:* the pixel groups are matched to the wrong goals, and a finish is credited to the wrong side (the fit's residual must be printed, and a burst in a goal the rule says is closed must show as a disagreement, not be dropped); a goal hidden under the toolbar reads "no finish" instead of "can't see"; a burst spills into the neighbouring goal and counts twice.
  4. *Reads:* `screenshots/finish_frames/<code>/` for both codes, `screenshots/ring_board/CURVE*.json`.
  5. *Check:* `read_ring_board` prints one line per ring (rotation, the goal side that burst or none, the rule's side, agree or not, or hidden), the fit's residual, and exits non-zero on any disagreement.
- **Outcomes declared before any live run:** rotations 5, 3, 1 and 2 finish at world sides 1, 3, 4 and 0. Rotations 0 and 4 load no marble, so nothing bursts. The rotation-2 ring sits by the toolbar on Colby's phone and may read hidden. The no-goal board: Colby's phone played goal-less boards (#28); declared here, the stop square shows on it.
