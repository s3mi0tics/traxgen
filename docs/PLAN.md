# traxgen — Plan

A procedural generator for GraviTrax marble run courses. Takes a piece
inventory, outputs a binary course file that opens in the official GraviTrax
app.

> Not affiliated with Ravensburger. "GraviTrax" is their trademark.
> This project reads and writes the binary course format reverse-engineered by
> [lfrancke/murmelbahn](https://github.com/lfrancke/murmelbahn) (Apache-2.0).

---

## Living document discipline

This plan drifts as we work. At the end of any session where something
substantive changed — a design decision got made, a new file became relevant,
a reference proved useful or useless, scope shifted, a milestone completed —
propose an updated version. Same rule applies to handoff prompts: they are
living documents and the next session should be told to propose updates at
its own end.

What to watch for when updating:
- **References block** (`docs/refs/`) — add anything we lean on, remove what
  turned out wrong.
- **Design decisions** — when an open question gets answered, move it to
  "decided: X, because Y."
- **Files in play** — when modifying a file not already in the module plan,
  add it.
- **Deferred cleanup** — add items as we find them, remove them when fixed.
- **Gotchas** — if something bit us, log it in environment notes.

---

## Confirmed decisions

| Decision | Choice |
|---|---|
| Language | Python 3.12 (pinned via `.python-version`; TypeScript port after v1) |
| Output | Binary `.course` file, schema version `POWER_2022` (v4) |
| Target inventory | **PRO Vertical Starter-Set (26832)**, 151 pieces, 4 baseplates |
| Env manager | `uv` |
| Test framework | `pytest` + `hypothesis` for property-based tests |
| Repo name | `traxgen` |
| Visibility | Public — https://github.com/s3mi0tics/traxgen |
| License | MIT |
| Schema reference | lfrancke/murmelbahn Rust source (`lib/src/app/layer.rs`) |
| Project layout | Flat package (`traxgen/traxgen/`), not src-layout |
| Validator API | Soft validation (returns list of Violations) + `validate_strict` wrapper |
| Rail data model | Flat `Mapping[RailKind, int]` with separate `straight_rail_limits` for per-length counts |

### Inventory target change (from Core 22410 → PRO Vertical 26832)

Originally planned around Core Starter-Set (22410). Switched to 26832 because
Colby has that physical set and needs to validate generated courses physically
against real pieces. The data model still supports Core via `CORE_STARTER_SET`;
that inventory is cataloged and tested alongside PRO Vertical.

---

## Long-term vision

Three generation modes, each progressively harder:

1. **Single-track mode** *(v1 — Phase 1)* — topologically valid track with
   ball reaching goal. No physics, no aesthetics. Proves the pipeline.
2. **Race mode** *(Phase 3)* — generate 3 parallel tracks with approximately
   equal travel times. Requires physics simulation, multi-track spatial
   planning, and a variance-minimizing optimizer.
3. **Perpetual mode** *(Phase 3)* — generate a closed-loop track with one or
   more energy-adding pieces such that net energy per cycle is at least 0.
   Requires cycle detection and energy-budget accounting.

Phase 2 and 3 aren't built in v1, but **the data model in v1 supports them
without a rewrite.** Pieces carry energy metadata from day one (via
`EnergyProfile`), and the generator will be pluggable via `GenerationMode`.

---

## Phase 1 success criterion

A single command — `python -m traxgen generate --set vertical-starter` —
produces a `.course` binary file that:

1. Opens in the official GraviTrax app without errors.
2. Uses only pieces from the PRO Vertical Starter-Set (26832) inventory.
3. Has a valid ball path from a starter tile to a goal tile.
4. Fits on the 4 baseplates the starter ships with.

Non-goals for v1: interesting tracks, variety, physics simulation, aesthetics,
race mode, perpetual mode. We are proving "the pipeline works end-to-end."

---

## Module plan

- `traxgen/types.py` — **done.** Schema enums, 1:1 with binary format.
- `traxgen/hex.py` — **done.** Axial coords, neighbors, rotation, distance.
- `traxgen/inventory.py` — **done.** `PieceSpec`, `Inventory`,
  `CORE_STARTER_SET`, `PRO_VERTICAL_STARTER_SET`, `StructuralInventory`,
  rail length specs.
- `traxgen/domain.py` — **done.** Course/Layer/Cell/TileTower/Rail dataclasses.
- `traxgen/parser.py` — **done.** Reads `.course` binaries (POWER_2022).
- `traxgen/serializer.py` — **done.** Writes `.course` binaries, byte-compare
  round-trip tested against GDZJZA3J3T.
- `traxgen/validator.py` — **in progress (5/13 v1 rules done + 3 Phase 2
  rules deferred).** All four inventory-budget rules plus
  `MISSING_STARTER_OR_GOAL` shipped; 8 v1 referential-integrity,
  schema-validity, and reachability rules remain. Three additional
  energy-based rules are Phase 2 scope.
- `traxgen/generator.py` — **not started.** Pluggable by `GenerationMode`.
- `traxgen/physics.py` — **not started.** Stub for Phase 2.

Test coverage mirrors the module layout. Fixtures live at `tests/fixtures/`;
`GDZJZA3J3T.course` is committed. Scripts (fixture fetcher and similar) live
at `scripts/`. Reference material (rail specs, structural notes, set
contents) lives at `docs/refs/`.

---

## Phase 1 milestones

1. **M1 Foundation** — **done.** `types.py`, `hex.py`, `inventory.py` cover
   schema, hex math is unit-tested.
2. **M2 Domain + parser** — **done.** Parse a real `.course` file into
   Python objects.
3. **M3 Round-trip** — **done (bbf7e36).** Parse → serialize → byte-compare
   matches original.
4. **M4 Validator** — **in progress (5/13 v1 rules done + 3 Phase 2
   rules deferred).** Given a domain object, correctly answer "is this
   legal?"
5. **M5 Generator** — not started. Produces a valid domain object using
   only inventory pieces.
6. **M6 End-to-end** — not started. Generated file opens in the real
   GraviTrax app.

### M4 — validator design

Soft-validation API: `validate(course, inventory)` returns a list of
`Violation` objects. `validate_strict` wraps it and raises `ValidationError`
if ERROR-severity violations exist. Each rule is a private `_check_*`
function registered in `_CHECKS`. No cross-rule dependencies in v1; we
introduce a shared context later if profiling says we need it.

Rules are implemented incrementally, one commit per rule, each with its own
unit tests. A single integration test (`test_validate_gdzjza3j3t_against_
unlimited_inventory_is_clean`) validates every registered rule against the
real GDZJZA3J3T fixture — details in "De-risking strategy" below.

#### v1 rule status

1. ✅ `INVENTORY_BUDGET_TILES` — tile counts by TileKind don't exceed
   inventory. Includes baseplate count (BASE_LAYER layers) and the
   switch-pool special case (sum of `SWITCH_LEFT` + `SWITCH_RIGHT` placed ≤
   pool size). Skips STACKER, STACKER_SMALL (handled by stackers rule) and
   STACKER_TOWER_CLOSED, STACKER_TOWER_OPENED, DOUBLE_BALCONY (handled by
   structural rule) in its per-kind check.
2. ✅ `INVENTORY_BUDGET_STACKERS` — two checks: (1) total
   `height_in_small_stacker` across all tree nodes ≤ 2×STACKER + STACKER_SMALL,
   and (2) count of odd-height stacks ≤ STACKER_SMALL. The parity check
   catches cases where total units fit but pieces don't (large stackers are
   indivisible size-2 pieces; odd-h stacks need exactly one small each).
