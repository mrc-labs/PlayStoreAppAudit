from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import playstore_app_audit.services.app_icon_disk_cache as disk_cache
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.data_maintenance import (
    CACHE_ACTIONS,
    CLEAR_ALL_CONFIRMATION,
    HISTORY_ACTIONS,
    DataMaintenanceDialog,
)
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "saved_smart_queries": [{"name": "Keep"}],
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(state, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def _callbacks(window: MainWindow):
    return {
        "store_results": window._perform_clear_audit_cache,
        "app_icons": window._perform_clear_app_icon_cache,
        "alternative_store": window._perform_clear_alternative_store_cache,
        "previous_audit_history": window._perform_clear_audit_history,
        "device_inventory_history": window._perform_clear_device_inventory_history,
    }


def _seed_data(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "settings": tmp_path / "settings.json",
        "store": tmp_path / "audit_cache.json",
        "history": tmp_path / "audit_history.json",
        "alternative": tmp_path / "alternative_distribution_cache.json",
        "inventory": tmp_path / "inventory_phone.json",
        "snapshot": tmp_path / "device_snapshots" / "saved.psaa.json",
    }
    paths["snapshot"].parent.mkdir(parents=True, exist_ok=True)
    for key, path in paths.items():
        path.write_text(json.dumps({"store": key}), encoding="utf-8")

    icon_dir = tmp_path / disk_cache.ICON_CACHE_DIRNAME
    icon_dir.mkdir(parents=True, exist_ok=True)
    (icon_dir / "index.json").write_text("{malformed", encoding="utf-8")
    (icon_dir / "orphan.img").write_bytes(b"icon")
    (icon_dir / "interrupted.img.tmp").write_bytes(b"temp")
    paths["icons"] = icon_dir
    return paths


def test_dialog_has_two_sections_exact_actions_and_no_combined_data_clear(
    window: MainWindow,
) -> None:
    dialog = DataMaintenanceDialog(window, _callbacks(window), lambda _message: None)
    try:
        assert dialog.cached_data_group.title() == "Cached data"
        assert dialog.history_group.title() == "History"
        assert tuple(action.title for action in CACHE_ACTIONS) == (
            "Store Results Cache",
            "App Icon Cache",
            "Alternative Store Cache",
        )
        assert tuple(action.title for action in HISTORY_ACTIONS) == (
            "Previous Audit History",
            "Device Inventory History",
        )
        assert set(dialog.action_buttons) == {
            "store_results",
            "app_icons",
            "alternative_store",
            "all_caches",
            "previous_audit_history",
            "device_inventory_history",
        }
        assert dialog.action_buttons["all_caches"].parent() is dialog.cached_data_group
        assert all("Everything" not in button.text() for button in dialog.action_buttons.values())
    finally:
        dialog.deleteLater()


def test_every_confirmation_defaults_to_no_and_names_preserved_scope(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    prompts: list[tuple[str, str, object]] = []
    callbacks = {key: lambda key=key: calls.append(key) for key in _callbacks(window)}
    dialog = DataMaintenanceDialog(window, callbacks, lambda _message: None)

    def question(_parent, title, message, _buttons, default):
        prompts.append((title, message, default))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", question)
    for action in (*CACHE_ACTIONS, *HISTORY_ACTIONS):
        dialog._run(action)
    dialog._clear_all_caches()

    assert calls == []
    assert all(prompt[2] == QMessageBox.StandardButton.No for prompt in prompts)
    messages = " ".join(prompt[1] for prompt in prompts)
    assert "Current results, history and settings will not be deleted" in messages
    assert "Audit evidence, scores, history and settings will not be changed" in messages
    assert "Google Play results, history and settings will not be deleted" in messages
    assert "Device Snapshots" in messages
    assert prompts[-1][1] == CLEAR_ALL_CONFIRMATION


def test_individual_cache_and_history_operations_preserve_other_stores(
    window: MainWindow,
    tmp_path: Path,
) -> None:
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "health_score": 92,
    }
    window.current_rows = [row]
    window.model.set_rows(window.current_rows)

    paths = _seed_data(tmp_path)
    assert window._perform_clear_audit_cache() == "Store Results Cache cleared"
    assert json.loads(paths["store"].read_text(encoding="utf-8")) == {}
    assert paths["alternative"].read_text(encoding="utf-8") != "{}"
    assert paths["icons"].is_dir()
    assert paths["history"].is_file() and paths["inventory"].is_file()
    assert paths["snapshot"].is_file() and paths["settings"].is_file()
    assert window.current_rows == [row]

    paths = _seed_data(tmp_path)
    window._perform_clear_alternative_store_cache()
    assert json.loads(paths["alternative"].read_text(encoding="utf-8")) == {}
    assert paths["store"].read_text(encoding="utf-8") != "{}"
    assert paths["history"].is_file() and paths["settings"].is_file()

    paths = _seed_data(tmp_path)
    window._perform_clear_app_icon_cache()
    assert not paths["icons"].exists()
    assert paths["store"].is_file() and paths["alternative"].is_file()
    assert paths["history"].is_file() and paths["inventory"].is_file()
    assert paths["snapshot"].is_file() and paths["settings"].is_file()
    assert window.current_rows == [row]
    assert row["play_last_update"] == "2026-08-01" and row["health_score"] == 92

    paths = _seed_data(tmp_path)
    window._perform_clear_audit_history()
    assert json.loads(paths["history"].read_text(encoding="utf-8")) == {}
    assert paths["store"].is_file() and paths["alternative"].is_file()
    assert paths["icons"].is_dir() and paths["inventory"].is_file()
    assert paths["snapshot"].is_file() and paths["settings"].is_file()

    paths = _seed_data(tmp_path)
    window._perform_clear_device_inventory_history()
    assert not paths["inventory"].exists()
    assert paths["snapshot"].is_file()
    assert paths["history"].is_file() and paths["store"].is_file()
    assert paths["alternative"].is_file() and paths["icons"].is_dir()
    assert paths["settings"].is_file()


def test_clear_all_caches_clears_exactly_three_caches(
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _seed_data(tmp_path)
    rows = [{"package_name": "com.example.keep", "health_score": 75}]
    window.current_rows = rows
    window.model.set_rows(rows)
    source_mode = window.source_mode
    status: list[str] = []
    dialog = DataMaintenanceDialog(window, _callbacks(window), status.append)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )

    dialog._clear_all_caches()

    assert json.loads(paths["store"].read_text(encoding="utf-8")) == {}
    assert json.loads(paths["alternative"].read_text(encoding="utf-8")) == {}
    assert not paths["icons"].exists()
    assert paths["history"].is_file() and paths["inventory"].is_file()
    assert paths["snapshot"].is_file() and paths["settings"].is_file()
    assert window.current_rows == rows
    assert window.source_mode == source_mode
    assert "saved_smart_queries" in window.user_settings
    assert status == [
        "Store Results Cache, App Icon Cache and Alternative Store Cache cleared"
    ]


def test_clear_all_reports_partial_failure_without_claiming_success(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    statuses: list[str] = []
    errors: list[tuple[str, str]] = []

    def fail_icons() -> None:
        calls.append("icons")
        raise OSError("locked")

    dialog = DataMaintenanceDialog(
        window,
        {
            "store_results": lambda: calls.append("store"),
            "app_icons": fail_icons,
            "alternative_store": lambda: calls.append("alternative"),
            "previous_audit_history": lambda: None,
            "device_inventory_history": lambda: None,
        },
        statuses.append,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, message: errors.append((title, message)),
    )

    dialog._clear_all_caches()

    assert calls == ["store", "icons", "alternative"]
    assert statuses and "incomplete" in statuses[0]
    assert "App Icon Cache" in statuses[0]
    assert errors and "locked" in errors[0][1]
    assert not any(status.endswith("caches cleared") for status in statuses)


def test_data_maintenance_action_and_controls_disable_for_incompatible_work(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert window.data_maintenance_action.isEnabled()

    window._source_operation_active = True
    window._sync_action_availability()
    assert not window.data_maintenance_action.isEnabled()

    window._source_operation_active = False
    monkeypatch.setattr(window.model, "icon_loader_busy", lambda: True)
    window._sync_action_availability()
    assert not window.data_maintenance_action.isEnabled()


def test_fresh_store_action_copy_is_explicitly_non_destructive(window: MainWindow) -> None:
    expected = (
        "Ignore cached Google Play and alternative-store results for this run. "
        "No cache files are deleted; app icons may still come from the icon cache."
    )
    assert window.force_full_refresh_action.text() == "Run with Fresh Store Results"
    assert window.force_full_refresh_action.toolTip() == expected
    assert window.force_full_refresh_action.statusTip() == expected


def test_fresh_store_command_bypasses_results_without_deleting_any_cache(
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _seed_data(tmp_path)
    before = {
        key: path.read_bytes()
        for key, path in paths.items()
        if key in {"store", "alternative"}
    }
    icon_files = {
        path.name: path.read_bytes()
        for path in paths["icons"].iterdir()
    }
    starts: list[bool] = []
    monkeypatch.setattr(window, "_start_audit", lambda: starts.append(True))

    window._force_full_refresh()

    assert starts == [True]
    assert window._force_refresh_next is True
    assert {key: paths[key].read_bytes() for key in before} == before
    assert {
        path.name: path.read_bytes() for path in paths["icons"].iterdir()
    } == icon_files
