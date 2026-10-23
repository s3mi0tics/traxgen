# s44-t1 — the graph checker, first design

**Status:** DONE

**In one paragraph:** A first design for the graph checker, agreed with Colby. A node is the marble crossing one doorway into one cell, at one height. Arrows run inside a piece (enter here, leave there) and between neighbouring pieces (one's way out is the other's way in). A course is valid when every route from the launch ends in a goal, with no dead end and no loop. The answer has three values: VALID, INVALID or UNMEASURED. Traced against the 20 measured finishes, it gets 20 of 20. But that trace tests only the half-hole term, which was fitted to the 3 misses. It also shows D066 is broader than the finish data: a *starter* on an uncompleted half-hole finished, so the finish rule is about the goal standing there.

## Open (written before the work)

- **Goal:** Propose a first design for the graph checker (what a node is, what an arrow is, what "valid" means, and where the half-hole rule sits) and trace it against the 20 entries in `graph.MEASURED_FINISHES`, for Colby to agree or change.
- **Scope:** this report only. No source changes; the design lives here until Colby agrees it, and t2 builds it.
- **Budget:** 45 minutes of reading and writing. No renders.
- **Done check:**
  1. *Step:* read the code the design builds on (`graph.py`, `plates.py`, `layout.py`, the corpus port findings), then write the design below with a trace of every `MEASURED_FINISHES` entry.
  2. *True after:* (a) the report defines node, arrow and valid in plain words, each tied to something already measured or marked as assumed; (b) it shows, for each of the 20 entries, what the design says and what was measured; (c) Colby has said yes, or said what to change.
  3. *Miss cases:*
     - The trace is typed by hand and disagrees with the table it claims to read.
     - The design reproduces the 20 only because it was fitted to them, and the report doesn't say which parts were fitted.
     - The design looks agreed because nobody objected, without Colby saying yes.
  4. *Reads:* `traxgen/graph.py` (`MEASURED_FINISHES`, `MEASURED_RUNS`), `traxgen/plates.py` (`half_hole_cells`), the output of the trace command pasted below, and Colby's reply in the session.
  5. *Check:* the trace table is the pasted output of a command run against `graph.MEASURED_FINISHES` this task, it reports how many of the 20 the design gets right, and the status line records Colby's answer.
- **Outcomes declared before any live run:** none, because there is no live run. Declared before the trace runs: the design should get 20 of 20, with the 3 misses explained by the half-hole rule alone. Anything less is a finding about the design.

## The design (proposed, for Colby)

### The picture in one paragraph

Think of every place a marble can cross from one hex into the next as a **doorway**. Each piece says which doorway the marble comes in by and which it leaves by. Two neighbouring pieces connect when one's way out is the other's way in. Follow the marble from the launch pad, doorway by doorway. The course is **valid** if every route ends in a goal: no route stops at a doorway with nothing behind it, and no route goes round in a circle forever. This is LeetCode 1059, *All Paths From Source Lead to Destination*, as vision.md says.

### Node: a doorway (port)

A node is **(cell, side, height)**: one hex cell, one of its six sides (0 to 5, E to SE, as in `hex.DIRECTION_NAMES`), and a height level.