3. ✅ `INVENTORY_BUDGET_STRUCTURAL` — pillar, wall, balcony counts don't
   exceed `structural` inventory. Walls use hex-distance-to-kind inference
   (1=SHORT, 2=MEDIUM, 3=LONG) on their tower endpoints. Walls with
   unexpected distances are silently skipped (deferred cleanup — see below).
   Single balconies count only when `cell_construction_data` is non-null
   (assumption, unverified).
4. ✅ `INVENTORY_BUDGET_RAILS` — per-kind count vs `inventory.rails[kind]`.
   For STRAIGHT rails, a fixed-length sub-budget: distance → length
   (1=SHORT, 2=MEDIUM, 3=LONG) with no cascading coverage. Invalid spans
   (d ∉ {1,2,3}) emit per-placement violations with `Location` populated.
   Cross-retainer STRAIGHT rails are skipped from the sub-budget — local
   coordinates can't yield physical distance across retainers without the
   baseplate world-arrangement answer (still-open unknown).
5. ⬜ `BASEPLATE_COVERAGE` — every cell's layer is present in the course's
   layer set.
6. ⬜ `CELL_COLLISION` — no two cells share `(layer_id, local_hex_position)`.
7. ⬜ `RAIL_ENDPOINT_MISSING` — each rail endpoint refers to a cell/retainer
   that exists.
