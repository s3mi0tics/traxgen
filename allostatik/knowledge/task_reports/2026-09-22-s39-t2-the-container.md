# s39-t2 — the container the work runs in

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** write the container config that lets Claude Code work on this repo inside Docker on Colby's Mac, with the drop folder from s39-t1 reaching in, and a Claude Code settings file that stops the mistakes a container run can make.
- **Scope:** `.devcontainer/`, `.claude/`, `.dockerignore`. The `TASK-OPEN s39-t2` ledger line is the record.
- **Budget:** 45 minutes, zero container builds here (no Docker daemon in this box, and it is x86_64 against the Mac's arm64).
- **Done check:**
  1. *Step:* writing the container config.
  2. *True after:*
     - `.devcontainer/` holds a `devcontainer.json` and a `Dockerfile` that mount this repo and the drop folder, run as a non-root user, and install Python 3.12, `uv` and Claude Code;
     - `.claude/settings.json` carries deny rules for what a container run should not do, and allow rules for the commands this project's work actually runs;
     - every JSON file is strict JSON and validates against its own published schema, with no key the schema does not know;
     - no deny rule blocks the session close from writing the seven files only it may write.
  3. *Miss cases:*
     - a config file that reads correctly and names a key the tool ignores, so it looks like configuration and is inert — the live hazard here, not a hypothetical: a guide subagent returned three confidently wrong schemas for this exact file (`bash:git *` for what is really `Bash(git *)`, a `sessionEnd` hook shape that does not exist), and a wrong key fails silently in both directions;
     - deny rules written broadly enough to block the session close, which must write `plan.md`, `log.md`, `decisions.md`, `observations.md`, the record index, `knowledge/environment.md` and `knowledge/resources.md`;
     - a `Dockerfile` that builds but leaves the project unable to run — no `uv`, or a Python that is not 3.12, which `traxgen/android.py` needs for its PEP 695 generics;
     - a drop-folder mount the container can write but the Mac's watcher cannot read, so the door is configured and dead;
     - config written as though the permission rules were the security boundary, when the container's isolation is.
  4. *Reads:* the config files themselves; the published JSON schemas, fetched at check time from `json.schemastore.org` and the devcontainer spec; the validator's output; and `workflow.md`'s *Task routine*, which names the close-owned files.
  5. *Check:* a validation script reports every JSON config file parsed, validated against its schema, and the number of errors; a grep over the deny rules returns none of the seven close-owned filenames; the `Dockerfile`'s version pins are read back and match 3.12; and the two mount paths in `devcontainer.json` are the same string the watcher's `--drop` takes.
- **Outcomes declared before any live run:** none here, because the build cannot run in this box. The build and first run are the task's stop, and the outcomes are declared for Colby to check: the image builds on arm64; `python --version` inside reports 3.12; `uv --version` and `claude --version` both answer; and `uv run pytest -q` inside the container reports the same pass count as the Mac.
