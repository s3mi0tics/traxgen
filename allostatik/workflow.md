# Workflow

This file holds the routines Claude runs at the start and end of every session in this project, plus the project-specific pieces those routines need. It's the operational half of your project config — identity, purpose, and domain context live in `project-instructions.md`; this file is procedure.

**This assumes local storage** — a repo or folder Claude can read and write (Claude Code, Cursor, or Claude Desktop with file access). A web / no-files "lite" path is a future addition, not covered here.

It comes in two parts:

- **Part 1 — Session routines.** The universal routines: session-open, drift-check, session-close, observation/decision capture, and handoff generation. They're the same shape in every project and ship as a working default.
- **Part 2 — This project's specifics.** The pieces those routines need from *this* project: which surfaces to drift-check, which files are canonical, any close steps unique here, handoff conventions, working notes. These are yours to fill in.

**Editing this file.** The Part 2 sections are yours — fill them in freely; that's the point of the file. The Part 1 routines are a different matter: they're the shared universal shape. To turn a routine *off*, log a skip row in `decisions.md` (a recorded decision, not a silent deletion). To supply project specifics a routine needs, use Part 2. Only edit a routine *body* when you genuinely need different universal behavior — and know that doing so forks your copy from the template's upstream version, so you'd re-pull the template to pick up later improvements. If you ask Claude to change a Part 1 routine body, it will surface that tradeoff and confirm before editing.

**How each routine works.** Every routine below has a cheap built-in check — a fast way to confirm it did its job. If a check fails, Claude follows the same pattern every time: **halt, surface what failed, and ask** before continuing. The checks fall into five kinds:

