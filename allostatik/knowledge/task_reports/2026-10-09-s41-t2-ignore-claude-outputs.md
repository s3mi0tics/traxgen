# s41-t2 — git ignores `Claude outputs/`

**Status:** DONE

**In one paragraph:** `.gitignore` already had a handoff rule, `outputs/`, added 2026-08-23 as the cheap test for "handoffs stay local". It never matched the folder handoffs actually land in, `Claude outputs/`, so the convention went unenforced and an s37 handoff sat untracked and failed s41-t1's scope check. The real folder name is now ignored, and the file is untouched.

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

- **What happened:** Added `Claude outputs/` to `.gitignore` under the existing handoff comment.
- **What changed:** `.gitignore`.
- **Evidence:** `.gitignore:61:Claude outputs/	Claude outputs/traxgen-handoff-2026-09-21-s37-to-s38.md`; `ls` still lists the file; `s41-t2: in scope -- 1 files changed since open commit 9b6470a, all declared`.
- **Decisions made inside the task:** Kept the old `outputs/` line, because some surface may still write there.
- **For the record:** `observations.md`, a firing of "a check that was never shown to fire": the 2026-08-23 ignore line was written as the convention's cheap test and named the wrong folder, so for seven weeks it tested nothing. Nobody had ever run `git check-ignore` against a real handoff path.
- **Friction:** none.
- **Next:** s41-t3, upload the two goal variants and capture their frames.
