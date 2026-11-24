# s52-t15 — which way the marble travels through each piece's sides, from rail heights (#7)

**Status:** OPEN

## Open (written before the work)

- **Goal:** fold a background corpus reader's direction-of-travel tables into the record, after re-running its calibration and table.
- **Scope:** none beyond the ledger and this report (the per-side table is appended).
- **Budget:** 10 minutes, no renders.
- **Done check:**
  1. *Step:* re-run `conv.py` (height unit calibration) and `sides.py` (per-side table) and diff the table.
  2. *True after:* the convention and the table come from runs in this task.
  3. *Miss cases:* a unit chosen because it looks tidy rather than because out-only and in-only pieces calibrate on it; level rails counted as either direction.
  4. *Reads:* the reader's `rails.jsonl` (16,097 rails with both ends on layer cells, from `mine_ports` helpers).
  5. *Check:* the report quotes the STARTER and GOAL_BASIN calibration lines for each candidate unit and the diff is empty.
- **Outcomes declared before any live run:** none, because there is no live run.
