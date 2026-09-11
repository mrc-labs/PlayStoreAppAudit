from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QTableView

import playstore_app_audit.ui.table_window as table_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_selected_item_uses_custom_paint_state_without_windows_item_accents(
    app: QApplication,
) -> None:
    model = table_ui.AuditTableModel()
    view = QTableView()
    delegate = table_ui.SemanticSelectionDelegate(view)
    try:
        model.set_rows(
            [
                {
                    "source_mode": "local_apk",
                    "criticality_key": "green",
                    "criticality": "Recent Update",
                    "local_apk_version_comparison": "Match",
                    "package_name": "com.example.app",
                }
            ]
        )
        view.setModel(model)
        index = model.index(0, model.columns.index("package_name"))
        option = QStyleOptionViewItem()
        option.state |= (
            QStyle.StateFlag.State_Selected
            | QStyle.StateFlag.State_HasFocus
            | QStyle.StateFlag.State_KeyboardFocusChange
        )

        delegate.initStyleOption(option, index)

        assert not option.state & QStyle.StateFlag.State_Selected
        assert not option.state & QStyle.StateFlag.State_HasFocus
        assert not option.state & QStyle.StateFlag.State_KeyboardFocusChange
        assert option.backgroundBrush.color().name().lower() == table_ui.SELECTED_ROW_BACKGROUND.lower()
    finally:
        view.deleteLater()
        model.deleteLater()
        app.processEvents()


def test_selected_semantic_cell_keeps_meaning_with_only_subtle_darkening(
    app: QApplication,
) -> None:
    model = table_ui.AuditTableModel()
    view = QTableView()
    delegate = table_ui.SemanticSelectionDelegate(view)
    try:
        model.set_rows(
            [
                {
                    "source_mode": "local_apk",
                    "criticality_key": "red",
                    "criticality": "Not Found",
                    "local_apk_version_comparison": "Unknown",
                }
            ]
        )
        view.setModel(model)
        index = model.index(0, model.columns.index("local_apk_version_comparison"))
        base_background = model.data(index, Qt.ItemDataRole.BackgroundRole)
        assert isinstance(base_background, QColor)

        option = QStyleOptionViewItem()
        option.state |= QStyle.StateFlag.State_Selected
        delegate.initStyleOption(option, index)

        expected = base_background.darker(104)
        assert option.backgroundBrush.color() == expected
        assert option.backgroundBrush.color() != QColor(table_ui.SELECTED_ROW_BACKGROUND)
    finally:
        view.deleteLater()
        model.deleteLater()
        app.processEvents()


def test_focus_outline_stylesheet_does_not_disable_keyboard_focus(
    app: QApplication,
) -> None:
    view = QTableView()
    try:
        original_policy = view.focusPolicy()
        view.setStyleSheet("QTableView { gridline-color: #dddddd; }")

        table_ui._suppress_table_item_focus_outline(view)
        first_style = view.styleSheet()
        table_ui._suppress_table_item_focus_outline(view)

        assert "gridline-color" in first_style
        assert table_ui.TABLE_ITEM_FOCUS_STYLE in first_style
        assert "QTableView::item:selected" not in first_style
        assert view.styleSheet().count(table_ui.TABLE_ITEM_FOCUS_STYLE) == 1
        assert view.focusPolicy() == original_policy
        assert original_policy != Qt.FocusPolicy.NoFocus
    finally:
        view.deleteLater()
        app.processEvents()
