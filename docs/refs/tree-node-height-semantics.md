# `height_in_small_stacker` semantics on tree nodes

## TL;DR

`height_in_small_stacker` on any `TileTowerConstructionData` is the number
of small-stacker units *between that node's base and whatever sits directly
beneath it* (the parent node's top, or the cell surface if the node is at
the tree root).

This holds uniformly for all tile kinds — including pillars
(`STACKER_TOWER_CLOSED` / `STACKER_TOWER_OPENED`) and balconies
(`DOUBLE_BALCONY`). There is no special case.

## Why this matters

For the inventory budget validator, total Core stacker usage is simply:

    total_small_units = sum(cd.height_in_small_stacker for every tree node)

Then feasibility: `2 * STACKER_count + STACKER_SMALL_count >= total_small_units`.

Stackers themselves do *not* appear as tree nodes — they're pure height
accounting on whatever sits on top of them. Pillars *do* appear as tree
nodes with their own fixed 14-small-stacker physical height, plus an `h`
field for any stackers beneath them.

## Evidence

Probe of GDZJZA3J3T (`scripts/probe_pillar_context.py`) found:

- Root pillars with `h > 0` exist (e.g., layer 134 has a lone pillar at
  `h=5`). This rules out "pillar_h references a parent's stack" since
  there is no parent.
- Stacked pillars exist (e.g., layer 130: pillar→pillar→bridge). Inner
  pillars carry `h` independent of outer — the inner pillar's `h` means
  stackers between the outer pillar's top and the inner pillar's base.
- Non-pillar children carry `h` meaning stackers between the parent's top
  and the child's base (e.g., layer 129: pillar(h=0) → curve(h=9) means
  9 small-stacker units between pillar top and curve base).

All three cases reduce to the same rule: `h` = stackers between this
node's base and the surface immediately below it.

## Physical height calculation

To compute the physical height (in small-stacker units) of a tile at
depth N in a tree:

    height = sum(node.h for every ancestor including self)
           + sum(PIECE_PHYSICAL_HEIGHT[ancestor.kind] for every strict ancestor)

Where `PIECE_PHYSICAL_HEIGHT` is 14 for pillars, varies for other pieces,
and is 0 for most standard tiles.

This formula isn't needed for the v1 inventory-budget rule, but will be
required for geometric rules in Phase 2+ (e.g., "does this rail's
endpoint elevation match its declared max Δheight").

## Known unknowns

- Does `h` on a pillar *ever* encode something about the pillar itself
  (partial pillar, extender)? No evidence for this in the fixture, and
  no known physical "partial pillar" piece. Leaning "purely stacker-
  accounting" but flagging as unverified.
- Does `PIECE_PHYSICAL_HEIGHT` vary within a pillar kind, or by pillar
  orientation? Not observed in fixture. Assume 14 for both
  `STACKER_TOWER_CLOSED` and `STACKER_TOWER_OPENED` until proven
  otherwise.

## If v1 inventory-budget rule is wrong...

The failure mode of over-summing (counting pillar `h` values that
actually mean something else) is flagging false-positive stacker
overruns — a course that's physically buildable getting marked
invalid. That's loud, so we'll catch it quickly if it happens.

Under-summing (missing genuine stacker usage) would silently pass
physically-infeasible courses — quieter failure. The current rule
doesn't risk this because it sums every `h` value.
