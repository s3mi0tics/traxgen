# s52-t19 — play the GOAL_BASIN board (resumes s52-t17, stopped on memory)

**Status:** DONE

**In one paragraph:** The GOAL_BASIN's entrances are its piece sides 0, 2 and 4, exactly as the corpus proposed, and a marble caught in it finishes. On `6ZX7WEFRTJ` the pads at rotations 1, 3 and 5 sent a marble into their basin (trail ends 32, 31, 26 px from the basin's centre) and the pads at 0, 2 and 4 loaded no marble at all -- 6 of 6 as declared in s52-t17. The board read placement active and finished (89 sparkles, frames 0.61 s apart), so the basin bursts like the goal rail. This is the first piece rule proposed by the corpus before any render and then confirmed by one.

## Open (written before the work)

- **Goal:** play `6ZX7WEFRTJ` once by link and score it against s52-t17's declared outcomes.
- **Scope:** none beyond the ledger and this report (frames go to `screenshots/`, gitignored).
- **Budget:** two attempts, 15 minutes.
- **Done check:**
  1. *Step:* `probe_finish_frames --link 6ZX7WEFRTJ`, then `read_trail_ends` against `screenshots/ring_board/goal_basin.json`, and a look at the frames.
  2. *True after:* per rotation, marble loaded or not and where its trail ends; the board's finish verdict.
  3. *Miss cases:* the load lands on a non-course screen and is read (D102's check refuses those); a trail claimed by the wrong pad.
  4. *Reads:* the run's frames and `frames.json`.
  5. *Check:* the report scores all six rotations against "1, 3, 5 catch; 0, 2, 4 load no marble" (s52-t17).
- **Outcomes declared before any live run:** as s52-t17: rotations 1, 3, 5 catch; 0, 2, 4 load no marble.

## Close

- **What happened:** `uv run python -m scripts.probe_finish_frames --link 6ZX7WEFRTJ` (exit 0). Attempt 1: main-menu wait timed out after 90 s, launcher in front, 5 of 25 frames unreadable (evidence `screenshots/device_evidence/20261124-071014.txt`). Attempt 2, same boot: menu after 15.9 s; `validity: active`, `finish: finished`, `finish_sparkles: 89`, `finish_peak: 3405`, `median_interval: 0.61`, 11 frames over 8.1 s. Trails read by `read_trail_ends.read` against each basin: rot0 none; rot1 32.2 px; rot3 31.2 px; rot5 26.4 px; rot2 and rot4 a 405-px piece ending 240-242 px from their own basin -- a neighbouring pad's trail (pads closer than about two cells, s52-t4's known limit). A crop of every pad (before, mid-run, last frame), looked at: red, green and blue trails into the basins at rotations 1, 3 and 5; no trail at 0, 2 and 4.
- **Score against the declared outcomes:** 6 of 6.
- **What changed:** this report and the ledger only.
- **Evidence:** the probe's result line above; the crops.
- **Decisions made inside the task:** read rotations 2 and 4 from the crops, not the trail reader, because the reader's own limit (close pads) explains its reading.
- **For the record:**
  - `decisions.md` (new row): GOAL_BASIN takes a marble in by piece sides 0, 2, 4 (in `track_graph`'s frame) and holds it; a marble in it finishes (89 sparkles). Proposed by the corpus (s52-t13, 220 rail ends), confirmed on `6ZX7WEFRTJ`, each rotation once. Candidate for `track_graph.PIECE_RULES`, and for the order line's "first finishing run on each other goal piece": done for GOAL_BASIN.
  - `vision.md`, *How far does decoding scale?*: the inversion ran end to end on a new piece -- corpus rails proposed the entrances, one board of six rotations confirmed them, no sweep.
  - `plan.md` #21: s52, 3 boots after t17's two: control (menu 25.2 s, then a loading screen refused, 0.650 white); basin attempt 1 (launcher, 90 s timeout), attempt 2 same boot (good). Swap 18.9 -> 20.3 GB around the control. Same-boot retries keep working where fresh boots do not.
  - `screenshots/rendered_KN6F459ZR3.png` was overwritten by the refused loading frame (hash `753d5022...`); the control hash check needs a good control render before it is used again.
- **Friction:** none.
- **Next:** the five generated routes (s52-t18), same probe, one boot each.
