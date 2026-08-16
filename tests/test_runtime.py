import subprocess

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


def test_find_adb_skips_binary_that_cannot_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path
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
