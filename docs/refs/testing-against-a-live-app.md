# Testing against a live app: what is actually hard here

Raised by Colby 2026-08-25 (s27), after a session in which two consecutive
render campaigns died without producing a single measurement, while the offline
suite sat at 730 green throughout:

> I think this is a hard part of having an external testing suite.

He is right, and this file exists because the difficulty is specific and
nameable rather than general. "Testing is hard" is not useful. **Testing code
whose correctness depends on a stateful system you do not control** is hard in
one particular way, it has cost this project more time than any other single
thing, and the answers the project has evolved are worth writing down in one
place instead of leaving scattered across nine sessions of `decisions.md`.

Scope: this is the *why* and the catalogue. The mechanics of one sub-problem —
deciding when a screen is ready — live in `ui-automation-synchronization.md`.
The harness itself is documented in `android-automation.md`. This file is the
frame those two sit inside.

---

## The structural problem: a fake is an assumption wearing a costume

`traxgen` has ~730 offline tests. They were green through every failure below.
They are not bad tests — the mutation batteries say they are unusually good
ones — but they are structurally incapable of catching this class, and it is
worth being precise about why rather than treating it as a coverage gap to be
filled.

An offline test replaces the real system with a fake. `FakeAdb` returns a frame
immediately, always at the same size, never wedged, always with the right app in
front. Each of those is an **assumption about the world**, encoded in the test
harness itself. So:

- A test can prove the code behaves correctly **given** the assumption.
- A test can never prove the assumption.
- And the assumption is what breaks.

That is not a flaw in the fakes. It is what a fake *is*. The moment you write
`return PNG_FRAME`, you have asserted "screencap returns a frame" — and every
test downstream inherits that assertion without ever testing it. Adding more
offline tests makes the code more correct against the same unexamined premise.

The consequence is that two layers are needed and they catch **disjoint**
classes of defect:

| Layer | Catches | Blind to |
|---|---|---|
| Offline suite | logic errors in our code | every assumption the fakes encode |
| The live run | assumption errors | almost nothing about our logic |

Neither substitutes for the other, and effort spent on one does not reduce the
need for the other. This project has repeatedly been in the position of having a
perfect offline suite and a completely broken campaign.

## The catalogue

