# Check a course file

Given any `.course` file, traxgen reads the bytes back, re-serializes them, and
requires identical bytes. It then runs every validator rule and lists all
violations, WARNINGs included.

## Sub-features

- `check-roundtrip` parse -> serialize is byte-identical.
- `check-parse-fail` a malformed file fails with the parser's offset message.
- `check-validator` full rule list with severities; exit 1 on any ERROR.

## How to get to it (user POV)

- `uv run python .claude/skills/verify/scripts/check_course.py FILE [--set vertical-starter]`
- As the `check` stage of `verify_chain.sh`.

## Driving it with verify_chain

Preconditions:

- A `.course` file: a run's `course.course`, or a fixture under `tests/fixtures/`.

- **Good file.** Run `check_course.py verify-runs/<run>/course.course`. Exit 0;
  `PASS round_trip 177 bytes ...`; `PASS validator 0 errors, 0 warnings`;
  `claim: CONNECTED`.
- **Four-plate file.** Same on a standard-square run: `PASS round_trip 253`,
  one `WARNING START_GOAL_CONNECTED: Cannot verify ...`, `claim: UNMEASURED`, exit 0.
- **Negative control, flipped byte.** Copy a good course, XOR its last byte with
  `0xFF`, and check it. Exit 1; `FAIL round_trip 177 -> 177 bytes, first difference at offset 176`.
- **Negative control, truncated.** `head -c 170` of a good course. Exit 1;
  `FAIL round_trip parse raised ValueError: short read ...`.

## Gotchas

- Exit 0 with WARNINGs is correct. WARNING means unmeasured, not wrong. Report
  the WARNINGs anyway.
- The parser speaks the POWER_2022 era (v4). App-exported SkyTrax-era (v7)
  files fail to parse until plan item 8 lands. That is a known gap, not a
  round-trip bug.
