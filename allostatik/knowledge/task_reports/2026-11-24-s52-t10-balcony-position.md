# s52-t10 — where a balcony sits in world coordinates (#4), from the corpus

**Status:** OPEN

## Open (written before the work)

- **Goal:** fold a background corpus reader's balcony rule into the record, after re-running its rule test and its validator count.
- **Scope:** none beyond the ledger and this report; scripts stay in the scratchpad.
- **Budget:** 15 minutes, no renders.
- **Done check:**
  1. *Step:* re-run `test_rule.py best` and `swapped`, `val.py`, and a wall-distance count.
  2. *True after:* the hit rates and the validator counts below come from runs in this task.
  3. *Miss cases:* the rule's hit rate is reported without a rival rule's rate beside it; the validator claim is passed on without running the validator.
  4. *Reads:* the corpus; `traxgen/validator.py` at HEAD.
  5. *Check:* the report quotes the re-run lines for the rule, a rival, the rail-span count and the wall distances.
- **Outcomes declared before any live run:** none, because there is no live run.
