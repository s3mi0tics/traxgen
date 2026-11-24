# s52-t8 — how retainer IDs are assigned (#5), from the corpus

**Status:** DONE

**In one paragraph:** Mostly answered. Every ID in a course is unique across layers, retainer tiles and balconies -- one namespace -- and every one of 51,755 references (rails, both pillar ends, both wall tower fields) resolves inside its course. Two schemes fill it. A baseplate's `layer_id` encodes where the plate sits, not when it was made: 129 plus its index on a square spiral over `world_hex_position`, reproducing all 126 baseplate IDs in the corpus with no exception (traxgen's own `FLW4TMLP5V`, with ID 100, is the one course that does not follow it). Everything else -- towers, DOUBLE_BALCONY, LIGHT_BASE, balconies, LARGE and SMALL layers -- takes the next value of one counter that starts at 1000, in what looks like creation order. So s40's pillar naming 1000 in PROBOOK12 is the first counter value, most likely a stacker tower. Still open: a third pattern in 12 courses (LARGE_LAYER IDs 0, 1, 2 ...), what the counter's gaps are, and whether the app requires 1000+ or only uniqueness.

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

## Close

- **What happened:** a background reader (read-only, scratchpad `agentA/`) wrote `ret.py` and `an.py` to `an7.py`. Re-run in this task: `ret.py` -> `files 808 parsed 640 skipped 168` (v2 77, v5 60, v7 31, every skip a `ValueError` from `parse_course`); `an.py` -> references rail 37,108 (layer 31,542, balcony 2,777, tile 2,789), pillar lower 6,743 (layer 5,480, tile 1,263), pillar upper 6,743 (layer), wall towers 1,161 + 1,161, `dangling Counter()`; `an5.py` -> `exact spiral formula v2: checked 126 mismatch []` (its first formula mismatched; the second is the reader's corrected one). Taken from the reader, not re-run: ID ranges per carrier (layers 0-2009, tiles 1000-2038, balconies 1005-2036; no tile or balcony below 1000), 0 duplicate IDs within any course, the counter's lowest value 1000 in 374 of 512 courses, stacked retainer tiles larger-than-below in 2,974 of 2,974, and the 12 courses with LARGE_LAYER IDs from 0.
- **What changed:** this report and the ledger only.
- **Evidence:** the three re-run outputs above.
- **Decisions made inside the task:** none.
- **For the record:**
  - `plan.md` #5: mostly answered s52-t8 -- one namespace per course, no dangling references (51,755); baseplate IDs are 129 + a square-spiral index of the plate's `world_hex_position` (126 of 126); all other carriers draw from one counter from 1000, creation-ordered. Open: the 12 courses with LARGE_LAYER IDs 0, 1, 2 ...; counter gaps (deletions?); whether the app requires 1000+.
  - `plan.md` #5's s40 note: PROBOOK12's pillar naming 1000 fits the counter's first value, a tower or other retainer tile; PROBOOK12 is not in the corpus, so not checked directly.
  - For the generator (no change now): traxgen's own baseplate uses `generator._LAYER_ID` = 100, which no app-saved course does; the app accepted it (`FLW4TMLP5V`), so uniqueness may be all it checks. Worth knowing before the generator writes towers.
  - `traxgen/domain.py`: `PillarConstructionData.lower_layer_id` also names towers and balcony pieces (1,263 of 6,743); the name undersells it.
- **Friction:** none.
- **Next:** the curve and balcony readers.
