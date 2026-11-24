# s52-t1 — the open's log command (#34), and whether a new build could keep the name 2.8 (#33)

**Status:** OPEN

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
