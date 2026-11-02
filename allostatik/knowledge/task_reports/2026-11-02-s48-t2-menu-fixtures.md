# s48-t2 — the reset tests' course frame is a course, not the menu

**Status:** DONE

**In one paragraph:** The two reset tests used the main-menu picture for every screencap, so after s48-t1 the load refused their "course" as a near-white screen. Each now serves the menu to the menu wait and a dark frame to the load, and the no-reset half of the second test uses the default dark frame. Nothing they assert changed.

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

## Close

- **What happened:** three `FakeAdb(...)` constructions changed; the third is the second test's no-reset render, which never polls the menu, so its only frame is the course frame.
- **What changed:** `tests/test_android_foreground.py`.
- **Evidence:** `s48-t2: in scope -- 1 files changed since open commit a487d96, all declared`; `1191 passed, 1 deselected`; `arrival.polls == 1` still asserted.
- **Decisions made inside the task:** the done check said two constructions and it was three; the third is in the same test and is the same fixture problem.
- **For the record:** nothing beyond s48-t1's.
- **Friction:** none.
- **Next:** s48-t3, the switch ring boards.
