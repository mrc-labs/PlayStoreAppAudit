from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

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


def test_missing_setting_migrates_to_exclude_system_apps_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cache_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(state, "settings_path", lambda: path)
    assert state.load_settings()["exclude_system_source"] is True


def test_explicit_false_setting_is_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"exclude_system_source": False}), encoding="utf-8")
    monkeypatch.setattr(state, "settings_path", lambda: path)
    assert state.load_settings()["exclude_system_source"] is False


def test_reset_settings_restores_exclude_system_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setattr(state, "settings_path", lambda: path)
    reset = state.reset_settings()
    assert reset["exclude_system_source"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["exclude_system_source"] is True


def _patch_window_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: dict[str, object],
    saved: list[dict[str, object]],
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(
        state,
        "save_settings",
        lambda values: saved.append(dict(values)) or dict(values),
    )
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(
        compact_ui,
        "save_settings",
        lambda values: saved.append(dict(values)) or dict(values),
    )
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])


def test_main_window_defaults_checked_and_persists_explicit_choice(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings: dict[str, object] = {"view_preset": "Basic", "recent_sources": []}
    saved: list[dict[str, object]] = []
    _patch_window_settings(monkeypatch, settings, saved)

    window = MainWindow()
    assert window.exclude_system_source_check.isChecked()
    window.exclude_system_source_check.setChecked(False)
    assert saved[-1]["exclude_system_source"] is False
    window.close()
    app.processEvents()


def test_main_window_preserves_explicit_false_choice(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": False,
    }
    saved: list[dict[str, object]] = []
    _patch_window_settings(monkeypatch, settings, saved)

    window = MainWindow()
    assert not window.exclude_system_source_check.isChecked()
    window.close()
    app.processEvents()
