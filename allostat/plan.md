# traxgen — Plan

This file holds the project's **operational state**: where things stand, what's in flight, where it's going, and in what order it gets there. The architecture — what a layer is, how the pieces compose — lives in `CLAUDE.md` and the README. The project's purpose and direction live in `project-instructions.md` and `vision.md`. This file is the live state in between.

---

## Living document discipline

Keep this file current at session close, as part of the close routine in `workflow.md` — that routine owns the *how*; this is just what to touch here:

- **Status changed?** Update Current state.
- **Item completed?** Remove it from Sequenced work in flight.
- **New work surfaced?** Add it to Sequenced work, naming its sequencing strategy.
- **Session done?** Append an entry to the Session log.

This file is **operational state** only. Don't duplicate `decisions.md` (locked choices) or `observations.md` (recurring process patterns) — point at them, and let each be the source of truth for its own domain.

## Current state

Phase 1 (single-track pipeline proof), late-stage. Milestone status:

| Milestone | Status |
|---|---|
| M1 Foundation (types, hex, inventory) | done |
| M2 Domain + parser | done |
| M3 Round-trip (byte-compare) | done (bbf7e36) |
| M4 Validator | done — 12/12 v1 rules; 3 Phase-2 rules deferred, 2 dropped |
| M5 Generator | M5.b-minimal done (2d89e77) **but emits the falsified explicit-rail model — M5.b-fix is the next task.** M5.a (track graph) and M5.c (connection rules) not started |
| M6.a Upload | done — `uploader.py`, mock-server tests + live canary |
| M6.b Round-trip verification | core question resolved (2026-06-12 rail-model breakthrough); closure blocked on M5.b-fix + goal-rotation generalization |
| M6.c Automated render verification | done — Android harness + play-button validity oracle, ~25s/code |

First traxgen-generated course certified valid by the app: share code `FLW4TMLP5V` (no-rail STARTER + GOAL_RAIL adjacency shape). The validated geometry: STARTER@(0,0) rot 0 + GOAL_RAIL@(-1,0) rot 3, `rail_count = 0`.

Artifact status: nothing was lost with the deleted `~/Desktop/Hub` checkout — `scripts/trace_both.py` and both oracle fixtures (`4YCV8JHLX7.course`, `X3WEQ6F296.course`) are committed and present in the fresh clone (verified via project tree, 2026-07-22).

## Phase 1 definition of done

`python -m traxgen generate --set vertical-starter` produces a `.course` binary that: (1) is accepted by the share-code upload endpoint, (2) loads in the official app via that code without errors, (3) uses only PRO Vertical Starter-Set (26832) pieces, (4) has a valid ball path from a starter to a goal, (5) fits on the set's 4 baseplates. Closure of queue item 3 (M6.b) is measured against this.

**Explicit v1 non-goals:** interesting tracks, variety, physics simulation, aesthetics, race mode, perpetual mode. Phase 1 proves the pipeline works end-to-end — nothing more.

## Sequenced work in flight

