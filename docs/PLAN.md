# traxgen — Plan

A procedural generator for GraviTrax marble run courses. Takes a piece inventory,
outputs a binary course file that opens in the official GraviTrax app.

> Not affiliated with Ravensburger. "GraviTrax" is their trademark.
> This project reads the binary course format reverse-engineered by
> [lfrancke/murmelbahn](https://github.com/lfrancke/murmelbahn) (Apache-2.0).

---

## Confirmed decisions

| Decision | Choice |
|---|---|
| Language | Python 3.11+ (will port to TypeScript after v1 works) |
| Output | Binary `.course` file, schema version `POWER_2022` (v4) |
| Target inventory | Classic Core Starter-Set (22410), ~122 pieces, 4 baseplates |
| Repo name | `traxgen` |
| Visibility | Public |
| License | MIT |
| Schema reference | lfrancke/murmelbahn `imhex-schema.txt` |
| Project layout | Flat package (`traxgen/traxgen/`), not src-layout |
| Editor | VS Code now, likely Cursor later (minimal effort to switch) |

---

## Long-term vision (what we're building toward)

Three generation modes, each progressively harder:

1. **Single-track mode** *(v1 — Phase 1)*
   Topologically valid track with ball reaching goal. No physics, no aesthetics.
   Proves the pipeline.

2. **Race mode** *(Phase 3)*
   Generate 3 parallel tracks with approximately equal travel times. Requires
   physics simulation + multi-track spatial planning + a variance-minimizing
   optimizer.

3. **Perpetual mode** *(Phase 3)*
   Generate a closed-loop track with one or more energy-adding pieces (Magnetic
   Cannon, Catapult, Lift, Elevator) such that the marble's net energy per cycle
   is ≥ 0. Requires cycle detection + energy-budget accounting.

Phases 2 and 3 aren't built in v1, but **the data model in v1 must support them
without a rewrite.** Specifically: pieces carry energy metadata from day one,
and the generator has a pluggable `GenerationMode` target.

---

## Phase 1 success criterion

A single command — `python -m traxgen generate --set starter` — produces a
`.course` binary file that:

1. Opens in the official GraviTrax app without errors
2. Uses only pieces from the Core Starter-Set inventory
3. Has a valid ball path from a starter tile to a goal tile (topologically connected)
4. Fits on the 4 baseplates the starter ships with

**Non-goals for v1:** interesting tracks, variety, physics simulation, aesthetics,
race mode, perpetual mode. We're proving "the pipeline works end-to-end."

---

## Module plan

```
traxgen/
├── traxgen/
│   ├── __init__.py
│   ├── types.py         ✅ done — schema enums (1:1 with binary format)
│   ├── hex.py           — axial coords, neighbors, rotation, distance
│   ├── inventory.py     — Starter-Set piece counts + connection specs + energy metadata
│   ├── physics.py       — STUB in v1: energy profiles, travel time estimator (empty impls)
│   ├── domain.py        — Course/Layer/Cell/TileTower/Rail dataclasses
│   ├── parser.py        — reads existing .course binaries (ground truth for serializer)
│   ├── validator.py     — "is this build legal?" (connections, inventory budget)
│   ├── generator.py     — pluggable by GenerationMode; v1 implements SINGLE_TRACK
│   └── serializer.py    — writes .course binaries (POWER_2022 format)
├── tests/
│   ├── fixtures/        — real .course files pulled via murmelbahn for round-trip tests
│   ├── test_hex.py
│   ├── test_parser.py
│   └── test_roundtrip.py
├── docs/
│   └── PLAN.md          ← this file
├── .cursorrules         — project conventions for Cursor (when we switch)
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

---

## Phase 1 milestones

| # | Milestone | Exit criteria |
|---|---|---|
| M1 | Foundation | `types.py`, `hex.py`, `inventory.py` — enums match schema, hex math has unit tests |
| M2 | Domain + parser | Can parse a real `.course` file pulled from murmelbahn into Python objects |
| M3 | Round-trip | Parse → serialize → byte-compare matches the original file exactly |
| M4 | Validator | Given a domain object, correctly answers "is this legal?" |
| M5 | Generator | Produces a valid domain object using only Starter-Set pieces |
| M6 | End-to-end | Generated file opens in the real GraviTrax app |

**M3 is the key milestone.** If round-trip works, serialization is solved and
we can generate with confidence. Parser before generator = serializer is proven
before it matters.

---

## Phase 2 preview — Physics simulation

Not in v1, but the data model must support it.

**Energy model** (empirical, not first-principles):

For each tile traversal, track kinetic energy:

    ΔE = ΔPE − μ_r · m · g · cos(θ) · d − piece_loss

Per-piece energy profile (stored on each tile spec in `inventory.py`):

```python
@dataclass
class EnergyProfile:
    path_length_mm: float          # physical distance marble travels through the piece
    height_change_mm: float        # Δh (positive = climbs, negative = drops)
    energy_input_j: float          # active piece energy add (cannon, catapult, lift)
    loss_coefficient: float        # piece-specific friction multiplier
    expected_time_ms: float        # mean traversal time at nominal entry speed
    time_variance_ms: float        # stddev of traversal time (see note below)
```

**On variance as a first-class feature:** Some pieces are *designed* to be
stochastic. The vortex spin-down, trampoline bounce, turntable phase-on-entry,
and catapult release all have meaningful variance. This isn't noise — it's part
of what makes the tracks fun to watch. The model stores variance per piece so
generation modes can reason about it explicitly.

Rough variance tiers:
- **Low (< 50ms):** straight rails, curves, drops, magnetic cannon
- **Medium (50–300ms):** splash, catch, switches, junctions
- **High (300–1000ms):** vortex, turntable, cascade, mixer
- **Very high (1000ms+):** trampoline, volcano, any piece with spring-loaded release

**Accuracy target: user-settable tolerance.** The generator accepts a
`--tolerance SECONDS` parameter (default 1.0s). Tight tolerance = fewer valid
solutions but tighter races; loose tolerance = more variety, can include
high-variance pieces like the vortex. No real-world calibration needed — textbook
values for μ_r (~0.005 for steel-on-plastic) combined with per-piece variance
data are well within useful accuracy for any reasonable tolerance setting.

**For perpetual mode specifically:** `--safety-margin` parameter (default 1.5×).
Require net energy per cycle ≥ margin × estimated losses so small physics
errors don't flip the sign. High safety margin = only "comfortably perpetual"
loops accepted; low margin = more candidates but some may fail in practice.

**Key reference:** [Cross 2016](https://aapt.scitation.org/doi/10.1119/1.4938149)
for the velocity-dependent μ_r form, if we need it. Unlikely we will.

---

## Phase 3 preview — Race & Perpetual modes

**Race mode:**
- Generate N candidate tracks independently (using Phase 2 physics to compute estimated completion time AND variance)
- Score by expected time spread AND variance overlap — tight tolerance avoids high-variance pieces; loose tolerance embraces them
- Constraint: 3 starters, 3 goals, no overlap in cells
- Parameter: `--tolerance SECONDS` controls how close track times must be

**Perpetual mode:**
- Detect cycles in the track graph (Tarjan's SCC or equivalent)
- For each cycle, compute net energy per traversal: `Σ inputs − Σ losses`
- Valid layout: at least one cycle with net ≥ `safety_margin × losses`
- Parameter: `--safety-margin MULTIPLIER` (default 1.5×) controls how much surplus is required
- Energy inputs on starter-only inventory: just the Magnetic Cannon. Chain them or use multiple to close the loop.

Both modes reuse ~80% of Phase 1 code. The generator just gets a different
scoring function and a different validity constraint.

---

## Known unknowns (ordered by risk)

**High risk — could derail M3/M6:**

1. **Hex rotation convention.** What does `hex_rotation = 0` mean for each tile?
   → *Mitigation: parse real curve-heavy courses, inspect the data.*

2. **Rail "side_hex_rot" semantics.** Which of 6 hex edges does it identify?
   → *Mitigation: infer from real courses.*

3. **Baseplate arrangement.** How do 4 baseplates tile together in world coords?
   → *Mitigation: parse a course that uses all 4 plates.*

4. **Retainer ID assignment.** Sequential, hashed, arbitrary?
   → *Mitigation: parse + inspect real data.*

**Medium risk:**

5. Binary endianness + string encoding (probably little-endian UTF-8, verify in M2)
6. GUID generation (app may or may not validate; try random first)
7. Connection rules per tile type (not in schema; derive from physical specs + real courses)

**Low risk:**

8. Starter-set piece counts (Staples listing is trustworthy, double-check against a physical box)
9. Which TileKind maps to the "3-in-1" / "vortex" / "landing" marketing names

**Phase 2+ unknowns (don't block v1):**

10. Does the GraviTrax app expose a physics API? (Check before we build our own — may be easier than we think.)

---

## De-risking strategy: parse first, generate second

1. Pull 3-5 real `.course` files from `murmelbahn.fly.dev/course/CODE/raw`
2. Build `parser.py` from the schema
3. Verify via round-trip: parse real → re-serialize → byte-compare
4. *Only then* build the generator

This front-loads schema-interpretation risk into M2-M3. By the time we build
the generator (M5), serialization is a solved problem.

**Course codes to target for fixtures:**
- A simple user-submitted course (small, few tile types)
- A PRO course (exercises PRO-specific fields)
- A POWER course (targets our chosen save version)
- The one from the murmelbahn README: `GDZJZA3J3T`

---

## Environment notes

**Local dev (Mac M1):** Python 3.11+, `venv` or `uv` (`uv` preferred — fast and
handles pyproject.toml natively), `pytest` for tests.

**Editor:** VS Code now, Cursor planned. Both read the same files; the only
Cursor-specific addition is a `.cursorrules` file at repo root with project
conventions (path expectations, code style, the "don't add terminal commands
at top of files" rule from your preferences). Zero switching cost otherwise.

**AI coding context:** Your `ctree` / `claudeproject` workflow works identically
in Cursor. `.cursorrules` makes the in-editor AI aware of conventions without
needing to paste them every time.

---

## Open questions for Colby

1. **Python version?** 3.11, 3.12, or 3.13?
2. **Env manager?** `uv` (recommended), `venv`, `poetry`?
3. **Test framework?** `pytest` (default) or preference otherwise?
4. **`gh` CLI installed?** Smoother repo creation if yes.
5. **GitHub username** for README links?
6. **OK to pull real course files via murmelbahn's public API as test fixtures?**
   (Low stakes — public endpoint — but flagging since we're being thoughtful about legal.)
