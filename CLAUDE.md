# traxgen

Mode: **software engineering** (Python 3.12+, `uv`, pytest).

## Orient first

Session state and routines live in the `allostatik/` files imported below. Follow
`allostatik/workflow.md`'s open routine before acting on anything substantive;
`allostatik/plan.md` is the single source of truth for "where are we." The former
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

<!-- BEGIN allostatik (managed — edits here are overwritten on `allostatik init`) -->

This region is contributed by Allostatik. It declares this as an Allostatik project and lists the project-scope files Claude loads each session. Architectural background for this pattern lives in the methodology's `README.md` — not duplicated here.

## This is an Allostatik project

The project's context lives in the `allostatik/` files below. At session start, load them and follow `allostatik/workflow.md` — its open routine runs the drift + session-log-freshness checks before work begins. Your own Custom Instructions apply as they always do: Allostatik is project-scoped and neither requires nor manages your personal/global layer.

## Project-scope `@`-imports

These files are loaded into every session for traxgen:

@allostatik/project-instructions.md
@allostatik/workflow.md
@allostatik/plan.md
@allostatik/decisions.md
@allostatik/observations.md
@allostatik/vision.md

Loaded when relevant (optional):

@allostatik/knowledge/environment.md

<!-- END allostatik (managed) -->
