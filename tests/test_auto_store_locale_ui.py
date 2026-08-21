from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.services.store_locale as store_locale
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.services.store_locale import StoreLocale
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _window(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "store_language": "auto",
        state.STORE_LANGUAGE_AUTO_MIGRATION_KEY: True,
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "add_recent_source", lambda _path: None)
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)
    return MainWindow()


def test_phone_scan_applies_android_locale_to_auto_store_context(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(app, monkeypatch)
    monkeypatch.setattr(window, "_get_authorised_adb", lambda: None)
    monkeypatch.setattr(window, "_find_adb", lambda: "adb")
    monkeypatch.setattr(
        store_locale,
        "detect_android_store_locale",
        lambda _adb: StoreLocale("it", "ch", "it-CH", "test"),
    )

    try:
        window._on_adb_scan_done(
            [{"app_name": "Example", "package_name": "com.example.app"}],
            set(),
        )

        assert window.source_mode == "device"
        assert window.country_edit.text() == "ch"
        assert store_locale.resolve_store_language("auto", "ch") == "it"
        assert "it-CH" in window.country_edit.toolTip()
        assert "Android system locale: it-CH" in window.source_label.toolTip()
    finally:
        store_locale.set_active_device_store_locale(None)
        window.close()
        app.processEvents()


def test_loading_file_clears_phone_language_context(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window = _window(app, monkeypatch)
    store_locale.set_active_device_store_locale(StoreLocale("it", "ch", "it-CH", "test"))
    source = tmp_path / "apps.csv"
    source.write_text("package_name\ncom.example.app\n", encoding="utf-8")

    try:
        window.country_edit.setText("ch")
        window._load_input_file(str(source))

        assert window.source_mode == "file"
        assert store_locale.active_device_store_locale() is None
        assert store_locale.resolve_store_language("auto", "ch") == "de"
    finally:
        store_locale.set_active_device_store_locale(None)
        window.close()
        app.processEvents()
