# s52-t20 — do the generated courses finish? (s52-t18's five picks, first renders)

**Status:** OPEN

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
