# Path: traxgen/scripts/probe_plate_membership.py
"""Separate the tile-port constraint from the baseplate-membership one (open unknown #15).

Every sweep through 2026-08-10 held the STARTER at local (0,0) on a single
BASE_LAYER_PIECE layer and moved only the goal. That produced the measured
live-direction table -- even starter rotations give {E, NW}, odd give {NE} --
whose *pattern* is parity but whose *mechanism* has stayed open, specifically
the part no symmetric model could explain: why the even set has two members and
the odd set one, and why the set does not rotate with the starter.

Corpus mining on 2026-08-21 supplied the missing term. Across 640 parsed
courses and 28,494 BASE_LAYER_PIECE cell placements, the plate's cells occupy
exactly 30 distinct local positions, and local (0,0) sits on two boundaries of
that footprint: its W, SW and SE neighbours are used **zero** times. Composed
with the STARTER's corpus-measured intrinsic ports (even-only tile-relative
edges {0,2,4}, n=380 unambiguous observations), that reproduces the whole table
with no free parameters:

    live(s) = plate_available(starter_pos) INTERSECT starter_world_ports(s)

    plate_available((0,0)) = {E, NE, NW}                    [corpus, n=28,494]
    starter_world_ports(s) = {(r + s) % 6 for r in {0,2,4}} [corpus, n=380]
                           = evens when s is even, odds when s is odd

    s even: {0,1,2} & {0,2,4} = {0,2} = {E, NW}   -- matches the measured row
    s odd:  {0,1,2} & {1,3,5} = {1}   = {NE}      -- matches the measured row

Reproducing the record is not evidence (observation #20, and the 2026-08-08
lock "a model fitted to the record is tested by prediction, not by fit"). This
probe is the prediction. It moves the STARTER off the corner and renders three
named rivals against each other:

    port_only  -- the STARTER's ports are the only constraint; position is
                  irrelevant. Predicts three live directions in every row.
    plate      -- ports AND the goal cell being on the plate. The candidate.
    table      -- what graph.py claimed until s22 (2026-08-21): the measured
                  table, keyed on starter rotation alone, so position-blind. Not
                  a straw man when these runs executed -- shipped code asserted
                  it for a starter anywhere on the plate. s22 fixed graph.py;
                  the rival is kept frozen as the refuted historical claim.

A model that ignores one of the four coordinates is asserting that it does not
matter, which is exactly what a render can falsify. `classify()` scores every
rival by the same arithmetic -- cells called wrong -- so nothing privileges the
model the probe was built to support.

**2026-08-21, starter (0,1) ("edge"), rotation 0, eight renders, both harness
brackets active.** E and SW -- off-plate, port-allowed -- both rendered
inactive; on-plate NW rendered active; the three parity-dead cells stayed dark.
Verdict MODEL_SURVIVES:plate. `port_only` died on both off-plate cells, and
`table` died on E, which graph.py at the time called live at rotation 0
regardless of where the starter sat. When these runs executed that was a live
bug, not a hypothetical: `connection_status()` was missing a coordinate, so
`START_GOAL_CONNECTED` could throw ERROR at a valid course whose starter was
not on the corner. s22 fixed it -- `connection_status` now requires the
starter's layer kind and local position, and answers UNMEASURED off the record.

What that run did NOT test is the model's positive half. Both its discriminating
cells were off-plate, so it established "off-plate kills" and left "on-plate plus
port parity suffices" resting on a single cell. The interior run is the test
that bites: at (-3,2) all six neighbours are on-plate, `plate` and `port_only`
agree by construction, and the surviving rival is `table` -- on SW alone, which
`plate` says lights up after being dark in six exhaustive sweeps.

Per observation #21 (ask what a null result would prove *before* running): a run
where everything comes back inactive is NOT evidence for any model, because "the
starter cannot sit at this cell at all" predicts the same thing. That is why
every run carries at least one **local control** -- a cell every rival calls
active -- and why a dark one is a pre-declared hard abort that reports
SETUP_SUSPECT rather than a verdict.

Goal rotations are not swept. `g = (d + 1) % 6` is the single most-confirmed
result in the project (six exhaustive 36-cell sweeps, zero violations), so each
direction is rendered only at its connecting rotation. That assumption is stated
here so that it is visible and falsifiable rather than buried: if a cell that
both models call inactive turns out to be live at some other rotation, this
probe would miss it -- and `classify()` reports ALL_REFUTED when a cell every
rival called dark renders active, precisely because that breaks more than this
probe.

What this probe does NOT settle: whether "off-plate" means physically off the
board or merely outside the layer's canonical coordinate window. The operational
consequence is identical either way, and courses can add plates (Colby,
2026-08-21) -- which makes plate membership a property of the course's declared
layer set, not of a position. That is open unknown #16 and sequenced item 5; a
follow-on probe that adds a second plate and re-renders a dead direction is the
test that separates those readings.

Run:
    uv run python -m scripts.probe_plate_membership --starter interior --dry-run
    uv run python -m scripts.probe_plate_membership --starter interior

`--starter` takes `edge` (0,1), `interior` (-3,2), or an explicit `y,x`;
`corner` is refused, because at (0,0) rotation 0 the NW cell *is* the certified
control and identical bytes would dedup to one share code. `--starter-rot`
selects the rotation, and its parity is what moves the port set.

Path: traxgen/scripts/probe_plate_membership.py
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from scripts.run_sweep_queue import SETTLE_SECONDS
from scripts.sweep_starter_rotation import build_variant
from traxgen.android import (
    AndroidAutomationError,
    assert_emulator_ready,
    render_course,
    reset_to_main_menu,
    resolve_context,
)
from traxgen.domain import Course
from traxgen.generator import generate_minimal
from traxgen.graph import (
    STARTER_INTRINSIC_PORTS as GRAPH_STARTER_PORTS,
)
from traxgen.graph import (
    goal_rotation_for,
)
from traxgen.graph import (
    starter_world_ports as graph_starter_world_ports,
)
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.plates import is_on_plate, plate_footprint
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind
from traxgen.uploader import UploadError, upload_course
from traxgen.validator import validate_strict

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "screenshots" / "plate_membership_probe"

DIRECTION_NAMES = ("E", "NE", "NW", "W", "SW", "SE")

# The BASE_LAYER_PIECE cell footprint now lives in `traxgen.plates`, generated
# from the corpus by `scripts/probe_plate_footprint.py`. It moved out of this
# script on 2026-08-21 (s22) when `graph.py` became plate-aware and needed the
# same constant: two copies of a measured set is one copy too many, and the
# library is where a fact the library reasons about belongs.
PLATE_FOOTPRINT: frozenset[tuple[int, int]] = plate_footprint(LayerKind.BASE_LAYER_PIECE)

# The STARTER's intrinsic ports (even tile-relative edges {0, 2, 4}, corpus
# mining 2026-08-18, n=380 unambiguous) also moved into the library on
# 2026-08-21 (s22): `graph.py` composes them with the plate term, so that is
# where the term is defined. Re-exported here under the name this probe's
# design documentation uses.
STARTER_INTRINSIC_PORTS: frozenset[int] = GRAPH_STARTER_PORTS

# Three named starter cells, by their relationship to the plate's boundary.
#
#   CORNER   -- (0,0), where every sweep through 2026-08-10 pinned the starter.
#               Three neighbours off-plate: W, SW, SE.
#   EDGE     -- (0,1), the 2026-08-21 run. Off-plate neighbours E, SW, SE, two
#               of which are port-allowed at even rotations, so the port and
#               plate models disagree there.
#   INTERIOR -- (-3,2), all six neighbours on-plate (corpus counts 1000/1045/
#               1036/1036/946/1015). There the port and plate models agree by
#               construction, and the rival that separates is `table` -- the
#               position-blind claim graph.py made until s22, which predicts
#               {E, NW} at even rotations here.
CORNER_STARTER_POS = HexVector(y=0, x=0)
EDGE_STARTER_POS = HexVector(y=0, x=1)
INTERIOR_STARTER_POS = HexVector(y=-3, x=2)

# The app-certified geometry (share code FLW4TMLP5V), starter at its original
# (0,0). Rendered first and again last, per the 2026-08-07 lock: an opening
# control proves the harness worked at render 1 and says nothing about render 9.
CERTIFIED_STARTER_POS = HexVector(y=0, x=0)
CERTIFIED_GOAL_POS = HexVector(y=-1, x=0)
CERTIFIED_GOAL_ROT = 3
CERTIFIED_STARTER_ROT = 0


def on_plate(pos: HexVector) -> bool:
    """Whether `pos` is a cell the corpus has ever shown occupied on a baseplate.

    Binds `is_on_plate` to BASE_LAYER_PIECE, which is the only layer kind this
    probe's geometries use.
    """
    return is_on_plate(LayerKind.BASE_LAYER_PIECE, pos)


def starter_world_ports(starter_rot: int) -> frozenset[int]:
    """The STARTER's port edges in world frame at `starter_rot`.

    Delegates to `graph.starter_world_ports`, which is the same function this
    probe used to own. Kept as a name here because the module docstring's
    derivation refers to it.
    """
    return graph_starter_world_ports(starter_rot)


def port_model_says_active(
    starter_pos: HexVector, starter_rot: int, direction: int, goal_rot: int
) -> bool:
    """Rival: the STARTER's ports are the only constraint; the plate is irrelevant.

    Takes `starter_pos` for a uniform model signature and ignores it -- that
    indifference is the claim being tested.
    """
    del starter_pos
    return direction in starter_world_ports(starter_rot) and goal_rot == goal_rotation_for(
        direction
    )


def plate_model_says_active(
    starter_pos: HexVector, starter_rot: int, direction: int, goal_rot: int
) -> bool:
    """Candidate: ports AND the goal cell being on the plate."""
    if not port_model_says_active(starter_pos, starter_rot, direction, goal_rot):
        return False
    return on_plate(starter_pos.neighbor(direction))


# The claim graph.py shipped between 2026-08-10 and 2026-08-21, quoted as a
# literal. Deliberately NOT derived from graph.py's measured record: a
# historical claim is a quotation, and a quotation must not change when the
# library corrects itself -- or when a future session re-measures the corner.
# Transcription is guarded by a literal-vs-literal test, not by the record.
TABLE_CLAIM_2026_08_10: Mapping[int, frozenset[int]] = MappingProxyType(
    {
        0: frozenset({0, 2}),  # E, NW
        1: frozenset({1}),  # NE
        2: frozenset({0, 2}),  # E, NW
        3: frozenset({1}),  # NE
        4: frozenset({0, 2}),  # E, NW
        5: frozenset({1}),  # NE
    }
)


def table_model_says_active(
    starter_pos: HexVector, starter_rot: int, direction: int, goal_rot: int
) -> bool:
    """Rival: the corner table applied everywhere -- what `graph.py` claimed until s22.

    This was not a straw man. Between 2026-08-10 and 2026-08-21 `connection_status()`
    was keyed on starter rotation alone, so shipped code asserted these verdicts
    for a starter anywhere on the plate. The runs below refuted it, and s22 fixed
    it -- so this function now states the refuted claim as its own frozen literal
    (`TABLE_CLAIM_2026_08_10`), with no call into `graph.py`'s live-direction
    record.

    Why not repoint it at the corrected code instead: corrected `graph.py`
    carries these very renders in `MEASURED_RUNS`, so a rival that asks it is
    graded against the answer key its own answers came from -- it cannot lose,
    and the replay stops measuring anything (observation #12's same-origin
    shape; verified by enacting the repoint in a scratch copy, s22 panel
    review). The failure is loud at first -- 13 fixtures go red because the
    "loser" stops losing -- and becomes silent only after the natural-looking
    edit that updates them; freezing the quotation removes that trap. It also
    keeps the probe runnable: the corrected code answers UNMEASURED at any
    fresh position, which maps to all-inactive and leaves `build_cells` unable
    to nominate a local control.

    It ignores `starter_pos` for the same reason the port model does: because
    that is the claim.
    """
    del starter_pos
    return direction in TABLE_CLAIM_2026_08_10.get(
        starter_rot, frozenset()
    ) and goal_rot == goal_rotation_for(direction)


# The rivals this probe renders against, in the order they are reported. Each
# takes the same four coordinates so a cell can ask all of them uniformly; a
# model that ignores one of those coordinates is *asserting* that it does not
# matter, which is precisely what a render can falsify.
MODELS: Mapping[str, Callable[[HexVector, int, int, int], bool]] = MappingProxyType(
    {
        "port_only": port_model_says_active,
        "plate": plate_model_says_active,
        "table": table_model_says_active,
    }
)


@dataclass
class ProbeCell:
    """One rendered geometry, with both models' predictions declared before the run."""

    kind: str  # 'probe' | 'control_certified'
    direction: int | None  # HEX_DIRECTIONS index; None for the certified control
    starter_y: int
    starter_x: int
    y: int
    x: int
    rot: int
    starter_rot: int
    goal_on_plate: bool
    role: str  # 'discriminator' | 'local_control' | 'shared_negative' | 'certified_control'
    predictions: dict[str, str] = field(default_factory=dict)  # model name -> active/inactive
    payload_sha256: str | None = None
    payload_bytes: int | None = None
    validator: str | None = None
    code: str | None = None
    upload_error: str | None = None
    validity: str | None = None  # 'active' | 'inactive'
    render_error: str | None = None
    screenshot: str | None = None

    @property
    def label(self) -> str:
        """Short filesystem-safe identifier: no parens, commas, or spaces."""
        return (
            f"start_y{self.starter_y}x{self.starter_x}_s{self.starter_rot}"
            f"_goal_y{self.y}x{self.x}_rot{self.rot}"
        )

    @property
    def models_disagree(self) -> bool:
        """Whether the rivals call this cell differently -- the cell's reason to exist."""
        return len(set(self.predictions.values())) > 1

    def separates(self) -> set[tuple[str, str]]:
        """Which pairs of models this cell tells apart."""
        names = sorted(self.predictions)
        return {
            (a, b)
            for i, a in enumerate(names)
            for b in names[i + 1 :]
            if self.predictions[a] != self.predictions[b]
        }


