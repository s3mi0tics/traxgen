# s50-t1 — a board of two-connection launch pads

**Status:** OPEN

**In one paragraph:** _written at close_

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
