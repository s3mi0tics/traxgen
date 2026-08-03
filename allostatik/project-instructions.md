# traxgen — Project Instructions

Canonical template source: allostatik/templates/project-boilerplate/allostatik/project-instructions.md
Project-scope location: /Users/colbykauk/Claude/Projects/traxgen/allostatik/project-instructions.md
Paste destination: claude.ai Project "traxgen" → Project Instructions field holds the Allostatik pointer block (not a copy of this file); files load per session via the Standing essentials bundle below. Claude Code loads this file directly via the CLAUDE.md `@`-imports.
Edit at the project-scope location above; sync to the paste destination per your storage mode. Drift-checked at session start and end.

---

## Session rituals

This project's current state lives in files in the `allostatik/` folder — not in these instructions, which describe the *system*, not where it currently is. On a filesystem surface (Claude Code, Cursor, Claude Desktop with file access) those files load from the repo, and `workflow.md` holds the full routines. These two rituals are the short version:

**Opening.** Before answering anything that depends on current state — "where are we," "what's next," the status of any work — load the `allostatik/` files if you don't already have them, then run the open checks: is `plan.md`'s session log current (if it's behind, a prior close was skipped — backfill it before new work), and do the deployed surfaces still match canonical? Don't reconstruct state from these instructions alone.

**Closing.** When a session wraps up, update the canonical files for whatever changed (`plan.md`, `decisions.md`, `observations.md`) and confirm the writes landed **before** producing any handoff — the handoff *points at* those files, it doesn't carry state. This is what makes each session build on the last rather than start over.

*(Full open/close routines — the four drift-checks, capture, and handoff shape — live in `allostatik/workflow.md`, which loads alongside these files.)*

## Mode

I'm in **engineering** mode for this project.

## Purpose

traxgen procedurally generates GraviTrax marble-run courses: given a piece inventory, it produces a binary `.course` file that the official GraviTrax app accepts via Ravensburger's share-code system. Phase 1 proves the pipeline end-to-end — a single command generating a topologically valid single-track course from the PRO Vertical Starter-Set (26832) that loads in the app. Not affiliated with Ravensburger; builds on the format reverse-engineered by lfrancke/murmelbahn (Apache-2.0, attribution required).

## Known references

Project reference material lives in `allostatik/knowledge/` (project-scope Layer 3) — Claude reads it from there rather than from a list restated here. This project's local reference corpus lives at `docs/refs/` in the repo (rail specs, set contents, upload API, probe findings), indexed by `docs/refs/README.md` and pointed at from `allostatik/knowledge/resources.md`. (`allostatik/knowledge/` also holds `environment.md`, the project-runtime environment.)

## Project-specific working notes

- **Code conventions live in `.cursorrules` — read it before editing source.** It owns schema fidelity (never renumber enums, never "fix" odd spellings like `TRANSFERT`, value gaps are intentional), type-hint and dataclass conventions, testing markers, and fixture rules. Pointed at, not duplicated — it stays authoritative for both Cursor and Claude Code.
- **Trust only harness-verified render results.** Manual share-code verification has a silent clipboard failure mode that has already invalidated a session's worth of observations. Any validity claim about a generated course goes through `traxgen.android.render_course()` and the play-button oracle, not a human eyeballing a phone.
- **Attribution applies to docs, not just code.** The `.cursorrules` attribution rules (murmelbahn credit, no implied Ravensburger endorsement) bind README and doc edits too.

## Standing essentials bundle

Bundle command to load the project's canonical files into a new conversation. Primary loading for paste-loaded surfaces (claude.ai chat); fallback on Claude Code if manual re-load is needed.

```bash
{
  cd /Users/colbykauk/Claude/Projects/traxgen && \
  for f in \
    allostatik/project-instructions.md \
    allostatik/plan.md \
    allostatik/workflow.md \
    allostatik/decisions.md \
    allostatik/observations.md \
    allostatik/vision.md ; do
    echo "===== FILE: $f ====="
    cat "$f"
    echo ""
  done
} 2>&1 | tee >(pbcopy)
```

## Other files available on request

- Recent commits, for structural history:
  `{ cd /Users/colbykauk/Claude/Projects/traxgen && git log --oneline -20 ; } 2>&1 | tee >(pbcopy)`
- Last commit details:
  `{ cd /Users/colbykauk/Claude/Projects/traxgen && git log -1 --stat ; } 2>&1 | tee >(pbcopy)`
- Project structure: run `ctree` and paste the output.
