from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui import schema, table_layout
from playstore_app_audit.ui.main_window import MainWindow
from playstore_app_audit.ui.table_window import TABLE_SCHEMA_VERSION


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: dict[str, object],
) -> None:
    def load_settings() -> dict[str, object]:
        return dict(settings)

    def save_settings(values: dict[str, object]) -> dict[str, object]:
        settings.update(values)
        return dict(settings)

    monkeypatch.setattr(state, "load_settings", load_settings)
    monkeypatch.setattr(state, "save_settings", save_settings)
    monkeypatch.setattr(compact_ui, "load_settings", load_settings)
    monkeypatch.setattr(compact_ui, "save_settings", save_settings)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)


def _technical_settings() -> dict[str, object]:
    return {
        "view_preset": "Technical",
        "recent_sources": [],
        "exclude_system_source": True,
        "inventory_history_enabled": False,
        "compare_previous": True,
        "health_score_enabled": True,
        "qt_header_schema_version": TABLE_SCHEMA_VERSION,
    }


def test_semantic_defaults_are_bounded_and_do_not_resize_to_body_values(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _technical_settings()
    _patch_settings(monkeypatch, settings)
    window = MainWindow()
    try:
        header = window.table.horizontalHeader()
        for logical, column in enumerate(window.model.columns):
            assert header.sectionResizeMode(logical) is QHeaderView.ResizeMode.Interactive
            assert window.table.columnWidth(logical) == table_layout.default_column_width(
                window.table, column
            )

        score_width = window.table.columnWidth(window.model.columns.index("health_score"))
        url_width = window.table.columnWidth(window.model.columns.index("store_url"))
        package_width = window.table.columnWidth(window.model.columns.index("package_name"))
        unwrapped_score_width = (
            header.fontMetrics().horizontalAdvance(schema.COLUMN_LABELS["health_score"])
            + table_layout.header_chrome_width(header)
        )
        assert score_width >= schema.DEFAULT_WIDTHS["health_score"]
        assert score_width < unwrapped_score_width
        assert url_width == 250
        assert url_width <= schema.COLUMN_WIDTH_POLICIES["store_url"].maximum
        assert package_width > score_width

        rows = [
            {
                "package_name": "com.example." + "package" * 40,
                "store_url": "https://play.google.com/store/apps/details?id=" + "x" * 500,
                "health_score": 100,
            }
        ]
        before = tuple(window.table.columnWidth(i) for i in range(len(window.model.columns)))
        window.model.set_rows(rows)
        app.processEvents()
        after = tuple(window.table.columnWidth(i) for i in range(len(window.model.columns)))
        assert after == before
    finally:
        window.close()
        app.processEvents()


def test_wrapped_headers_share_one_height_and_preserve_native_sorting(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _technical_settings()
    _patch_settings(monkeypatch, settings)
    window = MainWindow()
    try:
        header = window.table.horizontalHeader()
        chrome = table_layout.header_chrome_width(header)
        wrapped = (
            "health_score",
            "version_comparison",
            "compatibility_status",
            "device_change",
            "sensitive_permissions_count",
        )
        for column in wrapped:
            logical = window.model.columns.index(column)
            title = window.model.headerData(logical, Qt.Orientation.Horizontal)
            assert isinstance(title, str) and title.count("\n") == 1
            widest_line = max(
                header.fontMetrics().horizontalAdvance(line) for line in title.splitlines()
            )
            assert window.table.columnWidth(logical) >= widest_line + chrome

        store_url = window.model.columns.index("store_url")
        assert window.model.headerData(store_url, Qt.Orientation.Horizontal) == "Store URL"
        assert header.height() == table_layout.shared_header_height(header)
        assert header.height() >= 2 * header.fontMetrics().lineSpacing()
        assert window.table.verticalHeader().defaultSectionSize() == 24

        score = window.model.columns.index("health_score")
        window.table.sortByColumn(score, Qt.SortOrder.DescendingOrder)
        assert header.sortIndicatorSection() == score
        assert header.isSortIndicatorShown()
    finally:
        window.close()
        app.processEvents()


def test_saved_user_widths_override_defaults_after_restart(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _technical_settings()
    _patch_settings(monkeypatch, settings)
    columns = ("health_score", "store_url", "package_name")
    wanted = (111, 273, 333)

    first = MainWindow()
    for column, width in zip(columns, wanted, strict=True):
        first.table.setColumnWidth(first.model.columns.index(column), width)
    first._save_table_layout()
    first.close()
    app.processEvents()

    restarted = MainWindow()
    try:
        restored = tuple(
            restarted.table.columnWidth(restarted.model.columns.index(column))
            for column in columns
        )
        assert restored == wanted
    finally:
        restarted.close()
        app.processEvents()
