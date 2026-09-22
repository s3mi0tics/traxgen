# s39-t3 — the container had no Node, so Claude Code could not have installed

**Status:** STOPPED -- needs Colby: the build is on his Mac. One command, in *Next* below.

**In one paragraph:** s39-t2's `Dockerfile` ran `npm install -g @anthropic-ai/claude-code` against an image with no `npm` in it. The devcontainers base image ships git, zsh and a non-root user, and no Node; Claude Code's package declares `engines.node >= 22.0.0`; Ubuntu 24.04's own repository has 18. So the build would have failed, and if it had somehow got past that, `claude` would have refused to start. The fix installs Node 22 from NodeSource and then makes the build say what it installed -- `node`, `npm`, `python3.12` and `uv` all print their versions, and `claude` prints the path it resolves to, each in the layer that installed it. The defect was caught by reading the npm registry and the base image's README before handing Colby a ten-minute build, not by building.

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

## Close

- **What happened:** before handing over the build command, checked the two things the `Dockerfile` assumed. `https://registry.npmjs.org/@anthropic-ai%2Fclaude-code` reports `engines: {"node": ">=22.0.0"}`. The devcontainers base-image README lists the image's contents as `git`, `zsh`, Oh My Zsh, a non-root `vscode` user "and a set of common dependencies for development" -- no Node. Both readings came before any build, so the ten minutes was never spent.

- **What changed:** `.devcontainer/Dockerfile` and `.devcontainer/README.md`. The commit is the one that adds this report's close.

- **Evidence:**
  - `task_check s39-t3`: in scope -- 2 files changed since open commit `84f62ce`, all declared.
  - `engines.node` for `@anthropic-ai/claude-code@2.1.280`: `>=22.0.0`, read from the npm registry.
  - The base image's own README, which does not list Node among its contents.
  - No build. This box has no Docker daemon and is x86_64; the build is the stop.

- **Decisions made inside the task:**
  - Node comes from NodeSource, pinned to the 22 line, rather than from apt. Ubuntu 24.04's `nodejs` is 18, which is below the declared floor, so apt's default would produce an image that builds and cannot run `claude`. A failure that waits until first use is worse than one at build time.
  - The `Dockerfile` installs `curl`, `ca-certificates` and `gnupg` itself rather than assuming them. That is the same class of assumption that caused the defect; fixing the instance and leaving the class would have been the shallower repair.
  - Each install layer ends by printing what it installed. This is the build's own cheap test, and it puts the failure at the line that caused it. `command -v claude` rather than `claude --version`, because a version call can want a terminal and a false failure here would be worse than no check.
  - `uv` is installed after the switch to the `vscode` user, so it lands in that user's `~/.local/bin` rather than in root's.

- **For the record:**
  - `plan.md`: no change to the order. The container's config is written and unbuilt; the build is the same stop s39-t2 left.
  - `observations.md`, the s39-t2 entry gets a second instance rather than a new number: **a config file's claims are test cases in the same way code's are, and "it builds" is the test.** s39-t2 validated both JSON files against their published schemas and treated the `Dockerfile` as prose, because a `Dockerfile` has no schema to validate against. What it does have is two facts anyone can read without building: what the base image contains, and what the package requires. Neither was read until the moment before handing over a ten-minute build.
  - `knowledge/environment.md`: the devcontainers Ubuntu base image carries no Node, and Claude Code needs 22 or newer.

- **Friction:** s39-t2's done check asked whether the `Dockerfile` would leave the project "unable to run -- no `uv`, or a Python that is not 3.12". It named the two tools I was thinking about and not the one the image lacked. That is the same shape as s39-t1's defect, in the same session: the check covered the fields its author had in mind. A miss-case list is itself a class that wants enumerating, not a list of the instances that came to mind.

- **Next:** Colby's build, one command, about 5 minutes the first time:

      cd ~/Claude/Projects/traxgen && docker build -f .devcontainer/Dockerfile -t traxgen-dev .
