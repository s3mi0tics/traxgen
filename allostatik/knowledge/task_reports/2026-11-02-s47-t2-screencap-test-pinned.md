# s47-t2 — the screencap test expects the pinned argv

**Status:** OPEN

## Open (written before the work)

- **Goal:** `test_a_whole_frame_passes_through_byte_for_byte` expects `adb -s emulator-5554 exec-out screencap -p`, so the suite is green again after t1.
- **Scope:** `tests/test_screencap_guard.py`.
- **Budget:** 10 minutes.
- **Done check:**
  1. *Step:* update the one exact-argv assert.
  2. *True after:* the full suite passes, and the assert still names the whole argv rather than a part of it.
  3. *Miss cases:* the assert is loosened to a substring, so an unpinned screencap would pass it.
  4. *Reads:* the pytest summary; the diff of the assert.
  5. *Check:* the full suite reports 0 failed, and reverting `_run_adb_binary`'s `-s` makes this test fail.
- **Outcomes declared before any live run:** none, because there is no live run.
