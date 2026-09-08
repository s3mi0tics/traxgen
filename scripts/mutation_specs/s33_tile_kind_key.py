# scripts/mutation_specs/s33_tile_kind_key.py
"""Mutation spec for the s33 change: tile-kind terms on `MeasuredRun.lookup_key`.

Run from the repo root:

    uv run python -m scripts.mutation_battery scripts/mutation_specs/s33_tile_kind_key.py

Scoped to the diff, never the repo (workflow.md, Working notes). The control
records the first row as a GOAL_BASIN campaign: the certified course then
misses the record and every test that expects it CONNECTED goes red, which is
the shape s28 chose too -- a row-level mutation the suite runs against, rather
than a key-narrowing one that collapses collection (the s28 spec's docstring
has the story).

Four mutations are declared `expect="survive"`, and their survival is the
finding: `classify_pair` consults the record **twice** -- once as the gate
above the non-adjacency verdict (s25's fix), and again inside
`connection_status` -- so hard-wiring either kind at either site alone is
masked by the other site. That is the redundancy the s25 ordering fix bought,
and it means a single-site regression here is caught only by the other site
staying honest; the spec says so rather than letting four green rows read as
coverage. Hard-wiring a kind at *both* sites is what the suite grades
(`test_a_goal_basin_at_a_wrong_rotation_...` for the goal,
`test_classify_pair_passes_both_kinds_to_the_record` for the starter); it is
not expressible here, because a spec entry is one `old` string that must
match exactly once and the two sites are forty lines apart. The panel that
found the starter half missing ran the both-site mutation by hand: caught
after the pair-level test landed, survived before.
"""

GRAPH = "traxgen/graph.py"

CONTROL = {
    "label": "control: row 1 recorded as a GOAL_BASIN campaign (certified course misses)",
    "file": GRAPH,
    "old": (
        "        goal_plate_offset=None,  # the goal stood on the starter's own layer\n"
        "        goal_kind=TileKind.GOAL_RAIL,\n"
        '        provenance="2026-08-07 36-cell sweep'
    ),
    "new": (
        "        goal_plate_offset=None,  # the goal stood on the starter's own layer\n"
        "        goal_kind=TileKind.GOAL_BASIN,\n"
        '        provenance="2026-08-07 36-cell sweep'
    ),
}

MUTATIONS = [
    {
        "label": "measured_run: goal kind inert in the caller's key",
        "file": GRAPH,
        "old": "        goal_plate_offset,\n        goal_kind,\n    )",
        "new": "        goal_plate_offset,\n        TileKind.GOAL_RAIL,\n    )",
    },
    {
        "label": "measured_run: starter kind inert in the caller's key",
        "file": GRAPH,
        "old": "        starter_rot,\n        starter_kind,\n        plate_offsets,",
        "new": "        starter_rot,\n        TileKind.STARTER,\n        plate_offsets,",
    },
    {
        "label": "lookup_key: goal kind inert in the row's key",
        "file": GRAPH,
        "old": "            self.goal_kind,\n        )",
        "new": "            TileKind.GOAL_RAIL,\n        )",
    },
    {
        "label": "lookup_key: starter kind inert in the row's key",
        "file": GRAPH,
        "old": "            self.starter_kind,\n",
        "new": "            TileKind.STARTER,\n",
    },
    {
        "label": "classify_pair gate: goal kind hard-wired (masked by connection_status's lookup)",
        "file": GRAPH,
        "old": (
            "            goal_plate_offset=goal_offset,\n"
            "            goal_kind=goal.kind,\n"
            "        )\n"
            "        is None"
        ),
        "new": (
            "            goal_plate_offset=goal_offset,\n"
            "            goal_kind=TileKind.GOAL_RAIL,\n"
            "        )\n"
            "        is None"
        ),
        "expect": "survive",
    },
    {
        "label": "classify_pair verdict: goal kind hard-wired (masked by the gate)",
        "file": GRAPH,
        "old": (
            "        goal_plate_offset=goal_offset,\n"
            "        goal_kind=goal.kind,\n"
            "    )\n"
        ),
        "new": (
            "        goal_plate_offset=goal_offset,\n"
            "        goal_kind=TileKind.GOAL_RAIL,\n"
            "    )\n"
        ),
        "expect": "survive",
    },
    {
        "label": (
            "classify_pair gate: starter kind hard-wired "
            "(masked by connection_status's lookup)"
        ),
        "file": GRAPH,
        "old": (
            "            starter_local_pos=starter.local_pos,\n"
            "            starter_kind=starter.kind,\n"
            "            plate_offsets=plate_offsets,\n"
            "            goal_layer_kind=goal.layer_kind,\n"
            "            goal_plate_offset=goal_offset,\n"
            "            goal_kind=goal.kind,\n"
            "        )\n"
            "        is None"
        ),
        "new": (
            "            starter_local_pos=starter.local_pos,\n"
            "            starter_kind=TileKind.STARTER,\n"
            "            plate_offsets=plate_offsets,\n"
            "            goal_layer_kind=goal.layer_kind,\n"
            "            goal_plate_offset=goal_offset,\n"
            "            goal_kind=goal.kind,\n"
            "        )\n"
            "        is None"
        ),
        "expect": "survive",
    },
    {
        "label": "classify_pair verdict: starter kind hard-wired (masked by the gate)",
        "file": GRAPH,
        "old": (
            "        starter_local_pos=starter.local_pos,\n"
            "        starter_kind=starter.kind,\n"
            "        plate_offsets=plate_offsets,\n"
            "        goal_layer_kind=goal.layer_kind,\n"
            "        goal_plate_offset=goal_offset,\n"
            "        goal_kind=goal.kind,\n"
            "    )\n"
        ),
        "new": (
            "        starter_local_pos=starter.local_pos,\n"
            "        starter_kind=TileKind.STARTER,\n"
            "        plate_offsets=plate_offsets,\n"
            "        goal_layer_kind=goal.layer_kind,\n"
            "        goal_plate_offset=goal_offset,\n"
            "        goal_kind=goal.kind,\n"
            "    )\n"
        ),
        "expect": "survive",
    },
    {
        "label": "measured_run: goal_kind given a default",
        "file": GRAPH,
        "old": "    goal_kind: TileKind,\n) -> MeasuredRun | None:",
        "new": "    goal_kind: TileKind = TileKind.GOAL_RAIL,\n) -> MeasuredRun | None:",
    },
    {
        "label": "measured_live_directions: goal_kind given a default",
        "file": GRAPH,
        "old": "    goal_kind: TileKind,\n) -> frozenset[int] | None:",
        "new": "    goal_kind: TileKind = TileKind.GOAL_RAIL,\n) -> frozenset[int] | None:",
    },
    {
        "label": "connection_status: starter_kind given a default",
        "file": GRAPH,
        "old": (
            "    starter_kind: TileKind,\n"
            "    plate_offsets: tuple[tuple[int, int], ...],\n"
            "    goal_layer_kind: LayerKind,\n"
            "    goal_plate_offset: tuple[int, int] | None,\n"
            "    goal_kind: TileKind,\n"
            ") -> ConnectionStatus:"
        ),
        "new": (
            "    starter_kind: TileKind = TileKind.STARTER,\n"
            "    plate_offsets: tuple[tuple[int, int], ...],\n"
            "    goal_layer_kind: LayerKind,\n"
            "    goal_plate_offset: tuple[int, int] | None,\n"
            "    goal_kind: TileKind,\n"
            ") -> ConnectionStatus:"
        ),
    },
]
