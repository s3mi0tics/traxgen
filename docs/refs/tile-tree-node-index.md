# `TileTowerTreeNodeData.index` semantics

## TL;DR

The `index` field on `TileTowerTreeNodeData` has unclear semantics. It's
an `i32` with no documentation in the murmelbahn Rust source. Empirical
evidence from GDZJZA3J3T suggests it's **NOT cell-local unique** and
**NOT course-wide unique** — it's something murkier, probably related to
per-parent sibling disambiguation. The originally-planned
`TILE_INDEX_COLLISION` validator rule ("unique within a cell") was
dropped from v1 because it would false-positive on real app-produced
courses.

## What the schema says

From `lib/src/app/layer.rs` in lfrancke/murmelbahn:

```rust
#[deku_derive(DekuRead)]
#[derive(Debug, Serialize)]
#[deku(ctx = "version: CourseSaveDataVersion")]
pub struct TileTowerTreeNodeData {
    pub index: i32,

    #[deku(temp)]
    pub children_count: i32,

    #[deku(ctx = "version")]
    pub construction_data: TileTowerConstructionData,

    #[deku(count = "children_count")]
    #[deku(ctx = "version")]
    pub children: Vec<TileTowerTreeNodeData>,
}
```

No comment, no docstring, no cross-references to `index` elsewhere in
the codebase. lfrancke reads and writes the value verbatim without
attaching meaning to it.

## What the fixture shows

Probed via `scripts/probe_tile_index.py` and
`scripts/probe_tile_index_dupes.py` against GDZJZA3J3T (111 cells, 124
tree nodes total):

### Not cell-local unique

28 distinct index values appear in multiple cells. Example roots:

- `index=0`: appears at the root of 6 cells
- `index=6`: appears at the root of 7 cells
- `index=29`: appears at the root of 1 cell

### Root indices look like a per-course sequence (with gaps/reuse)

Single-node cells show the pattern clearly:

- cell #1: single node `SCREW_SMALL` at index=1
- cell #2: single node `SCREW_MEDIUM` at index=2
- cell #3: single node `SCREW_LARGE` at index=3
- cell #4: single node `ZIPLINE_START` at index=4
- cell #5: single node `LIFT_LARGE` at index=14

Looks like a sequence number assigned at some higher level (maybe at
save time, maybe by the level editor's placement counter), but not
strictly unique or dense across the course.

### Children mostly default to index=0

4 cells contain within-cell duplicates — all at index=0, all on non-root
tree nodes. Sample tree from cell #8:

```
[0] index= 6  STACKER_TOWER_OPENED   h=0    <-- root, proper index
  [1] index= 0  STACKER_TOWER_OPENED   h=0    <-- child, sentinel 0
    [2] index= 0  BRIDGE                 h=0    <-- grandchild, sentinel 0
```

Conclusion: **non-root nodes get index=0 as a default**, not a
meaningful identifier. "Within-cell uniqueness" is violated on real
valid app-produced courses.

### Sibling disambiguation — the one exception

Cell #20 has a single non-zero child index:

```
[0] index= 22  STACKER_TOWER_OPENED   h=0
  [1] index=  0  STACKER_TOWER_OPENED   h=0
    [2] index=  0  DOUBLE_BALCONY         h=0
      [3] index=  0  THREEWAY               h=0
      [3] index=  1  THREEWAY               h=0   <-- non-zero child
```

Two THREEWAY siblings under the same DOUBLE_BALCONY parent — one at 0,
one at 1. This is the **only non-root non-zero child index** in the
fixture. Suggests the real semantics might be:

> When a parent has multiple children of the same kind, disambiguate
> them with distinct indices within that sibling set. Otherwise, 0 is
> fine.

But this is one data point. Not a confirmed rule.

## What this means for the validator

The originally-planned `TILE_INDEX_COLLISION` rule ("unique within a
cell") was **dropped from v1** because it would produce false positives
on GDZJZA3J3T. See PLAN.md → "Resolved since original plan."

Possible narrower rules exist but lack evidence:

- **"Unique except 0"** — holds on GDZJZA3J3T but we don't know why.
- **"Unique within sibling sets"** — fits the cell #20 case but is
  exotic and has zero corroborating data.
- **"Non-negative"** — field is `i32`; no negatives seen in fixture;
  speculative.

Until we have a real failure mode or broader fixture evidence, validator
doesn't check this field.

## What to watch for

If a future generator produces courses the app rejects and the
rejection correlates with index values, this field is a suspect. Rerun
the probes against a known-good course the app accepted vs. a
known-bad one the app rejected, diff the index patterns.

If more fixtures become available, rerun `probe_tile_index.py` across
all of them and look for:

- Any within-cell duplicate at a non-zero index (would contradict the
  "0-is-sentinel" hypothesis)
- Sibling disambiguation patterns (would corroborate the cell #20 signal)
- Root index patterns — is it monotonic per layer? Per course?

## References

- `scripts/probe_tile_index.py` — initial per-cell/per-course survey
- `scripts/probe_tile_index_dupes.py` — deep-dive on the 4 duplicate cells
- `lib/src/app/layer.rs` in lfrancke/murmelbahn — schema definition
