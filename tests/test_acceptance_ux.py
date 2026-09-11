from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QStyle,
    QStyleOptionViewItem,
)

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.preferences_window as preferences_ui
from playstore_app_audit.ui import column_presets, schema, table_layout
from playstore_app_audit.ui.main_window import MainWindow
from playstore_app_audit.ui.results_window import NumericAuditFilterProxy
from playstore_app_audit.ui.table_window import TABLE_SCHEMA_VERSION, AuditTableModel


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window_store(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[dict[str, object], Callable[[], MainWindow]]]:
    settings: dict[str, object] = deepcopy(state.DEFAULT_SETTINGS)
    settings.update(
        {
            "view_preset": "Basic",
            "recent_sources": [],
            "qt_header_schema_version": TABLE_SCHEMA_VERSION,
        }
    )
    windows: list[MainWindow] = []

    def load_settings() -> dict[str, object]:
        return deepcopy(settings)

    def save_settings(values: dict[str, object]) -> dict[str, object]:
        settings.update(deepcopy(values))
        return deepcopy(settings)

    monkeypatch.setattr(state, "load_settings", load_settings)
    monkeypatch.setattr(state, "save_settings", save_settings)
    monkeypatch.setattr(compact_ui, "load_settings", load_settings)
    monkeypatch.setattr(compact_ui, "save_settings", save_settings)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)

    def create_window() -> MainWindow:
        window = MainWindow()
        windows.append(window)
        return window

    yield settings, create_window
    for window in windows:
        window.close()
    app.processEvents()


def _visible_order(window: MainWindow) -> list[str]:
    header = window.table.horizontalHeader()
    return [
        window.model.columns[header.logicalIndex(visual)]
        for visual in range(header.count())
        if not window.table.isColumnHidden(header.logicalIndex(visual))
    ]