def _predict_all(
    starter_pos: HexVector, starter_rot: int, direction: int, goal_rot: int
) -> dict[str, str]:
    """Every rival's verdict for one geometry, computed rather than typed in."""
    return {
        name: "active" if fn(starter_pos, starter_rot, direction, goal_rot) else "inactive"
        for name, fn in MODELS.items()
    }


def build_cells(
    starter_pos: HexVector = EDGE_STARTER_POS, starter_rot: int = 0
) -> list[ProbeCell]:
    """The certified control plus one cell per direction, predictions pre-declared.

    Every rival's verdict comes from its own function rather than being typed
    in, and the design preconditions below are stated in terms of what the run
    can *learn* rather than in terms of a hardcoded cell count -- so this
    generalizes to any starter position while still refusing to spend renders
    on a run that cannot discriminate (the 2026-08-08 lock; observation #19).
    """
    cells: list[ProbeCell] = [
        ProbeCell(
            kind="control_certified",
            direction=None,
            starter_y=CERTIFIED_STARTER_POS.y,
            starter_x=CERTIFIED_STARTER_POS.x,
            y=CERTIFIED_GOAL_POS.y,
            x=CERTIFIED_GOAL_POS.x,
            rot=CERTIFIED_GOAL_ROT,
            starter_rot=CERTIFIED_STARTER_ROT,
            goal_on_plate=on_plate(CERTIFIED_GOAL_POS),
            role="certified_control",
            predictions=dict.fromkeys(MODELS, "active"),
        )
    ]
    for direction in range(6):
        goal_pos = starter_pos.neighbor(direction)
        goal_rot = goal_rotation_for(direction)
        predictions = _predict_all(starter_pos, starter_rot, direction, goal_rot)
        verdicts = set(predictions.values())
        if len(verdicts) > 1:
            role = "discriminator"
        elif verdicts == {"active"}:
            role = "local_control"
        else:
            role = "shared_negative"
        cells.append(
            ProbeCell(
                kind="probe",
                direction=direction,
                starter_y=starter_pos.y,
                starter_x=starter_pos.x,
                y=goal_pos.y,
                x=goal_pos.x,
                rot=goal_rot,
                starter_rot=starter_rot,
                goal_on_plate=on_plate(goal_pos),
                role=role,
                predictions=predictions,
            )
        )

    if not on_plate(starter_pos):
        raise RuntimeError(
            f"design precondition failed: the starter cell {starter_pos} is itself "
            "off-plate. Every render would measure that, and nothing else."
        )
    probe_cells = [c for c in cells if c.kind == "probe"]
    certified = cells[0]
    collisions = [
        c
        for c in probe_cells
        if (c.starter_y, c.starter_x, c.starter_rot, c.y, c.x, c.rot)
        == (
            certified.starter_y,
            certified.starter_x,
            certified.starter_rot,
            certified.y,
            certified.x,
            certified.rot,
        )
    ]
    if collisions:
        raise RuntimeError(
            f"design precondition failed: probe cell {collisions[0].label} is the "
            "certified control's own geometry. Identical bytes dedup to one share "
            "code, so the run would render a single course while believing it "
            "rendered two. This is what starter 'corner' does -- and the corner is "
            "the position six exhaustive sweeps already measured, so probe a "
            "starter cell that moves."
        )
    if not any(c.role == "discriminator" for c in probe_cells):
        raise RuntimeError(
            f"design precondition failed: no cell at starter {starter_pos} rot "
            f"{starter_rot} separates any two rivals, so the run would render six "
            "courses and learn nothing. Pick a starter position where the models "
            "disagree."
        )
    if not any(c.role == "local_control" for c in probe_cells):
        raise RuntimeError(
            f"design precondition failed: no cell at starter {starter_pos} rot "
            f"{starter_rot} is called active by every rival. Without one, an "
            "all-inactive run cannot be told from a broken setup (observation #21)."
        )
    return cells


