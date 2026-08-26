# tests/test_mutation_battery.py
"""Offline tests for `scripts/mutation_battery.py`.

None of these spawn pytest. The battery takes its suite runner as a seam, and
every test here hands it a *fake* -- a callable the test controls, which
returns canned pytest output and records what the file on disk looked like at
the moment it was called. That last part is what makes "the mutation was on
disk during the run and gone afterwards" an assertion rather than a belief.

The point of the fake is the same as a Playwright `page.route()` handler: the
thing under test talks to something slow and external (here, a pytest
subprocess; there, a server), and the test replaces that thing with one whose
answers it chose. What is proven is how the battery *behaves given* those
answers -- rule (a) aborts, rule (b) halts, restoration happens -- which is
exactly the class of property a real pytest run would make slow and flaky to
check. What is not proven is that real pytest prints what the fake prints; the
`parse_summary` cases below pin the two real formats seen in s25 and s27.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.mutation_battery import (
    Battery,
    BatteryError,
    Mutation,
    Summary,
    parse_summary,
)

GREEN = "........\n732 passed, 1 deselected in 9.85s\n"
RED = "F.......\n=========== 1 failed, 731 passed in 9.90s ===========\n"
USAGE_ERROR = (
    "ERROR: usage: pytest [options] [file_or_dir] [...]\n"
    "pytest: error: unrecognized arguments: -p no:randomly\n"
)
# What pytest prints when an import-time exception stops collection: red, and
# zero tests ran. Seen in s28 when a lookup-key mutation broke a module-level
# `derive_geometry()` call.
COLLAPSED = (
    "!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!\n"
    "1 deselected, 1 error in 0.52s\n"
)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("732 passed, 1 deselected in 9.85s", Summary(732, 0, 0)),
        ("==== 3 failed, 700 passed in 1.20s ====", Summary(700, 3, 0)),
        ("=== 2 errors in 0.50s ===", Summary(0, 0, 2)),
        ("1 failed, 2 passed, 3 errors in 1.00s", Summary(2, 1, 3)),
        ("F..\n" + "x" * 40 + "\n5 passed, 1 failed in 0.3s", Summary(5, 1, 0)),
    ],
)
def test_parse_summary_reads_quiet_and_bannered_lines(line: str, expected: Summary) -> None:
    """Both formats seen for real: `-q`'s bare line (s27) and the `====` banner."""
    assert parse_summary(line) == expected


@pytest.mark.parametrize(
    "output",
    [
        USAGE_ERROR,
        "",
        # The s25 failure shape: a run that collected nothing prints no summary,
        # and a `FAILED` word in a traceback must not be read as one.
        "FAILED tests/test_x.py::test_y - AssertionError\nsome traceback text\n",
        # A summary-shaped fragment with no elapsed time is not pytest's line.
        "3 failed, 2 passed\n",
    ],
)
def test_parse_summary_refuses_a_run_with_no_summary_line(output: str) -> None:
    """Rule (a): a run that cannot be read is not scored."""
    with pytest.raises(BatteryError, match="no pytest summary line"):
        parse_summary(output)


# -- a tiny repo and a recording fake runner ----------------------------------

ORIGINAL = "def live(d):\n    return d in {0, 4}\n\nTHRESHOLD = 10.0\n"


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text(ORIGINAL, encoding="utf-8")
    return tmp_path


def control() -> Mutation:
    return Mutation("control: drop SW", "mod.py", "{0, 4}", "{0}")


def mutation(label: str = "threshold up", expect: str = "caught") -> Mutation:
    return Mutation(label, "mod.py", "THRESHOLD = 10.0", "THRESHOLD = 99.0", expect)


class FakeRunner:
    """Returns scripted outputs in order and records the file at each call."""

    def __init__(self, root: Path, outputs: list[str]) -> None:
        self.root = root
        self.outputs = list(outputs)
        self.seen: list[str] = []

    def __call__(self) -> str:
        self.seen.append((self.root / "mod.py").read_text(encoding="utf-8"))
        if not self.outputs:
            raise AssertionError("the battery ran the suite more times than scripted")
        return self.outputs.pop(0)


