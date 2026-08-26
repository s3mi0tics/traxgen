# scripts/mutation_specs/s28_model_correction.py
"""Mutation spec for the s28 model correction: the goal-plate addressing term.

    uv run python -m scripts.mutation_battery scripts/mutation_specs/s28_model_correction.py

Scoped to the diff. The control reverts the correction itself -- `goal_plate_offset`
ignored, so the model answers from the starter's own plate as it did before
2026-08-26 -- which the cross-plate contrast test and the whole-record sweep both
fail on. If that survives, nothing below means anything.
"""

GRAPH = "traxgen/graph.py"
FOOTPRINT_LOOKUP = (
    "    return _as_key(HexVector(local_pos.y - dy, local_pos.x - dx))"
    " in plate_footprint(kind)"
)
PLATES = "traxgen/plates.py"

CONTROL = {
    "label": "control: the correction reverted (goal plate ignored)",
    "file": GRAPH,
    "old": "        layer_kind, starter_local_pos, goal_plate_offset or (0, 0)",
    "new": "        layer_kind, starter_local_pos, (0, 0)",
}

MUTATIONS = [
    {
        "label": "offset applied with the wrong sign",
        "file": PLATES,
        "old": FOOTPRINT_LOOKUP,
        "new": FOOTPRINT_LOOKUP.replace("- dy", "+ dy").replace("- dx", "+ dx"),
    },
    {
        "label": "offset transposed (y/x)",
        "file": PLATES,
        "old": "    dy, dx = plate_offset",
        "new": "    dx, dy = plate_offset",
    },
    {
        "label": "addressability always true (every cell in-window)",
        "file": PLATES,
        "old": FOOTPRINT_LOOKUP + "\n",
        "new": "    return True\n",
    },
    {
        "label": "None goal offset treated as no plate rather than the home plate",
        "file": GRAPH,
        "old": "        layer_kind, starter_local_pos, goal_plate_offset or (0, 0)",
        "new": "        layer_kind, starter_local_pos, goal_plate_offset or (99, 99)",
    },
    {
        "label": "the port term dropped (plate alone decides)",
        "file": GRAPH,
        "old": """    return plate_available_directions_on(
        layer_kind, starter_local_pos, goal_plate_offset or (0, 0)
    ) & starter_world_ports(starter_rot)""",
        "new": """    return plate_available_directions_on(
        layer_kind, starter_local_pos, goal_plate_offset or (0, 0)
    )""",
    },
    {
        "label": "the plate term dropped (ports alone decide)",
        "file": GRAPH,
        "old": """    return plate_available_directions_on(
        layer_kind, starter_local_pos, goal_plate_offset or (0, 0)
    ) & starter_world_ports(starter_rot)""",
        "new": "    return starter_world_ports(starter_rot)",
    },
    {
        "label": "neighbour direction not applied (the cell itself is tested)",
        "file": PLATES,
        "old": "        if is_addressable_on_plate(kind, goal_plate_offset, local_pos.neighbor(d))",
        "new": "        if is_addressable_on_plate(kind, goal_plate_offset, local_pos)",
    },
]
