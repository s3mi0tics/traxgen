"""The four-plate campaign: bring `generate --board standard-square` up to the record's bar.

p2 rendered the course `generate_multi_plate()` emits -- share code
`H4OI26V7Q7` -- once, alone, and it lit the play button. One render is not a
`MEASURED_RUNS` row: the bar is a campaign bracketed by an active certified
control at both ends (`decisions.md` D027) with a control at the position under
test (D039). This is that campaign, four renders in one cold emulator session:

    certified_open   FLW4TMLP5V's geometry, one plate         predicted active
    local_control    the four-plate board, starter where the  predicted active
                     generator puts it, goal E on the
                     starter's own plate
    under_test       `generate_multi_plate()` byte for byte:  predicted active
                     goal SW, addressed on the plate at (3,-6)
    certified_close  the certified geometry again             predicted active

The local control is the cell both rival models call live at this starter
placement -- port-only (E is a starter port at rotation 0) and the conjunction
(E's neighbour is in-window on the home plate). So a dark local control means
the four-plate family does not render here, and the run aborts as
SETUP_SUSPECT rather than reporting anything about the arm under test.

The under-test arm is built by the generator itself, not a copy of its
placement: what gets recorded is what `generate` emits. Upload dedups by
content, so that arm must come back as `H4OI26V7Q7`; the sidecar records the
code it got and `classify` reports a mismatch rather than recording a different
course under that name.

Render loop and retry: `probe_plate_boundary.render_arm`, imported rather than
copied (plan item 16 is where these loops consolidate). The emulator lifecycle
is `scripts.emulator.session()`: kill, cold boot, render, kill in `finally`.

Run: `caffeinate -di uv run python -m scripts.probe_four_plate_control`
Plan only: `uv run python -m scripts.probe_four_plate_control --dry-run`

Path: traxgen/scripts/probe_four_plate_control.py
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
from traxgen.domain import Course
from traxgen.generator import generate_minimal, generate_multi_plate
from traxgen.graph import goal_rotation_for, predict_connection
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.layout import TilePlacement, build_course
from traxgen.plates import STANDARD_SQUARE
from traxgen.serializer import serialize_course
from traxgen.types import LayerKind, TileKind
from traxgen.uploader import UploadError, upload_course_with_retry
from traxgen.validator import validate_strict

EXPECTED_CODE = "H4OI26V7Q7"  # p2's single render of the generator's course
STARTER_LOCAL = HexVector(y=-4, x=0)  # where `generate_multi_plate` puts it
STARTER_ROT = 0
LOCAL_CONTROL_DIRECTION = 0  # E: live under every rival model at this starter
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent / "screenshots" / "four_plate_control"
)


@dataclass
class Arm:
    """One rendered course, with its expected verdict declared before the run.

    Same fields as the 2x2's `Arm` where they mean the same thing, so the
    sidecars read alike; `plates` replaces `two_plate` because this board has
    four.
    """

    role: str  # certified_control | local_control | under_test
    label: str
    plates: int
    goal_plate_index: int | None
    goal_local: tuple[int, int] | None
    goal_rot: int | None
    predicted: str
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


def local_control_course() -> Course:
    """The four-plate board, starter as generated, goal E on the starter's plate."""
    goal_local = STARTER_LOCAL.neighbor(LOCAL_CONTROL_DIRECTION)
    return build_course(
        plate_world_positions=tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE),
        tiles=(
            TilePlacement(
                kind=TileKind.STARTER,
                plate_index=0,
                local_pos=STARTER_LOCAL,
                hex_rotation=STARTER_ROT,
            ),
            TilePlacement(
                kind=TileKind.GOAL_RAIL,
                plate_index=0,
                local_pos=goal_local,
                hex_rotation=goal_rotation_for(LOCAL_CONTROL_DIRECTION),
            ),
        ),
        title="traxgen-four-plate-local-control",
    )


def build_arms() -> list[Arm]:
    """The four renders, in order, each with its verdict declared."""
    goal_local = STARTER_LOCAL.neighbor(LOCAL_CONTROL_DIRECTION)
    # The conjunction must call the control live, or it is not a control.
    assert predict_connection(
        STARTER_ROT,
        LOCAL_CONTROL_DIRECTION,
        goal_rotation_for(LOCAL_CONTROL_DIRECTION),
        layer_kind=LayerKind.BASE_LAYER_PIECE,
        starter_local_pos=STARTER_LOCAL,
        goal_plate_offset=None,
    )
    certified = "FLW4TMLP5V's geometry: proves the harness worked at this end of the run"
    return [
        Arm("certified_control", "certified_open", 1, None, None, None, "active", certified),
        Arm(
            "local_control",
            "local_control_E",
            len(STANDARD_SQUARE),
            0,
            (goal_local.y, goal_local.x),
            goal_rotation_for(LOCAL_CONTROL_DIRECTION),
            "active",
            "E on the starter's own plate at the generator's starter placement, on "
            "the four-plate board: port-only and the conjunction both call it live, "
            "so dark means the family does not render here (D039)",
        ),
        Arm(
            "under_test",
            "generated_standard_square",
            len(STANDARD_SQUARE),
            1,
            (-6, 5),
            5,
            "active",
            f"generate_multi_plate() byte for byte; p2 rendered it once as "
            f"{EXPECTED_CODE}, active",
        ),
        Arm("certified_control", "certified_close", 1, None, None, None, "active", certified),
    ]


