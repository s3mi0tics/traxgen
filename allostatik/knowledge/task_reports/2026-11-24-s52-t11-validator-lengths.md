# s52-t11 — the validator's straight-rail and wall lengths, against the corpus

**Status:** OPEN

## Open (written before the work)

- **Goal:** make the validator's STRAIGHT-rail and wall length tables match the corpus (cell distance 2, 3, 4 for SHORT, MEDIUM, LONG), and measure walls in world cells.
- **Scope:** `traxgen/validator.py`, `tests/test_validator.py`, `docs/refs/rail-specs.md`.
- **Budget:** 40 minutes, no renders.
- **Done check:**
  1. *Step:* change both tables; wall distance through the retainers' world positions (as rails already do); update the tests that pinned {1,2,3}; correct the reference.
  2. *True after:* over the 640 parseable corpus courses the validator reports no "invalid span" on any STRAIGHT rail, and every wall maps to a length.
  3. *Miss cases:* tests are edited to pass without one asserting distance 1 is now invalid; walls still use local positions for cross-retainer towers; the corpus check runs on a subset.
  4. *Reads:* the corpus; s52-t10's wall-distance count (2: 106, 3: 481, 4: 574 of 1,161) and the 2,522 distance-4 rails.
  5. *Check:* full suite passes; a corpus sweep prints 0 invalid-span rails and 0 unmapped walls over 640 courses, and the same sweep at the open commit prints 2,522 and a nonzero unmapped count.
- **Outcomes declared before any live run:** none, because there is no live run. Prediction: walls at world distance 2/3/4 map to SHORT/MEDIUM/LONG with none unmapped; the wall-budget findings on the corpus change.
