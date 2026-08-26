# scripts/probe_half_hole.py
"""The half-hole render experiment (plan.md item 5, s28).

The 2x2 (answered #17) proved that addressing a cell in-window on its owning
plate is what makes it connect. It could not say whether the cell must also be
physically *whole*, because a normal cell that is in-window on its own plate is
always also supported by that plate. Half-holes are the one configuration where
those come apart: a seam cell is on its plate's footprint (addressable, and the
model predicts it live) yet the app editor refuses a piece there until the
neighbouring plate at `find_tiling_delta` fills the other half of the hole.

So this puts a goal on a half-hole and changes *only* whether the completing
neighbour is present. The goal's address -- plate, local `(y,x)`, rotation -- is
byte-identical across the arms; the board around it is what moves.

Three arms per tested direction, one factor between them:

* **A (lone)** -- goal on the half-hole, the starter's plate and nothing else.
* **B (completed)** -- add the plate at the completer delta. It physically fills
  *this* seam's hole (verified by hole-adjacency, not by `_is_gapless`, which is
  the one-axis test the deferred-cleanup flags as unsound for picking a side).
* **C (null)** -- add a plate at the opposite delta instead. A real lattice
  neighbour, but it completes a *disjoint* seam set and leaves the tested cell as
  unsupported as arm A.

The comparisons: **C vs B** isolates support with both being two-plate courses;
**A vs C** is the predicted null -- adding a non-completing plate must change
nothing, and a difference there voids the reading (a positive result that
discriminates nothing, observation #21). The shipped `predict_connection` has no
support term, so it calls every arm active; if support gates, A and C render
dark and only B lights, refuting it exactly where the docstring says to expect
it (observation #20).

Two directions are rendered (E and SW from one starter), because this project
has twice been surprised by one direction behaving unlike its neighbour, so a
single-direction result would be n=1 where the record is least safe.

Geometry is **derived** from `plates.seam_cells` and `find_tiling_delta`, never
typed (observation #24 / the *Classes* discipline): the concrete cells below are
regenerated on every run, and `--dry-run` prints them for a human to check
before anything is uploaded.

Deferred-cleanup note this file adds: the upload+render+sidecar campaign harness
is now duplicated a third time (with `probe_plate_membership` and
`probe_plate_boundary`). The retry-on-refused `render_arm` is reused from
`probe_plate_boundary`; the loop around it wants extracting into a shared module,
which is a refactor to do between campaigns, not before one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from scripts.probe_plate_boundary import render_arm
from scripts.probe_plate_seams import find_tiling_delta, seam_cells
from traxgen.android import (
    AdbContext,
    AndroidAutomationError,
    assert_emulator_ready,
    reset_to_main_menu,
    resolve_context,
)
from traxgen.generator import generate_minimal
from traxgen.graph import predicted_live_directions
from traxgen.hex import HEX_DIRECTIONS, HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.layout import CERTIFIED_LAYER_HEIGHT, TilePlacement, build_course
from traxgen.plates import plate_footprint
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind, TileKind
from traxgen.uploader import UploadError, upload_course_with_retry
from traxgen.validator import validate_strict

PLATE = LayerKind.BASE_LAYER_PIECE
DIRECTION_NAMES = {0: "E", 1: "NE", 2: "NW", 3: "W", 4: "SW", 5: "SE"}
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "screenshots" / "half_hole"
RENDER_ATTEMPTS = 2  # matched to probe_plate_boundary.render_arm's own loop


def _neighbour(cell: tuple[int, int], direction: int) -> tuple[int, int]:
    v = HexVector(cell[0], cell[1]).neighbor(direction)
    return (v.y, v.x)


def _supports(delta: tuple[int, int], seam: tuple[int, int], footprint: frozenset) -> bool:
    """Whether a plate at `delta` physically completes `seam`'s hole.

    Hole-adjacency: the plate contributes a cell that is a hex-neighbour of the
    seam on the side *off* the home footprint. This is the discriminating test
    `_is_gapless` cannot do -- it calls both the completer and its opposite
    gapless, because gaplessness of the union is symmetric while completion of a
    *particular* seam is not.
    """
    translated = {(y + delta[0], x + delta[1]) for (y, x) in footprint}
    for d in range(len(HEX_DIRECTIONS)):
        n = _neighbour(seam, d)
        if n not in footprint and n in translated:
            return True
    return False


@dataclass(frozen=True, slots=True)
class Target:
    """One tested direction: a seam goal the starter reaches, and its rotation."""

    direction: int
    seam_local: tuple[int, int]
    goal_rot: int


@dataclass(frozen=True, slots=True)
class Geometry:
    kind: LayerKind
    starter_local: tuple[int, int]
    starter_rot: int
    completer_delta: tuple[int, int]
    null_delta: tuple[int, int]
    control_direction: int
    control_local: tuple[int, int]
    control_rot: int
    negative_direction: int
    negative_local: tuple[int, int]
    negative_rot: int
    targets: tuple[Target, ...]


def _goal_rotation(direction: int) -> int:
    # g = (d + 1) % 6, the goal-side rule (decisions.md 2026-08-08). Imported
    # indirectly via graph would be cleaner, but the rule is one line and stated
    # here beside the direction it applies to.
    return (direction + 1) % len(HEX_DIRECTIONS)


def derive_geometry(kind: LayerKind = PLATE) -> Geometry:
    """Everything the campaign needs, derived from the footprint and the seams.

    Finds a starter placement on a *solid* cell whose model-predicted live set
    reaches at least two seam cells (the tests) and at least one solid cell (the
    local control), all as direct neighbours. Prefers the placement offering the
    most tested seams, then the lowest starter coordinate, for determinism.
    """
    footprint = plate_footprint(kind)
    seams = seam_cells(kind)
    solid = footprint - seams
    completer = find_tiling_delta(footprint)

    best: tuple | None = None
    for s_cell in sorted(solid):
        for s_rot in range(len(HEX_DIRECTIONS)):
            live = predicted_live_directions(
                s_rot,
                layer_kind=kind,
                starter_local_pos=HexVector(*s_cell),
                # The goal on the starter's own plate: this search asks what one
                # plate reaches unaided, the arm the experiment turns on.
                goal_plate_offset=None,
            )
            seam_dirs = [d for d in sorted(live) if _neighbour(s_cell, d) in seams]
            solid_dirs = [d for d in sorted(live) if _neighbour(s_cell, d) in solid]
            if len(seam_dirs) >= 2 and solid_dirs:
                key = (-len(seam_dirs), s_cell, s_rot)
                if best is None or key < best[0]:
                    best = (key, s_cell, s_rot, seam_dirs, solid_dirs)
    if best is None:
        raise ValueError("no starter reaches two seam cells and a solid cell at once")
    _, s_cell, s_rot, seam_dirs, solid_dirs = best

    tested = seam_dirs[:2]
    tested_seams = [_neighbour(s_cell, d) for d in tested]
    # The null plate: the nearest lattice neighbour completing NEITHER tested seam.
    from scripts.probe_plate_seams import tiling_deltas

    null_candidates = [
        d
        for d in tiling_deltas(footprint)
        if not any(_supports(d, seam, footprint) for seam in tested_seams)
    ]
    if not null_candidates:
        raise ValueError("no lattice plate leaves both tested seams unsupported")
    null_delta = min(null_candidates, key=lambda d: (abs(d[0]) + abs(d[1]), d))
    # Sanity, verified rather than assumed: the completer supports BOTH tested seams.
    for seam in tested_seams:
        if not _supports(completer, seam, footprint):
            raise ValueError(f"completer {completer} does not support tested seam {seam}")

    control_dir = solid_dirs[0]
    # The negative control: the FIRST tested seam's own cell at a **wrong goal
    # rotation**. Single-factor from an arm the same run renders active, so if
    # the oracle returns inactive here it has demonstrably discriminated on this
    # boot; if it returns active, an all-active campaign carries no information
    # (the s27 splash/tutorial false-actives are exactly that failure mode).
    # `g = (d + 1) % 6` has zero exceptions across six exhaustive 36-cell sweeps
    # (`decisions.md` 2026-08-08), so a wrong rotation is measured-dark with the
    # largest n in the record -- and `predict_connection` returns False for it.
    negative_dir = tested[0]
    negative_rot = (_goal_rotation(negative_dir) + 3) % len(HEX_DIRECTIONS)
    return Geometry(
        kind=kind,
        starter_local=s_cell,
        starter_rot=s_rot,
        completer_delta=completer,
        null_delta=null_delta,
        control_direction=control_dir,
        control_local=_neighbour(s_cell, control_dir),
        control_rot=_goal_rotation(control_dir),
        negative_direction=negative_dir,
        negative_local=_neighbour(s_cell, negative_dir),
        negative_rot=negative_rot,
        targets=tuple(
            Target(direction=d, seam_local=_neighbour(s_cell, d), goal_rot=_goal_rotation(d))
            for d in tested
        ),
    )


@dataclass
class Arm:
    role: str  # certified_control | local_control | lone | completed | null
    label: str
    direction: int | None
    plate_deltas: tuple[tuple[int, int], ...]
    goal_local: tuple[int, int] | None
    goal_rot: int | None
    predicted: str  # 'active' | 'inactive' -- what the shipped model says
    why: str
    # result fields, filled as the run proceeds (names shared with render_arm)
    payload_bytes: int | None = None
    validator: str | None = None
    code: str | None = None
    upload_error: str | None = None
    upload_attempts: int | None = None
    validity: str | None = None
    render_error: str | None = None
    screenshot: str | None = None
    render_attempts: int = 0
    refused_screens: list[str] = field(default_factory=list)
    payload_sha256: str | None = None


def build_arms(geometry: Geometry) -> list[Arm]:
    """Certified brackets, a solid local control, and three arms per tested seam."""
    lone = ((0, 0),)
    completed = ((0, 0), geometry.completer_delta)
    null = ((0, 0), geometry.null_delta)
    arms: list[Arm] = [
        Arm(
            role="certified_control",
            label="certified_open",
            direction=None,
            plate_deltas=lone,
            goal_local=None,
            goal_rot=None,
            predicted="active",
            why="generate_minimal(): proves the harness renders at all (both ends)",
        ),
        Arm(
            role="local_control",
            label="local_control",
            direction=geometry.control_direction,
            plate_deltas=lone,
            goal_local=geometry.control_local,
            goal_rot=geometry.control_rot,
            predicted="active",
            why=(
                f"goal on solid {geometry.control_local} "
                f"({DIRECTION_NAMES[geometry.control_direction]}): proves this "
                "starter's geometry renders on a lone plate (decisions.md, s21)"
            ),
        ),
        Arm(
            role="negative_control",
            label="negative_control",
            direction=geometry.negative_direction,
            plate_deltas=lone,
            goal_local=geometry.negative_local,
            goal_rot=geometry.negative_rot,
            predicted="inactive",
            why=(
                f"same cell as lone_{DIRECTION_NAMES[geometry.negative_direction]} "
                f"at the WRONG goal rotation ({geometry.negative_rot} instead of "
                f"{_goal_rotation(geometry.negative_direction)}): proves the oracle "
                "can still return inactive on this boot, so an all-active run means "
                "something"
            ),
        ),
    ]
    for target in geometry.targets:
        name = DIRECTION_NAMES[target.direction]
        common = {
            "direction": target.direction,
            "goal_local": target.seam_local,
            "goal_rot": target.goal_rot,
            "predicted": "active",  # the shipped model has no support term
        }
        arms.append(
            Arm(
                role="lone",
                label=f"lone_{name}",
                plate_deltas=lone,
                why=f"half-hole {target.seam_local} {name}, unsupported (lone plate)",
                **common,
            )
        )
        arms.append(
            Arm(
                role="completed",
                label=f"completed_{name}",
                plate_deltas=completed,
                why=(
                    f"same goal, plate at {geometry.completer_delta} completes the hole "
                    "-- the only factor that moved from the lone arm"
                ),
                **common,
            )
        )
        arms.append(
            Arm(
                role="null",
                label=f"null_{name}",
                plate_deltas=null,
                why=(
                    f"same goal, plate at {geometry.null_delta} completes a disjoint seam "
                    "and leaves this one unsupported -- predicted null, must equal the lone arm"
                ),
                **common,
            )
        )
    # close bracket
    arms.append(
        Arm(
            role="certified_control",
            label="certified_close",
            direction=None,
            plate_deltas=lone,
            goal_local=None,
            goal_rot=None,
            predicted="active",
            why="generate_minimal() again: a dead close voids the run (decisions.md, s27)",
        )
    )
    return arms


def build_arm_course(arm: Arm, geometry: Geometry, layer_height: float):
    """The Course for one arm. The certified control is the generator's own output."""
    if arm.role == "certified_control":
        return generate_minimal()
    assert arm.goal_local is not None and arm.goal_rot is not None
    plate_positions = [HexVector(y, x) for (y, x) in arm.plate_deltas]
    starter = TilePlacement(
        TileKind.STARTER, 0, HexVector(*geometry.starter_local), geometry.starter_rot
    )
    goal = TilePlacement(
        TileKind.GOAL_RAIL, 0, HexVector(*arm.goal_local), arm.goal_rot
    )
    return build_course(
        plate_world_positions=plate_positions,
        tiles=(starter, goal),
        title="traxgen-minimal",
        layer_height=layer_height,
    )


