# s39-t2 — the container the work runs in

**Status:** STOPPED -- needs Colby: the build and first run are on his Mac. The commands, and the outcomes to check, are in *Next* below.

**In one paragraph:** the container is an Ubuntu 24.04 dev container with Python 3.12, `uv`, `ripgrep` and Claude Code, running as a non-root user, with this repo mounted and the drop folder from s39-t1 bind-mounted at `/traxgen-door`. `.claude/settings.json` carries deny rules for the mistakes a container run can make -- pushing, reading credentials, writing the door's own answers -- and allow rules for the commands this project's work actually runs. Both JSON files validate clean against their published schemas, which is the check that matters here: a wrong key or a wrong rule syntax is inert rather than loud, and a guide subagent handed me three confidently wrong schemas for these exact files. Nothing here was built: this box has no Docker daemon and is x86_64 against the Mac's arm64, so the build and first run are Colby's, and the outcomes to check were written down before he runs it.

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

## Close

- **What happened:** wrote `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`, `.devcontainer/README.md`, `.dockerignore` and `.claude/settings.json`. Before writing the settings file, asked a guide subagent for the documented schemas, did not trust its answer, and read the docs directly -- which is how the settings file has the right syntax.

- **What changed:** `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`, `.devcontainer/README.md`, `.dockerignore`, `.claude/settings.json`, all new. The commit is the one that adds this report's close.

- **Evidence:**
  - `task_check s39-t2`: in scope -- 5 files changed since open commit `67bc0ea`, all declared.
  - Schema validation: 2 files checked, 0 errors. `.claude/settings.json` against `claude-code-settings.json` (fetched from the SchemaStore repo, since `json.schemastore.org` is blocked by this box's egress proxy), `.devcontainer/devcontainer.json` against the devcontainer spec's `devContainer.base.schema.json`.
  - Deny rules naming a close-owned file: none.
  - Mount path: `devcontainer.json`'s mount target, its `containerEnv`, and the `Dockerfile` all say `/traxgen-door`; the README's watcher command takes the host side, `~/traxgen-door`.
  - Python: `Dockerfile` installs 3.12 on `ubuntu-24.04`; `.python-version` says 3.12.
  - No build, no container run. See the stop.

- **The check that earned its place, and the claim it refuted:** I wrote in this task's open that a schema check might not catch a wrong *rule syntax*, since the schema could type a permission rule as a plain string. That was a claim about a mechanism, so I ran it rather than writing it down: fed the subagent's `bash:git *` and `file:read:~/.ssh/*` to the published schema, and got 2 errors. The schema's `permissionRule` carries the full `^((Agent|Bash|Edit|...)(\([^)]+\))?|mcp__.*)$` pattern, so it does catch it. The grammar check I had written alongside it is redundant and narrower than the schema's own tool list, and is not being kept.

- **Decisions made inside the task:**
  - The seven close-owned files are deliberately *not* in the deny list. The close runs in the same container as the tasks, so a deny rule would block it too; `task_check` is the mechanism that can tell a task from a close, and it already fails a task that touches them. Written into the README so the omission reads as a decision rather than an oversight.
  - Deny rules only, no `ask` rules. An `ask` rule in an unattended container is a prompt with nobody in front of it: the useful states are "runs" and "does not".
  - The render checkout is a second clone, `~/Claude/Projects/traxgen-render`, not the working repo. The container can ask for a render; it cannot change what renders. Pulling a harness change into that clone is the human approval, and it is one `git pull` by someone who has looked at the diff.
  - `--dangerously-skip-permissions` is documented and named in the README, but not turned on anywhere. It decides how much runs between Colby's gates, which is his call, not a config file's.
  - `.dockerignore` excludes `.venv/` first. The repo carries a macOS virtualenv, and copying it into a Linux image is the same failure `environment.md` already records for `uv sync` inside the bridge mount.
  - `ubuntu-24.04` rather than the `:ubuntu` floating tag: 24.04 ships Python 3.12 as its system python3, which is the version `traxgen/android.py`'s PEP 695 generics require, and a floating tag would move off it silently.

- **For the record:**
  - `plan.md`, the order line: the container and the door are both written. What remains of both is the same live proof -- build, start the watcher, send one request -- which needs the Mac.
  - `decisions.md`, a row: the container is a dev container running as a non-root user with the repo and the drop folder mounted; `.claude/settings.json` stops mistakes, and the container's isolation plus the watcher are the security boundary. The close-owned files stay out of the deny list because the close runs in the same container. Reason: 2026-09-22, s39.
  - `observations.md`: **a subagent's "verified against the docs" is the subagent's own account of its work, and a check may not take the checked party's word.** The guide agent returned three schemas for a file about to be committed -- permission rules as `bash:git *`, a `sessionEnd` hook that is not an event name, a `hooks` shape with no `matcher` nesting -- each stated as verified, each wrong. The real syntax is `Bash(git *)`, the events include `Stop` and `SessionEnd` among thirty-three, and hooks nest through a `matcher`. What settled it was reading the docs and validating against the published schema: records that existed before the check ran. This is #55's shape again, one layer out -- the author of a text passes his own text -- and the third firing in two sessions. *Cheap test:* a subagent's answer being written into a committed file with no record read between the two.
  - `knowledge/environment.md`: this session's cloud clone has a Docker CLI but no daemon, and is x86_64; `json.schemastore.org` is blocked by its egress proxy, while `raw.githubusercontent.com` is not, so a SchemaStore schema is fetched from the source repo.

- **Friction:**
  - The scope line forbids widening after the work, which is right, and it means a check worth keeping cannot be committed by the task that invented it. The schema validation here ran as a one-off; making it `scripts/check_configs.py` is a separate task. Naming it because the alternative -- quietly widening -- is the thing the rule exists to stop.
  - The routine says nothing about a task whose only remaining step is a build that cannot run where the task runs. Declaring the outcomes in advance (#53) covers it, and that is what this task did, but the wording is about live *runs* rather than live builds.

- **Next:** Colby's build and first run, on the Mac. Three commands, in the handover.
