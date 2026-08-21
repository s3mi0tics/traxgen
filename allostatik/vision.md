# traxgen — Vision

Directional state — where this project is going at the longer horizon, and why it matters. This is distinct from its `allostatik/` siblings — `plan.md` holds operational state (what's in flight, in what order); this file holds direction (where it's all headed).

**Last meaningful update:** 2026-08-18

## The user story

Stated by Colby 2026-08-10, and sharper than what the mode list below implies:

> As a builder, I tell traxgen which pieces **I want to build with**, and it generates one or more courses that (a) use only those pieces, (b) are certified valid by the official app, and (c) arrive as a **share code** I can type into the app and then build on my table.

Three things this pins that were previously implicit:

- **The inventory is a build palette, not an ownership manifest.** "Pieces I want to build with" — explicitly not "pieces I own." Ownership is one way to fill the palette; wanting to use only the vortex and four curves is another. The inventory is a per-request input, which makes it the API's primary parameter rather than a configured constant.
- **The deliverable is the share code**, not the `.course` file. The binary is an intermediate; the thing a human can act on is a code they type into the app. Phase 1's definition of done already measures this — `FLW4TMLP5V` is exactly that artifact — but the story names it as the product.
- **"One or more."** A request can yield several candidate courses, not one canonical answer. Generation is a search over a space, and surfacing multiple results is closer to how the space actually behaves.

## Special cases are dimensions, not a class

Colby, 2026-08-10: there will be more special cases than energy-adders and the three-ball starter — "we just need a special case class, deal with them independently." The goal (independence) is right; a single `SpecialCase` bucket is the wrong shape for it, because every new quality lands in the same bucket and every consumer then has to know every case — the opposite of independent.

What keeps them independent is giving each quality **its own declared dimension with a default**, so an ordinary piece is the boring value of the same field. The codebase already does this twice: every piece carries an `EnergyProfile` (the cannon is not special-cased — it is a nonzero `energy_input_j` on a universal field, locked in `decisions.md`), and stochastic timing is a first-class `time_variance_ms` that the vortex merely has a large value for. The three-ball starter follows the same pattern once open unknown #7 forces a port model: a piece with three exit ports, not a piece with a flag.

Request-level conditions — "the three paths must converge," "they must not" — belong on the **generation request**, not on the piece. And new dimensions get added when a concrete piece plus a concrete mode needs one; that trigger is what keeps the set from being speculatively enumerated up front (YAGNI).

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
- **Beyond the starter set.** The catalog hints at expansion (`DOME_STARTER`, the POWER line). Is broader set coverage a goal, or does 26832 + Core remain the scope? The build-palette framing above pushes toward yes: if the inventory is a per-request input rather than a constant, set coverage becomes a catalog-completeness question rather than an architectural one.
- **How far does decoding scale?** The method has now produced one clean decoded rule (`g = (d + 1) % 6`, six exhaustive sweeps, zero violations) and one measured-but-unexplained pattern (parity of the live-direction set). Black-box sweeping does not scale combinatorially across pieces × placements × rotations; what would scale is decoding *per-piece connection semantics* (open unknown #7) well enough that a model predicts and renders become spot-checks of predictions rather than the primary instrument. Whether that inversion is reachable — model-first with render-verification — is the open question, and it is the difference between a generator that knows one certified shape and one that composes freely. A heavier alternative exists (decompiling the Unity app) and is deliberately not being pursued; the empirical route is working. **Post-close 2026-08-10, the reframe that keeps the route viable:** the scaling unit is the **port**, not the piece kind — 93 `TileKind`s make pairwise sweeping dead on arrival, but kinds collapse onto a small port vocabulary, and the format already speaks ports for rails (`side_hex_rot` + `exit_local_pos_y` on every rail exit identifier, verified in murmelbahn source). The candidate instrument stack, cheapest first: mine shared courses for rail attachment points (free, positive-evidence-only); read the app's own renders — it draws all 93 kinds regardless of ownership, so the catalog nobody owns is sitting in the viewer, with Claude as the reader at scale; confirm with chain-probe renders. Vision proposes, render disposes: reads are committed, auditable artifacts that prioritize the queue, and the three-valued table holds them at `UNMEASURED` until a render speaks. Design work is sequenced in `plan.md` item 1; the calibration test against the measured STARTER→GOAL_RAIL pair runs before any read is trusted. **2026-08-18: the inversion had its first live instance.** Corpus mining produced 43,375 port observations and a parity-class port model without spending a single render — and handed #15 a mechanism candidate whose entire job is now to *predict* renders rather than await them. Model-first with render-verification stopped being a question about whether the route exists and became a question of how far it carries.
- **The TypeScript port's purpose** — is it for a web-based generator UI, or something else? The decision is locked but its motivation isn't recorded anywhere.