- **comparison** — does X match Y? (e.g., does the canonical file match what's deployed?)
- **output** — did the expected thing get produced? (e.g., was the handoff actually written?)
- **state** — is something in the state we expect? (e.g., does `git status` show the files we edited as modified?)
- **attribution** — does this carry the right source and pointers? (e.g., does the handoff point at the canonical files instead of restating them?)
- **capability** — is the needed capability available? (e.g., are the file tools attached and scoped to the project?)

**Three layers of catching.** These checks protect the system at three levels, so a miss at one level gets caught at another:

1. **Per-routine** — each routine's own check fails loud in the moment (halt → surface → ask).
2. **Per-session** — the close's reflective pass re-checks that the routines actually ran.
3. **Across sessions** — the session-open drift-check catches anything the previous close missed.

The principles these routines put into practice — checkpoints, side notes, single- and double-loop correction — live in your global preferences (Layer 1). This file operationalizes them; it doesn't restate them.

---

**Part 1 — Session routines.** The universal routines, the same shape across every project. Where a routine needs something specific to this project, it points at the matching section in Part 2.

## First run — set up the files

This routine covers a **fresh project**. If the project already has real content — code, a README, planning docs, rules files — use **First run — existing project (migrate)** below instead: it protects what the project already knows.

The first time you're in this project, the `allostatik/` files are template stubs — guidance inside, no project content yet. Before the normal routines apply, walk the adopter through filling them: don't hand over empty files, and don't silently fill them yourself. This runs once; after it, every session is Session-open → work → Session-close.

1. **Confirm the setup.** Check the `allostatik/` folder is in place and file access is scoped to it (the *Session open* capability check). If files are missing, help place them from the template first.
2. **Seed and walk each file, in dependency order.** `project-instructions.md` (what this project is — mode, purpose, domain notes) first, then `plan.md` (done / current / next), then the rest (`decisions.md`, `observations.md`, `vision.md`, `knowledge/`) as they earn content. For each: propose a first draft from what the adopter tells you, show it, and let them **keep / change / drop / add** before it's saved. The point is that they *experience* building the file, so they can maintain it after — not that it arrives pre-filled.
3. **Fill the placeholders** as you go — the `[ALL-CAPS-WITH-HYPHENS]` slots and `<angle-bracket>` command tokens (the drift-check's placeholder scan will flag any you miss).
4. **Deploy the pointer.** Put the short "this is an Allostatik project — load the `allostatik/` files and follow `workflow.md`" block into the project's instructions (the Project Instructions field, or `CLAUDE.md` on Claude Code) so every later conversation picks the files up.
5. **Confirm it took.** Start a fresh conversation and check Claude orients from the files. *Check (output):* the files carry real project content, placeholders are filled, and the pointer is deployed. *If it fails:* finish the missing piece before treating setup as done.

After this, the files self-instruct — a fresh conversation loads them and runs Session open below.

## First run — existing project (migrate)

Most projects arrive with history: a README, planning docs, conventions files, months of decisions embedded in prose. Migrating onto Allostatik means moving the *living* parts of that history into the canonical files without silently losing any of it. The failure mode this routine exists to prevent is **bulk seeding** — the AI reading everything and writing all the files itself in one pass. That feels efficient and demonstrably drops content; worse, the adopter never learns their own files. Walk, don't bulk.

1. **Inventory first.** List every context-bearing artifact in the project — README, planning/TODO docs, rules files (`.cursorrules`, editor configs), architecture notes, informal decision records. Show the adopter the list and ask what's missing. *Check (output):* the adopter has confirmed the inventory is complete.
2. **Classify each source: live, archive, or fold-in.** For each artifact, agree: does it stay authoritative where it is (point at it — e.g. a rules file both surfaces already read), become a historical archive (point at it as history), or fold into a canonical file (its content moves)? Record the classification — it becomes a `decisions.md` row at the end. *Check (comparison):* every inventoried artifact has exactly one classification.
3. **Walk each canonical file, one at a time, drawing on the sources.** In the same dependency order as the fresh-project routine (`project-instructions.md`, then `plan.md`, then the rest). For each: propose a draft **derived from the classified sources**, show it with a note of *which source each part came from*, and let the adopter keep / change / drop / add before it's saved. Never write more than one file ahead of the adopter's review. *Check (state):* no canonical file was written without the adopter seeing its draft.
4. **Cross-check for silent drops — mandatory, not optional.** After the last file: re-read each source artifact against the canonical set and name anything that appears nowhere — content neither folded in, nor pointed at, nor consciously archived. Surface the orphans and let the adopter decide their home. *Check (comparison):* every load-bearing item in the sources is accounted for. (This step exists because unreviewed migration demonstrably drops content; it is the migrate-branch's version of "confirm it landed.")
5. **Record the migration.** A `plan.md` session-log entry (what moved, what's archived, what's live-in-place) and a `decisions.md` row for the classification map (e.g. "docs/PLAN.md = archive; .cursorrules = live for code conventions, pointed at not duplicated"). *Check (output):* the next session can reconstruct what happened from the files alone.
6. **Deploy the pointer and confirm it took** — same as the fresh-project routine, steps 4–5.

*If the adopter asks you to "just fill everything in": explain the drop risk in one sentence, offer the walkthrough, and if they still want bulk seeding, do it — then treat step 4's cross-check as REQUIRED and tell them what it found. The gate bends to the human; the verification doesn't.*

## Session open

Run these at the start of every session, in order. Don't begin substantive work until all five are done.

1. **Verify capability.** Confirm the tools this session needs are attached and scoped to the project — e.g., file access pointed at the right repo. *Check (capability):* the tool reports the expected scope. *If it fails:* halt, say what's missing, and fall back to whatever access is available — or ask the user to attach it — before continuing.
2. **Read the required context.** Read the handoff, if there is one, and the files it points at — fully, before responding. *Check (output):* you can name what you read. *If it fails:* don't proceed on assumption; ask for the missing file or the command that produces it.
3. **Run the drift-check.** Compare the canonical files against what's deployed, per the **Drift-check** routine below. *Check (comparison):* canonical matches deployed. *If it fails:* halt and surface the mismatch before anything else — a stale deployed surface silently undoes this session's work.
4. **Acknowledge the state in your own words.** Briefly restate what's done, what's open, and the immediate task. *Check (output):* the restatement is yours, not a copy of the handoff — putting it in your own words is what surfaces misunderstandings. *If it fails:* flag anything that doesn't line up with what you read.
5. **Propose a starting point and confirm.** Name where you'd start and why, then wait for the go-ahead. *Check (state):* the user has confirmed. *If it fails:* don't just begin — a wrong starting assumption is cheapest to fix right here.

## Drift-check

Your canonical files (in the repo) are the source of truth. Some are also *deployed* somewhere Claude reads them — your global preferences get pasted into Claude's Custom Instructions, your project instructions into the project's instructions field. These drift apart when one side is edited and the other isn't (you update the file but forget to re-paste, or paste a change without saving it back). This routine catches that at the start of a session, before stale config silently overrides the work. Run four checks; each fails the same way — **halt, surface the mismatch, and ask**.

1. **Canonical vs deployed.** For each pairing listed under *Drift-check surfaces* (Part 2 — your global preferences and project instructions, by default), compare the canonical file to what's actually deployed. One deployed surface can mirror **more than one** canonical file — e.g. if you merged your environment (L3) into Custom Instructions alongside your global preferences (L1), that single field reflects both files — so check *every* canonical file mapped to a surface, not just the one most recently edited. *Check (comparison):* each matches its portion of the deployed surface. *If any doesn't:* halt, show the difference, and ask which way to reconcile — usually re-pasting the canonical version, but confirm, since the deployed side may hold an edit that never made it back to the file. Re-read *both* sides at check time — the canonical file from disk and the deployed surface as it actually reads now — rather than trusting what either looked like earlier in this conversation; comparing your memory of a file against your memory of a setting is not a drift-check. If the deployed side can't be re-read on this surface (e.g. paste-loaded, with no way to read back what's actually in Custom Instructions), say so plainly and treat the check as *un-runnable* — carry it as a reconcile-before-work item — rather than passing it by assumption.
2. **Imports vs folder contents.** Compare the files listed in `CLAUDE.md` (the project's dependency manifest) against what's actually in the `allostatik/` folder. *Check (comparison):* every listed file exists, and every file that should load is listed. *If not:* halt and surface the gap — a broken import (listed but missing) or an orphan (present but never loaded).
3. **Unfilled placeholders.** Scan the template-derived files across `allostatik/` for placeholders that were never filled in — `<angle-bracket>` tokens in commands, `[ALL-CAPS-WITH-HYPHENS]` slots in prose. *Check (comparison):* none remain. *If any do:* surface them so they get filled (or confirmed intentional) rather than shipping a half-configured file.
4. **Session-log freshness.** Compare `plan.md`'s newest session-log entry against what actually happened last session. If the log is behind — the last session's work isn't recorded — a previous close was **skipped**, and the state you're about to trust is stale. *Check (comparison):* `plan.md`'s session log reflects the last session. *If it fails:* backfill the missing record (from that session's own account) and reconcile `decisions.md` / `observations.md` **before any new work**. This is the guard that catches a skipped close — the canonical-vs-deployed checks above can't, because a skipped close leaves the deployed surfaces untouched too; only the record falls behind.

## Session close

Run these at the end of every session, in order. This is the one routine the system's compounding depends on the user actually running — everything else loads on its own, but the close is what carries state forward. Treat it as run-every-session, not optional.

Where a step's mechanism depends on your setup — can Claude write files directly? do you use version control? — it names the common cases. **The handoff (step 6) is the last step that carries state forward; write it only after everything else is confirmed saved**, so it describes real state, not assumed state. Step 7 closes the session. Any project-specific close steps (see *Closing-protocol additions* in Part 2) run alongside these — after the persist/confirm steps and before the handoff.

1. **Reflective pass.** Before writing anything down, take one fast pass over the session: any friction points worth fixing? any higher-level framing the step-by-step view missed? any content you produced that's referenced but never written into a canonical file? *Check (comparison):* nothing derived this session is left orphaned — mentioned but not saved anywhere durable. *If it fails:* name it now, so it lands in the right file below.
2. **Update canonical state.** Fold the session's changes into the files that own them: current state / in-flight work → `plan.md`; newly locked choices → `decisions.md`; new process patterns or re-firings → `observations.md`; direction shifts → `vision.md`; plus any project-specific canonical files listed under *Canonical files* (Part 2). *How they get saved depends on your setup:* Claude writes the files directly (file access to the repo), or hands you each updated file to save yourself (paste / manual-write surfaces). *Check (output):* every change has a durable home.
3. **Re-paste edited surfaces (SEND).** If you edited a file that's also deployed (global preferences → Custom Instructions; project instructions → project field), re-paste it so the deployed copy matches. *Check (comparison):* deployed now matches canonical. *If you can't re-paste this session:* carry it as a "DO BEFORE THIS HANDOFF IS CONSUMED" item at the top of the handoff, so the next session reconciles before doing anything else.
4. **Confirm it landed** — use the strongest check your setup allows:
    - **Version control:** run `git status` and confirm every file you edited shows modified, and nothing you didn't.
    - **Files, no version control:** list or re-read the changed files to confirm the edits are actually on disk — a directory listing with timestamps, or re-reading the end of each file. (*Working notes* in Part 2 can supply the exact command for your system.)
    - **Manual placement:** confirm with the user that each updated file was saved into place.

    *Check (state):* what's actually saved matches what you changed. *If it fails:* a write didn't land — redo it and re-check before continuing.
5. **Commit, push, confirm** *(version control only — skip otherwise)*. Commit with an explicit file list, push, and confirm the remote is in sync. *Check (state):* clean working tree, remote matches local. *If it fails:* resolve before moving on.
6. **Write the handoff — last.** Everything above is now confirmed saved (and pushed, if you use version control), so the handoff describes real state. Produce it per **Writing the handoff** below. *Check (output):* the handoff exists and points at the canonical files rather than restating them.
7. **Name the session and confirm it's done.** Suggest a short, descriptive name for this session — what it accomplished — so the conversation is easy to find later, then confirm the session is complete for now. *Check (output):* a name is offered and the wrap is acknowledged.

## Capturing observations and decisions

This is the routine that lets the system improve itself — the engine behind "every session is a chance to refine how we work." Three parts:

**Capture as you go.** When a process pattern shows up mid-session — a friction, a recurring snag, something about *how* you're working rather than the work itself — note it as a candidate observation right then, so it isn't lost by close. A candidate becomes a permanent, promoted observation once it recurs enough to be real rather than noise (default: three firings across sessions; *Working notes* in Part 2 can set a different threshold). *Check (output):* the pattern is written down as a candidate, not just mentioned.

**Lock decisions by writing them down.** When a choice gets settled, record it as a row in `decisions.md` — first confirm it's actually settled, then write it. A decision that only lives in the conversation isn't locked; the next session won't see it. The written row *is* the lock. *Check (state):* the settled choice exists as a row, not just an agreement in chat.

**Invite feedback, and show it working.** Let the user steer the loop. Two markers, available anytime:

> Give feedback anytime — say **"checkpoint"** to review how we're working together, or **"side note"** to flag one thing without stopping the flow. Either gets captured as we go and folded into proposed updates at the close (you approve before anything's applied); anything bigger than this session carries to the next one.

When the user uses them, *show the loop working* — point to the concrete capture and where it'll land ("noted as a candidate observation; it'll go to `observations.md` at close") rather than just thanking them. As the habit forms, ease off the prompting — the reminder is scaffolding, not a permanent fixture. (What "checkpoint" and "side note" mean is defined in your global preferences; this routine just runs them.)

## Writing the handoff

A handoff is the message that kicks off the next session. It carries forward what that session needs — but as *pointers, not copies*: the durable detail already lives in your canonical files, and the handoff's job is to point at it, not duplicate it. A handoff that restates `plan.md` and `decisions.md` goes stale the moment those files change.

What every handoff carries:

- **Next-session goals** — what to accomplish next, in a suggested priority order the next session can adjust, each with a one-line "why."
- **Required reading** — the specific files (and sections) to read first, in order. Point at them; don't paste them.
- **A pointer to the close routine** — a reminder to run this file's session-open and session-close steps.

**Size it to layer maturity — fat when empty, lean when mature.** Early on, when your canonical files are thin, the handoff carries more itself (there's little to point at yet). As the files fill in, the handoff gets leaner — goals plus pointers — because the detail now lives where it belongs. The weight of the handoff is inversely proportional to how mature your layers are.

**Blocking carries go first.** If the close deferred something that *must* happen before the next session does anything else — most often a deployed-surface re-paste that didn't get done (close step 3) — put it at the very top under a heading like **"DO BEFORE THIS HANDOFF IS CONSUMED,"** with the exact action. The next session's drift-check will expect it resolved before work begins.

Add any conventions specific to *this* project's handoffs under *Handoff conventions* in Part 2.

*Check (attribution):* the handoff points at the canonical files rather than restating them. *Check (output):* it names next-session goals and required reading, and surfaces any blocking carry up top.

---

**Part 2 — This project's specifics.** Fill these in for your project. Keep the `<TOKEN>` placeholders and commented scaffolding even after you fill a section in — they show the next adopter (and your next project) what belongs there.

## Canonical files

The close's *update canonical state* step (Part 1) routes each kind of change to the file that owns it. The universal four — `plan.md`, `decisions.md`, `observations.md`, `vision.md` — are named in that step; don't restate them here.

Use this section to declare anything *project-specific* about that roster: extra files this project treats as canonical state, or a note if you've dropped or renamed one of the four (a drop is a `decisions.md` skip row).

<!-- Project-specific canonical files — one per line: `<FILE>` — <what it owns>. -->
<!-- Example: `backlog.md` — prioritized work not yet pulled into `plan.md`. -->

## Drift-check surfaces

The drift-check's *canonical vs deployed* check (Part 1) compares each canonical file against the place it's deployed, for the surfaces *this project lists here*.

Two surfaces ship by default — most projects have exactly these:

| Canonical file | Deployed at |
|---|---|
| `global_preferences.md` (L1) | Claude's Custom Instructions |
| `project-instructions.md` (L2) | this project's instructions field |

Add a row for any other surface where a canonical file is deployed and could drift. **A surface can appear more than once** — if you merge layers into a single deployed field (e.g. L3 environment into Custom Instructions alongside L1), list each canonical file as its own row pointing at that shared surface, so the drift-check compares all of them:

<!-- Additional surfaces — one row per pair: `<CANONICAL-FILE>` | <where it's deployed>. -->
<!-- Example: `.cursor/rules/*.mdc` | the Cursor rules a canonical file is mirrored into. -->

## Closing-protocol additions

The universal close (Part 1) runs the standard steps — from the reflective pass through committing and naming the session. List here any close steps that exist **only for this project**; they run in addition to those, not instead of them. (To turn *off* a universal step, use a `decisions.md` skip row.)

<!-- Project-only close steps — each with a one-line cheap test (how you confirm it ran), per the test-per-routine pattern. -->
<!-- Example: **Refresh the published docs** — after the commit lands, run the site build and commit the output. Test (state): the build succeeds and the generated files show as committed. -->

## Handoff conventions

The *Writing the handoff* routine (Part 1) holds the universal shape — next-session goals, required reading, a pointer to the close routine, blocking carries up top, and sizing the handoff to how mature your layers are. Add here any conventions specific to *this* project's handoffs.

**Deliver the handoff as a file, not as inline prose.** Write it to an outputs folder as `traxgen-handoff-<YYYY-MM-DD>.md` and hand the file over. In a chat transcript the start and end of a handoff are ambiguous — it runs into the surrounding conversation, and finding it again means scrolling. A file has unambiguous boundaries, survives scrollback, and can be opened alongside the next session instead of re-read in place. *Test (output):* the next session's opening message is a file, not a wall of text. (Raised 2026-08-07 after several handoffs delivered inline.)

**Handoff files stay local.** They are artifacts, not canonical state — nothing in a handoff is the source of truth for anything, so a committed handoff goes stale the moment `plan.md` moves. Don't commit them.

**Observation numbering runs cumulatively across sessions.** `observations.md` numbers are stable references; a handoff citing "#12" must mean the same thing next session. Never renumber.

<!-- Project-specific handoff conventions. Examples:
  - State to always carry (e.g. the current status of each layer or workstream).
  - A numbering scheme that runs across sessions (e.g. observations numbered cumulatively — don't restart per session).
  - Anything the next session reliably needs that the universal shape doesn't name.
-->

## Essentials bundle (optional)

Paste-loaded setups — where Claude can't read your files directly and you paste them in at session start — need a quick way to gather the canonical files into one paste. This section holds that command. **Direct-read setups (MCP, Cursor, Claude Code) don't need it** — leave the template below as-is.

If you do need it, the command concatenates your canonical files and pipes the result to the clipboard. The clipboard pipe differs by OS, so all three variants are inlined below — pick the one for your system.

<!-- Paste-loaded adopters: uncomment, set <PROJECT-ROOT> and your file list, then use the clipboard pipe for your OS.

{
  cd <PROJECT-ROOT> && \
  for f in allostatik/project-instructions.md allostatik/plan.md \
           allostatik/workflow.md allostatik/decisions.md \
           allostatik/observations.md <OTHER-CANONICAL-FILES> ; do
    echo "===== $f ====="; cat "$f"; echo ""
  done
} 2>&1 | <CLIPBOARD-PIPE>

Clipboard pipe by OS (replace <CLIPBOARD-PIPE>):
  macOS:               tee >(pbcopy)
  Linux:               tee >(xclip -selection clipboard)
  Windows (Git Bash):  tee /dev/clipboard
-->

## Working notes

Operational notes specific to how work runs in this project — conventions, quirks, and gotchas Claude should know while working. This is the *operational* half of the project's notes; identity, purpose, mode, and domain context live in `project-instructions.md` instead.

<!-- Project-specific operational notes. Examples:
  - Tool quirks and their workarounds (e.g. a tool that needs its output verified after each use).
  - Command conventions (e.g. always stage an explicit file list rather than everything).
  - The exact command this project uses to confirm edits landed (feeds close step 4).
  - A non-default observation-promotion threshold (feeds the capture routine).
  - Drafting or review conventions specific to this project.
-->

## Related files

- `global_preferences.md` (L1) — the principles the Part 1 routines operationalize.
- `project-instructions.md` — this project's identity, purpose, mode, and domain context (the counterpart to this file's working notes).
- The canonical state files — `plan.md`, `decisions.md`, `observations.md`, `vision.md` — that the close reads from and writes to.
