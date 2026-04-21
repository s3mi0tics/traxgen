# GraviTrax PRO structural system — notes

Not in Core Starter-Set scope; logged here so future-traxgen has the
context when we expand past starter.

## The four structural piece families

### 1. Pillars (aka stacker towers)

Equivalent to 7 height tiles (Ravensburger's official spec). Two
variants in the binary format:

- `STACKER_TOWER_CLOSED` (TileKind 43) — solid; rails cannot pass
  through.
- `STACKER_TOWER_OPENED` (TileKind 44) — has negative space allowing
  rails to pass through the tower itself.

Both appear as tree nodes in cells, and both carry their own
`height_in_small_stacker` values (observed in GDZJZA3J3T: 0, 1, 3, 5).
Don't confuse with Core stackers (`STACKER`, `STACKER_SMALL`), which
are *not* tree nodes — those are encoded as the height field on
whichever tile sits on the stack.

### 2. Walls

Span between pillars. Three lengths:

| Wall   | Spans | Balcony-mount columns |
|--------|-------|-----------------------|
| Long   | 3     | 4                     |
| Medium | 2     | 3                     |
| Short  | 1     | 2                     |

Rails pass through the gaps *between* the balcony-mount columns —
fixed positions per wall length, not arbitrary spots. Walls live in
`WallConstructionData` in domain.py, not as a TileKind.

### 3. Balconies

Two Ravensburger-official variants:

- **Single balcony** (aka "balcony") — wall-mounted. Replaces height
  tiles; doesn't stack above anything. In the binary, this is a
  `cell_construction_data` hanging off a `WallBalconyConstructionData`
  slot. No standalone TileKind.
- **Double balcony** (`DOUBLE_BALCONY`, TileKind 45) — does NOT need a
  wall. Clips onto another tile or pillar. Supports additional tiles
  stacked above it. Appears as its own tree node in a cell.

Clip-on balconies from the 3D-printing community (Masked Marble,
3DRCONE) are not Ravensburger-official and have no representation in
the binary format.

## Implications for validator

- **Rail endpoint existence (v1 rule)** — when expanded past starter,
  the "cell referenced by rail endpoint must exist" check needs to
  consider balcony cells as valid endpoints, not just layer cells.
- **Rail passthrough legality (future rule)** — a rail passing through
  a wall must go through a legal slot; a rail passing through a pillar
  requires `STACKER_TOWER_OPENED`, not `STACKER_TOWER_CLOSED`.
- **Balcony stacking** — double balconies can hold stacked tiles; the
  "tiles in a cell tree" walk already handles this because the
  DOUBLE_BALCONY sits at the cell root and children stack above it.
- **Double-balcony stability rule (future)** — wiki notes the force on
  the supporting side must exceed the extended side or the balcony
  topples. Probably a warning-severity rule eventually.

## Sources

- https://gravitrax.fandom.com/wiki/Gravitrax_PRO
- Ravensburger US product listings for PRO Vertical / Giant starter
  sets (piece counts and wall column specs)
- GDZJZA3J3T fixture (probe confirmed STACKER_TOWER_* appear as tree
  nodes with height; DOUBLE_BALCONY appears as tree node at h=0)
