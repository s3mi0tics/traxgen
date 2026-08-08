# TDD case study: the goal-rotation sweep

A worked account of one session (2026-08-07) building and running an
experiment against the GraviTrax app. It is recorded here because the
interesting part is not the code that shipped — it is the sequence of checks
that were wrong, and how each one was caught.

The work: derive the general rule mapping a goal tile's position relative to
the starter onto the `hex_rotation` it needs in order to connect. One
app-certified geometry was known. The experiment sweeps six adjacent
positions across six rotations and reads the app's own play button as the
oracle.

## The principle everything below is an instance of

> A check whose pass is indistinguishable from its never having run carries
> no information.

This project already had that written down as observation #12, promoted after
three firings in an earlier session. It fired three more times in this one.
Every instance has the same shape: the check compares two things that share
an origin, so agreement is guaranteed and means nothing.

## Test-first, applied to an experiment

An experiment's equivalent of writing the test first is declaring what each
possible result would mean *before* generating data. Otherwise the result
arrives and the interpretation gets fitted to it.

Five outcomes were written into `classify()` and covered by tests before a
single render:

| Verdict | Condition |
|---|---|
| `CLEAN_RULE` | one active rotation per direction, all six fitting one affine rule |
| `LOOKUP_TABLE` | one active per direction, no affine fit |
| `PARTIAL_FUNCTION` | some directions have zero active rotations |
| `MODEL_WRONG` | a direction has more than one active rotation, or the distance-2 control activates |
| `HARNESS_SUSPECT` | the app-certified control renders inactive |

`PARTIAL_FUNCTION` earned its slot by being named in advance as a *legitimate*
finding rather than a failure — GraviTrax has vertical structure, so a goal
uphill of the starter may simply be unreachable. Naming it up front is what
stops it being read later as a broken run.

## The test that encodes why the experiment exists

The one known data point is a goal at direction 2 (NW) with rotation 3. Two
rules satisfy it:

    rot = (d + 1) % 6   ->  2 + 1 = 3
    rot = (5 - d) % 6   ->  5 - 2 = 3

They agree at direction 2 and disagree everywhere else. So the single
observation constrains nothing, which is the entire justification for
spending 42 renders. That claim is a test:

    def test_single_observation_does_not_determine_the_rule():
        assert fit_affine_rules({2: 3}) == [(1, 1), (5, 5)]

If someone later "simplifies" the fitter into something that returns a unique
answer from one observation, this fails and says why.

## Cheapest failing test first

Test ordering is a cost decision. The known-good geometry is rendered first,
before the 41 unknowns, because a broken harness should cost one render and
not forty-two.

It did exactly that. The control came back `inactive`, the run aborted, and
the session spent one render learning the harness was untrustworthy.

## Error is not failure

`inactive` (the app says this course does not connect) and `render_error`
(the harness never got a reading) are recorded as separate fields, never
collapsed. Conflating them turns "the tooling broke" into "the hypothesis was
refuted", which is the more expensive of the two mistakes to make.

## Preconditions as executable assertions

Two checks run in the sweep itself, before any network call:

- The control variant must serialize byte-identically to `generate_minimal()`.
- All 42 payloads must have distinct SHA-256 hashes. The upload endpoint
  dedups by content hash, so two cells sharing bytes would silently share a
  share code and stop being two cells.

Both are ordinary assertions placed where the cost of being wrong is highest —
just before spending 42 uploads and 20 minutes.

## Four things that were wrong, and what caught each

### 1. A test helper that would have passed while testing nothing

`_classified()` builds a synthetic cell list for the classifier tests. First
version:

    if cell.is_positive_control and control_active:
        cell.validity = "active"
    elif cell.kind == "adjacent" and active.get(cell.direction) == cell.rot:
        cell.validity = "active"

When a test passed `control_active=False`, the control cell fell through to
the second branch and was marked active anyway by the direction map. The test
asserting `HARNESS_SUSPECT` would have set up an *active* control, and passed
for a reason unrelated to what it claimed to check.

Caught by reading the branch structure, not by running it — a passing test
cannot report this about itself. Fixed by making the control's state depend on
exactly one input.

### 2. The test caught the human

Twenty-two of twenty-three tests passed on first run. The failure was in an
*assertion*, not in the code under test: the mirror rule was written as
`(5, 1)` when one observation pins it to `(5, 5)`. The fitter had the right
answer throughout.