Every one of these was a session where the code was correct and the environment
was not what the code assumed. They are listed with what a wrong answer would
have been *believed* to mean, because that ranking (observations #17) is the
single most useful thing this project has learned about guards.

| When | What broke | What the harness would have reported | Blast radius |
|---|---|---|---|
| 2026-08-07 | Fullscreen IME had not finished laying out; `ime_ok` tapped an unready view, so the code was never submitted and the rest of the flow ran against a keyboard | `inactive` | **Lost data.** Reads as "no finding", costs a re-run |
| 2026-08-07 | Cold-booted AVD still on its splash; the render fired into a loading screen | **`active`** | **Invented data.** Would have been recorded as `MODEL_WRONG` — a discovery that never happened |
| 2026-08-10 | Lock screen occluded the emulator window; macOS throttled its GPU; a fixed sleep expired into a still-loading course | `active`/`inactive` by brightness | Invented data — caught only because the frame guard existed by then |
| 2026-08-21 | App was never launched. `render_course` starts tapping at the main menu; `assert_emulator_ready` checks the *emulator*, not the foreground. Every tap landed on the Android launcher and the oracle sampled wallpaper | `inactive`, confidently | **Worst case on record.** The probe *predicted* its discriminating cells dark, so a harness aimed at the launcher returns exactly the all-inactive result that reads as flawless confirmation of the hypothesis under test |
| 2026-08-23 | Two SSL handshake timeouts on upload took out both bracket controls | `INCOMPLETE` | Whole campaign void; the five cells that did render were consistent with the model and had to be discarded anyway |
| 2026-08-23 | Frame guard refused the opening control at `white_frac 0.660` — a loading screen | `INCOMPLETE` | One re-run. **The guard working** |
| 2026-08-25 | App showed its build tutorial (an empty editor) instead of the loaded course; the oracle sampled the greyed play button of a course that was never there | `inactive` — well-formed, and about the wrong screen | Two of seven renders. Caught only because one of the two was a *control* |
| 2026-08-25 | Emulator window rotated/resized mid-session; the graphics backend lost its colour buffers; `dumpsys window` wedged and every subsequent `adb shell` hit its timeout | Total failure, all seven arms | Campaign void. **Failed loudly, which is the good direction** |

Two more from outside the render path, same disease:

| When | What broke | Consequence |
|---|---|---|
| 2026-06-12 | Mac→iPhone clipboard silently re-pasted a **stale share code** during manual verification | Invalidated a session's worth of observations. The original sin, and the reason `decisions.md` gives manual verification zero evidentiary weight |
| 2026-08-23 | Terminal output re-selected from scrollback was pasted as a fresh run's result | Nearly caused a working fix to be diagnosed as broken and re-engineered. Caught by a *prose* detail, not by the data |

The pattern across all ten: **the dangerous failures are the ones that produce a
plausible answer.** An exception is cheap. A well-formed verdict about the wrong
screen is expensive, and it is expensive in proportion to how much it looks like
a finding.

## What the project evolved in response

None of these were designed up front. Each is a scar, and each is locked in
`decisions.md` with the failure that produced it.

**Controls at both ends of every run** (2026-08-07). Render a known-good
geometry first *and* again after the last cell. A non-active closing bracket
overrides the run's verdict to `HARNESS_SUSPECT` regardless of what the data
said. This is the single highest-value mechanism in the project: it has caught
failures nobody imagined when it was written, three times, including both of
2026-08-25's.

**A control at the position under test** (2026-08-21). The bracket proves the
*harness* works. It does not prove the *geometry family* under test is
renderable at all. Without a local control, "the starter cannot sit here" and
"the model is right" produce the identical all-dark run — a null that
discriminates nothing.

**Guards that refuse rather than answer**, each on a different axis, each with
its scope stated in the module rather than implied:

| Guard | Question it answers | Added |
|---|---|---|
| `frame_white_fraction` | is this a near-white splash? | 2026-08-07 |
| `assert_app_in_foreground` | which **application** is in front? | 2026-08-23 |
| `FrameStability` | has the surface stopped **animating**? | 2026-08-24 |
| `match_refused_screen` | is this a **known** dead screen? | 2026-08-25 |

Stating scope matters as much as the guard. `assert_emulator_ready` was read as
meaning more than it checked, and that gap is exactly how the 2026-08-21
launcher failure happened. Each guard above names what it cannot see.

**Three-valued knowledge.** `CONNECTED` / `DISCONNECTED` / `UNMEASURED`. A
two-valued API forces every gap into a false claim, and the false claim it picks
("not connected") is indistinguishable from a measured negative. The third value
is what keeps a hole in the record from becoming an assertion about the world.

**Retry by exception class, and count the retries.** 5xx and network yes; 4xx
and malformed no — retrying a wrong payload buys a slower no. The *count* goes
into the sidecar, because the failure rate is itself a measurement and a run
that quietly recovered twice must not read as a clean one.

**Freshness stamps on anything that crosses back through a human.** Runs print a
UTC timestamp because a stale paste is otherwise indistinguishable from a fresh
one, and *plausible* is the dangerous property — an implausible paste gets
questioned.

## The parallel that is real: browser automation

This is the same disease in a different organ, and the parallel is worth drawing
because the industry has been fighting it for longer.

- **Auto-waiting** exists because the DOM lies about when it is ready. A
  fixed sleep is a guess about someone else's scheduler. traxgen's whole
  fixed-sleep-to-polling arc is this lesson, arriving late.
- **Fresh browser contexts and disposable containers** exist because long-lived
  shared state accumulates exactly the corruption 2026-08-25 hit. Our emulator
  is a browser session that has been open for weeks.
- **Screenshot/trace on failure** exists because the picture ends arguments that
  reasoning cannot. The 2026-08-21 diagnosis took one look at a screenshot after
  a long stretch of theorising; so did 2026-08-25's.
- **Quarantine and retry policy** exists because "flaky" and "broken" need
  different responses, and conflating them either hides real defects or burns
  time on transients.

Borrow the concepts freely; do not import the tool. traxgen is a Python backend
library and pytest + hypothesis is its test story.

## What is still unsolved, stated plainly

**Every guard here is a signature guard, not a mode guard.** Each closes a
failure that has already happened. None of them recognises a screen nobody has
seen. The 2026-08-25 refused-screen guard is the clearest case: it knows the
build tutorial and is blind to whatever the app shows next. Closing the *mode*
would need a positive test — "this frame contains a course" — and no such test
exists.

**The structural fix is a disposable environment**, and it is a locked decision
that this Mac cannot have one: the Android emulator needs hardware
virtualization that Docker's Linux VM on an M1 does not expose. The trigger for
revisiting is named (a Linux host with KVM). 2026-08-25 is evidence *for* that
trigger.

**The affordable partial fix is a committed pre-flight**, and as of s27 it does
not exist. Four escalating diagnostic commands were hand-written in one evening,
and every one of them checked something that had actually broken: device
attached, boot complete, **zero graphics errors since boot**, app in foreground,
and **screencap geometry equal to tap-coordinate space**. The graphics-error
count alone would have caught 2026-08-25's second failure before seven uploads
and a void campaign. A check that lives in a human's habit is not a check.

## The honest accounting

Two things are true at once and the second does not cancel the first.

**This is expensive.** Across the render campaigns this project has attempted,
more have been voided by the harness or the environment than by the experiment
disagreeing with the model. The failure catalogue above is nine months of a
side project.

**And the discipline is working.** In every case above, the outcome was a
refusal, a re-run, or an `INCOMPLETE` — not a false entry in `MEASURED_RUNS`.
The record has never been corrupted by any of these, including the two that
produced a *positive* reading, because a control caught both. The cost has been
paid in time, not in knowledge, and that is precisely the trade the guards are
built to make: a false negative costs a re-run, a false positive costs
everything downstream that was reasoned from it.

The thing worth protecting is not the campaign. It is the record.
