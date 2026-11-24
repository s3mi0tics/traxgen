# s52-t18 — search for multi-piece courses the checker calls VALID (item 2, vision.md "Generation")

**Status:** OPEN

## Open (written before the work)

- **Goal:** a search that grows a route outward from a launch pad on the standard square with the measured pieces (CURVE, CROSS, GOAL_RAIL), keeps only courses `check_course` calls VALID and `validate` passes against PRO_VERTICAL_STARTER_SET, and emits a handful of them as candidate courses for rendering.
- **Scope:** `scripts/search_routes.py` (new), `tests/test_search_routes.py` (new). A script, not the generator: the generator's API is not decided here.
- **Budget:** 40 minutes, no renders; uploads only of the final candidates.
- **Done check:**
  1. *Step:* depth-first search from each buildable, on-screen pad cell; at each step place a goal rail (end) or a curve or cross at a rotation that takes the marble in.
  2. *True after:* the search returns courses of 1 to 6 pieces between pad and goal; every one is VALID by `check_course` and error-free by `validate`; a test re-checks the emitted ones.
  3. *Miss cases:* a course is emitted whose pad has a second accepting neighbour the search did not plan for (the checker catches it -- the test must run the checker, not trust the search); a piece under the toolbar; inventory exceeded.
  4. *Reads:* `track_graph.PIECE_RULES` and its track tables; `ring_board.is_buildable`, `under_toolbar`; `validator.validate`.
  5. *Check:* the test builds every emitted candidate and asserts `check_course(...).status is VALID` and no ERROR from `validate`, and that at least one candidate uses each of CURVE's two tracks and the CROSS.
- **Outcomes declared before any live run:** none here (renders wait on the Mac's memory); each candidate's checker verdict is its declared prediction for its first render.
