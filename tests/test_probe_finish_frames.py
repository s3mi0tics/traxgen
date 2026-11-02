# tests/test_probe_finish_frames.py
"""The probe never writes into a folder that already holds frames (s47-t3).

s46-t3 ran a code a second time and its frames replaced the first run's, which
was the good reference. `frame_folder` chooses the folder; these tests run it on
a scratch tree, with no device.
"""

from __future__ import annotations

from pathlib import Path

from scripts.probe_finish_frames import frame_folder


def _with_frames(folder: Path) -> None:
    folder.mkdir(parents=True)
    (folder / "before.png").write_bytes(b"png")


def test_a_first_single_run_goes_to_the_codes_folder(tmp_path: Path) -> None:
    assert frame_folder(tmp_path, "ABC", runs=1) == tmp_path / "ABC"


def test_a_second_single_run_goes_beside_the_first_not_over_it(tmp_path: Path) -> None:
    _with_frames(tmp_path / "ABC")
    assert frame_folder(tmp_path, "ABC", runs=1) == tmp_path / "ABC" / "run_1"


def test_a_failed_run_counts_as_frames(tmp_path: Path) -> None:
    """A failed attempt still writes frames.json with its evidence path; keep it too."""
    (tmp_path / "ABC").mkdir()
    (tmp_path / "ABC" / "frames.json").write_text("{}")
    assert frame_folder(tmp_path, "ABC", runs=1) == tmp_path / "ABC" / "run_1"


def test_repeated_runs_take_the_next_unused_number(tmp_path: Path) -> None:
    _with_frames(tmp_path / "ABC" / "run_1")
    _with_frames(tmp_path / "ABC" / "run_2")
    assert frame_folder(tmp_path, "ABC", runs=3) == tmp_path / "ABC" / "run_3"


def test_an_empty_run_folder_is_reused(tmp_path: Path) -> None:
    (tmp_path / "ABC" / "run_1").mkdir(parents=True)
    assert frame_folder(tmp_path, "ABC", runs=2) == tmp_path / "ABC" / "run_1"
