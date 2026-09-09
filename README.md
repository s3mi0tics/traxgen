# traxgen

Procedural generator for [GraviTrax](https://www.ravensburger.us/products/gravitrax) marble run courses.

> **Not affiliated with Ravensburger.** "GraviTrax" is a Ravensburger trademark.
> This project generates binary `.course` files compatible with the official GraviTrax app using the format reverse-engineered by [lfrancke/murmelbahn](https://github.com/lfrancke/murmelbahn).

## Status

Phase 1 closed on 2026-09-07: `python -m traxgen generate --set vertical-starter`
writes a course that the share-code upload endpoint accepts and the
official app renders as valid, verified through the Android harness
(`traxgen.android.render_course()` and its play-button oracle) on a
cold-booted emulator. Parser, serializer, validator, uploader and the
minimal generator are complete. Connection claims come from a rendered
record (`traxgen/graph.py`, `MEASURED_RUNS`), keyed on where each piece
stood, on which plate, and which pieces they were; the model that
proposes placements lives on a separate prediction surface and is
refuted by render, on purpose, when it is wrong.

Phase 2's target is the generator: multi-plate placement inside what
the record has measured. Current state lives in
[`allostatik/plan.md`](allostatik/plan.md); [`docs/PLAN.md`](docs/PLAN.md)
is the archived pre-August roadmap, including race mode and perpetual
mode (Phase 3).

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

# Render a share code in the Android emulator and capture a screenshot.
# Requires AVD `traxgen_m6c` running with GraviTrax at the main menu.
uv run python -m scripts.render_course X3WEQ6F296 --detect-validity
# rendering X3WEQ6F296 via emulator...
# screenshot saved: ~/Desktop/Hub/Projects/traxgen/screenshots/rendered_X3WEQ6F296.png
# play button: active
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
