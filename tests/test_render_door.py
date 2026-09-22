"""Tests for the drop-folder door between a container and the Mac's emulator.

The container is treated as hostile throughout: it can write any bytes, any
filename and any symlink into the shared folder, because that folder is how it
talks. Most of what is below is about what the watcher does with that.

Path: traxgen/tests/test_render_door.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts.render_door import (
    CLAIMED,
    MAX_PENDING_PER_PASS,
    MAX_REQUEST_BYTES,
    REJECTED,
    REQUESTS,
    RESULTS,
    SHARE_CODE,
    DoorError,
    Request,
    Result,
    _default_runner,
    await_result,
    entry,
    prepare,
    render_argv,
    serve_one,
    submit,
    watch,
)

CODE = "KN6F459ZR3"
RID = "0123456789ab"


class FakeRunner:
    """Stands in for the render. Records every call so a test can read the argv."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.calls: list[tuple[list[str], Path]] = []
        self._completed = subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=stdout, stderr=stderr
        )

    def __call__(self, argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(argv), cwd))
        return self._completed


@pytest.fixture
def drop(tmp_path: Path) -> Path:
    return prepare(tmp_path / "door")


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A directory that passes the watcher's "is this traxgen?" check."""
    root = tmp_path / "traxgen-render"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "render_course.py").write_text("", encoding="utf-8")
    return root


def _plant(drop: Path, body: object, request_id: str = RID) -> Path:
    """Write a request straight into the folder, as a hostile container would.

    `body` is whatever bytes-worth of JSON the container chose; `submit` writes
    `{"code", "created"}`, but nothing makes a container do that.
    """
    path = drop / REQUESTS / f"{request_id}.json"
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return path


def _files_under(root: Path) -> set[Path]:
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


# --- the boundary: what the door will and will not carry ---------------------

# The watcher normalises nothing -- it is the boundary, and a boundary that
# rewrites its input has a second parser in it. The client normalises case and
# surrounding whitespace, because a human types the code.
NORMALISED_BY_CLIENT = ["kn6f459zr3", "KN6F459ZR3\n"]

REFUSED = [
    "",
    "SHORT",
    "TOOMANYCHARS11",
    "KN6F459ZR-",
    "KN6F45 9ZR",
    "../../etc/pa",
    "--fresh",
    "; rm -rf /",
    "$(whoami)xx",
    # These two are the point of the strict regex: `str.isalnum()`, which
    # `render_course` uses, returns True for both. Deliberately ambiguous.
    "１２３４５６７８９０",  # noqa: RUF001 - full-width digits
    "١٢٣٤٥٦٧٨٩٠",  # Arabic-Indic digits
]


@pytest.mark.parametrize("code", REFUSED + NORMALISED_BY_CLIENT)
def test_watcher_refuses_anything_that_is_not_a_share_code(
    drop: Path, checkout: Path, code: str
) -> None:
    """The refusal happens before the render, not after it."""
    runner = FakeRunner()
    result = serve_one(
        drop, _plant(drop, {"code": code}), checkout, runner=runner, out=lambda _: None
    )

    assert runner.calls == [], f"a render ran for {code!r}"
    assert (result.status, result.exit_code) == ("rejected", 6)


@pytest.mark.parametrize("code", REFUSED)
def test_client_refuses_the_same_codes_before_writing_a_request(drop: Path, code: str) -> None:
    with pytest.raises(DoorError):
        submit(drop, code)
    assert list((drop / REQUESTS).glob("*.json")) == []


def test_the_pattern_itself_is_anchored() -> None:
    """Two guards hold this boundary: the `\\A`/`\\Z` anchors and the `fullmatch`
    call. Mutating either alone leaves the suite green, because the other still
    holds -- so without this, no test says which is load-bearing, and one edit
    dropping both would let a code through with anything appended to it. There is
    no shell in this path, so what that would buy an attacker is not command
    execution but a path, a flag or a megabyte of text reaching `render_course`.
    """
    assert SHARE_CODE.search(f"; rm -rf / {CODE}") is None
    assert SHARE_CODE.search(f"{CODE} --fresh") is None
    assert SHARE_CODE.search(f"prefix{CODE}") is None
    assert SHARE_CODE.search(CODE) is not None


