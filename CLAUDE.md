# traxgen — Claude Code adapter

Mode: **software engineering** (Python 3.12+, `uv`, pytest).

## Orient first

Before acting on anything substantive, read **`docs/PLAN.md`** — it is the
canonical living document for this project (status, confirmed decisions,
module plan, current milestone, known unknowns). Start with its top sections;
read deeper as the task requires. It is the single source of truth for "where
are we." This file does not duplicate it — it points at it.

## Living-document discipline

`docs/PLAN.md` drifts as we work and is meant to. At the end of any session
where something substantive changed — a decision made, a milestone completed,
scope shifted, a file became relevant — propose an updated PLAN.md. See its
"Living document discipline" section for what to watch.

## Code conventions

Coding conventions (schema fidelity, type hints, testing markers, fixtures)
live in **`.cursorrules`**. Read it before editing source — those rules apply
here too, even though it is named for the Cursor surface.

## Why this file is thin

This is one execution-surface adapter over a shared core. Cursor reads
`.cursorrules`; Claude Code auto-loads this `CLAUDE.md`; both point at the
same canonical living docs rather than copying them. Keep the payload (which
docs to read, which mode) identical to the other surfaces so it stays liftable
into a shared template if this pattern proves out.
