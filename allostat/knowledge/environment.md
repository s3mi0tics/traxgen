# traxgen — Environment (project-runtime)

Project-runtime environment context. Machine-wide setup lives in the user-scope environment file, not here.

> **Never put secrets here.** Env-var *names*, ports, and URLs are fine; actual keys, tokens, passwords, and credentials are not — these files are meant to be committed.

**Last updated:** 2026-07-22

## Runtime

- Mac M1. Python 3.12 pinned via `.python-version`; `uv` for env management; `pytest` runs the tests. Editor: VS Code, optionally Cursor (`.cursorrules` at repo root).
- Default pytest addopts include `-m 'not network'` — network-marked tests (the live upload canary) run only via `uv run pytest -m network`.
- Android SDK at `~/Library/Android/sdk`. AVD `traxgen_m6c` (Pixel 6, API 34, google_apis_playstore, arm64-v8a) hosts the render harness. Boot: `$ANDROID_HOME/emulator/emulator -avd traxgen_m6c -no-snapshot-load > /tmp/emulator.log 2>&1 &` — GraviTrax persists across reboots, no re-sign-in per session.

## Gotchas (each learned the hard way)

- `uv run python -m scripts.foo` puts the project on `sys.path`; plain `uv run python scripts/foo.py` does NOT.
- Shell-quoted Python containing `!` triggers zsh history expansion — use a heredoc (`cat > /tmp/foo.py << 'PYEOF' … PYEOF`) for anything beyond a trivial one-liner.
- Long bash blocks with markdown-bearing heredocs fail silently sometimes; prefer writing the file via a standalone artifact download when that happens.
- Filenames with parens/commas/coordinates (screenshot naming convention) work on the filesystem but break unquoted shell references.
- The murmelbahn source clone lives at `/tmp/murmelbahn-src` when present; `/tmp` gets wiped — re-clone from github.com/lfrancke/murmelbahn if needed.
- `ctree` outputs the project structure — ask for it rather than reconstructing the tree.
