# scripts/make_record_index.py
"""Derive `allostatik/decisions-and-observations-index.md` from the record.

`decisions.md` and `observations.md` are never modified, split, moved or abridged.
This script derives an index of them -- one line per entry, carrying the entry's own
first sentence verbatim, a flag when the body revises the title, the line address, and
the withheld body's word count -- and the index is what a session's open loads once
the record is over its byte budget (`allostatik/workflow.md`, open step 3).

Usage::

    uv run python -m scripts.make_record_index            # regenerate
    uv run python -m scripts.make_record_index --verify   # exit 1 if stale
    uv run python -m scripts.make_record_index --root DIR # another project

Exit codes: 0 ok, 1 stale (``--verify``) or refused (short index), 2 usage.

Why this is a project-owned re-implementation rather than the tool's script: the index
*format* is defined by Allostatik's `scripts/make-index.py` (read at v0.3.7 for this
file), and the upgrade contract's rule 3 forbids running anything fetched from the
tool's repo. The open routine regenerates and compares the index every session, and the
close regenerates it whenever an entry lands -- that is a regenerator run twice a
session, forever, which is exactly what earns a committed script. If the format moves
upstream (the monthly CHANGELOG review is the trigger), this file is where it is
re-read against.

Two properties the tests pin because they are the ones that fail silently: the index
refuses to write itself when its entry count differs from an independent count of the
record, and HTML-comment scaffolding is skipped only when a line *begins* with ``<!--``
-- a table cell that mentions a marker mid-line must not swallow the rows below it.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path

INDEX_NAME = "decisions-and-observations-index.md"

_MARK = re.compile(r"\[(AMENDED|SUPERSEDED|RETIRED|CORRECTED|CLOSES)([^\]]{0,40})")
# The bracket convention is not applied consistently, so a second, deliberately
# over-inclusive flag catches revisions stated in prose. A false positive costs one
# cheap lookup; a false negative is a title that lies.
_PROSE = re.compile(r"\b(superseded|no longer|retired|reversed|obsolete|replaced by)\b", re.I)
_OBS_BOLD = re.compile(r"^(\d+)\.\s+(\*\*.*?\*\*)(.*)$")
_OBS_PLAIN = re.compile(r"^(\d+)\.\s+([^*].*?\.)(\s.*)?$")
_OBS_ANY = re.compile(r"^\d+\.\s")
_D_LINE = re.compile(r"^D\d{3} · ")
_O_LINE = re.compile(r"^#\d+ · ")


class RecordIndexError(Exception):
    """The index would misdescribe the record; nothing was written."""


def content_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, line)`` for real content, skipping HTML-comment scaffolding.

    A comment counts only when a line *begins* with ``<!--`` and runs to the line
    carrying ``-->``. Stripping ``<!--`` wherever it appears is wrong: the record
    discusses markers inside its own table cells.
    """
    in_comment = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if line.lstrip().startswith("<!--"):
            if "-->" not in line:
                in_comment = True
            continue
        yield lineno, line


def flag(body: str) -> str:
    """The revision flag for an entry body, or ``""`` when the title stands as written."""
    match = _MARK.search(body)
    if not match:
        return " **[?revised]**" if _PROSE.search(body) else ""
    session = re.search(r"\bs(\d{1,3})\b", match.group(2))
    date = re.search(r"(\d{4}-\d{2}-\d{2})", match.group(2))
    when = f" s{session.group(1)}" if session else (f" {date.group(1)}" if date else "")
    return f" **[{match.group(1)}{when}]**"


def _decision_rows(text: str) -> Iterator[tuple[int, str]]:
    """Table rows below the header rule -- keyed on table structure, never a column name."""
    below_rule = False
    for lineno, line in content_lines(text):
        if line.startswith("|---") or line.startswith("| ---"):
            below_rule = True
            continue
        if below_rule and line.startswith("| "):
            yield lineno, line


def index_decisions(text: str) -> list[str]:
    """One ``DNNN`` line per table row, in file order."""
    out: list[str] = []
    for n, (lineno, line) in enumerate(_decision_rows(text), 1):
        cells = line.split(" | ")
        title = cells[0][2:].strip()
        body = " | ".join(cells[1:]).rstrip(" |") if len(cells) > 1 else ""
        out.append(f"D{n:03d} · {title}{flag(body)} → decisions.md:{lineno}, "
                   f"body {len(body.split())}w")
    return out


