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
| M5 Generator | M5.b-minimal done (2d89e77); M5.b-fix done (f6e5717) — `generate_minimal()` emits the validated no-rail adjacency shape, app-certified via `FLW4TMLP5V`. M5.a (track graph) and M5.c (connection rules) not started |
| M6.a Upload | done — `uploader.py`, mock-server tests + live canary |
| M6.b Round-trip verification | **done 2026-08-08** — connection semantics resolved. `g = (d + 1) % 6` is a *goal-side* rule, confirmed on every active cell ever measured with zero exceptions. What varies is the *live direction set*, which moves with the starter's `hex_rotation`: exhaustively mapped at s=0 (E rot 1, NW rot 3) and s=1 (NE rot 2 only). Characterizing s=2..5 is open unknown #15, not a blocker |
| M6.c Automated render verification | done — Android harness + play-button validity oracle, ~25s/code |

First traxgen-generated course certified valid by the app: share code `FLW4TMLP5V` (no-rail STARTER + GOAL_RAIL adjacency shape). The validated geometry: STARTER@(0,0) rot 0 + GOAL_RAIL@(-1,0) rot 3, `rail_count = 0`.

Artifact status: nothing was lost with the deleted `~/Desktop/Hub` checkout — `scripts/trace_both.py` and both oracle fixtures (`4YCV8JHLX7.course`, `X3WEQ6F296.course`) are committed and present in the fresh clone (verified via project tree, 2026-07-22).

## Phase 1 definition of done

`python -m traxgen generate --set vertical-starter` produces a `.course` binary that: (1) is accepted by the share-code upload endpoint, (2) loads in the official app via that code without errors, (3) uses only PRO Vertical Starter-Set (26832) pieces, (4) has a valid ball path from a starter to a goal, (5) fits on the set's 4 baseplates. Closure of Sequenced work item 4 (Close M6.b) is measured against this.

**Explicit v1 non-goals:** interesting tracks, variety, physics simulation, aesthetics, race mode, perpetual mode. Phase 1 proves the pipeline works end-to-end — nothing more.

## Sequenced work in flight

1. **M5.c connection rules + M5.a track graph** (`traxgen/graph.py`) — build against the verified table rather than a derived rule: goal rotation from `g = (d + 1) % 6`, live directions from the measured table (see `decisions.md`, 2026-08-08). *dependency* — unblocked by the 2026-08-08 sweeps; also unlocks validator rule #15 `START_GOAL_CONNECTED`.
2. **Characterize the live-direction set at s=2..5** — full 36-cell sweeps via `sweep_goal_rotation.py --starter-rot N`, ~18 min each. *learning* — open unknown #15. **s=2 is the highest-value single run**: E rot 1 and NW rot 3 are both already known active there, so a full sweep tests whether even rotations are genuinely identical to s=0 or merely share two cells.
3. **Wire polling into `render_course`** — `wait_until` / `wait_for_node` exist and are tested offline; the four native steps still use fixed sleeps. *blast radius* — smallest change that retires the 2026-08-07 stopgap. Deferred twice now; the fixed sleeps drove ~60 renders on 2026-08-08 without a single failure, so the urgency has dropped.
4. **A base layer that models the baseplates instead of assuming them** — everything measured so far sits on the standard PRO Vertical arrangement (four plates in a square). Real courses vary: plates can be added, and they connect only parallel-side to parallel-side, never perpendicular. Needs either a reverse-engineered base model or an explicit representation that treats the arrangement as input rather than a constant. *dependency* — open unknown #16; feeds #3 and the dropped `BASEPLATE_COVERAGE` rule. Raised by Colby 2026-08-08.
5. **Teach the parser schema v7** — accept `version = 7`, skip the `u32 = 13` at offset 0x2E. *blast radius* — smallest reversible next step; unblocks native oracle parsing without the one-off reader.
6. **Re-verify `local_hex_position` honoring under the harness** — promote the tentative finding to resolved or falsify it; the manual-loop evidence is tainted by the clipboard failure. *bake-time* — cheap now that sweeps are routine.
7. **Dedicated lint-cleanup session** — the 38 pre-existing ruff findings, plus whatever the three new scripts added. *relatedness* — batch as one session; not mixed into feature work.

