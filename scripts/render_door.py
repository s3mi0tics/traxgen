"""CLI: carry a render request from a container to the Mac, and the result back.

The Android emulator cannot run inside Docker on an M1 (s38-t5), so work that
lives in a container has to ask the Mac to render. This is that door, and it is
deliberately the narrowest one available: a shared folder, with data crossing it
and never a command.

    container                     shared folder                  Mac
    render_door request  ---->  requests/<id>.json  ---->  render_door watch
                                claimed/<id>.json   (the watcher took it)
    render_door request  <----  results/<id>.json   <----  render_course --fresh
                                rejected/<id>.json  (a filename that is not an id)

The watcher is the security boundary. Assume the container is hostile: it can
write any bytes, any filename and any symlink into the shared folder, because
that folder is how it talks. Three things hold the boundary, and each is checked
rather than trusted:

1.  **One field crosses into a command.** A request body carries a share code and
    nothing else that is read. The code is matched against `[A-Z0-9]{10}` before
    anything runs. There is no shell anywhere -- the command is an argument list
    passed to `subprocess.run` -- so what the check buys is not protection from
    shell metacharacters but the guarantee that a path, a flag, or a megabyte of
    text never reaches `render_course` or the Mac at all.
2.  **No request names a path.** The request's identity is its *filename*, found
    by `glob`, which cannot cross a directory separator; the body has no `id`.
    Every path this module builds is checked to land inside the drop folder, and
    the three subfolders are checked not to be symlinks, so a planted
    `results -> ~/.claude` cannot redirect a write. An earlier draft of this file
    took the id from the body and interpolated it into the result path, which
    gave the container an arbitrary-path write on the Mac -- found by review
    before it ran anywhere (s39-t1).
3.  **The watcher outlives bad input.** Malformed JSON, an oversized file, a
    vanished request: each fails one request and none stops the watcher. A
    boundary process that dies on hostile input is a boundary the container can
    take down at will.

`--checkout` says which copy of traxgen renders, and it is required, so no
request can name it. Point it at a copy that only a human updates. That is what
keeps a harness change the container just wrote from running on the Mac before
anyone has looked at it, and it is the gate, not an oversight: when the work
*is* the harness, updating that copy is the approval.

Usage:

    # on the Mac, in its own terminal, left running
    uv run python -m scripts.render_door watch --drop ~/traxgen-door \\
        --checkout ~/Claude/Projects/traxgen-render

    # in the container
    uv run python -m scripts.render_door request KN6F459ZR3 --drop /traxgen-door

Exit codes (request):
    0  the render ran and reported success
    1  bad share code, or an unusable drop folder
    2  bad arguments (argparse)
    3  the render did not succeed -- it failed, or never started
    4  no watcher ever claimed the request
    5  a watcher claimed the request and never answered, or it vanished
    6  the watcher refused the request

Path: traxgen/scripts/render_door.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

SHARE_CODE = re.compile(r"\A[A-Z0-9]{10}\Z")
"""The one field a request carries into a command. ASCII only -- `str.isalnum()`,
which `render_course` uses, also returns True for full-width and Arabic-Indic
digits."""

REQUEST_ID = re.compile(r"\A[0-9a-f]{12}\Z")
"""A request's identity is its filename. Matching this is what makes every path
built from it stay where it belongs."""

REQUESTS, CLAIMED, RESULTS, REJECTED = "requests", "claimed", "results", "rejected"
SUBDIRS = (REQUESTS, CLAIMED, RESULTS, REJECTED)

POLL_SECONDS = 1.0
CLAIM_TIMEOUT = 90.0
RESULT_TIMEOUT = 600.0
STDERR_TAIL_LINES = 40
MAX_REQUEST_BYTES = 4096
"""A request is a share code and a timestamp. Anything larger is not one, and
reading it whole is how a hostile container would spend the Mac's memory."""
MAX_PENDING_PER_PASS = 32
"""One pass serves at most this many, so a flood is slowed rather than obeyed."""
CODE_ECHO_CHARS = 32


