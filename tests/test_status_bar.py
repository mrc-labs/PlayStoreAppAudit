from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QStatusBar

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
def window(
    app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": True,
        "inventory_history_enabled": False,
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "add_recent_source", lambda _path: None)
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def test_status_bar_hosts_the_single_canonical_status_and_progress_widgets(
    window: MainWindow,
) -> None:
    status_bar = window.statusBar()
    root = window.centralWidget().layout()
    action_layout = compact_ui._find_layout_containing(root, window.run_button)

    assert isinstance(status_bar, QStatusBar)
    assert status_bar is window.status_bar
    assert status_bar.objectName() == "OperationalStatusBar"
    assert status_bar.isSizeGripEnabled()
    assert window.status_label.parentWidget() is status_bar
    assert window.progress.parentWidget() is status_bar
    assert status_bar.findChildren(QProgressBar) == [window.progress]
    assert [
        label
        for label in window.findChildren(QLabel)
        if label.accessibleName() == "Operational Status"
    ] == [window.status_label]
    assert window.progress.accessibleName() == "Operation Progress"
    assert window.progress.minimumWidth() == 200
    assert window.progress.maximumWidth() == 200
    assert window.progress.isHidden()
    assert window.status_label.text() == "Ready"

    assert action_layout is not None
    assert action_layout.itemAt(0).widget() is window.run_button
    assert action_layout.itemAt(1).spacerItem() is not None
    assert action_layout.itemAt(2).widget() is window.export_button
    assert action_layout.itemAt(3).widget() is window.clear_button
    assert compact_ui._find_layout_containing(root, window.status_label) is None
    assert compact_ui._find_layout_containing(root, window.progress) is None


def test_source_statuses_and_presentation_guard_use_the_status_bar(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "apps.csv"
    source.write_text("package_name\ncom.example.file\n", encoding="utf-8")

    window._load_input_file(str(source))
    assert window.status_label.text() == "File ready. Run the Play Store audit."
    assert window.progress.isHidden()

    window._set_busy(True)
    window.progress.setRange(0, 0)
    window.status_label.setText("Scanning phone…")
    window._set_presentation_status("Display settings saved")
    assert window.status_label.text() == "Scanning phone…"
    assert not window.progress.isHidden()

    monkeypatch.setattr(window, "_get_authorised_adb", lambda: None)
    monkeypatch.setattr(window, "_find_adb", lambda: None)
    window._on_adb_scan_done(
        [{"app_name": "Phone App", "package_name": "com.example.phone"}],
        set(),
    )
    assert window.status_label.text() == "Phone scan ready. Run the Play Store audit."
    assert window.progress.isHidden()

    window._set_presentation_status("Display settings saved")
    assert window.status_label.text() == "Display settings saved"


class _DormantThread:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def start(self) -> None:
        pass


def _start_dormant_audit(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> int:
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        window,
        "_get_apps_to_audit",
        lambda: (
            [{"app_name": "Audit Example", "package_name": "com.example.audit"}],
            set(),
            "test source",
        ),
    )
    monkeypatch.setattr(compact_ui.threading, "Thread", _DormantThread)
    monkeypatch.setattr(window, "_load_fresh_cache", lambda *args: {})
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    window._start_audit()
    assert warnings == []
    assert window._audit_active
    assert not window.progress.isHidden()
    assert window.status_label.text() == "Audit running • 0 cached • 1 live"
    return window._audit_session


def test_audit_lifecycle_progress_and_status_do_not_leave_stale_visible_state(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "audit.csv"
    source.write_text("package_name\ncom.example.audit\n", encoding="utf-8")
    window._load_input_file(str(source))

    session = _start_dormant_audit(window, monkeypatch)
    window._on_controlled_progress(session, 1, 1, "com.example.audit")
    assert window.progress.value() == 1
    assert window.status_label.text() == (
        "Checking Play Store • 1/1 live • 0 cached • com.example.audit"
    )

    window._toggle_pause()
    assert window.status_label.text() == "Paused • 1/1 completed"
    assert not window.progress.isHidden()
    window._set_presentation_status("Table layout reset to defaults")
    assert window.status_label.text() == "Paused • 1/1 completed"

    window._toggle_pause()
    assert window.status_label.text() == "Resumed • 1/1 completed"
    assert not window.progress.isHidden()

    window._clear_results()
    assert not window._audit_active
    assert window.status_label.text() == "Ready"
    assert window.progress.value() == 0
    assert window.progress.isHidden()

    completed_session = _start_dormant_audit(window, monkeypatch)
    row = {
        "package_name": "com.example.audit",
        "play_status": "available",
        "play_title": "Audit Example",
        "play_last_update": "2026-08-20",
    }
    window._on_controlled_done((completed_session, [row], "", 0, 1))
    assert window.status_label.text() == "Finalizing audit results • 0 cached • 1 live"
    assert not window.progress.isHidden()
    assert window.progress.minimum() == 0
    assert window.progress.maximum() == 0

    app.processEvents()
    assert window.status_label.text() == "Audit completed • 1 live"
    assert window.progress.value() == 1
    assert window.progress.isHidden()

    second_session = _start_dormant_audit(window, monkeypatch)
    window._on_controlled_progress(second_session, 0, 1, "com.example.audit")
    monkeypatch.setattr(compact_ui.QMessageBox, "critical", lambda *args: None)
    window._on_controlled_done((second_session, None, "network unavailable", 0, 0))
    assert window.status_label.text() == "Audit failed"
    assert not window._audit_active
    assert window.progress.isHidden()


def test_details_responsive_modes_do_not_disturb_status_bar_hosting(
    window: MainWindow,
) -> None:
    status_bar = window.status_bar
    status_label = window.status_label
    progress = window.progress

    for width, mode in ((500, "narrow"), (800, "wide"), (1180, "extra-wide"), (1079, "wide")):
        window.details_panel._update_adaptive_layout(width)
        assert window.details_panel.content_layout_mode() == mode
        assert window.status_bar is status_bar
        assert window.status_label is status_label
        assert window.progress is progress
        assert status_label.parentWidget() is status_bar
        assert progress.parentWidget() is status_bar
