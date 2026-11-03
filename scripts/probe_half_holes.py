"""Probe: does a goal on any uncompleted half-hole miss, or only the recorded placement? (#26, s50)

    uv run python -m scripts.probe_half_holes --build-only   # build and check, no upload
    uv run python -m scripts.probe_half_holes                # build, upload, print the codes

The record's 3 misses (s43, `MEASURED_FINISHES`) all put the goal on the
half-hole (0,1) of a lone plate, reached from the launch pad at (0,0)
travelling East, so "goals on a half-hole miss" and "that one placement
misses" can't be told apart. Here each course is a lone plate with one launch
pad and one goal rail on a half-hole: the other two half-holes from the West
as before, every other side a buildable launch pad can reach, and the original
placement as a control.

Output: screenshots/ring_board/half_holes.json -- each course's cells, checker verdict and code.

Path: traxgen/scripts/probe_half_holes.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass

from scripts.ring_board import OUT_DIR
from traxgen.domain import Course
from traxgen.graph import goal_rotation_for
from traxgen.hex import HexVector
from traxgen.layout import TilePlacement, build_course
from traxgen.serializer import serialize_course
from traxgen.track_graph import check_course
from traxgen.types import TileKind

STARTER_PORTS = (0, 2, 4)  # at rotation 0 (#15)
LONE_PLATE = (HexVector(y=0, x=0),)


@dataclass(frozen=True)
class HalfHoleCase:
    name: str
    goal: tuple[int, int]  # a half-hole of the lone plate
    travel: int  # the marble's direction of travel into the goal

    @property
    def goal_cell(self) -> HexVector:
        return HexVector(y=self.goal[0], x=self.goal[1])

    @property
    def pad_cell(self) -> HexVector:
        return self.goal_cell.neighbor((self.travel + 3) % 6)

    @property
    def pad_rotation(self) -> int:
        """The lowest launch pad rotation with a port facing the goal."""
        return min(r for r in range(6) if any((p + r) % 6 == self.travel for p in STARTER_PORTS))


CASES = (
    HalfHoleCase("control_0_1_E", (0, 1), 0),
    HalfHoleCase("hh_m1_3_E", (-1, 3), 0),
    HalfHoleCase("hh_m2_5_E", (-2, 5), 0),
    HalfHoleCase("hh_m2_5_SE", (-2, 5), 5),
    HalfHoleCase("hh_m1_3_SW", (-1, 3), 4),
    HalfHoleCase("hh_m1_3_SE", (-1, 3), 5),
    HalfHoleCase("hh_0_1_SW", (0, 1), 4),
    HalfHoleCase("hh_0_1_SE", (0, 1), 5),
)


def course_for(case: HalfHoleCase) -> Course:
    """A lone plate holding the case's launch pad and goal rail."""
    tiles = [
        TilePlacement(TileKind.STARTER, 0, case.pad_cell, case.pad_rotation),
        TilePlacement(TileKind.GOAL_RAIL, 0, case.goal_cell, goal_rotation_for(case.travel)),
    ]
    return build_course(plate_world_positions=LONE_PLATE, tiles=tiles, title=f"traxgen-{case.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-only", action="store_true", help="no upload")
    args = parser.parse_args(argv)

    rows = []
    for case in CASES:
        course = course_for(case)
        data = serialize_course(course)
        verdict = check_course(course)
        row: dict[str, object] = {
            "name": case.name,
            "goal": list(case.goal),
            "travel": case.travel,
            "pad": [case.pad_cell.y, case.pad_cell.x],
            "pad_rotation": case.pad_rotation,
            "goal_rotation": goal_rotation_for(case.travel),
            "checker": verdict.status.name,
            "reason": verdict.reason,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if not args.build_only:
            from traxgen.uploader import upload_course_with_retry

            row["code"], _attempts = upload_course_with_retry(data)
        rows.append(row)
        print(" ".join(f"{k}={v}" for k, v in row.items() if k != "sha256"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "half_holes.json"
    out.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
