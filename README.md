# traxgen

Procedural generator for [GraviTrax](https://www.ravensburger.us/products/gravitrax) marble run courses.

> **Not affiliated with Ravensburger.** "GraviTrax" is a Ravensburger trademark.
> This project generates binary `.course` files compatible with the official GraviTrax app using the format reverse-engineered by [lfrancke/murmelbahn](https://github.com/lfrancke/murmelbahn).

## Status

Early development. Parser, serializer, and validator are complete; the
minimal generator (M5.b) produces a 2-tile / 1-rail course that passes
every validation rule and round-trips byte-perfect through the
serializer. Next: verify the generated file opens in the real GraviTrax
app (M6).

Phase 1 goal: generate a topologically valid single-track course using
the PRO Vertical Starter-Set (26832) that opens in the GraviTrax app.

See [`docs/PLAN.md`](docs/PLAN.md) for the roadmap including race mode and perpetual mode (Phase 3).

## Quick start

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/s3mi0tics/traxgen.git
cd traxgen
uv sync
uv run python -m scripts.dump_minimal_course
# wrote 221 bytes to /tmp/traxgen-minimal.course
```

The unified `traxgen generate` CLI is not wired up yet — `dump_minimal_course`
is a thin wrapper around the M5.b-minimal generator that writes to disk
for app sideloading.

## Development

```bash
uv sync                           # install deps + dev deps
uv run pytest                     # run tests (skips network tests by default)
uv run pytest -m network          # run only tests that hit external APIs
uv run pytest -m ""               # run everything
uv run ruff check .               # lint
uv run mypy traxgen               # type-check
```

## Project layout

```
traxgen/
├── traxgen/              # main package
├── tests/                # pytest suite
├── scripts/              # one-off utilities (fixture fetchers, probes, etc.)
└── docs/
    ├── PLAN.md           # roadmap + design decisions
    └── refs/             # reference material (rail specs, set contents, etc.)
```

## License

[Apache-2.0](LICENSE)

## Acknowledgements

- [lfrancke/murmelbahn](https://github.com/lfrancke/murmelbahn) (Apache-2.0) for reverse-engineering the course binary format.
- [GraviSheet](https://docs.google.com/spreadsheets/d/1T-hLIBz05q4QMlt7xQ63Y1SrnG_3HYWchF_nLXvYkJg/template/preview) by Chris Fuchser for comprehensive set inventories.
- [Red Blob Games](https://www.redblobgames.com/grids/hexagons/) for the canonical hex coordinate reference.
