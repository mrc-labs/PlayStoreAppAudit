from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QProgressBar, QPushButton, QSizePolicy

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.details_panel as details_ui
from playstore_app_audit.domain.models import AuditRunState
from playstore_app_audit.ui.main_window import MainWindow

REVIEW_SIZES = ((1100, 700), (1500, 900), (1900, 1000))


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _create_window(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    *,
    width: int = 1100,
    height: int = 700,
) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": True,
        "inventory_history_enabled": False,
        "details_panel_position": "auto",
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "add_recent_source", lambda _path: None)
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)
    window = MainWindow()
    window.resize(width, height)
    window.show()
    app.processEvents()
    return window


def _global_rect(widget) -> QRect:
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def _layout_widgets(layout) -> list[object]:
    return [
        widget
        for index in range(layout.count())
        if (widget := layout.itemAt(index).widget()) is not None
    ]


def _header_layouts(window: MainWindow):
    results_layout = window.summary_label.parentWidget().layout()
    operations = compact_ui._find_layout_containing(results_layout, window.summary_label)
    filters = compact_ui._find_layout_containing(results_layout, window.all_chip)
    assert operations is not None
    assert filters is not None
    return operations, filters


def _geometry_snapshot(window: MainWindow) -> dict[str, tuple[int, int, int, int]]:
    return {
        name: (rect.x(), rect.y(), rect.width(), rect.height())
        for name, rect in (
            ("run", _global_rect(window.run_button)),
            ("stop", _global_rect(window.stop_button)),
            ("progress", _global_rect(window.progress)),
            ("export", _global_rect(window.export_button)),
            ("clear", _global_rect(window.clear_button)),
        )
    }


