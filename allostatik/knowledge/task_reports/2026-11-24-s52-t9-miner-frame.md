# s52-t9 — the corpus miner reads piece sides in a mirrored frame (#7; s20's curve "87/13")

**Status:** OPEN

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
