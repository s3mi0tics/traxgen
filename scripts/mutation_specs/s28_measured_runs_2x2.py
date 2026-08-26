# scripts/mutation_specs/s28_measured_runs_2x2.py
"""Mutation spec for the s28 change: the #17 2x2 recorded into `MEASURED_RUNS`.

Run from the repo root:

    uv run python -m scripts.mutation_battery scripts/mutation_specs/s28_measured_runs_2x2.py

Scoped to the diff, never the repo (workflow.md, Working notes). The control
recreates the collision that was watched go red in s28 -- the arm-1 row's
`goal_plate_offset` set to `None` makes the two 2x2 rows share a key, which is
what `test_every_measured_run_has_a_distinct_lookup_key` failed on before the
key was unified, and the sidecar test fails beside it. A first draft used
"drop a term from `lookup_key`" as the control and the battery's first run
showed why that is wrong: a 5-tuple never equals the 6-tuple key, every lookup
misses, a module-level `derive_geometry()` raises at import, and pytest runs
zero tests -- red, and proof of nothing. The battery now refuses such a
control. Key-narrowing mutations here slice the key instead, so the suite runs.
One mutation is declared `expect="survive"`: the corner-table `plate_offsets`
clause, whose deadness after the 2x2 is the claim the comment beside it makes.
"""

GRAPH = "traxgen/graph.py"

CONTROL = {
    "label": "control: arm-1 row's goal offset set to None (rows collide)",
    "file": GRAPH,
    "old": "goal_plate_offset=(5, 0),  # the goal stood on the completing plate",
    "new": "goal_plate_offset=None,  # the goal stood on the completing plate",
}

ARM_ONE_ROW = """    MeasuredRun(
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=(0, 1),
        starter_rot=0,
        live_directions=frozenset({0, 4}),  # E, SW -- both across the boundary
        directions_probed=frozenset({0, 4}),
        goal_rotations_swept=False,
        plate_offsets=STARTER_PLATE_PLUS_COMPLETER,
        goal_layer_kind=LayerKind.BASE_LAYER_PIECE,
        goal_plate_offset=(5, 0),  # the goal stood on the completing plate
        provenance=(
            "2026-08-25 #17 2x2, completer-plate arms -- the goal addressed "
            "in-window on the plate that owns the cell, (-5,2) rot 1 for E and "
            "(-4,0) rot 5 for SW, rendered active both times (UY36K96VLM, "
            "E3FMVREOBV): connection composes across a plate boundary. "
            "`predict_connection` called both dark and was refuted by "
            "prediction, as the probe's docstring declared it would be. 7/7, "
            "both certified controls active (KN6F459ZR3), no retries, no "
            "refused screens; ADDRESSING_MATTERS"
        ),
    ),
"""

MUTATIONS = [
    {
        "label": "arm-1 row: SW recorded dark",
        "file": GRAPH,
        "old": "live_directions=frozenset({0, 4}),  # E, SW -- both across the boundary",
        "new": "live_directions=frozenset({0}),  # E, SW -- both across the boundary",
    },
    {
        "label": "arm-1 row: goal offset transposed",
        "file": GRAPH,
        "old": "goal_plate_offset=(5, 0),  # the goal stood on the completing plate",
        "new": "goal_plate_offset=(0, 5),  # the goal stood on the completing plate",
    },
    {
        "label": "arm-1 row deleted outright",
        "file": GRAPH,
        "old": ARM_ONE_ROW,
        "new": "",
    },
    {
        "label": "arm-2 row: E recorded active",
        "file": GRAPH,
        "old": "live_directions=frozenset({2}),  # NW: the local control",
        "new": "live_directions=frozenset({0, 2}),  # NW: the local control",
    },
    {
        "label": "arm-2 row: E and SW dropped from probed",
        "file": GRAPH,
        "old": "directions_probed=frozenset({0, 2, 4}),  # E, NW, SW",
        "new": "directions_probed=frozenset({2}),  # E, NW, SW",
    },
    {
        "label": "arm-2 row: goal rotations claimed swept",
        "file": GRAPH,
        "old": (
            "directions_probed=frozenset({0, 2, 4}),  # E, NW, SW\n"
            "        goal_rotations_swept=False,"
        ),
        "new": (
            "directions_probed=frozenset({0, 2, 4}),  # E, NW, SW\n"
            "        goal_rotations_swept=True,"
        ),
    },
    {
        "label": "arm-1 row: goal rotations claimed swept",
        "file": GRAPH,
        "old": (
            "directions_probed=frozenset({0, 4}),\n        goal_rotations_swept=False,"
        ),
        "new": ("directions_probed=frozenset({0, 4}),\n        goal_rotations_swept=True,"),
    },
    {
        "label": "two-plate layout constant transposed",
        "file": GRAPH,
        "old": "STARTER_PLATE_PLUS_COMPLETER: tuple[tuple[int, int], ...] = ((0, 0), (5, 0))",
        "new": "STARTER_PLATE_PLUS_COMPLETER: tuple[tuple[int, int], ...] = ((0, 0), (0, 5))",
    },
    {
        "label": "rebase transposed (y/x) in plate_offsets_from",
        "file": GRAPH,
        "old": "return tuple(sorted((y - origin.y, x - origin.x) for y, x in plate_positions))",
        "new": "return tuple(sorted((x - origin.x, y - origin.y) for y, x in plate_positions))",
    },
    {
        "label": "lookup ignores both goal terms",
        "file": GRAPH,
        "old": "        if run.lookup_key == key:",
        "new": "        if run.lookup_key[:4] == key[:4]:",
    },
    {
        "label": "lookup ignores the plate layout",
        "file": GRAPH,
        "old": "        if run.lookup_key == key:",
        "new": "        if run.lookup_key[:3] + run.lookup_key[4:] == key[:3] + key[4:]:",
    },
    {
        "label": "corner-table plate_offsets clause deleted (claimed dead)",
        "file": GRAPH,
        "old": (
            "        and run.plate_offsets == STARTER_PLATE_ONLY\n"
            "        and run.goal_rotations_swept\n"
        ),
        "new": "        and run.goal_rotations_swept\n",
        "expect": "survive",
    },
]
