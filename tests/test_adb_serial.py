# tests/test_adb_serial.py
"""Every adb call names the emulator, and nothing else can be named (#67, plan item 22).

On 2026-11-01 the harness ran with no `-s`, and adb handed its commands to
Colby's USB-attached phone. These tests pin the four things that stop that:
the argv both runners build, the refusal of a non-emulator serial, the device
checks looking for *that* serial, and the boot starting the AVD on the port
that makes the serial name it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.emulator import spawn_emulator
from scripts.preflight import check_device_attached
from tests.test_android_foreground import FakeAdb, ctx_with
from traxgen.android import (
    EMULATOR_SERIAL,
    AdbContext,
    EmulatorNotReadyError,
    NotAnEmulatorError,
    _run_adb,
    _run_adb_binary,
    assert_emulator_ready,
    resolve_context,
)

ADB = Path("/sdk/platform-tools/adb")


@pytest.fixture
def android_home(tmp_path: Path) -> Path:
    adb = tmp_path / "platform-tools" / "adb"
    adb.parent.mkdir()
    adb.touch()
    return tmp_path


def test_both_runners_name_the_device_before_the_command() -> None:
    fake = FakeAdb()
    ctx = AdbContext(adb_path=ADB, runner=fake, sleep=lambda _: None)

    _run_adb(ctx, "shell", "getprop", "sys.boot_completed")
    _run_adb_binary(ctx, "exec-out", "screencap", "-p")

    assert [argv[:3] for argv in fake.calls] == [[str(ADB), "-s", EMULATOR_SERIAL]] * 2


@pytest.mark.parametrize(
    "serial", ["R58M12345", "emulator", "emulator-", "emulator-55a4", "192.168.1.5:5555"]
)
def test_a_serial_that_is_not_an_emulator_cannot_make_a_context(serial: str) -> None:
    with pytest.raises(NotAnEmulatorError, match=serial):
        AdbContext(adb_path=ADB, serial=serial)


def test_the_default_is_the_emulator_when_nothing_names_one(
    android_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANDROID_SERIAL", raising=False)
    assert resolve_context(android_home=android_home).serial == EMULATOR_SERIAL


def test_android_serial_may_name_another_emulator(
    android_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANDROID_SERIAL", "emulator-5556")
    assert resolve_context(android_home=android_home).serial == "emulator-5556"


def test_android_serial_naming_a_phone_is_refused_not_passed_through(
    android_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANDROID_SERIAL", "R58M12345")
    with pytest.raises(NotAnEmulatorError):
        resolve_context(android_home=android_home)


@pytest.mark.parametrize(
    "devices",
    [
        "List of devices attached\nR58M12345\tdevice\n\n",
        "List of devices attached\nemulator-5556\tdevice\n\n",
        "List of devices attached\nemulator-5554\toffline\nR58M12345\tdevice\n\n",
    ],
)
def test_readiness_needs_the_pinned_serial_not_any_device(devices: str) -> None:
    ctx = ctx_with(FakeAdb(devices=devices))
    with pytest.raises(EmulatorNotReadyError, match=EMULATOR_SERIAL):
        assert_emulator_ready(ctx)
    assert not check_device_attached(ctx).ok


def test_readiness_passes_beside_a_phone_and_never_drives_it() -> None:
    fake = FakeAdb(devices="List of devices attached\nR58M12345\tdevice\nemulator-5554\tdevice\n\n")
    ctx = ctx_with(fake)

    assert_emulator_ready(ctx)
    check = check_device_attached(ctx)

    assert check.ok
    assert "never driven: R58M12345" in check.measured
    assert not any("R58M12345" in " ".join(argv) for argv in fake.calls)


class _Popen:
    def __init__(self) -> None:
        self.argv: list[str] = []

    def __call__(self, argv: list[str], **_: object) -> object:
        self.argv = argv
        return object()


@pytest.mark.parametrize(("serial", "port"), [(EMULATOR_SERIAL, "5554"), ("emulator-5556", "5556")])
def test_the_boot_uses_the_port_the_serial_names(tmp_path: Path, serial: str, port: str) -> None:
    popen = _Popen()
    spawn_emulator(
        Path("/sdk/emulator/emulator"), "avd", tmp_path / "log", serial=serial, popen=popen
    )
    flag = popen.argv.index("-port")
    assert popen.argv[flag + 1] == port