def _render_order(cells: list[ProbeCell]) -> list[ProbeCell]:
    """Certified control, then the local control, then discriminators, then the rest.

    The local control comes before the discriminators on purpose: if the starter
    cannot sit at the probe position at all, that is the cheapest render at which
    to find out, and it invalidates the discriminators rather than being
    invalidated by them.
    """
    order = {"certified_control": 0, "local_control": 1, "discriminator": 2}
    return sorted(cells, key=lambda c: (order.get(c.role, 3), c.direction or 0))


def classify(cells: list[ProbeCell], final_control_validity: str | None) -> tuple[str, str]:
    """Pre-declared verdict for the whole probe: (verdict, explanation).

    Conditions are ordered by what they implicate: the harness first, then the
    setup, then the shared parity term, and only then the two models. Nothing
    below the harness checks is trusted if a harness check fails.
    """
    certified = next((c for c in cells if c.role == "certified_control"), None)
    local_controls = [c for c in cells if c.role == "local_control"]

    if certified is None or certified.validity is None:
        return "INCOMPLETE", "the certified control never rendered; nothing here is measured."
    if certified.validity != "active":
        return (
            "HARNESS_SUSPECT",
            f"the app-certified control rendered {certified.validity!r}. The oracle is "
            "not measuring what it should; no other cell in this run means anything.",
        )
    if final_control_validity is not None and final_control_validity != "active":
        return (
            "HARNESS_SUSPECT",
            f"the closing-bracket control rendered {final_control_validity!r}. The "
            "harness drifted during the run, so the cells between the brackets are "
            "not trustworthy regardless of what they said.",
        )

    if not local_controls or any(c.validity is None for c in local_controls):
        return (
            "INCOMPLETE",
            "a local control never rendered; the rivals cannot be told apart.",
        )
    dark_controls = [c for c in local_controls if c.validity != "active"]
    if dark_controls:
        names = ", ".join(c.label for c in dark_controls)
        return (
            "SETUP_SUSPECT",
            f"local control(s) {names} rendered inactive. Every rival predicts them "
            "active, so this run measured the probe setup -- most likely that the "
            "STARTER cannot sit at this cell -- and not the models. An all-inactive "
            "result here is NOT evidence for any of them.",
        )

    probe_cells = [c for c in cells if c.kind == "probe"]
    unrendered = [c for c in probe_cells if c.validity is None]
    if unrendered:
        names = ", ".join(c.label for c in unrendered)
        return "INCOMPLETE", f"cells not rendered: {names}"

    # Every rival is scored the same way: how many cells did it call wrong?
    # Nothing here privileges the model this probe was built to support.
    misses = {
        name: [c for c in probe_cells if c.predictions.get(name) != c.validity]
        for name in MODELS
    }
    survivors = sorted(name for name, wrong in misses.items() if not wrong)
    refuted = {
        name: [f"{c.label}({c.predictions[name]}->{c.validity})" for c in wrong]
        for name, wrong in misses.items()
        if wrong
    }
    detail = "; ".join(f"{name} missed {len(v)}: {', '.join(v)}" for name, v in refuted.items())

    if not survivors:
        return (
            "ALL_REFUTED",
            f"every rival got at least one cell wrong. {detail}. Something is going on "
            "that none of the stated models captures -- which is a finding, not a "
            "failure, but it means no model here may be carried forward.",
        )
    if len(survivors) > 1:
        # More than one survivor is not a shortfall. `build_cells` guarantees
        # only that SOME pair of rivals is separated, so a run can work exactly
        # as designed and still leave rivals standing that its cells cannot tell
        # apart -- at an interior starter `plate` and `port_only` predict
        # identically, because the plate term is vacuous when every neighbour is
        # on-plate. The first version of this function demanded a single
        # survivor and reported the clean 2026-08-21 interior run as
        # UNDISCRIMINATING, asserting more than the design ever promised
        # (observation #19).
        #
        # Note this is not a judgement call: surviving means matching every
        # rendered cell, and separating means differing on some cell, so two
        # survivors *entails* that nothing here separated them. There is no
        # "the run failed to discriminate" case left to branch on once every
        # cell has rendered -- INCOMPLETE above catches the one that could.
        return (
            "MODEL_SURVIVES:" + "+".join(survivors),
            f"{', '.join(survivors)} all predicted every rendered cell correctly, and "
            "no cell in this run could tell them apart -- they are equivalent at this "
            f"starter position by construction, not by accident. "
            f"{detail or 'no rival was refuted.'}. Separating them takes a position "
            "where their predictions differ.",
        )
    return (
        f"MODEL_SURVIVES:{survivors[0]}",
        f"'{survivors[0]}' predicted every rendered cell correctly and every rival was "
        f"refuted. {detail}. The predictions were declared in code before the run, so "
        "this is a surviving forward prediction rather than a fit -- which is what the "
        "2026-08-08 lock asks for and what a replay of the record cannot give.",
    )


