# s52-t8 — how retainer IDs are assigned (#5), from the corpus

**Status:** OPEN

## Open (written before the work)

- **Goal:** fold a background corpus reader's answer to #5 into the record, after re-running the scripts its main claims rest on.
- **Scope:** none beyond the ledger and this report; scripts stay in the scratchpad.
- **Budget:** 10 minutes, no renders.
- **Done check:**
  1. *Step:* re-run `ret.py` (parse tally), `an.py` (references and uniqueness) and `an5.py` (baseplate ID formula).
  2. *True after:* the tally, the dangling-reference count and the formula's mismatch count come from runs in this task.
  3. *Miss cases:* claims from scripts not re-run are reported as verified.
  4. *Reads:* the corpus; `traxgen.parser.parse_course` and `traxgen/domain.py` at HEAD.
  5. *Check:* the report separates figures re-run here from figures taken from the reader.
- **Outcomes declared before any live run:** none, because there is no live run.
