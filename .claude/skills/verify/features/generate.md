# Generate a course

A builder names a piece set and a board, and traxgen writes a `.course` file
that passed strict validation. It prints a `claim:` line saying whether the
rendered record has measured that placement.

## Sub-features

- `gen-single` writes the Phase 1 course: 177 bytes, `claim: CONNECTED`.
- `gen-square` writes a four-plate course: `claim: UNMEASURED`.
- `gen-measured-only` refuses (exit 3) on a board with no measured placement.
- `gen-invalid` refuses (exit 1) when strict validation fails, and writes nothing.

## How to get to it (user POV)

- `python -m traxgen generate --set vertical-starter [--board single-plate|standard-square] [--measured-only] [--out PATH]`
- The installed `traxgen generate ...` script (same entry point, `traxgen.__main__:main`).

## Driving it with verify_chain

Preconditions:

- Doctor exits 0.

- **Single plate.** Run `verify_chain.sh --no-upload`. `summary.txt` shows
  `PASS generate wrote 177 bytes; claim: CONNECTED ...`, `PASS determinism`,
  `PASS pin`.
- **Four plates.** Run `verify_chain.sh --board standard-square --no-upload`.
  `PASS generate wrote 253 bytes; claim: UNMEASURED ...` and `PASS determinism`.
  No `pin` line, because nothing is pinned for this board.
- **Refusal.** Run `verify_chain.sh --board standard-square --measured-only --no-upload`.
  The script exits 3 and `summary.txt` shows `REFUSED generate`. `generate.log`
  names the plate offsets and says to drop `--measured-only`. No
  `course.course` is written.

## Gotchas

- Exit 3 is the generator declining, not a crash. `REFUSED` is the expected
  result for `gen-measured-only` today and would become a FAIL-worthy change
  only if the record gains a measured cross-plate row.
- `--no-validate` exists to probe the validator. A course written with it has
  skipped the first judge. Never verify through it.
- Byte counts (177, 253) are observed as of `bb1ea4f`. The single-plate count
  is pinned by sha256. The four-plate count is not, so a changed 253 is
  information, not failure.
