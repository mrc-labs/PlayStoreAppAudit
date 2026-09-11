from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QStyle,
    QStyleOptionViewItem,
    QTableView,
)

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.details_panel as details_ui
import playstore_app_audit.ui.table_window as table_ui
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.mark.parametrize(
    ("field", "value", "status_key", "emphasis", "font_weight"),
    [
        ("version_comparison", "Outdated", "orange", "strong_warning", 700),
        ("version_comparison", "Different", "yellow", "warning", 700),
        ("version_comparison", "Unknown", "purple", "warning", 700),
        ("version_comparison", "Device-specific", "blue", "warning", 700),
        ("version_comparison", "Newer", "green", "warning", 700),
        ("version_comparison", "Match", "green", "warning", 700),
        (
            "local_apk_version_comparison",
            "Outdated",
            "orange",
            "strong_warning",
            700,
        ),
        ("local_apk_version_comparison", "Different", "yellow", "warning", 700),
        ("local_apk_version_comparison", "Unknown", "purple", "warning", 700),
        (
            "local_apk_version_comparison",
            "Device-specific",
            "blue",
            "warning",
            700,
        ),
        ("local_apk_version_comparison", "Newer", "green", "warning", 700),
        ("local_apk_version_comparison", "Match", "green", "warning", 700),
        ("compatibility_status", "Aging target", "yellow", "warning", 600),
        (
            "compatibility_status",
            "Legacy target",
            "orange",
            "strong_warning",
            600,
        ),
    ],
)
def test_warning_values_map_to_existing_status_semantics(
    field: str,
    value: str,
    status_key: str,
    emphasis: str,
    font_weight: int,
) -> None:
    value_presentation = presentation.semantic_value_presentation(field, value)

    assert value_presentation is not None
    assert value_presentation.status_key == status_key
    assert value_presentation.emphasis == emphasis
    assert value_presentation.font_weight == font_weight
    assert presentation.semantic_foreground_colour(field, value) == (
        presentation.STATUS_FOREGROUND_COLOURS[status_key]
    )
    assert base_ui.CRITICALITY[status_key]["foreground"] == (
        presentation.STATUS_FOREGROUND_COLOURS[status_key]
    )


def test_table_warning_typography_preserves_severity_hierarchy(
    app: QApplication,
) -> None:
    rows = [
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "version_comparison": "Same",
            "compatibility_status": "Modern",
        },
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "version_comparison": "Different",
            "compatibility_status": "Aging target",
        },
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "version_comparison": "Different",
            "compatibility_status": "Legacy target",
        },
    ]
    model = table_ui.AuditTableModel()
    model.set_rows(rows)

    comparison_column = model.columns.index("version_comparison")
    compatibility_column = model.columns.index("compatibility_status")
    status_column = model.columns.index("criticality")

    normal_font = model.data(
        model.index(0, compatibility_column), Qt.ItemDataRole.FontRole
    )
    different_font = model.data(
        model.index(1, comparison_column), Qt.ItemDataRole.FontRole
    )
    aging_font = model.data(
        model.index(1, compatibility_column), Qt.ItemDataRole.FontRole
    )
    legacy_font = model.data(
        model.index(2, compatibility_column), Qt.ItemDataRole.FontRole
    )
    status_font = model.data(model.index(2, status_column), Qt.ItemDataRole.FontRole)

    assert normal_font is None
    assert different_font.weight() == 700
    assert aging_font.weight() == legacy_font.weight() == 600
    assert status_font.weight() == 700
    assert different_font.weight() == status_font.weight()

    warning_colour = model.data(
        model.index(1, compatibility_column), Qt.ItemDataRole.ForegroundRole
    )
    strong_warning_colour = model.data(
        model.index(2, compatibility_column), Qt.ItemDataRole.ForegroundRole
    )
    assert warning_colour != strong_warning_colour

    model.deleteLater()
    app.processEvents()


def test_unrelated_values_do_not_receive_warning_presentation() -> None:
    unrelated = (
        ("version_comparison", "Same"),
        ("compatibility_status", "Modern"),
        ("compatibility_status", "Unknown"),
        ("compatibility_status", ""),
        ("play_status", "Different"),
    )

    for field, value in unrelated:
        assert presentation.semantic_value_presentation(field, value) is None
        assert presentation.semantic_foreground_colour(field, value) is None
        assert presentation.semantic_html_value(field, value) == value


def test_modern_remains_regular_without_semantic_warning_styling(
    app: QApplication,
) -> None:
    label = QLabel("Modern")

    assert label.font().weight() == QFont.Weight.Normal.value
    assert not base_ui.apply_semantic_label_presentation(
        label, "compatibility_status", "Modern"
    )
    assert label.font().weight() == QFont.Weight.Normal.value

    label.deleteLater()
    app.processEvents()


