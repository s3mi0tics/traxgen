# s52-t9 — the corpus miner reads piece sides in a mirrored frame (#7; s20's curve "87/13")

**Status:** DONE

**In one paragraph:** The corpus miner has read piece sides in a mirrored frame since s20, and the corpus agrees with the emulator once that is fixed. The format numbers a cell's edges the other way round from `HEX_DIRECTIONS`: edge `s` is world direction `(2 - s) % 6`, which every one of 15,880 straight rails with both ends on layers shows. The miner subtracted the rotation from the raw edge, which keeps parity (so STARTER's {0,2,4} looked right) but mirrors every asymmetric piece. In the corrected frame, single-tile curves carry rail ends on sides 0, 2, 3, 4 and none on 1 or 5 -- D097 exactly -- and single-tile X-intersections on 1, 2, 4, 5 and none on 0 or 3 -- D099 exactly. s20's curve "87/13" split was the sharp track's side 3, mirrored, not a height effect. `piece_side` now carries the corrected formula in one place, pinned by a fixture test that fails on the old one.

## Open (written before the work)

- **Goal:** correct `scripts/mine_ports.py`'s piece-relative side to `track_graph`'s frame, pinned by a test, after re-running the evidence a background corpus reader produced.
- **Scope:** `scripts/mine_ports.py`, `tests/test_mine_ports.py` (new).
- **Budget:** 25 minutes, no renders.
- **Done check:**
  1. *Step:* re-run the reader's rail-geometry check and corrected port tables; replace `(side_hex_rot - hex_rotation) % 6` with one named function; test it.
  2. *True after:* the miner's `rel` is `(2 - side_hex_rot - hex_rotation) % 6`, in one place, and a test pins the world-side half against `HEX_DIRECTIONS`.
  3. *Miss cases:* one of the two inline copies is left on the old formula; the test only restates the formula; the stored records' raw fields change (D037 keeps the observation, not the interpretation).
  4. *Reads:* the reader's `ports.jsonl` (the miner's own output on the corpus), its `f.py` and `g.py`; `traxgen.hex.HEX_DIRECTIONS`; `track_graph.PIECE_RULES`.
  5. *Check:* `grep` finds no `side_hex_rot - ` left in the miner, the new test passes, and the report quotes the re-run geometry line and the single-tile CURVE and CROSS rows.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** a background corpus reader (read-only, scratchpad `agentC/`) found the frame error. Re-run here: `f.py` -> `(exit1 side_hex_rot, HEX_DIRECTIONS index of exit1->exit2)`: (0,2) 3,001, (1,1) 2,370, (2,0) 2,832, (3,5) 2,779, (4,4) 1,874, (5,3) 1,525 -- one direction per edge, `(2 - s) % 6`, no exceptions. `g.py` (corrected frame, tower of one tile, all at height level k=0): CURVE {0: 6,625, 1: 0, 2: 6,641, 3: 2,462, 4: 2,502, 5: 0}; CROSS {0: 0, 1: 488, 2: 686, 3: 0, 4: 516, 5: 656}; STARTER {0: 120, 2: 144, 4: 116, odd: 0}; SWITCH_LEFT {0: 136, 2: 188, 4: 136}; SWITCH_RIGHT {0: 82, 2: 135, 4: 139}. The 92 curve ends on sides 1 and 5 in all towers sit in towers of 4 to 9 tiles held by DOUBLE_BALCONY retainers: the miner credits a rail end to every tile in a cell's tower. Then `piece_side()` replaced both inline `(side_hex_rot - hex_rotation) % 6` copies and the printed legend; the stale "plan.md item 5" in the generation shim's docstring now says item 8.
- **What changed:** `scripts/mine_ports.py`, `tests/test_mine_ports.py` (new).
- **Evidence:** `uv run pytest -q tests/test_mine_ports.py` 3 passed; with `piece_side` reverted to the old formula, 2 failed (the fixture's CROSS ends land on sides 0, 0 and 3); restored, `grep` finds the new formula once and no `side_hex_rot -` left. Ruff clean.
- **Decisions made inside the task:** fix the interpretation only; the records' raw `side_hex_rot` and `tile_hex_rotation` are unchanged, per D037 (records store the observation, not the interpretation).
- **For the record:**
  - `decisions.md` (new row): the format's cell edge `s` is world direction `(2 - s) % 6` (mirror of `HEX_DIRECTIONS`); piece side = `(2 - s - hex_rotation) % 6`. Corpus-measured, 15,880 straight rails; CURVE and CROSS port sets then match D097 and D099 with zero single-tile exceptions.
  - `plan.md` #7 and item 1: the corpus channel and the emulator agree on the three pieces measured both ways (curve, cross, switches), so corpus port sets in the corrected frame are evidence for the next pieces. s20's per-side sets for asymmetric kinds were permuted and must be re-derived; its parity counts survive (the mirror keeps parity). s45's "the corpus only half agrees" is withdrawn: it was this frame error.
  - `plan.md` item 20: its "first batch is the corpus ... the curve's 87/13 rail split first" is done -- the split was the frame error.
  - `observations.md` candidate: a symmetric calibration target cannot catch a mirror. STARTER's {0,2,4} passed s20's check under the wrong frame; CURVE or CROSS would have failed it. Calibrate on an asymmetric piece.
- **Friction:** none.
- **Next:** s52-t10, the balcony reader's result (#4) and the validator span it flags.
