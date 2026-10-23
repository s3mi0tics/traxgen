# s44-t1 — the graph checker, first design

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Propose a first design for the graph checker (what a node is, what an arrow is, what "valid" means, and where the half-hole rule sits) and trace it against the 20 entries in `graph.MEASURED_FINISHES`, for Colby to agree or change.
- **Scope:** this report only. No source changes; the design lives here until Colby agrees it, and t2 builds it.
- **Budget:** 45 minutes of reading and writing. No renders.
- **Done check:**
  1. *Step:* read the code the design builds on (`graph.py`, `plates.py`, `layout.py`, the corpus port findings), then write the design below with a trace of every `MEASURED_FINISHES` entry.
  2. *True after:* (a) the report defines node, arrow and valid in plain words, each tied to something already measured or marked as assumed; (b) it shows, for each of the 20 entries, what the design says and what was measured; (c) Colby has said yes, or said what to change.
  3. *Miss cases:*
     - The trace is typed by hand and disagrees with the table it claims to read.
     - The design reproduces the 20 only because it was fitted to them, and the report doesn't say which parts were fitted.
     - The design looks agreed because nobody objected, without Colby saying yes.
  4. *Reads:* `traxgen/graph.py` (`MEASURED_FINISHES`, `MEASURED_RUNS`), `traxgen/plates.py` (`half_hole_cells`), the output of the trace command pasted below, and Colby's reply in the session.
  5. *Check:* the trace table is the pasted output of a command run against `graph.MEASURED_FINISHES` this task, it reports how many of the 20 the design gets right, and the status line records Colby's answer.
- **Outcomes declared before any live run:** none, because there is no live run. Declared before the trace runs: the design should get 20 of 20, with the 3 misses explained by the half-hole rule alone. Anything less is a finding about the design.
