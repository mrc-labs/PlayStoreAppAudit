from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QLabel, QWidget

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
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[MainWindow]:
    settings: dict[str, object] = {"view_preset": "Basic", "recent_sources": []}
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def test_customize_view_uses_two_column_top_section_with_custom_spacing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    def inspect(dialog: QDialog) -> int:
        automatic_pane = dialog.findChild(QWidget, "AutomaticColumnsPane")
        display_pane = dialog.findChild(QWidget, "DisplayOptionsPane")
        automatic_title = dialog.findChild(QLabel, "AutomaticColumnsTitle")
        display_title = dialog.findChild(QLabel, "DisplayOptionsTitle")
        custom_title = dialog.findChild(QLabel, "CustomColumnsTitle")
        icons = dialog.findChild(QCheckBox, "ShowAppIconsCheck")
        date_format = dialog.findChild(QComboBox, "DateFormatCombo")

        assert automatic_pane is not None
        assert display_pane is not None
        assert automatic_title is not None and automatic_title.text() == "Automatic Columns"
        assert display_title is not None and display_title.text() == "Display Options"
        assert custom_title is not None
        assert icons is not None and icons.parentWidget() is display_pane
        assert date_format is not None and date_format.parentWidget() is display_pane

        automatic_checks = [
            check
            for check in dialog.findChildren(QCheckBox)
            if check.objectName().startswith("AutomaticColumnCheck_")
        ]
        assert len(automatic_checks) == 5
        assert all(check.parentWidget() is automatic_pane for check in automatic_checks)

        root = dialog.layout()
        assert root is not None
        custom_index = next(
            index
            for index in range(root.count())
            if root.itemAt(index).widget() is custom_title
        )
        spacer = root.itemAt(custom_index - 1).spacerItem()
        assert spacer is not None
        assert spacer.sizeHint().height() >= 14
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    window._show_display_settings()
