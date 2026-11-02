# s47-t4 — the X-intersection on a ring board, played on the emulator

**Status:** OPEN

## Open (written before the work)

- **Goal:** measure which side a marble leaves the X-intersection (`TileKind.CROSS`, 4 in the set) by, for each of its six rotations, on one ring board played on the emulator and read by `read_ring_board`.
- **Scope:** none in the repo. The manifests and frames go to `screenshots/` (gitignored); the report is always in scope.
- **Budget:** 2 uploads (the board and its goal-less twin); at most 2 probe sessions; 30 minutes of device time.
- **Done check:**
  1. *Step:* upload `CROSS` and `CROSS --no-goals`; play both by link in one probe session, goal-less first; read with `read_ring_board CROSS`.
  2. *True after:* for every rotation, a measured exit side, or "loads no marble", or "hidden", read from trails on frames on disk.
  3. *Miss cases:* the probe lands on the build tutorial or a loading screen, and the frames show no board; the fit pairs rings with the wrong groups (residual over 1 px); a ring reads "no marble" because the run hadn't settled.
  4. *Reads:* `screenshots/ring_board/CROSS*.json`; each run's `frames.json` (settled, stop square); the reader's residual and per-ring peaks; one look at the last frame.
  5. *Check:* `read_ring_board` prints six lines with a residual under 1 px, both runs' `frames.json` say settled with no error, and the last frame, looked at, shows trails where the reader says.
- **Outcomes declared before any live run:** the X-intersection is two straight tracks crossing at one level. A marble that enters an open side leaves by the opposite one, so every ring that loads a marble leaves by world side 2, opposite the launch pad. Four sides are open, so four rotations load a marble and two load none. The serial is pinned to `emulator-5554` and the boot passes `-port 5554` (s47-t1's first live use), so the device checks pass on that serial.
