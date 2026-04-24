# Path: traxgen/scripts/probe_baseplate_arrangement.py
"""Probe baseplate world-coordinate arrangement in GDZJZA3J3T.

Resolves (or reveals the shape of) two open questions from PLAN.md:

  #3: Baseplate world-coordinate arrangement — how 4 baseplates tile
      together in world space.
  #8: Cross-retainer rail geometry — whether world-coordinate math
      would let us validate rail spans across retainers.

The fixture has multiple BASE_LAYER layers. Each has:
  - layer_id: int
  - world_hex_position: HexVector (where this layer sits in world space)
  - cell_construction_datas: tuple of cells with local_hex_position

Questions this probe answers:

1. How many baseplates, and where are they positioned in world space?
2. For each baseplate, what's the extent of occupied local_hex_positions?
   (Gives us the "shape" of cell placement on that plate.)
3. Do the world-positioned baseplates tile without overlap?
4. Is there a visible pattern (grid-aligned offsets, hex tiling, etc.)
   that would let us derive the physical-world position of any cell?
5. For cross-retainer rails in the fixture, do the world-offset
   positions of their endpoints plausibly match real rail lengths?

Output: Tables of baseplate positions + occupancy extents + a
rudimentary ASCII map showing where baseplates are positioned relative
to each other.

Run: `uv run python -m scripts.probe_baseplate_arrangement`
"""

from __future__ import annotations

from pathlib import Path

from traxgen.hex import HexVector
from traxgen.parser import parse_course
from traxgen.types import LayerKind