def classify(arms: list[Arm]) -> tuple[str, str]:
    """The run's verdict from the arms' validities, in guard order.

    Order matters and mirrors the harness's own layering: a lie about the
    harness (a dead control) overrides everything, then a lie about the geometry
    family (a dead local control), then the null (adding a non-completer changed
    the result), and only inside all three is the support question read.
    """
    def validity(role: str, direction: int | None = None) -> str | None:
        for a in arms:
            if a.role == role and (direction is None or a.direction == direction):
                return a.validity
        return None

    controls = [a for a in arms if a.role == "certified_control"]
    if any(a.validity != "active" for a in controls):
        return "HARNESS_SUSPECT", "a certified control did not render active"
    if validity("negative_control") != "inactive":
        return (
            "ORACLE_SUSPECT",
            "the negative control did not render inactive, so the oracle has not been "
            "shown to discriminate on this boot and an all-active run carries no "
            "information -- the s27 false-active failure mode",
        )
    if validity("local_control") != "active":
        return (
            "SETUP_SUSPECT",
            "the solid local control did not render active, so a dark test arm cannot "
            "be read as a half-hole result rather than an unrenderable geometry",
        )

    per_direction: dict[str, dict[str, str | None]] = {}
    for a in arms:
        if a.role in ("lone", "completed", "null"):
            name = DIRECTION_NAMES[a.direction]
            per_direction.setdefault(name, {})[a.role] = a.validity

    readings: dict[str, str] = {}
    for name, arms_by_role in per_direction.items():
        lone = arms_by_role.get("lone")
        completed = arms_by_role.get("completed")
        null = arms_by_role.get("null")
        if None in (lone, completed) or (null is None and "null" in arms_by_role):
            return "INCOMPLETE", f"{name}: an arm has no validity ({arms_by_role})"
        if null is not None and lone != null:
            return (
                "CONFOUNDED",
                f"{name}: lone={lone} but null={null} -- adding a non-completing plate "
                "changed the result, so support is not the only factor moving",
            )
        if lone == "active" and completed == "active":
            readings[name] = "window_only"
        elif lone == "inactive" and completed == "active":
            readings[name] = "support_gates"
        else:
            return (
                "INDETERMINATE",
                f"{name}: lone={lone}, completed={completed} -- neither reading fits",
            )

    distinct = set(readings.values())
    if len(distinct) > 1:
        return "DIRECTIONS_DISAGREE", f"directions gave different readings: {readings}"
    reading = distinct.pop()
    if reading == "window_only":
        return (
            "WINDOW_ONLY",
            "half-holes render active on a lone plate: a correct in-window address is the "
            "whole rule, physical support is not a gate, and predict_connection is right here",
        )
    return (
        "SUPPORT_GATES",
        "half-holes render dark alone and active once completed: physical support is a "
        "second gate the generator must respect, and predict_connection is refuted here too",
    )


