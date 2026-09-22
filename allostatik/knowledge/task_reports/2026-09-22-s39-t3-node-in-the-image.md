# s39-t3 — the container had no Node, so Claude Code could not have installed

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** fix the `Dockerfile` s39-t2 committed, which installs Claude Code with `npm` into an image that has no `npm`, and make the build check its own results so the next defect of this shape fails at the line that caused it.
- **Scope:** `.devcontainer/`. The `TASK-OPEN s39-t3` ledger line is the record.
- **Budget:** 20 minutes, zero builds here (no Docker daemon in this box).
- **Done check:**
  1. *Step:* fixing the image.
  2. *True after:*
     - the `Dockerfile` installs a Node whose version satisfies the floor `@anthropic-ai/claude-code` declares, from a source that does not depend on what the base image happens to carry;
     - the build verifies each tool it installed, in the build, so a missing one fails the layer that installed it rather than the first run;
     - the `README` gives a build command that can be run and read on its own, without the devcontainer lifecycle.
  3. *Miss cases:*
     - a Node installed from Ubuntu's own repository, which is 18 on 24.04 and below the declared floor, so the image builds and `claude` refuses to start;
     - a Dockerfile that assumes the base image carries `curl`, `npm` or a Python, which is how this defect happened in the first place -- s39-t2 wrote `npm install` against an image whose README lists `git`, `zsh` and a non-root user and no Node;
     - a build that succeeds and leaves a tool missing, because nothing in it looks.
  4. *Reads:* the npm registry's own metadata for `@anthropic-ai/claude-code` (`engines.node`), fetched before this task ran; the devcontainers base-image README, which lists the image's contents; and the build output itself, which is a record the build produces and anyone can re-read.
  5. *Check:* `docker build` reports success, and its log shows the version line printed by each tool the image installs -- `node`, `npm`, `python3.12`, `uv` -- and the path `claude` resolves to. A build that omits any of those lines has not passed, whatever its exit code says. This check runs on Colby's Mac: this box has no Docker daemon and is x86_64 against its arm64.
- **Outcomes declared before any live run:** the build succeeds on arm64; `node --version` reports 22 or higher; `python3.12 --version` reports 3.12; `uv --version` answers; `claude` resolves to a path. Declared here so the build's log is graded against something written before it ran.