def test_client_normalises_case_and_whitespace(drop: Path) -> None:
    request = submit(drop, f"  {CODE.lower()}  ")
    assert request.code == CODE
    written = json.loads((drop / REQUESTS / f"{request.id}.json").read_text(encoding="utf-8"))
    assert written["code"] == CODE


# --- no request names a path -------------------------------------------------


@pytest.mark.parametrize(
    "hostile_id",
    ["/etc/passwd", "../../escaped", "esc/settings", "..", "", "ZZZZZZZZZZZZ", "0123456789ab\n"],
)
def test_an_id_in_the_request_body_cannot_steer_where_the_answer_is_written(
    drop: Path, checkout: Path, tmp_path: Path, hostile_id: str
) -> None:
    """The hole an earlier draft had: `id` was read from the body and interpolated
    into the result path, and `Path.__truediv__` discards its left operand when
    the right is absolute. The id now comes from the filename, which `glob` has
    already confined.
    """
    before = _files_under(tmp_path)
    path = _plant(drop, {"id": hostile_id, "code": CODE, "checkout": "/tmp/evil"})

    serve_one(drop, path, checkout, runner=FakeRunner(), out=lambda _: None)

    assert (drop / RESULTS / f"{RID}.json").is_file()
    written = _files_under(tmp_path) - before
    for rel in written:
        assert str(rel).startswith("door/"), f"{rel} was written outside the drop folder"


def test_the_request_body_has_no_id_field_to_read(drop: Path) -> None:
    request = submit(drop, CODE)
    body = json.loads((drop / REQUESTS / f"{request.id}.json").read_text(encoding="utf-8"))
    assert set(body) == {"code", "created"}


@pytest.mark.parametrize("name", ["not-an-id", "../escape", "0123456789AB", "abc"])
def test_a_filename_that_is_not_a_request_id_is_set_aside_not_served(
    drop: Path, checkout: Path, name: str
) -> None:
    """And it leaves `requests/`, so thirty-two of them cannot starve every pass."""
    (drop / REQUESTS / f"{name.replace('/', '_')}.json").write_text(
        json.dumps({"code": CODE}), encoding="utf-8"
    )
    runner = FakeRunner()

    watch(drop, checkout, once=True, runner=runner, out=lambda _: None)

    assert runner.calls == []
    assert list((drop / REQUESTS).glob("*.json")) == []
    assert len(list((drop / REJECTED).glob("*.json"))) == 1


