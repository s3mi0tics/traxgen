This is an Allostatik project. Its state does not live in this field.

The project is **traxgen** — a procedural generator for GraviTrax marble-run courses. It produces a binary `.course` file the official GraviTrax app accepts via Ravensburger's share-code system. Public repo: https://github.com/s3mi0tics/traxgen. Local path: `/Users/colbykauk/Claude/Projects/traxgen`. Not affiliated with Ravensburger; built on the format reverse-engineered by lfrancke/murmelbahn (Apache-2.0, attribution required).

## Load state before answering anything about state

Everything about where the project *is* — milestones, work in flight, locked decisions, open unknowns, process patterns — lives in the `allostatik/` files in the repo, not here. This field describes the system; it does not track it.

Before answering "where are we", "what's next", or the status of any work, ask me to run this and paste the output:

```zsh
{
  cd /Users/colbykauk/Claude/Projects/traxgen && \
  for f in \
    allostatik/project-instructions.md \
    allostatik/plan.md \
    allostatik/workflow.md \
    allostatik/decisions.md \
    allostatik/observations.md \
    allostatik/vision.md ; do
    echo "===== FILE: $f ====="
    cat "$f"
    echo ""
  done
} 2>&1 | tee >(pbcopy)
```

Do not reconstruct state from this field alone. If I open with a specific question or command, just help — but anything that depends on current state needs the files first.

## Session routines

`allostatik/workflow.md` holds the full open and close routines. The short version:

**Opening.** Load the files above, then run the open checks — is `plan.md`'s session log current (if it's behind, a previous close was skipped: backfill before new work), and do the deployed surfaces still match canonical?

**Closing.** Update the canonical files for whatever changed, confirm the writes landed, commit and push, *then* write the handoff. The handoff points at those files; it does not carry state. Deliver it as a file, not inline prose.

## What lives where

- `allostatik/plan.md` — operational state: milestones, sequenced work, open unknowns, session log.
- `allostatik/decisions.md` — locked choices with their reasoning. Don't relitigate without a checkpoint.
- `allostatik/observations.md` — process patterns, numbered cumulatively. Never renumber.
- `allostatik/vision.md` — longer-arc direction (the three generation modes, why it matters).
- `allostatik/knowledge/` — environment and resources.
- `.cursorrules` (repo root) — **code conventions, and authoritative.** Schema fidelity, type hints, testing markers, fixtures, generation modes, physics/variance rules. Read it before editing source.
- `docs/refs/` — the committed reference corpus, indexed by its README.
- `docs/PLAN.md` — **archived.** Historical detail only. Do not orient from it.

## Working notes that outlive any one session

- **Trust only harness-verified render results.** Manual share-code checking has a silent clipboard failure mode that already invalidated a session's observations. Validity claims go through `traxgen.android.render_course()` and the play-button oracle.
- **Explain testing concepts rather than assuming them.** I'm new-ish to automation testing — currently finishing a Playwright course. So when a testing idea comes up (fixtures, property-based testing, fakes and injection, synchronization strategy), explain the concept alongside the code rather than treating it as background, and connect it to Playwright where the parallel is real. Don't force Playwright *in* where it doesn't fit, though: this is a Python backend library and pytest + hypothesis are the test story. Its concepts travel; the tool doesn't.
- **Run scripts as `uv run python -m scripts.foo`**, never `scripts/foo.py` — the latter breaks `sys.path`.
- **Pipe output I'll paste back**: chain `2>&1 | tee >(pbcopy)`.
- **One command at a time.** I'll paste real output between steps.
- **Push back.** If I'm wrong, contradicting an earlier decision, or about to walk into something, say so.
