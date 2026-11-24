# s52-t14 — every validator rule over 640 app-saved courses

**Status:** DONE

**In one paragraph:** Every schema rule is silent on the corpus: BASEPLATE_COVERAGE, CELL_COLLISION, RAIL_ENDPOINT_MISSING, RETAINER_ID_COLLISION, LAYER_ID_COLLISION, PILLAR_ENDPOINT_MISSING, ROTATION_OUT_OF_RANGE, TILE_INDEX_COLLISION and WALL_ENDPOINT_MISSING report nothing on 640 app-saved courses, so none of them refuses a course the app accepts (this also bears on #11: no rotation outside range in the corpus). The four inventory rules fire as expected, since corpus courses use sets other than Colby's. The one course-level ERROR that fires is MISSING_STARTER_OR_GOAL, on 271 courses, and the rule is right by its own definition but the catalog under it is narrow: those courses start from a DOME_STARTER, an elevator or a lift, and finish in a FINISH_TRIGGER, a FINISH_ARENA or a CATCH, none of which the catalog marks. START_GOAL_CONNECTED warns on 3 (unswept rotation), as designed.

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

## Close

- **What happened:** `scratchpad/allrules.py`, 640 courses. Fired: INVENTORY_BUDGET_TILES 6,321 violations / 593 courses; INVENTORY_BUDGET_STACKERS 853 / 489; INVENTORY_BUDGET_RAILS 1,955 / 468 (no invalid span among them since s52-t11); MISSING_STARTER_OR_GOAL 387 / 271; INVENTORY_BUDGET_STRUCTURAL 385 / 182; START_GOAL_CONNECTED (WARNING) 3 / 3. Silent: the nine schema rules named above. MISSING_STARTER_OR_GOAL broken down: 239 courses with no STARTER, 148 with no GOAL_BASIN or GOAL_RAIL, 5 with nothing but stackers or light bases. In the no-starter courses: DOME_STARTER 98, CANNON 94, ELEVATOR 91, LIFT_SMALL 19, LIFT_LARGE 18, RELEASER_1 7, ZIPLINE_START 6. In the no-goal courses: CATCH 67, FINISH_TRIGGER 53, FINISH_ARENA 49.
- **What changed:** this report and the ledger only.
- **Evidence:** the counts above.
- **Decisions made inside the task:** no catalog change. Which pieces count as starters and goals is the scope question vision.md leaves open ("Beyond the starter set"), so it is Colby's.
- **For the record:**
  - `plan.md` #11: the corpus has no rotation outside range (ROTATION_OUT_OF_RANGE silent on 640 courses); the modulo hypothesis has no case to test there.
  - `plan.md` (new open question, or vision.md's "Beyond the starter set"): `PIECE_CATALOG` marks STARTER as the only starter and GOAL_BASIN, GOAL_RAIL as the only goals; real courses also start from DOME_STARTER (and elevators, lifts) and end in FINISH_TRIGGER, FINISH_ARENA, CATCH. Decide whether the catalog grows past the sets Colby owns.
  - The schema rules now have a cheap regression test available: run them over the corpus. A rule that fires on an app-saved course is suspect.
- **Friction:** none.
- **Next:** the direction-of-travel reader, then the close.
