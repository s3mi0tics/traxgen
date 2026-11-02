# s48-t4 — does a marble passing a switch flip its lever for the next one?

**Status:** OPEN

**In one paragraph:** _written at close_

## Open (written before the work)

- **Goal:** on one goal-less board, two marbles reach the same switch, the first by the side that passes and the second, delayed by a curve, by the side that stopped in s48-t3; read from the trails whether the second one passes.
- **Scope:** `scripts/probe_switch_flip.py` (new). Manifest and frames go to `screenshots/` (gitignored).
- **Budget:** 1 upload; at most 2 probe sessions; 20 minutes of device time.
- **Done check:**
  1. *Step:* build and upload the board (`left_pair`, `left_stop_only`, `right_pair`, `right_stop_only`, each switch at rotation 0); play it once by link through the probe.
  2. *True after:* for each of the four tests, which marbles left the switch and by which side, or stopped in it, read from frames on disk of a run that settled.
  3. *Miss cases:* the board loads without a course (now refused); the second marble reaches the switch first; a pad loads no marble and the test reads as "stopped"; a trail is counted on the wrong test.
  4. *Reads:* `screenshots/ring_board/switch_flip.json`; the run's `frames.json`; `before.png` (every pad shows a marble) and the mid-run and last frames, looked at.
  5. *Check:* `before.png` shows a marble on every pad, the run settles with no error, and each test gets one line: per pad, "left by side N" or "stopped in the switch" or "no marble", with the frame that shows it.
- **Outcomes declared before any live run:**
  - Controls: each lone stopping pad's marble stops in the switch, as in s48-t3 (`left_stop_only` by side 4, `right_stop_only` by side 0). If a control passes, the stop is not about the side, and the pair tests say nothing.
  - Pairs, if a passing marble flips the lever: the near pad's marble leaves by side 2, then the curve pad's marble passes too, also by side 2.
  - Pairs, if it doesn't flip: the near pad's marble leaves by side 2 and the curve pad's marble stops in the switch, as in the control.
  - If the curve marble arrives first, the pair reads like "doesn't flip" and the mid-run frames show the order; then the result is "order wrong", not a finding.
