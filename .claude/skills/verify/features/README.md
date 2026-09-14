# traxgen verification map

The maintained source for verifying traxgen's user-facing behavior. A "user"
here is a builder at a terminal: they run a command, get a `.course` file, turn
it into a share code, and type that code into the GraviTrax app. Read this index,
then use the matching feature file as the recipe.

## Baseline preconditions

- Repo root is a traxgen checkout with a working `uv` environment.
- `.claude/skills/verify/scripts/verify_chain.sh --doctor` exits 0.
- Upload stages need TCP to `gravitrax.link.ravensburger.com:443`.
- Render stages need AVD `traxgen_m6c` and no emulator this run did not start.

## Driving conventions

- Drive through the CLI and the scripts named here, never by calling library
  functions from a Python prompt.
- Write every file into a run directory under `verify-runs/`, never the repo root.
- Treat every command as literal.

## Proof and skip reporting

- CLI proof is the command, stdout, stderr and exit code, all in the run directory.
- Report the strongest claim each stage supports (see the judge table in
  `../SKILL.md`). `claim: UNMEASURED` is never reported as valid.
- Report an unreached stage (no network, emulator busy) as skipped with the
  unmet precondition. Do not report it as passed.

## Feature entry contract

Each file: H1 title, one paragraph, then `Sub-features`, `How to get to it
(user POV)`, `Driving it with verify_chain`, `Gotchas`.

## Features

- [Generate a course](./generate.md) covers boards, the measured-only refusal, and the claim line.
- [Check a course file](./check.md) covers the byte round trip and the full validator.
- [Get a share code](./upload.md) covers upload, dedup, and the Phase 1 pin.
- [Render in the app](./render.md) covers the play-button validity oracle. **UNPROVEN: never run from this skill.**
