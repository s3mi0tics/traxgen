"""Render the generator's four-plate course, bracketed so the result can become a row.

`python -m traxgen generate --set vertical-starter --board standard-square`
emits one cross-plate placement chosen by `predict_connection`. A lone render of
it is one data point with no control beside it, which fails the bar the comment
above `graph.MEASURED_RUNS` sets. This campaign renders it inside that bar:

    certified_open    generate_minimal(), KN6F459ZR3 -- the harness works (D027)
    local_control     same four plates and starter, goal on the starter's own
                      plate in a direction every rival model calls live (D039)
    generated         exactly generate_multi_plate() with its defaults
    certified_close   generate_minimal() again -- the harness still works (D027)

One emulator session for the whole run (`scripts.emulator.session`), and every
arm renders with `reset_first=True`, as `render_course.py --fresh` does.
Placements are derived from the generator and the model, never typed.

The render loop duplicates `probe_plate_boundary.render_arm` on purpose. The
shared harness is plan item 16, and extracting it inside an experiment build is
the s25 defect pattern.

Run: `uv run python -m scripts.probe_generated_placement --dry-run`

Path: traxgen/scripts/probe_generated_placement.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from traxgen.android import (
    AdbContext,
    RefusedScreenError,
    read_app_version,
    render_course,
)
from traxgen.domain import Course
from traxgen.generator import (
    _cross_plate_placements,
    generate_minimal,
    generate_multi_plate,
)
from traxgen.graph import (
    goal_rotation_for,
    predicted_live_directions,
    starter_world_ports,
)
from traxgen.hex import DIRECTION_NAMES, HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.layout import TilePlacement, build_course, owning_plate
from traxgen.plates import STANDARD_SQUARE, is_buildable_on_plate
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind, TileKind
from traxgen.uploader import UploadError, upload_course_with_retry
from traxgen.validator import validate_strict

if TYPE_CHECKING:
    from collections.abc import Callable

PLATE = LayerKind.BASE_LAYER_PIECE
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "screenshots" / "generated_placement"

# Matches `generate_multi_plate`, so the generated arm is its bytes exactly and
# the local control differs from it only in where the goal stands.
COURSE_TITLE = "traxgen-multi-plate"

# Same reasoning as `probe_plate_boundary.RENDER_ATTEMPTS`: a refused screen is
# an intermittent race, and one that repeats is a finding, not bad luck.
RENDER_ATTEMPTS = 2


class Role(StrEnum):
    CERTIFIED = "certified_control"
    LOCAL_CONTROL = "local_control"
    GENERATED = "generated"


class Verdict(StrEnum):
    HARNESS_SUSPECT = "HARNESS_SUSPECT"
    SETUP_SUSPECT = "SETUP_SUSPECT"
    INCOMPLETE = "INCOMPLETE"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


MEASURED_VERDICTS = frozenset({Verdict.CONNECTED, Verdict.DISCONNECTED})


@dataclass(frozen=True)
class GoalSite:
    """Where one arm's GOAL_RAIL stands, relative to the starter."""

    direction: int
    goal_plate_index: int
    goal_local: tuple[int, int]
    goal_rot: int
    goal_plate_offset: tuple[int, int] | None  # None: the starter's own plate


@dataclass(frozen=True)
class Geometry:
    """Everything the two non-certified arms need to be rebuilt, and nothing else."""

    plate_offsets: tuple[tuple[int, int], ...]
    starter_local: tuple[int, int]
    starter_rot: int
    generated: GoalSite
    local_control: GoalSite


def derive_geometry(
    plate_offsets: tuple[tuple[int, int], ...] = STANDARD_SQUARE,
) -> Geometry:
    """The generator's own first placement, plus a control cell every rival model lights.

    The local control must be live under the port model alone and under the
    conjunction with the goal on the starter's own plate. A direction only one
    of them lights would make a dark control ambiguous between "the four-plate
    family does not render" and "that model was wrong", which is what D039
    exists to rule out.
    """
    plates = tuple(HexVector(y=y, x=x) for y, x in plate_offsets)
    chosen = next(_cross_plate_placements(plates))
    starter = chosen.starter_local

    live_everywhere = starter_world_ports(chosen.starter_rot) & predicted_live_directions(
        chosen.starter_rot,
        layer_kind=PLATE,
        starter_local_pos=starter,
        goal_plate_offset=None,
    )
    home_world = plates[0] + starter
    candidates = []
    for direction in sorted(live_everywhere):
        owner = owning_plate(plates, home_world.neighbor(direction))
        if owner is None or owner[0] != 0 or not is_buildable_on_plate(PLATE, owner[1]):
            continue
        candidates.append((direction, owner[1]))
    if not candidates:
        raise ValueError(
            f"no direction from starter {starter} rot {chosen.starter_rot} is live under "
            "every rival model on the starter's own plate, so this run has no local control"
        )
    control_direction, control_local = candidates[0]

    return Geometry(
        plate_offsets=tuple(plate_offsets),
        starter_local=(starter.y, starter.x),
        starter_rot=chosen.starter_rot,
        generated=GoalSite(
            direction=chosen.direction,
            goal_plate_index=chosen.goal_plate_index,
            goal_local=(chosen.goal_local.y, chosen.goal_local.x),
            goal_rot=chosen.goal_rot,
            goal_plate_offset=chosen.goal_plate_offset,
        ),
        local_control=GoalSite(
            direction=control_direction,
            goal_plate_index=0,
            goal_local=(control_local.y, control_local.x),
            goal_rot=goal_rotation_for(control_direction),
            goal_plate_offset=None,
        ),
    )


