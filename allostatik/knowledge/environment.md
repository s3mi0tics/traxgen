# traxgen — Environment (project-runtime)

Project-runtime environment context. Machine-wide setup lives in the user-scope environment file, not here.

> **Never put secrets here.** Env-var *names*, ports, and URLs are fine; actual keys, tokens, passwords, and credentials are not — these files are meant to be committed.

**Last updated:** 2026-08-08

## Runtime

- Mac M1. Python 3.12 pinned via `.python-version`; `uv` for env management; `pytest` runs the tests. Editor: VS Code, optionally Cursor (`.cursorrules` at repo root).
- Default pytest addopts include `-m 'not network'` — network-marked tests (the live upload canary) run only via `uv run pytest -m network`.
- Android SDK at `~/Library/Android/sdk`. AVD `traxgen_m6c` (Pixel 6, API 34, google_apis_playstore, arm64-v8a) hosts the render harness. Boot: `${ANDROID_HOME:-$HOME/Library/Android/sdk}/emulator/emulator -avd traxgen_m6c -no-snapshot-load > /tmp/emulator.log 2>&1 &` — GraviTrax persists across reboots, no re-sign-in per session.
- A second AVD, `traxgen_test`, exists and is undocumented. Either it earns a line here or it gets deleted (tracked in `plan.md` deferred cleanup).
- `gh` CLI is installed and authenticated over SSH — GitHub operations (PRs, issues, releases) can go through `gh` rather than the web UI.
- Hammerspoon is installed, so macOS-side automation is available if a workflow ever wants it.
- Repo lives at `/Users/colbykauk/Claude/Projects/traxgen`. (The old `~/Desktop/Hub/Projects/traxgen` checkout is deleted — anything still naming that path is stale.)

- **Cowork sessions can read and write this repo directly, but cannot drive the emulator.** A Cowork session granted folder access gets a shell in a Linux VM with the repo mounted — `git`, `python3` and `uv` are present and file edits land straight on disk, so canonical-file and script edits need no paste round-trip. That VM has **no `adb`, no emulator, no network, and no view of `/Users`**, so every render, upload, test run and `git push` still has to come from this Mac. Verified 2026-08-08 by checking `command -v` rather than assuming.

## Gotchas (each learned the hard way)

- **`$ANDROID_HOME` is not exported in a default shell.** A boot command written as `$ANDROID_HOME/emulator/emulator ...` expands to `/emulator/emulator`, fails, and — because the command redirects into `/tmp/emulator.log` — fails *silently* while appearing to background successfully. Use `${ANDROID_HOME:-$HOME/Library/Android/sdk}`. The library is unaffected: `android.resolve_context()` already falls back to that path.
- **`direnv: unloading` with no matching load line means no `.envrc` here.** This repo has none. That line comes from direnv unloading whatever env the *previous* directory had as you `cd` in, and it appears on every `{ cd ...; }` one-liner. Harmless in itself — but it was misread for a whole session as confirmation that a (nonexistent) repo `.envrc` was working.
- **A cold-booted AVD (`-no-snapshot-load`) needs real time before it will drive.** `reset_to_main_menu()` + 8s was not enough for the Unity app to clear its splash screen on 2026-08-07; the render fired into the loading screen and the play-button oracle read the near-white splash as `active`. Allow ~30s, or better, poll (see `docs/refs/ui-automation-synchronization.md`).

- `uv run python -m scripts.foo` puts the project on `sys.path`; plain `uv run python scripts/foo.py` does NOT.
- Shell-quoted Python containing `!` triggers zsh history expansion — use a heredoc (`cat > /tmp/foo.py << 'PYEOF' … PYEOF`) for anything beyond a trivial one-liner.
- Long bash blocks with markdown-bearing heredocs fail silently sometimes; prefer writing the file via a standalone artifact download when that happens.
- Filenames with parens/commas/coordinates (screenshot naming convention) work on the filesystem but break unquoted shell references.
- The murmelbahn source clone lives at `/tmp/murmelbahn-src` when present; `/tmp` gets wiped — re-clone from github.com/lfrancke/murmelbahn if needed.
- `ctree` outputs the project structure — ask for it rather than reconstructing the tree.
