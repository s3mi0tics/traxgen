"""
Recursive structural diff for parser round-trip testing.

Walks two nested dict/list/primitive structures in parallel and reports every
field-level divergence with a path string like
'course.layer_construction_data[4].cell_construction_datas[12].tree_node_data.construction_data.kind'.

Floats compare with math.isclose (rel_tol=1e-6, abs_tol=1e-9) because f32
values are stored exactly in the binary but render with different precision
in murmelbahn's serde_json dump vs Python's float repr. See M2 notes.

Path: traxgen/traxgen/_diff.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

_FLOAT_REL_TOL = 1e-6
_FLOAT_ABS_TOL = 1e-9


@dataclass(frozen=True, slots=True)
class Diff:
    """One field-level mismatch between two structures."""
    path: str
    left: Any
    right: Any
    reason: str

    def __str__(self) -> str:
        return f"  at {self.path}: {self.reason}\n      left:  {self.left!r}\n      right: {self.right!r}"


def diff_structures(left: Any, right: Any, *, max_diffs: int = 20) -> list[Diff]:
    """Compare two nested structures. Returns empty list on exact match."""
    diffs: list[Diff] = []
    _walk(left, right, "", diffs, max_diffs)
    return diffs


def _walk(left: Any, right: Any, path: str, diffs: list[Diff], cap: int) -> None:
    if len(diffs) >= cap:
        return

    # Both None -> match
    if left is None and right is None:
        return

    # Type mismatch (treat int/float as compatible; everything else strict)
    if not _types_compatible(left, right):
        diffs.append(Diff(path or "<root>", left, right, f"type mismatch: {type(left).__name__} vs {type(right).__name__}"))
        return

    if isinstance(left, dict):
        _walk_dicts(left, right, path, diffs, cap)
    elif isinstance(left, list):
        _walk_lists(left, right, path, diffs, cap)
    elif isinstance(left, float) or isinstance(right, float):
        if not math.isclose(left, right, rel_tol=_FLOAT_REL_TOL, abs_tol=_FLOAT_ABS_TOL):
            diffs.append(Diff(path or "<root>", left, right, "float not close"))
    else:
        if left != right:
            diffs.append(Diff(path or "<root>", left, right, "value mismatch"))


def _walk_dicts(left: dict, right: dict, path: str, diffs: list[Diff], cap: int) -> None:
    left_keys = set(left.keys())
    right_keys = set(right.keys())

    for key in sorted(left_keys - right_keys):
        if len(diffs) >= cap:
            return
        diffs.append(Diff(f"{path}.{key}" if path else key, left[key], "<missing>", "key only in left"))

    for key in sorted(right_keys - left_keys):
        if len(diffs) >= cap:
            return
        diffs.append(Diff(f"{path}.{key}" if path else key, "<missing>", right[key], "key only in right"))

    for key in sorted(left_keys & right_keys):
        if len(diffs) >= cap:
            return
        child_path = f"{path}.{key}" if path else key
        _walk(left[key], right[key], child_path, diffs, cap)


def _walk_lists(left: list, right: list, path: str, diffs: list[Diff], cap: int) -> None:
    if len(left) != len(right):
        diffs.append(Diff(path or "<root>", f"<list of {len(left)}>", f"<list of {len(right)}>", "length mismatch"))
        return
    for i, (l_item, r_item) in enumerate(zip(left, right)):
        if len(diffs) >= cap:
            return
        _walk(l_item, r_item, f"{path}[{i}]", diffs, cap)


def _types_compatible(left: Any, right: Any) -> bool:
    """Int and float are cross-comparable; otherwise require type match."""
    if type(left) is type(right):
        return True
    numeric = (int, float)
    if isinstance(left, numeric) and isinstance(right, numeric) and not isinstance(left, bool) and not isinstance(right, bool):
        return True
    return False
