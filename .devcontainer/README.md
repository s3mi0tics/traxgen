# The container, and the door out of it

This folder is the box Claude Code works in on Colby's Mac. It holds the
editing, the tests, the reports and the commits. It cannot render.

## Why it cannot render

The Android emulator inside a container needs KVM, KVM needs nested
virtualisation, Docker Desktop cannot give a container nested virtualisation,
and Apple silicon did not have it before the M3. This Mac is an M1 Pro. The
sources are in `allostatik/knowledge/environment.md`; the research is
`allostatik/knowledge/task_reports/2026-09-21-s38-t5-docker-and-the-emulator.md`.

So renders happen on the Mac, and the container asks for them through a shared
folder. That is `scripts/render_door.py`, and its design is in that file's
docstring.

## Running it

**Once, on the Mac.** Make the shared folder and a second checkout of traxgen —
the one the renders run from:

    mkdir -p ~/traxgen-door
    git clone https://github.com/s3mi0tics/traxgen.git ~/Claude/Projects/traxgen-render

That second checkout is deliberate, and it is the gate. The container can write
a share code into the drop folder, but it cannot change the code that renders
it. When the work *is* the harness, pulling that change into
`traxgen-render` is the approval — one `git pull`, made by a human who has
looked at the diff.

**Every session, on the Mac,** in its own terminal, left running:

    cd ~/Claude/Projects/traxgen-render
    uv run python -m scripts.render_door watch \
        --drop ~/traxgen-door --checkout ~/Claude/Projects/traxgen-render

**To build and check the image** (about 5 minutes the first time, seconds
after that -- Docker caches the layers):

    cd ~/Claude/Projects/traxgen
    docker build -f .devcontainer/Dockerfile -t traxgen-dev .

The build prints `node`, `npm`, `python3.12` and `uv` version lines and the path
`claude` resolves to. Those lines are the check: a build that does not print
them has not made a working image, whatever its exit code says. Opening the
folder in VS Code or Cursor and choosing *Reopen in Container* uses the same
`Dockerfile` and adds the mounts from `devcontainer.json`.

**In the container**, a render is one command:

    uv run python -m scripts.render_door request KN6F459ZR3

`TRAXGEN_DOOR_DROP` is already set, so `--drop` is not needed inside.

## What the settings file is and is not

`.claude/settings.json` is not the security boundary. The container's isolation
is, and the watcher on the Mac is the boundary for everything that crosses the
door. The settings file stops *mistakes*: pushing from a box whose commits have
not been looked at, reading credentials, writing the door's own answers.

Rules are evaluated deny, then ask, then allow, and an allow rule cannot carve
an exception out of a deny rule.

**It applies on the Mac too.** `.claude/settings.json` is project-scoped, so
these rules reach every Claude Code session opened on this repo, not only the
one in the container. In practice that changes one thing: `Bash(git push:*)` is
denied, so a Claude Code session on the Mac cannot push either. That matches how
this project already works — pushes come from Colby's own shell — but it is a
real consequence rather than a container-only setting. To lift it for the Mac
alone, `.claude/settings.local.json` does not work: a deny rule from any scope
beats an allow from any other. Remove the line, or push from the shell.

**One deliberate omission.** The seven files only the session close may write —
`plan.md`, `log.md`, `decisions.md`, `observations.md`, the record index,
`knowledge/environment.md` and `knowledge/resources.md` — are *not* denied here,
even though a task must not touch them. A deny rule would block the close as
well, since the close runs in the same container. `scripts/task_check.py` is
what holds a task to its scope, and it fails a task that changes any of them.
The check belongs there, where it can tell a task from a close.

## Running unattended

Claude Code's `--dangerously-skip-permissions` is documented for exactly this
shape — a container, running as a non-root user, with commands confined to it.
Turning it on is Colby's call, not this file's, because it decides how much runs
between his gates. Without it, the allow list above covers the commands this
project's work actually runs, and anything else asks.