def test_selected_table_rows_keep_native_highlighted_text_role(
    app: QApplication,
) -> None:
    model = table_ui.AuditTableModel()
    model.set_rows(
        [
            {
                "criticality_key": "green",
                "version_comparison": "Different",
            }
        ]
    )
    view = QTableView()
    view.setModel(model)
    index = model.index(0, model.columns.index("version_comparison"))
    view.selectRow(0)
    view.show()
    app.processEvents()

    option = QStyleOptionViewItem()
    option.initFrom(view)
    option.state |= QStyle.StateFlag.State_Selected
    view.itemDelegate().initStyleOption(option, index)

    semantic_colour = model.data(index, Qt.ItemDataRole.ForegroundRole)
    assert view.selectionModel().isSelected(index)
    assert option.palette.color(QPalette.ColorRole.Text) == semantic_colour
    assert option.palette.color(QPalette.ColorRole.HighlightedText) != semantic_colour
    assert option.palette.color(QPalette.ColorRole.HighlightedText) == (
        view.palette().color(QPalette.ColorRole.HighlightedText)
    )

    view.close()
    model.deleteLater()
    app.processEvents()


def test_semantic_label_helper_preserves_disabled_palette_role(
    app: QApplication,
) -> None:
    label = QLabel("Legacy target")
    disabled_before = label.palette().color(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
    )

    assert base_ui.apply_semantic_label_presentation(
        label, "compatibility_status", "Legacy target"
    )
    assert label.font().weight() == 600
    assert label.palette().color(
        QPalette.ColorGroup.Active,
        QPalette.ColorRole.WindowText,
    ).name().casefold() == presentation.STATUS_FOREGROUND_COLOURS[
        "orange"
    ].casefold()
    assert label.palette().color(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
    ) == disabled_before

    label.deleteLater()
    app.processEvents()


def test_details_panel_styles_only_the_three_warning_values(
    app: QApplication,
) -> None:
    panel = details_ui.AppDetailsPanel()
    panel.set_row(
        {
            "package_name": "com.example.warning",
            "installed_version": "1.0",
            "play_version": "2.0",
            "version_comparison": "Different",
            "compatibility_status": "Legacy target",
            "target_sdk": "29",
        }
    )
    device_html = panel.device_label.text()

    assert device_html.count('class="semantic-warning"') == 1
    assert device_html.count('class="semantic-strong-warning"') == 1
    assert "Different" in device_html
    assert "Legacy target" in device_html
    assert "Installed version: 1.0" in device_html
    assert "Target SDK: 29" in device_html

    panel.deleteLater()
    app.processEvents()


def test_context_details_dialog_uses_the_same_semantic_label_helper(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "details_panel_position": "hidden",
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])

    captured: dict[str, QLabel] = {}

    def inspect_dialog(dialog: QDialog) -> int:
        for field in ("version_comparison", "compatibility_status"):
            label = dialog.findChild(QLabel, f"DetailsValue_{field}")
            assert label is not None
            captured[field] = label
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(QDialog, "exec", inspect_dialog)
    window = MainWindow()
    try:
        window._show_details(
            {
                "package_name": "com.example.warning",
                "version_comparison": "Different",
                "compatibility_status": "Legacy target",
            }
        )
        assert captured["version_comparison"].font().weight() == 700
        assert captured["compatibility_status"].font().weight() == 600
    finally:
        window.close()
        app.processEvents()


def test_html_report_uses_semantic_spans_without_changing_values(
    tmp_path: Path,
) -> None:
    rows = [
        {
            "package_name": "com.example.aging",
            "version_comparison": "Different",
            "compatibility_status": "Aging target",
        },
        {
            "package_name": "com.example.legacy",
            "version_comparison": "Same",
            "compatibility_status": "Legacy target",
        },
        {
            "package_name": "com.example.normal",
            "version_comparison": "Match",
            "compatibility_status": "Modern",
        },
    ]

    target = device_insights.write_html_report(tmp_path / "report.html", rows)
    report = target.read_text(encoding="utf-8")

    assert "<th>Installed vs Store</th>" in report
    assert presentation.semantic_html_value(
        "version_comparison", "Different"
    ) in report
    assert presentation.semantic_html_value(
        "compatibility_status", "Aging target"
    ) in report
    assert presentation.semantic_html_value(
        "compatibility_status", "Legacy target"
    ) in report
    assert '<span class="semantic-warning"' in report
    assert '<span class="semantic-strong-warning"' in report
    assert rows[0]["version_comparison"] == "Different"
    assert rows[1]["compatibility_status"] == "Legacy target"
