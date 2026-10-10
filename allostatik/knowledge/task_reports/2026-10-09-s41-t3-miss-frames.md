# s41-t3 — frames of runs that miss the goal

**Status:** STOPPED — needs Colby: on your phone, does the app load `I4BA3N5V6Y` (and `8I8EVU4NCU`)? "Track not found" there means the server side; a course on screen means the harness's typing.

**In one paragraph:** Both variants were built, proven to differ only in the goal rail's rotation, and uploaded: goal 0 is `I4BA3N5V6Y`, goal 2 is `8I8EVU4NCU`. murmelbahn fetches both, and goal 0's bytes match the upload exactly. In the app neither has ever loaded: three attempts gave one code field reading `II4` and two "Track not found" dialogs. No miss frames exist yet. The larger finding is item 18 caught live: on the first run the harness reported `inactive` for both codes, sampling the play-button spot on a Load-track dialog, and the refused-screen check did not recognise that dialog.

## Open (written before the work)

- **Goal:** Upload PROBOOK12 with only its goal rail turned (1 -> 0 and 1 -> 2), render both, press play and save the frames, so item 19's detector has runs that miss beside s41-t1's runs that finish.
- **Scope:** `scripts/make_goal_variants.py` (new), `scripts/probe_finish_frames.py`. Course files and frames land under `screenshots/finish_frames/`, which git ignores.
- **Budget:** 30 minutes, 2 uploads (Colby said yes, 2026-10-09), 1 emulator session.
- **Done check:**
  1. *Step:* build the two variants, prove each differs from PROBOOK12 in the goal rail's rotation only, upload, run the probe on both codes.
  2. *True after:* two share codes exist, each with a frames folder whose `frames.json` has no error, plus a reading of the play-button corner on every frame.
  3. *Miss cases:* a variant changed more than the goal's rotation, so a miss could come from the stray edit; the upload returned one code twice; a render landed on the wrong screen; the marble finished anyway, so there is still no miss.
  4. *Reads:* the builder's own assertions and printed lines; the two codes; `frames.json` and the PNGs; the corner samples.
  5. *Check:* the builder prints "nothing else" for both; the two codes differ; both `frames.json` have no `error`; and Claude's look at each final frame says where the trail ends, with at least one not in the goal.
- **Outcomes declared before any live run:** from Colby's s40 look ("turned other ways, it made the marble hit its side and roll along"), both variants miss: the triangle stays white, the trail ends off the goal rail. Unknown, and the point of the run: whether a miss also flips the button back to the triangle, and within the 60 s bound. If the marble rolls forever, the button stays a square and `settled` may still read true because the screen goes still. That is why the corner sample is the reading that counts.

## Close

- **What happened:** Session 1: menu reached (41.9s, 40.9s), first launch fine this time; `I4BA3N5V6Y`'s frame shows the Load-track dialog with `II4` in the field, `8I8EVU4NCU`'s shows "Track not found". `render_course` returned without error and the oracle said `inactive` for both. The play tap then hit nothing; `stop_square` was false on all 19 and 36 frames, and the menu's animation kept the screen moving (diffs ~1.6), so `settled` was false. Session 2: `I4BA3N5V6Y` again "Track not found" (before, after_00, after_01), then a truncated screencap (213,366 bytes) at after_02, then `adb: device offline` for every later call. The emulator is down.
- **What changed:** `scripts/make_goal_variants.py` (new); `scripts/probe_finish_frames.py` (records `stop_square` per frame, and the wait ends only when the screen is still and the button is back to a triangle).
- **Evidence:**
  - Builder: `goal rail 1 -> 0, nothing else; 1568 bytes`, `goal rail 1 -> 2, nothing else; 1568 bytes`.
  - Server: `curl https://murmelbahn.fly.dev/api/course/<code>/raw`: `I4BA3N5V6Y 200 1568`, `8I8EVU4NCU 200 1568`, `W8IEN7MG92 200 1563`; `cmp` goal0.course against the fetched bytes: identical.
  - `button_shows_stop` on s41-t1's frames: `SSSSSS.`, `SSSS...`, `SS....`, before-frames all false, matching t1's hand samples.
  - Failed frames: `screenshots/finish_frames/failed_typing/` (session 1) and `screenshots/finish_frames/I4BA3N5V6Y/` (session 2).
- **Decisions made inside the task:** Checked the codes through murmelbahn rather than re-uploading, so no third and fourth code was spent. Stopped after two sessions rather than a third: the cause can't be named from here, and a phone check separates the two candidates for free.
- **For the record:**
  - `plan.md` item 18, now observed live (2026-10-09): `render_course` returned success and the oracle `inactive` on a "Load track" dialog and on a "Track not found" dialog. Both are refused screens the set doesn't know. The stop square is a cheap positive check: a run that never shows it after play never ran.
  - `plan.md` open questions: why do two fresh codes that murmelbahn serves fail to load in the app? Candidates: the typing garbles them (one field read `II4`), or the app's lookup differs from the API path murmelbahn reads. s40's uploads, made the same way, load fine.
  - `plan.md` #21: the first launch after a cold boot did not die this time (2 sessions), so 3 of 3 is now 3 of 5.
  - `plan.md` #20: another truncated frame followed by `device offline`, this time during play (after_02), not during the menu wait.
- **Friction:** The probe catches every exception per course so one bad course can't cost the others. That also hides failures from `emulator.session()`, so no device evidence file was saved when the device went offline. A probe should re-raise device-level errors (`AdbCommandFailedError`, `FrameUnreadableError`) after recording them.
- **Next:** Colby's phone check. If the codes load on the phone, the harness's typing is the fault and gets fixed first, by reading back the code field before tapping load. If they don't, re-upload, and compare these two files with s40's for a difference the server cares about. Either way, item 18's guard (refuse any frame that shows a dialog) is now overdue and belongs in t2's detector.