@dataclass
class Arm:
    """One render, with its expected verdict declared before the run."""

    role: Role
    label: str
    predicted: str  # 'active' | 'inactive'
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


def build_arms(geometry: Geometry) -> list[Arm]:
    """The four renders, in render order."""
    generated = DIRECTION_NAMES[geometry.generated.direction]
    control = DIRECTION_NAMES[geometry.local_control.direction]
    return [
        Arm(
            role=Role.CERTIFIED,
            label="certified_open",
            predicted="active",
            why="generate_minimal() (KN6F459ZR3): proves the harness worked at render 1",
        ),
        Arm(
            role=Role.LOCAL_CONTROL,
            label="local_control",
            predicted="active",
            why=(
                f"{control} on the starter's own plate, live under the port model and the "
                "conjunction alike: proves the four-plate family renders at all"
            ),
        ),
        Arm(
            role=Role.GENERATED,
            label="generated",
            predicted="active",
            why=(
                f"generate_multi_plate(): {generated} onto plate "
                f"{geometry.generated.goal_plate_offset}, live by predict_connection"
            ),
        ),
        Arm(
            role=Role.CERTIFIED,
            label="certified_close",
            predicted="active",
            why="the closing bracket: proves the harness still worked at the last render",
        ),
    ]


def build_arm_course(role: Role, geometry: Geometry) -> Course:
    """Rebuild one arm's course from the geometry alone, so a sidecar can be hash-checked."""
    match role:
        case Role.CERTIFIED:
            return generate_minimal()
        case Role.GENERATED:
            site = geometry.generated
        case Role.LOCAL_CONTROL:
            site = geometry.local_control
    return build_course(
        plate_world_positions=tuple(HexVector(y=y, x=x) for y, x in geometry.plate_offsets),
        tiles=(
            TilePlacement(
                TileKind.STARTER,
                0,
                HexVector(y=geometry.starter_local[0], x=geometry.starter_local[1]),
                geometry.starter_rot,
            ),
            TilePlacement(
                TileKind.GOAL_RAIL,
                site.goal_plate_index,
                HexVector(y=site.goal_local[0], x=site.goal_local[1]),
                site.goal_rot,
            ),
        ),
        title=COURSE_TITLE,
    )


def classify(arms: list[Arm]) -> tuple[Verdict, str]:
    """The verdict, from rules declared before any render (D027, D039).

    Harness doubt outranks setup doubt, which outranks the data: a run whose
    instrument is in question has no finding to report.
    """
    by_role: dict[Role, list[Arm]] = {}
    for arm in arms:
        by_role.setdefault(arm.role, []).append(arm)
    certified = by_role.get(Role.CERTIFIED, [])
    (local,) = by_role[Role.LOCAL_CONTROL]
    (generated,) = by_role[Role.GENERATED]

    if len(certified) != 2 or any(arm.validity != "active" for arm in certified):
        return (
            Verdict.HARNESS_SUSPECT,
            "a certified control did not render active, so nothing else in this run is "
            "a measurement whatever it says",
        )
    if local.validity == "inactive":
        return (
            Verdict.SETUP_SUSPECT,
            "the local control rendered dark while both brackets were active, so the "
            "four-plate family may not render at all and the generated arm measures nothing",
        )
    if local.validity is None or generated.validity is None:
        return (
            Verdict.INCOMPLETE,
            "an arm produced no verdict (upload or render failed); see its error field",
        )
    if generated.validity == "active":
        return (
            Verdict.CONNECTED,
            "the generated placement rendered active inside active brackets with an "
            "active local control",
        )
    return (
        Verdict.DISCONNECTED,
        "the generated placement rendered dark while both brackets and the local "
        "control were active: predict_connection is refuted here",
    )


