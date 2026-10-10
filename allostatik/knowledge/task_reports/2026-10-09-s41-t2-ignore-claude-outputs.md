# s41-t2 — git ignores `Claude outputs/`

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Make git ignore `Claude outputs/`, where handoffs are written and left uncommitted by convention, so an old handoff there no longer fails every task's scope check.
- **Scope:** `.gitignore`
- **Budget:** 5 minutes.
- **Done check:**
  1. *Step:* add `Claude outputs/` to `.gitignore`.
  2. *True after:* `git status` no longer lists `Claude outputs/`, and the handoff file in it is untouched.
  3. *Miss cases:* the pattern doesn't match the folder name, because of the space; the file got moved or deleted instead of ignored.
  4. *Reads:* `git check-ignore -v` on the handoff file; `ls` of the folder.
  5. *Check:* `git check-ignore -v "Claude outputs/traxgen-handoff-2026-09-21-s37-to-s38.md"` names the new `.gitignore` line, and `ls` still shows the file.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close