def build_arm_course(arm: Arm) -> Course:
    if arm.role == "certified_control":
        return generate_minimal()
    if arm.role == "local_control":
        return local_control_course()
    if arm.role == "under_test":
        return generate_multi_plate()
    raise ValueError(f"unknown role {arm.role!r}")


def classify(arms: list[Arm]) -> tuple[str, str]:
    """The verdict, from conditions declared before any render.

    Harness and setup doubts override the arm under test (D027, D039).
    """
    controls = [a for a in arms if a.role == "certified_control"]
    if len(controls) != 2 or any(c.validity != "active" for c in controls):
        return (
            "HARNESS_SUSPECT",
            "a certified control did not render active, so nothing else in this run "
            "is a measurement",
        )
    (local,) = [a for a in arms if a.role == "local_control"]
    if local.validity != "active":
        return (
            "SETUP_SUSPECT",
            "the control at the position under test did not render active, so the "
            "four-plate family may not render here and the arm under test measures "
            "nothing",
        )
    (under,) = [a for a in arms if a.role == "under_test"]
    if under.code != EXPECTED_CODE:
        return (
            "WRONG_COURSE",
            f"the generator's course uploaded as {under.code}, not {EXPECTED_CODE}: "
            "the bytes changed since p2, so this run does not measure that render",
        )
    if under.validity == "active":
        return ("CONNECTED", "the generated cross-plate placement rendered active inside the bar")
    if under.validity == "inactive":
        return (
            "DISCONNECTED",
            "the generated cross-plate placement rendered dark with both control "
            "kinds active, contradicting p2's single render",
        )
    return ("INCOMPLETE", f"the arm under test produced no verdict: {under.render_error}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="plan only; nothing uploaded")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started = time.monotonic()
    arms = build_arms()

    payloads: list[bytes] = []
    for arm in arms:
        course = build_arm_course(arm)
        try:
            validate_strict(course, PRO_VERTICAL_STARTER_SET)
            arm.validator = "ok"
        except Exception as exc:  # recorded, not raised: the sidecar carries it
            arm.validator = f"{type(exc).__name__}: {exc}"
        binary = serialize_course(course)
        payloads.append(binary)
        arm.payload_sha256 = hashlib.sha256(binary).hexdigest()
        arm.payload_bytes = len(binary)

    for arm in arms:
        print(
            f"  {arm.label:<26} plates={arm.plates} goal_plate={arm.goal_plate_index} "
            f"local={arm.goal_local} rot={arm.goal_rot} predicted={arm.predicted} "
            f"validator={arm.validator} sha={(arm.payload_sha256 or '')[:12]}",
            file=sys.stderr,
        )
    if args.dry_run:
        print(f"{len(arms)} renders planned; nothing uploaded (--dry-run).")
        return 0

    for arm, binary in zip(arms, payloads, strict=True):
        try:
            arm.code, arm.upload_attempts = upload_course_with_retry(binary)
        except UploadError as exc:
            arm.upload_error = f"{type(exc).__name__}: {exc}"
        print(f"  {arm.label:<26} code {arm.code or arm.upload_error}", file=sys.stderr)

    from scripts.emulator import EmulatorLifecycleError, session

    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with session(out=lambda line: print(line, file=sys.stderr)) as ctx:
            print(f"run started {datetime.now(UTC):%H:%M:%SZ}", file=sys.stderr)
            for arm in arms:
                if arm.code is None:
                    continue
                render_arm(ctx, arm, args.output_dir)
                print(f"  {arm.label:<26} -> {arm.validity or arm.render_error}", file=sys.stderr)
    except EmulatorLifecycleError as exc:
        print(f"emulator lifecycle failed: {exc}", file=sys.stderr)

    verdict, reason = classify(arms)
    sidecar = args.output_dir / "results.json"
    sidecar.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "starter": {"y": STARTER_LOCAL.y, "x": STARTER_LOCAL.x},
                "starter_rot": STARTER_ROT,
                "plate_world_positions": [list(p) for p in STANDARD_SQUARE],
                "expected_code": EXPECTED_CODE,
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
