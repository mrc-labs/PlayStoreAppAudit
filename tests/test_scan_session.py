from __future__ import annotations

import subprocess
from dataclasses import fields
from datetime import UTC
from types import SimpleNamespace

import pytest

import playstore_app_audit.services.scan_session as scan_sessions
import playstore_app_audit.services.store_locale as store_locale

GETPROP_WITH_LOCALE = "\n".join(
    (
        "[ro.product.manufacturer]: [Google]",
        "[ro.product.model]: [Pixel 9 Pro]",
        "[ro.build.version.release]: [16]",
        "[ro.build.version.sdk]: [36]",
        "[ro.build.version.security_patch]: [2026-08-05]",
        "[persist.sys.locale]: [it-CH]",
    )
)


def _completed(stdout: str) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout)


def _successful_runner(
    calls: list[tuple[str, ...]], *, properties: str = GETPROP_WITH_LOCALE
):
    def run(_adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del timeout
        calls.append(args)
        if args == ("devices",):
            return _completed("List of devices attached\nraw-serial-1234\tdevice\n")
        if args == ("shell", "getprop"):
            return _completed(properties)
        if args == (
            "shell",
            "pm",
            "list",
            "packages",
            "-3",
            "-i",
            "--show-versioncode",
        ):
            return _completed(
                "package:com.example.beta versionCode:202 installer=null\n"
                "package:com.example.alpha versionCode:101 installer=com.android.vending\n"
            )
        if args == ("shell", "pm", "list", "packages", "-3", "-d"):
            return _completed("package:com.example.beta\n")
        if args == ("shell", "pm", "list", "packages", "-3"):
            return _completed("package:com.example.beta\npackage:com.example.alpha\n")
        if args == (
            "shell",
            "pm",
            "list",
            "packages",
            "-i",
            "--show-versioncode",
        ):
            return _completed(
                "package:com.android.settings versionCode:36 installer=null\n"
                "package:com.example.beta versionCode:202 installer=null\n"
                "package:com.example.alpha versionCode:101 installer=com.android.vending\n"
            )
        if args == ("shell", "pm", "list", "packages", "-d"):
            return _completed("package:com.example.beta\n")
        if args == ("shell", "pm", "list", "packages"):
            return _completed(
                "package:com.android.settings\n"
                "package:com.example.beta\n"
                "package:com.example.alpha\n"
            )
        if args == ("shell", "pm", "list", "packages", "-s"):
            return _completed("package:com.android.settings\n")
        raise AssertionError(args)

    return run


def test_scan_session_reuses_one_device_context_and_has_no_raw_serial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(scan_sessions, "run_adb", _successful_runner(calls))

    session = scan_sessions.collect_scan_session("adb", exclude_system=True)

    assert session.captured_at.tzinfo is UTC
    assert session.source_kind == "device"
    assert session.source_id.startswith(f"device:{session.device_id}:")
    assert session.device_id not in {"", "raw-serial-1234"}
    assert session.serial_masked == "••••1234"
    assert "raw-serial-1234" not in repr(session)
    assert "serial" not in {field.name for field in fields(session)} - {"serial_masked"}
    assert session.manufacturer == "Google"
    assert session.model == "Pixel 9 Pro"
    assert session.android_version == "16"
    assert session.android_api == "36"
    assert session.security_patch == "2026-08-05"
    assert session.locale == store_locale.StoreLocale(
        "it", "ch", "it-CH", "android_getprop:persist.sys.locale"
    )
    assert session.packages == ("com.example.alpha", "com.example.beta")
    assert session.package_count == 2
    assert session.third_party_package_count == 2
    assert session.system_package_count == 0
    assert session.system_scope == "third_party_only"
    assert not session.locale_fallback_attempted
    metadata = session.metadata_by_package()
    assert metadata["com.example.alpha"].installed_version_code == "101"
    assert metadata["com.example.alpha"].installer_package == "com.android.vending"
    assert metadata["com.example.alpha"].installer_source == (
        "Google Play (com.android.vending)"
    )
    assert metadata["com.example.alpha"].installer_category == "google_play"
    assert metadata["com.example.alpha"].is_enabled
    assert not metadata["com.example.alpha"].is_system
    assert metadata["com.example.beta"].installed_version_code == "202"
    assert metadata["com.example.beta"].installer_package == ""
    assert metadata["com.example.beta"].installer_source == "Unknown / preinstalled"
    assert not metadata["com.example.beta"].is_enabled
    assert calls == [
        ("devices",),
        ("shell", "getprop"),
        ("shell", "pm", "list", "packages", "-3", "-i", "--show-versioncode"),
        ("shell", "pm", "list", "packages", "-3", "-d"),
    ]


def test_all_package_scope_preserves_system_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(scan_sessions, "run_adb", _successful_runner(calls))

    session = scan_sessions.collect_scan_session("adb", exclude_system=False)

    assert session.packages == (
        "com.android.settings",
        "com.example.alpha",
        "com.example.beta",
    )
    assert session.system_packages == frozenset({"com.android.settings"})
    assert session.package_count == 3
    assert session.system_package_count == 1
    assert session.third_party_package_count == 2
    assert session.system_scope == "all_packages"
    assert session.metadata_by_package()["com.android.settings"].is_system
    assert not session.metadata_by_package()["com.example.alpha"].is_system
    assert calls[-3:] == [
        ("shell", "pm", "list", "packages", "-i", "--show-versioncode"),
        ("shell", "pm", "list", "packages", "-s"),
        ("shell", "pm", "list", "packages", "-d"),
    ]


def test_locale_fallback_runs_only_when_shared_properties_lack_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    properties = GETPROP_WITH_LOCALE.replace("[persist.sys.locale]: [it-CH]", "")
    monkeypatch.setattr(
        scan_sessions, "run_adb", _successful_runner(calls, properties=properties)
    )
    fallback_calls: list[list[str]] = []

    def fallback_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        fallback_calls.append(command)
        return _completed("de-DE,it-IT\n")

    monkeypatch.setattr(store_locale.subprocess, "run", fallback_run)

    session = scan_sessions.collect_scan_session("adb", exclude_system=True)

    assert session.locale_fallback_attempted
    assert session.locale == store_locale.StoreLocale(
        "de", "de", "de-DE", "android_settings:system_locales"
    )
    assert fallback_calls == [
        ["adb", "shell", "settings", "get", "system", "system_locales"]
    ]
    assert calls.count(("shell", "getprop")) == 1


def test_locale_fallback_failure_is_nonfatal_and_does_not_repeat_getprop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    properties = GETPROP_WITH_LOCALE.replace("[persist.sys.locale]: [it-CH]", "")
    monkeypatch.setattr(
        scan_sessions, "run_adb", _successful_runner(calls, properties=properties)
    )
    monkeypatch.setattr(
        store_locale.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("adb", 15)),
    )

    session = scan_sessions.collect_scan_session("adb", exclude_system=True)

    assert session.locale is None
    assert session.locale_fallback_attempted
    assert calls.count(("shell", "getprop")) == 1