def render_campaign(arms: list[Arm], render: Callable[[Arm], None]) -> None:
    """Render every uploaded arm in order, skipping the generated arm after a dark local control.

    The closing bracket still renders after that abort: it is what tells a
    dark local control (SETUP_SUSPECT) from a harness that broke mid-run.
    """
    aborted = False
    for arm in arms:
        if arm.code is None:
            continue
        if arm.role is Role.GENERATED and aborted:
            arm.render_error = "skipped: the local control rendered dark (D039)"
            continue
        render(arm)
        if arm.role is Role.LOCAL_CONTROL and arm.validity == "inactive":
            aborted = True


def render_arm(ctx: AdbContext, arm: Arm, output_dir: Path) -> None:
    """Render one arm from a fresh app reset, retrying once on a known dead screen."""
    for attempt in range(1, RENDER_ATTEMPTS + 1):
        arm.render_attempts = attempt
        try:
            result = render_course(
                arm.code or "",
                ctx=ctx,
                screenshot_dir=output_dir,
                screenshot_name=f"{arm.label}_try{attempt}",
                detect_validity=True,
                reset_first=True,
                on_menu=lambda arrival: print(f"  {arrival.line()}", file=sys.stderr),
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


def _git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def _prepare_payloads(arms: list[Arm], geometry: Geometry) -> dict[str, bytes]:
    """Build, validate and hash every arm. Raises if the run would not measure what it claims."""
    payloads: dict[str, bytes] = {}
    for arm in arms:
        course = build_arm_course(arm.role, geometry)
        try:
            validate_strict(course, PRO_VERTICAL_STARTER_SET)
            arm.validator = "ok"
        except Exception as exc:  # recorded, not fatal: the render is the oracle
            arm.validator = f"{type(exc).__name__}: {exc}"
        binary = serialize_course(course)
        payloads[arm.label] = binary
        arm.payload_sha256 = hashlib.sha256(binary).hexdigest()
        arm.payload_bytes = len(binary)

    if payloads["generated"] != serialize_course(generate_multi_plate()):
        raise ValueError(
            "the generated arm is not generate_multi_plate()'s output, so a render of it "
            "would not be a render of what `generate` emits"
        )
    # Upload dedup would collapse identical payloads into one share code, and so
    # one render. The two brackets are meant to be identical; nothing else is.
    if payloads["local_control"] in (payloads["generated"], payloads["certified_open"]):
        raise ValueError("the local control's payload duplicates another arm's")
    return payloads


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="plan only; nothing uploaded")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started = time.monotonic()
    geometry = derive_geometry()
    arms = build_arms(geometry)
    payloads = _prepare_payloads(arms, geometry)

    if args.dry_run:
        print(json.dumps(asdict(geometry), indent=2))
        for arm in arms:
            print(
                f"  {arm.label:<16} predicted={arm.predicted:<8} validator={arm.validator} "
                f"bytes={arm.payload_bytes} sha={(arm.payload_sha256 or '')[:12]}"
            )
        print(f"\n{len(arms)} renders; nothing uploaded (--dry-run).")
        return 0

    for arm in arms:

        def _note(attempt: int, exc: UploadError, delay: float, label: str = arm.label) -> None:
            print(
                f"  {label}: upload attempt {attempt} failed ({type(exc).__name__}); "
                f"retrying in {delay:.0f}s",
                file=sys.stderr,
            )

        try:
            arm.code, arm.upload_attempts = upload_course_with_retry(
                payloads[arm.label], on_retry=_note
            )
        except UploadError as exc:
            arm.upload_error = f"{type(exc).__name__}: {exc}"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    app_version: str | None = None
    lifecycle_error: str | None = None
    # Imported here so --dry-run and the offline tests never load the lifecycle.
    from scripts.emulator import EmulatorLifecycleError, session

    try:
        with session(out=lambda line: print(line, file=sys.stderr)) as ctx:
            app_version = read_app_version(ctx)

            def _render(arm: Arm) -> None:
                render_arm(ctx, arm, args.output_dir)
                print(f"  {arm.label:<16} -> {arm.validity or arm.render_error}", file=sys.stderr)

            render_campaign(arms, _render)
    except EmulatorLifecycleError as exc:
        lifecycle_error = f"{type(exc).__name__}: {exc}"
        print(f"emulator lifecycle failed: {exc}", file=sys.stderr)

    verdict, reason = classify(arms)
    if lifecycle_error is not None:
        reason = f"{reason} [{lifecycle_error}]"
    sidecar = args.output_dir / "results.json"
    sidecar.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "head": _git_head(),
                "app_version": app_version,
                "geometry": asdict(geometry),
                "verdict": verdict,
                "reason": reason,
                "arms": [asdict(a) for a in arms],
            },
            indent=2,
        )
    )
    print(f"\nverdict: {verdict}\n  {reason}\n  sidecar: {sidecar}")
    return 0 if verdict in MEASURED_VERDICTS else 1


if __name__ == "__main__":
    raise SystemExit(main())