def battery(
    root: Path, runner: Callable[[], str], *mutations: Mutation, ctrl: Mutation | None = None
) -> tuple[Battery, list[str]]:
    lines: list[str] = []
    return (
        Battery(
            root=root,
            control=ctrl or control(),
            mutations=tuple(mutations),
            runner=runner,
            report=lines.append,
            install_signal_handlers=False,
        ),
        lines,
    )


# -- preflight (rule c) --------------------------------------------------------


def test_a_red_baseline_aborts_before_any_mutation_is_applied(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    runner = FakeRunner(root, [RED])
    bat, _ = battery(root, runner, mutation())
    with pytest.raises(BatteryError, match="baseline is red"):
        bat.run()
    assert runner.seen == [ORIGINAL], "only the baseline ran, on the untouched tree"
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL


def test_a_stranded_mutation_fails_preflight_by_name(tmp_path: Path) -> None:
    """The s27 hole: an interrupted run left a mutation on disk, and a grep over
    five of eighteen strings called the tree clean. Here every `old` is checked."""
    root = make_repo(tmp_path)
    stranded = mutation("greyscale")
    (root / "mod.py").write_text(
        ORIGINAL.replace(stranded.old, stranded.new), encoding="utf-8"
    )
    runner = FakeRunner(root, [GREEN])
    bat, _ = battery(root, runner, stranded)
    with pytest.raises(BatteryError, match=r"'greyscale'.*matches 0 times"):
        bat.run()
    assert runner.seen == [], "preflight refused before spending a suite run"


def test_an_old_string_that_matches_twice_is_refused(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    ambiguous = Mutation("ambiguous", "mod.py", "d", "e")  # "def", "(d)", "d in"
    bat, _ = battery(root, FakeRunner(root, [GREEN]), ambiguous)
    with pytest.raises(BatteryError, match=r"matches 3 times"):
        bat.run()


# -- the control (rule b) -----------------------------------------------------


def test_control_survival_halts_before_any_row_prints(tmp_path: Path) -> None:
    """A broken battery reports reassurance; this one reports nothing."""
    root = make_repo(tmp_path)
    runner = FakeRunner(root, [GREEN, GREEN])  # baseline green, control *survives*
    bat, lines = battery(root, runner, mutation())
    with pytest.raises(BatteryError, match="CONTROL SURVIVED"):
        bat.run()
    assert lines == [], "no row was printed"
    assert runner.seen[1] == ORIGINAL.replace("{0, 4}", "{0}"), "the control was on disk"
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL, "and restored"


def test_a_control_that_collapses_collection_is_refused(tmp_path: Path) -> None:
    """Red on screen is not a catch when no test ran; the control must be caught
    *by a test*, or the battery has calibrated itself against an import error."""
    root = make_repo(tmp_path)
    runner = FakeRunner(root, [GREEN, COLLAPSED])
    bat, lines = battery(root, runner, mutation())
    with pytest.raises(BatteryError, match="CONTROL COLLAPSED THE SUITE"):
        bat.run()
    assert lines == []
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL


# -- scoring -------------------------------------------------------------------


def test_each_mutation_is_applied_then_restored(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    runner = FakeRunner(root, [GREEN, RED, RED, GREEN])
    bat, lines = battery(root, runner, mutation("caught one"), mutation("survivor"))
    results = bat.run()

    assert [r.outcome for r in results] == ["caught", "survived"]
    assert runner.seen == [
        ORIGINAL,
        ORIGINAL.replace("{0, 4}", "{0}"),
        ORIGINAL.replace("THRESHOLD = 10.0", "THRESHOLD = 99.0"),
        ORIGINAL.replace("THRESHOLD = 10.0", "THRESHOLD = 99.0"),
    ], "each run saw exactly its own mutation on disk, and nothing else's"
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL
    assert lines[-1] == "1 of 2 caught; unexpected: ['survivor']"


def test_a_mutation_that_collapses_collection_is_named_not_counted(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    runner = FakeRunner(root, [GREEN, RED, COLLAPSED, RED])
    bat, lines = battery(root, runner, mutation("breaks import"), mutation("real catch"))
    results = bat.run()
    assert [r.outcome for r in results] == ["collapsed", "caught"]
    assert [r.as_expected for r in results] == [False, True]
    assert lines[-1] == "1 of 2 caught, 1 collapsed the suite; unexpected: ['breaks import']"
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL


def test_expect_survive_is_scored_against_the_claim(tmp_path: Path) -> None:
    """A dead-clause claim is a mutation whose *survival* is the expected result."""
    root = make_repo(tmp_path)
    runner = FakeRunner(root, [GREEN, RED, GREEN, RED])
    bat, lines = battery(
        root,
        runner,
        mutation("dead clause", expect="survive"),
        mutation("live after all", "survive"),
    )
    results = bat.run()
    assert [r.as_expected for r in results] == [True, False]
    assert lines[-1] == "1 of 2 caught; unexpected: ['live after all']"


def test_a_missing_summary_mid_run_aborts_and_restores(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    runner = FakeRunner(root, [GREEN, RED, USAGE_ERROR])
    bat, _ = battery(root, runner, mutation())
    with pytest.raises(BatteryError, match="no pytest summary line"):
        bat.run()
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL


def test_restore_happens_even_when_the_runner_raises(tmp_path: Path) -> None:
    root = make_repo(tmp_path)

    calls = {"n": 0}

    def exploding() -> str:
        calls["n"] += 1
        if calls["n"] == 3:  # baseline ok, control ok, then the runner dies
            raise RuntimeError("adb wedged")
        return GREEN if calls["n"] == 1 else RED

    bat, _ = battery(root, exploding, mutation())
    with pytest.raises(RuntimeError, match="adb wedged"):
        bat.run()
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL


def test_restore_all_puts_held_files_back_and_reads_them_back(tmp_path: Path) -> None:
    """The layer the signal handler and the exit hook both call, exercised directly."""
    root = make_repo(tmp_path)
    bat, _ = battery(root, FakeRunner(root, []), mutation())
    path = root / "mod.py"
    bat._hold(path)
    path.write_text("mutated", encoding="utf-8")
    assert bat.restore_all() == []
    assert path.read_text(encoding="utf-8") == ORIGINAL


def test_scoring_purges_the_mutated_files_bytecode(tmp_path: Path) -> None:
    """The s28 bug: a byte-perfect restore shadowed by a stale `.pyc`.

    A restored source with an mtime colliding with the compiled bytecode leaves
    CPython importing the mutation while the file reads clean. The battery must
    leave nothing for a later interpreter to load, so it purges the file's `.pyc`
    after every restore. Here a `.pyc` is planted for the target and the run must
    remove it; the fake runner does not compile, so the plant stands in for one.
    """
    root = make_repo(tmp_path)
    cache = root / "__pycache__"
    cache.mkdir()
    poisoned = cache / "mod.cpython-312.pyc"
    poisoned.write_bytes(b"stale mutated bytecode")
    runner = FakeRunner(root, [GREEN, RED, RED])  # baseline, control caught, mutation caught
    bat, _ = battery(root, runner, mutation())
    bat.run()
    assert not poisoned.exists(), "a stale .pyc survived the run and would shadow the restore"
    assert (root / "mod.py").read_text(encoding="utf-8") == ORIGINAL


def test_default_runner_disables_bytecode_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The primary fix, checked without spawning pytest: the subprocess is told
    not to write bytecode, so no `.pyc` can be produced to go stale."""
    import scripts.mutation_battery as mb

    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env", {})
        return subprocess.CompletedProcess(cmd, 0, "1 passed in 0.1s", "")

    monkeypatch.setattr(mb.subprocess, "run", fake_run)
    mb.default_runner(())()
    assert "-B" in captured["cmd"]
    assert captured["env"].get("PYTHONDONTWRITEBYTECODE") == "1"


@pytest.mark.parametrize("bad", [{"expect": "maybe"}, {"new": "THRESHOLD = 10.0"}])
def test_a_malformed_mutation_is_refused_at_construction(bad: dict[str, str]) -> None:
    fields = {"label": "x", "file": "mod.py", "old": "THRESHOLD = 10.0", "new": "T = 1", **bad}
    with pytest.raises(BatteryError):
        Mutation(**fields)
