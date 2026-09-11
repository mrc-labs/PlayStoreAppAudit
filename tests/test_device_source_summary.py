from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.main_window import MainWindow
from playstore_app_audit.ui.results_window import _device_source_identity


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_device_source_identity_handles_partial_metadata() -> None:
    assert (
        _device_source_identity(
            {
                "manufacturer": "Google",
                "model": "Pixel 9 Pro",
                "android_version": "16",
                "android_api": "36",
            }
        )
        == "Google Pixel 9 Pro • Android 16 (API 36)"
    )
    assert _device_source_identity({"model": "Pixel", "android_api": "36"}) == (
        "Pixel • Android API 36"
    )
    assert _device_source_identity({"model": "Pixel", "android_version": "16"}) == (
        "Pixel • Android 16"
    )
    assert _device_source_identity({"model": "Pixel"}) == "Pixel"
    assert _device_source_identity({"android_version": "16", "android_api": "36"}) == (
        "Android 16 (API 36)"
    )
    assert _device_source_identity({}) == ""


def test_device_summary_backend_remains_available_without_the_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    getprop = "\n".join(
        (
            "[ro.product.manufacturer]: [Google]",
            "[ro.product.model]: [Pixel 9 Pro]",
            "[ro.build.version.release]: [16]",
            "[ro.build.version.sdk]: [36]",
            "[ro.build.version.security_patch]: [2026-08-05]",
        )
    )

    def fake_run(_adb: str, args: list[str], _timeout: int) -> str:
        return "serial-1234\n" if args == ["get-serialno"] else getprop

    monkeypatch.setattr(device_insights, "_run", fake_run)
    summary = device_insights.collect_device_summary("adb", 12, 5)

    assert summary["manufacturer"] == "Google"
    assert summary["model"] == "Pixel 9 Pro"
    assert summary["android_version"] == "16"
    assert summary["android_api"] == "36"
    assert summary["serial_masked"] == "••••1234"
    assert summary["device_id"] != "serial-1234"
    assert summary["third_party_packages"] == 7


def test_phone_scan_enriches_app_source_with_connected_device(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": True,
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(MainWindow, "_get_authorised_adb", lambda self: "adb")
    monkeypatch.setattr(MainWindow, "_find_adb", lambda self: None)
    monkeypatch.setattr(
        device_insights,
        "collect_device_summary",
        lambda _adb, total, system: {
            "manufacturer": "Google",
            "model": "Pixel 9 Pro",
            "android_version": "16",
            "android_api": "36",
            "security_patch": "2026-08-05",
            "serial_masked": "••••1234",
            "total_packages": total,
            "system_packages": system,
            "third_party_packages": total - system,
        },
    )

    window = MainWindow()
    window._on_adb_scan_done(
        [{"app_name": "Example", "package_name": "com.example.app"}],
        set(),
    )

    text = window.source_label.text()
    assert text.startswith("Phone source: Google Pixel 9 Pro • Android 16 (API 36) • ")
    assert "1 third-party packages loaded" in text
    assert "system apps excluded during ADB scan" in text
    assert window.source_label.toolTip() == (
        "Device: Google Pixel 9 Pro • Android 16 (API 36)\n"
        "Security patch: 2026-08-05\n"
        "Serial: ••••1234"
    )

    window.close()
    app.processEvents()