def _write_sidecar(path: Path, cells: list[ProbeCell], meta: dict) -> None:
    """Rewrite the results JSON. Called after every render so an abort loses nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({**meta, "cells": [dataclasses.asdict(c) for c in cells]}, indent=2)
    )


def _build_course(base: Course, cell: ProbeCell) -> Course:
    """The course one cell measures."""
    return build_variant(
        base,
        starter_rot=cell.starter_rot,
        starter_pos=HexVector(y=cell.starter_y, x=cell.starter_x),
        goal_pos=HexVector(y=cell.y, x=cell.x),
        goal_rot=cell.rot,
    )


def _assert_certified_control_matches_generator(base: Course, cells: list[ProbeCell]) -> None:
    """The certified control must serialize byte-identically to `generate_minimal()`.

    Guards the variant builder only -- both sides share an origin, which is the
    shape observation #12 names, so this cannot detect generator-vs-app drift.
    That separate question was settled on 2026-08-07 by diffing against
    FLW4TMLP5V's raw bytes. What it does catch is the new `starter_pos`
    parameter silently moving a tile it should have left alone.
    """
    control = next(c for c in cells if c.role == "certified_control")
    if serialize_course(_build_course(base, control)) != serialize_course(base):
        raise RuntimeError(
            "precondition failed: the certified control variant is no longer "
            "byte-identical to generate_minimal(). build_variant's starter_pos "
            "default has changed the geometry."
        )


NAMED_STARTERS: Mapping[str, HexVector] = MappingProxyType(
    {
        "corner": CORNER_STARTER_POS,
        "edge": EDGE_STARTER_POS,
        "interior": INTERIOR_STARTER_POS,
    }
)


def _parse_starter(value: str) -> HexVector:
    """Accept a named plate position or an explicit 'y,x'."""
    if value in NAMED_STARTERS:
        return NAMED_STARTERS[value]
    try:
        y_text, x_text = value.split(",")
        return HexVector(y=int(y_text), x=int(x_text))
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected one of {sorted(NAMED_STARTERS)} or 'y,x', got {value!r}"
        ) from None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--starter",
        type=_parse_starter,
        default=EDGE_STARTER_POS,
        help=(
            "starter cell: 'corner' (0,0), 'edge' (0,1), 'interior' (-3,2), or an "
            "explicit y,x (default: edge)"
        ),
    )
    parser.add_argument(
        "--starter-rot",
        type=int,
        default=0,
        choices=range(6),
        help="starter hex_rotation; parity is what moves the port set (default: 0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build, validate and hash every payload; upload and render nothing",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="upload every variant but skip the emulator",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"screenshots and results.json (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--budget-minutes",
        type=float,
        default=15.0,
        help="pre-declared wall-clock budget; the run aborts past it (default: 15)",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="upload timeout seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = _parse_args(argv)
    started = time.monotonic()

    base = generate_minimal()
    cells = build_cells(args.starter, args.starter_rot)
    _assert_certified_control_matches_generator(base, cells)
    separated = sorted({pair for c in cells for pair in c.separates()})
    print(
        f"starter {args.starter} rot {args.starter_rot}; rivals separated by this run: "
        + ", ".join(f"{a} vs {b}" for a, b in separated),
        file=sys.stderr,
    )
    print(
        "precondition ok: at least one discriminator and one local control, certified "
        "control byte-identical to generate_minimal()",
        file=sys.stderr,
    )

    payloads: dict[int, bytes] = {}
    for i, cell in enumerate(cells):
        course = _build_course(base, cell)
        try:
            validate_strict(course, PRO_VERTICAL_STARTER_SET)
            cell.validator = "ok"
        except Exception as exc:  # validator raises ValidationError; guard broadly
            cell.validator = f"{type(exc).__name__}: {exc}"
        binary = serialize_course(course)
        payloads[i] = binary
        cell.payload_sha256 = hashlib.sha256(binary).hexdigest()
        cell.payload_bytes = len(binary)

    digests = {c.payload_sha256 for c in cells}
    if len(digests) != len(cells):
        print(
            f"error: {len(cells)} cells produced only {len(digests)} distinct payloads. "
            "Upload dedup would collapse them; the probe would not measure what it claims.",
            file=sys.stderr,
        )
        return 1
    print(
        f"precondition ok: {len(cells)} cells, {len(digests)} distinct payloads",
        file=sys.stderr,
    )

    if args.dry_run:
        print("\nplan (render order):")
        for cell in _render_order(cells):
            name = DIRECTION_NAMES[cell.direction] if cell.direction is not None else "--"
            preds = " ".join(f"{n}={cell.predictions[n]:<8}" for n in MODELS)
            print(
                f"  {cell.label:<42} dir={name:<2} on_plate={cell.goal_on_plate!s:<5} "
                f"{preds} [{cell.role}]"
            )
        print(f"\n{len(cells)} cells; nothing uploaded or rendered (--dry-run).")
        return 0

    sidecar = args.output_dir / "results.json"
    meta = {
        "timestamp": datetime.now(UTC).isoformat(),
        "probe_starter": {"y": args.starter.y, "x": args.starter.x},
        "probe_starter_rot": args.starter_rot,
        "rivals": sorted(MODELS),
        "starter_intrinsic_ports": sorted(STARTER_INTRINSIC_PORTS),
        "plate_footprint_size": len(PLATE_FOOTPRINT),
        "budget_minutes": args.budget_minutes,
    }

    ctx = None
    if not args.no_render:
        try:
            ctx = resolve_context()
            assert_emulator_ready(ctx)
        except AndroidAutomationError as exc:
            print(f"error: emulator not ready: {exc}", file=sys.stderr)
            print("       (re-run with --no-render to upload without rendering)", file=sys.stderr)
            return 1

    for i, cell in enumerate(cells):
        try:
            cell.code = upload_course(payloads[i], timeout=args.timeout)
        except UploadError as exc:
            cell.upload_error = f"{type(exc).__name__}: {exc}"
            print(f"  {cell.label}: upload failed: {exc}", file=sys.stderr)
            continue
        print(f"  {cell.label}: uploaded -> {cell.code}", file=sys.stderr)

    uploaded = [c for c in cells if c.code]
    codes = {c.code for c in uploaded}
    if len(codes) != len(uploaded):
        print(
            f"error: {len(uploaded)} uploads returned only {len(codes)} distinct share "
            "codes despite distinct payloads. Halting -- the cells are not distinct.",
            file=sys.stderr,
        )
        _write_sidecar(sidecar, cells, meta)
        return 1

    _write_sidecar(sidecar, cells, meta)
    if args.no_render:
        print(f"\nuploaded {len(uploaded)}/{len(cells)} cells; renders skipped.")
        print(f"results JSON: {sidecar}")
        return 0

    # `render_course` starts tapping at the main menu; it does not launch the
    # app, and `assert_emulator_ready` checks the emulator rather than what is
    # in the foreground. Run standalone against a booted emulator whose app is
    # closed, every tap lands on the launcher and the oracle samples the home
    # screen -- dark wallpaper, so the near-white frame guard passes it and the
    # verdict reads 'inactive'. That happened on the 2026-08-21 first run and
    # only the certified control caught it. `run_sweep_queue.py` never hit it
    # because it resets before every sweep; this borrows its settle constant
    # rather than picking a second number.
    print(f"resetting the app to the main menu, then settling {SETTLE_SECONDS:.0f}s...",
          file=sys.stderr)
    reset_to_main_menu(ctx)
    time.sleep(SETTLE_SECONDS)
    meta["reset_before_render"] = {"settle_seconds": SETTLE_SECONDS}

    budget_seconds = args.budget_minutes * 60.0
    first_render = True
    aborted: str | None = None
    for cell in _render_order(cells):
        if cell.code is None:
            continue
        elapsed = time.monotonic() - started
        if elapsed > budget_seconds:
            print(
                f"\nBUDGET ABORT: {elapsed / 60:.1f} min exceeds the pre-declared "
                f"{args.budget_minutes:.0f} min. Results so far are in {sidecar}.",
                file=sys.stderr,
            )
            aborted = "budget"
            break
        print(f"  rendering {cell.label} ({cell.code})...", file=sys.stderr)
        try:
            result = render_course(
                cell.code,
                ctx=ctx,
                screenshot_dir=args.output_dir,
                screenshot_name=f"{cell.label}_{cell.code}",
                cleanup=True,
                expect_disclaimer=first_render,
                detect_validity=True,
            )
        except AndroidAutomationError as exc:
            cell.render_error = f"{type(exc).__name__}: {exc}"
            print(f"  {cell.label}: render FAILED: {exc}", file=sys.stderr)
            _write_sidecar(sidecar, cells, meta)
            continue
        first_render = False
        cell.validity = result.validity
        cell.screenshot = str(result.screenshot)
        print(f"  {cell.label}: play button = {cell.validity}", file=sys.stderr)
        _write_sidecar(sidecar, cells, meta)

        if cell.role == "certified_control" and cell.validity != "active":
            print(
                "\nHARNESS ABORT: the app-certified control rendered "
                f"{cell.validity!r}. Debug the harness before spending the probe.",
                file=sys.stderr,
            )
            aborted = "harness"
            break
        if cell.role == "local_control" and cell.validity != "active":
            print(
                f"\nSETUP ABORT: the local control {cell.label} rendered "
                f"{cell.validity!r}. Both models predict it active, so the STARTER "
                "probably cannot sit at this cell. Rendering the discriminators now "
                "would produce an all-inactive run that looks like a confirmation "
                "and is not one.",
                file=sys.stderr,
            )
            aborted = "setup"
            break

    control = next(c for c in cells if c.role == "certified_control")
    final_validity: str | None = None
    if aborted is None and control.code:
        print("  re-rendering the certified control (closing bracket)...", file=sys.stderr)
        try:
            result = render_course(
                control.code,
                ctx=ctx,
                screenshot_dir=args.output_dir,
                screenshot_name=f"{control.label}_{control.code}_FINAL",
                cleanup=True,
                expect_disclaimer=False,
                detect_validity=True,
            )
            final_validity = result.validity
            meta["final_control_validity"] = final_validity
            meta["final_control_screenshot"] = str(result.screenshot)
            print(f"  closing bracket = {final_validity}", file=sys.stderr)
        except AndroidAutomationError as exc:
            meta["final_control_error"] = f"{type(exc).__name__}: {exc}"
            print(f"  closing bracket FAILED: {exc}", file=sys.stderr)

    verdict, explanation = classify(cells, final_validity)
    meta["aborted"] = aborted
    meta["verdict"] = verdict
    meta["verdict_explanation"] = explanation
    _write_sidecar(sidecar, cells, meta)

    print(f"\nprobe results ({len(cells)} cells):")
    print(
        f"  {'cell':<42} {'dir':<3} {'plate':<6} "
        + " ".join(f"{n:<9}" for n in MODELS)
        + f" {'rendered':<9}"
    )
    for cell in cells:
        name = DIRECTION_NAMES[cell.direction] if cell.direction is not None else "--"
        preds = " ".join(f"{cell.predictions.get(n, '-'):<9}" for n in MODELS)
        print(
            f"  {cell.label:<42} {name:<3} {cell.goal_on_plate!s:<6} {preds} "
            f"{cell.validity or cell.render_error or cell.upload_error or '-':<9}"
        )
    print(f"\nVERDICT: {verdict}")
    print(f"  {explanation}")
    print(f"\nresults JSON: {sidecar}")
    # A refutation is a successful run. Only an unreadable one is a failure.
    return 0 if verdict.startswith("MODEL_SURVIVES") or verdict == "ALL_REFUTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
