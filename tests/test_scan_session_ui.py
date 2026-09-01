from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.scan_session as scan_sessions
import playstore_app_audit.services.state as state
import playstore_app_audit.services.store_locale as store_locale
import playstore_app_audit.ui.audit_window as audit_ui
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.main_window import MainWindow


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
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()
    store_locale.set_active_device_store_locale(None)


def _session(
    name: str,
    device_id: str,
    package: str,
    *,
    locale: store_locale.StoreLocale | None = None,
) -> scan_sessions.ScanSession:
    return scan_sessions.ScanSession(
        session_id=f"session-{name}",
        captured_at=datetime(2026, 9, 2, 10, 0, tzinfo=UTC),
        source_id=f"device:{device_id}:session-{name}",
        source_kind="device",
        device_id=device_id,
        serial_masked=f"••••{name[-4:]}",
        manufacturer="Google",
        model=name,
        android_version="16",
        android_api="36",
        security_patch="2026-08-05",
        locale=locale,
        packages=(package,),
        package_metadata=(
            scan_sessions.CompactPackageMetadata(
                package_name=package,
                installed_version_code="100",
                installer_package="com.android.vending",
                installer_source="Google Play (com.android.vending)",
                installer_category="google_play",
                is_enabled=True,
                is_system=False,
            ),
        ),
        system_packages=frozenset(),
        system_scope="third_party_only",
        locale_fallback_attempted=False,
    )


def _select_session(window: MainWindow, session: scan_sessions.ScanSession) -> None:
    request_id = window._begin_phone_scan_request()
    window._on_adb_scan_done(session, request_id)