@pytest.mark.parametrize("name", [RESULTS, CLAIMED, REQUESTS])
def test_a_subfolder_replaced_by_a_symlink_is_refused(
    drop: Path, checkout: Path, tmp_path: Path, name: str
) -> None:
    """A container that owns the drop folder can point `results` at the Mac's
    home. Resolving a path *under* that symlink lands outside and still looks
    contained, so the check has to be on the directory itself.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = drop / name
    for stale in target.glob("*"):
        stale.unlink()
    target.rmdir()
    target.symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(DoorError, match="not a real directory"):
        entry(drop, name, RID)
    assert watch(drop, checkout, once=True, runner=FakeRunner(), out=lambda _: None) == 1


# --- the watcher outlives bad input ------------------------------------------


@pytest.mark.parametrize(
    "body", ["not json at all", "", "[1, 2, 3]", '{"code":', "null", '"just a string"']
)
def test_a_malformed_request_is_refused_and_the_watcher_keeps_going(
    drop: Path, checkout: Path, body: str
) -> None:
    """`json.JSONDecodeError` subclasses `ValueError`, not `OSError`: an earlier
    draft caught only `OSError` and the watcher died on a 15-byte file.
    """
    _plant(drop, body)
    _plant(drop, {"code": CODE}, request_id="ffffffffffff")
    runner = FakeRunner()

    assert watch(drop, checkout, once=True, runner=runner, out=lambda _: None) == 0
    assert len(runner.calls) == 1, "the good request must still be served"
    statuses = {
        json.loads(p.read_text(encoding="utf-8"))["status"]
        for p in (drop / RESULTS).glob("*.json")
    }
    assert statuses == {"rejected", "rendered"}


def test_an_oversized_request_is_refused_without_being_read_whole(
    drop: Path, checkout: Path
) -> None:
    _plant(drop, json.dumps({"code": CODE, "pad": "x" * (MAX_REQUEST_BYTES * 4)}))
    runner = FakeRunner()

    result = serve_one(
        drop, drop / REQUESTS / f"{RID}.json", checkout, runner=runner, out=lambda _: None
    )

    assert runner.calls == []
    assert result.status == "rejected"
    assert result.reason is not None and "limit" in result.reason


def test_one_pass_serves_a_bounded_number_of_requests(drop: Path, checkout: Path) -> None:
    for n in range(MAX_PENDING_PER_PASS + 10):
        _plant(drop, {"code": CODE}, request_id=f"{n:012x}")
    runner = FakeRunner()

    watch(drop, checkout, once=True, runner=runner, out=lambda _: None)

    assert len(runner.calls) == MAX_PENDING_PER_PASS


def test_what_the_watcher_prints_cannot_be_forged_by_the_container(
    drop: Path, checkout: Path
) -> None:
    """The watcher's terminal is the human's only view of this boundary, and the
    project's standing note is to trust only harness-verified results. Raw escape
    codes reaching it would let the container erase a line and redraw a success.
    """
    forged = "\x1b[2K\x1b[1Arendered KN6F459ZR3 (exit 0)"
    (drop / REQUESTS / f"{forged}.json".replace("/", "_")).write_text(
        json.dumps({"code": "\x1b[2Kx"}), encoding="utf-8"
    )
    _plant(drop, {"code": "\x1b[2K\x1b[1A"})
    lines: list[str] = []

    watch(drop, checkout, once=True, runner=FakeRunner(), out=lines.append)

    assert lines, "the watcher said nothing"
    assert not any("\x1b" in line for line in lines), lines


# --- the command the watcher actually builds ---------------------------------


def test_the_render_command_is_render_course_fresh_in_the_watchers_checkout(
    drop: Path, checkout: Path
) -> None:
    """A stubbed result would pass a status check; this reads the argv itself."""
    runner = FakeRunner(stdout="/tmp/shot.png\n")
    serve_one(drop, _plant(drop, {"code": CODE}), checkout, runner=runner, out=lambda _: None)

    (argv, cwd) = runner.calls[0]
    assert argv == render_argv(CODE)
    assert argv[:5] == ["uv", "run", "python", "-m", "scripts.render_course"]
    assert "--fresh" in argv
    assert CODE in argv, "the code must be one whole argument, never spliced into a string"
    assert cwd == checkout


def test_the_checkout_comes_from_the_watcher_not_from_the_request(
    drop: Path, checkout: Path, tmp_path: Path
) -> None:
    attacker = tmp_path / "container-copy"
    attacker.mkdir()
    path = _plant(drop, {"code": CODE, "checkout": str(attacker), "argv": ["rm", "-rf"]})

    runner = FakeRunner()
    serve_one(drop, path, checkout, runner=runner, out=lambda _: None)

    (argv, cwd) = runner.calls[0]
    assert cwd == checkout
    assert str(attacker) not in argv


def test_the_real_runner_spawns_without_a_shell(tmp_path: Path) -> None:
    """Every other test injects a fake, so this is the only one that grades the
    code that actually starts a process. `shell=True` would make the argv a
    single string and this would not survive it.
    """
    marker = "; echo INJECTED"
    completed = _default_runner(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", marker], tmp_path
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == marker, "the shell would have eaten this"


def test_watch_refuses_a_checkout_that_is_not_traxgen(drop: Path, tmp_path: Path) -> None:
    runner = FakeRunner()
    assert watch(drop, tmp_path / "nope", once=True, runner=runner, out=lambda _: None) == 1
    assert runner.calls == []


# --- what comes back ---------------------------------------------------------


def test_a_successful_render_reports_its_screenshot_and_validity(
    drop: Path, checkout: Path
) -> None:
    runner = FakeRunner(
        stdout="/tmp/shot.png\n",
        stderr="rendering...\nplay button: active\nscreenshot saved: /tmp/shot.png\n",
    )
    result = serve_one(
        drop, _plant(drop, {"code": CODE}), checkout, runner=runner, out=lambda _: None
    )

    assert (result.status, result.exit_code) == ("rendered", 0)
    assert (result.screenshot, result.validity) == ("/tmp/shot.png", "active")
    assert json.loads((drop / RESULTS / f"{RID}.json").read_text(encoding="utf-8"))["status"] == (
        "rendered"
    )


def test_a_failed_render_carries_the_device_evidence_path_back(drop: Path, checkout: Path) -> None:
    """#20's whole point: the container must learn where the phone's account went."""
    runner = FakeRunner(
        returncode=3,
        stderr=(
            "rendering...\n"
            "device evidence saved: screenshots/device_evidence/20260922-101500.txt\n"
            "render failed: boom\n"
        ),
    )
    result = serve_one(
        drop, _plant(drop, {"code": CODE}), checkout, runner=runner, out=lambda _: None
    )

    assert (result.status, result.exit_code) == ("failed", 3)
    assert result.evidence == "screenshots/device_evidence/20260922-101500.txt"
    assert "render failed: boom" in result.stderr_tail[-1]


