# traxgen/.devcontainer/Dockerfile
#
# The box Claude Code works in. It holds the editing, the tests, the reports and
# the commits. It cannot render: the Android emulator needs nested
# virtualisation, which Docker Desktop cannot give a container and Apple silicon
# did not have before the M3 (s38-t5). Renders go out through the drop folder in
# scripts/render_door.py and happen on the Mac.
#
# Nothing below assumes what the base image carries. It ships git, zsh, a
# non-root `vscode` user and common build dependencies -- no Node, and no
# guarantee about anything else this needs. s39-t2 assumed an npm was there and
# committed a Dockerfile that could not have built.

FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# Node 22 is a floor, not a preference: @anthropic-ai/claude-code declares
# `engines.node >= 22.0.0`, and Ubuntu 24.04's own repository has 18. So the
# version comes from NodeSource rather than from apt's default.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends \
      nodejs python3.12 python3.12-venv python3.12-dev ripgrep \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code

# Python 3.12 is required, not preferred: traxgen/android.py uses PEP 695
# generics, which 3.11 cannot parse. .python-version pins the same 3.12.
#
# Each tool says its own version here, in the layer that installed it. A build
# that cannot print these lines has not produced a working image, and this is
# where it should stop -- not on the first run, three commands later, with the
# cause a layer behind.
RUN node --version \
 && npm --version \
 && python3.12 --version \
 && command -v claude

# The drop folder. Created here so the bind mount lands on a directory that
# exists and belongs to the user Claude Code runs as, rather than to root.
RUN mkdir -p /traxgen-door && chown vscode:vscode /traxgen-door

ENV TRAXGEN_DOOR_DROP=/traxgen-door \
    PATH=/home/vscode/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1

USER vscode

# uv goes in the user's own ~/.local/bin, which is where a non-root container
# should keep it, so it is installed after the user switch rather than as root.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && uv --version
