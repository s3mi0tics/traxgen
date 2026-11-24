# s52-t10 — where a balcony sits in world coordinates (#4), from the corpus

**Status:** DONE

**In one paragraph:** #4 is answered from the corpus, position only. A wall runs straight between its two stacker towers, 2, 3 or 4 cells apart, and has that many columns. A balcony at `column` sits beside the wall line, touching line cells `column` and `column + 1`, on the side `wall_side` names: `p1 + column * dir(u) + (dir(u+1) if EAST else dir(u-1))`, with `u` the direction from tower 1 to tower 2. Every one of 709 balcony-to-other rails then has a span its kind allows (707 also point along both ends' sides), and so do all 1,034 balcony-to-balcony rails; swapping EAST and WEST drops that to 46 of 709. Height is not pinned (each row is probably 0.72, one full tile). On the way the reader found the validator's straight-rail and wall lengths off by one against the corpus, which s52-t11 takes.

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

## Close

- **What happened:** a background reader (read-only, scratchpad `agentD/`). Re-run here, `test_rule.py best`: `no-balcony {span_ok 16799, ok 16793, bad 17, span_bad 11}`, `balcony-other {span_ok 709, ok 707, bad 2}`, `balcony-balcony {span_ok 1034, ok 1034}`; the two misses are `P8DI6A9YE4` rails 21 and 41, balcony to a STACKER_TOWER_CLOSED tile, span right and direction wrong -- the same course misses direction on a non-balcony rail too. `swapped` lists failures from its first course on (the reader's table: 46 of 709 full). `val.py` (the validator's own `_check_inventory_budget_rails` over 640 courses): `440 Counter({'STRAIGHT rail with invalid span: distance 4': 2522})`. Wall towers measured here in world cells (retainer world position + local position): 1,161 walls at 2 (106), 3 (481), 4 (574), none else; the validator's local-only distance equals that on 325 of 1,161 and runs 0 to 6.
- **What changed:** this report and the ledger only.
- **Evidence:** the re-run lines above.
- **Decisions made inside the task:** none.
- **For the record:**
  - `plan.md` #4: answered for position s52-t10 -- the rule above, 709/709 spans, 1,034/1,034 balcony-to-balcony; a rail end on a balcony is always at local (0,0) (2,777 of 2,777). Height open: rows look 0.72 apart (slope 0.725, n=382), zero point not pinned; columns 0 and 3 never use rows 5-7, unexplained. The validator can now give balcony-touching rails a span check instead of skipping them.
  - The rail-geometry rule the reader established first agrees with s52-t9: a straight rail leaves along `HEX_DIRECTIONS[(2 - side_hex_rot) % 6]` (16,793 of 16,810).
  - Validator defects: s52-t11.
- **Friction:** none.
- **Next:** s52-t11, the validator's straight-rail and wall lengths.