def _render_order(arms: list[Arm]) -> list[Arm]:
    if arms[0].role != "certified_control" or arms[-1].role != "certified_control":
        raise ValueError("the run must open and close on a certified control")
    return arms


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--layer-height",
        type=float,
        default=CERTIFIED_LAYER_HEIGHT,
        help="try -0.2 if the local control renders dark (decisions.md, s24)",
    )
    parser.add_argument("--dry-run", action="store_true", help="plan only; nothing uploaded")
    parser.add_argument("--no-render", action="store_true", help="upload but do not render")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started = time.monotonic()
    geometry = derive_geometry()
    arms = _render_order(build_arms(geometry))

    print(
        f"derived: starter {geometry.starter_local} rot {geometry.starter_rot}; "
        f"completer {geometry.completer_delta}; null {geometry.null_delta}",
        file=sys.stderr,
    )
    for target in geometry.targets:
        print(
            f"  test {DIRECTION_NAMES[target.direction]:<2}: half-hole goal "
            f"{target.seam_local} rot {target.goal_rot}",
            file=sys.stderr,
        )

    payloads: dict[int, bytes] = {}
    for i, arm in enumerate(arms):
        course = build_arm_course(arm, geometry, args.layer_height)
        try:
            validate_strict(course, PRO_VERTICAL_STARTER_SET)
            arm.validator = "ok"
        except Exception as exc:  # ValidationError; guarded broadly on purpose
            arm.validator = f"{type(exc).__name__}: {exc}"
        binary = serialize_course(course)
        payloads[i] = binary
        arm.payload_sha256 = hashlib.sha256(binary).hexdigest()
        arm.payload_bytes = len(binary)

    # The two certified controls dedup to one share code by design; every other
    # arm must be distinct or upload dedup collapses two renders into one. Note
    # the lone/completed/null arms for one direction share a goal address but
    # differ in plate layout, so their payloads differ -- checked, not assumed.
    non_control = [a for a in arms if a.role != "certified_control"]
    distinct = {a.payload_sha256 for a in non_control}
    if len(distinct) != len(non_control):
        print(
            f"error: {len(non_control)} non-control arms produced {len(distinct)} "
            "distinct payloads; dedup would collapse them",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        print("\nplan (render order):")
        for arm in arms:
            plates = "+".join(str(d) for d in arm.plate_deltas)
            print(
                f"  {arm.label:<18} plates={plates:<16} goal={arm.goal_local} "
                f"rot={arm.goal_rot} predicted={arm.predicted:<8} [{arm.role}]"
            )
            print(f"      validator={arm.validator}  sha={(arm.payload_sha256 or '')[:12]}")
            print(f"      {arm.why}")
        print(f"\n{len(arms)} renders; nothing uploaded (--dry-run).")
        return 0

    ctx: AdbContext | None = None
    if not args.no_render:
        try:
            ctx = resolve_context()
            assert_emulator_ready(ctx)
        except AndroidAutomationError as exc:
            print(f"error: emulator not ready: {exc}", file=sys.stderr)
            return 1

    for i, arm in enumerate(arms):
        def _note(attempt: int, exc: UploadError, delay: float, label: str = arm.label) -> None:
            print(
                f"  {label}: upload attempt {attempt} failed ({type(exc).__name__}); "
                f"retrying in {delay:.0f}s",
                file=sys.stderr,
            )

        try:
            arm.code, arm.upload_attempts = upload_course_with_retry(payloads[i], on_retry=_note)
        except UploadError as exc:
            arm.upload_error = f"{type(exc).__name__}: {exc}"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if ctx is not None:
        print(f"run started {datetime.now(UTC):%H:%M:%SZ}", file=sys.stderr)
        reset_to_main_menu(ctx)
        for arm in arms:
            if arm.code is None:
                continue
            render_arm(ctx, arm, args.output_dir)
            print(f"  {arm.label:<18} -> {arm.validity or arm.render_error}", file=sys.stderr)

    verdict, reason = classify(arms)
    sidecar = args.output_dir / "results.json"
    sidecar.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "geometry": asdict(geometry),
                "layer_height": args.layer_height,
                "verdict": verdict,
                "reason": reason,
                "arms": [asdict(a) for a in arms],
            },
            indent=2,
        )
    )
    print(f"\nverdict: {verdict}\n  {reason}\n  sidecar: {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
