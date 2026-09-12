import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from playstore_app_audit.devices import adb as adb_service
from playstore_app_audit.platform import runtime


def test_platform_tools_url_is_official_google_endpoint() -> None:
    assert runtime.platform_tools_url().startswith(
        "https://dl.google.com/android/repository/platform-tools-latest-"
    )
    assert runtime.platform_tools_url().endswith(".zip")


def test_adb_name_matches_platform() -> None:
    if runtime.platform_key() == "windows":
        assert runtime.adb_executable_name() == "adb.exe"
    else:
        assert runtime.adb_executable_name() == "adb"


def test_store_country_has_two_letters() -> None:
    country = runtime.detect_store_country()
    assert len(country) == 2
    assert country.isalpha()


def test_linux_arm64_requires_native_adb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "aarch64")

    assert runtime.platform_key() == "linux"
    assert runtime.machine_key() == "arm64"
    assert not runtime.managed_platform_tools_download_supported()
    assert "sudo apt install adb" in runtime.managed_platform_tools_unavailable_message()

    with pytest.raises(RuntimeError, match="ARM64"):
        adb_service.install_platform_tools()


def test_linux_x64_managed_adb_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "x86_64")

    assert runtime.machine_key() == "x64"
    assert runtime.managed_platform_tools_download_supported()


def test_macos_arm64_managed_adb_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "arm64")

    assert runtime.platform_key() == "macos"
    assert runtime.machine_key() == "arm64"
    assert runtime.managed_platform_tools_download_supported()


def test_macos_x86_64_managed_adb_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "x86_64")

    assert runtime.platform_key() == "macos"
    assert runtime.machine_key() == "x64"
    assert runtime.managed_platform_tools_download_supported()


@pytest.mark.parametrize(
    ("reported", "normalised"),
    [
        ("x86_64", "x64"),
        ("AMD64", "x64"),
        ("aarch64", "arm64"),
        ("ARM64", "arm64"),
    ],
)
def test_machine_architecture_aliases_are_normalised(
    monkeypatch: pytest.MonkeyPatch, reported: str, normalised: str
) -> None:
    monkeypatch.setattr(runtime.platform, "machine", lambda: reported)

    assert runtime.machine_key() == normalised


@pytest.mark.parametrize("reported", ["ppc64le", "riscv64", ""])
def test_unexpected_linux_architecture_requires_native_adb(
    monkeypatch: pytest.MonkeyPatch, reported: str
) -> None:
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(runtime.platform, "machine", lambda: reported)

    assert not runtime.managed_platform_tools_download_supported()
    assert "native ADB" in runtime.managed_platform_tools_unavailable_message()


def test_find_adb_skips_binary_that_cannot_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    broken = tmp_path / "broken-adb"
    native = tmp_path / "native-adb"
    broken.write_text("broken", encoding="utf-8")
    native.write_text("native", encoding="utf-8")
    monkeypatch.setattr(adb_service, "adb_candidates", lambda: [broken, native])

    def fake_run(adb: str, *args: str, timeout: int = 30):
        assert args == ("version",)
        if adb == str(broken):
            raise OSError("Exec format error")
        return subprocess.CompletedProcess([adb, *args], 0, "Android Debug Bridge\n", "")

    monkeypatch.setattr(adb_service, "run_adb", fake_run)
    assert adb_service.find_adb() == str(native)


def test_find_adb_skips_candidate_that_times_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timed_out = tmp_path / "timed-out-adb"
    native = tmp_path / "native-adb"
    timed_out.touch()
    native.touch()
    monkeypatch.setattr(adb_service, "adb_candidates", lambda: [timed_out, native])

    def fake_run(adb: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        if adb == str(timed_out):
            raise subprocess.TimeoutExpired([adb, *args], timeout)
        return subprocess.CompletedProcess([adb, *args], 0, "Android Debug Bridge\n", "")

    monkeypatch.setattr(adb_service, "run_adb", fake_run)

    assert adb_service.find_adb() == str(native)


def test_find_adb_rejects_nonzero_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    failed = tmp_path / "failed-adb"
    failed.touch()
    monkeypatch.setattr(adb_service, "adb_candidates", lambda: [failed])

    def fake_run(adb: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, [adb, *args])

    monkeypatch.setattr(adb_service, "run_adb", fake_run)

    assert adb_service.find_adb() is None


def test_find_adb_returns_none_when_all_candidates_are_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unusable = [tmp_path / "wrong-arch-adb", tmp_path / "broken-adb"]
    for candidate in unusable:
        candidate.touch()
    monkeypatch.setattr(adb_service, "adb_candidates", lambda: unusable)

    def fake_run(adb: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        if adb == str(unusable[0]):
            raise OSError("Exec format error")
        raise subprocess.CalledProcessError(1, [adb, *args])

    monkeypatch.setattr(adb_service, "run_adb", fake_run)

    assert adb_service.find_adb() is None


def test_scan_phone_schedules_adb_discovery_without_running_it_inline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from playstore_app_audit.ui import main_window

    discovery_ran = False
    thread_started = False
    local_apk_state_invalidated = False
    progressive_state_invalidated = False
    icon_generation_started = False

    def discover(_request_id: int) -> None:
        nonlocal discovery_ran
        discovery_ran = True

    def invalidate_local_apk_parse(*, clear_artifacts: bool) -> None:
        nonlocal local_apk_state_invalidated
        assert clear_artifacts
        local_apk_state_invalidated = True

    def invalidate_progressive_presentation(*, reset_counts: bool) -> None:
        nonlocal progressive_state_invalidated
        assert reset_counts
        progressive_state_invalidated = True

    def begin_icon_result_generation() -> None:
        nonlocal icon_generation_started
        icon_generation_started = True

    class DeferredThread:
        def __init__(self, *, target: Any, args: tuple[int], daemon: bool) -> None:
            assert target is discover
            assert args == (1,)
            assert daemon

        def start(self) -> None:
            nonlocal thread_started
            thread_started = True

    progress = SimpleNamespace(setRange=lambda _start, _end: None)
    status = SimpleNamespace(setText=lambda _text: None)
    window = SimpleNamespace(
        _set_busy=lambda _busy: None,
        progress=progress,
        status_label=status,
        _find_adb_worker=discover,
        _begin_phone_scan_request=lambda: 1,
        _invalidate_local_apk_parse=invalidate_local_apk_parse,
        _invalidate_progressive_presentation=invalidate_progressive_presentation,
        _begin_icon_result_generation=begin_icon_result_generation,
        source_mode="file",
    )
    monkeypatch.setattr(main_window.threading, "Thread", DeferredThread)

    main_window.MainWindow._scan_phone(window)  # type: ignore[arg-type]

    assert thread_started
    assert not discovery_ran
    assert local_apk_state_invalidated
    assert progressive_state_invalidated
    assert icon_generation_started
