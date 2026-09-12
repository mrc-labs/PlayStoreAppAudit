from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.main_window as main_ui
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult
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


def test_successful_audit_logs_stage_timings_without_package_names(
    window: MainWindow, app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    samples = iter((103.0, 104.0))
    logged: list[str] = []
    monkeypatch.setattr(main_ui.time, "perf_counter", lambda: next(samples))
    monkeypatch.setattr(device_insights, "log_event", logged.append)

    window.source_mode = "file"
    window._audit_session = 12
    window._audit_active = True
    window._audit_paused = False
    window._audit_started_at = 100.0
    window._audit_pause_event.set()
    window.current_system_packages = set()
    window.current_rows = []
    window.model.set_rows([])
    window._progressive_payload_count = 5
    window._progressive_refresh_count = 2

    row = {
        "package_name": "com.example.privatepackage",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "play_title": "Example",
    }
    result = AuditRunResult(
        session=12,
        outcome=AuditRunOutcome.SUCCESS,
        rows=[row],
        cached_count=2,
        live_completed_count=1,
        total_count=1,
        metadata={
            "physical_count": 1,
            "package_count": 1,
            "parse_ms": 27000,
            "store_ms": 900,
        },
    )
    window._on_controlled_done(result)

    app.processEvents()

    assert logged == [
        "audit_performance source=file outcome=success physical=1 packages=1 "
        "parse_ms=27000 store_ms=900 total_ms=4000 cached=2 live=1 "
        "progressive_payloads=5 progressive_refreshes=2"
    ]
    assert "com.example.privatepackage" not in logged[0]
    assert window._audit_started_at is None
    assert window._audit_pre_finalize_seconds is None


def test_failed_audit_logs_pre_finalize_timing(
    window: MainWindow, app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    logged: list[str] = []
    monkeypatch.setattr(main_ui.time, "perf_counter", lambda: 203.5)
    monkeypatch.setattr(device_insights, "log_event", logged.append)
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "critical",
        lambda *_args, **_kwargs: compact_ui.QMessageBox.StandardButton.Ok,
    )

    window.source_mode = "device"
    window._audit_session = 13
    window._audit_active = True
    window._audit_started_at = 200.0

    window._on_controlled_done((13, None, "network failure", 0, 0))
    app.processEvents()

    assert logged == [
        "audit_performance source=device outcome=failed physical=0 packages=0 "
        "parse_ms=0 store_ms=0 total_ms=3500 cached=0 live=0 "
        "progressive_payloads=0 progressive_refreshes=0"
    ]
    assert window._audit_started_at is None
    assert window._audit_pre_finalize_seconds is None