1. **M5.b-fix — rewrite `generate_minimal()` to the no-rail adjacency shape** (STARTER + GOAL_RAIL, zero rails, hardcoded inventory). *dependency* — everything downstream of the generator needs it emitting the validated model, not the falsified one.
2. **Goal-rotation sweep** — generalize relative-position → required `GOAL_RAIL` `hex_rotation` beyond the single observed geometry; run under the M6.c harness. *learning* — the mapping feeds M5.c connection rules and closes half of M6.b.
3. **Close M6.b** — declare it done once 1 and 2 land and a generated course renders active end-to-end via the harness. *dependency* on items 1–2.
4. **Teach the parser schema v7** — accept `version = 7`, skip the `u32 = 13` at offset 0x2E. Small and well-scoped. *blast radius* — smallest reversible next step; unblocks native oracle parsing without the one-off reader.
5. **Re-verify `local_hex_position` honoring under the harness** — promote the tentative finding to resolved or falsify it; the manual-loop evidence is tainted by the clipboard failure. *bake-time* — cheap once sweeps are routine.
6. **M5.a track graph + M5.c connection rules** (`traxgen/graph.py`; also unlocks validator rule #15 `START_GOAL_CONNECTED`). *dependency* — blocked on connection-semantics evidence (open unknown #7), fed by item 2.
7. **Dedicated lint-cleanup session** — the 38 pre-existing ruff findings. *relatedness* — batch as one session; not mixed into feature work.

## Triggered reviews

- When a milestone completes → refresh the README's status paragraph (it drifts otherwise).
- When murmelbahn's schema changes upstream → update `types.py` to match and note the source commit in the docstring (per `.cursorrules`).
- When `ROTATION_OUT_OF_RANGE` appears to false-positive on an app-accepted course → revisit the modulo-normalization hypothesis (open unknown #11).
- When rendering in the emulator gets laggy → upgrade the harness from fixed sleeps to polling-based waits.

## Open questions

Still-open v1-scope unknowns, numbering preserved from the original PLAN.md for traceability (resolved/dissolved items live in the archived PLAN and in `decisions.md` where they hardened):

- **#1 Switch TileKind encoding** — state via TileKind vs separate field; verify by parsing an app-exported single-switch course.
- **#2 Rail `side_hex_rot` semantics** — de-prioritized 2026-06-12 (not the minimal-course blocker); matters again when the generator places explicit rails.
- **#3 Baseplate physical shape** — blocks any real `BASEPLATE_COVERAGE` rule.
- **#4 Balcony world-coord resolution** — probe-first follow-up; until then balcony-touching rails skip span validation.
- **#5 Retainer ID assignment scheme** — ranges known, scheme unknown.
- **#6 GUID generation** — GUID=0 accepted by upload; app-side validation unverified beyond current evidence.
- **#7 Connection rules per tile type** — feeds the track graph; derive from physical specs + fixtures.
- **#8 `THREE_ENTRANCE_FUNNEL` mapping** — best-guess; confirm from a fixture using the piece.
- **#9 Track-graph representation** — design when #7 is answered enough to be worth it.
- **#10 `LayerKind` semantics** — `BASE_LAYER` vs `BASE_LAYER_PIECE` distinction; what `LARGE_GHOST_LAYER` is.
- **#11 Rotation modulo hypothesis** — see triggered review above.
- **#12 Which upload headers are strictly required** — full set works; stripping untested.
- **#13 Schema v7 delta** — narrowed to one `u32 = 13` at 0x2E; meaning unknown; parser support is queue item 4.

**Deferred cleanup** (small, non-blocking — from PLAN.md, trimmed to what's still live): `AUTUMN_2024 = 10` missing from `types.py`; pillar id u32-vs-i32 read; mounted-only balcony counting assumption; walls with unexpected hex distance silently skipped; starter/goal override API (design when a consumer forces it); render outcomes should be recorded as text, screenshots deleted; `android.py`'s `DEFAULT_SCREENSHOT_DIR` hardcodes the deleted `~/Desktop/Hub` checkout path and silently recreates it via `mkdir` — make it repo-relative or config-driven; re-photograph the starter-set manual pages, rail-height table first (primary evidence for Δheight = 4; photos were never committed; verified no .gitignore rule involved — PRO 26832 pages worth adding too).

## Session log

Backfilled from the dated history embedded in PLAN.md — earlier sessions left no per-session records. Date-based naming (this project's history is already date-keyed).

- **2026-04-22:** Sideload ruled out architecturally — iOS app accepts no local data-in path. M6 reframed around the share-code API. → reverse-engineer upload.
- **2026-04-24:** Upload API captured via mitmproxy under a pre-declared 4-hour budget (endpoint, headers, dedup-by-content-hash). M6.a shipped: `uploader.py`, exception hierarchy, mock-server tests, live canary. First uploads rendered tiles but never rails — new unknowns surfaced; manual loop identified as the bottleneck. → automation (M6.c).
- **2026-04-25:** M6.c shipped — AVD `traxgen_m6c`, Play-Store GraviTrax, `android.py` harness, play-button validity oracle calibrated on X3WEQ6F296/MT756NLLMI. → resume M6.b under automation.
- **2026-06-12:** Rail-model breakthrough — valid courses have `rail_count = 0`; GOAL_RAIL carries its own rail; adjacency + goal rotation is the connection. `FLW4TMLP5V` is the first app-certified generated course. v7 delta narrowed to one u32. Clipboard failure mode discovered — pre-discovery manual observations demoted to tentative. → M5.b-fix.
- **2026-07-22 (migration):** Project migrated onto Allostat. `docs/PLAN.md` folded into the canonical files and archived; `.cursorrules`, README, `docs/refs/` classified live-in-place; CLAUDE.md rewritten as adapter over the allostat files; `docs/refs/android-automation.md` written from the archive + `android.py` (closing the deferred item); original checkout at `~/Desktop/Hub` confirmed deleted — artifact survival flagged for verification. → M5.b-fix.

## Cross-references

- `project-instructions.md` — identity, purpose, mode, and domain context (Layer 2).
- `workflow.md` — the session routines (open, drift-check, close, capture, handoff).
- `decisions.md` — locked choices, with the reasoning behind them.
- `observations.md` — recurring process patterns.
- `vision.md` — the project's longer-arc direction.
- `knowledge/` — project-scope reference material (Layer 3).
- `docs/refs/` (repo) — the project's committed reference corpus, indexed by its README.
- Archived: `docs/PLAN.md` — the pre-Allostat living document; historical detail beyond what the files above carry.
