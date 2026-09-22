# traxgen/.devcontainer/Dockerfile
#
# The box Claude Code works in. It holds the editing, the tests, the reports and
# the commits. It cannot render: the Android emulator needs nested
# virtualisation, which Docker Desktop cannot give a container and Apple silicon
# did not have before the M3 (s38-t5). Renders go out through the drop folder in
# scripts/render_door.py and happen on the Mac.

FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# Python 3.12 is required, not preferred: traxgen/android.py uses PEP 695
# generics, which 3.11 cannot parse. Ubuntu 24.04 ships 3.12 as its system
# python3, and uv pins the same version from .python-version.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3.12 python3.12-venv python3.12-dev ripgrep \
 && rm -rf /var/lib/apt/lists/*

# Claude Code needs Node. The base image carries a recent one for `vscode`.
RUN su vscode -c "curl -LsSf https://astral.sh/uv/install.sh | sh" \
 && su vscode -c "npm install -g @anthropic-ai/claude-code" 2>/dev/null \
 || npm install -g @anthropic-ai/claude-code

# The drop folder. Created here so the bind mount lands on a directory that
# exists and is owned by the user Claude Code runs as, rather than by root.
RUN mkdir -p /traxgen-door && chown vscode:vscode /traxgen-door

ENV TRAXGEN_DOOR_DROP=/traxgen-door \
    PATH=/home/vscode/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1

USER vscode
