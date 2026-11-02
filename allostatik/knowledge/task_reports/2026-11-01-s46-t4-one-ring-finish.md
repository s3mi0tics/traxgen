# s46-t4 — the one-ring course, seen to finish

**Status:** DONE

**In one paragraph:** The first course with a curve in it finished, measured by the harness. `QTOVZBN3AV` (a launch pad, a curve at rotation 5, five goals) rendered with a white play button, and the finish check read a burst (peak 484 against a threshold of 30). The checker, with the curve rule, had called it VALID beforehand.

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

## Close

- **What happened:** the first `--fresh` render landed on the build tutorial, and the refused-screen guard raised (distance 1.709, exit 3; evidence `screenshots/device_evidence/20261101-212401.txt`). That was the fourth bad first launch of the night (#21). The retry rendered: placement active, finished, peak 484, 9 frames.
- **What changed:** nothing but this report and the ledger.
- **Evidence:** `play button: active` / `finish: finished (peak 484, 9 frames, sparkle burst)`. `task_check s46-t4`: in scope.
- **Declared outcomes against what happened:** both held.
- **Decisions made inside the task:** one retry, as budgeted.
- **For the record:** `plan.md` item 2: the first starter -> curve -> goal route is measured to finish. #21 gains tonight's count: the first launch after a cold boot was bad in 4 of 5 emulator boots (2 loading screens, 2 build tutorials; the `device offline` was a second launch), re-derived from the four run logs at close.
- **Friction:** none.
- **Next:** the session close.
