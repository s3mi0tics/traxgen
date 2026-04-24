# Path: traxgen/scripts/probe_retainer_references.py
"""Probe retainer_id and layer_id declarer/reference semantics in GDZJZA3J3T.

Claude's working hypothesis:

    Declarers (fields that INTRODUCE a retainer/layer ID):
      - LayerConstructionData.layer_id
      - TileTowerConstructionData.retainer_id (when non-null)
      - WallBalconyConstructionData.retainer_id

    References (fields that POINT TO a declared ID):
      - RailConstructionExitIdentifier.retainer_id
      - PillarConstructionData.lower_layer_id / upper_layer_id
      - WallConstructionData.lower_stacker_tower_{1,2}_retainer_id

If correct:
  - Every reference should be in the declarer set (RAIL_ENDPOINT_MISSING
    and PILLAR_ENDPOINT_MISSING would fire 0 times on valid fixtures).
  - Declarers should be unique among themselves (RETAINER_ID_COLLISION
    would fire 0 times on valid fixtures).

If the probe surprises us — a reference not in the declarer set, or
two declarers sharing an ID — we learn BEFORE writing three bad rules.

Run: `uv run python -m scripts.probe_retainer_references`
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from traxgen.domain import Course
from traxgen.parser import parse_course


def _iter_all_tile_retainer_ids(course: Course) -> list[tuple[int, str]]:
    """Yield (retainer_id, source_description) for every non-null tile retainer_id."""
    from traxgen.domain import TileTowerTreeNodeData

    def walk(node: TileTowerTreeNodeData, source: str) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        cd = node.construction_data
        if cd.retainer_id is not None:
            out.append((cd.retainer_id, f"{source} tile={cd.kind.name}"))
        for child in node.children:
            out.extend(walk(child, source))
        return out

    result: list[tuple[int, str]] = []
    for layer_i, layer in enumerate(course.layer_construction_data):
        for cell in layer.cell_construction_datas:
            src = f"layer#{layer_i} id={layer.layer_id} pos=({cell.local_hex_position.y},{cell.local_hex_position.x})"
            result.extend(walk(cell.tree_node_data, src))
    for wall_i, wall in enumerate(course.wall_construction_data):
        for bal_i, balcony in enumerate(wall.balcony_construction_datas):
            if balcony.cell_construction_data is None:
                continue
            src = f"wall#{wall_i} balcony#{bal_i}"
            result.extend(walk(balcony.cell_construction_data.tree_node_data, src))
    return result


def main() -> None:
    fixture_path = Path("tests/fixtures/GDZJZA3J3T.course")
    course = parse_course(fixture_path.read_bytes())

    # --- Collect declarers -----------------------------------------------
    print("=" * 72)
    print("DECLARERS")
    print("=" * 72)

    layer_ids = [layer.layer_id for layer in course.layer_construction_data]
    print(f"\n1. LayerConstructionData.layer_id ({len(layer_ids)} layers)")
    print(f"   range: {min(layer_ids)}..{max(layer_ids)}")
    print(f"   sample: {sorted(layer_ids)[:10]}{'...' if len(layer_ids) > 10 else ''}")

    tile_retainer_ids_with_source = _iter_all_tile_retainer_ids(course)
    tile_retainer_ids = [rid for rid, _ in tile_retainer_ids_with_source]
    print(f"\n2. TileTowerConstructionData.retainer_id (non-null only): "
          f"{len(tile_retainer_ids)} occurrences")
    if tile_retainer_ids:
        print(f"   range: {min(tile_retainer_ids)}..{max(tile_retainer_ids)}")
        # Show kind distribution — expect pillars, maybe balconies
        kind_counter: Counter[str] = Counter()
        for _, source in tile_retainer_ids_with_source:
            # Extract the tile kind from source string.
            kind = source.split("tile=", 1)[1] if "tile=" in source else "?"
            kind_counter[kind] += 1
        print(f"   kinds declaring retainer_ids: {dict(kind_counter)}")
        print(f"   sample (first 5): {tile_retainer_ids_with_source[:5]}")

    balcony_retainer_ids: list[int] = []
    for wall in course.wall_construction_data:
        for balcony in wall.balcony_construction_datas:
            balcony_retainer_ids.append(balcony.retainer_id)
    print(f"\n3. WallBalconyConstructionData.retainer_id: "
          f"{len(balcony_retainer_ids)} occurrences")
    if balcony_retainer_ids:
        print(f"   range: {min(balcony_retainer_ids)}..{max(balcony_retainer_ids)}")
        print(f"   sample: {sorted(balcony_retainer_ids)[:10]}")

    # --- Collisions among declarers ---------------------------------------
    print("\n" + "=" * 72)
    print("DECLARER UNIQUENESS")
    print("=" * 72)
    all_declarers = (
        [("layer", rid) for rid in layer_ids]
        + [("tile", rid) for rid in tile_retainer_ids]
        + [("balcony", rid) for rid in balcony_retainer_ids]
    )
    all_ids = [rid for _, rid in all_declarers]
    all_counter = Counter(all_ids)
    dupes = {i: n for i, n in all_counter.items() if n > 1}
    if dupes:
        print(f"\n!! Found {len(dupes)} ID(s) declared by multiple sources:")
        for rid, n in sorted(dupes.items()):
            sources = [src for src, r in all_declarers if r == rid]
            print(f"   id={rid}: {n} declarers, sources={sources}")
        print("\nIf this fires, RETAINER_ID_COLLISION rule is viable; if NOT, "
              "the namespace is cross-type-unique and the rule matters.")
    else:
        print("\nAll declarer IDs are unique across layer/tile/balcony spaces.")
        print("=> RETAINER_ID_COLLISION rule is well-founded on this fixture.")

    # Also check within-type uniqueness.
    print("\nPer-type uniqueness:")
    for name, ids in (
        ("layer_ids", layer_ids),
        ("tile retainer_ids", tile_retainer_ids),
        ("balcony retainer_ids", balcony_retainer_ids),
    ):
        c = Counter(ids)
        wtd = {i: n for i, n in c.items() if n > 1}
        status = "UNIQUE" if not wtd else f"DUPLICATES: {wtd}"
        print(f"  {name}: {status}")

    # --- References vs declarer set ---------------------------------------
    print("\n" + "=" * 72)
    print("REFERENCES (checking against declarer set)")
    print("=" * 72)

    declarer_set = set(all_ids)

    # Rail endpoints.
    rail_refs = []
    for rail_i, rail in enumerate(course.rail_construction_data):
        rail_refs.append((rail_i, 1, rail.exit_1_identifier.retainer_id))
        rail_refs.append((rail_i, 2, rail.exit_2_identifier.retainer_id))
    rail_missing = [
        (ri, ei, rid) for (ri, ei, rid) in rail_refs if rid not in declarer_set
    ]
    print(f"\n1. Rail endpoint retainer_ids: {len(rail_refs)} total")
    print(f"   Not in declarer set: {len(rail_missing)}")
    if rail_missing:
        print(f"   Samples: {rail_missing[:5]}")
    else:
        print("   => All rail endpoints point to declared retainers.")

    # Pillar endpoints.
    pillar_refs = []
    for pi, pillar in enumerate(course.pillar_construction_data):
        pillar_refs.append((pi, "lower", pillar.lower_layer_id))
        pillar_refs.append((pi, "upper", pillar.upper_layer_id))
    pillar_missing = [
        (pi, side, lid) for (pi, side, lid) in pillar_refs if lid not in declarer_set
    ]
    print(f"\n2. Pillar layer_ids: {len(pillar_refs)} total")
    print(f"   Not in declarer set: {len(pillar_missing)}")
    if pillar_missing:
        print(f"   Samples: {pillar_missing[:5]}")
    else:
        print("   => All pillar endpoints point to declared layers/retainers.")

    # Wall stacker_tower retainer references.
    wall_refs = []
    for wi, wall in enumerate(course.wall_construction_data):
        wall_refs.append((wi, 1, wall.lower_stacker_tower_1_retainer_id))
        wall_refs.append((wi, 2, wall.lower_stacker_tower_2_retainer_id))
    wall_missing = [
        (wi, twr, rid) for (wi, twr, rid) in wall_refs if rid not in declarer_set
    ]
    print(f"\n3. Wall stacker_tower_{'{1,2}'}_retainer_id: {len(wall_refs)} total")
    print(f"   Not in declarer set: {len(wall_missing)}")
    if wall_missing:
        print(f"   Samples: {wall_missing[:5]}")
    else:
        print("   => All wall tower references point to declared retainers.")

    # --- Summary ---------------------------------------------------------
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print("Declarers:")
    print(f"  {len(layer_ids)} layer_ids + {len(tile_retainer_ids)} tile retainer_ids + "
          f"{len(balcony_retainer_ids)} balcony retainer_ids = {len(all_ids)} total")
    print("References:")
    print(f"  {len(rail_refs)} rail endpoints + {len(pillar_refs)} pillar endpoints + "
          f"{len(wall_refs)} wall tower refs")
    print(f"Missing references: rail={len(rail_missing)}, pillar={len(pillar_missing)}, "
          f"wall={len(wall_missing)}")
    print(f"Declarer collisions: {len(dupes)}")


if __name__ == "__main__":
    main()