def test_completed_phone_scan_selects_one_coherent_session(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    locale = store_locale.StoreLocale("it", "ch", "it-CH", "test")
    session = _session("Pixel A", "device-a", "com.example.a", locale=locale)
    for owner, name in (
        (window, "_find_adb"),
        (window, "_get_authorised_adb"),
        (device_insights, "collect_device_summary"),
        (store_locale, "detect_android_store_locale"),
    ):
        monkeypatch.setattr(
            owner,
            name,
            lambda *_args, _name=name, **_kwargs: pytest.fail(
                f"Scan completion unexpectedly recollected {_name}"
            ),
        )

    _select_session(window, session)

    assert window._scan_session is session
    assert window.source_mode == "device"
    assert window.device_apps_all == [
        {"app_name": "com.example.a", "package_name": "com.example.a"}
    ]
    assert window._device_summary == session.device_summary()
    assert window._device_store_locale is locale
    assert store_locale.active_device_store_locale() is locale
    assert "Google Pixel A • Android 16 (API 36)" in window.source_label.text()


def test_phone_a_to_phone_b_replaces_session_without_metadata_bleed(
    window: MainWindow,
) -> None:
    phone_a = _session(
        "Pixel A",
        "device-a",
        "com.example.a",
        locale=store_locale.StoreLocale("it", "it", "it-IT", "test-a"),
    )
    phone_b = _session(
        "Pixel B",
        "device-b",
        "com.example.b",
        locale=store_locale.StoreLocale("de", "de", "de-DE", "test-b"),
    )

    _select_session(window, phone_a)
    _select_session(window, phone_b)

    assert window._scan_session is phone_b
    assert window._device_summary["device_id"] == "device-b"
    assert window._device_store_locale is phone_b.locale
    assert window.device_apps_all[0]["package_name"] == "com.example.b"
    assert "Pixel A" not in window.source_label.text()


def test_phone_to_file_clears_device_session_and_locale(
    window: MainWindow, tmp_path: Path
) -> None:
    _select_session(
        window,
        _session(
            "Pixel A",
            "device-a",
            "com.example.a",
            locale=store_locale.StoreLocale("it", "it", "it-IT", "test"),
        ),
    )
    source = tmp_path / "apps.txt"
    source.write_text("com.example.file\n", encoding="utf-8")

    window._load_input_file(str(source))

    assert window.source_mode == "file"
    assert window._scan_session is None
    assert window._device_summary == {}
    assert window._device_store_locale is None
    assert store_locale.active_device_store_locale() is None
    assert window.device_apps_all == []
    assert window.file_apps[0]["package_name"] == "com.example.file"


def test_file_to_phone_selects_new_device_session(window: MainWindow, tmp_path: Path) -> None:
    source = tmp_path / "apps.txt"
    source.write_text("com.example.file\n", encoding="utf-8")
    window._load_input_file(str(source))
    phone = _session("Pixel B", "device-b", "com.example.phone")

    _select_session(window, phone)

    assert window.source_mode == "device"
    assert window._scan_session is phone
    assert window.file_apps == []
    assert window.device_apps_all[0]["package_name"] == "com.example.phone"


def test_stale_phone_completion_cannot_replace_newer_phone_request(
    window: MainWindow,
) -> None:
    phone_a = _session("Pixel A", "device-a", "com.example.a")
    phone_b = _session("Pixel B", "device-b", "com.example.b")
    request_a = window._begin_phone_scan_request()
    request_b = window._begin_phone_scan_request()

    window._on_adb_scan_done(phone_a, request_a)
    assert window._scan_session is None
    window._on_adb_scan_done(phone_b, request_b)

    assert window._scan_session is phone_b
    assert window.device_apps_all[0]["package_name"] == "com.example.b"


def test_stale_adb_discovery_cannot_start_a_newer_scan(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_request = window._begin_phone_scan_request()
    current_request = window._begin_phone_scan_request()
    starts: list[tuple[str, int]] = []
    monkeypatch.setattr(
        window,
        "_start_adb_scan",
        lambda adb, request_id: starts.append((adb, request_id)),
    )

    window._on_adb_discovery_done("adb", stale_request)
    window._on_adb_discovery_done("adb", current_request)

    assert starts == [("adb", current_request)]


def test_session_collection_is_scheduled_off_the_ui_thread(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_started = False
    worker_ran = False
    request_id = window._begin_phone_scan_request()

    def worker(_adb: str, _exclude_system: bool, _request_id: int) -> None:
        nonlocal worker_ran
        worker_ran = True

    monkeypatch.setattr(window, "_scan_phone_worker_branch", worker)

    class DeferredThread:
        def __init__(
            self, *, target: object, args: tuple[str, bool, int], daemon: bool
        ) -> None:
            assert target is worker
            assert args == ("adb", True, request_id)
            assert daemon

        def start(self) -> None:
            nonlocal thread_started
            thread_started = True

    monkeypatch.setattr(audit_ui.threading, "Thread", DeferredThread)

    window._start_adb_scan("adb", request_id)

    assert thread_started
    assert not worker_ran


def test_failed_replacement_scan_preserves_previous_complete_session(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    phone_a = _session("Pixel A", "device-a", "com.example.a")
    _select_session(window, phone_a)
    monkeypatch.setattr(
        "playstore_app_audit.ui.audit_window.QMessageBox.critical",
        lambda *_args: None,
    )
    replacement_request = window._begin_phone_scan_request()

    window._on_adb_scan_failed(replacement_request, "replacement failed")

    assert window._scan_session is phone_a
    assert window.source_mode == "device"
    assert window.device_apps_all[0]["package_name"] == "com.example.a"


def test_stale_phone_completion_cannot_replace_file_source(
    window: MainWindow, tmp_path: Path
) -> None:
    stale = _session("Pixel A", "device-a", "com.example.a")
    request_id = window._begin_phone_scan_request()
    window._set_busy(True)
    source = tmp_path / "apps.txt"
    source.write_text("com.example.file\n", encoding="utf-8")
    window._load_input_file(str(source))

    window._on_adb_scan_done(stale, request_id)

    assert window.source_mode == "file"
    assert window._scan_session is None
    assert not window._source_operation_active
    assert window.file_apps[0]["package_name"] == "com.example.file"


def test_failed_scan_does_not_select_partial_session(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "playstore_app_audit.ui.audit_window.QMessageBox.critical",
        lambda _parent, title, message: messages.append((title, message)),
    )
    request_id = window._begin_phone_scan_request()

    window._on_adb_scan_failed(request_id, "ADB connection error:\n\nsummary failed")

    assert window._scan_session is None
    assert window.source_mode is None
    assert window._active_scan_request_id is None
    assert messages == [
        ("Operation failed", "ADB connection error:\n\nsummary failed")
    ]


def test_stale_scan_failure_does_not_overwrite_newer_source(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "playstore_app_audit.ui.audit_window.QMessageBox.critical",
        lambda _parent, title, message: messages.append((title, message)),
    )
    request_id = window._begin_phone_scan_request()
    source = tmp_path / "apps.txt"
    source.write_text("com.example.file\n", encoding="utf-8")
    window._load_input_file(str(source))

    window._on_adb_scan_failed(request_id, "stale failure")

    assert window.source_mode == "file"
    assert window.status_label.text() == "File ready. Run the Play Store audit."
    assert messages == []
