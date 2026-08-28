# Path: scripts/mine_ports.py
"""Prototype rail-port extractor: mine RailConstructionExitIdentifiers from .course files.

Corpus-mining instrument (a) of the port-taxonomy attack on open unknown #7.
Positive evidence only: emits what the corpus shows attaching, never what doesn't.
Prototype status: output format is design material, not locked.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import traxgen.parser as _parser
from traxgen.domain import Course, RailConstructionExitIdentifier, TileTowerTreeNodeData
from traxgen.parser import parse_course
from traxgen.types import CourseElementGeneration


def _tolerant_generation(value: int):
    """Miner-local shim: keep unknown generation ids as raw ints.

    types.py's CourseElementGeneration is behind the app (missing >=10 --
    AUTUMN_2024 onward; upstream 8d7974a has through 13). Read-only mining
    keeps the raw int instead of crashing the course; the enum catch-up is
    plan.md item 5 / deferred-cleanup work, not this script's.
    """
    try:
        return CourseElementGeneration(value)
    except ValueError:
        return value


_parser.CourseElementGeneration = _tolerant_generation


@dataclass(frozen=True, slots=True)
class TowerTile:
    """One tile within a cell's stacking tower, flattened from the tree."""
    kind_name: str
    height_in_small_stacker: int
    hex_rotation: int
    retainer_id: int | None


@dataclass(frozen=True, slots=True)
class ExitContext:
    """One rail end joined (best-effort) to the structure it attaches to."""
    retainer_id: int
    retainer_kind: str          # "layer" | "tile" | "UNMATCHED"
    cell_local: tuple[int, int]
    world_pos: tuple[int, int] | None
    side_hex_rot: int
    exit_local_pos_y: float
    tower: tuple[TowerTile, ...]


def flatten_tower(node: TileTowerTreeNodeData) -> tuple[TowerTile, ...]:
    """Depth-first flatten of a stacking tree into (kind, height, rot, retainer) rows."""
    cd = node.construction_data
    row = TowerTile(
        kind_name=cd.kind.name,
        height_in_small_stacker=cd.height_in_small_stacker,
        hex_rotation=cd.hex_rotation,
        retainer_id=cd.retainer_id,
    )
    out = [row]
    for child in node.children:
        out.extend(flatten_tower(child))
    return tuple(out)


def build_retainer_index(course: MinedCourse) -> tuple[dict, dict]:
    """Index retainer_id -> layer, and retainer_id -> (layer, cell) for tile-carried ids."""
    layer_by_id = {layer.layer_id: layer for layer in course.layers}
    tile_retainers: dict[int, tuple] = {}
    for layer in course.layers:
        for cell in layer.cell_construction_datas:
            for tile in flatten_tower(cell.tree_node_data):
                if tile.retainer_id is not None:
                    tile_retainers[tile.retainer_id] = (layer, cell, tile)
    return layer_by_id, tile_retainers


def join_exit(
    ex: RailConstructionExitIdentifier, layer_by_id: dict, tile_retainers: dict
) -> ExitContext:
    """Join one exit identifier to its retainer's cell and tile tower, best-effort."""
    cell_local = (ex.cell_local_hex_pos.x, ex.cell_local_hex_pos.y)
    if ex.retainer_id in layer_by_id:
        layer = layer_by_id[ex.retainer_id]
        world = (
            layer.world_hex_position.x + ex.cell_local_hex_pos.x,
            layer.world_hex_position.y + ex.cell_local_hex_pos.y,
        )
        tower: tuple[TowerTile, ...] = ()
        for cell in layer.cell_construction_datas:
            if (cell.local_hex_position.x, cell.local_hex_position.y) == cell_local:
                tower = flatten_tower(cell.tree_node_data)
                break
        return ExitContext(
            retainer_id=ex.retainer_id,
            retainer_kind="layer" if tower else "layer(no-cell-match)",
            cell_local=cell_local,
            world_pos=world,
            side_hex_rot=ex.side_hex_rot,
            exit_local_pos_y=ex.exit_local_pos_y,
            tower=tower,
        )
    if ex.retainer_id in tile_retainers:
        layer, cell, tile = tile_retainers[ex.retainer_id]
        return ExitContext(
            retainer_id=ex.retainer_id,
            retainer_kind=f"tile({tile.kind_name})",
            cell_local=cell_local,
            world_pos=None,
            side_hex_rot=ex.side_hex_rot,
            exit_local_pos_y=ex.exit_local_pos_y,
            tower=flatten_tower(cell.tree_node_data),
        )
    return ExitContext(
        retainer_id=ex.retainer_id,
        retainer_kind="UNMATCHED",
        cell_local=cell_local,
        world_pos=None,
        side_hex_rot=ex.side_hex_rot,
        exit_local_pos_y=ex.exit_local_pos_y,
        tower=(),
    )


