# s47-t1 — every adb call names the emulator

**Status:** OPEN

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
