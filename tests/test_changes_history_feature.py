from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QGroupBox

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def local_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(state, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    return tmp_path


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_fresh_and_legacy_default_only_settings_migrate_master_off(
    local_state: Path,
) -> None:
    assert state.DEFAULT_SETTINGS[state.CHANGES_HISTORY_ENABLED_KEY] is False
    assert state.load_settings()[state.CHANGES_HISTORY_ENABLED_KEY] is False
    persisted = json.loads(state.settings_path().read_text(encoding="utf-8"))
    assert persisted[state.CHANGES_HISTORY_ENABLED_KEY] is False

    state.settings_path().write_text(
        json.dumps({"inventory_history_enabled": True}), encoding="utf-8"
    )
    assert state.load_settings()[state.CHANGES_HISTORY_ENABLED_KEY] is False


@pytest.mark.parametrize("evidence", ["store_setting", "store_history", "inventory", "snapshot"])
def test_real_use_evidence_migrates_master_on_once(
    local_state: Path, evidence: str
) -> None:
    settings: dict[str, object] = {"inventory_history_enabled": True}
    if evidence == "store_setting":
        settings["compare_previous"] = True
    elif evidence == "store_history":
        _write_json(
            state.history_path(),
            {"com.example.app": {"play_status": "available"}},
        )
    elif evidence == "inventory":
        _write_json(local_state / "inventory_device-a.json", {"apps": {}})
    else:
        _write_json(
            local_state / "device_snapshots" / "device.psaa.json",
            {"format": device_insights.DEVICE_SNAPSHOT_FORMAT, "apps": []},
        )
    _write_json(state.settings_path(), settings)

    migrated = state.load_settings()

    assert migrated[state.CHANGES_HISTORY_ENABLED_KEY] is True
    assert json.loads(state.settings_path().read_text(encoding="utf-8"))[
        state.CHANGES_HISTORY_ENABLED_KEY
    ] is True

    state.save_settings({state.CHANGES_HISTORY_ENABLED_KEY: False})
    assert state.load_settings()[state.CHANGES_HISTORY_ENABLED_KEY] is False


def test_explicit_master_off_stays_off_and_preserves_all_retained_data(
    local_state: Path,
) -> None:
    history = {"com.example.app": {"play_status": "available"}}
    inventory = {"device": {"device_id": "a"}, "apps": {}}
    snapshot = {"format": device_insights.DEVICE_SNAPSHOT_FORMAT, "apps": []}
    _write_json(state.history_path(), history)
    inventory_path = local_state / "inventory_device-a.json"
    snapshot_path = local_state / "device_snapshots" / "saved.psaa.json"
    _write_json(inventory_path, inventory)
    _write_json(snapshot_path, snapshot)
    _write_json(
        state.settings_path(),
        {state.CHANGES_HISTORY_ENABLED_KEY: False, "compare_previous": True},
    )

    assert state.load_settings()[state.CHANGES_HISTORY_ENABLED_KEY] is False
    assert json.loads(state.history_path().read_text(encoding="utf-8")) == history
    assert json.loads(inventory_path.read_text(encoding="utf-8")) == inventory
    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == snapshot


@pytest.fixture
def ui_settings(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": True,
        "changes_history_enabled": False,
        "compare_previous": True,
        "inventory_history_enabled": True,
    }

    def load() -> dict[str, object]:
        return dict(settings)

    def save(values: dict[str, object]) -> dict[str, object]:
        settings.update(values)
        return dict(settings)

    monkeypatch.setattr(state, "load_settings", load)
    monkeypatch.setattr(state, "save_settings", save)
    monkeypatch.setattr(compact_ui, "load_settings", load)
    monkeypatch.setattr(compact_ui, "save_settings", save)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    return settings


@pytest.fixture
def window(app: QApplication, ui_settings: dict[str, object]) -> MainWindow:
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def _tools_text(window: MainWindow) -> list[str]:
    return [action.text() for action in window.tools_menu.actions() if not action.isSeparator()]


def test_master_controls_final_tools_menu_without_old_history_tree(
    window: MainWindow,
) -> None:
    assert _tools_text(window) == ["Advanced Settings…", "Data Maintenance…"]
    assert window.changes_history_action is None
    assert not hasattr(window, "device_history_menu")
    assert not hasattr(window, "snapshots_menu")
    assert not hasattr(window, "device_inventory_changes_action")

    window.user_settings[state.CHANGES_HISTORY_ENABLED_KEY] = True
    window._sync_changes_history_action()
    first_action = window.changes_history_action
    window._sync_changes_history_action()

    assert _tools_text(window) == [
        "Advanced Settings…",
        "Changes & History…",
        "Data Maintenance…",
    ]
    assert window.changes_history_action is first_action


def test_advanced_master_disables_children_and_refreshes_menu_immediately(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def enable_master(dialog: QDialog) -> int:
        master = dialog.findChild(QCheckBox, "ChangesHistoryEnabledCheck")
        store = dialog.findChild(QCheckBox, "ComparePreviousAuditCheck")
        device = dialog.findChild(QCheckBox, "InventoryHistoryCheck")
        assert master is not None and not master.isChecked()
        assert store is not None and not store.isEnabled() and store.isChecked()
        assert device is not None and not device.isEnabled() and device.isChecked()
        master.setChecked(True)
        assert store.isEnabled() and device.isEnabled()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", enable_master)
    window._show_advanced_settings()

    assert window.user_settings[state.CHANGES_HISTORY_ENABLED_KEY] is True
    assert window.changes_history_action is not None
    assert "Changes & History…" in _tools_text(window)

    def disable_master(dialog: QDialog) -> int:
        master = dialog.findChild(QCheckBox, "ChangesHistoryEnabledCheck")
        store = dialog.findChild(QCheckBox, "ComparePreviousAuditCheck")
        device = dialog.findChild(QCheckBox, "InventoryHistoryCheck")
        assert master is not None and master.isChecked()
        assert store is not None and store.isEnabled() and store.isChecked()
        assert device is not None and device.isEnabled() and device.isChecked()
        master.setChecked(False)
        assert not store.isEnabled() and store.isChecked()
        assert not device.isEnabled() and device.isChecked()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", disable_master)
    window._show_advanced_settings()

    assert window.user_settings[state.CHANGES_HISTORY_ENABLED_KEY] is False
    assert window.user_settings["compare_previous"] is True
    assert window.user_settings["inventory_history_enabled"] is True
    assert window.changes_history_action is None
    assert "Changes & History…" not in _tools_text(window)


def test_dialog_sections_and_current_evidence_prerequisites(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.user_settings.update(
        {
            state.CHANGES_HISTORY_ENABLED_KEY: True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window._sync_changes_history_action()
    window.source_mode = "device"
    window._results_incomplete = False
    window.current_rows = [
        {
            "package_name": "com.example.app",
            state.AUDIT_CHANGES_FIELD: [
                {"type": "store_version_changed", "previous": "1", "current": "2"}
            ],
        }
    ]
    window.model.set_rows(window.current_rows)
    window._store_comparison_had_baseline = True
    window._last_inventory_changes = {"had_previous": True, "counts": {}}

    window._show_changes_history()
    app.processEvents()
    dialog = window._changes_history_dialog
    assert dialog is not None
    groups = {group.objectName(): group.title() for group in dialog.findChildren(QGroupBox)}
    assert groups == {
        "StoreChangesSection": "Store changes",
        "DeviceChangesSection": "Device changes",
        "DeviceSnapshotsSection": "Device Snapshots",
    }
    assert not dialog.review_store_button.isHidden()
    assert not dialog.review_device_button.isHidden()
    assert dialog.save_snapshot_button.isEnabled()
    assert dialog.compare_snapshot_button.isEnabled()

    window.current_rows = [{"package_name": "com.example.app"}]
    window.model.set_rows(window.current_rows)
    window._store_comparison_had_baseline = False
    window._last_inventory_changes = {}
    window.source_mode = "file"
    monkeypatch.setattr(state, "has_meaningful_previous_audit_history", lambda: True)
    window._show_changes_history()
    app.processEvents()
    dialog = window._changes_history_dialog
    assert dialog is not None
    assert dialog.review_store_button.isHidden()
    assert "first successful comparable audit" in dialog.store_message_label.text()
    assert dialog.review_device_button.isHidden()
    assert not dialog.save_snapshot_button.isEnabled()
    assert not dialog.compare_snapshot_button.isEnabled()


@pytest.mark.parametrize(
    ("history", "current_version", "expected_baseline", "expected_review", "message"),
    [
        (
            {"com.old.app": {"play_status": "available", "play_version": "1"}},
            "1",
            False,
            False,
            "first successful comparable audit",
        ),
        (
            {"com.new.app": {"play_status": "available", "play_version": "1"}},
            "1",
            True,
            False,
            "No meaningful Store changes were detected in the current comparison.",
        ),
        (
            {"com.new.app": {"play_status": "available", "play_version": "1"}},
            "2",
            True,
            True,
            "Meaningful changes are available from the current comparison.",
        ),
    ],
)
def test_store_review_reflects_current_comparable_baseline_and_changes(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    history: dict[str, dict[str, object]],
    current_version: str,
    expected_baseline: bool,
    expected_review: bool,
    message: str,
) -> None:
    window.user_settings.update(
        {
            state.CHANGES_HISTORY_ENABLED_KEY: True,
            "compare_previous": True,
            "inventory_history_enabled": False,
        }
    )
    window._sync_changes_history_action()
    window.source_mode = "file"
    monkeypatch.setattr(compact_ui, "load_history", lambda: history)
    monkeypatch.setattr(state, "save_history", lambda _rows: None)
    window._audit_session += 1
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=window._audit_session,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[
                {
                    "package_name": "com.new.app",
                    "play_status": "available",
                    "play_version": current_version,
                }
            ],
            live_completed_count=1,
            total_count=1,
            metadata={"source_mode": "file"},
        )
    )
    app.processEvents()

    assert window._store_comparison_had_baseline is expected_baseline
    window._show_changes_history()
    app.processEvents()
    dialog = window._changes_history_dialog
    assert dialog is not None
    assert (not dialog.review_store_button.isHidden()) is expected_review
    store_message = dialog.store_message_label.text()
    assert message in store_message
    if not expected_baseline:
        assert "No meaningful Store changes were detected" not in store_message


def _available_row() -> dict[str, object]:
    return {
        "package_name": "com.example.app",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "play_version": "2",
        "change": "stale",
        "device_change": "Version changed",
        state.AUDIT_CHANGES_FIELD: [
            {"type": "store_version_changed", "previous": "1", "current": "2"}
        ],
    }


def test_master_off_prevents_comparison_promotion_and_annotations(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    window.user_settings.update(
        {
            state.CHANGES_HISTORY_ENABLED_KEY: False,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window.source_mode = "device"
    window.device_apps_all = [{"package_name": "com.example.app"}]
    window._device_summary = {"device_id": "device-a"}
    monkeypatch.setattr(
        compact_ui,
        "load_history",
        lambda: pytest.fail("master Off loaded Store history"),
    )
    monkeypatch.setattr(state, "save_history", lambda _rows: calls.append("store"))
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: calls.append("device") or {},
    )
    window._audit_session = 41
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=41,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row()],
            live_completed_count=1,
            total_count=1,
        )
    )
    app.processEvents()

    assert calls == []
    row = window.current_rows[0]
    assert row.get("change") == ""
    assert "device_change" not in row
    assert state.AUDIT_CHANGES_FIELD not in row
    assert "_device_inventory_had_previous" not in row
    assert window._last_inventory_changes == {}


@pytest.mark.parametrize(
    ("store_child", "device_child", "expected"),
    [
        (False, True, ["device"]),
        (True, False, ["store"]),
        (True, True, ["store", "device"]),
    ],
)
def test_master_on_children_gate_automatic_promotions_independently(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    store_child: bool,
    device_child: bool,
    expected: list[str],
) -> None:
    calls: list[str] = []
    window.user_settings.update(
        {
            state.CHANGES_HISTORY_ENABLED_KEY: True,
            "compare_previous": store_child,
            "inventory_history_enabled": device_child,
        }
    )
    window.source_mode = "device"
    window.current_rows = [_available_row()]
    window._device_summary = {"device_id": "device-a"}
    monkeypatch.setattr(state, "save_history", lambda _rows: calls.append("store"))
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: calls.append("device") or {"had_previous": True},
    )
    result = AuditRunResult(
        session=1,
        outcome=AuditRunOutcome.SUCCESS,
        rows=list(window.current_rows),
        total_count=1,
    )

    window._promote_successful_audit(result)

    assert calls == expected
