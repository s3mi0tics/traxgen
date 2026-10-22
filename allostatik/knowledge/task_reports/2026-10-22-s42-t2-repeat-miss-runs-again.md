# s42-t2 — run each miss code three more times (rerun of s42-t1)

**Status:** DONE

**In one paragraph:** All six runs worked first try, the first launch after the cold boot included. Each course misses every time, the same way: goal 0's trail always passes left of the goal rail and goal 2's always passes right. But the trail doesn't end in the same place twice. How far it runs past the rail changes from run to run, by up to about 30 px on screen. The course loads byte-identically every run, so the variation is in the app's physics, not in our loading. The declared outcome that the last frames would be byte-identical within each code failed: none of the eight were. So #23's answer is the same verdict every run, but not the same ending. A finish check has to judge where the trail ends with some slack, and a course whose trail ends near a goal's edge may need more than one run.

## Open (written before the work)

- **Goal:** Do what s42-t1 was stopped from doing: three more runs of `I4BA3N5V6Y` and `8I8EVU4NCU` by link, to say whether each course's trail ends in the same place every run (#23).
- **Scope:** `scripts/probe_finish_frames.py`, only if a fix is needed to get the runs through.
- **Budget:** 30 minutes, 1 emulator session. If round 1 fails the way s42-t1 did (adb timeouts after the first launch), stop and don't spend the other rounds.
- **Done check:** s42-t1's five slots, unchanged: six runs, each settled with a `stop_square` that holds a true and ends false, and a `rendered.png` showing PROBOOK12; for each code, whether the goal-area crops (x 1250-1650, y 240-560) of the last frames are byte-identical, and if not, where each trail ends.
- **Outcomes declared before any live run:** s42-t1's, unchanged. Repeatable: goal 0 passes left of the rail and goal 2 passes right of it on every run, with byte-identical crops within each code. A trail that ends somewhere else on any run answers #23 yes. State of the Mac at open: up 16 days, `memory_pressure` 36 % free, load 5.1, no restart since s42-t1.

## Close

- **What happened:** One `--fresh` session, 2026-10-22. Boot 26.7 s on Metal, 0 bad color buffers. Six runs, alternating codes, every one attempt 1, `active`, settled. Main menu after 31.5, 24.1, 17.6, 15.7, 15.1 and 15.2 s; each run settled in 11.2 to 15.6 s. Teardown PASS emulator_down. The Mac had not been restarted (up 16 days, 36 % free), so s42-t1's failures were not down to the Mac's memory alone.
- **What changed:** nothing in scope. The probe ran as committed in s42-t1.
- **Evidence:**
  - `task_check`: `s42-t2: in scope -- 0 files changed since open commit a7ed1d8, all declared`.
  - `stop_square` per run: `TTTFFF`, `TTTFFF`, `TTTTFF`, `TTTFFF`, `TTTTTFFFF`, `TTTTTFFFF` (I4 run_1, 8I run_1, I4 run_2, 8I run_2, I4 run_3, 8I run_3).
  - `rendered.png` md5 per code, the same across s41-t5 and run_1-3: I4 `4785f9236d`, 8I `aeb448a17d`.
  - Goal-area crop md5s all differ (I4: `11cc094423`, `061ce3fdb0`, `ccb0545683`, `f16ca9c3b8`; 8I: `1e2753a279`, `4fa7622200`, `fd80c7da38`, `cf9eff3a9b`, s41-t5 first).
  - Trail bounding boxes agree to a few px, except where the trail ends: 8I's right edge reaches x 1515, 1493, 1484, 1520. The pink-mask overlap between runs is only 0.20 to 0.58, which reads as the chevron pattern shifting along the trail as well as the end moving. Claude's look at the trail ends (crops 8I x 1380-1560 y 270-390, I4 x 1260-1440 y 260-380) is in the paragraph above.
  - Done check: met for the six runs. Declared outcome "byte-identical crops within each code": **failed**.
- **Decisions made inside the task:** Judged by eye at the trail ends, not by the crop hashes, as the done check's fallback says.
- **For the record:**
  - #23 answered: same verdict every run, not the same ending. The app's physics varies run to run on a byte-identical load, so a finish check needs slack, and a near-edge course needs repeat runs.
  - #21: 1 clean first launch of 1 this time, on an unrestarted Mac at 36 % free, where s42-t1 failed at 41 % free. Neither host memory nor restart separates good boots from bad.
  - Masks from a pink threshold miss the trail's dark chevrons, so two masks of the same trail overlap poorly. The detector should grow the mask, or judge the trail's outline, not compare pixels.
- **Friction:** none.
- **Next:** t3, the finish detector. First it needs a way to find the goal piece on screen; Colby picks the approach.
