from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.scan_session as scan_sessions
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.device_window as device_ui
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.ui.main_window import MainWindow


def _completed(stdout: str) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout)


def _compact(
    package: str = "com.example.app",
    *,
    version_code: str | None = "101",
    installer_package: str | None = "com.android.vending",
    enabled: bool | None = True,
    system: bool = False,
) -> scan_sessions.CompactPackageMetadata:
    if installer_package is None:
        installer_label = None
        installer_category = None
    elif installer_package == "com.android.vending":
        installer_label = "Google Play (com.android.vending)"
        installer_category = "google_play"
    elif installer_package == "com.sec.android.app.samsungapps":
        installer_label = "Galaxy Store (com.sec.android.app.samsungapps)"
        installer_category = "alternative_store"
    else:
        installer_label = "Unknown / preinstalled"
        installer_category = "unknown_or_preinstalled"
    return scan_sessions.CompactPackageMetadata(
        package_name=package,
        installed_version_code=version_code,
        installer_package=installer_package,
        installer_source=installer_label,
        installer_category=installer_category,
        is_enabled=enabled,
        is_system=system,
    )


def _session(
    *metadata: scan_sessions.CompactPackageMetadata,
    name: str = "Pixel",
    device_id: str = "device-a",
) -> scan_sessions.ScanSession:
    packages = tuple(item.package_name for item in metadata)
    system_packages = frozenset(item.package_name for item in metadata if item.is_system)
    return scan_sessions.ScanSession(
        session_id=f"session-{device_id}",
        captured_at=datetime(2026, 9, 2, 10, 30, tzinfo=UTC),
        source_id=f"device:{device_id}:session-{device_id}",
        source_kind="device",
        device_id=device_id,
        serial_masked="••••1234",
        manufacturer="Google",
        model=name,
        android_version="16",
        android_api="36",
        security_patch="2026-08-05",
        locale=None,
        packages=packages,
        package_metadata=tuple(metadata),
        system_packages=system_packages,
        system_scope="all_packages" if system_packages else "third_party_only",
        locale_fallback_attempted=False,
    )


def _store_row(package: str = "com.example.app") -> dict[str, object]:
    return {
        "app_name": "Example",
        "package_name": package,
        "play_status": "available",
        "play_title": "Example",
        "play_last_update": "2026-08-01",
        "play_version": "1.0",
    }


def test_compact_model_is_immutable_and_contains_no_rich_fields() -> None:
    item = _compact()

    with pytest.raises(FrozenInstanceError):
        item.installed_version_code = "202"  # type: ignore[misc]

    field_names = {field.name for field in fields(item)}
    assert field_names == {
        "package_name",
        "installed_version_code",
        "installer_package",
        "installer_source",
        "installer_category",
        "is_enabled",
        "is_system",
    }
    assert "installed_version" not in field_names
    assert "target_sdk" not in field_names
    assert "min_sdk" not in field_names


def test_compact_parser_accepts_android_output_order_and_separator_variants() -> None:
    parsed = scan_sessions._parse_compact_package_rows(
        "package:one installer=com.android.vending versionCode:101\n"
        "package:two versionCode=202  installer=null\n"
        "ignored diagnostic line\n"
    )

    assert parsed == {
        "one": ("101", "com.android.vending"),
        "two": ("202", "null"),
    }