8. ⬜ `PILLAR_ENDPOINT_MISSING` — pillar endpoints refer to existing cells
   and layers.
9. ⬜ `RETAINER_ID_COLLISION` — retainer IDs are unique across tiles,
   pillars, walls.
10. ⬜ `LAYER_ID_COLLISION` — layer IDs are unique.
11. ⬜ `ROTATION_OUT_OF_RANGE` — `hex_rotation` and `side_hex_rot` are in
    `[0, 5]`.
12. ✅ `MISSING_STARTER_OR_GOAL` — at least one tile with `is_starter=True`
    and one with `is_goal=True`. Catalog-derived: `_STARTER_KINDS` and
    `_GOAL_KINDS` are computed from `PieceSpec` flags at import time, so
    adding a new catalog entry with `is_starter=True` (e.g., `DOME_STARTER`
    when the POWER line is cataloged) automatically satisfies the rule.
    Two independent violations — empty course fires both. **Single-track
    mode only.** Perpetual mode is a closed loop and doesn't require a
    starter or goal; when M5+ introduces `GenerationMode`, this rule will
    need mode-awareness (either mode-gated registration or a mode-aware
    dispatch). See "Starter/goal override API" in deferred cleanup.
13. ⬜ `TILE_INDEX_COLLISION` — tree-node `index` values are unique within
    a cell.
14. ⬜ `START_GOAL_CONNECTED` — a topological path exists from some
    starter to some goal through the track graph. Pure graph reachability;
    no physics. Requires a track-graph representation (piece-exit
    adjacency via rails) that doesn't exist yet — probably lives in its
    own module (`traxgen/graph.py`) since the generator will reuse it
    in M5. Flagged by Colby during M4 as a fundamental playability
    requirement alongside `MISSING_STARTER_OR_GOAL`.
15. ⬜ `SUFFICIENT_POTENTIAL_ENERGY` *(Phase 2)* — total energy along the
    path from starter to goal is positive: initial PE + energy-input-piece
    contributions ≥ cumulative losses. Aggregate check, depends on the
    Phase 2 physics model. Not v1.
16. ⬜ `NO_ENERGY_DEADLOCK` *(Phase 2)* — KE remains positive at every
    point along the path. Point-wise check; a flat section after a drop
    can drain KE to zero even when the aggregate energy budget is
    positive. Harder than #15. Not v1.

**Rule interaction note:** rules are nominally independent but the tiles
rule explicitly skips kinds owned by the stackers and structural rules.
When adding new rules that partition `TileKind` space, update the tiles
rule's skip set accordingly.

---

## Phase 2 preview — Physics simulation

Not in v1. Data model supports it via `EnergyProfile` in `inventory.py`.