def test_stderr_tail_survives_the_json_round_trip_as_a_tuple(drop: Path, checkout: Path) -> None:
    """JSON has no tuples, so a plain `Result(**json.loads(...))` hands the
    container a list while the dataclass says tuple.
    """
    request = submit(drop, CODE)
    serve_one(
        drop,
        drop / REQUESTS / f"{request.id}.json",
        checkout,
        runner=FakeRunner(stderr="one\ntwo\n"),
        out=lambda _: None,
    )
    result = await_result(drop, request, sleep=lambda _: None, clock=lambda: 0.0)

    assert isinstance(result.stderr_tail, tuple)
    assert result.stderr_tail == ("one", "two")


def test_a_result_file_with_unknown_fields_is_still_readable(drop: Path) -> None:
    """A watcher one version ahead must not make the client throw a TypeError."""
    request = Request(id=RID, code=CODE, created="")
    (drop / RESULTS / f"{RID}.json").write_text(
        json.dumps(
            {"id": RID, "code": CODE, "status": "rendered", "exit_code": 0, "from_the_future": 1}
        ),
        encoding="utf-8",
    )
    assert await_result(drop, request, sleep=lambda _: None, clock=lambda: 0.0).status == "rendered"


def test_a_served_request_leaves_requests_empty_and_is_claimed_once(
    drop: Path, checkout: Path
) -> None:
    serve_one(drop, _plant(drop, {"code": CODE}), checkout, runner=FakeRunner(), out=lambda _: None)
    assert list((drop / REQUESTS).glob("*.json")) == []
    assert [p.name for p in (drop / CLAIMED).glob("*.json")] == [f"{RID}.json"]


# --- the three silences ------------------------------------------------------


