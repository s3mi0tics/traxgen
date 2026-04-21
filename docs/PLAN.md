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
- `traxgen/validator.py` — **in progress.** Skeleton in place; rules added
  one at a time.
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
4. **M4 Validator** — **in progress.** Given a domain object, correctly
   answer "is this legal?"
5. **M5 Generator** — not started. Produces a valid domain object using
   only inventory pieces.
6. **M6 End-to-end** — not started. Generated file opens in the real
   GraviTrax app.

### M4 (current) — validator design

Soft-validation API: `validate(course, inventory)` returns a list of
`Violation` objects. `validate_strict` wraps it and raises `ValidationError`
if ERROR-severity violations exist. Each rule is a private `_check_*`
function registered in `_CHECKS`. No cross-rule dependencies; we introduce
a shared context later if profiling says we need it.

v1 rules, approximate order of implementation:

1. `INVENTORY_BUDGET_TILES` — tile counts by TileKind don't exceed inventory.
   Includes baseplate count. Also the switch-pool special case
   (sum of `SWITCH_LEFT` + `SWITCH_RIGHT` placed ≤ pool size).
2. `INVENTORY_BUDGET_STACKERS` — sum of `height_in_small_stacker` across all
   tree nodes is feasible given available STACKER + STACKER_SMALL counts.
3. `INVENTORY_BUDGET_STRUCTURAL` — pillar, wall, balcony counts don't exceed
   the `structural` inventory. Walls counted from `wall_construction_data`;
   pillars from tree nodes; single balconies from `WallBalconyConstructionData`
   entries with non-null cells; double balconies from `DOUBLE_BALCONY` tree
   nodes.
4. `INVENTORY_BUDGET_RAILS` — rail counts by `RailKind` don't exceed inventory.
   For STRAIGHT rails, additionally bucket each placed rail by endpoint hex
   distance and compare against per-length limits.
5. `BASEPLATE_COVERAGE` — every cell's layer is present in the course's
   layer set.
6. `CELL_COLLISION` — no two cells share `(layer_id, local_hex_position)`.
7. `RAIL_ENDPOINT_MISSING` — each rail endpoint refers to a cell/retainer
   that exists.
8. `PILLAR_ENDPOINT_MISSING` — pillar endpoints refer to existing cells
   and layers.
9. `RETAINER_ID_COLLISION` — retainer IDs are unique across tiles, pillars,
   walls.
10. `LAYER_ID_COLLISION` — layer IDs are unique.
11. `ROTATION_OUT_OF_RANGE` — `hex_rotation` and `side_hex_rot` are in `[0, 5]`.
12. `MISSING_STARTER_OR_GOAL` — at least one tile with `is_starter=True`
    and one with `is_goal=True`.
13. `TILE_INDEX_COLLISION` — tree-node `index` values are unique within a cell.

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
   together. Inferable from a fixture that uses all 4 plates.
4. **Retainer ID assignment scheme** — sequential/hashed/arbitrary.
   Inferable from fixtures.
5. **GUID generation** — the app may or may not validate course GUIDs.
   M6-blocking risk. Try random first; regenerate if the app rejects.
6. **Connection rules per tile type** — not in schema. Derive from physical
   specs and real fixtures.
7. **`THREE_ENTRANCE_FUNNEL` TileKind assignment** — best-guess mapping
   for the "3-in-1" / "3-way merge" piece. Confirmable by parsing a
   fixture that uses this piece.

### Resolved since original plan

- Hex rotation convention — verified in M2.
- Stacker representation — not tree nodes; they live as
  `height_in_small_stacker` on whichever tile sits on the stack. See
  `docs/refs/tree-node-height-semantics.md`.
- Pillar height semantics — 14 small-stacker units per pillar; the `h` field
  on pillar nodes is stackers-below-base, same rule as any other tile.
- Starter-set piece counts — fully reconciled for 26832 through physical
  inspection. 3-in-1 mystery resolved as `THREE_ENTRANCE_FUNNEL` (best-guess).

### Phase 2+ unknowns (don't block v1)

- Whether the GraviTrax app exposes a physics API.

### Deferred cleanup (small, not blocking)

- `CourseElementGeneration.AUTUMN_2024 = 10` exists in Rust but not in
  `types.py`. Won't hit it on any POWER_2022 fixture.
- `PillarConstructionData.{lower,upper}_layer_id` — parser reads u32,
  Rust struct is i32. Bytes identical for non-negative IDs. Fix before
  M5 if we care about negative layer IDs.

---

## De-risking strategy

Phase 1 sequence was parse first, generate second. Front-loads
schema-interpretation risk into M2–M3. The generator (M5) inherits a
proven serializer.

Fixtures at `tests/fixtures/`; `GDZJZA3J3T.course` is a kitchen-sink course
that exercises almost every schema path. Add more user-submitted or
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