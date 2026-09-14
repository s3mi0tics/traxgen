# Render in the app

The official GraviTrax app loads a share code and shows the course. Its play
button is lit (`active`) only when the app considers the course valid. This is
the project's judge of record for validity.

## Sub-features

- `render-active` a valid course renders with the play button `active`.
- `render-inactive` an invalid course renders with it `inactive`.
- `render-lifecycle` `--fresh` runs from nothing to nothing: kill, cold boot, menu, render, kill.

## How to get to it (user POV)

- `uv run python -m scripts.render_course CODE --fresh --detect-validity`
- As the opt-in `render` stage: `verify_chain.sh --render`.

## Driving it with verify_chain

Preconditions:

- Doctor shows `adb present` and `emulator not running`.
- About 2.5 minutes, and the machine may be left alone. Do not touch or rotate
  the emulator window.

- **Certified course.** Run `verify_chain.sh --render`. `summary.txt` ends with
  `PASS render play button active (...rendered_KN6F459ZR3.png)`. The screenshot
  is in the run directory. `render.log` ends with `PASS emulator_down`.
- **New course.** Run `verify_chain.sh --board standard-square --render`. The
  verdict turns that board's `claim: UNMEASURED` into a measurement, either way.
  Record it before claiming anything about four-plate generation.

## Gotchas

- `--fresh` kills any emulator already running, including one a human is using.
- The oracle samples pixels. A locked or occluded display throttles the
  emulator, so hold the display: prefix with `caffeinate -di`.
- `grep -c "bad color buffer" /tmp/emulator.log` should be 0. A climbing count
  means stop, not retry.
- The app version must be `android.MEASURED_APP_VERSION` (2.8). Preflight
  refuses others, because a Play Store update invalidates the tap map.