class DoorError(Exception):
    """A request that cannot be made, or a drop folder that is not usable."""


@dataclass(frozen=True)
class Request:
    """What the container writes. The id is the filename, deliberately not a field."""

    id: str
    code: str
    created: str

    def body(self) -> dict[str, str]:
        """The bytes that cross. The id stays out: nothing may name its own path."""
        return {"code": self.code, "created": self.created}


@dataclass(frozen=True)
class Result:
    """What the watcher writes back."""

    id: str
    code: str
    status: str  # rendered | failed | rejected
    exit_code: int
    screenshot: str | None = None
    validity: str | None = None
    evidence: str | None = None
    reason: str | None = None
    stderr_tail: tuple[str, ...] = ()
    started: str = ""
    finished: str = ""

    @classmethod
    def from_json(cls, raw: object) -> Result:
        """Rebuild from a parsed result file, tolerating a file this version did
        not write: JSON has no tuples, and an older or newer watcher may carry
        fields this one does not know."""
        if not isinstance(raw, dict):
            raise DoorError("the result file is not an object")
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, object] = {k: v for k, v in raw.items() if k in known}
        kwargs["stderr_tail"] = tuple(str(line) for line in kwargs.get("stderr_tail") or ())
        try:
            return cls(**kwargs)  # type: ignore[arg-type]
        except TypeError as exc:
            raise DoorError(f"the result file is missing a field: {exc}") from exc


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def subdir(drop: Path, name: str) -> Path:
    """One of the three subfolders, checked to be a real directory.

    The container can write into the drop folder, so it can replace `results`
    with a symlink to somewhere on the Mac. Resolving a path under that symlink
    would land outside and still look contained, so the check is on the
    directory itself, and it runs on every use rather than once at startup.
    """
    path = drop / name
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise DoorError(f"{path} is not a real directory -- refusing to use this drop folder")
    return path


def entry(drop: Path, name: str, request_id: str) -> Path:
    """The path for one request in one subfolder, proven to land inside it."""
    if not REQUEST_ID.fullmatch(request_id):
        raise DoorError(f"not a request id: {request_id[:CODE_ECHO_CHARS]!r}")
    parent = subdir(drop, name)
    path = parent / f"{request_id}.json"
    if path.parent != parent:
        raise DoorError(f"{path} would escape {parent}")
    return path


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    """Write JSON so a reader never sees a half-written file."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_bounded(path: Path) -> object:
    """Parse one request file, refusing anything too big to be one."""
    size = path.stat().st_size
    if size > MAX_REQUEST_BYTES:
        raise DoorError(f"request is {size} bytes, over the {MAX_REQUEST_BYTES}-byte limit")
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise DoorError(f"request is not JSON: {exc}") from exc


def prepare(drop: Path) -> Path:
    """Create the three subfolders. Idempotent, and refuses a tampered folder."""
    for name in SUBDIRS:
        subdir(drop, name).mkdir(parents=True, exist_ok=True)
    return drop


# --- container side ----------------------------------------------------------


def submit(drop: Path, code: str) -> Request:
    """Write one request. Raises `DoorError` on a code this door will not carry."""
    normalised = code.strip().upper()
    if not SHARE_CODE.fullmatch(normalised):
        raise DoorError(f"expected a 10-character share code, got {code[:CODE_ECHO_CHARS]!r}")
    prepare(drop)
    request = Request(id=uuid.uuid4().hex[:12], code=normalised, created=_now())
    _write_atomic(entry(drop, REQUESTS, request.id), request.body())
    return request


def await_result(
    drop: Path,
    request: Request,
    *,
    claim_timeout: float = CLAIM_TIMEOUT,
    result_timeout: float = RESULT_TIMEOUT,
    poll: float = POLL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Result:
    """Wait for the watcher's answer. Every silence is bounded and named.

    Three of them, and they mean different things: still in `requests/` means no
    watcher is running; sitting in `claimed/` means a watcher took it and died;
    in none of the three means something removed it underneath us.
    """
    result_path = entry(drop, RESULTS, request.id)
    claimed_path = entry(drop, CLAIMED, request.id)
    pending_path = entry(drop, REQUESTS, request.id)
    started = clock()
    claimed_at: float | None = None

    while True:
        if result_path.exists():
            return Result.from_json(_read_bounded(result_path))
        if claimed_at is None and claimed_path.exists():
            claimed_at = clock()
        now = clock()

        if claimed_at is not None:
            if now - claimed_at >= result_timeout:
                raise DoorError(
                    f"a watcher claimed {request.id} {now - claimed_at:.0f}s ago and never "
                    f"answered -- the door is down, check the Mac's terminal"
                )
        elif not pending_path.exists():
            raise DoorError(
                f"request {request.id} is in none of the three folders -- something removed "
                f"it; nothing will answer"
            )
        elif now - started >= claim_timeout:
            raise DoorError(
                f"no watcher claimed {request.id} in {claim_timeout:.0f}s -- "
                f"is `render_door watch` running on the Mac?"
            )
        sleep(poll)


# --- Mac side ----------------------------------------------------------------


def _default_runner(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the render. No shell: the code is one element of an argument list."""
    return subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True, check=False)