def describe_exit(ctx: ExitContext) -> str:
    """One-line human rendering of a joined exit."""
    tower = " / ".join(
        f"{t.kind_name}@h{t.height_in_small_stacker},rot{t.hex_rotation}" for t in ctx.tower
    ) or "-"
    world = f"world{ctx.world_pos}" if ctx.world_pos else "world?"
    return (
        f"ret={ctx.retainer_id}({ctx.retainer_kind}) cell{ctx.cell_local} {world} "
        f"side={ctx.side_hex_rot} y={ctx.exit_local_pos_y:g} tower=[{tower}]"
    )


@dataclass(frozen=True, slots=True)
class MinedCourse:
    """The subset of a course the miner needs, version-agnostic."""
    title: str
    version_label: str
    generation_raw: int | None       # v7: the moved-up CourseElementGeneration u32
    layers: tuple
    rails: tuple
    leftover_bytes: int              # v7: unparsed tail (pillars/walls/connectors/sha)


def parse_v7_skytrax(data: bytes) -> MinedCourse:
    """Parse a v7 (SkyTrax) course far enough to mine rails.

    Layout per murmelbahn upstream 8d7974a (lib/src/app/skytrax.rs), which now
    documents v7: metadata, then CourseElementGeneration (the u32 that open
    unknown #13 saw as '13'), then layers with (id, kind, position, INTEGER
    small-stacker height — position/height swapped and re-typed vs v4), then
    rails. Cells/towers/rails are shared with LIGHT_STONES_2023 (power AND
    light-stone fields per tile). Pillars/walls/connectors/sha-tail unparsed —
    not needed for mining. Prototype-local; library v7 is plan.md item 5.
    """
    from traxgen.domain import LayerConstructionData
    from traxgen.parser import Reader, parse_cell, parse_meta_data, parse_rail
    from traxgen.types import CourseSaveDataVersion, LayerKind

    v5 = CourseSaveDataVersion.LIGHT_STONES_2023
    r = Reader(data)
    r.read_u128()
    version_raw = r.read_u32()
    if version_raw != 7:
        raise ValueError(f"not a v7 course: version={version_raw}")
    meta = parse_meta_data(r)
    generation_raw = r.read_u32()
    layer_count = r.read_s32()
    layers = []
    for _ in range(layer_count):
        layer_id = r.read_s32()
        layer_kind = LayerKind(r.read_u32())
        position = r.read_hex_vector()
        small_stacker_height = r.read_s32()
        cell_count = r.read_s32()
        cells = tuple(parse_cell(r, v5) for _ in range(cell_count))
        layers.append(LayerConstructionData(
            layer_id=layer_id,
            layer_kind=layer_kind,
            layer_height=float(small_stacker_height),  # integer on wire in v7
            world_hex_position=position,
            cell_construction_datas=cells,
        ))
    rail_count = r.read_s32()
    rails = tuple(parse_rail(r, v5) for _ in range(rail_count))
    # Tail structure per skytrax.rs: pillar[], wall[], connector[], then a
    # trailing sha256. Read the counts to VERIFY the decomposition rather than
    # asserting it from the byte total; nonzero counts are left unparsed here.
    tail = {}
    for name in ("pillar_count", "wall_count", "connector_count"):
        tail[name] = r.read_s32() if r.remaining >= 4 else None
    tail["post_counts_bytes"] = r.remaining
    return MinedCourse(
        title=meta.title,
        version_label=f"SKYTRAX_v7(gen={generation_raw}, tail={tail})",
        generation_raw=generation_raw,
        layers=tuple(layers),
        rails=rails,
        leftover_bytes=r.remaining,
    )


