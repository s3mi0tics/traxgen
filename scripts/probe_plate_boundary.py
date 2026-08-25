"""The #17 2x2: is "off-plate" physical, or outside a canonical coordinate window?

A goal cell absent from the measured baseplate footprint does not connect --
rendered, twice, at two starter positions (`decisions.md`, 2026-08-21). What no
render has established is **why**. Either the cell has no plate under it, or the
format stores layer-local coordinates inside a canonical window and our variants
were simply malformed addresses. The operational consequence is identical today,
which is why it never blocked #15 -- but it decides how the generator places
tiles once a course has more than one plate, and 599 of 640 real courses do.

**The experiment is a 2x2, and the design is locked** (`decisions.md`, s24). The
handoff's original shape -- add a plate beneath a dead cell and re-render -- moves
plate presence and address validity together, so both readings predict a light
and a positive result discriminates nothing (observations #21, in the mirror).
Instead the *same world cell* is rendered under both addressings on one
two-plate course:

    plate present + in-window address    arm 1 -- goal on the plate that owns it
    plate present + out-of-window        arm 2 -- goal on the home plate
    plate absent  + out-of-window        measured dark, 2026-08-21 (s21)
    plate absent  + in-window            impossible: in-window *means* on plate

Arm 1 against arm 2 isolates addressing. Arm 2 against s21 isolates plate
presence. Every geometry here is derived from the measured footprint and the
rendered record rather than typed -- see `derive_geometry`.

**What each outcome licenses** is pre-declared in `classify` rather than read
into the result afterwards (`decisions.md`, 2026-08-08). Note the conjunction
predicts **both arms dark**: `predict_connection` carries no plate-set term, so
it answers from the starter's own footprint alone, where the target direction is
off-plate. A light in either arm refutes the single-plate model for multi-plate
courses, which is the whole point; both dark is informative too, but only because
the local control proves the two-plate family renders at all.

**Controls, per two locked rules.** The certified geometry brackets the run at
both ends, and a non-active closing bracket overrides the verdict to
HARNESS_SUSPECT whatever the data said (2026-08-07). And because this run moves
tiles onto a plate layout nothing has ever rendered, it also carries a control
*at the position under test* -- a cell the measured record already calls active
at this starter placement -- so that "the two-plate family does not render" and
"the model is right" cannot produce the same all-dark run (2026-08-21).

**Scope, stated rather than implied.** This is a second render harness beside
`probe_plate_membership.py`, and the run loop below duplicates its
upload-then-render ordering, retry counting and sidecar shape. That duplication
is deliberate and is a follow-up, not an oversight: the two probes declare
genuinely different cells -- that one varies direction on one plate, this one
varies *which layer the goal is addressed on* -- and `ProbeCell` has no field for
the latter. Extracting the shared harness is the right refactor and belongs in
its own change; doing it inside an experiment build is how the s25 defect
happened (a guard relocated while behaviour changed).

Run: `uv run python -m scripts.probe_plate_boundary --dry-run`

Path: traxgen/scripts/probe_plate_boundary.py
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

from scripts.probe_plate_seams import find_tiling_delta
from traxgen.android import (
    AdbContext,
    AndroidAutomationError,
    RefusedScreenError,
    assert_emulator_ready,
    render_course,
    reset_to_main_menu,
    resolve_context,
)
from traxgen.generator import generate_minimal
from traxgen.graph import (
    STARTER_PLATE_ONLY,
    goal_rotation_for,
    measured_live_directions,
    predict_connection,
    starter_world_ports,
)
from traxgen.hex import DIRECTION_NAMES, HEX_DIRECTIONS, HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.layout import CERTIFIED_LAYER_HEIGHT, TilePlacement, build_course
from traxgen.plates import MEASURED_FOOTPRINTS
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind, TileKind
from traxgen.uploader import UploadError, upload_course_with_retry
from traxgen.validator import validate_strict

PLATE = LayerKind.BASE_LAYER_PIECE

# The starter placement this run uses, and the reason it is this one: s21
# rendered it on a lone plate and recorded the result, so the third cell of the
# 2x2 (plate absent, out-of-window address) is already measured and the local
# control can be derived from the record rather than predicted.
STARTER_LOCAL = HexVector(y=0, x=1)
STARTER_ROT = 0

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "screenshots" / "plate_boundary"


@dataclass(frozen=True)
class Target:
    """One world cell the 2x2 is run on, addressable two ways."""

    direction: int
    home_local: tuple[int, int]
    completer_local: tuple[int, int]

    @property
    def goal_rot(self) -> int:
        return goal_rotation_for(self.direction)

    @property
    def name(self) -> str:
        return DIRECTION_NAMES[self.direction]


@dataclass(frozen=True)
class Geometry:
    """Everything about where the tiles go, derived rather than typed."""

    completer_delta: tuple[int, int]
    targets: tuple[Target, ...]
    control_direction: int
    control_home_local: tuple[int, int]

    @property
    def control_goal_rot(self) -> int:
        return goal_rotation_for(self.control_direction)


def derive_geometry() -> Geometry:
    """Pick the target and control cells from measured facts, never by hand.

    A target must satisfy three things at once: it is a port the starter
    actually has at this rotation, its neighbour is **off** the home plate's
    footprint, and that same neighbour is **on** the completing plate's
    footprint. Any of the three typed in by hand would be a coordinate claim
    with nothing behind it (observations #12's *Classes* discipline, and the #30
    ordering lesson one axis over).

    **Two directions qualify at this starter, not one**, which the first version
    of this function asserted and its own guard refused (s27). E and SW are both
    port-allowed, both off the home footprint, and both covered by the completing
    plate. So the 2x2 runs twice, on two different directions, and
    `decisions.md`'s "five renders including the controls" becomes seven. That is
    a replication rather than a design change, and it is worth the two renders:
    this project has twice had a direction behave differently from its
    neighbours -- SW rendered active at an interior cell after six exhaustive
    sweeps called it dark -- so a single-direction result would be n=1 in exactly
    the place the record has been surprised before.

    The control comes from the rendered record rather than from a model:
    `measured_live_directions` at this exact placement, which is s21's edge run.
    Deriving it that way is what makes it a control -- a cell the record already
    calls active -- rather than another cell the model merely likes.
    """
    footprint = frozenset(MEASURED_FOOTPRINTS[PLATE])
    completer = find_tiling_delta(footprint)
    ports = starter_world_ports(STARTER_ROT)

    targets = []
    for direction in sorted(ports):
        dy, dx = HEX_DIRECTIONS[direction]
        home_local = (STARTER_LOCAL.y + dy, STARTER_LOCAL.x + dx)
        if home_local in footprint:
            continue  # on the home plate: not the cell this experiment is about
        on_completer = (home_local[0] - completer[0], home_local[1] - completer[1])
        if on_completer in footprint:
            targets.append(Target(direction, home_local, on_completer))
    if not targets:
        raise ValueError(
            "no port direction at this starter is both off the home footprint and on "
            "the completing plate, so there is no cell the 2x2 can be run on"
        )

    live = measured_live_directions(
        STARTER_ROT,
        layer_kind=PLATE,
        starter_local_pos=STARTER_LOCAL,
        plate_offsets=STARTER_PLATE_ONLY,
        goal_layer_kind=PLATE,
        goal_plate_offset=None,
    )
    if not live:
        raise ValueError(
            f"no rendered run covers starter {STARTER_LOCAL} rot {STARTER_ROT} on a "
            "lone plate, so this run has no control the record already calls active"
        )
    control_direction = sorted(live)[0]
    cdy, cdx = HEX_DIRECTIONS[control_direction]
    control_home_local = (STARTER_LOCAL.y + cdy, STARTER_LOCAL.x + cdx)
    if control_home_local not in footprint:
        raise ValueError(
            f"the control cell {control_home_local} is off the home footprint, so it "
            "would test the same thing the arms do rather than bracket them"
        )

    return Geometry(
        completer_delta=completer,
        targets=tuple(targets),
        control_direction=control_direction,
        control_home_local=control_home_local,
    )


@dataclass
class Arm:
    """One rendered geometry, with its expected verdict declared before the run."""

    role: str  # certified_control | local_control | arm1_owning_plate | arm2_home_plate
    label: str
    target_name: str | None
    two_plate: bool
    goal_plate_index: int | None
    goal_local: tuple[int, int] | None
    goal_rot: int | None
    predicted: str  # 'active' | 'inactive' -- what the shipped model says
    why: str
    payload_sha256: str | None = None
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


# One retry, and the reasoning is the same as the s23 upload-retry lock.
#
# The 2026-08-25 run lost two of seven renders to the build-tutorial screen at
# positions 3 and 7, with 4, 5 and 6 clean in between -- an intermittent race,
# not a state that persists, so a second attempt is very likely to land. One
# rather than three because a refused screen that repeats is a *finding* (the
# flow is broken, not unlucky) and burning renders on it hides that.
#
# The count is recorded into the sidecar rather than swallowed, for the reason
# `upload_attempts` is: a run that quietly recovered twice must not read as a
# clean one, and the refusal distances are the calibration data for the
# threshold that produced them.
RENDER_ATTEMPTS = 2


def render_arm(ctx: AdbContext, arm: Arm, output_dir: Path) -> None:
    """Render one arm, retrying once if the harness lands on a known dead screen.

    Only `RefusedScreenError` is retried. Every other harness failure is
    recorded and left alone, by the same exception-class discipline the upload
    retry uses: a wrong foreground app or an unreadable frame will not be
    different on a second try, and retrying is a slower no.
    """
    for attempt in range(1, RENDER_ATTEMPTS + 1):
        arm.render_attempts = attempt
        try:
            result = render_course(
                arm.code or "",
                ctx=ctx,
                screenshot_dir=output_dir,
                # NOT f"{arm.label}.png" -- `render_course` appends the
                # extension itself, and the old form produced `.png.png` files.
                screenshot_name=f"{arm.label}_try{attempt}",
                detect_validity=True,
                reset_first=True,
            )
        except RefusedScreenError as exc:
            arm.refused_screens.append(f"{exc.screen}@{exc.distance:.3f}")
            arm.render_error = f"{type(exc).__name__}: {exc}"
            if attempt < RENDER_ATTEMPTS:
                print(
                    f"  {arm.label}: landed on {exc.screen!r} "
                    f"(distance {exc.distance:.3f}); re-rendering",
                    file=sys.stderr,
                )
                continue
            return
        except Exception as exc:  # harness failure is data, not a crash
            arm.render_error = f"{type(exc).__name__}: {exc}"
            return
        arm.render_error = None
        arm.validity = result.validity
        arm.screenshot = str(result.screenshot) if result.screenshot else None
        return


def plate_positions(geometry: Geometry) -> tuple[HexVector, HexVector]:
    """Home plate at the origin, completer at the derived delta."""
    return (
        HexVector(y=0, x=0),
        HexVector(y=geometry.completer_delta[0], x=geometry.completer_delta[1]),
    )


def build_arms(geometry: Geometry) -> list[Arm]:
    """The renders, in order, each with a pre-declared verdict.

    Two arms per target plus one local control, bracketed by the certified
    geometry: seven renders for the two targets this starter offers.

    The arms are declared **inactive** because that is what the shipped
    conjunction says, computed here rather than asserted: `predict_connection`
    has no plate-set term, so at this starter every target direction is off the
    home footprint and the model calls it dead on any layout. That makes each
    arm a genuine forward test rather than a fit (observations #20) -- a light
    refutes the single-plate model where #17 says it might.
    """

    def predict(direction: int) -> str:
        return (
            "active"
            if predict_connection(
                STARTER_ROT,
                direction,
                goal_rotation_for(direction),
                layer_kind=PLATE,
                starter_local_pos=STARTER_LOCAL,
            )
            else "inactive"
        )

    control = DIRECTION_NAMES[geometry.control_direction]
    arms = [
        Arm(
            role="certified_control",
            label="certified_open",
            target_name=None,
            two_plate=False,
            goal_plate_index=None,
            goal_local=None,
            goal_rot=None,
            predicted="active",
            why="FLW4TMLP5V's geometry: proves the harness worked at render 1",
        ),
        Arm(
            role="local_control",
            label=f"local_control_{control}",
            target_name=None,
            two_plate=True,
            goal_plate_index=0,
            goal_local=geometry.control_home_local,
            goal_rot=geometry.control_goal_rot,
            predicted=predict(geometry.control_direction),
            why=(
                f"{control} is active in the rendered record at this starter on a lone "
                "plate; here it proves the TWO-plate family renders at all, which is "
                "the only thing that makes a dark set of arms mean anything"
            ),
        ),
    ]
    for target in geometry.targets:
        arms.append(
            Arm(
                role="arm1_owning_plate",
                label=f"arm1_{target.name}_on_completer",
                target_name=target.name,
                two_plate=True,
                goal_plate_index=1,
                goal_local=target.completer_local,
                goal_rot=target.goal_rot,
                predicted=predict(target.direction),
                why=(
                    "plate present, in-window address: the goal is addressed on the "
                    "plate that owns the cell. Recordable since s27 -- the record now "
                    "keys on which layer the goal stood on"
                ),
            )
        )
        arms.append(
            Arm(
                role="arm2_home_plate",
                label=f"arm2_{target.name}_on_home",
                target_name=target.name,
                two_plate=True,
                goal_plate_index=0,
                goal_local=target.home_local,
                goal_rot=target.goal_rot,
                predicted=predict(target.direction),
                why=(
                    "plate present, out-of-window address: the same world cell, "
                    "addressed on the home plate off its own footprint. `build_course` "
                    "deliberately does not refuse this (decisions.md, s24)"
                ),
            )
        )
    arms.append(
        Arm(
            role="certified_control",
            label="certified_close",
            target_name=None,
            two_plate=False,
            goal_plate_index=None,
            goal_local=None,
            goal_rot=None,
            predicted="active",
            why="the closing bracket: proves the harness still worked at the last render",
        )
    )
    return arms


def build_arm_course(arm: Arm, geometry: Geometry, layer_height: float):
    """The Course for one arm. The certified control is the generator's own output."""
    if arm.role == "certified_control":
        return generate_minimal()
    plates = plate_positions(geometry)
    assert arm.goal_local is not None and arm.goal_rot is not None
    assert arm.goal_plate_index is not None
    return build_course(
        plate_world_positions=plates,
        tiles=(
            TilePlacement(TileKind.STARTER, 0, STARTER_LOCAL, STARTER_ROT),
            TilePlacement(
                TileKind.GOAL_RAIL,
                arm.goal_plate_index,
                HexVector(y=arm.goal_local[0], x=arm.goal_local[1]),
                arm.goal_rot,
            ),
        ),
        title="traxgen-minimal",
        layer_height=layer_height,
    )


def classify(arms: list[Arm]) -> tuple[str, str]:
    """The verdict, from conditions declared before any render.

    Order matters and is itself a locked rule: anything questioning the harness
    or the setup overrides whatever the arms said, because a run whose
    instrument is in doubt has no findings to report (`decisions.md` 2026-08-07
    and 2026-08-21).

    With more than one target the per-target verdicts are computed first and
    only then combined, so that **targets disagreeing is its own outcome** rather
    than being averaged into one of the others. That case is not a failure of the
    run; it would mean the answer is direction-specific, which is a thing this
    project has measured before and would need its own follow-up.
    """
    by_role: dict[str, list[Arm]] = {}
    for arm in arms:
        by_role.setdefault(arm.role, []).append(arm)

    controls = by_role.get("certified_control", [])
    if not controls or any(c.validity != "active" for c in controls):
        return (
            "HARNESS_SUSPECT",
            "a certified control did not render active, so nothing else in this run "
            "is a measurement whatever it says",
        )

    local = (by_role.get("local_control") or [None])[0]
    if local is None or local.validity != "active":
        return (
            "SETUP_SUSPECT",
            "the control at the position under test did not render active, so the "
            "two-plate family may not render at all and a dark arm measures nothing. "
            f"First thing to try: layer_height -0.2 rather than {CERTIFIED_LAYER_HEIGHT} "
            "(decisions.md, s24) -- 4,598 of 4,599 real plates use it",
        )

    per_target: dict[str, str] = {}
    ones = {a.target_name: a for a in by_role.get("arm1_owning_plate", [])}
    twos = {a.target_name: a for a in by_role.get("arm2_home_plate", [])}
    if not ones or set(ones) != set(twos):
        return ("INCOMPLETE", "a target is missing one of its two arms")
    for name in sorted(ones):
        one, two = ones[name], twos[name]
        if one.validity is None or two.validity is None:
            return ("INCOMPLETE", f"target {name} produced no verdict for an arm")
        lit_one, lit_two = one.validity == "active", two.validity == "active"
        if lit_one and not lit_two:
            per_target[name] = "ADDRESSING_MATTERS"
        elif lit_one and lit_two:
            per_target[name] = "PLATE_PRESENCE_MATTERS"
        elif not lit_one and not lit_two:
            per_target[name] = "NEITHER_ARM_LIT"
        else:
            per_target[name] = "UNEXPECTED_ORDERING"

    verdicts = set(per_target.values())
    detail = ", ".join(f"{n}={v}" for n, v in sorted(per_target.items()))
    if len(verdicts) > 1:
        return (
            "TARGETS_DISAGREE",
            f"the two target cells did not behave the same way ({detail}), so whatever "
            "gates this cell is direction-specific. Do not collapse this into either "
            "reading of #17 -- it is a third thing, and it needs its own run",
        )

    verdict = verdicts.pop()
    reasons = {
        "ADDRESSING_MATTERS": (
            "the cell connects when addressed on the plate that owns it and not when "
            "addressed off the home plate's window, so 'off-plate' is a coordinate "
            "window rather than a physical absence. The generator must address a cell "
            "on its owning plate"
        ),
        "PLATE_PRESENCE_MATTERS": (
            "the cell connects under both addressings, and s21 measured it dark with "
            "no plate beneath, so what changed is the plate rather than the address. "
            "'Off-plate' is physical"
        ),
        "NEITHER_ARM_LIT": (
            "adding the plate did not make the cell connect under either addressing, "
            "while the local control proves the family renders. So neither reading of "
            "#17 as stated is sufficient, and something else gates this cell"
        ),
        "UNEXPECTED_ORDERING": (
            "arm 2 lit while arm 1 did not, which no reading of #17 predicted: the "
            "out-of-window address on the home plate worked where the in-window "
            "address on the owning plate did not. Do not theorise from this run alone"
        ),
    }
    return (verdict, f"{reasons[verdict]} ({detail})")


def _render_order(arms: list[Arm]) -> list[Arm]:
    """Declaration order already brackets the run; stated so it cannot drift."""
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
        f"derived: completer plate at {geometry.completer_delta}; control "
        f"{DIRECTION_NAMES[geometry.control_direction]} at "
        f"{geometry.control_home_local}",
        file=sys.stderr,
    )
    for target in geometry.targets:
        print(
            f"  target {target.name:<2}: home local {target.home_local} == completer "
            f"local {target.completer_local}, goal rot {target.goal_rot}",
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

    # The two certified controls are byte-identical by design, so they dedup to
    # one share code -- which is correct and is what brackets the run. Every
    # other payload must be distinct, or upload dedup would collapse two arms
    # into one render and the probe would not measure what it claims.
    distinct = {a.payload_sha256 for a in arms if a.role != "certified_control"}
    non_control = [a for a in arms if a.role != "certified_control"]
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
            print(
                f"  {arm.label:<28} plates={2 if arm.two_plate else 1} "
                f"goal_plate={arm.goal_plate_index} local={arm.goal_local} "
                f"rot={arm.goal_rot} predicted={arm.predicted:<8} [{arm.role}]"
            )
            sha = (arm.payload_sha256 or "")[:12]
            print(f"      validator={arm.validator}  sha={sha}")
            print(f"      {arm.why}")
        print(f"\n{len(arms)} renders; nothing uploaded (--dry-run).")
        return 0

    ctx = None
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
            arm.code, arm.upload_attempts = upload_course_with_retry(
                payloads[i], on_retry=_note
            )
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
            print(f"  {arm.label:<28} -> {arm.validity or arm.render_error}", file=sys.stderr)

    verdict, reason = classify(arms)
    sidecar = args.output_dir / "results.json"
    sidecar.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "starter": {"y": STARTER_LOCAL.y, "x": STARTER_LOCAL.x},
                "starter_rot": STARTER_ROT,
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