Runner = Callable[[Sequence[str], Path], "subprocess.CompletedProcess[str]"]


def render_argv(code: str) -> list[str]:
    """The command the watcher runs. An argument list, never a shell string."""
    return [
        "uv", "run", "python", "-m", "scripts.render_course",
        code, "--fresh", "--detect-validity",
    ]  # fmt: skip


def _scrape(stderr: str, prefix: str) -> str | None:
    for line in reversed(stderr.splitlines()):
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _rejected(request_id: str, code: str, reason: str, started: str) -> Result:
    return Result(
        id=request_id,
        code=code[:CODE_ECHO_CHARS],
        status="rejected",
        exit_code=6,
        reason=reason,
        started=started,
        finished=_now(),
    )


def serve_one(
    drop: Path,
    request_path: Path,
    checkout: Path,
    *,
    runner: Runner = _default_runner,
    out: Callable[[str], None] = lambda line: print(line, file=sys.stderr),
) -> Result:
    """Claim one request, render it if the code is one this door carries, answer.

    The id comes from the filename and never from the body, so nothing the
    container writes inside the file can steer where the answer is written.
    """
    request_id = request_path.stem
    claimed_path = entry(drop, CLAIMED, request_id)
    result_path = entry(drop, RESULTS, request_id)
    os.replace(request_path, claimed_path)
    started = _now()

    try:
        raw = _read_bounded(claimed_path)
        code = str(raw.get("code", "")) if isinstance(raw, dict) else ""
    except DoorError as exc:
        # `!r` on every echo: the watcher's terminal is the human's only view of
        # this boundary, and raw bytes from the container could redraw it.
        out(f"refused {request_id!r}: {exc}")
        result = _rejected(request_id, "", f"unreadable request: {exc}", started)
    else:
        if not SHARE_CODE.fullmatch(code):
            out(f"refused {request_id!r}: {code[:CODE_ECHO_CHARS]!r} is not a share code")
            result = _rejected(
                request_id, code, "not a 10-character share code; nothing was run", started
            )
        else:
            out(f"rendering {code} for {request_id!r}")
            completed = runner(render_argv(code), checkout)
            stderr = completed.stderr or ""
            result = Result(
                id=request_id,
                code=code,
                status="rendered" if completed.returncode == 0 else "failed",
                exit_code=completed.returncode,
                screenshot=(completed.stdout or "").strip() or None,
                validity=_scrape(stderr, "play button:"),
                evidence=_scrape(stderr, "device evidence saved:"),
                stderr_tail=tuple(stderr.splitlines()[-STDERR_TAIL_LINES:]),
                started=started,
                finished=_now(),
            )
            out(f"{result.status} {code} (exit {result.exit_code})")

    _write_atomic(result_path, asdict(result))
    return result


