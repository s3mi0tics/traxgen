# s47-t4 — the X-intersection on a ring board, played on the emulator

**Status:** DONE, with one deviation: read from the goal-less board through s47-t3's screen map, not by `read_ring_board`

**In one paragraph:** the X-intersection is two straight tracks. In its own frame, sides 1 and 4 join, sides 2 and 5 join, and sides 0 and 3 take no marble. On the ring board, rotations 0, 1, 3 and 4 sent their marble straight out world side 2, opposite the launch pad, and rotations 2 and 5 loaded nothing, as declared. The board with goals never loaded in two sessions, so its per-board fit wasn't available. The trails came from the goal-less board, mapped to rings with t3's measured map of the standard square.

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

## Close

- **What happened:** uploaded `8NN7VNHLIA` (goals) and `YFUGDSMDUH` (goal-less). **Session 1:** the goal-less board failed both attempts (an adb timeout on the app launch, then a loading screen the guard refused). The goal board "loaded" onto the build tutorial: an empty board, which the probe recorded as `validity: inactive` with no error and the stop square never shown. **Session 2:** the goal-less board played on its second attempt (active, stop square shown, settled in 5 frames). The goal board failed both attempts on adb timeouts at the app launch. Both sessions' boots passed every device check on `emulator-5554` with `-port 5554`, which is s47-t1's first live use, and session 2's frames went to `run_1`, which is s47-t3's.
- **What changed:** nothing in the repo; frames under `screenshots/finish_frames/YFUGDSMDUH/run_1/` and `8NN7VNHLIA/`, manifests under `screenshots/ring_board/CROSS*.json`.
- **Evidence:** trail pixels per world side, counted between `before.png` and `after_04.png` of `YFUGDSMDUH/run_1` with `read_ring_board`'s own `changed_full`, `side_of` and ring annulus, on `STANDARD_SQUARE_SCREEN`: rotation 0 (entered side 5) `{1: 5, 2: 398}`; rotation 1 (side 4) `{2: 343}`; rotation 2 (side 3) none; rotation 3 (side 2) `{2: 270}`; rotation 4 (side 1) `{1: 10, 2: 320}`; rotation 5 (side 0) none. Looked at: four trails, all running away from their launch pads, and two rings without one.
- **Declared outcomes against what happened:** all held. Four rotations loaded, two didn't, and every exit was world side 2. The serial and port held.
- **Decisions made inside the task:** read the trails without the goal board instead of spending a third session. Each finished ring's trail was 270 px or more against a 30 px floor, and t3's map was fitted on this same plate set. With no goals, this reads the exit direction, not a finish.
- **For the record:**
  - The CROSS rule (D-row): tracks 1↔4 and 2↔5, sides 0 and 3 closed, all four entries measured once.
  - Item 18 fired again, on the link path. `probe_finish_frames`' `load_by_link` reported a build-tutorial screen as `inactive` with no error, and the top-level frames of `5H5NQ7HT7D` (s46) are the same failure. Item 18 should cover the link path and the probe.
  - #21: the first launches were bad in both boots, and in session 2 the later attempts were bad too (adb timeouts on `monkey`): 2 boots, 7 attempts, 1 good.
  - The goal-less board is enough to read a piece's exits when the screen map is measured. That cuts each ring board to one upload and one play.
- **Friction:** the done check named a tool (`read_ring_board`) and not the measurement, so a sound reading by other means reads as a deviation.
- **Next:** s47-t5: the CROSS rule into `track_graph.PIECE_RULES`.