def test_source_selector_order_buttons_and_or_separators(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    _settings, create_window = window_store
    window = create_window()
    source_frames = window.findChildren(QFrame, "SourceOption")
    labels = [
        next(label.text() for label in frame.findChildren(QLabel) if label.text() != "or")
        for frame in source_frames
    ]
    assert labels == ["Android Phone (ADB)", "Local APK(s)", "App List File"]
    assert window.scan_button.text() == "Scan Phone"
    assert window.choose_apk_button.text() == "Choose APK Source…"
    assert window.choose_button.text() == "Choose File"
    assert len([label for label in window.findChildren(QLabel) if label.text() == "or"]) == 2
    assert window.findChild(QPushButton, "RecentSourcesButton") is None
    assert window.recent_sources_button.accessibleName() == "Recent Sources"
    assert [action.text() for action in window.local_apk_options_menu.actions()] == [
        "File(s)…",
        "Folder…",
    ]


def test_store_status_label_precedes_criticality_only_chips(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    _settings, create_window = window_store
    window = create_window()
    parent_layout = window.store_status_filter_label.parentWidget().layout()
    layout = compact_ui._find_layout_containing(
        parent_layout, window.store_status_filter_label
    )

    assert window.store_status_filter_label.text() == "Store Status:"
    assert layout is not None
    assert layout.indexOf(window.store_status_filter_label) < layout.indexOf(window.all_chip)
    assert "version relationships remain independent" in window.store_status_filter_label.toolTip()


def test_store_status_chip_counts_ignore_local_relationship_state(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    _settings, create_window = window_store
    window = create_window()
    window.current_rows = [
        {
            "source_mode": "local_apk",
            "criticality_key": "red",
            "local_apk_version_comparison": "Outdated",
        },
        {
            "source_mode": "local_apk",
            "criticality_key": "red",
            "local_apk_version_comparison": "Match",
        },
    ]
    window.model.set_rows(window.current_rows)

    window._update_summary()

    assert window.criticality_buttons["red"].text().endswith(" 2")
    assert window.criticality_buttons["green"].text().endswith(" 0")


@pytest.mark.parametrize("source_mode", ["device", "local_apk", "file"])
def test_store_status_text_is_symbol_free_for_every_source_type(source_mode: str) -> None:
    from playstore_app_audit.ui.base_window import CRITICALITY

    model = AuditTableModel()
    model.set_rows(
        [
            {
                "source_mode": source_mode,
                "criticality_key": "green",
                "criticality": CRITICALITY["green"]["label"],
            }
        ]
    )
    index = model.index(0, model.columns.index("criticality"))

    assert index.data(Qt.ItemDataRole.DisplayRole) == "Recent Update"


def test_source_status_text_names_the_active_source(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    tmp_path: Path,
) -> None:
    _settings, create_window = window_store
    window = create_window()
    app_list = tmp_path / "apps.csv"
    app_list.write_text("package_name\ncom.example.app\n", encoding="utf-8")
    apk = tmp_path / "one.apk"
    apk.write_bytes(b"not parsed during selection")

    window._load_input_file(str(app_list))
    assert window.source_label.text().startswith("App List source:")

    window._establish_local_apk_candidates((apk,), "selected")
    assert window.source_label.text().startswith("Local package source:")

    window.source_mode = "device"
    window._device_summary = {"manufacturer": "Google", "model": "Pixel"}
    window.source_label.setText("Phone scan: 1 third-party package loaded")
    window._restore_device_source_identity()
    assert window.source_label.text().startswith("Phone source: Google Pixel")


@pytest.mark.parametrize(
    ("preset", "source", "expected"),
    [
        (
            "Basic",
            "file",
            [
                "criticality", "change", "package_name", "play_title", "play_version",
                "play_last_update", "age_days", "health_score", "notes",
            ],
        ),
        (
            "Basic",
            "device",
            [
                "criticality", "change", "package_name", "play_title",
                "version_comparison", "installed_version", "play_version",
                "play_last_update", "age_days", "health_score", "notes",
            ],
        ),
        (
            "Basic",
            "local_apk",
            [
                "local_apk_version_comparison", "criticality", "local_apk_file_name",
                "local_apk_label", "package_name", "local_apk_version_name",
                "play_version", "play_last_update", "age_days", "health_score", "notes",
            ],
        ),
        (
            "Source Details",
            "file",
            [
                "criticality", "change", "package_name", "play_title", "play_version",
                "play_last_update", "age_days", "app_name", "store_url",
                "health_score", "notes",
            ],
        ),
        (
            "Source Details",
            "device",
            [
                "criticality", "change", "package_name", "play_title",
                "version_comparison", "installed_version", "play_version",
                "play_last_update", "age_days", "compatibility_status",
                "installer_source", "installer_category", "app_enabled", "first_install_time",
                "last_local_update", "device_change", "health_score", "notes",
            ],
        ),
        (
            "Source Details",
            "local_apk",
            [
                "local_apk_version_comparison", "criticality", "local_apk_file_name",
                "local_apk_label", "package_name", "play_title",
                "local_apk_version_name", "play_version",
                "play_last_update", "age_days", "local_apk_location", "health_score", "notes",
            ],
        ),
    ],
)
def test_basic_and_source_details_layouts(
    preset: str, source: str, expected: list[str]
) -> None:
    assert column_presets.visible_columns(
        preset,
        source,
        compare_previous=True,
        health_score_enabled=True,
    ) == expected


@pytest.mark.parametrize("source", ["file", "local_apk", "device"])
def test_technical_is_source_aware_and_notes_last(source: str) -> None:
    columns = column_presets.visible_columns(
        "Technical", source, compare_previous=True, health_score_enabled=True
    )
    assert columns[-1] == "notes"
    if source == "device":
        assert "installed_version" in columns
        assert "local_apk_location" not in columns
    elif source == "local_apk":
        assert columns[0] == "local_apk_version_comparison"
        assert "local_apk_location" in columns
        assert "installed_version" not in columns
        assert "sensitive_permissions" not in columns
    else:
        assert "installed_version" not in columns
        assert "local_apk_location" not in columns


@pytest.mark.parametrize("preset", column_presets.BUILTIN_PRESETS)
def test_file_apk_adb_switching_reapplies_builtin_order_and_widths_without_custom(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    preset: str,
) -> None:
    settings, create_window = window_store
    settings.update({"view_preset": preset, "compare_previous": True, "health_score_enabled": True})
    window = create_window()

    for source in ("file", "local_apk", "device"):
        window.source_mode = source
        window._apply_established_source_defaults()
        expected = column_presets.visible_columns(
            preset, source, compare_previous=True, health_score_enabled=True
        )
        assert _visible_order(window) == expected
        assert settings["view_preset"] == preset
        assert settings["custom_view_exists"] is False
        assert _visible_order(window)[-1] == "notes"
        for column in expected:
            logical = window.model.columns.index(column)
            assert window.table.columnWidth(logical) == table_layout.default_column_width(
                window.table, column
            )


def test_custom_notes_position_and_layout_survive_source_switch_and_restart(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": ["criticality", "notes", "package_name"],
            "custom_view_order": ["criticality", "notes", "package_name"],
            "custom_view_widths": {"criticality": 151, "notes": 311, "package_name": 333},
        }
    )
    first = create_window()
    expected = _visible_order(first)
    for source in ("file", "local_apk", "device"):
        first.source_mode = source
        first._apply_established_source_defaults()
        assert _visible_order(first) == expected
        assert first.table.columnWidth(first.model.columns.index("notes")) == 311
    first.close()

    restarted = create_window()
    assert _visible_order(restarted) == expected
    assert settings["view_preset"] == "Custom"


def test_device_preset_migrates_without_touching_custom_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_path = tmp_path / "settings.json"
    custom = {
        "custom_view_exists": True,
        "custom_view_columns": ["criticality", "notes", "package_name"],
        "custom_view_order": ["criticality", "notes", "package_name"],
        "custom_view_widths": {"notes": 319},
    }
    settings_path.write_text(
        json.dumps({"view_preset": "Device", **custom}), encoding="utf-8"
    )
    monkeypatch.setattr(state, "settings_path", lambda: settings_path)
    loaded = state.load_settings()
    assert loaded["view_preset"] == "Source Details"
    for key, value in custom.items():
        assert loaded[key] == value


def _proxy_rows(proxy: NumericAuditFilterProxy, model: AuditTableModel) -> list[dict[str, object]]:
    return [
        model.row_dict(proxy.mapToSource(proxy.index(row, 0)).row())
        for row in range(proxy.rowCount())
    ]


def test_local_apk_relationship_sort_uses_risk_store_and_identity_tie_breaks() -> None:
    rows = [
        {
            "source_mode": "local_apk", "local_apk_version_comparison": relationship,
            "criticality_rank": store_rank, "local_apk_file_name": file_name,
            "package_name": package,
        }
        for relationship, store_rank, file_name, package in [
            ("Match", 0, "z.apk", "z"),
            ("Outdated", 2, "z.apk", "z"),
            ("Different", 0, "z.apk", "z"),
            ("Unknown", 0, "z.apk", "z"),
            ("Device-specific", 0, "z.apk", "z"),
            ("Newer", 0, "z.apk", "z"),
            ("Outdated", 1, "z.apk", "z"),
            ("Outdated", 1, "a.apk", "z"),
            ("Outdated", 1, "a.apk", "a"),
        ]
    ]
    model = AuditTableModel()
    model.set_rows(rows)
    proxy = NumericAuditFilterProxy()
    proxy.setSourceModel(model)
    column = model.columns.index("local_apk_version_comparison")
    proxy.sort(column, Qt.SortOrder.AscendingOrder)
    ordered = _proxy_rows(proxy, model)
    assert [row["local_apk_version_comparison"] for row in ordered] == [
        "Outdated", "Outdated", "Outdated", "Outdated", "Unknown", "Different",
        "Device-specific", "Newer", "Match",
    ]
    assert [row["package_name"] for row in ordered[:3]] == ["a", "z", "z"]
    assert [row["criticality_rank"] for row in ordered[:4]] == [1, 1, 1, 2]


def test_new_source_default_sort_then_manual_sort_is_respected_during_refresh(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    _settings, create_window = window_store
    window = create_window()
    window.source_mode = "local_apk"
    window._apply_established_source_defaults()
    assert window.table.horizontalHeader().sortIndicatorSection() == window.model.columns.index(
        "local_apk_version_comparison"
    )
    package = window.model.columns.index("package_name")
    window.table.sortByColumn(package, Qt.SortOrder.DescendingOrder)
    window.model.set_rows([{"package_name": "a"}, {"package_name": "b"}])
    assert window.table.horizontalHeader().sortIndicatorSection() == package

    window.source_mode = "device"
    window._apply_established_source_defaults()
    assert window.table.horizontalHeader().sortIndicatorSection() == window.model.columns.index(
        "criticality"
    )


@pytest.mark.parametrize(
    ("relationship", "status_key"),
    [
        ("Outdated", "orange"),
        ("Different", "yellow"),
        ("Unknown", "purple"),
        ("Device-specific", "blue"),
        ("Newer", "green"),
        ("Match", "green"),
    ],
)
def test_local_apk_dual_status_colours_and_neutral_ordinary_cells(
    relationship: str, status_key: str
) -> None:
    from playstore_app_audit.ui.base_window import CRITICALITY

    model = AuditTableModel()
    model.set_rows(
        [{
            "source_mode": "local_apk", "criticality_key": "red",
            "criticality": "Not Found", "local_apk_version_comparison": relationship,
            "package_name": "com.example.app",
        }]
    )
    criticality = model.index(0, model.columns.index("criticality"))
    relationship_index = model.index(0, model.columns.index("local_apk_version_comparison"))
    package = model.index(0, model.columns.index("package_name"))
    assert criticality.data(Qt.ItemDataRole.BackgroundRole) == QColor(
        CRITICALITY["red"]["background"]
    )
    assert relationship_index.data(Qt.ItemDataRole.BackgroundRole) == QColor(
        CRITICALITY[status_key]["background"]
    )
    assert relationship_index.data(Qt.ItemDataRole.ForegroundRole) == QColor(
        CRITICALITY[status_key]["foreground"]
    )
    assert relationship_index.data(Qt.ItemDataRole.FontRole).weight() == 700
    assert package.data(Qt.ItemDataRole.BackgroundRole) is None


def test_selected_local_row_has_no_focus_marker_and_keeps_both_semantics(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    _settings, create_window = window_store
    window = create_window()
    window.source_mode = "local_apk"
    window.model.set_rows(
        [
            {
                "source_mode": "local_apk",
                "criticality_key": "red",
                "criticality": "Not Found",
                "local_apk_version_comparison": "Outdated",
                "package_name": "com.example.app",
            }
        ]
    )
    window.table.selectRow(0)
    current = window.proxy.index(0, window.model.columns.index("package_name"))
    window.table.setCurrentIndex(current)
    app.processEvents()

    delegate = window.table.itemDelegate()
    selected_states = 0
    focus_cells = 0
    selected_colours: dict[str, QColor] = {}
    for column, name in enumerate(window.model.columns):
        index = window.proxy.index(0, column)
        option = QStyleOptionViewItem()
        option.initFrom(window.table)
        option.state |= QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus
        delegate.initStyleOption(option, index)
        selected_states += bool(option.state & QStyle.StateFlag.State_Selected)
        focus_cells += bool(option.state & QStyle.StateFlag.State_HasFocus)
        if name in {"criticality", "local_apk_version_comparison"}:
            selected_colours[name] = option.backgroundBrush.color()

    assert selected_states == 0
    assert focus_cells == 0
    assert selected_colours["criticality"] != selected_colours["local_apk_version_comparison"]


def test_customize_column_groups_partition_the_existing_schema() -> None:
    common, advanced = preferences_ui.custom_column_groups()
    expected = set(schema.MODEL_COLUMNS) - {"criticality", "package_name"}

    assert set(common).isdisjoint(advanced)
    assert set(common) | set(advanced) == expected
    assert {"play_title", "local_apk_location", "installer_source"} <= set(common)
    assert {
        "installed_version_code",
        "local_apk_version_code",
        "target_sdk",
        "min_sdk",
        "installer_package",
        "local_apk_sha256",
        "play_status",
        "play_http_status",
        "updated_source",
    } <= set(advanced)


def test_file_and_adb_keep_whole_row_store_tint() -> None:
    from playstore_app_audit.ui.base_window import CRITICALITY

    model = AuditTableModel()
    model.set_rows(
        [
            {"source_mode": "file", "criticality_key": "green", "package_name": "file"},
            {"source_mode": "device", "criticality_key": "orange", "package_name": "adb"},
        ]
    )
    package = model.columns.index("package_name")
    assert model.index(0, package).data(Qt.ItemDataRole.BackgroundRole) == QColor(
        CRITICALITY["green"]["background"]
    )
    assert model.index(1, package).data(Qt.ItemDataRole.BackgroundRole) == QColor(
        CRITICALITY["orange"]["background"]
    )
