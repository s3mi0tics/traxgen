# tests/test_main.py
"""Tests for `traxgen/__main__.py` -- the command Phase 1's definition of done names.

Two kinds of test here, and the distinction is worth knowing.

The in-process tests call ``main([...])`` directly and hand it a **fake generator**
through the ``generate=`` keyword. A fake is a stand-in that returns a value we chose
-- here, a course with its goal removed -- so the failure path runs deterministically
without finding a way to make the real generator fail. The seam is ordinary dependency
injection: ``main`` never imports its collaborator by name inside the body, it takes
it as a parameter with a real default. Playwright's equivalent is ``page.route()``:
you intercept a dependency at its boundary and answer it yourself.

The last test is different in kind. It spawns ``python -m traxgen`` as a **process**,
because that is the claim under test: the module resolves and runs from the command
line. Every in-process test would pass with `__main__.py` misnamed; only the process
test would fail. It carries the ``integration`` marker for that reason -- it crosses
the interpreter boundary, not because it is slow.
"""

from __future__ import annotations

import dataclasses
import io
import subprocess
import sys
from pathlib import Path

import pytest

from traxgen.__main__ import SETS, main
from traxgen.domain import Course
from traxgen.generator import generate_minimal
from traxgen.inventory import PRO_VERTICAL_STARTER_SET, Inventory
from traxgen.serializer import serialize_course
from traxgen.types import TileKind

REPO_ROOT = Path(__file__).resolve().parent.parent


def goalless(inventory: Inventory) -> Course:
    """A fake generator: the minimal course with its GOAL_RAIL cell dropped."""
    course = generate_minimal(inventory)
    layer = course.layer_construction_data[0]
    keep = tuple(
        cell for cell in layer.cell_construction_datas
        if cell.tree_node_data.construction_data.kind is not TileKind.GOAL_RAIL
    )
    assert len(keep) == 1
    bad_layer = dataclasses.replace(layer, cell_construction_datas=keep)
    return dataclasses.replace(course, layer_construction_data=(bad_layer,))


def test_generate_writes_exactly_the_library_bytes(tmp_path: Path) -> None:
    out = tmp_path / "vs.course"
    stdout = io.StringIO()
    assert main(["generate", "--set", "vertical-starter", "--out", str(out)], stdout=stdout) == 0
    assert out.read_bytes() == serialize_course(generate_minimal(PRO_VERTICAL_STARTER_SET))
    assert stdout.getvalue() == f"wrote {out.stat().st_size} bytes to {out}\n"


def test_default_output_is_the_set_name_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["generate", "--set", "vertical-starter"], stdout=io.StringIO()) == 0
    assert (tmp_path / "vertical-starter.course").is_file()


def test_invalid_course_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    out = tmp_path / "bad.course"
    stderr = io.StringIO()
    code = main(["generate", "--set", "vertical-starter", "--out", str(out)],
                generate=goalless, stderr=stderr)
    assert code == 1
    assert not out.exists()
    assert "MISSING_STARTER_OR_GOAL" in stderr.getvalue()
    assert stderr.getvalue().startswith(f"refusing to write {out}")


def test_no_validate_writes_the_course_anyway(tmp_path: Path) -> None:
    out = tmp_path / "bad.course"
    code = main(["generate", "--set", "vertical-starter", "--out", str(out), "--no-validate"],
                generate=goalless, stdout=io.StringIO())
    assert code == 0
    assert out.read_bytes() == serialize_course(goalless(PRO_VERTICAL_STARTER_SET))


@pytest.mark.parametrize("argv", [[], ["generate"], ["generate", "--set", "core"]])
def test_bad_usage_exits_2(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    assert "usage: traxgen" in capsys.readouterr().err


def test_only_certified_sets_are_offered() -> None:
    assert set(SETS) == {"vertical-starter"}


@pytest.mark.integration
def test_python_dash_m_traxgen_runs_the_dod_command(tmp_path: Path) -> None:
    out = tmp_path / "dod.course"
    proc = subprocess.run(
        [sys.executable, "-m", "traxgen", "generate", "--set", "vertical-starter",
         "--out", str(out)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"wrote {out.stat().st_size} bytes to {out}\n"
    assert out.read_bytes() == serialize_course(generate_minimal(PRO_VERTICAL_STARTER_SET))
