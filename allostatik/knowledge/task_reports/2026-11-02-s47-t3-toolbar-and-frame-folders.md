# s47-t3 — rings stay out from under the toolbar; frame folders are never overwritten

**Status:** OPEN

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