def index_observations(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Sections after the first ``## `` heading, each with tagged lines.

    Tag ``E`` is an indexed entry; ``T`` is section prose kept for sections that hold
    no numbered entries (a watch list's roster is content, and an empty heading would
    assert there is nothing there).
    """
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    heading: str | None = None
    buf: list[tuple[str, str]] = []
    for lineno, line in content_lines(text):
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, buf))
            heading, buf = line, []
            continue
        if heading is None:
            continue
        match = _OBS_BOLD.match(line) or _OBS_PLAIN.match(line)
        if match:
            body = (match.group(3) or "").strip()
            buf.append(("E", f"#{match.group(1)} · {match.group(2).strip()}{flag(body)}"
                             f" → observations.md:{lineno}, body {len(body.split())}w"))
        elif line.strip() and not line.startswith("---"):
            buf.append(("T", line))
    if heading is not None:
        sections.append((heading, buf))
    return sections


def count_sources(decisions: str, observations: str) -> tuple[int, int]:
    """Entry counts taken independently of the index builder's own regexes."""
    n_dec = sum(1 for _ in _decision_rows(decisions))
    n_obs, started = 0, False
    for _, line in content_lines(observations):
        if line.startswith("## "):
            started = True
        elif started and _OBS_ANY.match(line):
            n_obs += 1
    return n_dec, n_obs


def _header(flagged: int) -> list[str]:
    note = (f"{flagged} of these decision titles carry one." if flagged
            else "No decision title in this project carries one yet.")
    return [
        "# Decisions and observations — index of every entry this project holds\n",
        "**This is an index, not the record.** Each line is that entry's own first\n"
        "sentence, verbatim — never a summary, never rewritten. The reasoning, evidence,\n"
        "scope and exceptions are NOT here; they are in `decisions.md` and\n"
        "`observations.md`, which are complete, unmodified and still in force. Nothing\n"
        "has been retired, moved or demoted.\n",
        "`body NNNw` is the length of what this line is not showing. A **[AMENDED]** or\n"
        "**[SUPERSEDED]** flag means the body changes or reverses what the title says —\n"
        f"**those are never safe to act on from this file.** {note}\n",
        "Look one up by the line address on its own line — exact, and unaffected by any\n"
        "punctuation in a title that a literal `grep` would trip over:\n\n"
        "    sed -n '127p' allostatik/decisions.md\n"
        "    sed -n '412p' allostatik/observations.md\n\n"
        "Line addresses are regenerated with this file, so they are current whenever the\n"
        "open's verify passes. `D` numbers are positional in file order; both files are\n"
        "append-only, so they are stable in practice, but an insert would renumber below it.\n",
        "Generated by `uv run python -m scripts.make_record_index`; regenerated at close\n"
        "and checked at the open (`--verify`). Do not hand-edit — edits belong in the two\n"
        "files above.\n",
    ]


def build(root: Path) -> str:
    """The index text for the project at ``root``; raises RecordIndexError rather than
    return an index that describes fewer entries than the record holds."""
    record = root / "allostatik"
    decisions = (record / "decisions.md").read_text(encoding="utf-8")
    observations = (record / "observations.md").read_text(encoding="utf-8")

    d_lines = index_decisions(decisions)
    sections = index_observations(observations)
    o_lines = [text for _, buf in sections for tag, text in buf if tag == "E"]

    n_dec, n_obs = count_sources(decisions, observations)
    if (len(d_lines), len(o_lines)) != (n_dec, n_obs):
        raise RecordIndexError(
            f"REFUSING to write a short index: decisions {len(d_lines)}/{n_dec}, "
            f"observations {len(o_lines)}/{n_obs}"
        )
    for heading, buf in sections:
        if buf and not any(text.strip() for _, text in buf):
            raise RecordIndexError(
                f"REFUSING: source section {heading!r} has content but would render empty"
            )

    flagged = sum(1 for line in d_lines if "**[" in line)
    out = _header(flagged)
    out.append("\n## Decisions\n")
    out.extend(d_lines)
    out.append("\n## Observations\n")
    out.append("*`Promoted` and `Candidates` are both observations; the split is maturity, not\n"
               "kind. Promotion means three or more firings across separate sessions.*\n")
    for heading, buf in sections:
        out.append("\n" + heading + "\n")
        entries = [text for tag, text in buf if tag == "E"]
        out.extend(entries if entries else [text for tag, text in buf if tag == "T"])
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="make_record_index",
        description="Derive the record index. Exit 0 ok, 1 stale or refused, 2 usage.",
    )
    parser.add_argument("--verify", action="store_true",
                        help="check the index is current; write nothing (exit 1 if stale)")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="project root holding allostatik/ (default: cwd)")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    if not (root / "allostatik").is_dir():
        print(f"no allostatik/ under {root} -- pass --root <project>", file=sys.stderr)
        return 2
    target = root / "allostatik" / INDEX_NAME
    try:
        new = build(root)
    except RecordIndexError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.verify:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current == new:
            print(f"{INDEX_NAME}: CURRENT")
            return 0
        print(f"{INDEX_NAME}: STALE — regenerate with "
              "`uv run python -m scripts.make_record_index`")
        return 1

    target.write_text(new, encoding="utf-8")
    words = len(new.split())
    n_d = sum(1 for line in new.splitlines() if _D_LINE.match(line))
    n_o = sum(1 for line in new.splitlines() if _O_LINE.match(line))
    print(f"{INDEX_NAME} written: {n_d} decisions, {n_o} observations, "
          f"{new.count(chr(10))} lines, {words} words (~{round(words * 1.35 / 1000)}k tokens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
