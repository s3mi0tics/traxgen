# s52-t20 — do the generated courses finish? (s52-t18's five picks, first renders)

**Status:** DONE

**In one paragraph:** All five courses the route search generated finish in the app, 5 of 5 as the checker predicted: one curve each way, one X-intersection, curve-cross-curve, and two curves and a cross on both curve tracks. Four read `finished` by the sparkle count (24 to 34 sparkles). The fifth, `X6XXWZV7FS`, read `not_finished` with frames 0.63 s apart -- but its trail ends in the goal rail (26 px) and the app threw a celebration over the goal: pastel coloured fireworks, not the white star sparkles the counter looks for (peak 67 near-white pixels, 1 sparkle). So the app has at least two finish animations and the sparkle count sees only one. The generator's first five courses are certified by the app; the finish check has a false negative to fix.

## Open (written before the work)

- **Goal:** play the five routes s52-t18's search generated and the checker called VALID, once each, in one boot, and score each against its prediction.
- **Scope:** none beyond the ledger and this report.
- **Budget:** one boot, one retry per code, 20 minutes.
- **Done check:**
  1. *Step:* `probe_finish_frames --link 5O3ZSS2LTE K755C9FBKM NXRDV4EKOK X6XXWZV7FS QO4BBHN94B`; trails read against each route's goal rail.
  2. *True after:* per code, placement reading, finish verdict with sparkles and frame spacing, and trail end to the goal.
  3. *Miss cases:* a `not_finished` read with frames more than 1.5 s apart (s52-t2: not evidence); a load on a non-course screen.
  4. *Reads:* each run's `frames.json` and frames; `screenshots/ring_board/routes.json`.
  5. *Check:* every code is scored finished / not / unjudged with its spacing, and every disagreement between sparkles and trail is named.
- **Outcomes declared before any live run:** all five finish (`check_course` VALID): gentle_curve `5O3ZSS2LTE`, sharp_curve `K755C9FBKM`, cross `NXRDV4EKOK`, curve_cross_curve `X6XXWZV7FS`, longest `QO4BBHN94B`. A miss is a checker error to chase.

## Close

- **What happened:** one boot, all five first attempt (`probe_finish_frames --link`, exit 0). Readings (placement / finish / sparkles / peak / spacing): `5O3ZSS2LTE` active / finished / 33 / 944 / 1.10 s; `K755C9FBKM` active / finished / 34 / 1,028 / 0.60 s; `NXRDV4EKOK` active / finished / 24 / 761 / 0.65 s; `X6XXWZV7FS` active / not_finished / 1 / 67 / 0.63 s; `QO4BBHN94B` active / finished / 28 / 1,082 / 0.63 s. For `X6XXWZV7FS`: per-frame near-white 8, 8, 9, 8, 67, 64, 45 (stop square on) then 0; burst frame's largest white component 15 px; `read_trail_ends` end 26.3 px from the goal, in goal; full frames looked at -- `after_05` shows coloured fireworks above the goal rail, where `K755C9FBKM/after_04` shows white stars.
- **Score against the declared outcomes:** 5 of 5 finish (four by sparkles, one by trail and eye against a sparkle false negative).
- **What changed:** this report and the ledger only.
- **Evidence:** the readings above; the two full frames.
- **Decisions made inside the task:** score `X6XXWZV7FS` as finished on the trail and the frame, and name the sparkle reading a false negative, because the trail is in the goal and the burst is visible.
- **For the record:**
  - `plan.md` item 2 / vision.md *Generation*: the route search's first five courses all finish -- the generator produces app-certified multi-piece courses from measured pieces. Wiring it into `generate --set vertical-starter` is the next step (Colby's design call on the API).
  - `plan.md` item 24: trigger fired again, differently -- a `not_finished` at good spacing (0.63 s) on a finish, because the celebration was coloured fireworks, not white stars. D105's sparkle count is a white-only detector. Item 24 (b) (trail end) caught it; the finish check should flag a sparkle/trail disagreement as UNJUDGED.
  - `observations.md`: re-fires "keep looking for other finish signals" (Colby, s49) -- a second, independent way the sparkle count says no on a finish.
- **Friction:** none.
- **Next:** s52-t21, the coloured celebration measured on the frames on disk.
