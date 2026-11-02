# s48-t2 — the reset tests' course frame is a course, not the menu

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** the two `reset_first` tests in `tests/test_android_foreground.py` serve the main menu to the menu wait and a dark course frame to the load, so the suite passes with s48-t1's near-white check in the load.
- **Scope:** `tests/test_android_foreground.py`.
- **Budget:** 15 minutes, no device.
- **Done check:**
  1. *Step:* change the two tests' `FakeAdb` to `screencap_pngs=(MAIN_MENU_PNG, PNG_FRAME)`.
  2. *True after:* both tests pass, and each still checks what it checked before (the call order; `on_menu` heard before the first tap); the suite passes.
  3. *Miss cases:* a test passes because the menu wait now times out or matches on a different frame; the assertions were loosened to make it pass.
  4. *Reads:* the diff of the two tests; the pytest summary.
  5. *Check:* the diff changes only the two `FakeAdb(...)` constructions, `arrival.polls` is still asserted `== 1`, and the summary reports 0 failed.
- **Outcomes declared before any live run:** none, because there is no live run.
