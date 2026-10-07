"""Offline tests for the generated-placement campaign (scripts/probe_generated_placement.py).

No emulator, no network. What must be right before renders are spent: the
generated arm is byte-for-byte what `generate` emits, the local control sits at
the same starter on the starter's own plate, the brackets open and close the
run, and every verdict branch fires on the inputs it should.

Path: traxgen/tests/test_probe_generated_placement.py
"""

from __future__ import annotations

import hashlib

import pytest

from scripts.probe_generated_placement import (
    Arm,
    GoalSite,
    Role,
    Verdict,
    build_arm_course,
    build_arms,
    classify,
    derive_geometry,
    main,
    render_campaign,
)
from traxgen.generator import generate_multi_plate
from traxgen.graph import placed_tiles
from traxgen.hex import HexVector
from traxgen.serializer import serialize_course
from traxgen.types import TileKind

GEOMETRY = derive_geometry()


def _sha(role: Role) -> str:
    return hashlib.sha256(serialize_course(build_arm_course(role, GEOMETRY))).hexdigest()


def test_geometry_is_the_generators_first_placement_and_the_east_control() -> None:
    assert GEOMETRY.plate_offsets == ((0, 0), (3, -6), (5, 0), (8, -6))
    assert GEOMETRY.starter_local == (-4, 0)
    assert GEOMETRY.starter_rot == 0
    assert GEOMETRY.generated == GoalSite(
        direction=4, goal_plate_index=1, goal_local=(-6, 5), goal_rot=5, goal_plate_offset=(3, -6)
    )
    assert GEOMETRY.local_control == GoalSite(
        direction=0, goal_plate_index=0, goal_local=(-4, 1), goal_rot=1, goal_plate_offset=None
    )


def test_generated_arm_is_generate_multi_plate_byte_for_byte() -> None:
    built = serialize_course(build_arm_course(Role.GENERATED, GEOMETRY))
    assert built == serialize_course(generate_multi_plate())
    assert len(built) == 253
    assert _sha(Role.GENERATED) == (
        "13a04d760311cf353a947912624adbc0e0324f6b862009a4871e4e0431afb172"
    )


def test_certified_arm_is_the_kn6f459zr3_payload() -> None:
    assert _sha(Role.CERTIFIED) == (
        "1ede9be9e5a843b1f09576837be8e80c4c2f579d5eb1a331aed99cc49ff7db1c"
    )


def test_local_control_shares_the_starter_and_puts_the_goal_on_plate_zero() -> None:
    control = build_arm_course(Role.LOCAL_CONTROL, GEOMETRY)
    generated = build_arm_course(Role.GENERATED, GEOMETRY)
    assert _sha(Role.LOCAL_CONTROL) == (
        "b6e2492e6c72fec2de87d99f912b22f85abf0e17d08711975fd077de19766028"
    )

    def starter(course):
        (tile,) = [t for t in placed_tiles(course) if t.kind is TileKind.STARTER]
        return (tile.world_pos, tile.local_pos, tile.hex_rotation, tile.layer_id)

    assert starter(control) == starter(generated)

    plate_zero = control.layer_construction_data[0]
    assert plate_zero.world_hex_position == HexVector(y=0, x=0)
    goals = [
        (cell.local_hex_position, cell.tree_node_data.construction_data.hex_rotation)
        for cell in plate_zero.cell_construction_datas
        if cell.tree_node_data.construction_data.kind is TileKind.GOAL_RAIL
    ]
    assert goals == [(HexVector(y=-4, x=1), 1)]
    assert len(control.layer_construction_data) == 4


def test_arms_render_in_bracketed_order_all_predicted_active() -> None:
    arms = build_arms(GEOMETRY)
    assert [(a.label, a.role) for a in arms] == [
        ("certified_open", Role.CERTIFIED),
        ("local_control", Role.LOCAL_CONTROL),
        ("generated", Role.GENERATED),
        ("certified_close", Role.CERTIFIED),
    ]
    assert [a.predicted for a in arms] == ["active"] * 4


def _arms(open_: str | None, local: str | None, gen: str | None, close: str | None) -> list[Arm]:
    arms = build_arms(GEOMETRY)
    for arm, validity in zip(arms, (open_, local, gen, close), strict=True):
        arm.validity = validity
    return arms


@pytest.mark.parametrize(
    ("validities", "expected"),
    [
        (("active", "active", "active", "active"), Verdict.CONNECTED),
        (("active", "active", "inactive", "active"), Verdict.DISCONNECTED),
        (("active", "active", "active", "inactive"), Verdict.HARNESS_SUSPECT),
        (("inactive", "active", "active", "active"), Verdict.HARNESS_SUSPECT),
        (("active", "inactive", "inactive", "inactive"), Verdict.HARNESS_SUSPECT),
        ((None, "active", "active", "active"), Verdict.HARNESS_SUSPECT),
        (("active", "inactive", None, "active"), Verdict.SETUP_SUSPECT),
        (("active", "inactive", "active", "active"), Verdict.SETUP_SUSPECT),
        (("active", None, "active", "active"), Verdict.INCOMPLETE),
        (("active", "active", None, "active"), Verdict.INCOMPLETE),
    ],
)
def test_verdict_table(validities: tuple[str | None, ...], expected: Verdict) -> None:
    verdict, _ = classify(_arms(*validities))
    assert verdict is expected


def _uploaded() -> list[Arm]:
    arms = build_arms(GEOMETRY)
    for arm in arms:
        arm.code = "AAAAAAAAAA"
    return arms


def test_a_dark_local_control_skips_the_generated_render_but_not_the_closing_bracket() -> None:
    rendered: list[str] = []
    outcome = {"certified_open": "active", "local_control": "inactive", "certified_close": "active"}

    def fake_render(arm: Arm) -> None:
        rendered.append(arm.label)
        arm.validity = outcome[arm.label]

    arms = _uploaded()
    render_campaign(arms, fake_render)

    assert rendered == ["certified_open", "local_control", "certified_close"]
    assert arms[2].validity is None
    assert arms[2].render_error == "skipped: the local control rendered dark (D039)"
    assert classify(arms)[0] is Verdict.SETUP_SUSPECT


def test_an_arm_that_failed_to_upload_is_not_rendered() -> None:
    rendered: list[str] = []
    arms = _uploaded()
    arms[2].code = None

    def fake_render(arm: Arm) -> None:
        rendered.append(arm.label)
        arm.validity = "active"

    render_campaign(arms, fake_render)
    assert rendered == ["certified_open", "local_control", "certified_close"]
    assert classify(arms)[0] is Verdict.INCOMPLETE


def test_dry_run_exits_zero_and_uploads_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "4 renders; nothing uploaded (--dry-run)." in out
    assert "sha=13a04d760311" in out


def test_render_arm_calls_render_course_with_arguments_it_accepts(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Every other test stops short of the render, so a keyword `render_course`
    does not take reached the emulator once, swallowed into `render_error`."""
    import inspect

    from scripts import probe_generated_placement as probe
    from traxgen import android

    real = inspect.signature(android.render_course)

    def fake(*args, **kwargs):
        real.bind(*args, **kwargs)
        return android.RenderResult(screenshot=tmp_path / "x.png", validity="active")

    monkeypatch.setattr(probe, "render_course", fake)
    arm = probe.build_arms(probe.derive_geometry())[0]
    arm.code = "KN6F459ZR3"
    probe.render_arm(object(), arm, tmp_path)
    assert (arm.validity, arm.render_error) == ("active", None)