## Triggered reviews

- When a milestone completes → refresh the README's status paragraph (it drifts otherwise).
- When murmelbahn's schema changes upstream → update `types.py` to match and note the source commit in the docstring (per `.cursorrules`).
- When `ROTATION_OUT_OF_RANGE` appears to false-positive on an app-accepted course → revisit the modulo-normalization hypothesis (open unknown #11).
- ~~When rendering in the emulator gets laggy → upgrade the harness from fixed sleeps to polling-based waits.~~ **Fired 2026-08-07**; stopgap applied and the polling primitives built. Retire this row once item 3 of Sequenced work lands.
- When the two Unity-surface waits (`after_load`, `after_render_load`) start failing → they cannot be polled via `uiautomator` (the game surface is opaque to it); a pixel-stability predicate is the only route. Not yet triggered — the IME step is what failed.

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
- **#14 Why four of six adjacent directions have no connecting rotation** — **answered 2026-08-08.** The suspect was right: the starter's `hex_rotation` was pinned at 0 for all 42 cells of the 2026-08-07 sweep, and it moves which directions connect. The four dead directions were dead *at that starter rotation*, not in general — NE, dead at all six rotations on 2026-08-07, is active at s=1. The apparent partiality was never in the rotation rule; `g = (d + 1) % 6` is a goal-side rule that has never once been violated. What is restricted is the live direction set, which is a starter-side property. Superseded by #15, which asks what that set actually is.
- **#15 What determines the live direction set, and why does its size change?** — at s=0 exactly two cells connect (E rot 1, NW rot 3); at s=1 exactly one (NE rot 2). Both rotations were swept exhaustively, 36 cells each, harness-bracketed. A rotating exit *pair* is refuted in both chiralities: `{NE, W}` and `{NE, SE}` are the +1 and -1 images of `{E, NW}`, and W and SE are dead at every rotation at s=1. So the count itself varies with starter rotation, which no symmetric model explains. s=2 is known to include both E rot 1 and NW rot 3; s=4 includes E rot 1; s=3 and s=5 exclude it. Sequenced work item 2 maps the rest. Practically non-blocking: M5.c can build from the measured table.
- **#16 Baseplate arrangement is assumed, not modelled** — every course measured to date sits on the standard PRO Vertical base: four plates in a square. That is a constant in the code and an assumption in the evidence. Real courses add plates and arrange them differently, and plates connect only parallel-side to parallel-side, never perpendicular — so arrangement is constrained, not free. Needs either a reverse-engineered base model or a representation that takes the arrangement as input. Overlaps #3 (physical shape) and #10 (`LayerKind` semantics); distinct from both in being about *adjacency between plates*. Raised by Colby 2026-08-08 while reading the sweep results.

**Deferred cleanup** (small, non-blocking — from PLAN.md, trimmed to what's still live): `AUTUMN_2024 = 10` missing from `types.py`; pillar id u32-vs-i32 read; mounted-only balcony counting assumption; walls with unexpected hex distance silently skipped; starter/goal override API (design when a consumer forces it); render outcomes should be recorded as text, screenshots deleted; `android.py`'s `DEFAULT_SCREENSHOT_DIR` hardcodes the deleted `~/Desktop/Hub` checkout path and silently recreates it via `mkdir` — make it repo-relative or config-driven (`scripts/sweep_goal_rotation.py` routes around it with a repo-relative default, but the library default is unchanged); `knowledge/environment.md`'s emulator boot line uses `$ANDROID_HOME`, which is not exported in a default shell — fixed there 2026-08-07, but `resolve_context()`'s fallback is what actually saves the library; a second AVD `traxgen_test` exists and is undocumented — describe it or delete it; re-photograph the starter-set manual pages, rail-height table first (primary evidence for Δheight = 4; photos were never committed; verified no .gitignore rule involved — PRO 26832 pages worth adding too).

## Session log

Backfilled from the dated history embedded in PLAN.md — earlier sessions left no per-session records. Date-based naming (this project's history is already date-keyed).

- **2026-04-22:** Sideload ruled out architecturally — iOS app accepts no local data-in path. M6 reframed around the share-code API. → reverse-engineer upload.
- **2026-04-24:** Upload API captured via mitmproxy under a pre-declared 4-hour budget (endpoint, headers, dedup-by-content-hash). M6.a shipped: `uploader.py`, exception hierarchy, mock-server tests, live canary. First uploads rendered tiles but never rails — new unknowns surfaced; manual loop identified as the bottleneck. → automation (M6.c).
- **2026-04-25:** M6.c shipped — AVD `traxgen_m6c`, Play-Store GraviTrax, `android.py` harness, play-button validity oracle calibrated on X3WEQ6F296/MT756NLLMI. → resume M6.b under automation.
- **2026-06-12:** Rail-model breakthrough — valid courses have `rail_count = 0`; GOAL_RAIL carries its own rail; adjacency + goal rotation is the connection. `FLW4TMLP5V` is the first app-certified generated course. v7 delta narrowed to one u32. Clipboard failure mode discovered — pre-discovery manual observations demoted to tentative. → M5.b-fix.
- **2026-07-22 (migration):** Project migrated onto Allostatik. `docs/PLAN.md` folded into the canonical files and archived; `.cursorrules`, README, `docs/refs/` classified live-in-place; CLAUDE.md rewritten as adapter over the allostatik files; `docs/refs/android-automation.md` written from the archive + `android.py` (closing the deferred item); original checkout at `~/Desktop/Hub` confirmed deleted — artifact survival flagged for verification. → M5.b-fix.
- **2026-07-27 (repair):** Canonical-vs-repo drift found and cleared. `plan.md` still listed M5.b-fix as next when `generate_minimal()` had emitted the validated no-rail shape since `f6e5717` (app-certified `FLW4TMLP5V`) — reconciled at `19abcf4`, which also filled a placeholder in `knowledge/docs/README.md`. `decisions.md` locked Python 3.12 as "pinned `.python-version`", but scaffold boilerplate (`a757183`) had gitignored that file into never existing and fresh clones silently resolved to CPython 3.14.4 — fixed at `9b028e4`, with `requires-python` left at `>=3.12` as the consumer compatibility floor. Suite 279 passing / 1 deselected on 3.12.13, matching the pre-move baseline. Close routine did not run; row backfilled 2026-08-04. → goal-rotation sweep.
- **2026-08-03/04 (rename):** `allostat/` → `allostatik/` for the upstream Allostatik 0.3.0 rename — one Claude Code session spanning both dates. `7158605`: migrate script applied — folder `git mv`'d wholesale, 25/48 fences flipped, 7 `@`-imports repointed, 39 in-folder replacements; script and independent verify both green. Zone 4 (host-project references outside `allostatik/`, which the script reports but by design never edits) cleared by hand across two commits: `f8ab4bf` repointed `scripts/update_docs_20260727.py`, and `4988c41` repointed 3 CLAUDE.md preamble mentions that turned out to be live path pointers rather than prose — the orient step had been directed at `allostat/workflow.md` and `allostat/plan.md`, neither of which existed post-rename. `docs/PLAN.md`'s archive banner and the `docs/refs` mentions were left deliberately as historical record. Close routine did not run; row backfilled 2026-08-04. → goal-rotation sweep.
- **2026-08-04 (backfill):** Closed the session-log gap left by the two preceding sessions. `plan.md` gained rows for 2026-07-27 and 2026-08-03/04; `decisions.md`'s rename row marked `[AMENDED]`; `observations.md` promoted #12 (a check can pass while asserting something false — three firings) and added candidates #13 and #14. Commits `0b9e989`, `7535813`. Key finding: the `Claude-Session` trailer proved `7158605`/`f8ab4bf`/`4988c41` were one session spanning two dates, putting missed closes at two rather than three — below the double-loop threshold, so the freshness-check repair was deliberately *not* attempted. That repair and #13 are upstream Allostatik work. Sweep untouched. → goal-rotation sweep.
- **2026-08-07 (goal-rotation sweep):** Sweep built, run, and partially answered. `scripts/sweep_goal_rotation.py` + 27 offline tests; 36 adjacency cells plus a positive control and six distance-2 negative controls, with all five falsification conditions pre-declared in `classify()` and tested before the first render. **Result: `rot = (d + 1) % 6` is the sole surviving affine rule** — E rot 1 was the discriminator that separated the two chiralities the single 2026-06-12 geometry could not. Four directions have no connecting rotation, which the rule mispredicts; recorded as open unknown #14. Run one aborted after a single render when the control read `inactive`: a cold-booted AVD had not laid out the fullscreen IME inside the 0.3 s `after_text`, so `ime_ok` tapped an unready view and the oracle sampled a keyboard. Tap coordinate exonerated in one command via `uiautomator` bounds (`[2216,252][2384,378]` contains (2270,305)); the fixed-sleep triggered review fired. Stopgap (`after_text` 1.5, `after_tap` 0.8) plus a closing-bracket control; polling primitives (`wait_until`, `find_node`, `wait_for_node`) built and tested offline against a captured dump but not yet wired in. Separately: the byte-identical control returning a *new* share code exposed that `generate_minimal()`'s certification had never been compared to the certified artifact — diffing `FLW4TMLP5V` showed the only divergence is the title string, so the geometry stands and content-hash dedup is confirmed. The resume run then produced a **false `active`** from a splash screen, which without the closing bracket would have been reported as `MODEL_WRONG`; `white_frac >= 0.50` frame guard added to the oracle, calibrated on measured screencaps. Commits: see `Claude-Session` trailer. → starter-rotation sweep.

- **2026-08-08 (starter rotation: three sweeps, one refuted model):** Opened with the drift-check passing as a *real diff* for the first time — both claude.ai fields written to `/tmp` and `diff`'d against `allostatik/deployed/`, `IDENTICAL` each. Session ran with direct repo file access (device bridge) but no `adb`/emulator on that side, so every render came from Colby's shell one command at a time. **Sweep 1 — starter rotation, 9 renders.** The handoff's design (hold the mispredicted NE rot 2, sweep the starter) was replaced before coding: a null result there cannot separate "direction unreachable" from "coupling real but never yields rot 2 here". Holding a *known-active* cell (E rot 1) makes both outcomes informative. Result: E rot 1 active at s ∈ {0,2,4}, dead at {1,3,5}; NE rot 2 — dead at every rotation on 2026-08-07 — active at s=1; NW rot 0 backfill inactive, completing the 42-cell grid with one-rotation-per-direction intact. **The run's own printed verdict asserted a mechanism its data refuted** (`{s, s+2} mod 6` excludes E at s=2, where E connected): pre-declared trigger sound, attached free-text explanation not. **Sweep 2 — parity model, 5 renders.** A model fitted to all prior data (exit pair `{E,NW}` even / `{NE,W}` odd, `g` unchanged) was tested by declaring each cell's verdict *in code* before rendering. Three of four held: the app-certified geometry does break at s=1, the rival `g = (d + 1 + 3s) % 6` is dead, and s=2 restores s=0 exactly. The fourth missed — W rot 4 dead at s=1. **Sweep 3 — full 36-cell at s=1, 43 renders, 18.2 min.** Exactly **one** connecting cell at s=1: NE rot 2. Both chiralities of the exit-pair model are refuted (W and SE dead at all rotations), so the pair framing is gone; what survives is that `g = (d + 1) % 6` has never once been violated across two exhaustively swept starter rotations. M6.b closed on that basis; #14 answered, #15 and #16 opened. **Refactor:** rather than a third near-duplicate script, `sweep_goal_rotation.py` gained `--starter-rot` (control pinned at s=0 and excluded from the per-direction tally, because the certified geometry is inactive at s=1), and `_goal_variant` was retired for the shared `build_variant`. Suite 332 → 397. HTTP 520 struck once more mid-batch (observation #15, second firing); the resume path closed the hole in one render. → M5.c, and the s=2..5 characterization.

## Cross-references

- `project-instructions.md` — identity, purpose, mode, and domain context (Layer 2).
- `workflow.md` — the session routines (open, drift-check, close, capture, handoff).
- `decisions.md` — locked choices, with the reasoning behind them.
- `observations.md` — recurring process patterns.
- `vision.md` — the project's longer-arc direction.
- `knowledge/` — project-scope reference material (Layer 3).
- `docs/refs/` (repo) — the project's committed reference corpus, indexed by its README.
- Archived: `docs/PLAN.md` — the pre-Allostatik living document; historical detail beyond what the files above carry.
