# s42-t1 — run each miss code three more times

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Run `I4BA3N5V6Y` (goal 0) and `8I8EVU4NCU` (goal 2) three more times each by link, and say whether each course's trail ends in the same place every run (#23).
- **Scope:** `scripts/probe_finish_frames.py` (a `--runs N` option that keeps each run's frames in its own folder, and alternates the codes so a slow drift within one boot doesn't line up with one code).
- **Budget:** 40 minutes, 2 emulator sessions.
- **Done check:**
  1. *Step:* one `--fresh` session; the two codes in turn, three rounds, each loaded by link, played and watched until settled.
  2. *True after:* six new runs on disk, three per code, each with a `rendered.png` showing PROBOOK12, a `stop_square` list holding a true and ending false, and a stated trail end.
  3. *Miss cases:* a run that never played (`stop_square` never true) counted as a run; a rendered frame that is a dialog or the menu; a run cut off by the 60 s bound (`settled` false) counted as an end; a comparison made against the s41 frames only, not across the new runs.
  4. *Reads:* each run's `frames.json`, `rendered.png` and last after-frame; the md5 of each last frame and of its goal-area crop (x 1250-1650, y 240-560, t5's crop).
  5. *Check:* every one of the six runs is settled with a true then false `stop_square`; for each code, report whether the goal-area crops of the last frames are byte-identical, and if not, Claude looks at them side by side and says where each trail ends.
- **Outcomes declared before any live run:** if a course ends the same way every run, all three goal-0 runs pass left of the rail onto the plate and all three goal-2 runs pass right of it, as in s41-t5, and the goal-area crops are byte-identical within each code (the control render is byte-identical across sessions, so a deterministic run should be too). Crops that differ but trails that end in the same place mean the trail is repeatable while something else on screen moves. A trail that ends somewhere else on any run answers #23 yes: the loop then needs several runs per course.

## Close

- **What happened:** _plain words_
- **What changed:** _files_
- **Evidence:** _task_check line, run lines_
- **Decisions made inside the task:** _one sentence each_
- **For the record:** _what the close folds in_
- **Friction:** _quoted, with what the task did_
- **Next:** _next task_
