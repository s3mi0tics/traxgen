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
