# s50-t1 — a board of two-connection launch pads

**Status:** DONE

**In one paragraph:** `scripts/probe_two_marbles.py` builds a goal-ringed board on the standard square with three tests, one per pair of a rotation-0 launch pad's ports ({0,2}, {2,4}, {0,4}). Each used port runs through two straight X-intersections into its own goal rail, the third port faces an empty cell, and each test alone checks VALID. A run of three fits only one test on the standard square, so the default is two. Nothing was uploaded; t2 plays it.

## Open (written before the work)

- **Goal:** build, offline, a goal-ringed board on the standard square where each test is one launch pad with exactly two valid connections, each route running through the same number of straight X-intersections into its own goal rail, so that in the frames a trail that leads the other means its marble left first.
- **Design:** one test per pair of the launch pad's ports, {0,2}, {2,4} and {0,4} at rotation 0, so a port-order rule (if there is one) shows as a pattern across the three; the third port faces an empty cell. Equal route lengths so travel time cancels; the run length is a flag (default 3, which s48-t4 found long enough to separate two marbles, and six too long). Checked by `track_graph.check_course` per test: each test alone must read VALID, since the marble guard only fires with a switch.
- **Scope:** `scripts/probe_two_marbles.py`, `tests/test_probe_two_marbles.py`.
- **Budget:** 45 minutes; no uploads (t2 uploads).
- **Done check:**
  1. *Step:* the script and its offline test.
  2. *True after:* `probe_two_marbles --build-only` prints a board whose every test is one launch pad facing exactly two accepting cells, with equal-length routes, every cell buildable and off the toolbar, and each test alone checked VALID.
  3. *Miss cases:* a pad's third port faces a piece (a third marble); the two routes differ in length; a test reads VALID only because the checker skipped it (UNMEASURED); a cell sits under the toolbar or on an uncompleted half-hole; tests too close, so one test's marble enters another's piece.
  4. *Reads:* `tests/test_probe_two_marbles.py`, run by pytest against the script's `layout`.
  5. *Check:* the test asserts, for every test of the built board, two accepting neighbours and one empty, equal run lengths, buildable and visible cells, spacing to other tests, and `check_course` VALID on the test alone; the suite reports the count passed.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** wrote the script and its test. The first layout tried tests strictly in order and fitted one of three at a run of 3; letting each cell take any unplaced test still fitted one at 3, and all three at 2.
- **What changed:** `scripts/probe_two_marbles.py`, `tests/test_probe_two_marbles.py`.
- **Evidence:** `s50-t1: in scope -- 2 files changed since open commit bcd138b, all declared`; 8 new tests pass; full suite 1234 passed; ruff clean on both files. Mutants: a wrong X-intersection rotation failed 1 test (the accepting-ports test); using all three ports errored 7 (layout no longer fits), so that one is caught by the fit, not by the third-port test directly.
- **Decisions made inside the task:** default run 2, since 3 fits one test; the class is `PadTest`, not `Test`, so pytest doesn't try to collect it.
- **For the record:** the standard square holds three two-route launch-pad tests at two X-intersections per route, one at three (`test_a_run_of_three_does_not_fit_all_three`).
- **Friction:** none.
- **Next:** t2, upload and play the board twice by link, swap-ins and memory-free percentage read before and after.
