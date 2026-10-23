# s44-t3 — a marble loads only where the starter has a valid connection

**Status:** DONE

**In one paragraph:** The starter now counts only *valid connections*: a neighbour on its plate that takes the marble in from that side. That follows Colby's observation that the app loads a marble only there. A lone starter, or one whose only neighbour is a goal turned away, reads INVALID with "no marble loads". A valid goal beside a wrong-way goal now reads VALID (it read UNMEASURED before). Two valid connections still read UNMEASURED. The 3 half-hole misses stay *connections*: the marble rolls in and isn't caught, so they read as a dead end at the goal's doorway.

## Open (written before the work)

- **Goal:** Make the starter count only valid connections, per Colby's observation: "a marble automatically loads when there is a valid connection to the start (not a valid track, a valid connection)."
- **Scope:** `traxgen/track_graph.py`, `tests/test_track_graph.py`.
- **Budget:** 20 minutes. No renders.
- **Done check:**
  1. *Step:* the starter's routes are the sides whose neighbour accepts the marble from that side and is on its plate; none reads INVALID with "no marble loads"; more than one reads UNMEASURED.
  2. *True after:* (a) a valid goal beside a wrong-way goal reads VALID; (b) a lone wrong-way goal reads INVALID, "no marble loads"; (c) two valid goals still read UNMEASURED; (d) every t2 record test still passes.
  3. *Miss cases:* the filter still counts tile presence, so (a) reads UNMEASURED; the filter counts a goal on an uncompleted half-hole as no connection, so the 3 misses read "no marble loads" (they are connections: the marble rolls and isn't caught).
  4. *Reads:* the pytest and ruff output.
  5. *Check:* `uv run pytest -q` passes with tests for (a), (b), (c) and one asserting the 3 misses are dead ends at the goal's doorway, not "no marble loads"; ruff clean on both files.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:**
  - Added `Through.accepts`, so "no way in here" (a goal turned away) is distinct from "taken in, no way on" (a goal on an uncompleted half-hole).
  - The starter filters its sides by `accepts`.
  - Three mutants were run. One survived: the mid-route "no way in" check, which starter-and-goal courses can't reach. A test that routes through an injected test piece into a wrong-way goal now kills it.
- **What changed:** `traxgen/track_graph.py`, `tests/test_track_graph.py`.
- **Evidence:**
  - `task_check`: in scope.
  - Suite: `1121 passed, 1 deselected`.
  - `ruff check` and `ruff format`: clean.
  - Mutants (failing tests out of 19): starter counts any neighbour 2; half-hole goal treated as no connection 1; no-way-in unchecked on route 1, after the added test (0 before).
- **Decisions made inside the task:**
  - "Valid connection" means the neighbour is on its plate's footprint and accepts the marble from that side. Its half-hole status doesn't matter, because the half-hole misses rolled (s43 frames: no finish burst, but a run).
- **For the record:**
  - `decisions.md`, in the graph-checker row: a marble loads only where the starter has a valid connection (Colby, s44, observed in the app; not a render measurement).
  - `plan.md`: replace the open question "does the app let you choose where marbles sit" with "with two or more valid connections, where do the marbles go?" Cheap test: one course, a starter with two valid goal rails, watched once.
- **Friction:** none.
- **Next:** the session close.
