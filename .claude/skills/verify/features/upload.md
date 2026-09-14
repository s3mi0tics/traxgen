# Get a share code

A builder uploads a `.course` file to Ravensburger's share-code endpoint and
gets a 10-character code to type into the GraviTrax app.

## Sub-features

- `upload-code` a valid upload returns a 10-character alphanumeric code.
- `upload-dedup` identical bytes return the identical code.
- `upload-pin` the single-plate course returns `KN6F459ZR3`, the code the app
  rendered `active` at Phase 1 close.

## How to get to it (user POV)

- `uv run python -m scripts.upload_course FILE` (stdout: code only; stderr: context; exit 3 on upload failure).
- As the `upload` stage of `verify_chain.sh`, which is on by default.

## Driving it with verify_chain

Preconditions:

- Doctor shows `PASS network`.
- The user has agreed to publish. Every new byte sequence becomes a public course.

- **Pinned path.** Run `verify_chain.sh`. `summary.txt` shows
  `PASS upload KN6F459ZR3` and `PASS code_pin matches the app-certified code`.
  `share_code.txt` holds the code.
- **Dedup.** Run the same chain twice. Both runs' `share_code.txt` hold the same
  code.

## Gotchas

- The endpoint accepting bytes is not the app accepting the course. Do not
  report a share code as proof of validity; see `render.md`.
- The upload URL, headers and user agent live in `traxgen/uploader.py`. The
  offline tests mock them. Only `uv run pytest -m network` and this chain touch
  the real endpoint.
- Transient 520s and TLS timeouts happen under load. One retry, then report.
