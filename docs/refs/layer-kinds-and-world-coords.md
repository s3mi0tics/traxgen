# LayerKind semantics and world coordinates

<!-- Path: traxgen/docs/refs/layer-kinds-and-world-coords.md -->

Captures findings from the baseplate-arrangement probe (commit 3865bcb)
and the baseplate LayerKind decision made when fixing
`INVENTORY_BUDGET_TILES`'s baseplate sub-check.

---

## The five LayerKind variants

From `lfrancke/murmelbahn`, `lib/src/app/layer.rs`:

| id | Rust name        | Our name            |
|----|------------------|---------------------|
| 0  | `BaseLayerPiece` | `BASE_LAYER_PIECE`  |
| 1  | `BaseLayer`      | `BASE_LAYER`        |
| 2  | `LargeLayer`     | `LARGE_LAYER`       |
| 3  | `LargeGhostLayer`| `LARGE_GHOST_LAYER` |
| 4  | `SmallLayer`     | `SMALL_LAYER`       |

The Rust source has no comments on the individual variants. The meaning
we've inferred comes from fixture evidence, the one docstring on
`LayerConstructionData` (see "Positioning conventions" below), and the
plural phrasing in the `layer_height` doc-comment.

## Observed counts in fixtures

### GDZJZA3J3T (POWER_2022, PRO-era kitchen-sink)

    0  BASE_LAYER
   15  BASE_LAYER_PIECE
    4  LARGE_LAYER
    0  LARGE_GHOST_LAYER
    1  SMALL_LAYER
    --
   20  total

Source: `scripts/probe_baseplate_arrangement.py`.

No other fixtures probed yet. PRO-era courses appear to use
`BASE_LAYER_PIECE` (plural small baseplate pieces that tile together) and
never `BASE_LAYER`. `LARGE_GHOST_LAYER` has not been observed in any
fixture.

## Baseplate LayerKind decision

### The question

`INVENTORY_BUDGET_TILES`'s baseplate sub-check needs to count "how many
baseplate layers does this course use?" The v1 implementation counted
only `LayerKind.BASE_LAYER`. On GDZJZA3J3T that count is zero, which is
clearly wrong — the PRO Vertical Starter-Set physically ships with 4
baseplates and GDZJZA3J3T obviously uses them. The 15 `BASE_LAYER_PIECE`
layers are the real baseplates.

So: is `BASE_LAYER` also a baseplate? Both? Or just `BASE_LAYER_PIECE`?

### Evidence

The Rust source's doc-comment on `LayerConstructionData.layer_height`
is the strongest signal:

    /// This is in multiples of 0.36 and because it's a float it's not exact.
    /// -0.2 is the layer height for all base plates

"**all base plates**" — plural. The author is treating "base plate" as a
category with multiple height-carrying variants, not a synonym for one
specific LayerKind. The two LayerKinds whose names include "base" are
`BaseLayer` and `BaseLayerPiece`.

