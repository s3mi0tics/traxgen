# s52-t7 — what the corpus says about LayerKind (#10) and the plate lattice (vision.md)

**Status:** DONE

**In one paragraph:** Every plate offset the corpus contains lies on the lattice: 599 courses with two or more plates, 120 distinct ordered offsets, 120 on the lattice with basis (5,0) and (3,-6), none off it (exact arithmetic). #10 is only half answerable here: `BASE_LAYER` and `LARGE_GHOST_LAYER` occur in none of the 640 parseable courses, so what they are stays unknown. The other three kinds are now described from the corpus: `BASE_LAYER_PIECE` is the baseplate (every course, height -0.2, the 30-cell footprint, layer ids 100-317); `LARGE_LAYER` is a radius-2, 19-cell level plate at heights in multiples of 0.36 (ids up to 2009); `SMALL_LAYER` is a radius-1, 7-cell plate (ids from 1000). Empty layers occur for every kind, so emptiness does not mark a ghost.

## Open (written before the work)

- **Goal:** fold a background corpus reader's results on #10 and on "whether all 120 observed deltas lie on the lattice" into the record, after re-running its script.
- **Scope:** none beyond the ledger and this report; the scripts stay in the scratchpad.
- **Budget:** 10 minutes, no renders.
- **Done check:**
  1. *Step:* re-run the reader's `layerkinds.py` and compare its output with the reader's own.
  2. *True after:* the figures below come from a run made in this task, and match the reader's.
  3. *Miss cases:* the report repeats the reader's numbers without re-running; the lattice test uses floats or a different basis from `plates.py`.
  4. *Reads:* `~/Claude/Projects/traxgen-corpus/raw/*.course`; `scripts.probe_plate_arrangement.pairwise_deltas` and `on_lattice` at HEAD.
  5. *Check:* `diff -q` of the reader's output and this task's re-run is empty, and the report quotes the tally and lattice lines.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** a background reader (read-only, scratchpad only) wrote `layerkinds.py`; this task re-ran it from the repo root with `PYTHONDONTWRITEBYTECODE=1 uv run python`. Output identical to the reader's (`diff -q` empty). Tally: `{'skip v2': 77, 'parsed': 640, 'skip v7': 31, 'skip ValueError': 60}`. Lattice: `(B) courses with 2+ plates: 599; distinct ordered deltas: 120` / `on lattice: 120  off: 0`. Per kind (layers / courses): BASE_LAYER_PIECE 4,599 / 640; LARGE_LAYER 1,544 / 401; SMALL_LAYER 704 / 181; BASE_LAYER 0; LARGE_GHOST_LAYER 0. The 60 v5 files the strict parser rejects (SkyTrax-era TileKind 94-101 and generation ids 10-12) were re-parsed leniently by the reader, in-process only: same three kinds, 36 multi-plate courses, none off the lattice -- that half was not re-run here.
- **What changed:** this report and the ledger only.
- **Evidence:** the tally and lattice lines above.
- **Decisions made inside the task:** none.
- **For the record:**
  - `vision.md`, *The board*: "Left open and cheap: whether all 120 observed deltas lie on the lattice" -- answered yes, 120 of 120 over 599 courses (s52-t7).
  - `plan.md` #10: partly answered -- BASE_LAYER_PIECE, LARGE_LAYER and SMALL_LAYER described from the corpus as above; BASE_LAYER and LARGE_GHOST_LAYER never occur in v3-v5 courses, so they stay unknown, and the v1/v2 and v7 files are where to look next.
  - Two stale pointers the reader found, not fixed: `docs/refs/layer-kinds-and-world-coords.md` still says "No other fixtures probed yet"; `scripts/probe_plate_arrangement.py` says v7 waits on "plan.md item 5", which is item 8 now.
- **Friction:** none.
- **Next:** the other two corpus readers (#5 retainer IDs; the curve's odd-side rails).