def to_mined(course: Course) -> MinedCourse:
    """Adapt a natively parsed (v4) Course to the miner's shape."""
    return MinedCourse(
        title=course.meta_data.title,
        version_label=course.header.version.name,
        generation_raw=None,
        layers=course.layer_construction_data,
        rails=course.rail_construction_data,
        leftover_bytes=0,
    )


def mine(path: Path, port_obs: dict, records: list, verbose: bool = True) -> str:
    """Mine one course into port_obs/records. Returns a one-word status for the tally."""
    data = path.read_bytes()
    if int.from_bytes(data[16:20], "little") == 7:
        course = parse_v7_skytrax(data)
    else:
        course = to_mined(parse_course(data))
    code = path.stem
    if not verbose:
        layer_by_id, tile_retainers = build_retainer_index(course)
        for rail_idx, rail in enumerate(course.rails):
            for exit_slot, ex in enumerate((rail.exit_1_identifier, rail.exit_2_identifier), 1):
                ctx = join_exit(ex, layer_by_id, tile_retainers)
                for tile in ctx.tower:
                    port_obs[tile.kind_name].append(
                        (ctx.side_hex_rot, (ctx.side_hex_rot - tile.hex_rotation) % 6,
                         round(ctx.exit_local_pos_y, 3), tile.height_in_small_stacker,
                         rail.rail_kind.name, code))
                    records.append({
                        "tile_kind": tile.kind_name, "side_hex_rot": ctx.side_hex_rot,
                        "tile_hex_rotation": tile.hex_rotation,
                        "exit_local_pos_y": round(ctx.exit_local_pos_y, 4),
                        "tile_height_in_small_stacker": tile.height_in_small_stacker,
                        "rail_kind": rail.rail_kind.name, "retainer_kind": ctx.retainer_kind,
                        "world_pos": list(ctx.world_pos) if ctx.world_pos else None,
                        "course": code, "channel": "corpus",
                        "rail_index": rail_idx, "exit_slot": exit_slot,
                        "tower_size": len(ctx.tower),
                    })
        return "mined" if course.rails else "no_rails"
    extra = f"  UNPARSED_TAIL={course.leftover_bytes}B" if course.leftover_bytes else ""
    print(f"\n=== {code}  title={course.title!r}  "
          f"version={course.version_label}  rails={len(course.rails)}{extra}")
    layer_by_id, tile_retainers = build_retainer_index(course)
    print("    layers: " + ", ".join(
        f"id={lyr.layer_id}:{lyr.layer_kind.name}"
        f"@world({lyr.world_hex_position.x},{lyr.world_hex_position.y})"
        for lyr in course.layers))
    if tile_retainers:
        print("    tile-carried retainer ids: " + ", ".join(
            f"{rid}->{t[2].kind_name}" for rid, t in sorted(tile_retainers.items())))
    if not course.rails:
        for layer in course.layers:
            for cell in layer.cell_construction_datas:
                world = (layer.world_hex_position.x + cell.local_hex_position.x,
                         layer.world_hex_position.y + cell.local_hex_position.y)
                tower = " / ".join(
                    f"{t.kind_name}@h{t.height_in_small_stacker},rot{t.hex_rotation}"
                    for t in flatten_tower(cell.tree_node_data))
                lp = cell.local_hex_position
                print(f"    cell local({lp.x},{lp.y}) world{world}: {tower}")
    for i, rail in enumerate(course.rails):
        e1 = join_exit(rail.exit_1_identifier, layer_by_id, tile_retainers)
        e2 = join_exit(rail.exit_2_identifier, layer_by_id, tile_retainers)
        print(f"  rail[{i}] {rail.rail_kind.name}")
        print(f"    exit1: {describe_exit(e1)}")
        print(f"    exit2: {describe_exit(e2)}")
        for ctx in (e1, e2):
            for tile in ctx.tower:
                rel = (ctx.side_hex_rot - tile.hex_rotation) % 6
                port_obs[tile.kind_name].append(
                    (ctx.side_hex_rot, rel, round(ctx.exit_local_pos_y, 3),
                     tile.height_in_small_stacker, rail.rail_kind.name, code)
                )
                records.append({
                    "tile_kind": tile.kind_name, "side_hex_rot": ctx.side_hex_rot,
                    "tile_hex_rotation": tile.hex_rotation,
                    "exit_local_pos_y": round(ctx.exit_local_pos_y, 4),
                    "tile_height_in_small_stacker": tile.height_in_small_stacker,
                    "rail_kind": rail.rail_kind.name, "retainer_kind": ctx.retainer_kind,
                    "world_pos": list(ctx.world_pos) if ctx.world_pos else None,
                    "course": code, "channel": "corpus",
                })
    return "mined" if course.rails else "no_rails"


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    jsonl_out = next((a.split("=", 1)[1] for a in argv if a.startswith("--jsonl=")), None)
    paths = [Path(p) for p in args] or sorted(Path("tests/fixtures").rglob("*.course"))
    if len(paths) == 1 and paths[0].is_dir():
        paths = sorted(paths[0].glob("*.course"))
    verbose = len(paths) <= 10
    port_obs: dict[str, list] = defaultdict(list)
    records: list[dict] = []
    tally: dict[str, list] = defaultdict(list)
    for path in paths:
        version = int.from_bytes(path.read_bytes()[16:20], "little")
        if version in (1, 2):
            # ZiplineAdded2019 and earlier are a separate schema family
            # (murmelbahn ziplineadded2019.rs); the v4-family reader misparses
            # them into garbage TileKinds. Skip by declared version instead.
            tally[f"skipped(v{version}-layout-unsupported)"].append(path.stem)
            continue
        try:
            tally[mine(path, port_obs, records, verbose=verbose)].append(path.stem)
        except Exception as exc:  # bulk mode: skip-and-record, never invent
            tally[f"skipped({type(exc).__name__})"].append(f"{path.stem}: {exc}")
    print(f"\n=== Tally over {len(paths)} course file(s) ===")
    for status, items in sorted(tally.items()):
        print(f"  {status}: {len(items)}")
        if status.startswith("skipped"):
            cap = 15 if status.startswith("skipped(v") else 500
            for line in items[:cap]:
                print(f"    {line}")
            if len(items) > cap:
                print(f"    ... and {len(items) - cap} more")
    if jsonl_out:
        import json
        with open(jsonl_out, "w") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        print(f"  {len(records)} observation records -> {jsonl_out}")
    print("\n=== Port observations by TileKind (POSITIVE EVIDENCE ONLY) ===")
    print("    (side=raw side_hex_rot; rel=(side - tile.hex_rotation) % 6, the")
    print("     tile-relative-edge HYPOTHESIS; y=exit_local_pos_y; h=tile height)")
    for kind in sorted(port_obs):
        rows = port_obs[kind]
        print(f"  {kind}: {len(rows)} observation(s)")
        for side, rel, y, h, rk, code in rows:
            print(f"    side={side} rel={rel} y={y:g} h={h} rail={rk} [{code}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
