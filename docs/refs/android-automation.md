# Android render automation — M6.c harness

Reference for the automated render-verification loop: render a share code in the real GraviTrax Android app and read the app's own validity verdict, ~25 s per code, no human in the loop. Exists because manual verification has a silent failure mode (see the clipboard finding — `allostat/observations.md` #5); harness results are the only render evidence that counts (`allostat/decisions.md`).

## Emulator

- AVD `traxgen_m6c` — Pixel 6, Android 14 (API 34), `google_apis_playstore` image, arm64-v8a, 2400×1080 landscape.
- GraviTrax installed via Play Store (throwaway Google account; ~30 min one-time setup including sign-in). Persists across reboots — no per-session re-sign-in.
- No writable-system, no cert injection: UI automation only, no MITM needed. The Play Store path is what rescued this approach after the earlier cert-injection Android attempt sank.
- Unity renders fine in the emulator — no GPU compatibility issues observed.
- Boot command lives in `allostat/knowledge/environment.md` (point, don't duplicate).

## Flow

`traxgen.android.render_course(code) -> RenderResult` drives the full sequence via `adb`: open the share-code dialog → dismiss the disclaimer → type the code via the native IME → submit → wait for load → screenshot → clean up. CLI wrapper: `uv run python -m scripts.render_course <CODE> [--detect-validity]`.

## Unity UI facts (why the harness works the way it does)

- The entire app is one `unitySurfaceView` covering [0,0][2400,1080] — the accessibility tree is opaque, so all taps are raw coordinates. Appium/uiautomator-selector approaches are ruled out.
- Exception: tapping a text field opens a *native* Android IME with a real `EditText` overlay — that part is selectable and accepts `adb shell input text`. Hence: raw coordinates for taps, native injection for typing.
- iOS Simulator was evaluated and is a dead end — it cannot install third-party App Store apps, and there's no GraviTrax source to build. Android emulation is the only viable automated-render path.

## Validity oracle

`detect_play_button_state()` samples the play-button triangle's interior at (2190, 980) on the 2400×1080 screencap. White interior = `'active'` (app considers the course valid); pale-green = `'inactive'`. Threshold: min RGB channel ≥ 220 → active. Calibrated against the known-state pair X3WEQ6F296 (valid) / MT756NLLMI (invalid) with wide margin in both directions.

## Known limitation

Fixed `time.sleep` delays between UI actions, not state polling. Reliable on the current emulator; if rendering ever gets laggy, upgrade to polling-based waits (capture → check stability → re-capture). A triggered review in `allostat/plan.md` tracks this.

## Tap-coordinate map (2400×1080 device space)

Mapped manually during M6.c (2026-04-25). `traxgen/android.py`'s `COORDS` dict is the source of truth — if the two disagree, android.py wins and this table gets re-synced. Re-measure if the device profile ever changes.

| Name | (x, y) | What it hits |
|---|---|---|
| `share_code_hex` | (265, 970) | Main-menu share-code hex |
| `load_track_now` | (1450, 800) | Disclaimer dismiss ("load track now") |
| `code_input_field` | (1200, 630) | Share-code text field (opens native IME) |
| `ime_ok` | (2270, 305) | IME confirm |
| `load_track_button` | (1200, 800) | Submit the code |
| `loaded_track_hex` | (1200, 540) | Open the loaded track |
| `back_save_icon` | (180, 60) | Back/save (starts cleanup) |
| `dont_save` | (950, 800) | Decline save |
| `trash_icon` | (1530, 280) | Delete the loaded track |
| `delete_confirm` | (1200, 800) | Confirm delete |

Waits (seconds): after_tap 0.5 · after_text 0.3 · after_load 4.0 · after_render_load 5.0 · after_back 1.0 · after_delete 1.5.

**Flow detail the prose above compresses:** cleanup is a five-tap sequence (back → don't save → trash → confirm), on by default; `expect_disclaimer` handles the first-load dialog; `reset_to_main_menu()` force-stops and relaunches when the UI state is unknown.

## Oracle constants (exact)

Sample: 12×12 px box centered at (2190, 980); threshold min avg channel ≥ 220 → `'active'`. Calibration pair (2026-04-25): valid = RGB(247, 250, 234), min 234; invalid = RGB(207, 222, 124), min 124 — the blue channel is the discriminator. Pillow is imported lazily so the automation flow works without it.

## Failure modes

`AdbNotFoundError` (bad ANDROID_HOME), `EmulatorNotReadyError` (no device or `sys.boot_completed ≠ 1` — checked before every render), `AdbCommandFailedError` (non-zero exit or timeout, command and stderr attached).

## Known bug (as of 2026-07-22)

`DEFAULT_SCREENSHOT_DIR` is hardcoded to `~/Desktop/Hub/Projects/traxgen/screenshots` — a checkout that no longer exists. `screencap()`'s `mkdir(parents=True)` will silently recreate the phantom path. Fix tracked in `allostat/plan.md` deferred cleanup: make it repo-relative or config-driven (dovetails with "record outcomes as text, delete PNGs").
