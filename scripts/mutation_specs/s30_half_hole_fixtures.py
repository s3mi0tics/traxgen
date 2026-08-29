# scripts/mutation_specs/s30_half_hole_fixtures.py
"""Mutation spec for the s30 half-hole fixture promotion.

    uv run python -m scripts.mutation_battery scripts/mutation_specs/s30_half_hole_fixtures.py

Two runs, not thirteen: this promotion added no production code, so the only
question worth asking is whether the new tests *bite*. A fixture test that
passes because it never really rebuilt anything is the failure mode #24 exists
to prevent, one layer in.

The control perturbs the goal rotation inside the probe's own builder. Every
rebuilt arm then serializes to different bytes, so the `payload_sha256` check
must fail -- if it does not, the sidecars are decorative and the courses these
tests reason about are not the courses that rendered.

The single mutation drops `classify`'s negative-control requirement, which is
what makes the nine-arm run replay as ORACLE_SUSPECT. Its survival would mean
the frozen quotation recording *why* the ten-arm re-run exists is unenforced.
"""

PROBE = "scripts/probe_half_hole.py"

CONTROL = {
    "label": "control: the builder no longer rebuilds the course that rendered",
    "file": PROBE,
    "old": "        TileKind.GOAL_RAIL, 0, HexVector(*arm.goal_local), arm.goal_rot",
    "new": "        TileKind.GOAL_RAIL, 0, HexVector(*arm.goal_local), (arm.goal_rot + 1) % 6",
}

MUTATIONS = [
    {
        "label": "classify stops requiring a negative control before scoring",
        "file": PROBE,
        "old": '    if validity("negative_control") != "inactive":',
        "new": '    if False:',
    },
]
