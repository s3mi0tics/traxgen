# s47-t2 — the screencap test expects the pinned argv

**Status:** DONE

**In one paragraph:** the last test that expected an unpinned adb call now expects `-s emulator-5554`, and still names the whole argv. The suite is green again.

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

## Close

- **What happened:** one assert updated to the full pinned argv.
- **What changed:** `tests/test_screencap_guard.py`.
- **Evidence:** `s47-t2: in scope -- 1 files changed since open commit 396cd97, all declared`. Suite: 1166 passed. With `_run_adb_binary`'s `-s` removed, this file fails 1 of 7.
- **Decisions made inside the task:** none.
- **For the record:** nothing beyond t1's.
- **Friction:** none.
- **Next:** s47-t3: the rest of item 22's batch (the ring board's toolbar cells and `probe_finish_frames`' overwrite).
