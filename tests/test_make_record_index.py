# tests/test_make_record_index.py
"""Offline tests for `scripts/make_record_index.py` -- the record index.

Every test builds a small synthetic record under `tmp_path` and reads the index
back, so nothing here depends on the project's real `decisions.md` or
`observations.md`. That is the same move as an injected fake: the script takes a
project root, and a root we wrote ourselves is a root whose right answer we know.

What these pin, in order of how silently each would fail: the completeness refusal
(an index short by one entry loses that entry with no error anywhere), the line
addresses (a wrong address sends the reader to the wrong entry), the verbatim title
and revision flags (a flag missing on a superseded decision is the line someone
acts on), the comment-scaffolding boundary, and the `--verify` exit codes the open
routine keys on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.make_record_index import (
    INDEX_NAME,
    RecordIndexError,
    build,
    count_sources,
    flag,
    main,
)

DECISIONS = """# Decisions

<!-- Template scaffolding, not a decision:
| Example | Choice | Rationale |
-->

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Ships with the tooling we already run |
| Repo private first | Private, public later **[SUPERSEDED s12]** | Went public at s12 |
| Marker prose | A cell that mentions `<!-- BEGIN` mid-line | Must not swallow rows below |
| Fixed sleeps | Kept for now | The polling primitives no longer fit; revisit |
"""

OBSERVATIONS = """# Observations

Preamble: 1. this numbered line is not an entry.

## Promoted

1. **Probe first, implement second.** A small probe beats a big assumption.
2. Plain-title entry ends at its first period. Then the body continues here.

## Candidates

3. **(candidate)** Tagged the way a late-session entry sometimes is.

## Watch list

Roster: #2 (two firings), #3 (one firing).
"""


def write_record(root: Path, decisions: str = DECISIONS, observations: str = OBSERVATIONS) -> Path:
    record = root / "allostatik"
    record.mkdir()
    (record / "decisions.md").write_text(decisions, encoding="utf-8")
    (record / "observations.md").write_text(observations, encoding="utf-8")
    return root


def entry_lines(index: str) -> tuple[list[str], list[str]]:
    lines = index.splitlines()
    return ([ln for ln in lines if ln.startswith("D0")],
            [ln for ln in lines if ln.startswith("#") and " · " in ln])


def test_one_line_per_entry_and_addresses_resolve(tmp_path: Path) -> None:
    root = write_record(tmp_path)
    index = build(root)
    d_lines, o_lines = entry_lines(index)
    assert len(d_lines) == 4 and len(o_lines) == 3
    assert count_sources(DECISIONS, OBSERVATIONS) == (4, 3)
    # Every address points at a line that begins the entry it names.
    decisions = DECISIONS.splitlines()
    observations = OBSERVATIONS.splitlines()
    for line in d_lines:
        lineno = int(line.split("decisions.md:")[1].split(",")[0])
        title = line.split(" · ", 1)[1].split(" →")[0].split(" **[")[0]
        assert decisions[lineno - 1].startswith("| " + title)
    for line in o_lines:
        number = line[1:].split(" · ")[0]
        lineno = int(line.split("observations.md:")[1].split(",")[0])
        assert observations[lineno - 1].startswith(f"{number}. ")


def test_title_is_verbatim_and_body_is_counted_not_shown(tmp_path: Path) -> None:
    index = build(write_record(tmp_path))
    d_lines, o_lines = entry_lines(index)
    assert d_lines[0] == "D001 · Language → decisions.md:9, body 10w"
    assert o_lines[0] == "#1 · **Probe first, implement second.** → observations.md:7, body 7w"
    assert o_lines[1].startswith("#2 · Plain-title entry ends at its first period. →")
    assert o_lines[1].endswith("observations.md:8, body 5w")
    assert "beats a big assumption" not in index


def test_flags_from_bracket_and_from_prose() -> None:
    assert flag("Went public **[SUPERSEDED s12]** later") == " **[SUPERSEDED s12]**"
    assert flag("Changed **[AMENDED 2026-08-28]**") == " **[AMENDED 2026-08-28]**"
    assert flag("the primitives no longer fit") == " **[?revised]**"
    assert flag("a plain body") == ""


def test_flagged_titles_are_marked_and_counted(tmp_path: Path) -> None:
    index = build(write_record(tmp_path))
    d_lines, _ = entry_lines(index)
    assert " **[SUPERSEDED s12]** → " in d_lines[1]
    assert " **[?revised]** → " in d_lines[3]
    assert "2 of these decision titles carry one." in index


def test_scaffolding_skipped_but_inline_marker_keeps_rows(tmp_path: Path) -> None:
    index = build(write_record(tmp_path))
    d_lines, _ = entry_lines(index)
    assert not any("Example" in line for line in d_lines)
    assert any(line.startswith("D003 · Marker prose") for line in d_lines)
    assert any(line.startswith("D004 · Fixed sleeps") for line in d_lines)


def test_section_without_entries_keeps_its_prose(tmp_path: Path) -> None:
    index = build(write_record(tmp_path))
    assert "## Watch list\n\nRoster: #2 (two firings), #3 (one firing)." in index
    assert "Preamble: 1. this numbered line" not in index


def test_refuses_to_write_a_short_index(tmp_path: Path) -> None:
    # Counted as an entry by the independent count, matched by neither title shape.
    short = OBSERVATIONS.replace("## Candidates\n", "## Candidates\n\n4. lowercase and no period\n")
    root = write_record(tmp_path, observations=short)
    with pytest.raises(RecordIndexError, match=r"observations 3/4"):
        build(root)
    assert main(["--root", str(root)]) == 1
    assert not (root / "allostatik" / INDEX_NAME).exists()


def test_verify_reports_current_then_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write_record(tmp_path)
    assert main(["--root", str(root)]) == 0
    assert "4 decisions, 3 observations" in capsys.readouterr().out
    assert main(["--verify", "--root", str(root)]) == 0
    with (root / "allostatik" / "decisions.md").open("a", encoding="utf-8") as fh:
        fh.write("| New row | Chosen | Because |\n")
    assert main(["--verify", "--root", str(root)]) == 1
    assert "STALE" in capsys.readouterr().out


def test_usage_error_without_a_record(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path)]) == 2
