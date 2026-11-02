# s46-t4 — the one-ring course, seen to finish

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** the finish check, on the emulator, says whether `QTOVZBN3AV` finishes. It is one ring: a curve at rotation 5, its launch pad, and five goals. The checker, with the curve rule, reads it VALID.
- **Scope:** no files; the ledger and this report only.
- **Budget:** one `--fresh` render, with one retry if the first launch dies (#21).
- **Done check:**
  1. *Step:* `ANDROID_SERIAL=emulator-5554 uv run python -m scripts.render_course QTOVZBN3AV --fresh --detect-validity --detect-finish`.
  2. *True after:* a `finish:` reading exists for a starter -> curve -> goal course.
  3. *Miss cases:* a refused or loading screen reads as a miss (the harness's guards raise instead); the run never starts (UNJUDGED, not a miss).
  4. *Reads:* the command's `play button:` and `finish:` lines.
  5. *Check:* the `finish:` line says finished, with its peak.
- **Outcomes declared before any live run:** placement active; finish finished. One ring means the board's single burst can only be this ring's.
