# s46-t3 — the ring board, read per goal on the emulator

**Status:** DONE

**In one paragraph:** The emulator played the curve's ring board, and the harness read which side each ring's marble left by. All six rings agree with the curve rule: rotations 1, 2, 3 and 5 left by sides 4, 0, 3 and 1, and rotations 0 and 4 loaded no marble. So side 1 is now measured, not only seen on Colby's phone. The plan to read the finish sparkle per goal failed: on a board with several rings the app throws one burst over the middle of the board. The reader reads the marbles' trails instead, which was Colby's suggestion.

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

## Close

- **What happened:**
  - *First live attempt:* adb reached Colby's Pixel 6, which was plugged in over USB, because the harness names no device. It failed at the read-only device checks, so nothing touched the phone, but the evidence step saved the phone's log to `screenshots/device_evidence/20261101-205019.txt` (gitignored).
  - *Every later run:* `ANDROID_SERIAL=emulator-5554`.
  - *Goals board `TKLKNFJGT3`:* failed twice at first, once on a loading screen and once on `device offline`. It played on the next boot as the second course: active, finished, burst peak 4,209.
  - *The burst:* one celebration over the middle of the board, rising off its top (after_03), not at any goal.
  - *Goal-less board `5H5NQ7HT7D`:* played active, with the stop square shown and no burst. That answers #28: a board without goals plays.
  - *A warm-up run* landed on the build tutorial and overwrote the good goal-less frames, because `probe_finish_frames` reuses a code's folder. The goal-less board was rerun with `--runs 2` (run_1 needed a second attempt).
  - *The reader:* rewritten from bursts to trails.
- **What changed:** `traxgen/ring_board.py` (a `goals=False` board), `tests/test_ring_board.py`, `scripts/ring_board.py` (`--no-goals`), `scripts/read_ring_board.py`, `tests/test_read_ring_board.py`.
- **Evidence:**
  - `read_ring_board CURVE --without-goals .../5H5NQ7HT7D/run_1`: fit residual 0.30 px; all six rings agree. Trail pixels on the exit side: 57, 324, 328 and 467. The largest spill into a wrong side is 176 (rotation 3, side 4).
  - The same against run_2: identical.
  - With the rule shifted one side: 4 DISAGREE, exit 1.
  - Suite: 1150 passed. `task_check s46-t3`: in scope, 5 files.
- **Declared outcomes against what happened:** the four exits held, and rotations 0 and 4 loaded nothing. The rotation-2 ring is half under the toolbar and still read correctly (its exit side is visible; sides 3 and 4 are flagged hidden). The stop square showed on the goal-less board, as declared.
- **Decisions made inside the task:**
  - Read trails, not bursts.
  - Fit the ring positions without the smallest pixel group. The half-hidden ring dragged the fit from 0.3 px to 3.2 px, about half a cell.
  - Count trail pixels at full resolution, 0.35 to 1.3 cells from a ring's centre.
  - The reading is the side with the most trail pixels: a floor (30) can't separate a weak true trail (57) from a strong spill (176).
- **For the record:**
  - #29 answered (several finish lines play).
  - #28 answered: a goal-less board plays, here and on Colby's phone. s42-t4's pale button was a single-launch-pad course; the difference is unexplained.
  - The curve's side 1 is measured closed.
  - The finish burst is one per board, not per goal. Observation: the burst was assumed local because every earlier course had one goal.
  - Harness weakness: adb with no device named reached a USB-attached phone. The fix is `ANDROID_SERIAL` or `-s` in `AdbContext`.
  - `probe_finish_frames` overwrites a code's earlier frames.
  - The toolbar hides the bottom corner of the standard square; the ring board should avoid it.
- **Friction:** the 90-minute budget ran over, to about 2 hours, because of two failed boots and the switch from bursts to trails.
- **Next:**
  - Pin adb to the emulator in the harness.
  - Keep rings out from under the toolbar.
  - Run the ring board on the next piece.