Physical inspection also supports this. The Core Starter-Set (22410)
ships with a different baseplate form-factor than the PRO line; older
sets had one large green baseplate (plausibly `BASE_LAYER`), newer PRO
sets have smaller modular baseplate pieces that tile together
(plausibly `BASE_LAYER_PIECE`, count 15 matches PRO's modular tiling).

### Decision

**Treat both `BASE_LAYER` and `BASE_LAYER_PIECE` as baseplates** for the
purposes of inventory budgeting. Encoded in
`traxgen/validator.py` as `_BASEPLATE_LAYER_KINDS`.

### Why this, not the alternatives

**Option considered: count only `BASE_LAYER_PIECE`.** Would match
GDZJZA3J3T exactly but contradict the "all base plates" plural and
silently undercount baseplates in any Core-era fixture where `BASE_LAYER`
is the actual baseplate kind. Risk of missing a real overrun in future
fixtures with no upside.

**Option considered: hold the fix until we probe a Core-era fixture.**
Would give us positive evidence for what `BASE_LAYER` means in its native
habitat. Rejected for now because (a) the Rust comment is direct enough,
(b) it blocks M4 closeout on finding a Core fixture we may not easily
have access to, and (c) the integration canary (see below) will surface
any surprise cheaply.

### When to revisit

Revisit this decision if **any** of these happen:

- A fixture is encountered where `BASE_LAYER` layers exist alongside
  normal course content, and reading them as baseplates produces
  nonsensical results (e.g., a non-baseplate structure at layer_height
  `-0.2`, or a `BASE_LAYER` that isn't positioned as a baseplate corner).
- The GDZJZA3J3T integration canary ("unlimited inventory, expect zero
  violations") starts emitting a "baseplate budget exceeded" violation
  against a reasonable inventory. That would indicate we're counting
  something we shouldn't.
- A new schema version introduces additional LayerKinds and the
  plural-baseplate convention doesn't obviously extend.

If revisiting, look at:

- `traxgen/validator.py` → `_BASEPLATE_LAYER_KINDS` (the set)
- `traxgen/validator.py` → `_check_inventory_budget_tiles` (the use site)
- Tests in `tests/test_validator.py` prefixed `test_budget_tiles_baseplate_`
- This document's "Observed counts" section — add the offending fixture

## Positioning conventions

From the Rust doc-comment on `LayerConstructionData.world_hex_position`:

    /// This is the absolute position of this layer in the world
    /// For baselayers this is the position of the one green cell in
    /// the corner (there is only one)
    /// For the (hexagonal) clear layers it is the cell in the middle

Two conventions:

- **Baselayers** (`BASE_LAYER`, `BASE_LAYER_PIECE`) anchor at their
  corner cell.
- **Clear layers** (`LARGE_LAYER`, `SMALL_LAYER`, presumably
  `LARGE_GHOST_LAYER`) anchor at their center cell.

Matters if/when we ever need to derive a layer's physical extent from
its `world_hex_position` — the anchor offset differs by kind.

## Retainer ID numeric conventions

From probe fb2e547 (retainer-family investigation):

- Layer IDs live roughly in the 100-900 range
- Tile retainer IDs (structural tiles declaring retainers) live roughly
  in the 1000-2000 range
- Balcony retainer IDs also live roughly in the 1000-2000 range

The *scheme* the app uses to pick specific IDs within those ranges is
still unknown — see PLAN.md open unknown #4.

## World-coordinate math

Verified by the baseplate-arrangement probe:

    physical_hex = layer.world_hex_position + cell.local_hex_position

Holds for the cells on `BASE_LAYER_PIECE` layers in GDZJZA3J3T — no two
cells on different baseplates map to the same physical hex under this
formula.

Holds for cross-retainer rail endpoints when both endpoints' retainers
resolve to a layer or tile retainer. Example from GDZJZA3J3T:

- rail #18: cross-retainer STRAIGHT, world-distance = 3 (valid LONG)
- rail #19: cross-retainer STRAIGHT, world-distance = 2 (valid MEDIUM)

Local distance (distance between endpoints' `cell_local_hex_pos` alone)
does **not** reflect physical distance for cross-retainer rails,
because each endpoint's local position is relative to its own
retainer's frame. This is why `INVENTORY_BUDGET_RAILS` originally
skipped cross-retainer rails from its STRAIGHT-length sub-budget — the
local distance could be anything from 0 (same offset, different
retainers) to arbitrarily large and tell us nothing about the physical
rail piece needed.

### Retainer-to-world resolution

For a tile retainer (structural-tile declaring a `retainer_id` on a
layer cell): use the containing layer's `world_hex_position` plus the
cell's `local_hex_position` as the tile retainer's world position.

For a layer retainer: use the layer's `world_hex_position` directly.

For a balcony retainer: **not resolvable by this formula.** Balcony
cells live in their wall's coordinate system, not a layer's. Probing
the balcony case is deferred — see PLAN.md open unknowns.

## Open questions

- **What distinguishes `BASE_LAYER` from `BASE_LAYER_PIECE` in
  practice?** Current hypothesis: era/form-factor (legacy full-plate vs
  modern modular tiles). Confirmable with a Core Starter-Set fixture.
- **What is `LARGE_GHOST_LAYER`?** Never observed. "Ghost" suggests a
  layer used for placement preview or alignment that doesn't correspond
  to a physical piece. Confirmable by parsing a fixture that uses one
  (if we can find one).
- **Baseplate physical shape.** Knowing baseplates tile disjointly
  under the world-coord formula is not the same as knowing which hexes
  a single baseplate covers. Still needed for a real
  `BASEPLATE_COVERAGE` rule. See PLAN.md open unknown #3.
- **Balcony retainer world resolution.** Separate probe-first work
  item before it can be folded into world-coord math.
