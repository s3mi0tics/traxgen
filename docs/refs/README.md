# References

Authoritative source material for traxgen's piece and rail specs. These
files are committed because:

- Community wikis are sometimes wrong (e.g., the GraviTrax Fandom wiki
  lists long rails as max 3.5 full-tiles Δheight; Ravensburger's own
  starter-set manual shows 4 full-tiles — confirmed by physical test).
- Handoff conversations should be able to see these directly without
  chasing web links.
- When sources disagree, the reconciled version lives here alongside
  the code that uses it.

Source priority when they conflict: physical inspection > manual photos >
wiki > Ravensburger listings.

Layout:

- `rail-specs.md` — reconciled rail capacity table (hex distance,
  Δheight) used by the validator's rail-inventory-budget rule.
- `pro-vertical-starter-set-26832.md` — piece contents of the target
  inventory (the set on the shelf).
- `pro-structural-notes.md` — structural notes on PRO-line pieces.
- `tree-node-height-semantics.md` — how height works in the tile tree
  (probe finding).
- `tile-tree-node-index.md` — tile-index semantics investigation (why
  `TILE_INDEX_COLLISION` was dropped from v1).
- `layer-kinds-and-world-coords.md` — LayerKind and world-coordinate
  findings.
- `upload-api.md` — the reverse-engineered share-code upload API
  (endpoint, headers, dedup-by-content-hash behavior).
- `android-automation.md` — the M6.c render harness: emulator config,
  tap-coordinate map, validity oracle.
- `ui-automation-synchronization.md` — how the harness decides a screen is
  ready: the three generations of synchronization, why Unity blocks
  `uiautomator` polling for half the flow, and the 2026-08-07 IME timing
  failure worked through end to end.
- `agentic-workflow-notes.md` — cross-project learnings on working
  with AI coding agents: tool selection, session patterns, Colby's
  working style, per-session findings. Scope is wider than traxgen;
  lives here for history and is updated opportunistically at handoffs.
  Classified live-in-place 2026-07-22; its strongest traxgen-relevant
  patterns are folded into `allostatik/observations.md` (#7–#11).
- `starter-set-manual/` — 22410 manual-page photos (per its README).
  Primary source; trust these over the wiki. Currently holds no photos —
  they were never committed (verified 2026-07-22: no .gitignore rule
  involved), so the deleted checkout took any local copies with it.
  Re-photograph, rail-height table first (primary evidence for long-rail
  Δheight = 4); PRO 26832 pages are worth adding too, post-pivot.
  Tracked in `allostatik/plan.md` deferred cleanup.