Per-traversal energy bookkeeping (placeholder, not implemented):

    delta_E = delta_PE - mu_r * m * g * cos(theta) * d - piece_loss

`EnergyProfile` fields: `path_length_mm`, `height_change_mm`,
`energy_input_j`, `loss_coefficient`, `expected_time_ms`, `time_variance_ms`.

Variance is a first-class feature — some pieces are designed to be stochastic
(vortex spin-down, trampoline bounce, turntable phase-on-entry, catapult
release). Rough tiers:

- Low (< 50ms): straight rails, curves, drops, magnetic cannon.
- Medium (50–300ms): splash, catch, switches, junctions.
- High (300–1000ms): vortex, turntable, cascade, mixer.
- Very high (1000ms+): trampoline, volcano, spring-loaded pieces.

Accuracy target: user-settable tolerance via `--tolerance SECONDS` (default
1.0s). Tight tolerance = fewer valid solutions, tighter races. Loose
tolerance = more variety including high-variance pieces. No real-world
calibration needed; textbook mu_r (~0.005 for steel-on-plastic) plus
per-piece variance data is within useful accuracy for any reasonable
tolerance setting.

Perpetual mode safety margin: `--safety-margin MULTIPLIER` (default 1.5x).
Require net energy per cycle ≥ margin × estimated losses.

Key reference: Cross 2016 (AAPT) for velocity-dependent mu_r form, if needed.

---

## Phase 3 preview — Race and Perpetual modes

**Race mode:**
- Generate N candidate tracks independently using Phase 2 physics to compute
  estimated completion time and variance.
- Score by expected time spread and variance overlap.
- Constraint: 3 starters, 3 goals, no overlap in cells.
- Parameter: `--tolerance SECONDS`.

