from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLabel

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.insights_window as insights_ui
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


def test_device_snapshot_save_load_and_comparison_round_trip(
    local_state: Path,
) -> None:
    snapshot_path = device_insights.snapshots_dir() / "phone.psaa.json"
    saved_rows = [
        {
            "package_name": "com.example.app",
            "installed_version": "1",
            "installer_source": "Google Play",
            "app_enabled": True,
        },
        {"package_name": "com.removed.app", "installed_version": "1"},
    ]
    device_summary = {"device_id": "phone-a", "model": "Example Phone"}

    assert device_insights.save_snapshot(
        snapshot_path, saved_rows, device_summary
    ) == snapshot_path
    loaded = device_insights.load_snapshot(snapshot_path)
    comparison = device_insights.compare_snapshots(
        [
            {
                "package_name": "com.example.app",
                "installed_version": "2",
                "installer_source": "F-Droid",
                "app_enabled": False,
            },
            {"package_name": "com.new.app", "installed_version": "1"},
        ],
        device_summary,
        loaded,
    )

    assert loaded["format"] == device_insights.DEVICE_SNAPSHOT_FORMAT
    assert loaded["device"] == device_summary
    assert comparison["only_snapshot"] == ["com.removed.app"]
    assert comparison["only_current"] == ["com.new.app"]
    assert comparison["version_differences"] == ["com.example.app"]
    assert comparison["installer_differences"] == ["com.example.app"]
    assert comparison["state_differences"] == ["com.example.app"]


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


def test_changes_history_is_always_in_tools_without_old_history_tree(
    window: MainWindow,
) -> None:
    assert _tools_text(window) == [
        "Advanced Settings…",
        "Changes & History…",
        "Data Maintenance…",
    ]
    action = window.changes_history_action
    assert not hasattr(window, "device_history_menu")
    assert not hasattr(window, "snapshots_menu")
    assert not hasattr(window, "device_inventory_changes_action")

    window.user_settings[state.CHANGES_HISTORY_ENABLED_KEY] = True
    assert _tools_text(window) == [
        "Advanced Settings…",
        "Changes & History…",
        "Data Maintenance…",
    ]
    assert window.changes_history_action is action