def _set_aside(drop: Path, request_path: Path, out: Callable[[str], None]) -> None:
    """Move a request the watcher cannot serve out of `requests/`, under a name
    this module chose. Without this, a filename that is not an id is re-globbed
    on every pass: thirty-two of them would fill each pass and starve the real
    requests. Nothing is deleted -- the file stays for a human to look at."""
    try:
        os.replace(request_path, entry(drop, REJECTED, uuid.uuid4().hex[:12]))
    except (DoorError, OSError) as exc:  # pragma: no cover - only if the folder is gone
        out(f"could not set aside {request_path.name!r}: {exc}")


def watch(
    drop: Path,
    checkout: Path,
    *,
    once: bool = False,
    poll: float = POLL_SECONDS,
    runner: Runner = _default_runner,
    sleep: Callable[[float], None] = time.sleep,
    out: Callable[[str], None] = lambda line: print(line, file=sys.stderr),
) -> int:
    """Serve requests until interrupted. Returns a process exit code."""
    if not (checkout / "scripts" / "render_course.py").is_file():
        out(f"error: {checkout} does not look like a traxgen checkout")
        return 1
    try:
        prepare(drop)
    except (DoorError, OSError) as exc:
        out(f"error: {exc}")
        return 1
    out(f"watching {drop / REQUESTS}, rendering from {checkout}")

    while True:
        try:
            pending = sorted(subdir(drop, REQUESTS).glob("*.json"))[:MAX_PENDING_PER_PASS]
        except DoorError as exc:
            out(f"error: {exc}")
            return 1
        for request_path in pending:
            try:
                serve_one(drop, request_path, checkout, runner=runner, out=out)
            except Exception as exc:  # one bad request must not end the watch
                out(f"skipped {request_path.name!r}: {type(exc).__name__}: {exc}")
                _set_aside(drop, request_path, out)
        if once:
            return 0
        sleep(poll)


# --- CLI ---------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    request_parser = sub.add_parser("request", help="ask the Mac to render a share code")
    request_parser.add_argument("code", help="10-character GraviTrax share code")
    request_parser.add_argument("--claim-timeout", type=float, default=CLAIM_TIMEOUT)
    request_parser.add_argument("--result-timeout", type=float, default=RESULT_TIMEOUT)

    watch_parser = sub.add_parser("watch", help="serve requests on the Mac")
    watch_parser.add_argument(
        "--checkout",
        type=Path,
        required=True,
        help="the traxgen copy to render from; required, so no request can name it",
    )
    watch_parser.add_argument("--once", action="store_true", help="drain once and exit")

    env_drop = os.environ.get("TRAXGEN_DOOR_DROP", "").strip()
    for subparser in (request_parser, watch_parser):
        subparser.add_argument(
            "--drop",
            type=Path,
            default=Path(env_drop) if env_drop else None,
            required=not env_drop,
            help="the shared folder (or set TRAXGEN_DOOR_DROP)",
        )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand. Returns a process exit code."""
    args = _parse_args(argv)

    if args.command == "watch":
        try:
            return watch(args.drop, args.checkout, once=args.once)
        except KeyboardInterrupt:
            print("\nwatcher stopped", file=sys.stderr)
            return 0

    try:
        request = submit(args.drop, args.code)
    except (DoorError, OSError) as exc:
        print(f"door: {exc}", file=sys.stderr)
        return 1

    print(f"requested {request.code} as {request.id}", file=sys.stderr)
    try:
        result = await_result(
            args.drop,
            request,
            claim_timeout=args.claim_timeout,
            result_timeout=args.result_timeout,
        )
    except DoorError as exc:
        print(f"door: {exc}", file=sys.stderr)
        return 4 if "no watcher" in str(exc) else 5

    print(json.dumps(asdict(result), indent=2))
    return {"rendered": 0, "failed": 3, "rejected": 6}.get(result.status, 3)


if __name__ == "__main__":
    sys.exit(main())
