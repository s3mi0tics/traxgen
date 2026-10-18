# s41-t5 — load by link, and capture the miss runs

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** Teach the finish-frame probe to load a course by share link (s41-t4) instead of typing, and use it to capture the play runs of `I4BA3N5V6Y` (goal 0) and `8I8EVU4NCU` (goal 2), the frames s41-t3 couldn't get.
- **Scope:** `scripts/probe_finish_frames.py`.
- **Budget:** 30 minutes, 2 emulator sessions.
- **Done check:**
  1. *Step:* reset to the main menu, send the link, tap Load track, tap the loaded-track hex as the typed path does, then the existing play-and-watch.
  2. *True after:* for both codes, a `rendered.png` showing PROBOOK12's layout in the editor, and an after-play series whose `stop_square` reads true at least once and ends false.
  3. *Miss cases:* the rendered frame is a dialog or the menu, which is t3's failure again (Claude looks at every `rendered.png`); play never ran (`stop_square` never true); the run never ended within 60 s.
  4. *Reads:* `rendered.png`, `frames.json` (`stop_square`, `settled`), the final after-frame.
  5. *Check:* both `rendered.png` show the course; both `stop_square` lists contain a true and end false; Claude states where each trail ends.
- **Outcomes declared before any live run:** from Colby's 2026-10-18 look, one of the two rolls past the goal rail onto the base plate (a clear miss), and the other's trail stops exactly where it meets the goal rail. Which code is which is unknown. For the second, a trail ending that looks like the as-built course's finish means either it isn't a miss or the end of the trail can't tell the two apart; this task only records it.

## Close