def test_unsupported_versioncode_flag_uses_installer_only_aggregate_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(_adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del timeout
        calls.append(args)
        if args == ("devices",):
            return _completed("List of devices attached\nprivate-serial\tdevice\n")
        if args == ("shell", "getprop"):
            return _completed("[persist.sys.locale]: [en-US]\n")
        if args[-2:] == ("-i", "--show-versioncode"):
            raise subprocess.CalledProcessError(1, ["adb", *args])
        if args[-1:] == ("-i",):
            return _completed("package:com.example.app installer=com.android.vending\n")
        if args[-1:] == ("-d",):
            return _completed("")
        raise AssertionError(args)

    monkeypatch.setattr(scan_sessions, "run_adb", run)

    session = scan_sessions.collect_scan_session("adb", exclude_system=True)

    item = session.package_metadata[0]
    assert item.installed_version_code is None
    assert item.installer_package == "com.android.vending"
    assert item.installer_category == "google_play"
    assert item.is_enabled is True
    assert calls[-3:] == [
        ("shell", "pm", "list", "packages", "-3", "-i", "--show-versioncode"),
        ("shell", "pm", "list", "packages", "-3", "-i"),
        ("shell", "pm", "list", "packages", "-3", "-d"),
    ]


def test_unsupported_compact_queries_preserve_plain_enumeration_and_unknown_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(_adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del timeout
        calls.append(args)
        if args == ("devices",):
            return _completed("List of devices attached\nprivate-serial\tdevice\n")
        if args == ("shell", "getprop"):
            return _completed("[persist.sys.locale]: [en-US]\n")
        if args[-2:] == ("-i", "--show-versioncode") or args[-1:] == ("-i",):
            raise subprocess.CalledProcessError(1, ["adb", *args])
        if args == ("shell", "pm", "list", "packages", "-3"):
            return _completed("package:com.example.app\n")
        if args[-1:] == ("-d",):
            raise subprocess.CalledProcessError(1, ["adb", *args])
        raise AssertionError(args)

    monkeypatch.setattr(scan_sessions, "run_adb", run)

    session = scan_sessions.collect_scan_session("adb", exclude_system=True)

    assert session.packages == ("com.example.app",)
    item = session.package_metadata[0]
    assert item.installed_version_code is None
    assert item.installer_package is None
    assert item.installer_source is None
    assert item.installer_category is None
    assert item.is_enabled is None
    assert item.is_system is False
    assert not any("dumpsys" in args for args in calls)


def test_scan_collection_never_invokes_full_metadata_collector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(_adb: str, *args: str, timeout: int = 30) -> SimpleNamespace:
        del timeout
        calls.append(args)
        if args == ("devices",):
            return _completed("List of devices attached\nprivate-serial\tdevice\n")
        if args == ("shell", "getprop"):
            return _completed("[persist.sys.locale]: [en-US]\n")
        if args[-2:] == ("-i", "--show-versioncode"):
            return _completed(
                "package:com.example.app versionCode:101 installer=com.android.vending\n"
            )
        if args[-1:] == ("-d",):
            return _completed("")
        raise AssertionError(args)

    monkeypatch.setattr(scan_sessions, "run_adb", run)
    monkeypatch.setattr(
        device_insights,
        "collect_device_metadata_v9",
        lambda *_args, **_kwargs: pytest.fail("full collector ran during Scan Phone"),
    )

    session = scan_sessions.collect_scan_session("adb", exclude_system=True)

    assert session.package_count == 1
    assert not any("dumpsys" in args for args in calls)


def test_authorised_device_match_uses_only_hashed_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_id, _masked = scan_sessions._masked_device_identity("private-serial")
    monkeypatch.setattr(
        scan_sessions,
        "run_adb",
        lambda *_args, **_kwargs: _completed(
            "List of devices attached\nprivate-serial\tdevice\n"
        ),
    )

    assert scan_sessions.authorised_device_matches("adb", expected_id)
    assert not scan_sessions.authorised_device_matches("adb", "different-device")


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": True,
        "compare_previous": False,
        "collect_device_metadata": True,
        "inventory_history_enabled": False,
        "alternative_distribution": {"fdroid_main": {"enabled": False}},
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(compact_ui.QMessageBox, "critical", lambda *_args, **_kwargs: None)
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def _select_session(window: MainWindow, session: scan_sessions.ScanSession) -> None:
    request_id = window._begin_phone_scan_request()
    window._on_adb_scan_done(session, request_id)


def _run_worker(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    session: scan_sessions.ScanSession,
) -> None:
    row = _store_row()

    def audit(
        _apps,
        _config,
        progress,
        *,
        pause_event,
        cancel_event,
        row_completed_callback,
    ):
        del pause_event, cancel_event
        row_completed_callback(0, row)
        progress(1, 1, "com.example.app")
        return [row]

    monkeypatch.setattr(device_metadata, "audit_apps_v8", audit)
    window._audit_session = 41
    window._audit_requested_outcome = None
    window._audit_cancel_event = threading.Event()
    window._audit_pause_event = threading.Event()
    window._audit_pause_event.set()
    window._set_audit_state(AuditRunState.RUNNING)
    apps = [{"app_name": "Example", "package_name": "com.example.app"}]

    device_ui.DeviceWindow._controlled_audit_worker(
        window,
        apps,
        apps,
        {},
        AuditConfig(country="us", language="en", max_workers=1),
        41,
        window._audit_pause_event,
        window._audit_cancel_event,
        False,
        session,
    )
    app.processEvents()
    app.processEvents()


def test_disconnected_run_keeps_t1_compact_values_and_store_audit(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(_compact())
    _select_session(window, session)
    monkeypatch.setattr(window, "_get_matching_scan_session_adb", lambda _session: None)
    monkeypatch.setattr(
        window,
        "_collect_device_metadata",
        lambda *_args: pytest.fail("T2 collector ran for a disconnected phone"),
    )

    _run_worker(window, app, monkeypatch, session)

    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert len(window.current_rows) == 1
    row = window.current_rows[0]
    assert row["play_status"] == "available"
    assert row["installed_version_code"] == "101"
    assert row["installer_package"] == "com.android.vending"
    assert row["installer_source"] == "Google Play (com.android.vending)"
    assert row["installer_category"] == "google_play"
    assert row["app_enabled"] == "Enabled"
    assert row["is_system"] is False
    assert row["installed_version"] == ""
    assert row["target_sdk"] == ""
    assert row["min_sdk"] == ""
    assert row["compatibility_status"] == ""
    assert row["version_comparison"] == "Unknown"


def test_connected_run_keeps_t1_inventory_fields_and_populates_rich_t2(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(_compact())
    _select_session(window, session)
    monkeypatch.setattr(window, "_get_matching_scan_session_adb", lambda _session: "adb")
    monkeypatch.setattr(
        window,
        "_collect_device_metadata",
        lambda *_args: {
            "com.example.app": {
                "installed_version": "1.0",
                "installed_version_code": "999",
                "installer_source": "Galaxy Store (com.sec.android.app.samsungapps)",
                "installer_package": "com.sec.android.app.samsungapps",
                "installer_category": "alternative_store",
                "target_sdk": "35",
                "min_sdk": "26",
                "first_install_time": "2026-01-01",
                "last_local_update": "2026-08-01",
                "app_enabled": "Disabled",
                "compatibility_status": "Modern",
                "sensitive_permissions_count": "0",
                "sensitive_permissions": "",
            }
        },
    )

    _run_worker(window, app, monkeypatch, session)

    row = window.current_rows[0]
    assert row["installed_version"] == "1.0"
    assert row["target_sdk"] == "35"
    assert row["min_sdk"] == "26"
    assert row["compatibility_status"] == "Modern"
    assert row["version_comparison"] == "Match"
    assert row["installed_version_code"] == "101"
    assert row["installer_package"] == "com.android.vending"
    assert row["app_enabled"] == "Enabled"


def test_inventory_uses_t1_fields_not_rich_t2_hybrid(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    baseline_display = [{"package_name": "com.example.app"}]
    baseline_t1 = [
        {
            "package_name": "com.example.app",
            "installed_version_code": "101",
            "installer_package": "com.android.vending",
            "installer_source": "Google Play (com.android.vending)",
            "app_enabled": "Enabled",
            "is_system": False,
        }
    ]
    device_insights.annotate_inventory_changes_and_save(
        baseline_display, {"device_id": "phone-a"}, baseline_t1
    )
    display = [
        {
            "package_name": "com.example.app",
            "installed_version": "different-rich-name",
            "installed_version_code": "999",
            "installer_package": "com.sec.android.app.samsungapps",
            "installer_source": "Galaxy Store (com.sec.android.app.samsungapps)",
            "app_enabled": "Disabled",
        }
    ]

    result = device_insights.annotate_inventory_changes_and_save(
        display, {"device_id": "phone-a"}, baseline_t1
    )

    assert display[0]["device_change"] == "Same"
    assert result["counts"]["same"] == 1


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"installer_package": "com.sec.android.app.samsungapps", "installer_source": "Galaxy Store (com.sec.android.app.samsungapps)"}, "Installer changed"),
        ({"installed_version_code": "202"}, "Version changed"),
        ({"app_enabled": "Disabled"}, "State changed"),
        ({"installer_package": "", "installer_source": ""}, "Same"),
    ],
)
def test_inventory_compact_change_classification(
    tmp_path, monkeypatch: pytest.MonkeyPatch, updates: dict[str, object], expected: str
) -> None:
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    baseline = {
        "package_name": "com.example.app",
        "installed_version_code": "101",
        "installer_package": "com.android.vending",
        "installer_source": "Google Play (com.android.vending)",
        "app_enabled": "Enabled",
        "is_system": False,
    }
    device_insights.annotate_inventory_changes_and_save(
        [{"package_name": "com.example.app"}],
        {"device_id": "phone-a"},
        [dict(baseline)],
    )
    current = dict(baseline)
    current.update(updates)
    display = [{"package_name": "com.example.app"}]

    device_insights.annotate_inventory_changes_and_save(
        display, {"device_id": "phone-a"}, [current]
    )

    assert display[0]["device_change"] == expected


def test_inventory_added_removed_and_system_state_are_from_t1(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    device_insights.annotate_inventory_changes_and_save(
        [{"package_name": "old"}],
        {"device_id": "phone-a"},
        [{"package_name": "old", "installed_version_code": "1", "is_system": False}],
    )
    display = [{"package_name": "new"}]

    result = device_insights.annotate_inventory_changes_and_save(
        display,
        {"device_id": "phone-a"},
        [{"package_name": "new", "installed_version_code": "1", "is_system": True}],
    )

    assert display[0]["device_change"] == "New on device"
    assert result["removed"] == ["old"]
    assert result["counts"]["new"] == 1
    assert result["counts"]["removed"] == 1
    saved = json.loads(device_insights.inventory_path("phone-a").read_text(encoding="utf-8"))
    assert saved["apps"]["new"]["is_system"] is True


def test_successful_promotion_passes_exact_session_t1_inventory(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session(_compact())
    _select_session(window, session)
    window.user_settings["inventory_history_enabled"] = True
    window.current_rows = [
        {
            **_store_row(),
            "installed_version": "rich-name",
            "installed_version_code": "999",
            "installer_source": "rich-t2-installer",
            "app_enabled": "Disabled",
        }
    ]
    captured: list[tuple[list[dict[str, object]], dict[str, object]]] = []

    def promote(_rows, summary, inventory):
        captured.append((inventory, summary))
        return {"had_previous": False}

    monkeypatch.setattr(device_insights, "annotate_inventory_changes_and_save", promote)
    result = AuditRunResult(
        session=1,
        outcome=AuditRunOutcome.SUCCESS,
        rows=list(window.current_rows),
        total_count=1,
        live_completed_count=1,
        metadata={"scan_session": session},
    )

    assert window._promote_successful_audit(result)
    inventory, summary = captured[0]
    assert inventory == scan_sessions.inventory_rows(session)
    assert inventory[0]["installed_version_code"] == "101"
    assert inventory[0]["installer_source"] == "Google Play (com.android.vending)"
    assert inventory[0]["app_enabled"] == "Enabled"
    assert summary["device_id"] == "device-a"

    for outcome in (AuditRunOutcome.STOPPED, AuditRunOutcome.FAILED):
        result.outcome = outcome
        assert not window._promote_successful_audit(result)
    assert len(captured) == 1


def test_scan_selection_alone_never_promotes_inventory(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: pytest.fail("Scan Phone promoted the inventory baseline"),
    )

    _select_session(window, _session(_compact()))

    assert window._scan_session is not None
    assert window.current_rows == []


def test_phone_a_to_phone_b_compact_metadata_isolated(window: MainWindow) -> None:
    phone_a = _session(_compact(version_code="101"), device_id="device-a")
    phone_b = _session(
        _compact(
            package="com.example.app",
            version_code="202",
            installer_package="com.sec.android.app.samsungapps",
            enabled=False,
        ),
        device_id="device-b",
    )

    _select_session(window, phone_a)
    _select_session(window, phone_b)

    assert window._scan_session is phone_b
    assert window._scan_session.package_metadata[0].installed_version_code == "202"
    assert window._scan_session.package_metadata[0].installer_category == "alternative_store"
    assert window._scan_session.package_metadata[0].is_enabled is False
