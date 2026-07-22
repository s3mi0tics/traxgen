# traxgen — Decisions

Locked decisions about how this project works — architectural choices, conventions, and resolved tradeoffs. Once something is locked here, don't renegotiate it without raising a checkpoint. This file is the project's reasoning trail: it records not just *what* was decided but *why*, so a later session doesn't relitigate settled ground.

This is the decisions layer, distinct from its `allostat/` siblings — `plan.md` holds current operational state (what's in flight), `observations.md` holds process patterns (how the work tends to go). Point at those rather than restating them here.

**Update protocol.** At session close, append decisions locked during the session. If a locked decision later changes, mark it rather than deleting it — the trail matters:

- `[SUPERSEDED <date>]` — full overturn. Replace the Choice with the marker plus a pointer to the row that replaces it.
- `[AMENDED <date>]` / `[PARTIALLY SUPERSEDED <date>]` — partial change where the original mostly holds. Prefix the marker to the Choice; leave the original text intact.

Always name the superseding or amending row so the trail stays followable.

**Last updated:** 2026-07-22

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 (pinned `.python-version`); TypeScript port after v1 | Ship v1 in one language; port when the pipeline is proven |
| Output format | Binary `.course`, schema `POWER_2022` (v4) | Matches the murmelbahn-documented format the app accepts |
| Target inventory | PRO Vertical Starter-Set (26832); Core (22410) cataloged alongside | Colby owns 26832 physically — generated courses can be validated against real pieces |
| Tooling | `uv` + `pytest` + `hypothesis` | uv for env; property-based tests earn their keep on hex math |
| Repo | `traxgen`, public, github.com/s3mi0tics/traxgen | — |
| License | Apache-2.0 | PLAN.md's table said MIT; the repo's LICENSE file says Apache-2.0. Confirmed Apache-2.0 during the 2026-07-22 migration — the LICENSE file is authoritative |
| Schema reference | murmelbahn Rust source (`lib/src/app/layer.rs`) | Reverse-engineered ground truth; imhex-schema mirrors it |
| Project layout | Flat package (`traxgen/traxgen/`), not src-layout | Simplicity; no packaging need for src indirection yet |
| Validator API | Soft `validate()` → `list[Violation]`; `validate_strict` raises | Generator needs inspectable violations; strict wrapper for tests/CLI |
| Rail data model | Flat `Mapping[RailKind, int]` + separate `straight_rail_limits` | Rail lengths are fixed (1/2/3 hexes), not cascading — per-length budgets required |
| Upload transport | Stdlib `urllib`, no `requests` | One endpoint doesn't justify a dependency |
| Upload headers | Hardcoded module constants matching the real iOS app | Only the full verified set is known to work (open unknown #12); cargo-culting is safe |
| Upload error model | Rich exception hierarchy per failure mode | Callers can distinguish transport vs server vs malformed-response; note upload endpoint doesn't validate payloads, so 4xx/5xx paths are defensive |
| Upload test strategy | In-process mock server default; live canary behind `network` marker | Fast deterministic suite; one real-world tripwire on demand |
| Correctness contract for serialization | Byte round-trip, NOT Python-float equality | f32 storage makes `-0.2` read back as `-0.2000000029…`; bytes are the promise, floats aren't |
| Minimal-course goal piece | `GOAL_RAIL` over `GOAL_BASIN` | Full root-placeable tile vs insert needing a host frame |
| Baseplate LayerKind | Both `BASE_LAYER` and `BASE_LAYER_PIECE` count as baseplates (b8052e4) | Rust doc-comment's plural "all base plates"; GDZJZA3J3T's 15 baseplates are all `BASE_LAYER_PIECE` |
| Cannon is not a starter (d89218f) | Modeled via `energy_profile.energy_input_j`, not `is_starter` | Requires an incoming ball; energy injector, not origin |
| `BASEPLATE_COVERAGE` dropped from v1 | Revisit in M5+ if baseplate shape becomes derivable | Original spec didn't match the domain model; re-interpretation blocked on open unknown #3 |
| `TILE_INDEX_COLLISION` dropped from v1 | Revisit if fixtures reveal a pattern | Real app courses violate it (non-root nodes default index=0); rule as specced false-positives |
| App integration path | Share-code upload API only; sideload is dead | iOS app registers no local data-in path (2026-04-22); upload endpoint verified end-to-end |
| Render verification | Automated harness + play-button oracle only; manual verification carries no evidentiary weight | Silent Mac→iPhone clipboard failure invalidated a session of manual observations (promoted from the pattern now in `observations.md`) |
| Migration classification (2026-07-22) | `docs/PLAN.md` = fold-in → archive; `.cursorrules` = live (code conventions, pointed at); root README = live; `docs/refs/` = live (Layer-3 corpus); CLAUDE.md = rewritten as adapter over `allostat/` | One source of truth per domain; the required migrate-branch record |
