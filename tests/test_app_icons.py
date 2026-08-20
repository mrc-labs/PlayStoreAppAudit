from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.app_icon_metadata as metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.table_window as table_ui
from playstore_app_audit.ui.app_icon_loader import _normalise_icon_url


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_app_icons_are_off_by_default() -> None:
    assert state.DEFAULT_SETTINGS["show_app_icons"] is False


def test_icon_metadata_accepts_only_https_urls() -> None:
    metadata.clear_icon_metadata()
    metadata._remember_result_icon(
        {"appId": "com.example.good", "icon": "https://example.invalid/icon.png"}
    )
    metadata._remember_result_icon(
        {"appId": "com.example.bad", "icon": "http://example.invalid/icon.png"}
    )

    assert metadata.icon_url_for_package("com.example.good") == "https://example.invalid/icon.png"
    assert metadata.icon_url_for_package("com.example.bad") == ""


def test_loader_url_normalisation_rejects_non_https() -> None:
    assert _normalise_icon_url("https://example.invalid/icon.png")
    assert _normalise_icon_url("http://example.invalid/icon.png") == ""
    assert _normalise_icon_url("") == ""


def test_table_icons_are_opt_in_and_use_captured_metadata(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": False})
    monkeypatch.setattr(
        metadata,
        "icon_url_for_package",
        lambda package: "https://example.invalid/icon.png" if package == "com.example.app" else "",
    )

    model = table_ui.AuditTableModel()
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
        "criticality_key": "green",
    }
    model.set_rows([row])
    assert model.rows[0]["play_icon_url"] == "https://example.invalid/icon.png"

    package_column = model.columns.index("package_name")
    index = model.index(0, package_column)
    assert model.data(index, Qt.ItemDataRole.DecorationRole) is None

    expected = QIcon()
    model._icon_loader = SimpleNamespace(icon_for_url=lambda _url: expected)  # type: ignore[assignment]
    model.set_app_icons_enabled(True)
    assert model.data(index, Qt.ItemDataRole.DecorationRole) is expected

    model.deleteLater()
    app.processEvents()


def test_unavailable_rows_do_not_show_stale_icons(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": True})
    monkeypatch.setattr(
        metadata,
        "icon_url_for_package",
        lambda _package: "https://example.invalid/icon.png",
    )

    model = table_ui.AuditTableModel()
    model.set_rows(
        [
            {
                "package_name": "com.example.removed",
                "play_status": "not_found_in_checked_countries",
                "criticality_key": "red",
            }
        ]
    )
    package_column = model.columns.index("package_name")
    index = model.index(0, package_column)
    assert "play_icon_url" not in model.rows[0]
    assert model.data(index, Qt.ItemDataRole.DecorationRole) is None

    model.deleteLater()
    app.processEvents()
