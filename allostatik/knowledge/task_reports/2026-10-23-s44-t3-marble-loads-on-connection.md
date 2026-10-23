# s44-t3 — a marble loads only where the starter has a valid connection

**Status:** OPEN

**In one paragraph:** _written at close_

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
