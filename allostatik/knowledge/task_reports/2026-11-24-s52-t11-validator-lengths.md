# s52-t11 — the validator's straight-rail and wall lengths, against the corpus

**Status:** DONE

**In one paragraph:** The validator's length tables were one short, and its walls were measured in the wrong frame. A STRAIGHT rail or wall's SHORT, MEDIUM and LONG join cells 2, 3 and 4 apart, not 1, 2 and 3: no rail in 640 app-saved courses joins adjacent cells, and 2,522 join cells 4 apart, which the validator called invalid. Walls were measured from local positions only, though in 919 of 1,161 corpus walls the two towers sit on different retainers; the validator could not classify 680 of them and skipped them without a word. Both tables now read {2, 3, 4} and walls are measured through the retainers' world positions, as rails already were. Over the corpus the validator now reports 0 invalid spans and classifies every wall, and its wall-budget findings moved (SHORT 24 -> 5, MEDIUM 14 -> 37, LONG 31 -> 39).

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

## Close

- **What happened:** baseline sweep at the open commit (`scratchpad/sweep.py`, 640 courses): `walls 1161 unmapped walls 680 {'invalid span': 2522, 'wall budget SHORT': 24, 'wall budget LONG': 31, 'wall budget MEDIUM': 14}`. After the change: `walls 1161 unmapped walls 0 {'wall budget MEDIUM': 37, 'wall budget LONG': 39, 'wall budget SHORT': 5}`, no invalid span. Twelve tests pinned {1, 2, 3}; their distances moved up by one, the distance-4 invalid-span test became distance 5, and three tests were added: distance 1 is invalid, distance 4 is LONG, and a wall across two plates is measured in world cells. `_wall` in the tests now puts both towers on one retainer by default (it used retainers 0 and 1, and 1 resolves to nothing).
- **What changed:** `traxgen/validator.py` (`_WALL_DISTANCE_TO_KIND`, `_STRAIGHT_DISTANCE_TO_LENGTH`, new `_wall_distance`, the structural rule's docstring and TODO), `tests/test_validator.py`, `docs/refs/rail-specs.md` (a column for the format's distance, and the correction).
- **Evidence:** `uv run pytest -q tests/test_validator.py` 145 passed; with HEAD's validator restored, 14 failed; full suite 1,248 passed, 1 deselected. Ruff: the 11 findings in `tests/test_validator.py`, the 2 long docstring lines in `traxgen/validator.py`, and both files' format drift are all present at HEAD unchanged; none is new.
- **Decisions made inside the task:** corpus over the wiki-sourced reference (source priority: direct observation first); the change is the validator's arithmetic, not a rule; no `decisions.md` row recorded {1, 2, 3}, so nothing locked is overturned. Not run through the adversarial panel: the corpus sweep is a stronger check of this change than a review would be, and a clean revert undoes it.
- **For the record:**
  - `decisions.md` (new row): STRAIGHT rails and walls -- SHORT, MEDIUM, LONG join cells 2, 3, 4 apart in world cells; walls measured through tower retainers. Corpus, 640 courses: 0 rails at distance 1, 2,522 at 4; walls 106 / 481 / 574 at 2 / 3 / 4.
  - `plan.md` *Deferred cleanup*: "walls with unexpected hex distance silently skipped" -- no corpus wall now lands outside {2, 3, 4}; the skip stays for malformed input.
  - `observations.md` candidate: a fan-wiki number ("max hex distance 1") went into code unconverted; "distance" meant two different counts. The corpus would have caught it on day one -- run each validator rule over the corpus once when it is written.
  - Balcony-touching rails are still skipped by the span check; s52-t10's rule can now resolve them (next step, not done here).
- **Friction:** none.
- **Next:** s52-t12, or the close.
