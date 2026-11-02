# s47-t1 — every adb call names the emulator

**Status:** DONE

**In one paragraph:** the harness can no longer reach a phone. Every adb command now starts `adb -s emulator-5554`, and an `AdbContext` cannot be built with a serial that isn't `emulator-<digits>`, so a phone's serial in `ANDROID_SERIAL` raises instead of being used. The device checks (`assert_emulator_ready` and preflight's `device_attached`) now look for that exact serial in state `device`; before, any `emulator-` row passed. They name any other attached device as "never driven". The boot starts the AVD with `-port 5554`, so the pinned serial is the emulator it booted, and a taken port fails the boot. One out-of-scope test still asserts the old unpinned argv, and t2 fixes it.

## Open (written before the work)

- **Goal:** every adb command the harness runs carries `-s <serial>`, the serial must be an emulator's, and the device checks pass only when that serial is attached (plan item 22, #67).
- **Scope:** `traxgen/android.py`, `scripts/emulator.py`, `scripts/preflight.py`, and their tests (`test_android_foreground`, `test_emulator`, `test_emulator_session`, `test_preflight`), plus a new `tests/test_adb_serial.py`. The `TASK-OPEN` line is the record.
- **Budget:** 60 minutes, no renders, no device.
- **Done check:**
  1. *Step:* pin the serial in `AdbContext`, refuse a non-emulator serial, and make the device checks look for that serial.
  2. *True after:* (a) every argv that `_run_adb` and `_run_adb_binary` build starts `adb -s emulator-NNNN`; (b) building a context with a serial that is not `emulator-<digits>` raises, including through `ANDROID_SERIAL`; (c) `assert_emulator_ready` and preflight's `device_attached` fail when only some other device is listed, even another emulator; (d) the boot launches the emulator on the port that gives the pinned serial.
  3. *Miss cases:* the pin is added to one runner and not the other; a phone's serial in `ANDROID_SERIAL` is passed straight through; the device check still passes on "any `emulator-` row"; the boot starts on a free port of its own choosing, so the pinned serial names nothing.
  4. *Reads:* the argv the fake runners record; the exception raised for a phone serial; the checks' verdicts against scripted `adb devices` output; the argv `spawn_emulator` passes to `popen`.
  5. *Check:* `tests/test_adb_serial.py` asserts (a) to (d) on recorded argv and verdicts, and fails in each miss case, shown by deliberately breaking the code once per case; then the full suite passes.
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** pinned the serial in `AdbContext` (validated in `__post_init__`), put `-s` into both runners, added `device_state` and used it in both device checks, and passed `-port` from the serial in `spawn_emulator`. The test fakes now go through `adb_args`, which fails any unpinned call, so the whole offline suite doubles as a check that no code path is left unpinned.
- **What changed:** `traxgen/android.py`, `scripts/emulator.py`, `scripts/preflight.py`, `tests/test_android_foreground.py`, `tests/test_emulator.py`, `tests/test_emulator_session.py`, `tests/test_preflight.py`, new `tests/test_adb_serial.py` (17 tests).
- **Evidence:** `s47-t1: in scope -- 8 files changed since open commit 98b6ef9, all declared`. Suite: 1165 passed, 1 failed (`test_screencap_guard::test_a_whole_frame_passes_through_byte_for_byte`, which asserts the exact unpinned argv and sits outside this scope; it goes to t2). Six deliberate breakages, each caught: binary runner unpinned (6 failed), text runner unpinned (34), no serial validation (6), readiness on any emulator row (2), preflight on any emulator row (4), no `-port` (3). Ruff is clean on the new file; the two findings in `android.py` predate this task.
- **Decisions made inside the task:** the pin goes in argv as `-s`, not in the `ANDROID_SERIAL` environment, so every recorded argv and every `AdbCommandFailedError` shows which device was meant. `ANDROID_SERIAL` may still pick *another emulator* (`emulator-5556`), but never a phone. `-port` is derived from the serial, not set on its own, so the two can't disagree.
- **For the record:** plan item 22's first half is done (the serial; the frame-folder overwrite and the toolbar cells are left). environment.md's gotcha "prefix every harness command with `ANDROID_SERIAL=emulator-5554`" is retired: the default is now the pin. #67 is answered in code.
- **Friction:** the done check said "then the full suite passes", but one affected test lived in a file the scope didn't declare. Next time, grep the tests for exact argv asserts (`== [[str(ADB)`) before declaring scope.
- **Next:** s47-t2, the one test in `test_screencap_guard.py`.
