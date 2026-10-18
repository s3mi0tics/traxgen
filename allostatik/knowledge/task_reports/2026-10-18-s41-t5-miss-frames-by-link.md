# s41-t5 — load by link, and capture the miss runs

**Status:** DONE

**In one paragraph:** Loading by link worked first try for both codes, the first launch after the cold boot included. Both goal variants render with a white triangle and both are clear misses: goal 0's trail passes the goal rail to the left and goal 2's to the right, each ending on the plate. Set beside the as-built finish (trail runs up the goal rail) and goal 4 (trail stops where it meets the rail), the four PROBOOK12 runs give item 19 its first labelled set: one finish, two misses, one undecided. Apart from the trail, nothing on screen marks a finish, so the check has to read where the trail ends.

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

- **What happened:** One session. `I4BA3N5V6Y`: menu in 31.9s, loaded by link, `active`, `stop_square` `SSSSS..`, settled at 12.5s. `8I8EVU4NCU`: menu in 15.3s, `active`, `SSSSS....`, settled at 14.9s. Claude's read of the goal area, all four PROBOOK12 runs (sheet built from `THIIEUH35Z/after_06`, `W8IEN7MG92/after_06`, `I4BA3N5V6Y/after_06`, `8I8EVU4NCU/after_08`, crop x 1250-1650, y 240-560): as built (goal 1), trail runs up the length of the goal rail; goal 4, trail ends at the rail's near end; goal 0, trail passes left of the rail onto the plate; goal 2, trail passes right of the rail onto the plate.
- **What changed:** `scripts/probe_finish_frames.py` (`--link` mode: menu, link, Load track, loaded-track hex).
- **Evidence:**
  - The two `frames.json` lines above; both `rendered.png` show PROBOOK12 in the editor.
  - Change outside the trail, before vs last frame (pixels whose RGB moved more than 60 in total, minus the trail mask grown 6 px, toolbar excluded): as built 270, goal 4 305, goal 0 361, goal 2 358, `KN6F459ZR3` 0. The same small spots appear in every run (largest blob 342 px). Nothing is specific to the finish. Run with `uv run --with numpy --with scipy`, since neither is a project dependency.
  - Done check: met. Both rendered frames show the course; both `stop_square` lists hold a true and end false; trail ends stated above.
- **Decisions made inside the task:** Reset to the main menu before sending the link, so a first-launch death (#21) costs a menu wait, not a link.
- **For the record:**
  - `plan.md` *What is true now*: two PROBOOK12 variants whose marble misses the goal both show a white triangle (2026-10-18). The triangle is not a finish check, now shown by harness frames as well as by Colby's eye.
  - `plan.md` item 19: a labelled set exists in `screenshots/finish_frames/` (gitignored): finish `THIIEUH35Z`, `KN6F459ZR3` (eye); miss `I4BA3N5V6Y`, `8I8EVU4NCU`; undecided `W8IEN7MG92`. No on-screen finish signal other than the trail.
  - `plan.md` item 18 / `render_course`: loading by link removes typing; the first two uses both worked (2 of 2).
  - `observations.md`: s40's "B's turned goal still caught the marble" (W8IEN7MG92) now looks different in harness frames: the trail stops at the rail's end and doesn't run along it. Whether that is a catch is the open question.
- **Friction:** none.
- **Next:** Colby watches `W8IEN7MG92` run once and says whether the marble ends in the goal. Then the finish detector (trail end inside the goal rail's footprint), tested on these frames, and loading by link moves into `render_course`.
