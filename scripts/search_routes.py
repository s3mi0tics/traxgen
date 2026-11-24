"""Search for courses the graph checker calls VALID, grown outward from a launch pad (s52-t18).

    uv run python -m scripts.search_routes                 # count, and print the picks
    uv run python -m scripts.search_routes --upload        # also upload the picks

vision.md's "Generation": the same graph, searched outward from the starter --
place a piece whose way in matches the open exit, back up at dead ends. Pieces
are the ones `track_graph` has measured rules for and Colby's set holds: CURVE
(tracks 0-2, 3-4), CROSS (1-4, 2-5), and a GOAL_RAIL to end. Standard square,
launch pad at rotation 0, every tile buildable and off the toolbar so a render
can see it. Each candidate is kept only if `check_course` says VALID and
`validate` reports no ERROR against PRO_VERTICAL_STARTER_SET; the checker's
verdict is the prediction its first render tests.

Output: screenshots/ring_board/routes.json -- the picks' tiles, verdicts and codes.

Path: traxgen/scripts/search_routes.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass

from scripts.probe_two_marbles import placements
from scripts.ring_board import OUT_DIR
from traxgen.domain import Course
from traxgen.graph import goal_rotation_for
from traxgen.hex import HexVector
from traxgen.inventory import PRO_VERTICAL_STARTER_SET
from traxgen.layout import build_course
from traxgen.plates import STANDARD_SQUARE
from traxgen.ring_board import is_buildable, under_toolbar
from traxgen.serializer import serialize_course
from traxgen.track_graph import CROSS_TRACKS, CURVE_TRACKS, TrackStatus, check_course
from traxgen.types import TileKind
from traxgen.validator import Severity, validate

PLATES = tuple(HexVector(y=y, x=x) for y, x in STANDARD_SQUARE)
STARTER_PORTS = (0, 2, 4)  # at rotation 0 (#15)
TRACKS = {TileKind.CURVE: CURVE_TRACKS, TileKind.CROSS: CROSS_TRACKS}

Tile = tuple[TileKind, HexVector, int]


@dataclass(frozen=True)
class Route:
    tiles: tuple[Tile, ...]

    @property
    def middle(self) -> tuple[Tile, ...]:
        return self.tiles[1:-1]

    def kinds(self) -> tuple[str, ...]:
        return tuple(k.name for k, _, _ in self.middle)


def usable(cell: HexVector) -> bool:
    return is_buildable(PLATES, cell) and not under_toolbar(cell)


def steps(kind: TileKind, travel: int) -> Iterator[tuple[int, int]]:
    """(rotation, new travel) per rotation of `kind` that takes in a marble travelling `travel`.

    The marble enters by world side `(travel + 3) % 6`, piece side that minus
    the rotation; it leaves by the track's other end, turned back to world. A
    CROSS's two tracks are both straight, so one rotation per way through.
    """
    seen: set[int] = set()
    for rotation in range(6):
        side = (travel + 3 - rotation) % 6
        out = TRACKS[kind].get(side)
        if out is None:
            continue
        leave = (out + rotation) % 6
        if kind is TileKind.CROSS and leave in seen:
            continue
        seen.add(leave)
        yield rotation, leave


def grow(pad: HexVector, port: int, max_middle: int) -> Iterator[Route]:
    """Every route from `pad` out of `port` with up to `max_middle` pieces before the goal."""
    start: Tile = (TileKind.STARTER, pad, 0)

    def walk(
        cell: HexVector, travel: int, tiles: list[Tile], used: set[HexVector]
    ) -> Iterator[Route]:
        nxt = cell.neighbor(travel)
        if nxt in used or not usable(nxt):
            return
        yield Route((*tiles, (TileKind.GOAL_RAIL, nxt, goal_rotation_for(travel))))
        if len(tiles) - 1 >= max_middle:
            return
        for kind in (TileKind.CURVE, TileKind.CROSS):
            for rotation, leave in steps(kind, travel):
                yield from walk(nxt, leave, [*tiles, (kind, nxt, rotation)], used | {nxt})

    yield from walk(pad, port, [start], {pad})


def course_of(route: Route) -> Course:
    return build_course(
        plate_world_positions=PLATES,
        tiles=placements(PLATES, list(route.tiles)),
        title="traxgen-route",
    )


def is_valid(route: Route) -> bool:
    course = course_of(route)
    if check_course(course).status is not TrackStatus.VALID:
        return False
    return not any(v.severity is Severity.ERROR for v in validate(course, PRO_VERTICAL_STARTER_SET))


def search(max_middle: int) -> Iterator[Route]:
    pads = sorted(
        {p + HexVector(y=y, x=x) for p in PLATES for y in range(-6, 1) for x in range(6)},
        key=lambda c: (c.y, c.x),
    )
    for pad in pads:
        if not usable(pad):
            continue
        for port in STARTER_PORTS:
            for route in grow(pad, port, max_middle):
                if is_valid(route):
                    yield route


def uses_track(route: Route, kind: TileKind, sides: frozenset[int]) -> bool:
    """True if some `kind` in the route is ridden on the track joining `sides` (piece frame)."""
    tiles = route.tiles
    for i in range(1, len(tiles) - 1):
        k, cell, rotation = tiles[i]
        if k is not kind:
            continue
        prev = tiles[i - 1][1]
        travel = next(d for d in range(6) if prev.neighbor(d) == cell)
        if (travel + 3 - rotation) % 6 in sides:
            return True
    return False


def picks(routes: list[Route]) -> dict[str, Route]:
    """A few routes that between them use both curve tracks and the cross, shortest first."""
    by_len = sorted(routes, key=lambda r: (len(r.tiles), r.tiles[0][1].y, r.tiles[0][1].x))
    gentle = frozenset({0, 2})
    sharp = frozenset({3, 4})
    wanted = {
        "gentle_curve": lambda r: r.kinds() == ("CURVE",) and uses_track(r, TileKind.CURVE, gentle),
        "sharp_curve": lambda r: r.kinds() == ("CURVE",) and uses_track(r, TileKind.CURVE, sharp),
        "cross": lambda r: r.kinds() == ("CROSS",),
        "curve_cross_curve": lambda r: r.kinds() == ("CURVE", "CROSS", "CURVE"),
        "longest": lambda r: (
            len(r.middle) == max(len(x.middle) for x in routes)
            and "CROSS" in r.kinds()
            and uses_track(r, TileKind.CURVE, gentle)
            and uses_track(r, TileKind.CURVE, sharp)
        ),
    }
    out: dict[str, Route] = {}
    for name, pred in wanted.items():
        found = next((r for r in by_len if pred(r)), None)
        if found is not None:
            out[name] = found
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-middle", type=int, default=5, help="pieces between pad and goal")
    parser.add_argument("--upload", action="store_true", help="upload the picks")
    args = parser.parse_args(argv)

    routes = list(search(args.max_middle))
    lengths: dict[int, int] = {}
    for r in routes:
        lengths[len(r.middle)] = lengths.get(len(r.middle), 0) + 1
    by_len = dict(sorted(lengths.items()))
    print(f"VALID routes: {len(routes)}; by pieces between pad and goal: {by_len}")
    rows = []
    for name, route in picks(routes).items():
        data = serialize_course(course_of(route))
        row: dict[str, object] = {
            "name": name,
            "kinds": list(route.kinds()),
            "tiles": [[k.name, [c.y, c.x], r] for k, c, r in route.tiles],
            "checker": "VALID",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if args.upload:
            from traxgen.uploader import upload_course_with_retry

            row["code"], _attempts = upload_course_with_retry(data)
        rows.append(row)
        print(name, row["kinds"], row["tiles"], row.get("code"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "routes.json"
    out.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
