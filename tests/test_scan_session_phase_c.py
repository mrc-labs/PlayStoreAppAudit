from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import test_scan_session_phase_b as phase_b
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QPushButton

from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult
from playstore_app_audit.services import (
    audit_profiles,
    device_insights,
    device_metadata,
    performance_diagnostics,
    state,
)
from playstore_app_audit.services import (
    scan_session as scans,
)
from playstore_app_audit.ui.main_window import MainWindow

KEY = "collect_full_device_metadata_on_scan"
PACKAGE = "com.example.app"
SERIAL = "phase-c-test-device-1234"
DUMP = f"""Packages:
  Package [{PACKAGE}] (abc):
    versionCode=999 minSdk=26 targetSdk=35
    versionName=1.0
    firstInstallTime=2026-01-01 10:00:00
    lastUpdateTime=2026-08-01 11:00:00
    requested permissions:
      android.permission.CAMERA

Queries:
  ignored
"""
app = phase_b.app


@pytest.fixture
def local_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(state, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def window(app: QApplication, local_settings: Path) -> MainWindow:
    state.save_settings({
        "view_preset": "Basic", "inventory_history_enabled": False,
        "alternative_distribution": {"fdroid_main": {"enabled": False}},
    })
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


class FakePhone:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.serial = SERIAL
        self.dump = DUMP
        self.fail_full = False
        self.full_started: threading.Event | None = None
        self.full_release: threading.Event | None = None
        self.cancel_on_dump: threading.Event | None = None

    def run(self, adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del adb, timeout
        self.calls.append(args)
        if args[:1] == ("-s",):
            if not self.serial or args[1] != self.serial:
                raise RuntimeError("Pinned device is unavailable")
            args = args[2:]
        if args == ("devices",):
            return SimpleNamespace(stdout="List of devices attached\n" + (
                f"{self.serial}\tdevice\n" if self.serial else ""
            ))
        if args == ("shell", "getprop"):
            output = (
                "[ro.product.manufacturer]: [Google]\n[ro.product.model]: [Pixel]\n"
                "[ro.build.version.sdk]: [36]\n[persist.sys.locale]: [en-US]\n"
            )
        elif args[:4] == ("shell", "pm", "list", "packages"):
            output = "" if "-d" in args or "-s" in args else (
                f"package:{PACKAGE} installer=com.android.vending versionCode:101\n"
            )
        elif args[:3] == ("shell", "dumpsys", "package"):
            if self.full_started is not None:
                self.full_started.set()
            if self.full_release is not None:
                assert self.full_release.wait(5), "Test did not release the full collector"
            if self.cancel_on_dump is not None:
                self.cancel_on_dump.set()
            if self.fail_full:
                raise RuntimeError("Full metadata unavailable")
            output = self.dump
        else:
            raise AssertionError(f"Unexpected fake-device command: {args}")
        return SimpleNamespace(stdout=output)


@pytest.fixture
def phone(monkeypatch: pytest.MonkeyPatch, local_settings: Path) -> FakePhone:
    fake = FakePhone()
    monkeypatch.setattr(scans, "run_adb", fake.run)
    monkeypatch.setattr(device_insights, "_run", lambda adb, args, timeout=30: fake.run(adb, *args, timeout=timeout).stdout)
    return fake


def full_scan() -> scans.ScanSession:
    return scans.collect_scan_session("adb", exclude_system=True, collect_full_metadata=True)


@pytest.mark.parametrize("value", [None, False, True, "true", "false", 1, 0, [], {}, "invalid"])
def test_setting_load_save_is_strict_boolean(local_settings: Path, value: object) -> None:
    state.settings_path().write_text(json.dumps({KEY: value}), encoding="utf-8")
    assert state.load_settings()[KEY] is (value is True)
    saved = state.save_settings({KEY: value})
    assert saved[KEY] is (value is True)
    assert json.loads(state.settings_path().read_text(encoding="utf-8"))[KEY] is (value is True)


def test_fresh_missing_and_restart_settings(local_settings: Path) -> None:
    assert state.DEFAULT_SETTINGS[KEY] is False
    assert state.load_settings()[KEY] is False
    state.settings_path().write_text('{"store_language": "it"}', encoding="utf-8")
    assert state.load_settings()[KEY] is False
    for enabled in (True, False, True, False):
        state.save_settings({KEY: enabled})
        assert state.load_settings()[KEY] is enabled


def test_native_settings_toggle_reset_and_cancel(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    for initial, selected, accept in ((False, True, True), (True, False, False), (True, False, True)):
        def edit(
            dialog: QDialog, initial: bool = initial,
            selected: bool = selected, accept: bool = accept,
        ) -> int:
            check = dialog.findChild(QCheckBox, "CollectFullDeviceMetadataOnScanCheck")
            assert check is not None and check.isChecked() is initial
            assert check.text() == "Collect full device metadata during Scan Phone"
            assert check.parentWidget().objectName() == "DeviceSettingsPage"
            assert "significantly increase scan time" in check.toolTip()
            assert "dumpsys" not in check.toolTip()
            check.setChecked(selected)
            return QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", edit)
        window._show_advanced_settings()
        assert state.load_settings()[KEY] is (selected if accept else initial)

    state.save_settings({KEY: True})

    def reset(dialog: QDialog) -> int:
        next(button for button in dialog.findChildren(QPushButton) if button.text() == "Reset All to Defaults").click()
        assert not dialog.findChild(QCheckBox, "CollectFullDeviceMetadataOnScanCheck").isChecked()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", reset)
    window._show_advanced_settings()
    assert state.load_settings()[KEY] is True


@pytest.mark.parametrize("enabled", [False, True])
def test_presets_do_not_capture_or_apply_scan_preference(local_settings: Path, enabled: bool) -> None:
    settings = {KEY: enabled}
    profile = audit_profiles.capture_profile(settings, "us", source_mode="device")
    assert KEY not in profile["settings"]
    profile["settings"][KEY] = not enabled
    _country, _source, merged = audit_profiles.apply_profile_to_settings(profile, settings)
    assert merged[KEY] is enabled


def test_standard_never_calls_full_collector(phone: FakePhone, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(device_insights, "collect_device_metadata_v9", lambda *args, **kwargs: pytest.fail("Standard invoked full collector"))
    session = scans.collect_scan_session("adb", exclude_system=True)
    assert session.full_metadata_status is scans.FullMetadataStatus.NOT_REQUESTED
    assert session.full_metadata == ()
    assert session.full_metadata_captured_at is None
    assert len(phone.calls) == 4  # discovery/version is outside collect_scan_session
    assert not any("dumpsys" in command for command in phone.calls)


@pytest.mark.parametrize("permissions", [False, True])
def test_complete_full_scan_reuses_context_and_keeps_immutable_rich_fields(phone: FakePhone, permissions: bool) -> None:
    state.save_settings({"permissions_audit_enabled": permissions})
    session = full_scan()
    assert session.full_metadata_status is scans.FullMetadataStatus.COMPLETE
    assert session.full_metadata_captured_at >= session.captured_at
    assert session.full_metadata_includes_permissions is permissions
    info = session.full_metadata_by_package()[PACKAGE]
    assert info["installed_version"] == "1.0"
    assert info["target_sdk"] == "35" and info["min_sdk"] == "26"
    assert info["compatibility_status"] == "Modern"
    assert info["sensitive_permissions"] == ("Camera" if permissions else "")
    assert session.package_metadata[0].installed_version_code == "101"
    assert info["installed_version_code"] == "999"
    assert phone.calls[-2:] == [("devices",), ("-s", SERIAL, "shell", "dumpsys", "package")]
    assert len(phone.calls) == 6
    info["installed_version"] = "mutated"
    assert session.full_metadata_by_package()[PACKAGE]["installed_version"] == "1.0"
    with pytest.raises(FrozenInstanceError):
        session.full_metadata[0].package_name = "other"
    assert SERIAL not in repr(session)
    assert "Packages:" not in repr(session)


@pytest.mark.parametrize("connected", [False, True])
@pytest.mark.parametrize("permissions", [False, True])
def test_run_after_advanced_never_recollects_and_preserves_all_fields(
    window: MainWindow, app: QApplication, phone: FakePhone, monkeypatch: pytest.MonkeyPatch,
    connected: bool, permissions: bool,
) -> None:
    state.save_settings({"permissions_audit_enabled": permissions})
    collector = Mock(wraps=device_insights.collect_device_metadata_v9)
    monkeypatch.setattr(device_insights, "collect_device_metadata_v9", collector)
    session = full_scan()
    assert collector.call_count == 1
    phase_b._select_session(window, session)
    before = len(phone.calls)
    phone.serial = SERIAL if connected else ""
    monkeypatch.setattr(window, "_get_matching_scan_session_adb", lambda *_args: pytest.fail("Run rediscovered device"))
    monkeypatch.setattr(window, "_collect_device_metadata", lambda *_args: pytest.fail("Run repeated full collector"))
    phase_b._run_worker(window, app, monkeypatch, session)
    assert collector.call_count == 1
    assert len(phone.calls) == before
    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    row = window.current_rows[0]
    assert row["installed_version"] == "1.0" and row["installed_version_code"] == "101"
    assert row["installer_package"] == "com.android.vending"
    assert row["installer_source"] == "Google Play (com.android.vending)"
    assert row["app_enabled"] == "Enabled" and row["is_system"] is False
    assert row["target_sdk"] == "35" and row["min_sdk"] == "26"
    assert row["compatibility_status"] == "Modern"
    assert row["first_install_time"] == "2026-01-01 10:00:00"
    assert row["last_local_update"] == "2026-08-01 11:00:00"
    assert row["sensitive_permissions"] == ("Camera" if permissions else "")
    assert row["version_comparison"] == "Match"


@pytest.mark.parametrize("failure", ["exception", "unusable", "partial", "cancelled", "missing_receipt"])
def test_incomplete_full_discards_partial_data(phone: FakePhone, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    cancel = threading.Event()
    if failure == "exception":
        phone.fail_full = True
    elif failure == "unusable":
        phone.dump = "not a package dump"
    elif failure == "partial":
        phone.dump = DUMP.replace(" minSdk=26", "")
    elif failure == "cancelled":
        phone.cancel_on_dump = cancel
    else:
        monkeypatch.setattr(device_insights, "collect_device_metadata_v9", lambda *args, **kwargs: {PACKAGE: {"installed_version": "partial"}})
    session = scans.collect_scan_session("adb", exclude_system=True, collect_full_metadata=True, cancel_event=cancel)
    assert session.full_metadata_status is scans.FullMetadataStatus.INCOMPLETE
    assert session.full_metadata == () and session.full_metadata_captured_at is None
    assert session.full_metadata_by_package() == {}
    assert session.package_metadata[0].installed_version_code == "101"


@pytest.mark.parametrize("connected", [False, True])
def test_failed_full_falls_back_to_standard_run(
    window: MainWindow, app: QApplication, phone: FakePhone, monkeypatch: pytest.MonkeyPatch, connected: bool,
) -> None:
    phone.fail_full = True
    session = full_scan()
    phase_b._select_session(window, session)
    assert "compact metadata" in window.status_label.text()
    assert "could not be captured" in window.status_label.text()
    assert window.run_button.isEnabled()
    phone.fail_full = False
    monkeypatch.setattr(window, "_get_matching_scan_session_adb", lambda *_args: "adb" if connected else None)
    collector = Mock(wraps=window._collect_device_metadata)
    monkeypatch.setattr(window, "_collect_device_metadata", collector)
    phase_b._run_worker(window, app, monkeypatch, session)
    assert collector.call_count == int(connected)
    row = window.current_rows[0]
    assert row["installed_version_code"] == "101"
    assert row["installed_version"] == ("1.0" if connected else "")
    assert row["target_sdk"] == ("35" if connected else "")
    assert row["version_comparison"] == ("Match" if connected else "Unknown")


@pytest.mark.parametrize("replacement", ["", "another-phone"])
def test_context_rejects_unavailable_or_different_phone(phone: FakePhone, replacement: str) -> None:
    session = scans.collect_scan_session("adb", exclude_system=True)
    phone.serial = replacement
    result = scans._capture_full_metadata("adb", session, None)
    assert result.full_metadata_status is scans.FullMetadataStatus.INCOMPLETE
    assert not any("dumpsys" in command for command in phone.calls)


def test_missing_compact_context_falls_back_to_existing_aggregate_probes(phone: FakePhone) -> None:
    session = scans.collect_scan_session("adb", exclude_system=True)
    session = replace(session, android_api="", package_metadata=(replace(session.package_metadata[0], is_enabled=None, installer_package=None),))
    phone.calls.clear()
    full = scans._capture_full_metadata("adb", session, None)
    assert full.full_metadata_status is scans.FullMetadataStatus.COMPLETE
    assert len(phone.calls) == 5
    assert phone.calls[0] == ("devices",)
    assert all(command[:2] == ("-s", SERIAL) for command in phone.calls[1:])


@pytest.mark.parametrize("new_source", ["phone", "file", "close"])
def test_slow_full_scan_cannot_replace_new_source_or_closed_window(
    window: MainWindow, app: QApplication, phone: FakePhone, tmp_path: Path, new_source: str,
) -> None:
    request = window._begin_phone_scan_request()
    old_cancel = window._scan_cancel_event
    phone.full_started = threading.Event()
    phone.full_release = threading.Event()
    thread = threading.Thread(target=window._scan_phone_worker_branch, args=("adb", True, request, True, old_cancel))
    thread.start()
    assert phone.full_started.wait(3)
    ticks: list[bool] = []
    QTimer.singleShot(0, lambda: ticks.append(True))
    app.processEvents()
    assert ticks  # full collection is blocked, Qt still dispatches events
    if new_source == "phone":
        replacement = phase_b._session(phase_b._compact(version_code="202"), device_id="phone-b")
        phase_b._select_session(window, replacement)
    elif new_source == "file":
        source = tmp_path / "source.txt"
        source.write_text("com.example.file\n", encoding="utf-8")
        window._load_input_file(str(source))
    else:
        window.close()
    assert old_cancel.is_set()
    phone.full_release.set()
    thread.join(4)
    assert not thread.is_alive()
    app.processEvents()
    if new_source == "phone":
        assert window._scan_session is replacement
        assert window._scan_session.full_metadata == ()
    else:
        assert window._scan_session is None


def test_full_session_inventory_promotion_and_storage_boundaries(
    window: MainWindow, phone: FakePhone, local_settings: Path,
) -> None:
    state.save_settings({"permissions_audit_enabled": True})
    session = full_scan()
    window.user_settings["inventory_history_enabled"] = True
    phase_b._select_session(window, session)
    assert not device_insights.inventory_path(session.device_id).exists()
    window.current_rows = [{**phase_b._store_row(), **session.full_metadata_by_package()[PACKAGE]}]
    result = AuditRunResult(session=1, outcome=AuditRunOutcome.STOPPED, rows=window.current_rows, total_count=1, metadata={"scan_session": session})
    for outcome in (AuditRunOutcome.STOPPED, AuditRunOutcome.FAILED):
        result.outcome = outcome
        assert not window._promote_successful_audit(result)
        assert not device_insights.inventory_path(session.device_id).exists()
    result.outcome = AuditRunOutcome.SUCCESS
    assert window._promote_successful_audit(result)
    saved = json.loads(device_insights.inventory_path(session.device_id).read_text(encoding="utf-8"))
    assert saved["apps"][PACKAGE]["installed_version_code"] == "101"
    assert saved["apps"][PACKAGE]["installed_version"] == ""
    assert window.current_rows[0]["device_change"] == "New on device"
    assert not state.cache_path().exists()
    assert not state.history_path().exists()
    for path in local_settings.rglob("*"):
        if path.is_file():
            contents = path.read_text(encoding="utf-8")
            assert SERIAL not in contents and "Packages:" not in contents
            assert session.session_id not in contents
            assert "full_metadata" not in contents


def test_production_diagnostics_forwards_full_capture_context(
    phone: FakePhone, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Restore the installed wrappers at test exit, including the install guard.
    monkeypatch.setattr(performance_diagnostics, "_INSTALLED", False)
    monkeypatch.setattr(device_insights, "collect_device_metadata_v9", device_insights.collect_device_metadata_v9)
    monkeypatch.setattr(device_metadata, "audit_apps_v8", device_metadata.audit_apps_v8)
    monkeypatch.setattr(performance_diagnostics.play_store, "fetch_locale", performance_diagnostics.play_store.fetch_locale)
    performance_diagnostics.install_performance_diagnostics()
    session = full_scan()
    assert session.full_metadata_status is scans.FullMetadataStatus.COMPLETE


@pytest.mark.parametrize("enabled", [False, True, False])
def test_ui_scan_option_controls_collector_after_settings_reload(
    window: MainWindow, app: QApplication, phone: FakePhone, monkeypatch: pytest.MonkeyPatch, enabled: bool,
) -> None:
    state.save_settings({KEY: enabled})
    workers: list[threading.Thread] = []
    original_thread = threading.Thread

    def start_thread(**kwargs: object) -> threading.Thread:
        thread = original_thread(**kwargs)
        workers.append(thread)
        return thread

    monkeypatch.setattr(threading, "Thread", start_thread)
    request = window._begin_phone_scan_request()
    window._start_adb_scan("adb", request)
    workers[0].join(4)
    app.processEvents()
    assert window._scan_session is not None
    assert window._scan_session.full_metadata_status is (
        scans.FullMetadataStatus.COMPLETE if enabled else scans.FullMetadataStatus.NOT_REQUESTED
    )
    assert sum("dumpsys" in command for command in phone.calls) == int(enabled)
    assert window.run_button.isEnabled()


def test_standalone_collector_retains_historical_commands(phone: FakePhone) -> None:
    result = device_insights.collect_device_metadata_v9("adb", [PACKAGE])
    assert result[PACKAGE]["installed_version"] == "1.0"
    assert phone.calls == [
        ("shell", "getprop"), ("shell", "pm", "list", "packages", "-d"),
        ("shell", "pm", "list", "packages", "-i"), ("shell", "dumpsys", "package"),
    ]


def test_no_subprocess_needed_for_captured_metadata(phone: FakePhone, monkeypatch: pytest.MonkeyPatch) -> None:
    session = full_scan()
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("Snapshot reuse launched subprocess"))
    assert session.full_metadata_by_package()[PACKAGE]["installed_version"] == "1.0"


@pytest.mark.parametrize("replacement", [SERIAL, "", "different-device"])
def test_standard_t2_authorization_checks_identity_once(
    window: MainWindow, phone: FakePhone, monkeypatch: pytest.MonkeyPatch, replacement: str,
) -> None:
    session = scans.collect_scan_session("adb", exclude_system=True)
    phone.serial = replacement
    phone.calls.clear()
    monkeypatch.setattr(window, "_find_adb", lambda: "adb")
    assert window._get_matching_scan_session_adb(session) == ("adb" if replacement == SERIAL else None)
    assert phone.calls == [("devices",)]


@pytest.mark.parametrize("source", ["phone", "file"])
def test_completed_full_session_cannot_bleed_into_replacement_run(
    window: MainWindow, app: QApplication, phone: FakePhone,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source: str,
) -> None:
    old = full_scan()
    old_request = window._begin_phone_scan_request()
    window._on_adb_scan_done(old, old_request)
    if source == "phone":
        current = phase_b._session(phase_b._compact(version_code="202"), device_id="phone-b")
        phase_b._select_session(window, current)
    else:
        source_file = tmp_path / "replacement.txt"
        source_file.write_text(PACKAGE + "\n", encoding="utf-8")
        window._load_input_file(str(source_file))
        current = None
    # Even a queued complete success from A is rejected by request generation.
    window._on_adb_scan_done(old, old_request)
    assert window._scan_session is current
    monkeypatch.setattr(window, "_get_matching_scan_session_adb", lambda *_args: None)
    phase_b._run_worker(window, app, monkeypatch, current)
    assert window.current_rows[0]["installed_version"] == ""
    assert window.current_rows[0]["target_sdk"] == ""


def test_full_collection_fallback_can_certify_recovered_package(phone: FakePhone, monkeypatch: pytest.MonkeyPatch) -> None:
    original = device_insights._run

    def missing_bulk(adb: str, args: list[str], timeout: int) -> str:
        if args[-3:] == ["shell", "dumpsys", "package"]:
            return "unrecognized OEM bulk output"
        return original(adb, args, timeout)

    monkeypatch.setattr(device_insights, "_run", missing_bulk)
    result = full_scan()
    assert result.full_metadata_status is scans.FullMetadataStatus.COMPLETE
    assert phone.calls[-1] == ("-s", SERIAL, "shell", "dumpsys", "package", PACKAGE)


def test_context_probe_failure_cannot_certify_complete_snapshot(phone: FakePhone, monkeypatch: pytest.MonkeyPatch) -> None:
    session = scans.collect_scan_session("adb", exclude_system=True)
    session = replace(session, android_api="")
    original = device_insights._run

    def failed_getprop(adb: str, args: list[str], timeout: int) -> str:
        if args[-2:] == ["shell", "getprop"]:
            raise RuntimeError("Device context unavailable")
        return original(adb, args, timeout)

    monkeypatch.setattr(device_insights, "_run", failed_getprop)
    result = scans._capture_full_metadata("adb", session, None)
    assert result.full_metadata_status is scans.FullMetadataStatus.INCOMPLETE
    assert result.full_metadata == ()


def test_device_disconnect_during_full_capture_preserves_compact(phone: FakePhone, monkeypatch: pytest.MonkeyPatch) -> None:
    original = device_insights._run

    def disconnected(adb: str, args: list[str], timeout: int) -> str:
        phone.serial = ""
        return original(adb, args, timeout)

    monkeypatch.setattr(device_insights, "_run", disconnected)
    session = full_scan()
    assert session.full_metadata_status is scans.FullMetadataStatus.INCOMPLETE
    assert session.package_metadata[0].installed_version_code == "101"