class FakeClock:
    """Time that only moves when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def test_an_unclaimed_request_is_reported_as_no_watcher(drop: Path) -> None:
    clock = FakeClock()
    request = submit(drop, CODE)

    with pytest.raises(DoorError, match="no watcher"):
        await_result(drop, request, claim_timeout=30, sleep=clock.sleep, clock=clock)
    assert clock.now < 60, "it must give up, not block"


def test_a_claimed_request_that_is_never_answered_is_reported_as_the_door_being_down(
    drop: Path,
) -> None:
    clock = FakeClock()
    request = Request(id=RID, code=CODE, created="")
    (drop / CLAIMED / f"{RID}.json").write_text("{}", encoding="utf-8")

    with pytest.raises(DoorError, match="never answered"):
        await_result(
            drop, request, claim_timeout=30, result_timeout=120, sleep=clock.sleep, clock=clock
        )
    assert clock.now < 200


def test_a_request_that_vanished_from_every_folder_is_reported_rather_than_waited_on(
    drop: Path,
) -> None:
    """The state an earlier draft spun on forever: the claim timeout was armed
    only while the request file existed, so removing it disarmed the guard.
    """
    clock = FakeClock()
    request = submit(drop, CODE)
    (drop / REQUESTS / f"{request.id}.json").unlink()

    with pytest.raises(DoorError, match="none of the three folders"):
        await_result(drop, request, sleep=clock.sleep, clock=clock)
    assert clock.now == 0.0, "nothing can arrive; it must not wait at all"


def test_a_slow_claim_is_not_mistaken_for_a_dead_watcher(drop: Path, checkout: Path) -> None:
    """Once a watcher has the request, the claim timeout must stop applying --
    and the wait must actually pass *through* the claimed state to show it, which
    an earlier version of this test did not do.
    """
    clock = FakeClock()
    request = submit(drop, CODE)
    pending = drop / REQUESTS / f"{request.id}.json"
    claimed = drop / CLAIMED / f"{request.id}.json"
    seen_claimed = 0

    def sleep(seconds: float) -> None:
        nonlocal seen_claimed
        clock.sleep(seconds)
        if clock.now == 5.0:  # a watcher takes it, well inside the claim timeout
            pending.replace(claimed)
        if claimed.exists() and not (drop / RESULTS / f"{request.id}.json").exists():
            seen_claimed += 1
        if clock.now == 60.0:  # ... and answers long after the claim timeout passed
            serve_one(drop, claimed, checkout, runner=FakeRunner(), out=lambda _: None)

    result = await_result(drop, request, claim_timeout=10, sleep=sleep, clock=clock)

    assert seen_claimed > 40, "the wait must sit in the claimed state, not skip it"
    assert clock.now == 60.0
    assert result.status == "rendered"


def test_a_result_already_waiting_is_returned_without_sleeping(
    drop: Path, checkout: Path
) -> None:
    clock = FakeClock()
    request = submit(drop, CODE)
    serve_one(
        drop,
        drop / REQUESTS / f"{request.id}.json",
        checkout,
        runner=FakeRunner(),
        out=lambda _: None,
    )

    result = await_result(drop, request, sleep=clock.sleep, clock=clock)
    assert result.id == request.id
    assert clock.now == 0.0


def test_watch_drains_every_pending_request_in_one_pass(drop: Path, checkout: Path) -> None:
    for n in range(3):
        _plant(drop, {"code": CODE}, request_id=f"{n:012x}")
    runner = FakeRunner()

    assert watch(drop, checkout, once=True, runner=runner, out=lambda _: None) == 0
    assert len(runner.calls) == 3
    assert len(list((drop / RESULTS).glob("*.json"))) == 3


# --- the CLI's own defaults --------------------------------------------------


def test_drop_is_required_when_the_environment_does_not_supply_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Path("")` is `PosixPath(".")`, which is truthy, so an `or None` default
    silently made the current directory the drop folder -- and a stray `request`
    from the repo root created `requests/` inside the checkout.
    """
    monkeypatch.delenv("TRAXGEN_DOOR_DROP", raising=False)
    from scripts.render_door import _parse_args

    with pytest.raises(SystemExit) as exit_info:
        _parse_args(["request", CODE])
    assert exit_info.value.code == 2


def test_the_environment_can_supply_the_drop_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAXGEN_DOOR_DROP", "/traxgen-door")
    from scripts.render_door import _parse_args

    assert _parse_args(["request", CODE]).drop == Path("/traxgen-door")


def test_result_from_json_refuses_something_that_is_not_an_object() -> None:
    with pytest.raises(DoorError):
        Result.from_json([1, 2, 3])
