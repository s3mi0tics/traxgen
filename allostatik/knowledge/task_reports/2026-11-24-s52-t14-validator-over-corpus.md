# s52-t14 — every validator rule over 640 app-saved courses

**Status:** OPEN

## Open (written before the work)

- **Goal:** run `validate()` over every parseable corpus course and name any rule that fires on courses the app accepted for a reason other than inventory.
- **Scope:** none beyond the ledger and this report.
- **Budget:** 15 minutes, no renders.
- **Done check:**
  1. *Step:* `validate(course, PRO_VERTICAL_STARTER_SET)` over 640 courses, counted by rule and severity; break down any non-inventory ERROR.
  2. *True after:* each rule has a count of violations and courses, and each non-inventory ERROR has a named cause.
  3. *Miss cases:* inventory-budget errors (expected: courses use other sets) read as rule defects; a rule with zero hits not reported, so its silence cannot be told from absence.
  4. *Reads:* the corpus; `traxgen/validator.py` and `traxgen/inventory.py` at HEAD (after s52-t11 and t12).
  5. *Check:* the report lists every rule that fired with counts, says which rules fired on none, and names the cause behind each non-inventory ERROR.
- **Outcomes declared before any live run:** none, because there is no live run.