**Perpetual mode:**
- Detect cycles in the track graph (Tarjan's SCC or equivalent).
- For each cycle, compute net energy: sum of inputs minus sum of losses.
- Valid layout: at least one cycle with net ≥ safety_margin × losses.
- Parameter: `--safety-margin MULTIPLIER`.

Both modes reuse ~80% of Phase 1 code.

---

## Known unknowns

### Still open (v1-scope)

1. **Switch TileKind encoding.** Unverified whether switch starting state is
   encoded via `SWITCH_LEFT` vs `SWITCH_RIGHT` TileKind, or via a separate
   field. Current working assumption: TileKind-encoded. Pool semantics
   (up to 2 total placements) is the v1 validator rule. To verify: export
   a course from the app with a single switch in a known state, parse it,
   observe which TileKind shows up. See
   `docs/refs/pro-vertical-starter-set-26832.md`.
2. **Rail `side_hex_rot` semantics** — which of 6 hex edges it identifies.
   Inferable from fixtures when M5 needs it.
3. **Baseplate world-coordinate arrangement** — how 4 baseplates tile
   together in world space. Now actively blocking cross-retainer rail
   span validation (see #8 below). Inferable from a fixture that uses
   all 4 plates.
4. **Retainer ID assignment scheme** — sequential/hashed/arbitrary.
   Inferable from fixtures.
5. **GUID generation** — the app may or may not validate course GUIDs.
   M6-blocking risk. Try random first; regenerate if the app rejects.
6. **Connection rules per tile type** — not in schema. Derive from physical
   specs and real fixtures.
7. **`THREE_ENTRANCE_FUNNEL` TileKind assignment** — best-guess mapping
   for the "3-in-1" / "3-way merge" piece. Confirmable by parsing a
   fixture that uses this piece.
8. **Cross-retainer rail geometry.** Rail endpoints use
   `cell_local_hex_pos` (local to the endpoint's retainer). For rails
   spanning different retainers, local distance doesn't reflect physical
   span. GDZJZA3J3T has real cross-retainer STRAIGHT rails with local
   distances 0 and 5 (impossible for a fixed-length piece). The rails
   validator skips cross-retainer rails from the length sub-budget as a
   workaround. Proper validation needs world coordinates, which needs
   unknown #3 resolved.
9. **Track-graph representation.** Needed for `START_GOAL_CONNECTED`
   (rule #14) and reused by the generator in M5. Nodes = piece exits;
   edges = rails (and implicit through-piece connections for multi-exit
   pieces like switches, junctions, threeway). Connection semantics per
   tile type (unknown #6) feeds directly into this. Likely lands in its
   own module (`traxgen/graph.py`) rather than bolted into the validator.
   Design when #6 is answered enough to be worth it.

### Resolved since original plan

- Hex rotation convention — verified in M2.
- Stacker representation — not tree nodes; they live as
  `height_in_small_stacker` on whichever tile sits on the stack. See
  `docs/refs/tree-node-height-semantics.md`.
- Pillar height semantics — 14 small-stacker units per pillar; the `h` field
  on pillar nodes is stackers-below-base, same rule as any other tile.
- Starter-set piece counts — fully reconciled for 26832 through physical
  inspection. 3-in-1 mystery resolved as `THREE_ENTRANCE_FUNNEL` (best-guess).
- **Rail length semantics — fixed, not "up-to."** A SHORT rail spans exactly
  1 hex. MEDIUM spans exactly 2. LONG spans exactly 3. No cascading coverage
  where a longer rail can satisfy a shorter demand — each physical piece has
  one fixed length. Informed the bucket-check logic in the rails validator.
- **Stacker budget isn't a simple sum.** Large stackers are indivisible
  size-2 pieces at one physical location. A course with total-units at
  capacity can still be infeasible if too many individual stacks have odd
  heights — each odd-h stack needs exactly one small stacker. Parity check
  added to the stackers rule alongside the total-units check.
- **Integration canary pattern.** Validating a real parsed fixture against
  an unlimited inventory catches rule bugs that synthetic unit tests miss.
  Caught a real false-positive in the rails rule on the commit that added
  it. See "De-risking strategy" for the pattern.
- **Cannon is not a starter.** Originally `PieceSpec(CANNON, is_starter=True)`
  on the belief that a cannon could launch a ball. Corrected during M4
  design for `MISSING_STARTER_OR_GOAL`: the cannon is an energy injector,
  not a starter — it requires an incoming ball (via gravity from
  elsewhere) to do anything. Its role is modeled via
  `energy_profile.energy_input_j`, not `is_starter`. Fixed in commit d89218f;
  the validator rule is catalog-derived so the fix flowed through
  automatically.
- **Playability ≠ just "has starter and goal."** A valid single-track course
  needs: (a) at least one starter and one goal, (b) a topological path
  between them, (c) enough potential energy (plus any energy-input pieces)
  to traverse the path accounting for losses, and (d) no point along the
  path where KE drops to zero. Items (a) and (b) are v1 (rules
  `MISSING_STARTER_OR_GOAL` and `START_GOAL_CONNECTED`); (c) and (d)
  require the Phase 2 physics model. Perpetual mode doesn't need (a) at
  all — closed loop. Race mode wants N starters and N goals.

### Phase 2+ unknowns (don't block v1)

- Whether the GraviTrax app exposes a physics API.

### Deferred cleanup (small, not blocking)

- `CourseElementGeneration.AUTUMN_2024 = 10` exists in Rust but not in
  `types.py`. Won't hit it on any POWER_2022 fixture.
- `PillarConstructionData.{lower,upper}_layer_id` — parser reads u32,
  Rust struct is i32. Bytes identical for non-negative IDs. Fix before
  M5 if we care about negative layer IDs.
- **Mounted-only balcony counting** — assumption in
  `_check_inventory_budget_structural` that a balcony slot counts against
  inventory only when it holds a cell. Verify against a fixture with
  explicit balcony placements; revise if empty slots are also consumed
  pieces.
- **Walls with unexpected hex distance** — silently skipped in
  `_check_inventory_budget_structural`. A future schema-validity rule
  should flag distance ∉ {1, 2, 3} as invalid wall geometry.
- **Starter/goal override API.** `_STARTER_KINDS` and `_GOAL_KINDS` in the
  validator are catalog-derived globals — no per-call override. Custom
  generation modes or experimental house-rules (e.g., treating a cannon
  as a starter because the user will physically drop a ball on it) would
  need an escape hatch. Likely shape: optional `starter_kinds` /
  `goal_kinds` parameters on `validate()`, or a future `ValidatorConfig`
  object, or mode-aware dispatch from `GenerationMode`. Design when a
  real consumer forces the shape — don't pre-build.

---

## De-risking strategy

Phase 1 sequence was parse first, generate second. Front-loads
schema-interpretation risk into M2–M3. The generator (M5) inherits a
proven serializer.

**Integration canary for validator rules.** Every commit that adds or
modifies a validator rule runs against the GDZJZA3J3T fixture with an
inventory of 10,000 of everything. Any violation emitted = a rule is
misreading real binary data, not a legitimate budget overrun. Added
during M4 after Colby flagged the risk of accumulating assumption bugs
across rules without end-to-end testing. Has already caught one bug
(cross-retainer rails in the rails sub-budget). Extend or replace with
additional canary fixtures as needed — same-layer-only courses,
starter-set-only courses — when a rule demands narrower coverage.

Fixtures at `tests/fixtures/`; `GDZJZA3J3T.course` is a kitchen-sink course
that exercises almost every schema path, including cross-retainer rails,
stacked pillars, and wall-mounted balconies. Add more user-submitted or
starter-set-only fixtures if specific validator rules need a clean oracle.

Endpoint for fetching fixtures: `murmelbahn.fly.dev/api/course/{code}/raw`.

---

## Environment notes

Local dev is on a Mac M1, Python 3.12 pinned via `.python-version`, `uv` for
env management, `pytest` for tests.

Known gotchas:

- `uv run python -m scripts.foo` puts the project on `sys.path`. Plain
  `uv run python scripts/foo.py` does NOT. Learned the hard way in M2.
- Shell-quoted Python with `!` triggers zsh history expansion. For anything
  fancier than a trivial one-liner, use a heredoc:
  `cat > /tmp/foo.py << 'PYEOF' ... PYEOF` then `uv run python ...`.
- Long bash blocks containing heredocs with markdown content can be fragile.
  If a block fails silently (command not found on comment lines,
  unexpected truncation), prefer writing the file via a standalone artifact
  download.
- The murmelbahn repo was cloned at `/tmp/murmelbahn-src` in earlier sessions;
  may be wiped. Re-clone if needed:
  `git clone https://github.com/lfrancke/murmelbahn /tmp/murmelbahn-src`.
- `ctree` command outputs project structure — ask if needed.

Editor: VS Code, optionally Cursor. `.cursorrules` at repo root carries
project conventions.

---

## References folder (docs/refs/)

Committed reference material for when web sources disagree or disappear.
Source priority: physical inspection > wiki > Ravensburger product listings.
Ravensburger listings have been the least reliable in practice.

- `README.md` — index.
- `rail-specs.md` — reconciled rail capacity (hex distance, max Δheight) for
  starter-set rails. Physical manual beats the Fandom wiki (which is wrong
  about long-rail Δheight).
- `tree-node-height-semantics.md` — how `height_in_small_stacker` works on
  tree nodes (probe evidence plus semantic reasoning).
- `pro-structural-notes.md` — pillars, walls, balconies for the PRO line.
  Not v1-validator-blocking; documentation for future expansion.
- `pro-vertical-starter-set-26832.md` — full reconciled contents list for
  26832, plus behavioral quirks (switch state, cannon single-use).
- `starter-set-manual/` — photos of relevant manual pages; primary source
  for rail Δheight specs.
