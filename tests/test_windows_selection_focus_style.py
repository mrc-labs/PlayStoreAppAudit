from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QTableView

import playstore_app_audit.ui.table_window as table_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_selected_item_strips_both_windows_focus_painting_states(
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
                }
            ]
        )
        view.setModel(model)
        index = model.index(0, model.columns.index("criticality"))
        option = QStyleOptionViewItem()
        option.state |= (
            QStyle.StateFlag.State_Selected
            | QStyle.StateFlag.State_HasFocus
            | QStyle.StateFlag.State_KeyboardFocusChange
        )

        delegate.initStyleOption(option, index)

        assert option.state & QStyle.StateFlag.State_Selected
        assert not option.state & QStyle.StateFlag.State_HasFocus
        assert not option.state & QStyle.StateFlag.State_KeyboardFocusChange
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
        assert "QTableView::item:focus { outline: none; border: none; }" in first_style
        assert "QTableView::item:selected { border: none; }" in first_style
        assert table_ui.TABLE_ITEM_FOCUS_STYLE in first_style
        assert view.styleSheet().count(table_ui.TABLE_ITEM_FOCUS_STYLE) == 1
        assert view.focusPolicy() == original_policy
        assert original_policy != Qt.FocusPolicy.NoFocus
    finally:
        view.deleteLater()
        app.processEvents()