- *Measured:* sides are the right unit. Rail ends in the corpus carry a side (`side_hex_rot`), and the starter's openings are sides {0, 2, 4} turned by its rotation (`STARTER_INTRINSIC_PORTS`, 380 corpus starters).
- *Measured:* heights come in steps (`y = 0.27 + 0.36k`, 8 levels, no exceptions in 43,375 rail ends), so height is a whole number k, not a float.
- *For the first build:* every piece sits flat on a baseplate, so k is always 0. Height is in the node from day one so nothing changes shape when stackers arrive.
- Two extra nodes: **START** (the marble's launch) and **GOAL** (the marble is caught). GOAL has no way out, and that's allowed.

**Amended after Colby's review: the node carries the direction of travel.** A node is the marble crossing one doorway *into* one cell: (cell entered, side it came in by, height). Plan item 1 already defined a port this way, as (side, height, direction-of-travel). Without the direction, a curve ridden A->B and one ridden B->A make two arrows between the same two nodes, which reads as a loop. And a cross piece sends two routes through one cell, so a loop has to mean reaching the same (doorway, direction) twice, never the same cell twice.

### Arrows, of two kinds

1. **Inside a piece:** "enter by this side, leave by that one". Each kind has its own rules, written once in the piece's own frame and turned by its `hex_rotation`. The first build needs only two pieces:
   - STARTER: START -> each of its three sides, (0, 2, 4) + rotation. *Measured* (the record).
   - GOAL_RAIL: enter by the side facing back toward the starter -> GOAL. *Measured:* the goal rotation rule `(d + 1) % 6`, with no exceptions in any campaign.
2. **Between pieces (a join):** a way out on side e of one cell meets a way in on side (e + 3) % 6 of the neighbouring cell, at the same height. A join needs both cells to be addressable on the plate each is named on. That's the s27 rule (`plates.is_addressable_on_plate`). Rails come later as a third kind of join, spanning a gap.

### Valid

Start at START and walk every arrow you can reach.

- **Dead end:** a way out the marble actually takes, with no join behind it, that isn't GOAL. That makes the course invalid, and the checker names the doorway.
- **Loop:** you reach a doorway you're already partway through. That's also invalid: the marble never finishes.
- **Valid:** neither happens.

The work grows with the number of doorways, never with the number of possible courses.

**One assumption, flagged rather than hidden.** The starter has three openings, but the marble doesn't leave by all three. In every recorded course two of them have nothing behind them, and the marble still finishes. So for the starter, a side with no join is not a route. The marble goes toward the attached piece. That's measured only with **one** piece attached. With two attached, which way it goes is unknown, and the first build refuses to answer rather than guess.

### The answer has three values, like `ConnectionStatus`

- **VALID**: every arrow on every route is measured.
- **INVALID**: a dead end or a loop, using measured arrows only.
- **UNMEASURED**: some arrow on a route rests on a piece rule nobody has measured (a curve's, for now).

This is the rule `graph.py` already lives by: a gap in the record never becomes a claim about the course. It also makes the checker useful before #7 is solved, because it says *which* piece rule is missing. That gives the unattended loop (item 20) its next measurement.

### The half-hole rule: two questions, not one

The 20 finishes split what used to be one question:

- **Placed legally?** This is what the play button checks. No half-hole term: goals on uncompleted half-holes rendered white (s28, and again in s43).
- **Does the marble get through?** This is what the finish burst checks. A GOAL_RAIL on an **uncompleted** half-hole has no arrow to GOAL. The marble arrives and isn't caught.

**This is narrower than D066, and the record says so.** D066 says a half-hole "is not a usable square". But r06 puts the **starter** on the uncompleted half-hole (0,1) of a lone plate, and it finished (peak 964). So the finish rule is about the goal standing there, not the square in general.

**What's fitted.** The half-hole term was written after seeing the 3 misses. All 3 share one placement: starter (0,0), goal East on (0,1), at rotations 0, 2 and 4. So "a goal on an uncompleted half-hole" and "this one placement" can't be told apart yet. *Cheap test:* goals on the other two half-holes, (-1,3) and (-2,5), reached from a side other than West. That's a handful of renders. The generator already refuses half-holes (`plates.is_buildable_on_plate`), so nothing the product emits depends on the answer.

### Trace against `MEASURED_FINISHES`

Pasted output of `trace2.py` (scratchpad, run this task). The "join?" column is `graph.predict_connection`, and the half-hole column is `plates.half_hole_cells`, with "uncompleted" meaning no plate at the owner's +(5,0).

| entry | starter (cell, rot) | goal cell, plate | join? | goal on open half-hole? | design says | measured |
|---|---|---|---|---|---|---|
| r00-d0 | (0, 0), 0 | E -> (0, 1), plate (0, 0) | yes | yes | misses | misses |
| r00-d2 | (0, 0), 0 | NW -> (-1, 0), plate (0, 0) | yes | no | finishes | finishes |
| r01-d1 | (0, 0), 1 | NE -> (-1, 1), plate (0, 0) | yes | no | finishes | finishes |
| r02-d0 | (0, 0), 2 | E -> (0, 1), plate (0, 0) | yes | yes | misses | misses |
| r02-d2 | (0, 0), 2 | NW -> (-1, 0), plate (0, 0) | yes | no | finishes | finishes |
| r03-d1 | (0, 0), 3 | NE -> (-1, 1), plate (0, 0) | yes | no | finishes | finishes |
| r04-d0 | (0, 0), 4 | E -> (0, 1), plate (0, 0) | yes | yes | misses | misses |
| r04-d2 | (0, 0), 4 | NW -> (-1, 0), plate (0, 0) | yes | no | finishes | finishes |
| r05-d1 | (0, 0), 5 | NE -> (-1, 1), plate (0, 0) | yes | no | finishes | finishes |
| r06-d2 | (0, 1), 0 | NW -> (-1, 1), plate (0, 0) | yes | no | finishes | finishes |
| r07-d0 | (-3, 2), 0 | E -> (-3, 3), plate (0, 0) | yes | no | finishes | finishes |
| r07-d2 | (-3, 2), 0 | NW -> (-4, 2), plate (0, 0) | yes | no | finishes | finishes |
| r07-d4 | (-3, 2), 0 | SW -> (-2, 1), plate (0, 0) | yes | no | finishes | finishes |
| r08-d1 | (-3, 2), 1 | NE -> (-4, 3), plate (0, 0) | yes | no | finishes | finishes |
| r08-d3 | (-3, 2), 1 | W -> (-3, 1), plate (0, 0) | yes | no | finishes | finishes |
| r08-d5 | (-3, 2), 1 | SE -> (-2, 2), plate (0, 0) | yes | no | finishes | finishes |
| r09-d2 | (0, 1), 0 | NW -> (-1, 1), plate (0, 0) | yes | no | finishes | finishes |
| r10-d0 | (0, 1), 0 | E -> (-5, 2), plate (5, 0) | yes | no | finishes | finishes |
| r10-d4 | (0, 1), 0 | SW -> (-4, 0), plate (5, 0) | yes | no | finishes | finishes |
| r11-d4 | (-4, 0), 0 | SW -> (-6, 5), plate (3, -6) | yes | no | finishes | finishes |

20 of 20 right

**What this trace does and doesn't test.** All 20 entries are cells the placement record already calls live, so "join?" is yes on every row. **This trace tests only the half-hole term.** The joining rule is tested by the placement record's dark cells, which the existing model already reproduces (every row in `MEASURED_RUNS`; `tests/test_graph.py`). A finish-level test of a join that *fails* has no data yet.

### What the first build (t2) would be

- A new module, `traxgen/track_graph.py`. `graph.py` is 1,400 lines of pair classification and the record, and the checker is a different concern that reads it.
- Nodes, the two piece rules, joins, the walk (dead end, loop), and the three-valued answer, with the dead-end doorway named.
- Tests: all 20 `MEASURED_FINISHES` entries, built as courses and checked. Every `MEASURED_RUNS` dark cell checked INVALID or UNMEASURED, never VALID. A hand-made loop and a hand-made dead end. A curve anywhere giving UNMEASURED.
- Not in it: rails, heights above 0, switches, energy, and any piece besides STARTER and GOAL_RAIL.
- Known limits, not built around: the graph says a route *can* connect, not that physics carries the marble along it (vision.md; #23). And switches will add their state to the node when they arrive.

## Close

- **What happened:** read the code the design builds on, wrote the design, and traced the proposed rule against all 20 `MEASURED_FINISHES` entries with a script whose output is pasted above. Colby approved the shape ("yes unless you can think of something we are missing"). The one addition was direction of travel in the node.
- **What changed:** this report only.
- **Evidence:** trace, 20 of 20 right. `task_check` line is in the close commit's output.
- **Decisions made inside the task:**
  - The checker is a new module, `traxgen/track_graph.py`, not more of `graph.py`.
  - The answer is three-valued, like `ConnectionStatus`.
  - With two or more pieces attached to the starter, the checker returns UNMEASURED. Measured only with one; Colby had not objected when t2 opened.
  - The half-hole finish rule applies to the goal only, and is labelled fitted.
- **For the record:**
  - `decisions.md`: the graph checker's node, arrow and validity definitions, and its three-valued answer (s44).
  - `decisions.md` / D066 note: the finish evidence is goal-only. r06 (starter on the uncompleted half-hole (0,1), lone plate) finished, peak 964. So "not a usable square" holds for building and for a goal's finish, not for every piece standing there.
  - `plan.md` open question: are the 3 misses about the half-hole or about the one placement? Cheap test: goals on (-1,3) and (-2,5) of a lone plate, from a side other than West.
  - `plan.md` item 2: design agreed (this report); t2 builds the first version.
- **Friction:** a design task has no file scope, and `scope=` is empty. `task_check` accepted that, so this is noted, not a problem.
- **Next:** s44-t2, build `traxgen/track_graph.py`.
