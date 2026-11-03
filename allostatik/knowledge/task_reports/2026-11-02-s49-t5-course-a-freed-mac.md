# s49-t5 — course A after Colby freed memory (run after the session close)

**Status:** DONE

**In one paragraph:** Course A finished, first try, read FINISHED at 32 sparkles. It was the first clean first launch of the day, and it came right after Colby quit BambuStudio and a large Docker workload: boot 22.8 s, main menu 34.4 s (s48's were ~48 to 50 s). The trail runs from the launch pad through `SWITCH_LEFT` and along the goal rail, and the lever has swung. With s49-t1's offline checks and t2's held twin, item 23's three-part done check is met.

## Open (written before the work)

- **Goal:** Colby, after the close commit: "try one more time, I shut off a huge thing in docker and I also stopped bambu studio." Play A `DLYQPCH46H` by link in one probe session.
- **Note on order:** the ledger already reads `CLOSED s49`; this task runs after it at Colby's word, and its result is folded into the record with a follow-up commit.
- **Mac before the run:** swap 14,648 of 15,360 MB used (was 18,352 of 19,456), load 5.18 / 10.12 / 13.70, BambuStudio gone; the two Docker virtual machines still hold 5.1 and 4.2 GB; the stray mutant (PID 64287) still holds 2.5 GB.
- **Scope:** none in the repo; frames to `screenshots/finish_frames/` (gitignored).
- **Budget:** 1 probe session; no uploads.
- **Done check:** as s49-t3's: A's newest `frames.json` has no error, `settled` true, `finish: finished` with `finish_sparkles` >= 6; the last frame shows a trail through the switch into the goal rail.
- **Outcomes declared before any live run:** as s49-t2 declared for A: FINISHED, 18 to 102 sparkles, the lever swung.

## Close

- **What happened:** one session, `--link DLYQPCH46H`; device checks passed; attempt 1 loaded and played; emulator down at the end.
- **What changed:** nothing in the repo; frames `screenshots/finish_frames/DLYQPCH46H/run_4/`.
- **Evidence:** `frames.json`: `validity: active`, `finish: finished`, `finish_sparkles: 32`, `finish_peak: 1315`, `settled: true`, 10 frames, 0.71 s median interval. `after_09.png`, looked at: pink trail through the switch along the goal rail; lever on its other side.
- **Declared outcomes against what happened:** FINISHED, 32 sparkles, inside 18 to 102; lever swung. All held.
- **Decisions made inside the task:** none.
- **For the record:**
  - Item 23 done: a live switch course that finishes reads finished (32 sparkles), its held twin reads not finished (0).
  - D104: the checker's VALID on A matched the run, the first switch course the checker passed and the app finished.
  - #70 / #21: after freeing ~5 GB (BambuStudio) and a Docker workload, the first launch was clean and the menu came in 34 s; one run, so a candidate, not a finding. Swap read 16,396 of 17,408 MB used after the run.
- **Friction:** the task ran after `CLOSED s49`, at Colby's word; the routine has no step for that, so the result is folded in by a follow-up commit.
- **Next:** handoff.
