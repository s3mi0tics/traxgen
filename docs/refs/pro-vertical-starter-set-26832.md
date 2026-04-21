# GraviTrax PRO Vertical Starter Set (26832)

Reconciled contents list. Derived from Colby's physical piece
inspection + the Fandom wiki page + extensive back-and-forth
untangling of conflicting naming conventions across sources.

## Primary sources

1. **Physical piece inspection** — Colby has the box and confirmed
   every count in this list against actual pieces.
2. **Fandom wiki page for 26832:**
   https://gravitrax.fandom.com/wiki/Vertical_Starter_Set
3. **docs/refs/rail-specs.md** — rail capacity (max Δheight, max
   hex distance) for starter-set rails.

## Source priority

Physical inspection > wiki > Ravensburger product listings.
Ravensburger listings (and the various retailer regurgitations of
them) were inconsistent about wall counts, X-intersection counts,
and whether certain pieces are inserts vs standalone tiles.

## Piece identity reconciliation

Two physically distinct pieces exist that both involve "three
paths" — easy to conflate, but DIFFERENT:

### THREEWAY (insert — TileKind 9)
- Fits into a basic-tile frame
- Ball enters any of 3 sides, exits based on direction — passive
  junction
- Marketed as: "Y-point", "3-way junction", "junction", "threeway"

### THREE_ENTRANCE_FUNNEL (standalone tile — TileKind 56)
- Full hex tile, sits on baseplate like a curve
- 3 entrances, 1 fixed exit (funnel behavior)
- Marketed as: "3-way merge", "3-in-1 tile"

TileKind assignment for THREE_ENTRANCE_FUNNEL is best-guess from
the schema name. Confirmable by parsing a real fixture that uses
this piece. High confidence but not proven.

This finding also resolves the long-standing Core Starter-Set
mystery: the "1 3-in-1 tile" in 22410 is THREE_ENTRANCE_FUNNEL,
not a separate unmapped piece.

## Full contents (26832)

### Standalone track tiles
| Count | Piece | TileKind |
|-------|-------|----------|
| 1 | Launch Pad | STARTER |
| 28 | Curve | CURVE |
| 4 | X-intersection | CROSS |
| 1 | Vortex | SPIRAL |
| 1 | Magnetic Cannon | CANNON |
| 1 | Finish Line | GOAL_RAIL |
| 1 | 3-way merge / "3-in-1" | THREE_ENTRANCE_FUNNEL (best-guess) |

SPLASH is NOT in this set. Earlier confusion: the bowl-shaped
piece that drops a marble vertically is SPIRAL (vortex), not
SPLASH.

### Inserts (live as tree nodes, slot into basic-tile frames)
| Count | Piece | TileKind |
|-------|-------|----------|
| 2 | Catcher | CATCH |
| 1 | Freefall / Drop | DROP |
| 1 | Threeway / Y-point junction | THREEWAY |
| 1 | Landing | GOAL_BASIN |

5 inserts total, 3 basic-tile frames to hold them. Only 3 can be
active at any one time (frame-count limit). Tracked in Inventory
as `basic_tile_frames = 3`.

### Switches (pool of 2 physical pieces)
Each physical switch can be configured as either SWITCH_LEFT or
SWITCH_RIGHT. Inventory encodes this as 2 of each TileKind (so
either configuration is valid for a placed piece), with a pool
constraint enforced by the validator: total placed
(SWITCH_LEFT + SWITCH_RIGHT) must not exceed 2.

| Count | Piece | TileKind |
|-------|-------|----------|
| 2 (pool) | Switch | SWITCH_LEFT and/or SWITCH_RIGHT |

### Height tiles (stackers)
Stackers are not tree nodes — they're encoded as the
`height_in_small_stacker` field on whichever tile sits on top.
See docs/refs/tree-node-height-semantics.md.

| Count | Piece | TileKind |
|-------|-------|----------|
| 20 | Full height tile | STACKER |
| 9 | Half height tile | STACKER_SMALL |

### Structural (PRO-line, kept in StructuralInventory)
Walls and single balconies have no TileKind. Pillars map to TileKind
via PILLAR_KIND_TO_TILE_KIND. Double balconies have a TileKind but
are counted with other balconies for conceptual consistency.

| Count | Piece | Schema representation |
|-------|-------|-----------------------|
| 8 | Solid pillar | STACKER_TOWER_CLOSED (tree node) |
| 4 | Tunnel pillar | STACKER_TOWER_OPENED (tree node) |
| 2 | Long wall | WallConstructionData with 3-hex span |
| 2 | Medium wall | WallConstructionData with 2-hex span |
| 1 | Short wall | WallConstructionData with 1-hex span |
| 16 | Single balcony | WallBalconyConstructionData with cell |
| 4 | Double balcony | DOUBLE_BALCONY (tree node) |

### Rails
Rail length is not stored on the rail itself — it's inferred from
hex distance between the rail's two endpoints. See
docs/refs/rail-specs.md for per-length capacity (max Δheight).

| Count | Piece | RailKind |
|-------|-------|----------|
| 9 | Short straight | STRAIGHT (inferred length) |
| 6 | Medium straight | STRAIGHT (inferred length) |
| 3 | Long straight | STRAIGHT (inferred length) |
| 3 | Bernoulli left | BERNOULLI_SMALL_LEFT |
| 3 | Bernoulli right | BERNOULLI_SMALL_RIGHT |
| 2 | Bernoulli straight | BERNOULLI_SMALL_STRAIGHT |

Total: 18 STRAIGHT rails (pool) + 8 Bernoulli rails (3 kinds) = 26 rails.

Note: in Ravensburger's piece-count accounting, GOAL_RAIL (finish
line) is often counted as a "rail" bringing the user-facing rail
total to 27. We keep GOAL_RAIL as a tile in our data model because
the schema stores it as a TileKind.

### Scalars
| Count | Item |
|-------|------|
| 3 | Basic tile frames (hold up to 3 inserts) |
| 4 | Cardboard baseplates |
| 1 | Transparent level |
| 6 | Marbles |

## Total piece count: 151

Broken down Colby's way (physical-pile categories):

- tiles + inserts: 47 (standalone tiles + inserts + switches + basic-tile frames)
- stackers: 29
- platforms (baseplates + transparent): 5
- walls: 5
- rails (incl. GOAL_RAIL): 27
- balconies: 20
- towers (pillars): 12
- balls: 6

Total = 151.

Ravensburger advertises 153. The 2-piece discrepancy is unresolved.
Possibilities: rail-related hardware (connectors?) counted
separately, or a miscount on Ravensburger's side. Not pursuing
for v1.

## Known behavioral quirks (not validator-blocking in v1)

- **Switch state**: each switch starts in a LEFT or RIGHT state.
  Ball passes alternate the state. The starting state matters for
  generation — the generator must declare it per-switch. Validator
  can ignore starting state for v1.
- **Switch TileKind encoding (UNVERIFIED)**: we currently assume
  starting state is encoded via TileKind (`SWITCH_LEFT` vs
  `SWITCH_RIGHT`). This is plausible based on the GDZJZA3J3T probe
  (1 of each kind in that course) but not proven. The alternative
  is that LEFT and RIGHT are different physical pieces and starting
  state is stored in a separate field we haven't identified. To
  verify: export a course from the GraviTrax app with a single
  switch in a known starting state, parse it, see which TileKind
  shows up. Until verified, inventory uses 2+2 pool encoding and
  the validator budget rule enforces pool size.
- **Cannon single-use**: a Magnetic Cannon accepts only one ball.
  A second ball arriving while the first is loaded breaks the
  intended behavior. Future "piece preconditions" rule.