def test_c2_is_the_canonical_results_header_without_duplicate_controls(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _create_window(app, monkeypatch)
    try:
        operations, filters = _header_layouts(window)
        assert operations.objectName() == "ResultsOperationsHeader"
        assert filters.objectName() == "ResultsFiltersHeader"
        assert "Prototype" not in window.windowTitle()
        assert window.centralWidget().property("actionLayoutPrototype") is None

        command_buttons = (
            window.run_button,
            window.stop_button,
            window.export_button,
            window.clear_button,
        )
        assert all(
            window.findChildren(QPushButton).count(button) == 1
            for button in command_buttons
        )
        assert window.findChildren(QProgressBar) == [window.progress]
        assert window.findChildren(details_ui.DetailsPanelControl) == [
            window.details_control
        ]

        expected_operations = [
            window.run_button,
            window.stop_button,
            window.progress,
            window.export_button,
            window.clear_button,
        ]
        assert [
            widget
            for widget in _layout_widgets(operations)
            if widget in expected_operations
        ] == expected_operations
        assert compact_ui._find_layout_containing(filters, window.search_edit) is filters
        assert compact_ui._find_layout_containing(filters, window.details_control) is filters

        results_card = window.summary_label.parentWidget()
        assert all(button.parentWidget() is results_card for button in command_buttons)
        assert window.progress.parentWidget() is results_card
        assert window.details_control.parentWidget() is results_card
        assert window.status_bar.findChildren(QProgressBar) == []
        assert window.status_label.parentWidget() is window.status_bar

        assert window.progress.minimumWidth() == compact_ui.OPERATION_PROGRESS_MIN_WIDTH
        assert window.progress.maximumWidth() == compact_ui.OPERATION_PROGRESS_MAX_WIDTH
        assert (
            window.progress.sizePolicy().horizontalPolicy()
            is QSizePolicy.Policy.Expanding
        )
        assert window.progress.isVisible()
        assert (window.progress.minimum(), window.progress.maximum(), window.progress.value()) == (
            0,
            100,
            0,
        )
    finally:
        window.close()
        app.processEvents()


def test_c2_lifecycle_keeps_progress_and_command_geometry_stable(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _create_window(app, monkeypatch, width=1500, height=900)
    try:
        window.source_mode = "file"
        window.file_apps = [{"app_name": "Example", "package_name": "com.example"}]
        window.current_rows = [
            {"package_name": "com.example", "play_status": "available"}
        ]
        window._sync_action_availability()
        app.processEvents()

        idle_geometry = _geometry_snapshot(window)
        assert window.progress.isVisible()
        assert window.progress.value() == 0

        window.progress.setRange(0, 8)
        window.progress.setValue(3)
        window._set_audit_state(AuditRunState.RUNNING)
        app.processEvents()
        assert window.run_button.text() == "Pause"
        assert (window.progress.minimum(), window.progress.maximum(), window.progress.value()) == (
            0,
            8,
            3,
        )
        assert _geometry_snapshot(window) == idle_geometry

        window._set_audit_state(AuditRunState.PAUSED)
        app.processEvents()
        assert window.run_button.text() == "Resume"
        assert _geometry_snapshot(window) == idle_geometry

        window._set_audit_state(AuditRunState.RUNNING)
        app.processEvents()
        assert window.run_button.text() == "Pause"
        assert _geometry_snapshot(window) == idle_geometry

        window._set_audit_state(AuditRunState.STOPPING)
        app.processEvents()
        assert window.run_button.text() == "Stopping…"
        assert _geometry_snapshot(window) == idle_geometry

        window.progress.setRange(0, 0)
        window._set_audit_state(AuditRunState.FINALIZING)
        app.processEvents()
        assert window.run_button.text() == "Finalizing…"
        assert window.progress.minimum() == window.progress.maximum() == 0
        assert _geometry_snapshot(window) == idle_geometry

        window._set_audit_state(AuditRunState.IDLE)
        app.processEvents()
        assert window.run_button.text() == "Run Play Store Audit"
        assert window.progress.isVisible()
        assert (window.progress.minimum(), window.progress.maximum(), window.progress.value()) == (
            0,
            100,
            0,
        )
        assert _geometry_snapshot(window) == idle_geometry
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize(("width", "height"), REVIEW_SIZES)
def test_c2_controls_do_not_overlap_or_clip_at_review_sizes(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    width: int,
    height: int,
) -> None:
    window = _create_window(app, monkeypatch, width=width, height=height)
    try:
        window.summary_label.setText(
            "250 apps • 18 Removed • 27 Stale • 205 Recent Update"
        )
        window.progress.setRange(0, 24)
        window.progress.setValue(7)
        window._set_audit_state(AuditRunState.RUNNING)
        app.processEvents()

        operations, filters = _header_layouts(window)
        assert operations.objectName() == "ResultsOperationsHeader"
        assert filters.objectName() == "ResultsFiltersHeader"
        operation_widgets = [
            window.run_button,
            window.stop_button,
            window.progress,
            window.export_button,
            window.clear_button,
        ]
        operation_rects = [_global_rect(widget) for widget in operation_widgets]
        assert all(widget.isVisible() for widget in operation_widgets)
        assert all(rect.width() > 0 and rect.height() > 0 for rect in operation_rects)
        for index, rect in enumerate(operation_rects):
            for other in operation_rects[index + 1 :]:
                assert not rect.intersects(other)

        filter_widgets = [
            window.all_chip,
            *window.criticality_buttons.values(),
            window.hide_system_check,
            window.search_edit,
            window.details_control,
        ]
        assert all(widget.isVisible() for widget in filter_widgets)
        assert all(_global_rect(widget).height() > 0 for widget in filter_widgets)

        assert window.progress.width() >= compact_ui.OPERATION_PROGRESS_MIN_WIDTH
        results_rect = _global_rect(window.summary_label.parentWidget())
        for widget in (
            window.run_button,
            window.stop_button,
            window.progress,
            window.export_button,
            window.clear_button,
            window.details_control,
        ):
            assert results_rect.contains(_global_rect(widget))
    finally:
        window.close()
        app.processEvents()


def test_details_control_keeps_one_state_shared_with_view_menu(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _create_window(app, monkeypatch, width=1900, height=1000)
    try:
        assert window.details_panel_menu is window.details_control.mode_menu
        assert window.details_panel_menu.menuAction() in window.view_menu.actions()
        assert set(window.details_control.position_actions) == {
            "auto",
            "right",
            "below",
            "hidden",
        }

        window.details_control.set_position("below")
        app.processEvents()
        assert window.details_control.position() == "below"
        assert window._details_panel_position == "below"
        assert window.details_control.position_actions["below"].isChecked()
        assert window.details_splitter.orientation() == Qt.Orientation.Vertical

        window.details_control.position_actions["hidden"].trigger()
        app.processEvents()
        assert window.details_control.position() == "hidden"
        assert window._details_panel_position == "hidden"
        assert window.details_panel.isHidden()

        window.details_control.position_actions["auto"].trigger()
        app.processEvents()
        assert window.details_control.position() == "auto"
        assert window._details_panel_position == "auto"
        assert window.details_control.position_actions["auto"].isChecked()
    finally:
        window.close()
        app.processEvents()