def test_advanced_settings_has_no_changes_history_configuration(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def inspect(dialog: QDialog) -> int:
        assert dialog.findChild(QCheckBox, "ChangesHistoryEnabledCheck") is None
        assert dialog.findChild(QCheckBox, "ComparePreviousAuditCheck") is None
        assert dialog.findChild(QCheckBox, "InventoryHistoryCheck") is None
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    window._show_advanced_settings()

    assert window.user_settings[state.CHANGES_HISTORY_ENABLED_KEY] is False
    assert window.user_settings["compare_previous"] is True
    assert window.user_settings["inventory_history_enabled"] is True
    assert "Changes & History…" in _tools_text(window)


def test_dialog_persists_tracking_controls_and_keeps_snapshots_independent(
    window: MainWindow,
    app: QApplication,
    ui_settings: dict[str, object],
) -> None:
    window.source_mode = "device"
    window._results_incomplete = False
    window.current_rows = [{"package_name": "com.example.app"}]
    window.model.set_rows(window.current_rows)

    window._show_changes_history()
    app.processEvents()
    dialog = window._changes_history_dialog
    assert dialog is not None
    assert not dialog.automatic_tracking_check.isChecked()
    assert not dialog.store_tracking_check.isEnabled()
    assert dialog.store_tracking_check.isChecked()
    assert not dialog.device_tracking_check.isEnabled()
    assert dialog.device_tracking_check.isChecked()
    assert dialog.save_snapshot_button.isEnabled()
    assert dialog.compare_snapshot_button.isEnabled()

    dialog.automatic_tracking_check.setChecked(True)
    assert dialog.store_tracking_check.isEnabled()
    assert dialog.device_tracking_check.isEnabled()
    dialog.store_tracking_check.setChecked(False)
    dialog.automatic_tracking_check.setChecked(False)
    assert not dialog.store_tracking_check.isEnabled()
    assert not dialog.device_tracking_check.isEnabled()
    dialog.automatic_tracking_check.setChecked(True)
    assert not dialog.store_tracking_check.isChecked()
    assert dialog.device_tracking_check.isChecked()
    dialog.automatic_tracking_check.setChecked(False)
    dialog.apply_button.click()

    assert ui_settings[state.CHANGES_HISTORY_ENABLED_KEY] is False
    assert ui_settings["compare_previous"] is False
    assert ui_settings["inventory_history_enabled"] is True
    assert dialog.settings_status_label.text() == "Settings saved."
    assert dialog.save_snapshot_button.isEnabled()
    assert dialog.compare_snapshot_button.isEnabled()

    window._show_changes_history()
    app.processEvents()
    dialog = window._changes_history_dialog
    assert dialog is not None
    assert not dialog.automatic_tracking_check.isChecked()
    assert not dialog.store_tracking_check.isChecked()
    assert dialog.device_tracking_check.isChecked()
    dialog.automatic_tracking_check.setChecked(True)
    assert dialog.store_tracking_check.isEnabled()
    assert dialog.device_tracking_check.isEnabled()
    dialog.apply_button.click()
    assert ui_settings[state.CHANGES_HISTORY_ENABLED_KEY] is True
    assert ui_settings["compare_previous"] is False
    assert ui_settings["inventory_history_enabled"] is True


@pytest.mark.parametrize(
    (
        "initial_master",
        "initial_store",
        "updated_master",
        "updated_store",
        "initially_hidden",
        "finally_hidden",
    ),
    [
        (False, True, True, True, True, False),
        (True, True, False, True, False, True),
        (True, True, True, False, False, True),
    ],
)
def test_apply_refreshes_change_column_visibility_immediately(
    window: MainWindow,
    app: QApplication,
    ui_settings: dict[str, object],
    initial_master: bool,
    initial_store: bool,
    updated_master: bool,
    updated_store: bool,
    initially_hidden: bool,
    finally_hidden: bool,
) -> None:
    ui_settings.update(
        {
            state.CHANGES_HISTORY_ENABLED_KEY: initial_master,
            "compare_previous": initial_store,
            "view_preset": "Basic",
        }
    )
    window.user_settings.update(ui_settings)
    window.source_mode = "file"
    change_column = window.model.columns.index("change")
    window._apply_column_visibility(reset_order=False)
    assert window.table.isColumnHidden(change_column) is initially_hidden

    window._show_changes_history()
    app.processEvents()
    dialog = window._changes_history_dialog
    assert dialog is not None
    dialog.automatic_tracking_check.setChecked(updated_master)
    if not dialog.store_tracking_check.isEnabled():
        dialog.automatic_tracking_check.setChecked(True)
    dialog.store_tracking_check.setChecked(updated_store)
    dialog.automatic_tracking_check.setChecked(updated_master)
    dialog.apply_button.click()

    assert window.table.isColumnHidden(change_column) is finally_hidden


@pytest.mark.parametrize(
    (
        "initial_master",
        "initial_device",
        "updated_master",
        "updated_device",
        "initially_hidden",
        "finally_hidden",
    ),
    [
        (False, True, True, True, True, False),
        (True, True, False, True, False, True),
        (True, True, True, False, False, True),
    ],
)
def test_apply_refreshes_device_change_column_visibility_immediately(
    window: MainWindow,
    app: QApplication,
    ui_settings: dict[str, object],
    initial_master: bool,
    initial_device: bool,
    updated_master: bool,
    updated_device: bool,
    initially_hidden: bool,
    finally_hidden: bool,
) -> None:
    ui_settings.update(
        {
            state.CHANGES_HISTORY_ENABLED_KEY: initial_master,
            "inventory_history_enabled": initial_device,
            "view_preset": "Basic",
        }
    )
    window.user_settings.update(ui_settings)
    window.source_mode = "device"
    device_change_column = window.model.columns.index("device_change")
    window._apply_column_visibility(reset_order=False)
    assert window.table.isColumnHidden(device_change_column) is initially_hidden

    window._show_changes_history()
    app.processEvents()
    dialog = window._changes_history_dialog
    assert dialog is not None
    dialog.automatic_tracking_check.setChecked(updated_master)
    if not dialog.device_tracking_check.isEnabled():
        dialog.automatic_tracking_check.setChecked(True)
    dialog.device_tracking_check.setChecked(updated_device)
    dialog.automatic_tracking_check.setChecked(updated_master)
    dialog.apply_button.click()

    assert window.table.isColumnHidden(device_change_column) is finally_hidden


def test_snapshot_save_uses_canonical_default_with_master_off(
    window: MainWindow,
    local_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.user_settings[state.CHANGES_HISTORY_ENABLED_KEY] = False
    window.source_mode = "device"
    window.current_rows = [{"package_name": "com.example.app"}]
    window._device_summary = {"model": "Example Phone"}
    selected_path = local_state / "chosen.psaa.json"
    defaults: list[str] = []

    def choose_snapshot(
        _parent: object, _title: str, default: str, _file_filter: str
    ) -> tuple[str, str]:
        defaults.append(default)
        return str(selected_path), ""

    monkeypatch.setattr(
        insights_ui.QFileDialog, "getSaveFileName", choose_snapshot
    )
    monkeypatch.setattr(insights_ui.QMessageBox, "information", lambda *_args: None)

    window._save_device_snapshot()

    assert Path(defaults[0]).parent == local_state / "device_snapshots"
    assert Path(defaults[0]).name == "Example_Phone_snapshot.psaa.json"
    assert device_insights.load_snapshot(selected_path)["apps"][0][
        "package_name"
    ] == "com.example.app"


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
    section_titles = {
        name: dialog.findChild(QLabel, f"{name}Title").text()
        for name in (
            "StoreChangesSection",
            "DeviceChangesSection",
            "DeviceSnapshotsSection",
        )
    }
    assert section_titles == {
        "StoreChangesSection": "Play Store listing changes",
        "DeviceChangesSection": "Device app inventory changes",
        "DeviceSnapshotsSection": "Device Snapshots",
    }
    assert dialog.automatic_tracking_check.text() == "Enable automatic change tracking"
    assert dialog.store_tracking_check.text() == "Track Play Store listing changes"
    assert dialog.device_tracking_check.text() == "Track device app inventory changes"
    descriptions = {
        label.property("role"): label.text() for label in dialog.findChildren(QLabel)
    }
    assert descriptions["StoreTrackingDescription"] == (
        "Detect availability, Store version and update-status changes between audits."
    )
    assert descriptions["DeviceTrackingDescription"] == (
        "Detect installed, removed, version, installer and enabled-state changes "
        "between scans of the same phone."
    )
    assert dialog.review_store_button.text() == "Review Play Store Changes…"
    assert dialog.settings_status_label.isHidden()
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
            "No meaningful Play Store changes were detected in the current comparison.",
        ),
        (
            {"com.new.app": {"play_status": "available", "play_version": "1"}},
            "2",
            True,
            True,
            "Meaningful Play Store changes are available from the current comparison.",
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


def test_local_apk_success_never_promotes_automatic_history(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.user_settings.update(
        {
            state.CHANGES_HISTORY_ENABLED_KEY: True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window.source_mode = local_apk_audit.SOURCE_MODE
    window.current_rows = [_available_row()]
    monkeypatch.setattr(
        state,
        "save_history",
        lambda _rows: pytest.fail("Local APK promoted Store history"),
    )
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: pytest.fail("Local APK promoted device history"),
    )

    promoted = window._promote_successful_audit(
        AuditRunResult(
            session=1,
            outcome=AuditRunOutcome.SUCCESS,
            rows=list(window.current_rows),
            total_count=1,
            metadata={"source_mode": local_apk_audit.SOURCE_MODE},
        )
    )

    assert promoted is False
