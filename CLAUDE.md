# traxgen

Mode: **software engineering** (Python 3.12+, `uv`, pytest).

## Orient first

Session state and routines live in the `allostat/` files imported below. Follow
`allostat/workflow.md`'s open routine before acting on anything substantive;
`allostat/plan.md` is the single source of truth for "where are we." The former
living document, `docs/PLAN.md`, is **archived** — historical detail only; do
not orient from it or propose updates to it.

## Code conventions

Coding conventions (schema fidelity, type hints, testing markers, fixtures)
live in **`.cursorrules`**. Read it before editing source — those rules apply
here too, even though it is named for the Cursor surface.

## Why this file is thin

This is one execution-surface adapter over a shared core. Cursor reads
`.cursorrules`; Claude Code auto-loads this `CLAUDE.md`; both point at the same
canonical files rather than copying them.

<!-- BEGIN allostat (managed — edits here are overwritten on `allostat init`) -->

This region is contributed by Allostat. It declares this as an Allostat project and lists the project-scope files Claude loads each session. Architectural background for this pattern lives in the methodology's `README.md` — not duplicated here.

## This is an Allostat project

The project's context lives in the `allostat/` files below. At session start, load them and follow `allostat/workflow.md` — its open routine runs the drift + session-log-freshness checks before work begins. Your own Custom Instructions apply as they always do: Allostat is project-scoped and neither requires nor manages your personal/global layer.

## Project-scope `@`-imports

These files are loaded into every session for traxgen:

@allostat/project-instructions.md
@allostat/workflow.md
@allostat/plan.md
@allostat/decisions.md
@allostat/observations.md
@allostat/vision.md

Loaded when relevant (optional):

@allostat/knowledge/environment.md

<!-- END allostat (managed) -->
