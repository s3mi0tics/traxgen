# s52-t1 — the open's log command (#34), and whether a new build could keep the name 2.8 (#33)

**Status:** DONE

**In one paragraph:** Both answered by reading. #34: the open's command stops at the first `##` heading in `log.md`, and every entry from s42 on sits below `## Retired 2026-09-11 (s34)` (line 74), so it prints s41. Dropping the `awk` and taking the last dated bullet in the whole file prints the newest entry. #33: the Play Store lists **2.8.1** (updated Oct 12, 2026), so the pending build does not keep the name 2.8, and preflight's exact `versionName` match refuses it: `parse_app_version` reads `2.8.1` and `2.8.1 == "2.8"` is false. No `versionCode` pin is needed for this release.

## Open (written before the work)

- **Goal:** answer open questions #34 and #33 by reading, with no change to any file but this report and the ledger.
- **Scope:** none beyond the ledger and this report.
- **Budget:** 15 minutes, no renders.
- **Done check:**
  1. *Step:* read the command's output against `log.md`'s headings; read the Play Store's listing for `com.ravensburger.gravitrax`.
  2. *True after:* #34 has a named cause and a one-line fix; #33 has the store's current version name, or a named reason it could not be read.
  3. *Miss cases:* the fix is proposed without being run against the file; the store page answers with a generic "Varies with device" and that is read as a version.
  4. *Reads:* `allostatik/log.md`; the `awk` line in `project-instructions.md`; the Play Store page as fetched.
  5. *Check:* the proposed command, run against `log.md`, prints the s51-or-newer entry, and the report quotes the store's version string verbatim or says it was not shown.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** #34: `awk '/^## /{exit} 1' allostatik/log.md | grep -E '^- \*\*[0-9]{4}-' | tail -n 1` printed the s41 entry; `log.md`'s only `##` heading is line 74, `## Retired 2026-09-11 (s34)`, and entries s42 to s51 plus the claude.ai chat's follow it. `grep -E '^- \*\*[0-9]{4}-' allostatik/log.md | tail -n 1` printed the 2026-11-03 claude.ai-chat entry, the newest. #33: WebFetch of the store page came back truncated; `curl` of `play.google.com/store/apps/details?id=com.ravensburger.gravitrax&hl=en_US&gl=US` (1,333,618 bytes) carried one version string, `[[["2.8.1"]]`, and the date `"Oct 12, 2026"`. `scripts/preflight.py:220` compares `found == expected` exactly; `_VERSION_NAME` captures `\S+`, so `2.8.1` is read whole and refused.
- **What changed:** this report and the ledger only.
- **Evidence:** the two command outputs above; `parse_app_version('    versionName=2.8.1\n')` -> `'2.8.1'`, `== '2.8'` False.
- **Decisions made inside the task:** fix #34 by changing the command, not by moving `log.md`'s entries above the Retired heading -- the command is one line in two files, the move would churn ~80 lines of the record, and entries keep being appended at the end.
- **For the record:**
  - `plan.md` #34: answered s52-t1 -- the command stops at the Retired heading; the fix is to drop the `awk '/^## /{exit} 1'` stage, in `project-instructions.md`'s bundle and `deployed/claude-ai-project-instructions.md`, then re-paste the claude.ai Project instructions field (Colby's hands).
  - `plan.md` #33: answered s52-t1 -- the pending release is 2.8.1 (store, 2026-10-12); the exact-match check refuses it. A `versionCode` pin waits for a build that keeps an old name.
  - `knowledge/environment.md`: the pending store release is 2.8.1, dated Oct 12, 2026 (the 2026-10-07 date it records came from a different reading; the store page shows 10-12 now).
- **Friction:** none.
- **Next:** s52-t2, item 23's leftover from frames on disk.
