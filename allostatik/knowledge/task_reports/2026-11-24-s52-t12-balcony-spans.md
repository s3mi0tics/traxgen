# s52-t12 — the validator span-checks rails that touch a balcony (#4 applied)

**Status:** OPEN

## Open (written before the work)

- **Goal:** resolve balcony retainers to world cells with s52-t10's rule, so STRAIGHT rails touching a balcony get the span check and the length bucket instead of being skipped.
- **Scope:** `traxgen/validator.py`, `tests/test_validator.py`.
- **Budget:** 30 minutes, no renders.
- **Done check:**
  1. *Step:* add balcony positions to `_resolve_retainer_world_positions`; a test with a wall, a balcony and a rail.
  2. *True after:* over the corpus, STRAIGHT rails touching a balcony are bucketed, and the validator still reports 0 invalid spans.
  3. *Miss cases:* balconies are resolved but the EAST/WEST sides are swapped (the corpus check would show invalid spans); the test passes because the rail is skipped rather than measured.
  4. *Reads:* the corpus; s52-t10's rule and figures.
  5. *Check:* the corpus sweep reports the number of balcony-touching STRAIGHT rails now measured and 0 invalid spans, and the same sweep with WEST and EAST swapped reports invalid spans; the new test fails with balcony resolution removed.
- **Outcomes declared before any live run:** none, because there is no live run. Prediction: every balcony-touching STRAIGHT rail lands on 2, 3 or 4.
