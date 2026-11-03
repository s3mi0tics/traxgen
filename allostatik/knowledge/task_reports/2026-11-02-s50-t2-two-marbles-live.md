# s50-t2 — the two-marble board, live

**Status:** DONE

**In one paragraph:** A launch pad with two valid connections releases **two marbles, together**. On `OGIVHBFRK7`, in both runs, every one of the three pads left two trails, one into each of its goal rails, six in all. In run 2's first frame after play the two marbles of every pair sat at the same point on their equal routes (both at the second X-intersection), and one frame (0.73 s) later all six were at their goals: no pad sent one marble ahead of the other, whichever two ports it used. Run 1 also showed something the record needed: its frames came 2.06 s apart, the finish burst fell between them, and the finish check read `not_finished`, 0 sparkles, on a run whose six trails all end in goals. That is plan item 24's false negative, seen live, and its trigger for a trail-based backup.

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

## Close

- **What happened:** uploaded `OGIVHBFRK7` (manifest `screenshots/ring_board/two_marbles_run2.json`), one probe session, `--link --runs 2`. Run 1: attempt 1 landed on the build tutorial and was refused (distance 2.115); attempt 2 loaded. Run 2 loaded first try. Emulator down at the end. Before this task, a `probe_finish_frames --help` I ran to read its options was taken as a share code and booted the emulator; I stopped it, killed the emulator cleanly, and deleted its `--help` frame folder before looking at the frames, so that boot's screens are not known.
- **What changed:** nothing in the repo.
- **Evidence:**
  - run 1 `frames.json`: `validity: active`, `finish: not_finished`, `finish_sparkles: 0`, `median_interval: 2.06`, 5 frames, `settled: true`. `after_00.png`: all six marbles at their goals, six trails. `after_04.png`: six trails into goals, marbles gone.
  - run 2 `frames.json`: `validity: active`, `finish: finished`, `finish_sparkles: 167`, `finish_peak: 5486`, `median_interval: 0.73`, 10 frames. `after_00.png`: six marbles in flight, each pair level at its second X-intersection. `after_01.png`: all six at their goals. `after_09.png`: six trails, each into its own goal rail.
  - Trail colours by route were the same in both runs (port 0's red on both pads that used it).
  - Menu waits 81.0 s, 78.2 s, 19.5 s. #21 count: 1 boot, 3 load attempts, 2 good (the bad one caught).
  - Mac after: memory free 42%; swap-ins 152,438,453, up 2,718,181 pages over the session: it was paging throughout (#70).
- **Declared outcomes against what happened:** 2 marbles per pad, both trails into their goals: held, all three pads, both runs. `finish: finished`: held in run 2, **not** in run 1 (frames too far apart). Order: no prediction; they left together.
- **Decisions made inside the task:** read the order by eye from the frames rather than writing a trail reader, since run 2's frame 00 settles it at sight.
- **For the record:**
  - #27's first half answered: a launch pad releases one marble per valid connection, all at once (two ports: three pads, two runs, level in the one frame that caught them in flight; at 0.73 s a frame, a lead of more than about a tenth of a second would show as one marble a quarter tile ahead -- an estimate from the marbles' travel between frames 00 and 01).
  - D104's guard stays: with simultaneous release, which marble reaches a switch first depends on route length and physics, which the checker does not model; but it could now be predicted from the routes rather than from release order.
  - Item 24: false negative seen live. `OGIVHBFRK7/run_1` read not finished at 0 sparkles with frames 2.06 s apart, all trails into goals. Its trigger fired ("a burst and a trail disagreeing").
  - Trail colours were stable across the two runs of one boot (s45 saw them change run to run).
  - `probe_finish_frames` takes any argument as a share code, `--help` included, and boots the emulator to try it.
- **Friction:** reading a script's options with `--help` started a live session; read the source's argument handling instead.
- **Next:** #26, or the close.
