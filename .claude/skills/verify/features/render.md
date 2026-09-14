# Render in the app

The official GraviTrax app loads a share code and shows the course. Its play
button is lit (`active`) only when the app considers the course valid. This is
the project's judge of record for validity.

> **UNPROVEN. Nothing in this file has been executed from the verify skill.**
> The commands match `scripts/render_course.py`'s flags and the chain's render
> wiring, checked by reading the code. Every result below marked *expected* is
> what that code should print, and none of it has been observed. A reader must
> not treat this recipe as verified, or a course as valid because this file
> describes how it would be shown valid. The first passing
> `verify_chain.sh --render` retires this notice; see `../SKILL.md`, Status.

## Sub-features

- `render-active` a valid course renders with the play button `active`.
- `render-inactive` an invalid course renders with it `inactive`.
- `render-lifecycle` `--fresh` runs from nothing to nothing: kill, cold boot, menu, render, kill.

## How to get to it (user POV)

- `uv run python -m scripts.render_course CODE --fresh --detect-validity`
- As the opt-in `render` stage: `verify_chain.sh --render`.

## Driving it with verify_chain

Preconditions:

- macOS. The recipe assumes the SDK at `~/Library/Android/sdk` (or
  `ANDROID_HOME`), `caffeinate`, and AVD `traxgen_m6c`.
- Doctor shows `adb present` and `emulator not running`.
- About 2.5 minutes with the machine left alone. Do not touch or rotate the
  emulator window.

- **Certified course.** Run `verify_chain.sh --render`. *Expected, never
  observed:* `summary.txt` ends with
  `PASS render play button active (...rendered_KN6F459ZR3.png)`, the screenshot
  is in the run directory, and `render.log` ends with `PASS emulator_down`.
  Anything different is a finding about this file, not only about the course.
- **New course.** Run `verify_chain.sh --board standard-square --render`.
  *Expected, never observed:* a `render` line whose verdict turns that board's
  `claim: UNMEASURED` into a measurement, either way. Record it before claiming
  anything about four-plate generation.

## Gotchas

- `--fresh` kills any emulator already running, including one a human is using.
- The oracle reads the button's colour. It never presses play, so `active`
  does not show that the marble reaches the goal.
- A wrong screen fools the oracle: a splash has read `active`, and the
  launcher `inactive`. `--fresh` waits for a recognised main menu to prevent
  this. That wait is also unobserved from this skill.
- The oracle samples pixels. A locked or occluded display throttles the
  emulator, so hold the display: prefix with `caffeinate -di`.
- `grep -c "bad color buffer" /tmp/emulator.log` should be 0. A climbing count
  means stop, not retry.
- The app version must be `android.MEASURED_APP_VERSION` (2.8). The cold boot's
  device checks refuse any other, because a Play Store update invalidates the
  tap map.
