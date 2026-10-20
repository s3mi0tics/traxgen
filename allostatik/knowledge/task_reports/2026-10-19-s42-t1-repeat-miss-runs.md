# s42-t1 — run each miss code three more times

**Status:** STOPPED — needs Colby: rerun in the morning, on a rested Mac. The command is `caffeinate -di uv run python -m scripts.probe_finish_frames --link --runs 3 I4BA3N5V6Y 8I8EVU4NCU`.

**In one paragraph:** The probe now repeats runs (`--runs N`), and each run gets its own folder. The live run was stopped partway at Colby's call, because memory pressure looked too high to finish. No usable run came out of it, so #23 is still open. Of four render attempts, one loaded. It read `inactive` and hadn't settled when the 60 s limit ran out. The others failed on adb timeouts (`monkey`, `force-stop`) and on one main-menu wait that ran out at 90 s. That's how the device acts when it's struggling, so these runs count as unmeasured, not as data about the courses.

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

- **What happened:** One `--fresh` session on 2026-10-19. `I4BA3N5V6Y` run_1: attempt 1 died at launch (`monkey`, adb timeout), the #21 shape. Attempt 2 reached the main menu after 92.5 s and loaded by link, but read `inactive`, `settled` false after 63.2 s, with the frame diffs still above 1.0 at the end. `8I8EVU4NCU` run_1: both attempts failed on adb timeouts (`force-stop`, then `monkey`). `I4BA3N5V6Y` run_2: attempt 1's main-menu wait timed out at 90 s with the app in front (distance 127.1). Colby stopped the run during attempt 2. The emulator was then shut down with `scripts.emulator kill` (PASS emulator_down). `memory_pressure` read 41 % free after the shutdown.
- **What changed:** `scripts/probe_finish_frames.py`: `--runs N` (codes alternate round by round, frames go to `<code>/run_<k>/`). Also corrected the retry comment, which said the first launch died in every s41 session; the record says 4 of 7.
- **Evidence:** `task_check`: `s42-t1: in scope -- 1 files changed since open commit ee84255, all declared`. Done check: not met (0 of 6 runs usable). Run lines are in this session's scratchpad, not committed.
- **Decisions made inside the task:** The broken frames under `screenshots/finish_frames/*/run_1` and `run_2` stay on disk (gitignored). The rerun overwrites them.
- **For the record:**
  - #21: the first launch after a cold boot died again (5 of 8 sessions now). This time later launches in the same boot failed too, with adb timeouts. That's new: in s41 no later launch failed.
  - The probe still catches errors course by course, so these failures saved no device evidence file. This is the t3 friction s41 named, firing again.
- **Friction:** none in the routine's text.
- **Next:** in the morning, the same command from a rested Mac. If the first round is clean, carry on to t2 (the detector).
