# Rail specifications — Core Starter-Set (22410)

Source priority: **physical manual + physical test > Ravensburger website > GraviTrax Fandom wiki**.

The Fandom wiki lists long rails as max 3.5 full-tiles Δheight; the
starter-set manual and physical testing both show 4 full-tiles. The
manual wins.

Heights below are in small-stacker units. Conversions:

- 1 full stacker = 2 small-stacker units
- 1 half stacker = 1 small-stacker unit

## Starter-Set rails (all `RailKind.STRAIGHT`)

| Name   | Count | Max hex distance | Max Δheight (small-stacker units) | Max Δheight (human) |
|--------|-------|------------------|-----------------------------------|---------------------|
| Short  | 9     | 1                | 5                                 | 2 full + 1 half     |
| Medium | 6     | 2                | 7                                 | 3 full + 1 half     |
| Long   | 3     | 3                | 8                                 | 4 full              |

## Notes

- All starter rails share `RailKind.STRAIGHT` (value 0). Rail length is
  inferred from hex distance between endpoints, not stored on the rail
  itself.
- Δheight is the absolute difference between the two endpoints, not a
  signed value — rails work up or down.
- "Max" is the manufacturer-documented maximum. The validator should
  treat exceeding this as an ERROR (piece physically won't connect).

## Non-starter rails (not yet cataloged)

- Bernoulli (left/right): span 1, Δheight 3-4 full
- Short Bernoulli: span 1, Δheight 2.5-3.5 full
- Slow, Fast (spans 4): specs TBD when we expand past starter

Add rows here when those rails enter scope.
