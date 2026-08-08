# UI automation synchronization

How an automation harness decides that the thing it is about to interact with
is actually there yet. traxgen's Android render harness (`traxgen/android.py`)
hits this constantly, and got it wrong on 2026-08-07 in a way worth recording.

## Three generations

**1. Fixed sleep.** `time.sleep(4)`. Guess the worst-case duration and wait
that long unconditionally. Wrong in both directions: too short means flaky,
too long means slow, and the right value moves with machine load, emulator
state, and whether the app was cold-started. A sleep also *asserts nothing* —
when it is too short the next action fires into an unready screen and the run
continues, producing output that looks like data.

**2. Explicit polling.** Wait until a condition is true, checking every
~250ms, raising on a timeout. Selenium's `WebDriverWait`, Playwright's
`expect(...).toBeVisible()`. Two gains over a sleep, and the second matters
more than the first:

- *Faster in the common case* — proceeds the moment the condition holds
  instead of always paying worst-case.
- *Fails loudly* — a timeout is an error with a name ("the OK button never
  appeared"), not a silently wrong screenshot. It converts a silent failure
  into a reported one.

**3. Auto-waiting.** The framework polls before every action, so you never
write a wait at all. Playwright's default behaviour: `click()` waits for the
element to be attached, visible, stable, and enabled first.

Generation 3 needs a framework that owns the action API. `adb shell input tap`
has no such layer, so it isn't available here — the live question for traxgen
is only whether to stay at generation 1 or move to generation 2.

## Where traxgen sits, and the Unity constraint

`android.py` is generation 1: a `WAITS` dict of fixed sleeps, tuned by hand
during the M6.c session (2026-04-25) against a warm emulator.

Moving to generation 2 requires something to *poll*, and here the app splits
in half. GraviTrax is a Unity app: everything below the native Android dialogs
renders into a single opaque `UnityPlayerActivity` surface. `uiautomator` sees
native views and nothing else. A dump taken mid-flow on 2026-08-07 returned
the IME's `EditText` and `Button` — and no game board, no play button, no menu.

| Harness step | Pollable via `uiautomator`? |
|---|---|
| share-code hex, disclaimer, code field, IME OK | **yes** — native views and dialogs |
| `after_load`, `loaded_track_hex`, `after_render_load` | **no** — Unity surface |

So generation 2 is reachable for the native half and *not* reachable for the
Unity half by the same technique. Polling the Unity steps would need a
pixel-based predicate — poll `screencap` until consecutive frames stop
changing — which is a different and less certain piece of work: each capture
is a full 2400x1080 PNG pulled over adb, and "the screen stopped changing" is
ambiguous in a 3D app that may animate at idle.

This is the same wall a browser harness hits on a `<canvas>` or WebGL app:
no queryable tree, so synchronization falls back to visual comparison. Same
root cause, different tool.

## Worked example: the 2026-08-07 IME failure

The goal-rotation sweep's positive control rendered `inactive`, which by its
pre-declared falsification conditions meant HARNESS_SUSPECT, and the run
aborted after one render instead of 42.

What actually happened, in order:

1. The AVD was cold-booted (`-no-snapshot-load`), so no warm snapshot.
2. `tap(code_input_field)` focused the field; `type_text` injected the code.
3. `WAITS["after_text"]` was 0.3s. The fullscreen extract-mode IME had not
   finished laying out.
4. `tap(ime_ok)` fired into an unready view. The code was never submitted.
5. Every later step — `load_track_button`, `loaded_track_hex`, `screencap` —
   ran against a keyboard.
6. `detect_play_button_state` sampled pixel (2190, 980), which on that screen
   is around the `m`/backspace keys, got a non-white average, and returned
   `inactive`.

The oracle was not wrong about the course. It never saw a course.

**The coordinate was not the problem, and checking that mattered.** A
`uiautomator` dump gave the OK button's real bounds as `[2216,252][2384,378]`,
which contains the calibrated `(2270, 305)` on both axes. Without that check
the obvious move is to re-measure tap coordinates — hours spent on the wrong
layer.

**Stopgap applied:** `after_text` 0.3 -> 1.5, `after_tap` 0.5 -> 0.8. This is
still generation 1 and still asserts nothing; it re-tunes a constant that was
already tuned once and had drifted. It buys a run, not a fix.

**Also note what this failure mode is.** It did not crash. It produced a
verdict, in the right format, in the right field, that happened to be about a
keyboard. Silent-wrong-answer is the failure this project keeps meeting — the
Mac-to-iPhone clipboard re-pasting a stale share code (2026-06-12) was the same
shape, and is why harness-only render verification is a locked decision. A
fixed sleep is a silent failure mode by construction.

## Next step

Generation 2 for the four native steps: a `wait_for(ctx, predicate, timeout,
interval)` helper polling `uiautomator`, used to wait for the OK button before
tapping it and for its disappearance after. Two design notes for whoever
builds it:

- `uiautomator dump` *fails* while the IME is animating. The predicate must
  read a failed dump as "not ready yet", not as an error — otherwise the
  polling reintroduces the flakiness it was meant to remove.
- A timeout must raise `AndroidAutomationError`, so callers record it as a
  render error rather than a validity verdict. `scripts/sweep_goal_rotation.py`
  already keeps `render_error` and `inactive` as distinct states; nothing
  currently produces the former for this case.

The helper is testable with no emulator: a captured `uiautomator` dump is a
fixture, and the dump-failure branch is the case most worth covering.

Pixel-stability polling for the two Unity steps is queued behind that, and
only earns its place if those sleeps actually bite. They have not yet.

## Related

- `docs/refs/android-automation.md` — the harness itself: emulator config,
  tap-coordinate map, validity oracle.
- `allostatik/plan.md` — carries the triggered review this failure satisfied
  ("when rendering in the emulator gets laggy -> upgrade the harness from
  fixed sleeps to polling-based waits").
