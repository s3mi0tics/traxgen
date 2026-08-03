# traxgen — Vision

Directional state — where this project is going at the longer horizon, and why it matters. This is distinct from its `allostatik/` siblings — `plan.md` holds operational state (what's in flight, in what order); this file holds direction (where it's all headed).

**Last meaningful update:** 2026-07-22

## Where this is going

Three generation modes, each progressively harder, with v1's data model already shaped to carry all three without a rewrite (pieces carry `EnergyProfile` from day one; the generator dispatches via `GenerationMode`):

1. **Single-track** *(v1, Phase 1 — current)* — a topologically valid track, ball reaches goal, no physics. Proves the pipeline: generate → upload → app-certified valid.
2. **Race** *(Phase 3)* — three parallel tracks with approximately equal completion times. Needs the Phase 2 physics simulation, multi-track spatial planning, and a variance-minimizing optimizer.
3. **Perpetual** *(Phase 3)* — a closed-loop track whose net energy per cycle clears a safety margin. Needs cycle detection and energy-budget accounting.

Phase 2 (physics) sits between: per-piece energy bookkeeping with variance as a first-class property — some pieces are *designed* to be stochastic, and tolerance is a user parameter, not a constant. After v1: a TypeScript port (locked in `decisions.md`).

## Why it matters

Named explicitly in the 2026-04-24 session (recorded in `docs/refs/agentic-workflow-notes.md`): this is a **portfolio project that also has real user value**, and the dual purpose actively shapes technical direction — it's why M6 was bounded and investigated rather than deferred. Concretely: generated courses are buildable from the pieces you actually own — the target inventory is the physical set on Colby's shelf, and the app-upload loop means a generated course can go from algorithm to marble-in-hand. Race and perpetual modes are course designs that are genuinely hard for a human to produce by trial and error — equal-time parallel tracks and energy-positive loops are optimization problems, which is why a generator earns its keep.

## Architectural identity

- **Empirical over speculative.** Format knowledge comes from probes, fixtures, and app-built oracles, not spec-reading — the app itself is the validity oracle of record.
- **Schema fidelity to murmelbahn.** The reverse-engineered format is mirrored exactly, quirks included; correctness is byte round-trip.
- **v1 carries Phase 2/3's skeleton.** Energy metadata and mode dispatch exist before the features that need them, so later phases extend rather than rewrite.

## Open questions

- **Schema v4 vs the app's v7.** traxgen emits POWER_2022 (v4); the current app *saves* v7. v4 uploads work today — but is emitting a superseded schema version viable long-term, or does the project eventually target v7 output?
- **Beyond the starter set.** The catalog hints at expansion (`DOME_STARTER`, the POWER line). Is broader set coverage a goal, or does 26832 + Core remain the scope?
- **The TypeScript port's purpose** — is it for a web-based generator UI, or something else? The decision is locked but its motivation isn't recorded anywhere.
