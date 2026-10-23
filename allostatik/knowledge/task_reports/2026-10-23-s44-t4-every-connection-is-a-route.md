# s44-t4 — every valid connection on the starter is a route

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Follow every valid connection on the starter as its own route, per Colby: "once you have two valid connections to the starter there are two pathways you have to measure."
- **Scope:** `traxgen/track_graph.py`, `tests/test_track_graph.py`.
- **Budget:** 15 minutes. No renders.
- **Done check:**
  1. *Step:* remove the starter's more-than-one-connection UNMEASURED case; the walk follows each valid connection.
  2. *True after:* (a) two valid goals on one starter read VALID; (b) one valid goal plus a connection whose route dead-ends reads INVALID at that route's doorway; (c) all earlier tests pass.
  3. *Miss cases:* the walk stops after the first route that ends in a goal, so (b) reads VALID.
  4. *Reads:* pytest and ruff output.
  5. *Check:* `uv run pytest -q` passes with tests for (a) and (b), where (b)'s dead-end route is the second one walked (sides are walked in order, so the goal is on the lower side); ruff clean.
- **Outcomes declared before any live run:** none, because there is no live run.
