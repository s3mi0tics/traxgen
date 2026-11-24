# s52-t7 — what the corpus says about LayerKind (#10) and the plate lattice (vision.md)

**Status:** OPEN

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
