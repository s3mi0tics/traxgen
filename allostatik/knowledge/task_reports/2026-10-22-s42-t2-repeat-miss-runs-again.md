# s42-t2 — run each miss code three more times (rerun of s42-t1)

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Do what s42-t1 was stopped from doing: three more runs of `I4BA3N5V6Y` and `8I8EVU4NCU` by link, to say whether each course's trail ends in the same place every run (#23).
- **Scope:** `scripts/probe_finish_frames.py`, only if a fix is needed to get the runs through.
- **Budget:** 30 minutes, 1 emulator session. If round 1 fails the way s42-t1 did (adb timeouts after the first launch), stop and don't spend the other rounds.
- **Done check:** s42-t1's five slots, unchanged: six runs, each settled with a `stop_square` that holds a true and ends false, and a `rendered.png` showing PROBOOK12; for each code, whether the goal-area crops (x 1250-1650, y 240-560) of the last frames are byte-identical, and if not, where each trail ends.
- **Outcomes declared before any live run:** s42-t1's, unchanged. Repeatable: goal 0 passes left of the rail and goal 2 passes right of it on every run, with byte-identical crops within each code. A trail that ends somewhere else on any run answers #23 yes. State of the Mac at open: up 16 days, `memory_pressure` 36 % free, load 5.1, no restart since s42-t1.

## Close

- **What happened:** _plain words_
- **What changed:** _files_
- **Evidence:** _task_check line, run lines_
- **Decisions made inside the task:** _one sentence each_
- **For the record:** _what the close folds in_
- **Friction:** _quoted, with what the task did_
- **Next:** _next task_
