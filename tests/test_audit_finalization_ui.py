from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
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


def test_live_progress_distinguishes_cached_and_live_work(window: MainWindow) -> None:
    window._audit_session = 7
    window._audit_active = True
    window._audit_paused = False
    window._audit_cached_count = 2
    window._audit_live_count = 3

    window._on_controlled_progress(7, 3, 5, "com.example.app")

    assert window.progress.value() == 3
    assert window.status_label.text() == (
        "Checking Play Store • 1/3 live • 2 cached • com.example.app"
    )


def test_success_is_visibly_finalizing_before_rows_are_installed(
    window: MainWindow, app: QApplication
) -> None:
    window._audit_session = 9
    window._audit_active = True
    window._audit_paused = False
    window._audit_pause_event.set()
    window.source_mode = "file"
    window.file_apps = [{"package_name": "com.example.current", "app_name": "Example"}]
    window.current_system_packages = set()
    window.current_rows = []
    window.model.set_rows([])

    row = {
        "package_name": "com.example.current",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "play_title": "Example",
    }
    payload = (9, [row], "", 2, 1)

    window._on_controlled_done(payload)

    assert window.status_label.text() == "Finalizing audit results • 2 cached • 1 live"
    assert window.progress.minimum() == 0
    assert window.progress.maximum() == 0
    assert window.run_button.text() == "Finalizing…"
    assert not window.run_button.isEnabled()
    assert window.model.rowCount() == 0

    app.processEvents()

    assert window.model.rowCount() == 1
    assert window.current_rows[0]["package_name"] == "com.example.current"
    assert window.status_label.text() == "Audit completed • 2 cached • 1 live"
    assert window.run_button.text() == "Run Play Store Audit"
    assert window.run_button.isEnabled()
    assert window.progress.maximum() == 1
    assert window.progress.value() == 1
