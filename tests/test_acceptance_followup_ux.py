from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QTableView

import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.table_window as table_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_store_status_labels_are_symbol_free_and_recent_update_is_explicit() -> None:
    for info in base_ui.CRITICALITY.values():
        assert "●" not in str(info["label"])
        assert "●" not in str(info["button"])
    assert base_ui.CRITICALITY["green"]["label"] == "Recent Update"
    assert base_ui.CRITICALITY["green"]["button"] == "Recent Update"


@pytest.mark.parametrize("column", ["local_apk_version_comparison", "version_comparison"])
def test_version_relationship_cells_match_store_status_emphasis_and_alignment(
    app: QApplication,
    column: str,
) -> None:
    model = table_ui.AuditTableModel()
    try:
        row = {
            "source_mode": "local_apk" if column.startswith("local_") else "device",
            "criticality_key": "green",
            "criticality": "Recent Update",
            column: "Match",
        }
        model.set_rows([row])
        relationship_index = model.index(0, model.columns.index(column))
        status_index = model.index(0, model.columns.index("criticality"))

        relationship_font = model.data(relationship_index, Qt.ItemDataRole.FontRole)
        status_font = model.data(status_index, Qt.ItemDataRole.FontRole)
        assert isinstance(relationship_font, QFont)
        assert isinstance(status_font, QFont)
        assert relationship_font.weight() == status_font.weight() == QFont.Weight.Bold
        assert model.data(relationship_index, Qt.ItemDataRole.TextAlignmentRole) == int(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
    finally:
        model.deleteLater()
        app.processEvents()


def test_selected_current_cell_does_not_keep_windows_focus_edge(app: QApplication) -> None:
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
        view.setCurrentIndex(index)
        option = QStyleOptionViewItem()
        option.state |= QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus

        delegate.initStyleOption(option, index)

        assert option.state & QStyle.StateFlag.State_Selected
        assert not option.state & QStyle.StateFlag.State_HasFocus
    finally:
        view.deleteLater()
        model.deleteLater()
        app.processEvents()
