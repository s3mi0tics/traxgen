"""Run the finish check over every live cell in the rendered record (s43-t2).

`MEASURED_RUNS` holds placement claims: each row's live directions are cells
whose play button rendered white. Since s40 that means placed legally, not
finished (#57). This rebuilds one course per live cell, checks the build
reproduces the recorded cell (`start_goal_status` must say CONNECTED, i.e. the
record covers it), uploads it, and renders it once by link with the finish
check (D093), in one cold emulator session. The Phase 1 course `KN6F459ZR3` is
rendered first and last as the control; if either is not active and finished,
the run says nothing about the cells.

    uv run python -m scripts.finish_record --build-only   # build + check, no upload or render
    uv run python -m scripts.finish_record                # build, upload, render

Output: screenshots/finish_record/results.json, one entry per cell, written
after every cell so a run that dies keeps what it measured.

Path: traxgen/scripts/finish_record.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from traxgen.android import DEFAULT_SCREENSHOT_DIR, AdbContext, read_app_version, render_course
from traxgen.domain import Course
from traxgen.graph import (
    MEASURED_RUNS,
    ConnectionStatus,
    MeasuredRun,
    goal_rotation_for,
    start_goal_status,
)
from traxgen.hex import HEX_DIRECTIONS, HexVector
from traxgen.layout import TilePlacement, build_course
from traxgen.serializer import serialize_course

OUT = DEFAULT_SCREENSHOT_DIR / "finish_record"
CONTROL = "KN6F459ZR3"


@dataclass(frozen=True)
class Cell:
    """One live cell of one recorded row: the starter, and the goal in one direction."""

    row: int
    run: MeasuredRun
    direction: int

    @property
    def label(self) -> str:
        return f"r{self.row:02d}-d{self.direction}"


def live_cells(runs: tuple[MeasuredRun, ...] = MEASURED_RUNS) -> list[Cell]:
    """Every (row, live direction) in the record, in record order."""
    return [Cell(i, run, d) for i, run in enumerate(runs) for d in sorted(run.live_directions)]


def build_cell_course(cell: Cell) -> Course:
    """The course a recorded cell describes: starter and goal at the connecting rotation."""
    run = cell.run
    plates = [HexVector(y=y, x=x) for y, x in run.plate_offsets]
    sy, sx = run.starter_local_pos
    starter_world = plates[0] + HexVector(y=sy, x=sx)
    dy, dx = HEX_DIRECTIONS[cell.direction]
    goal_world = starter_world + HexVector(y=dy, x=dx)
    offset = run.goal_plate_offset
    goal_plate = 0 if offset is None else run.plate_offsets.index(offset)
    goal_local = goal_world - plates[goal_plate]
    return build_course(
        plate_world_positions=plates,
        tiles=(
            TilePlacement(run.starter_kind, 0, HexVector(y=sy, x=sx), run.starter_rot),
            TilePlacement(run.goal_kind, goal_plate, goal_local, goal_rotation_for(cell.direction)),
        ),
        title=f"traxgen-finish {cell.label}",
    )


def checked_bytes(cell: Cell) -> bytes:
    """The cell's course bytes, refused unless the record says this exact course is connected."""
    course = build_cell_course(cell)
    status = start_goal_status(course)
    if status is not ConnectionStatus.CONNECTED:
        raise ValueError(f"{cell.label}: rebuilt course reads {status} from the record")
    return serialize_course(course)


def describe(cell: Cell, payload: bytes) -> dict[str, object]:
    run = cell.run
    return {
        "row": cell.row,
        "provenance": run.provenance,
        "starter_local_pos": list(run.starter_local_pos),
        "starter_rot": run.starter_rot,
        "plate_offsets": [list(p) for p in run.plate_offsets],
        "goal_plate_offset": None if run.goal_plate_offset is None else list(run.goal_plate_offset),
        "direction": cell.direction,
        "goal_rotation": goal_rotation_for(cell.direction),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def render_one(ctx: AdbContext, code: str, folder: Path) -> dict[str, object]:
    result = render_course(
        code, ctx=ctx, screenshot_dir=folder, screenshot_name=code,
        by_link=True, detect_validity=True, detect_finish=True, reset_first=True,
        on_menu=lambda a: print(a.line(), file=sys.stderr),
    )
    finish = result.finish
    assert finish is not None
    return {
        "validity": result.validity,
        "finish": finish.status.value,
        "finish_peak": finish.peak_new_white,
        "finish_frames": finish.frames,
        "finish_reason": finish.reason,
    }


def main(argv: list[str]) -> int:
    cells = live_cells()
    payloads = {c.label: checked_bytes(c) for c in cells}  # every build checked before any upload
    print(f"{len(cells)} live cells, every rebuilt course CONNECTED in the record", file=sys.stderr)
    if "--build-only" in argv:
        return 0

    from scripts.emulator import session
    from scripts.probe_finish_frames import keep_evidence
    from traxgen.uploader import upload_course_with_retry

    OUT.mkdir(parents=True, exist_ok=True)
    out_file = OUT / "results.json"
    results: dict[str, dict[str, object]] = {}
    for c in cells:
        code, attempts = upload_course_with_retry(payloads[c.label])
        results[c.label] = {**describe(c, payloads[c.label]), "code": code,
                            "upload_attempts": attempts}
        print(f"{c.label}: uploaded as {code}", file=sys.stderr)

    results = {"control_first": {"code": CONTROL}, **results, "control_last": {"code": CONTROL}}
    with session(out=lambda line: print(line, file=sys.stderr)) as ctx:
        version = read_app_version(ctx)
        for label, entry in results.items():
            entry["app_version"] = version
            for attempt in (1, 2):  # a second try in the same boot (#21)
                try:
                    entry.update(attempt=attempt, **render_one(ctx, str(entry["code"]), OUT))
                    entry.pop("error", None)
                    break
                except Exception as exc:  # one bad cell must not cost the others
                    error = f"{type(exc).__name__}: {exc}"
                    reason = f"{label} attempt {attempt}: {error}"
                    entry.update(attempt=attempt, error=error, evidence=keep_evidence(ctx, reason))
            keys = ("code", "validity", "finish", "finish_peak", "error")
            print(f"{label}: {json.dumps({k: entry.get(k) for k in keys})}", file=sys.stderr)
            out_file.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    return 0 if all("error" not in e for e in results.values()) else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
