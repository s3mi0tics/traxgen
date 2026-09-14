---
name: verify
description: Prove a traxgen change against its outside judges -- generate a GraviTrax .course with the real CLI, byte round-trip it through the parser, run the full validator, upload it to Ravensburger for a share code, and optionally have the Android app render it. Use after touching the generator, serializer, parser, validator or uploader, before claiming a course works, or when asked to verify, prove, or get a share code for a generated course.
---

# verify (traxgen)

traxgen is a Python library and CLI. There is no server to keep alive: each run
generates a file, judges it offline, then asks two outside judges. One command
runs the whole chain and leaves evidence on disk:

```bash
.claude/skills/verify/scripts/verify_chain.sh                       # single-plate, with upload
.claude/skills/verify/scripts/verify_chain.sh --board standard-square
.claude/skills/verify/scripts/verify_chain.sh --no-upload           # offline only
.claude/skills/verify/scripts/verify_chain.sh --render              # + app oracle, ~2.5 min
```

Read `summary.txt` in the printed `verify-runs/...` directory. Each stage is one
`PASS|FAIL|REFUSED <stage> <detail>` line.

## What each judge can and cannot prove

State the strongest claim the run supports. Do not state a stronger one.

| Stage | Judge | Proves | Does not prove |
|---|---|---|---|
| generate | `validate_strict` inside the CLI | no ERROR rule fired | anything about WARNINGs, which it discards |
| check | `check_course.py` | bytes parse and re-serialize identically; full violation list | that the app agrees with the format |
| upload | Ravensburger's endpoint | the server accepted the bytes and assigned a code | **validity**: the endpoint stores bytes and never runs the ball path |
| code_pin | the endpoint's content dedup | single-plate bytes are the ones the app certified at Phase 1 close | anything about other boards |
| render | GraviTrax app, play-button oracle | the app calls the course valid (`active`) | nothing further; this is the judge of record |

Project rule (`allostatik/project-instructions.md`): validity claims go through
`render_course()` and the play-button oracle, never a human looking at a phone.
Without `--render`, a new course is "well-formed and accepted", not "valid".
The generator's own `claim:` line says the same: `UNMEASURED` means no render
has tested that placement.

## Launch

Nothing to launch for stages 1-4. Run from anywhere in the repo; the script
`cd`s to the root. Dependencies are the repo's `uv` environment (`uv sync` if
`uv run` complains).

The render stage launches the emulator itself: `render_course --fresh` kills
any running emulator, cold-boots AVD `traxgen_m6c`, waits for the recognised
main menu, renders, and tears the emulator down on every exit path. Ready is
internal to that command. You do not start or poll anything.

## Doctor

Run first, and whenever a stage fails for a reason that is not the code:

```bash
.claude/skills/verify/scripts/verify_chain.sh --doctor
```

Read-only. Prints `repo` (HEAD, and whether tracked files are modified, which
means the run judges uncommitted code), `import` (traxgen resolves inside this
checkout), `network` (TCP to the upload host), and `render` (adb present,
emulator running or not). Exit 0 when repo, import and network pass. If
`network` fails, run with `--no-upload`. If the emulator shows RUNNING and this
run did not start it, do not pass `--render`.

For the emulator specifically, `uv run python -m scripts.preflight` grades a
running device with six checks. It is the repo's own doctor for renders.

## Drive

The feature map in `features/` is the recipe per user-facing feature. Start at
`features/README.md`. The chain script drives the top path of each feature. The
map lists the other entry points.

To judge a `.course` you already have (a fixture, a hand-built probe):

```bash
uv run python .claude/skills/verify/scripts/check_course.py path/to/file.course
uv run python -m scripts.upload_course path/to/file.course     # stdout: the code only
```

## Evidence

Every run writes `verify-runs/<UTC stamp>-<board>[-measured]-<4 chars>/` (gitignored) containing:
`summary.txt`, `course.course`, `course.again.course`, `generate.log`,
`check.log`, and when run, `upload.log`, `share_code.txt`, `render.log`, and
`rendered_<code>.png`. A report cites the directory and quotes `summary.txt`.

Proof standards:

- Drive the real CLI (`python -m traxgen generate`), not `generate_minimal()`
  from Python. The CLI is what the definition of done names.
- The round trip reads the bytes on disk, not the in-memory `Course`.
- Quote `claim:` and every WARNING. A PASS with `claim: UNMEASURED` is a
  prediction, not a measurement.
- A share code is evidence of acceptance only. Pair it with `render` before
  calling a course valid.
- Negative control when a judge is new or changed: feed it a known-bad input
  and confirm FAIL (flip the last byte of a good course: round trip fails at
  that offset; truncate it: parse raises). A judge never seen to fail proves
  nothing.

## Cleanup

Stages 1-4 create only the run directory, which is the evidence. Keep it.
Delete old runs by hand when they pile up: `rm -rf verify-runs/<stamp>-*`.

`--render` tears down its own emulator. If a render was interrupted, run
`uv run python -m scripts.emulator kill`. It asks through `adb emu kill` and
confirms `qemu-system` is gone. Do not `pkill` the emulator: that can strand
the AVD lock and fail the next boot. Note the one departure from "kill only
what you started": this repo owns a single AVD, and `--fresh` deliberately
takes it over. That is why the doctor warns when one is already up.

## Isolation

- generate/check: pure and parallel-safe. Each run has its own directory.
- upload: an external, **public** service. Each distinct byte sequence creates
  a new shareable course on Ravensburger's servers. Identical bytes return the
  same code, so rerunning a chain is free. Do not loop over variants without
  the user's say-so. The endpoint fails transiently (HTTP 520, TLS timeouts):
  one retry is reasonable, and `traxgen.uploader.upload_course_with_retry`
  encodes the policy.
- render: one emulator, one run at a time. Never run two `--render` chains at
  once.

## Helpers

| Script | Invocation | Does |
|---|---|---|
| `scripts/verify_chain.sh` | see top of file | the whole chain, evidence dir, summary |
| `scripts/check_course.py` | `uv run python .claude/skills/verify/scripts/check_course.py FILE [--set vertical-starter]` | round trip + full validator, exit 0/1 |
| `scripts/doctor.py` | `verify_chain.sh --doctor` | read-only readiness check |

Pins inside `verify_chain.sh`: `PIN_SHA` and `PIN_CODE=KN6F459ZR3`, the Phase 1
closing artifact (`allostatik/plan.md`). A single-plate `pin` or `code_pin` FAIL
means the default command no longer emits the certified bytes. Treat that as a
regression unless the change was meant to alter them. If it was, re-render,
then update both pins in the same commit.
