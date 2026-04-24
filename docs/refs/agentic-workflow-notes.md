<!-- docs/refs/agentic-workflow-notes.md -->

# Agentic Workflow Notes

Accumulated learnings about working with AI coding agents and building agentic
systems. Two loose scopes:

- **Building with the Claude API / MCP / tool use** (writing code that drives
  LLMs with tools).
- **Using delegation tools** (Cursor, Claude Code, and similar) as part of
  day-to-day development.

These are not mutually exclusive, and patterns often transfer between them.

Updated opportunistically — especially at handoff time.

---

## Tool selection: Cursor vs Claude Code

**Working hypothesis, not a commitment.** They serve different modes:

- **Cursor** — tight inline loop. You drive, AI assists. Tab completion,
  live diffs, multi-model routing. Good daily driver for exploratory edits
  and small-scope changes where feedback needs to be immediate.
- **Claude Code** — long-horizon autonomous tasks. Delegate a multi-step
  goal (read N files, coordinate edits across M, run tests, iterate on
  failures). Terminal-native, so plays well with existing `uv run`,
  heredoc, and `tee >(pbcopy)` workflow. API-metered, so a big task =
  a real bill.

**Heuristic:** if the task is "help me edit this buffer," reach for Cursor.
If it's "go implement X across the repo and come back when tests pass,"
try Claude Code on that specific task.

Tracking outcomes from both as they accumulate.

---

## Patterns from working with Claude in this chat interface

Things that have proven to work well and are likely to transfer to
Cursor/Claude Code/custom agentic workflows:

### One-command-at-a-time discipline
In back-and-forth sessions, giving exactly one command and waiting for
output produces much higher-quality sessions than stacking "run this,
and if it looks right run this next." The agent's reasoning stays
grounded in actual output rather than predicted output. Worth enforcing
explicitly in agent prompts / system instructions.

### Preemptive cleanup over deferral
When the agent offers a choice between cleaning something up now vs.
deferring, taking the "now" option tends to save net time. Future
sessions don't inherit the mental model that made the deferred cleanup
trivial.

### Physical-world sources beat web sources for niche domains
For traxgen specifically: physical inspection of the PRO set > Fandom
wiki > Ravensburger product listings. The agent needs to be explicitly
told this priority order, because its default is to trust the web. This
probably generalizes: for any niche technical domain, the "authoritative"
web source is often wrong, and the agent needs a priority hierarchy
baked into its prompt.

### Source-of-truth priority should be explicit in agent prompts
Related to the above. If an agent is going to make factual claims about
a domain, its system prompt should state "when X conflicts with Y, prefer
X" rather than leaving resolution to its priors.

### When each fix creates a new problem, stop and reconsider
Watch for the pattern: error A → workaround → new error B → workaround →
new error C. When the errors are *different* (not the same error
returning after a fix), that's a signal the whole approach is off the
rails, not that one more fix will crack it. The session that surfaced
this: iOS sideload dead → Android pivot → writable-system overlay →
APEX cert store discovery → bind-mount dance → network broken. Each
step was locally rational; the cumulative path was unproductive.
Noticing the pattern early and stopping to reframe is cheaper than
pushing through.

### Empirical test beats vendor docs for niche questions
Generalization of the physical-inspection rule above. When the
question is "does this product do X?", App Store descriptions,
vendor support pages, and marketing copy are unreliable. They
describe intended behavior, not actual behavior. If the question
is cheap to test empirically, test it — don't search for
documentation first. Specific example from this session: the iOS
GraviTrax app not accepting `.course` files via AirDrop wasn't
findable in docs; one AirDrop attempt answered it definitively.

### Consumer-mobile HTTPS interception is not a 15-minute task
If a task requires intercepting HTTPS traffic from a third-party
mobile app, budget an hour minimum for setup-and-smoke-test and
assume more if the target app pins certs. Both iOS (profile trust,
potential pinning) and Android 14+ (network security config
defaults user-certs-untrusted, APEX conscrypt overlay) have real
setup costs that aren't obvious upfront. For agentic workflows
where cost matters: don't accept "I'll just MITM the app" as a
step in a larger plan without pricing in that hour.

### Android Studio's Network Inspector is ideal but only for debuggable APKs
Production APKs from the Play Store are `debuggable=false` and
Studio's Network Inspector won't attach. Worth knowing before
spending time on mitmproxy setup for a third-party app — the
apparently-obvious path is closed.

### Time-box exploratory and reverse-engineering work up front
When the work is exploratory (will this even succeed?) with a capped
upside and open-ended downside, declare the budget before starting,
not mid-session. The 2026-04-24 traxgen session had a 4-hour ceiling
for app-integration work written into the opening plan. In practice
the answer came at ~2 hours. The budget was still useful in that
scenario because it made "stop now, we've won" a principled decision
rather than a judgment call. Had the work gone sideways, the same
budget would have made "stop now, this isn't working" principled
too. Without a pre-declared budget, both endpoints are harder — the
"we've won" case drifts into over-verification, and the "not working"
case drifts into sunk-cost pushing.

Applies to: reverse-engineering, debugging an unknown failure mode,
evaluating whether a library/approach will work, any "spike" in the
XP sense. Doesn't apply to: incremental feature work where progress
is linear and a budget would just be noise.

### Name the project's purpose before picking a technical direction
When a project could reasonably go several technical directions,
the deciding question is often non-technical: what is this *for*?
The 2026-04-24 traxgen session surfaced this explicitly — "portfolio
project that also has real user value" changed the path from "defer
M6 and build the generator" to "bound the M6 investigation, then
generator." Without naming the purpose, we'd have debated paths on
technical merits alone and missed that portfolio value + fan value
together argued for a different shape than either alone.