This is the value that is hard to demonstrate on purpose. The arithmetic error
was in the layer doing the checking, and only an independent execution of it
surfaced that.

### 3. A precondition that verified the wrong thing

The byte-identity precondition was the check with the most weight on it — if
the variant builder diverged from the generator, the sweep would measure a
course the app never certified while looking healthy.

It compared the variant against `generate_minimal()`. Both come from the same
function. It could not have failed for the reason that mattered, and it never
tested the actual claim: *does `generate_minimal()` still produce the bytes the
app certified as share code `FLW4TMLP5V`?*

The evidence that something was off was visible and nearly missed. The control
uploaded as a **new** share code, `KN6F459ZR3`, not `FLW4TMLP5V` — and the
endpoint dedups by content hash, so identical bytes should have returned the
certified code.

Fetching the certified artifact and diffing settled it:

    FLW4TMLP5V:        0e "traxgen-norail"    176 bytes
    generate_minimal:  0f "traxgen-minimal"   177 bytes

From the end of the title onward the two streams are byte-identical, offset by
exactly one. Same layer id, same `13 00 00 00` (TileKind 19 = GOAL_RAIL), same
rotation, same everything. **The only divergence is the course title**, which
is metadata and cannot affect validity.

Three results fell out of one diff: the generator is substantively correct and
its certification stands; content-hash dedup is confirmed rather than
falsified; and the alternative explanation for the inactive control collapses,
leaving exactly one cause to chase instead of two.

### 4. A claim in a handoff that nothing had checked

The session handoff stated: *"Repo has a `.envrc`; direnv loads on `cd`."*
There is no `.envrc` in the repo. Every command in the session printed
`direnv: unloading` and no matching load line — visible three times before
anyone read it, including by the author of this document, who called it
harmless.

It surfaced when `$ANDROID_HOME` turned out to be unset and the emulator boot
command silently failed into a redirect.

## The system stopping itself

The run's own abort is the outcome worth pointing at. Sequence:

1. Control rendered first.
2. Oracle returned `inactive`.
3. Pre-declared condition matched `HARNESS_SUSPECT`.
4. Run halted after one render, sidecar written, 42 share codes preserved.

Then diagnosis, which is where the checks paid for themselves. A
`uiautomator` dump gave the OK button's real bounds as `[2216,252][2384,378]`,
which *contains* the calibrated tap coordinate `(2270, 305)`. The obvious
suspect — a stale coordinate — was eliminated in one command, leaving timing.
The cold-booted AVD had not finished laying out the fullscreen IME when the
0.3s wait expired, so the code was never submitted and the oracle sampled a
keyboard. Full account in `docs/refs/ui-automation-synchronization.md`.

Note the failure mode: no crash, no exception. A verdict, in the right format,
in the right field, about the wrong thing.

## Verifying the instrument at both ends

The opening control proves the harness worked at render 1. It says nothing
about render 25. A drift halfway through would surface as a page of `inactive`
verdicts that read like findings.

So the control is rendered again after the last cell, and a non-active closing
bracket overrides the verdict to `HARNESS_SUSPECT` regardless of what the data
looked like. Active at both ends is not proof the harness held throughout, but
it is a great deal more than active at one end.

## What it cost and what it bought

Cost: roughly an hour on 23 offline tests, two runtime preconditions, an
ordering constraint, and a closing bracket — none of which produce any of the
sweep's actual output.

Bought:

- One render spent on a broken harness instead of forty-two.
- A byte-level answer about generator drift, reached in one diff, from a
  discrepancy that would otherwise have read as noise.
- Two independent candidate causes for the failure reduced to one, before
  any time was spent on the wrong one.
- Three wrong checks caught while they were still cheap.

The recurring lesson is narrow and worth stating plainly: the checks that
failed were not the ones that ran and went red. They were the ones that ran,
went green, and could not have done otherwise.

## Related

- `scripts/sweep_goal_rotation.py` — the experiment.
- `tests/test_sweep_goal_rotation.py` — the 23 offline tests.
- `docs/refs/ui-automation-synchronization.md` — the harness failure in detail.
- `allostatik/observations.md` — observation #12, the pattern these are all
  instances of.
