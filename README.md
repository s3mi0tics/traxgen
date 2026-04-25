# traxgen

Procedural generator for [GraviTrax](https://www.ravensburger.us/products/gravitrax) marble run courses.

> **Not affiliated with Ravensburger.** "GraviTrax" is a Ravensburger trademark.
> This project generates binary `.course` files compatible with the official GraviTrax app using the format reverse-engineered by [lfrancke/murmelbahn](https://github.com/lfrancke/murmelbahn).

## Status

Early development. Parser, serializer, validator, and minimal generator
(M5.b) are complete; the uploader (M6.a) is complete and verified
against the live endpoint. `upload_course()` POSTs a `.course` binary
to Ravensburger's share-code endpoint and returns the 10-character
code. M6.b (end-to-end round-trip verification) is in progress: the
pipeline renders courses in the real app, but rails don't yet render
alongside tiles, and the app writes a newer schema version (7) than
our parser knows about (4). M6.c will install the GraviTrax Android
app in an emulator and automate the render-and-verify loop via `adb`
— the manual loop of typing share codes into a physical iPhone proved
too slow and too error-prone to drive generator iteration.

Phase 1 goal: generate a topologically valid single-track course using
the PRO Vertical Starter-Set (26832) that loads in the GraviTrax app
via its share-code system.

See [`docs/PLAN.md`](docs/PLAN.md) for the roadmap including race mode and perpetual mode (Phase 3).

## Quick start

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/s3mi0tics/traxgen.git
cd traxgen
uv sync

# Generate the M5.b minimal course (2 tiles + 1 rail, writes 221 bytes).
uv run python -m scripts.dump_minimal_course
# wrote 221 bytes to /tmp/traxgen-minimal.course

# Upload a .course binary and print the assigned share code.
uv run python -m scripts.upload_course tests/fixtures/GDZJZA3J3T.course
# uploading GDZJZA3J3T.course (6342 bytes) to https://gravitrax.link.ravensburger.com/api/upload/
# share code: GDZJZA3J3T
# GDZJZA3J3T
```

The unified `traxgen generate` CLI is not wired up yet — `dump_minimal_course`
is a thin wrapper around the M5.b-minimal generator and `upload_course`
is a thin wrapper around `traxgen.uploader.upload_course`.

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
