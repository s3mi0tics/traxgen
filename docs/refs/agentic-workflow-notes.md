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


## 2026-04-24 M6.b session

### Silent clipboard failures can invalidate hours of test results

When a test loop involves copy-pasting short strings between two
devices (Mac → iPhone in this case, via iCloud Universal Clipboard),
and the clipboard sync silently fails, the user keeps pasting the
*last successful* string while believing they're pasting the new
one. Every test renders the same output because it's literally the
same input. From the debug perspective, this looks like "the
generator produces consistent output regardless of what we change"
— which sends debugging in exactly the wrong direction.

Lesson: in any manual test loop with a copy-paste step, **verify the
input got through** before interpreting the output. Options: type a
sentinel character the user doesn't expect, display the code on-screen
at the testing device for visual comparison, or (the real fix)
automate the step so there's no clipboard involved.

This failure mode is particularly insidious because:
- The user had no indication the clipboard was broken (it worked
  for normal copy-paste during other tasks).
- The "same result every time" pattern rationalizes well as
  "something about our generator is wrong in a specific way" — i.e.
  the false hypothesis is plausible.
- Every new hypothesis test gets "confirmation" from the ghost data.

Related lesson: **confirmation of a result must include confirmation
that the input reached the system.** This is a pattern that should
appear in any automation we build going forward — log the exact bytes
that were sent to the target, not just the result from the target.

### Build an oracle from the real system's own output

When reverse-engineering a data format, it's tempting to guess-and-
check: write some bytes, feed them to the target, see what happens.
This burns iterations. A much cheaper technique: use the real
system to produce its own output, capture those bytes, then you have
a reference to compare against.

For traxgen this meant: build a minimal course inside the real
GraviTrax app, save it to get a share code, download the bytes via
the existing download API, and now we have byte-level ground truth
for what the real system considers a valid minimal course. Immediately
revealed a schema version mismatch (app writes v7, we know v4) that
could have been chased for hours otherwise.

This works whenever the target system has:
- A persistent storage/export path (save, share, download).
- A way to read back its own exports (download API, share-code
  resolution, etc).
- A minimal input surface (the ability to create a small example).

Generalizes to: protocol reverse-engineering, binary format work,
API response diffing, storage schema inference. Any time the question
is "what would the real system produce for case X?", ask the real
system instead of guessing.

### Byte-by-byte parser traces reveal schema deltas precisely

