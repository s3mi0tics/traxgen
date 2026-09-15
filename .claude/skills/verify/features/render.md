# Render in the app

The official GraviTrax app loads a share code and shows the course. Its play
button is lit (`active`) only when the app considers the course valid. This is
the project's judge of record for validity.

Run from this skill on 2026-09-15, app 2.8: single-plate at `b07ddba`
(`verify-runs/20260915T040428Z-single-plate-8mW4/`) and standard-square at
`47a062d` (`verify-runs/20260915T041644Z-standard-square-pQRf/`). Both
directories are gitignored and live on the machine that ran them. Results below
marked *observed* come from those runs.

## Sub-features

- `render-active` a valid course renders with the play button `active`. Observed.
- `render-inactive` an invalid course renders with it `inactive`. Not yet run
  from this skill.
- `render-lifecycle` `--fresh` runs from nothing to nothing: kill, cold boot,
  menu, render, kill. Observed on the passing path only.

## How to get to it (user POV)

- `uv run python -m scripts.render_course CODE --fresh --detect-validity`
- As the opt-in `render` stage: `caffeinate -di verify_chain.sh --render`.

## Driving it with verify_chain

Preconditions:

- macOS. The recipe assumes the SDK at `~/Library/Android/sdk` (or
  `ANDROID_HOME`), `caffeinate`, and AVD `traxgen_m6c`.
- Doctor shows `adb present` and `emulator not running`.
- About 2 minutes with the machine left alone. Do not touch or rotate the
  emulator window.

- **Certified course.** Run `caffeinate -di verify_chain.sh --render`.
  *Observed:* exit 0 in 2m10s. `summary.txt` ends with
  `PASS render play button active (<run dir>/rendered_KN6F459ZR3.png)`. The
  screenshot shows the course editor with the one-plate course loaded and a
  lit play button. `render.log` reads, in order: the pre-boot
  `PASS emulator_down`, `boot_completed in 29.2s`, four device checks
  (`device_attached`, `boot_complete`, `graphics_errors` at 0,
  `app_version` 2.8), the teardown `PASS emulator_down ... process gone after
  5.2s`, then `screenshot saved:` and `play button: active`. The verdict comes
  after teardown, so `render.log` ends with `play button:`, not with
  `emulator_down`.
- **New course.** Run `caffeinate -di verify_chain.sh --board standard-square --render`.
  *Observed:* exit 0 in 2m11s, code `H4OI26V7Q7`, `PASS render play button
  active`, and the same `render.log` sequence as above (boot 28.7s). The
  screenshot shows all four plates, with the starter and goal rail on the
  right-hand plate. The course places the STARTER at local `(y=-4, x=0)` on
  the plate at world `(0,0)`, and the GOAL_RAIL at local `(y=-6, x=5)`,
  rotation 5, on the plate at world `(y=3, x=-6)`. `generate` and `check`
  still print `claim: UNMEASURED`, because the verdict lives only in the run
  directory until `MEASURED_RUNS` records it.

## Gotchas

- `--fresh` kills any emulator already running, including one a human is using.
- The oracle reads the button's colour. It never presses play, so `active`
  does not show that the marble reaches the goal.
- A wrong screen fools the oracle: a splash has read `active`, and the
  launcher `inactive`. `--fresh` waits for a recognised main menu to prevent
  this, and a wait that times out fails the render. `render.log` has no line
  for the wait, so how long the menu took is not recorded. Open the
  screenshot to confirm the screen.
- The oracle samples pixels. A locked or occluded display throttles the
  emulator. The chain does not hold the display, so prefix with
  `caffeinate -di`.
- `render.log`'s `graphics_errors` line counts `bad color buffer` in
  `/tmp/emulator.log` after boot. It should be 0. A climbing count means stop,
  not retry.
- The app version must be `android.MEASURED_APP_VERSION` (2.8). The cold boot's
  `app_version` check refuses any other, because a Play Store update
  invalidates the tap map.
