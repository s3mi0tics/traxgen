# s48-t4 — does a marble passing a switch flip its lever for the next one?

**Status:** DONE, with two deviations: the delay became a straight run of X-intersections at Colby's word, and the controls ran only on the first board

**In one paragraph:** A marble that passes a switch flips its lever for the next one. On the board with the delayed pad three X-intersections away (`8WL7RXS9H4`), the frames show the order. For `SWITCH_LEFT`, the near marble went in by side 0 and out by side 2. Then the delayed marble came in by side 4, the side that stops a lone marble, and passed out side 2. `SWITCH_RIGHT` did the mirror: in by 4, out by 2, then in by 0 and out by 2. On the first board (one curve of delay, `ZJR47DUFFX`) both lone-pad controls stopped, as in s48-t3, and both pairs sent two marbles out side 2, but the frames could not show the order. Six X-intersections (`8D9CU5AEY3`) was too long: one delayed marble stopped on the line and the other left it before the switch. What the switch does depends on which marble gets there first, so with more than one marble the result depends on timing.

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

## Close

- **What happened:**
  - Board 1, `ZJR47DUFFX` (`--run` did not exist yet; one curve between the far pad and the switch): attempt 1 refused as a loading screen (0.654 near-white), attempt 2 played. Controls stopped; both pairs sent two marbles out side 2; frames 2.6 s apart, so the order is unknown.
  - Colby: "you have to put the second marble further away for the timing to work." The delay became `--run N` X-intersections in a straight line, with `--pairs-only`, since four tests no longer fit.
  - Board 2, `8D9CU5AEY3` (run 6): attempt 1 refused as a loading screen (0.652), attempt 2 played. The near marbles passed out side 2. The delayed marbles never reached the switch: `left_pair`'s stopped on the line, and `right_pair`'s left it near the end.
  - Board 3, `8WL7RXS9H4` (run 3): played first try; the result above, in order, frames 0.7 s apart.
  - The emulator was down after each session.
- **What changed:** `scripts/probe_switch_flip.py` (new).
- **Evidence:**
  - Frames `screenshots/finish_frames/8WL7RXS9H4/after_00` to `after_03`. `left_pair`: red out side 2 in `after_00`; green on the switch in `after_01`, past it on red's trail in `after_02` and `after_03`. `right_pair`: blue out side 2 in `after_00`; red coming down the line in `after_00`, at the switch in `after_01`, out along blue's trail in `after_02`.
  - Controls on `ZJR47DUFFX/after_07`: `left_stop_only`'s red and `right_stop_only`'s green trails end at the switch.
  - ruff clean on the script.
- **Decisions made inside the task:**
  - The X-intersection's rotation comes from `track_graph.CROSS_TRACKS`, not a formula. The formula I first wrote, `(side + 3) % 6`, would have laid every track across the line; caught before upload by checking it against the table.
  - Uploaded two lengths, 6 and 3, in one session, in case the long run lost the marble. It did.
- **For the record:**
  - Switch (D-row candidate): a passing marble flips the lever. After one marble passes `SWITCH_LEFT` (0→2), side 4 passes to 2, which is `SWITCH_RIGHT`'s table; and the mirror. So the evidence fits the two kinds being one piece in two lever states (#1), with side 2 as the switch's common end and sides 0 and 4 its branches. Whether a marble entering by side 2 flips the lever is not measured directly; the t3 frames show levers swung after such passes.
  - #27: with two marbles on one switch, what happens depends on arrival order, which the app's physics decides. A checker can say what one marble does; with more than one, it can't without timing.
  - Ring and probe boards: a marble on six flat X-intersections in a row stops or leaves the line; three is fine.
  - Unknown, seen twice: a red hexagon flashes where a marble comes to rest off a track.
  - #21: 3 sessions, 4 load attempts, 2 refused as loading screens, both caught by s48-t1's check.
- **Friction:**
  - I wrote the script before the `TASK-OPEN` commit; the open commit still carried only the ledger and the report, so `task_check` passes, but the order broke the routine's rule. Nothing was run or uploaded before the open.
  - A done check declared before Colby's design change was carried through a change of instrument; the change and its reason are in *What happened*.
- **Next:** the switch rule, or the written reason the checker can't hold it yet.