When a parser fails on a file at an unexpected point ("100 is not a
valid LayerKind" when we expected kind=0 for a baseplate), the
useful debugging move is to walk the reader through the file
manually up to that point, printing each read with its offset and
value. You see exactly where alignment starts to drift.

For this session, the parser failed at "read layer_kind = 100"; the
byte-trace showed the reader was at offset 0x3A trying to interpret
bytes that we'd read in v4 at offset 0x3E as layer_kind. The 4-byte
offset delta — plus the clear presence of the value `0x0d = 13` at
the spot where v4 has nothing — revealed the v7 schema insertion
with high confidence.

Pattern to reuse: when a parse fails at field X with a surprising
value, print each field the parser just read with its offset. The
alignment drift tells you where the structural difference lives.
`scripts/trace_both.py` in this repo is a concrete template for
doing this against two files simultaneously (the failing one vs. a
known-good one).

### Manual verification is a production blocker, not just a speed issue

Intuition going into M6.b was "typing share codes is slow but it
works." Reality: the slow loop *plus* the silent-failure mode
(copy-paste ghost) meant verification was unreliable, not just slow.
Those are very different problems. Slow verification can drive
iteration if each cycle is trustworthy. Unreliable verification
poisons debugging because "same output" could mean "my change
didn't take effect" or "my change took effect and was silently
ignored" or "my change was discarded by the test harness." You
can't tell which.

Automation was the right pivot — not because it's faster, but
because it collapses the ambiguity: the automation log shows the
exact code that was typed and the exact screenshot that resulted.
The same failure mode becomes a 5-line diff in a log, not an
undetectable ghost.


## 2026-04-25 M6.c session

### Tooling-first preference (Colby's working style, made explicit)

Colby strongly prefers building tooling that automates a repeated
manual step over executing the manual step many times. If a workflow
involves more than ~3 manual clicks/drag-and-drops/copy-pastes that
will need to be repeated, the right move is to stop and build the
tool, even if it means a 20-30 minute detour.

Claude should proactively flag this, not wait to be asked:

- If a flow is being done manually that could be scripted — propose
  the script. Don't keep walking through the manual flow.
- If file-sharing through chat upload is becoming the bottleneck —
  recommend Claude Desktop with filesystem MCP, or Claude Code (which
  has direct file access). Setup is a one-time ~5-min cost that pays
  back immediately.
- If the same coordinate sequence is being typed repeatedly — wrap
  it in a Python function or shell function before the third
  repetition.
- If the same diagnostic is being run by hand each session — make
  it a `scripts/` entry.

Concrete examples from the M6.c session that should have been caught
earlier:
- Dragging emulator screenshots from the side-toolbar camera into
  Claude chat: should have suggested an `adb screencap`-based shell
  function (`shot <name>`) at message ~2, not message ~30.
- Walking through 12 emulator taps manually for two test codes:
  should have offered the Python harness *before* the first walk-
  through, not after the second was about to start.

### Use the target system's own UI as a validity oracle

Generalization of the "oracle from real system's output" pattern
from the M6.b session. Beyond binary-format ground truth, the target
system often has UI affordances that classify input correctness for
free. For traxgen: the GraviTrax app's play button is solid-green
when a course is valid by the app's rules and outline-only when it's
not. We don't need to write a validator that reproduces the app's
judgment — we capture a screenshot and sample the button color.

More generally: when reverse-engineering or building a generator
for a real system, look for places the system already exposes its
own correctness judgments. Disabled buttons, validation badges,
error toasts, status indicators — these are oracles you don't have
to build. Cheaper than recreating the system's logic in your code,
and self-updating: if the system's rules change, the oracle reflects
that automatically.

Limit: only works when the oracle is observable in a screenshot or
automation-readable state. Some systems hide their judgments inside
internal animation timing or sound effects — those don't generalize.

### Pixel sampling beats CV for fixed-position UI elements

The M6.c validity oracle is implemented as a 12×12 pixel sample at
a fixed coordinate, classified on min-RGB-channel. Total: 20 lines
of code, ~50ms per classification, no model files, no training. We
considered piece-level computer vision ("is the STARTER at hex
(-2,3)?") and rejected it as overkill — the play-button signal is
a binary classification at a known location, not an open-ended
scene-understanding problem.

Rule of thumb: for fixed-resolution, fixed-position UI elements with
known visual states, sample the pixels and threshold the values.
Reach for CV only when (a) position varies (camera pans, scrolls),
(b) state space is open-ended (object detection, OCR), or (c) the
visual difference between states is subtle and noise-prone.

Calibration: collect a known-state pair (one positive, one negative),
sample both, pick a threshold midway between the readings. The M6.c
session pair X3WEQ6F296 (valid, min_channel ~234) and MT756NLLMI
(invalid, min_channel ~124) gave a wide enough gap that any
threshold in [180, 220] would work; we picked 220 for safety margin
on the negative side.

### Heredocs scale; long-file copy-paste doesn't

When Claude generates a 200+ line file in chat, the user has two
ways to land it on disk:
1. Copy-paste from the artifact panel into a text editor.
2. Run a `cat > path << 'EOF' ... EOF` heredoc that Claude generates.

Option 2 is faster *if* the file content has no nested heredocs and
no characters that interact with shell quoting. The M6.c session's
200-line `traxgen/android.py` landed cleanly via heredoc. The
previous M6.b session had an attempted heredoc fail because the
file content contained markdown backticks and triple-quoted Python
strings that interacted with the shell parser.

Rule: heredocs work for pure code (Python, JSON, etc.) without
embedded shell metacharacters, single quotes around the EOF
delimiter (`<< 'EOF'`) to suppress shell expansion, and no nested
heredocs. For files containing heredocs themselves, or markdown
with code blocks, use the artifact-copy path.

### Multi-edit patch script reused effectively

The pattern from M6.a (Python patch script with exact-match
validation) reused twice in M6.c: once for the gitignore update,
once for the multi-doc living-doc updates at session end. Worth
promoting from "useful technique" to "default approach for any
documentation edit involving more than one location."

Specifically: if you're updating PLAN.md, README.md, or any other
doc, and the edit is more than "add one paragraph at the end," use
the patch-script pattern. Inline edits in chat are error-prone
for documents Claude can't see directly — having the script error
out on a mismatch is much better than silently writing wrong text.

### Screenshot file-naming convention

Adopted convention: `<phase>_<code>_<shape>.png`

- **phase**: `menu` | `dialog` | `rendered` | `error`
- **code**: 10-char share code, source of truth for the test case
- **shape**: terse description of contents — `S(-2,3)+G(-3,3)` for
  STARTER + GOAL_RAIL at those hexes, with `R` for rails, `P` for
  pillars, `W` for walls, `B` for balconies. Multi-piece example:
  `3x-S(-1,0,n3,2,n5,4)`. Append `_valid` or `_invalid` if the
  state is meaningful for the test.

Example: `rendered_X3WEQ6F296_S(-2,3)+G(-3,3)_valid.png`

Future automation will write `<code>_<timestamp>.png` automatically;
this convention is for the manual-screenshot phase only.
