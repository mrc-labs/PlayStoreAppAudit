from __future__ import annotations

import os
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.alternative_distribution as alternative
import playstore_app_audit.services.config_secret_protection as secrets
import playstore_app_audit.services.state as state
from playstore_app_audit.ui.alternative_distribution_settings import (
    AlternativeDistributionSettingsPage,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture(autouse=True)
def stable_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "local_machine_identity", lambda: "settings-machine")
    monkeypatch.setattr(secrets, "local_user_identity", lambda: "settings-user")


def test_provider_defaults_and_store_persistence() -> None:
    settings = state.load_settings()
    config = settings["alternative_distribution"]

    assert config["fdroid_main"]["enabled"] is True
    assert config["aptoide"]["enabled"] is False


def test_settings_widget_masks_replaces_removes_and_expands_information(
    app: QApplication,
) -> None:
    page = AlternativeDistributionSettingsPage(state.load_settings())
    page.api_key.setText("synthetic-ui-key")
    assert page.api_key.echoMode() == page.api_key.EchoMode.Password
    page.replace_button.click()

    configured = page.configuration()
    protected = configured["aptoide"]["api_key_protected"]
    assert protected.startswith("v1:")
    assert "synthetic-ui-key" not in protected
    assert page.api_key.text() == ""
    assert page.info_toggle.text() == "Provider availability and limitations"
    assert (
        page.info_toggle.toolButtonStyle()
        is Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    )

    page.info_toggle.setChecked(True)
    assert page.info_panel.isVisibleTo(page)
    rendered = " ".join(
        str(item["name"]) + " " + str(item["status"])
        for item in alternative.PROVIDER_INFORMATION
    )
    for provider in (
        "F-Droid",
        "Aptoide",
        "Samsung Galaxy Store",
        "Huawei AppGallery",
        "Amazon Appstore",
        "APKMirror",
        "APKPure",
        "Uptodown",
    ):
        assert provider in rendered
    assert all(url.startswith("https://") for item in alternative.PROVIDER_INFORMATION for _label, url in item["links"])

    page.remove_button.click()
    removed = page.configuration()
    assert removed["aptoide"]["api_key_protected"] == ""
    assert removed["aptoide"]["enabled"] is False
    page.deleteLater()
    app.processEvents()


def test_decryption_failure_disables_aptoide_but_retains_ciphertext(
    app: QApplication,
) -> None:
    settings = state.load_settings()
    settings["alternative_distribution"]["aptoide"] = {
        "enabled": True,
        "store_name": "authorized-store",
        "api_key_protected": "v1:invalid-ciphertext",
    }

    page = AlternativeDistributionSettingsPage(settings)

    assert not page.aptoide_enabled.isChecked()
    assert "cannot be used on this device" in page.credential_status.text()
    assert page.configuration()["aptoide"]["api_key_protected"] == "v1:invalid-ciphertext"
    page.deleteLater()
    app.processEvents()


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("ok", "Authorized connection succeeded."),
        ("configuration_error", "Authorization configuration failed."),
        ("network_error", "Provider network failed."),
    ],
)
def test_connection_result_states_are_presented(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    message: str,
) -> None:
    settings = alternative.replace_aptoide_credential(state.load_settings(), "synthetic-test-key")
    settings["alternative_distribution"]["aptoide"].update(
        {"enabled": True, "store_name": "authorized-store"}
    )
    monkeypatch.setattr(
        alternative.AptoideProvider,
        "test_connection",
        lambda _self: (status, message),
    )
    page = AlternativeDistributionSettingsPage(settings)

    page.test_button.click()
    deadline = time.monotonic() + 2
    while page.credential_status.text() != message and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    assert page.credential_status.text() == message
    assert page.test_button.isEnabled()
    page.deleteLater()
    app.processEvents()
