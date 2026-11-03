# s50-t2 — the two-marble board, live

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** upload s50-t1's board (run 2) and play it twice by link in one probe session, then read from the frames how many marbles each launch pad released and which route's trail led.
- **Mac before the run:** memory free 44%; swap 14,404 of 15,360 MB used; swap-ins 149,720,272 (pages, cumulative). Read again after the run; a large rise means the Mac was paging during it (#70).
- **Scope:** none in the repo. Manifest to `screenshots/ring_board/two_marbles_run2.json`, frames to `screenshots/finish_frames/<code>/` (both gitignored); a scratch reader in the session's scratchpad.
- **Budget:** 1 upload; 1 probe session, `--runs 2`; if both attempts of a run fail, stop and report (#21).
- **Done check:**
  1. *Step:* the live runs and the reading.
  2. *True after:* for each of the three tests, in each run that loaded, the count of trails leaving its launch pad and, where the frames allow, which trail was longer first.
  3. *Miss cases:* a run that never loaded read as "no marbles" (the load guard, D102, and `validity: active` cover it); a trail hidden by another test's trail (tests are 3 apart); a frame taken after both marbles had finished, so the lead can't be seen (then "order: unreadable at this frame rate", not a guess).
  4. *Reads:* each run's `frames.json` and its `after_*.png` frames; the manifest's cells through `ring_board.screen_position`.
  5. *Check:* per run, `frames.json` has no error and `validity: active`, and for each test the reading names the trails seen on each route in the last frame and the earliest frame where the two differ, quoting the frame numbers.
- **Outcomes declared before any live run:** from Colby's s44 description (a marble per valid connection), each launch pad releases **2** marbles, both trails reaching their goal rails, and `finish: finished`. Order: no prediction. If they leave together, the two trails match in every frame; if one leads, the same port should lead in both runs.