def main() -> None:
    fixture_path = Path("tests/fixtures/GDZJZA3J3T.course")
    course = parse_course(fixture_path.read_bytes())

    # --- Q1: Which layers are baseplates and where are they? -------------
    print("=" * 72)
    print("Q1: BASEPLATE LAYERS")
    print("=" * 72)
    baseplates = [
        layer for layer in course.layer_construction_data
        if layer.layer_kind is LayerKind.BASE_LAYER
    ]
    print(f"\nFound {len(baseplates)} BASE_LAYER layer(s):")
    for layer in baseplates:
        wp = layer.world_hex_position
        ncells = len(layer.cell_construction_datas)
        print(f"  id={layer.layer_id:>4}  world=({wp.y:>3}, {wp.x:>3})  "
              f"height={layer.layer_height:>5.2f}  cells={ncells}")

    # Also show non-baseplate layers for context.
    other_layers = [
        layer for layer in course.layer_construction_data
        if layer.layer_kind is not LayerKind.BASE_LAYER
    ]
    print(f"\nFor context — {len(other_layers)} non-baseplate layer(s):")
    kind_groups: dict[str, list] = {}
    for layer in other_layers:
        kind_groups.setdefault(layer.layer_kind.name, []).append(layer)
    for kind_name, layers in sorted(kind_groups.items()):
        print(f"  {kind_name}: {len(layers)} layers (sample ids: "
              f"{[l.layer_id for l in layers[:5]]}{'...' if len(layers) > 5 else ''})")

    # --- Q2: Occupied local_hex_position extents per baseplate -----------
    print()
    print("=" * 72)
    print("Q2: OCCUPIED LOCAL-HEX EXTENT PER BASEPLATE")
    print("=" * 72)
    print("\nFor each baseplate, the range of local_hex_position values used by")
    print("its cells. Helps reveal the physical 'size/shape' of a single plate.")
    print()

    for layer in baseplates:
        cells = layer.cell_construction_datas
        if not cells:
            print(f"  id={layer.layer_id}: (no cells)")
            continue
        ys = [c.local_hex_position.y for c in cells]
        xs = [c.local_hex_position.x for c in cells]
        print(f"  id={layer.layer_id}  world=({layer.world_hex_position.y}, "
              f"{layer.world_hex_position.x})")
        print(f"    cell count: {len(cells)}")
        print(f"    y range: {min(ys)}..{max(ys)}   x range: {min(xs)}..{max(xs)}")
        # Compute cube-distance extent — more meaningful on hex grid.
        origins = [HexVector(y=c.local_hex_position.y, x=c.local_hex_position.x)
                   for c in cells]
        max_dist_from_origin = max(HexVector(0, 0).distance_to(o) for o in origins)
        print(f"    furthest cell from local (0,0): {max_dist_from_origin} hexes")
        # Sample cell positions (first 6, sorted).
        positions_sorted = sorted((c.local_hex_position.y,
                                     c.local_hex_position.x) for c in cells)[:6]
        print(f"    sample positions: {positions_sorted}")

    # --- Q3: World-position relationships between baseplates -------------
    print()
    print("=" * 72)
    print("Q3: WORLD-POSITION DELTAS BETWEEN BASEPLATES")
    print("=" * 72)
    print("\nPairwise hex distance (and axial delta) between every pair of")
    print("baseplate world_hex_positions. Equal distances suggest regular tiling.")
    print()

    for i, a in enumerate(baseplates):
        for b in baseplates[i + 1:]:
            apos = HexVector(y=a.world_hex_position.y, x=a.world_hex_position.x)
            bpos = HexVector(y=b.world_hex_position.y, x=b.world_hex_position.x)
            dy = bpos.y - apos.y
            dx = bpos.x - apos.x
            dist = apos.distance_to(bpos)
            print(f"  id={a.layer_id} -> id={b.layer_id}: "
                  f"delta=({dy:>3}, {dx:>3})  hex-distance={dist}")

    # --- Q4: Does the local extent fit inside the world-position grid? ---
    print()
    print("=" * 72)
    print("Q4: OVERLAP CHECK (can cells from different baseplates collide")
    print("    in world coordinates?)")
    print("=" * 72)
    print("\nFor each cell, compute its world-space position (world + local) and")
    print("check whether two cells on different baseplates map to the same hex.")
    print()

    world_cells: dict[tuple[int, int], list[tuple[int, tuple[int, int]]]] = {}
    for layer in baseplates:
        for cell in layer.cell_construction_datas:
            wy = layer.world_hex_position.y + cell.local_hex_position.y
            wx = layer.world_hex_position.x + cell.local_hex_position.x
            world_cells.setdefault((wy, wx), []).append(
                (layer.layer_id,
                 (cell.local_hex_position.y, cell.local_hex_position.x))
            )
    overlaps = {
        pos: sources for pos, sources in world_cells.items()
        if len({layer_id for layer_id, _ in sources}) > 1
    }
    if overlaps:
        print(f"!! Found {len(overlaps)} world-hex position(s) claimed by cells ")
        print("   from multiple baseplates. This would mean baseplates overlap,")
        print("   OR the naive `world + local` addition is NOT the right formula.")
        for pos, sources in list(overlaps.items())[:10]:
            print(f"   world=({pos[0]}, {pos[1]}): {sources}")
    else:
        print(f"No overlaps across {len(world_cells)} world-hex positions.")
        print("=> naive addition (world + local) yields disjoint placements.")
        print("   This is consistent with baseplates tiling without overlap.")

    # --- Q5: Cross-retainer rails and world-space distance ---------------
    print()
    print("=" * 72)
    print("Q5: CROSS-RETAINER RAIL GEOMETRY")
    print("=" * 72)
    print("\nFor each STRAIGHT rail whose endpoints live on different retainers,")
    print("compute the world-space distance between its endpoints. A sensible")
    print("distance (1, 2, or 3 hexes) would indicate naive addition works for")
    print("rail span validation.")
    print()

    # Build a map: retainer_id -> (world_hex_position, "layer"/"tile"/"balcony")
    # Only layer-based retainers have world positions directly; tiles/balconies
    # are attached to their containing layer's world position plus local offset.
    retainer_world: dict[int, tuple[int, int, str]] = {}
    for layer in course.layer_construction_data:
        retainer_world[layer.layer_id] = (
            layer.world_hex_position.y, layer.world_hex_position.x,
            f"layer(kind={layer.layer_kind.name})"
        )

    # For tile-declared retainers, approximate their world position as the
    # containing layer's world position + the cell's local position. (We know
    # from the retainer-references probe that all tile retainers are declared
    # by structural tiles sitting on layer cells.)
    for layer in course.layer_construction_data:
        for cell in layer.cell_construction_datas:
            _walk_for_tile_retainers(
                cell.tree_node_data, layer, cell.local_hex_position, retainer_world,
            )

    print(f"Retainer world-positions known for {len(retainer_world)} retainer ID(s).\n")

    cross_retainer_straights = []
    for rail_index, rail in enumerate(course.rail_construction_data):
        e1 = rail.exit_1_identifier
        e2 = rail.exit_2_identifier
        if e1.retainer_id == e2.retainer_id:
            continue
        if rail.rail_kind.name != "STRAIGHT":
            continue
        cross_retainer_straights.append((rail_index, rail))

    print(f"Cross-retainer STRAIGHT rails in fixture: {len(cross_retainer_straights)}\n")
    for rail_index, rail in cross_retainer_straights[:20]:
        e1 = rail.exit_1_identifier
        e2 = rail.exit_2_identifier

        # World position of each endpoint = retainer's world pos + cell_local_hex_pos.
        r1 = retainer_world.get(e1.retainer_id)
        r2 = retainer_world.get(e2.retainer_id)
        if r1 is None or r2 is None:
            print(f"  rail #{rail_index:>3}: retainer_ids={e1.retainer_id}, "
                  f"{e2.retainer_id}  — unresolved retainer world position(s)")
            continue

        w1y = r1[0] + e1.cell_local_hex_pos.y
        w1x = r1[1] + e1.cell_local_hex_pos.x
        w2y = r2[0] + e2.cell_local_hex_pos.y
        w2x = r2[1] + e2.cell_local_hex_pos.x

        local_dist = HexVector(e1.cell_local_hex_pos.y, e1.cell_local_hex_pos.x) \
            .distance_to(HexVector(e2.cell_local_hex_pos.y, e2.cell_local_hex_pos.x))
        world_dist = HexVector(w1y, w1x).distance_to(HexVector(w2y, w2x))

        marker = " <-- valid (1,2,3)" if world_dist in (1, 2, 3) else " <-- NOT in (1,2,3)"
        print(f"  rail #{rail_index:>3}: retainer_ids={e1.retainer_id}->"
              f"{e2.retainer_id}")
        print(f"      local  positions: ({e1.cell_local_hex_pos.y},"
              f"{e1.cell_local_hex_pos.x}) -> ({e2.cell_local_hex_pos.y},"
              f"{e2.cell_local_hex_pos.x})  local-distance={local_dist}")
        print(f"      world positions:  ({w1y},{w1x}) -> ({w2y},{w2x})  "
              f"world-distance={world_dist}{marker}")

    # --- Rough ASCII map of baseplate world positions --------------------
    print()
    print("=" * 72)
    print("ROUGH ASCII MAP OF BASEPLATE WORLD POSITIONS")
    print("=" * 72)
    print("\n(Columns = world_hex_position.x; rows = world_hex_position.y)")
    print()
    if baseplates:
        ys = [layer.world_hex_position.y for layer in baseplates]
        xs = [layer.world_hex_position.x for layer in baseplates]
        miny, maxy = min(ys), max(ys)
        minx, maxx = min(xs), max(xs)
        positions: dict[tuple[int, int], int] = {}
        for layer in baseplates:
            positions[(layer.world_hex_position.y, layer.world_hex_position.x)] = \
                layer.layer_id
        print(f"    {'':>5} ", end="")
        for x in range(minx, maxx + 1):
            print(f"{x:>6}", end="")
        print()
        for y in range(miny, maxy + 1):
            print(f"    y={y:>3} ", end="")
            for x in range(minx, maxx + 1):
                if (y, x) in positions:
                    print(f"  {positions[(y, x)]:>3} ", end=" ")
                else:
                    print("     .", end="")
            print()


def _walk_for_tile_retainers(node, layer, local_pos, out):
    """Record world position of every tile-retainer declared in this tree."""
    cd = node.construction_data
    if cd.retainer_id is not None:
        # Approximation: tile retainer's world position = layer world + cell local.
        # Doesn't account for stacking or balcony placement beneath the retainer,
        # but good enough for this probe.
        out[cd.retainer_id] = (
            layer.world_hex_position.y + local_pos.y,
            layer.world_hex_position.x + local_pos.x,
            f"tile(kind={cd.kind.name})",
        )
    for child in node.children:
        _walk_for_tile_retainers(child, layer, local_pos, out)


if __name__ == "__main__":
    main()
