# s47-t3 — rings stay out from under the toolbar; frame folders are never overwritten

**Status:** DONE

**In one paragraph:** on the standard square, the ring board now knows where the app draws each cell. The map is the cell-to-pixel fit from s46-t3, and it is good to a fraction of a cell: drawn over s46's frame, it lands on the pieces. The ring board also knows where the toolbar sits, and it places no ring cell under the toolbar or clipped by it. The map gives back s46's reading exactly: the only goals it calls hidden are the two that read hidden. Six rings still fit, so keeping the toolbar clear costs no plate. The finish probe no longer overwrites a code's frames: a second run goes to the next unused `run_<n>`.

## Open (written before the work)

- **Goal:** the rest of plan item 22. `ring_board` on the standard square places no ring cell where the app's toolbar covers it, and `probe_finish_frames` never writes into a folder that already holds frames.
- **Scope:** `traxgen/ring_board.py`, `tests/test_ring_board.py`, `scripts/probe_finish_frames.py`, new `tests/test_probe_finish_frames.py`.
- **Budget:** 60 minutes, no renders.
- **Done check:**
  1. *Step:* (a) a measured map from standard-square cells to screen pixels, plus the toolbar's rectangles, and ring placement that skips hidden cells; (b) a folder chooser for the probe that moves to the next unused `run_<n>` when a folder already has frames.
  2. *True after:* (a) every cell of the curve ring board lands outside the toolbar under the map; the map reproduces s46-t3's reading, so the two goals that read hidden (rotation 2, sides 3 and 4) are hidden under it and the 28 goals that read visible are not; (b) a second probe run of the same code lands in a new folder, and the first run's files are untouched.
  3. *Miss cases:* (a) the map or rectangles are wrong, so the filter hides nothing (the old board passes) or hides everything (no board fits); (a) the filter is applied only to the centre, not to every ring cell; (b) a run with `--runs 1` still writes to `<code>/` when it already has frames; (b) `--runs N` rewrites `run_1`.
  4. *Reads:* `screenshots/ring_board/CURVE.json` and s46-t3's reading (hidden = rotation 2, sides 3 and 4); `screenshots/finish_frames/5H5NQ7HT7D/before.png`, which shows the toolbar, for the rectangles; the chooser's answer on a `tmp_path` tree.
  5. *Check:* `tests/test_ring_board.py` asserts the s46 hidden set exactly from the old ring positions, and that the new board has no hidden cell. `tests/test_probe_finish_frames.py` asserts the chooser on folders that do and don't hold frames. Each fails under a deliberate break: a zero margin and an empty rectangle set for (a), and an always-`<code>/` chooser for (b).
- **Outcomes declared before any live run:** none, because there is no live run. Declared before computing it: the standard square still fits six rings with the bottom corner excluded. If it doesn't, the task stops: whether a ring board may use a fifth plate is Colby's call.

## Close

- **What happened:** measured the toolbar's two rectangles on an empty-board frame, took the s46 fit as `STANDARD_SQUARE_SCREEN`, and added `under_toolbar` to ring placement (standard square only, where the map is measured). Added `frame_folder` to the probe.
- **What changed:** `traxgen/ring_board.py`, `tests/test_ring_board.py` (+3 tests), `scripts/probe_finish_frames.py`, new `tests/test_probe_finish_frames.py` (5 tests).
- **Evidence:** `s47-t3: in scope -- 4 files changed since open commit 396d017, all declared`. Suite: 1174 passed. The ring board's new cells are drawn between y=201 and y=740, against the tab row at 818. Breakages: no toolbar rectangles (1 failed), the filter on the centre only (1), always `<code>/` (2), always `run_1` (1), zero margin (16 passed at first: s46's hidden goals sit inside the toolbar with no margin at all; after adding a test for the clipped launch pad, 1 failed).
- **Decisions made inside the task:** a cell is hidden within 45 px of the toolbar, because s46's launch pad 38 px above the tab row is visibly clipped. The screen map applies only to the standard square, because the camera framing for other plate sets is unmeasured; on any other set, nothing is filtered. The curve board as `ring_board(CURVE)` now builds it is no longer `TKLKNFJGT3`: its rings moved.
- **For the record:** plan item 22 is done. `screenshots/finish_frames/5H5NQ7HT7D/before.png` (top level) is a build-tutorial frame with an empty board, not the goal-less ring board. `read_ring_board`'s default folder for the goal-less board would read it; s46's reading used `run_1`. The camera frames the plates, not the pieces: an empty board and a full one sit in the same pixels (seen again, after s42-t4).
- **Friction:** the done check declared that a zero margin would fail a test, before checking that any test could tell. It took one more test to make the declaration true.
- **Next:** s47-t4: the X-intersection ring board, built and played on the emulator.
