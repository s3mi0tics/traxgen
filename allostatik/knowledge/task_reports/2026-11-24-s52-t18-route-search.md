# s52-t18 — search for multi-piece courses the checker calls VALID (item 2, vision.md "Generation")

**Status:** DONE

**In one paragraph:** The checker can now generate, not only check: a depth-first search from a launch pad, placing a curve, an X-intersection or a goal rail at each step, found 25,825 courses on the standard square with up to three pieces between pad and goal that `check_course` calls VALID and `validate` passes against Colby's set (0 pieces: 270; 1: 1,203; 2: 4,968; 3: 19,384). Five picks between them ride both curve tracks and the cross, and are uploaded as share codes for their first render. Each carries the checker's VALID as its declared prediction. This is vision.md's "Generation" step run for the first time, on the four pieces measured on the emulator.

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

## Close

- **What happened:** `scripts/search_routes.py` (pad at rotation 0 on any buildable, on-screen cell; out of each of its ports; at each step a GOAL_RAIL at `goal_rotation_for(travel)` ends the route, or a CURVE at any of the 4 rotations that take the marble in, or a CROSS at one rotation per way through; no cell reused). Every candidate is built, checked by `check_course` and validated; kept if VALID and no ERROR. 23.5 s at depth 3. Picks, uploaded:

  | pick | pieces | code |
  |---|---|---|
  | gentle_curve | STARTER (-6,4) r0, CURVE (-6,5) r3, GOAL_RAIL (-5,5) r0 | `5O3ZSS2LTE` |
  | sharp_curve | STARTER (-6,4) r0, CURVE (-6,5) r0, GOAL_RAIL (-5,4) r5 | `K755C9FBKM` |
  | cross | STARTER (-6,4) r0, CROSS (-5,3) r0, GOAL_RAIL (-4,2) r5 | `NXRDV4EKOK` |
  | curve_cross_curve | STARTER (-6,4) r0, CURVE (-6,5) r0, CROSS (-5,4) r0, CURVE (-4,3) r1, GOAL_RAIL (-4,2) r4 | `X6XXWZV7FS` |
  | longest (both curve tracks + cross) | STARTER (-6,4) r0, CURVE (-6,5) r0, CURVE (-5,4) r1, CROSS (-5,3) r1, GOAL_RAIL (-5,2) r4 | `QO4BBHN94B` |

  Manifest: `screenshots/ring_board/routes.json`.
- **What changed:** `scripts/search_routes.py`, `tests/test_search_routes.py` (new).
- **Evidence:** `tests/test_search_routes.py` 5 passed (it re-runs the checker and validator on a sample of every emitted route at depth 2, and on each pick); ruff clean. The first test run failed because it expected a three-piece pick from a depth-2 search; the test now asks only for what depth 2 can contain.
- **Decisions made inside the task:** a script, not `generator.py`: the generator's API (palette input, how many results, which to prefer) is Colby's design call. Picks are the first match by length then position -- deterministic, not curated.
- **For the record:**
  - `plan.md` item 2: the checker searched outward for the first time (s52-t18): 25,825 VALID courses up to three pieces from four measured pieces. Five uploaded for first renders: `5O3ZSS2LTE`, `K755C9FBKM`, `NXRDV4EKOK`, `X6XXWZV7FS`, `QO4BBHN94B`. Declared: each finishes. A miss on any is a checker error to chase (physics, a rule, or a side the curve's sharp track cannot take at speed).
  - `vision.md`, *The equation*: "Generation. The same graph, searched outward from the starter" -- first run; the next step is wiring it into `generate --set vertical-starter` once the renders say the checker's VALID means a finish.
- **Friction:** none.
- **Next:** render the five picks and the basin board when the Mac has memory; then the close.