@pytest.mark.parametrize(
    ("device_line", "message"),
    [
        ("", "no Android phone is visible"),
        ("serial\tunauthorized", "not authorised"),
        ("serial\toffline", "offline"),
    ],
)
def test_invalid_device_state_never_collects_or_returns_a_session(
    monkeypatch: pytest.MonkeyPatch, device_line: str, message: str
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(_adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del timeout
        calls.append(args)
        assert args == ("devices",)
        suffix = f"{device_line}\n" if device_line else ""
        return _completed(f"List of devices attached\n{suffix}")

    monkeypatch.setattr(scan_sessions, "run_adb", run)

    with pytest.raises(RuntimeError, match=message):
        scan_sessions.collect_scan_session("adb", exclude_system=True)
    assert calls == [("devices",)]


def test_multiple_authorised_devices_are_rejected_before_collecting_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(_adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del timeout
        calls.append(args)
        return _completed(
            "List of devices attached\nserial-a\tdevice\nserial-b\tdevice\n"
        )

    monkeypatch.setattr(scan_sessions, "run_adb", run)

    with pytest.raises(RuntimeError, match="More than one authorised"):
        scan_sessions.collect_scan_session("adb", exclude_system=True)
    assert calls == [("devices",)]


def test_summary_failure_does_not_continue_to_package_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(_adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del timeout
        calls.append(args)
        if args == ("devices",):
            return _completed("List of devices attached\nserial\tdevice\n")
        raise subprocess.CalledProcessError(1, ["adb", *args])

    monkeypatch.setattr(scan_sessions, "run_adb", run)

    with pytest.raises(RuntimeError, match="device summary"):
        scan_sessions.collect_scan_session("adb", exclude_system=True)
    assert calls == [("devices",), ("shell", "getprop")]


def test_package_enumeration_failure_does_not_return_a_partial_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    successful = _successful_runner(calls)

    def run(adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        if args[:5] == ("shell", "pm", "list", "packages", "-3"):
            calls.append(args)
            raise subprocess.CalledProcessError(1, [adb, *args])
        return successful(adb, *args, timeout=timeout)

    monkeypatch.setattr(scan_sessions, "run_adb", run)

    with pytest.raises(subprocess.CalledProcessError):
        scan_sessions.collect_scan_session("adb", exclude_system=True)
    assert calls[-1] == ("shell", "pm", "list", "packages", "-3")


def test_empty_package_enumeration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    successful = _successful_runner(calls)

    def run(adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        if args[:5] == ("shell", "pm", "list", "packages", "-3"):
            calls.append(args)
            return _completed("")
        return successful(adb, *args, timeout=timeout)

    monkeypatch.setattr(scan_sessions, "run_adb", run)

    with pytest.raises(RuntimeError, match="no Android packages"):
        scan_sessions.collect_scan_session("adb", exclude_system=True)


def test_short_serial_is_fully_masked() -> None:
    summary = scan_sessions.device_summary_from_properties({}, "abc")
    assert summary["serial_masked"] == "•••"
    assert summary["device_id"] != "abc"