Signs the project's purpose should be named explicitly: when
reasonable options point in incompatible directions, when "what
should I build next" has no clear answer, when you notice yourself
re-litigating the same tradeoff across sessions. The question to
ask (of oneself, or of the user): "A vs B vs C — which of these
outcomes do you actually want?" Not "which is technically better."

### "Each fix creates a new problem" — applied proactively
The 2026-04-22 traxgen session surfaced this pattern the painful
way (iOS → Android → writable-system → APEX → broken network).
The 2026-04-24 session applied it proactively: before starting the
iOS retry, we pre-declared "if GraviTrax traffic shows a TLS error
in mitmproxy, we stop iOS and pivot — we do not start debugging
cert pinning." The rule never triggered (no pinning), but having
the rule in place meant there was no ambiguity about what "stop"
meant if it had.

Generalizes to: any session where we can predict the failure mode
in advance. State the stop condition before starting. If the
condition is met, stop is the default, "push through" requires
explicit argument.

### Multi-edit patch scripts with exact-match validation beat sed for documentation edits
When updating a document with multiple independent edits (e.g.,
PLAN.md with 9 edits across milestones, decisions table, unknowns,
resolved list), a Python script that applies each edit with strict
"old must match exactly once" validation is strictly better than
sed. Reasons: (a) you see exactly which edit is about to run, with
a description; (b) if the document has drifted from what you saw,
the script errors out on the specific mismatched edit instead of
silently applying wrong changes; (c) delta accounting (net chars
added/removed per edit) is visible, giving a sanity check on
whether each edit is the size you expected.

Minimal pattern:

    EDITS: list[tuple[str, str, str]] = [
        (description, old, new),
        ...
    ]

    for desc, old, new in EDITS:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"edit {desc!r}: matched {count} times, expected 1")
        text = text.replace(old, new)

The "matched {count} times, expected 1" check is the critical part
— it catches both "old text has drifted" (matches 0) and "old text
is too generic and matches in multiple places" (matches N > 1).

---

## Patterns from building agentic systems (placeholder)

To be filled in as Colby starts the build-side work. Likely topics:

- MCP server patterns that have worked / haven't
- Tool-use prompt engineering learnings
- Cost management strategies (caching, model selection, batching)
- Failure modes and recovery patterns

---

## Session-specific findings worth promoting

_Learnings that started as session-specific but generalized.
Promote here when they've survived at least one subsequent session._

(empty for now)


## 2026-04-24 M6.a session

### "Probe minimally, write, iterate" worked

Session opened with exactly one open question that probing could answer:
what the upload endpoint returns on malformed input. Policy going in
was "one probe, then write." One truncated-payload probe resolved it —
server returned 200 and a fresh code, telling us the endpoint is
content-agnostic at upload time. No further probing (oversized,
missing headers, rate limits) because the answer to the first probe
already told us there's nothing useful to design around.

The rule of thumb: probe until the next probe would not change what
you write, then stop. "Probe until you understand everything" is a
trap — you can always think of another experiment. For M6.a, "one
probe" was correct; for the retainer-family probe in M4, "many probes"
was correct. The difference is that M4's probes each updated the
schema interpretation (changing what the validator would do); M6.a's
hypothetical second probe would have updated nothing.

### Narrow lint scope when there's pre-existing debt

Ran `uv run ruff check .` at the start of the final-checks step and
got 61 errors. Looked alarming for a moment — then every single one
turned out to be in files we hadn't touched (probe scripts, test_hex,
test_validator, _diff, hex, serializer, validator). Our three M6.a
files were clean.

Lesson: when a repo has accumulated pre-existing lint debt, a broad
lint run during review buries the signal. Narrow to the files actually
changed in the current work. Once the current work is confirmed
clean, then a separate pass can triage the pre-existing debt as its
own chore — don't mix "this session's lint" with "the repo's lint."

We did the triage anyway (auto-fixed 23 of the 61, left 38 as a new
deferred-cleanup item) but committed it as its own commit, not as
part of M6.a.

### Four-cluster commit untangling

When `git status` came up at the end of M6.a, the working tree had
four overlapping change clusters that had never been properly
separated:

1. Last session's doc updates (README, PLAN, agentic-workflow-notes,
   upload-api.md) — never committed in the previous session.
2. This session's M6.a work (uploader.py, test_uploader.py,
   pyproject.toml addopts change).
3. The CLI wrapper (scripts/upload_course.py).
4. Ruff auto-fixes touching 7 unrelated files (validator.py,
   serializer.py, probe_*.py, tests/test_hex.py, tests/test_validator.py).

Instead of one giant "M6.a and everything else" commit, we staged and
committed each cluster separately — four commits, each with a focused
message. The extra two minutes of filepath juggling paid off: if any
one commit breaks something later, bisect points at it cleanly.

Generalizable rule: before committing a session's work, run
`git status` and categorize the changes by *why* they exist. If
there's more than one "why," commit them separately. A commit's
mental model should be one paragraph — if you'd need two to explain
it, it's two commits.

### Living-docs commit at session end, not mid-session

Handoff prompt says "propose updated versions at session end" and
this session confirmed the value. The PLAN.md changes needed to
reflect M6.a's completion — not an intermediate state. Attempting to
update PLAN.md mid-session would have meant revising it every time we
learned something new (the probe finding, the 38-remaining-lint
number, the exact commit hashes). By batching at the end, each
living-doc change is a single stable edit against a known state of
the world.
