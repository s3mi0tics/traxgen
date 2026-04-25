"""Trace oracle (v7) and fixture (v4) through metadata. Compare post-metadata bytes.

Path: traxgen/scripts/trace_both.py
"""
from enum import IntEnum
from traxgen import types

class ExtendedCourseSaveDataVersion(IntEnum):
    INITIAL_LAUNCH = 100101
    RAIL_REWORK_2018 = 100201
    PERSISTENCE_REFACTOR_2019 = 1
    ZIPLINE_ADDED_2019 = 2
    PRO_2020 = 3
    POWER_2022 = 4
    LIGHT_STONES_2023 = 5
    UNKNOWN_6 = 6
    UNKNOWN_7 = 7

types.CourseSaveDataVersion = ExtendedCourseSaveDataVersion

import importlib, traxgen.domain, traxgen.parser
importlib.reload(traxgen.domain)
importlib.reload(traxgen.parser)

from pathlib import Path
from traxgen.parser import Reader


def trace(bytes_data, label):
    r = Reader(bytes_data)
    guid = r.read_u128()
    version = r.read_u32()
    ts = r.read_u64()
    title = r.read_string()
    order = r.read_s32()
    kind = r.read_u8()
    obj = r.read_u8()
    diff = r.read_u32()
    comp = r.read_u8()

    print(f"=== {label} ===")
    print(f"  guid={guid}")
    print(f"  version={version} title={title!r} order={order} kind={kind} obj={obj} diff={diff} comp={comp}")
    print(f"  metadata ends at pos=0x{r.pos:04x}")
    print(f"  next 40 bytes raw:")
    for i in range(min(40, len(bytes_data) - r.pos)):
        b = bytes_data[r.pos + i]
        print(f"    +{i:2d} (abs 0x{r.pos+i:04x}): 0x{b:02x} = {b:>3d}")
    print()


oracle = Path("tests/fixtures/oracle/4YCV8JHLX7.course").read_bytes()
fixture = Path("tests/fixtures/GDZJZA3J3T.course").read_bytes()

trace(oracle, "ORACLE (v7)")
trace(fixture, "FIXTURE (v4)")
