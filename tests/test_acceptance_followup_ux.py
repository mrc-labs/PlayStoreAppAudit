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


def test_selected_current_cell_uses_custom_row_paint_without_changing_selection(
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
        view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        index = model.index(0, model.columns.index("package_name"))
        view.setCurrentIndex(index)
        view.selectRow(0)
        assert view.selectionModel().isSelected(index)

        option = QStyleOptionViewItem()
        option.state |= QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus
        delegate.initStyleOption(option, index)

        # The delegate removes only the native selected-item paint state. The
        # view/selection model remains selected and keyboard navigation remains intact.
        assert not option.state & QStyle.StateFlag.State_Selected
        assert not option.state & QStyle.StateFlag.State_HasFocus
        assert view.selectionModel().isSelected(index)
        assert option.backgroundBrush.color().name().lower() == table_ui.SELECTED_ROW_BACKGROUND.lower()
    finally:
        view.deleteLater()
        model.deleteLater()
        app.processEvents()


def test_available_live_row_missing_icon_metadata_is_eligible_for_bounded_backfill(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(table_ui.state, "load_settings", lambda: {"show_app_icons": True})
    monkeypatch.setattr(table_ui.app_icon_metadata, "icon_url_for_package", lambda _package: "")
    model = table_ui.AuditTableModel()
    scheduled: list[tuple[object, object, object]] = []
    monkeypatch.setattr(
        model._metadata_backfill,
        "schedule",
        lambda package, country, language: scheduled.append((package, country, language)) or True,
    )
    try:
        model.set_store_context_provider(lambda: ("it", "it"))
        model.set_rows(
            [
                {
                    "source_mode": "local_apk",
                    "package_name": "com.example.live-no-icon",
                    "play_status": "available",
                    "play_last_update": "2026-09-01",
                    "cache_hit": False,
                }
            ]
        )

        assert scheduled == [("com.example.live-no-icon", "it", "it")]
    finally:
        model.deleteLater()
        app.processEvents()
