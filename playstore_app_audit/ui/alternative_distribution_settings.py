from __future__ import annotations

import threading
from collections.abc import Mapping

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from playstore_app_audit.services import alternative_distribution as alternative


class AlternativeDistributionSettingsPage(QWidget):
    connection_result = Signal(str, str)

    def __init__(self, settings: Mapping[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AlternativeDistributionSettings")
        raw = alternative.alternative_settings(settings)
        fdroid = raw.get("fdroid_main") if isinstance(raw.get("fdroid_main"), dict) else {}
        aptoide = raw.get("aptoide") if isinstance(raw.get("aptoide"), dict) else {}
        self._api_key_protected = str(aptoide.get("api_key_protected") or "")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.fdroid_enabled = QCheckBox("Enable F-Droid main-repository checks")
        self.fdroid_enabled.setObjectName("FDroidProviderEnabledCheck")
        self.fdroid_enabled.setChecked(bool(fdroid.get("enabled", True)))
        root.addWidget(self.fdroid_enabled)
        fdroid_note = QLabel(
            "Built-in provider using the official active main-repository exact-package API. "
            "No credentials are required; archive and third-party repositories are not checked."
        )
        fdroid_note.setWordWrap(True)
        fdroid_note.setObjectName("Muted")
        root.addWidget(fdroid_note)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(separator)

        aptoide_title = QLabel("Aptoide — Advanced provider, authorized API access required")
        title_font = aptoide_title.font()
        title_font.setBold(True)
        aptoide_title.setFont(title_font)
        aptoide_title.setWordWrap(True)
        root.addWidget(aptoide_title)
        aptoide_note = QLabel(
            "Requires authorized access to the Aptoide API. Configure credentials associated "
            "with your permitted Aptoide account/store and ensure your use complies with "
            "Aptoide's applicable terms. Play Store App Audit does not grant or verify access."
        )
        aptoide_note.setWordWrap(True)
        aptoide_note.setObjectName("Muted")
        root.addWidget(aptoide_note)

        self.aptoide_enabled = QCheckBox("Enable Aptoide checks")
        self.aptoide_enabled.setObjectName("AptoideProviderEnabledCheck")
        self.aptoide_enabled.setChecked(bool(aptoide.get("enabled", False)))
        root.addWidget(self.aptoide_enabled)

        form = QFormLayout()
        self.store_name = QLineEdit(str(aptoide.get("store_name") or ""))
        self.store_name.setObjectName("AptoideStoreNameEdit")
        self.store_name.setPlaceholderText("authorized-store-name")
        self.store_name.setToolTip(
            "Aptoide store identifier associated with your authorized API access."
        )
        form.addRow("Store name", self.store_name)

        key_row = QHBoxLayout()
        self.api_key = QLineEdit()
        self.api_key.setObjectName("AptoideApiKeyEdit")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText(
            "Saved protected credential" if self._api_key_protected else "Enter API key"
        )
        self.api_key.setToolTip(
            "The plaintext API key is never displayed after saving. Enter a value to replace it."
        )
        key_row.addWidget(self.api_key, 1)
        self.replace_button = QPushButton("Replace")
        self.replace_button.setObjectName("ReplaceAptoideCredentialButton")
        self.replace_button.clicked.connect(self._replace_credential)
        key_row.addWidget(self.replace_button)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setObjectName("RemoveAptoideCredentialButton")
        self.remove_button.clicked.connect(self._remove_credential)
        key_row.addWidget(self.remove_button)
        form.addRow("API key", key_row)
        root.addLayout(form)

        action_row = QHBoxLayout()
        self.test_button = QPushButton("Test connection")
        self.test_button.setObjectName("TestAptoideConnectionButton")
        self.test_button.clicked.connect(self._test_connection)
        action_row.addWidget(self.test_button)
        self.credential_status = QLabel()
        self.credential_status.setObjectName("AptoideCredentialStatus")
        self.credential_status.setWordWrap(True)
        action_row.addWidget(self.credential_status, 1)
        root.addLayout(action_row)

        credential = alternative.aptoide_credential(settings)
        if self._api_key_protected and not credential.available:
            self.credential_status.setText(credential.message)
            self.aptoide_enabled.setChecked(False)
        elif credential.available:
            self.credential_status.setText("A protected API credential is saved for this device.")
        else:
            self.credential_status.setText("No Aptoide API credential is saved.")

        self.info_toggle = QToolButton()
        self.info_toggle.setObjectName("ProviderAvailabilityToggle")
        self.info_toggle.setText("Provider availability and limitations")
        self.info_toggle.setCheckable(True)
        self.info_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.info_toggle.setArrowType(Qt.ArrowType.RightArrow)
        root.addWidget(self.info_toggle)
        self.info_panel = QWidget()
        self.info_panel.setObjectName("ProviderAvailabilityPanel")
        info_layout = QVBoxLayout(self.info_panel)
        info_layout.setContentsMargins(12, 2, 0, 0)
        info_layout.setSpacing(9)
        for item in alternative.PROVIDER_INFORMATION:
            heading = QLabel(f"<b>{item['name']}</b> — {item['status']}")
            heading.setWordWrap(True)
            info_layout.addWidget(heading)
            explanation = QLabel(str(item["explanation"]))
            explanation.setWordWrap(True)
            explanation.setObjectName("Muted")
            info_layout.addWidget(explanation)
            links = QLabel(
                " · ".join(
                    f'<a href="{url}">{label}</a>' for label, url in item["links"]
                )
            )
            links.setOpenExternalLinks(False)
            links.linkActivated.connect(self._open_official_link)
            links.setWordWrap(True)
            info_layout.addWidget(links)
        self.info_panel.hide()
        self.info_toggle.toggled.connect(self._toggle_information)
        root.addWidget(self.info_panel)
        root.addStretch(1)

        self.connection_result.connect(self._on_connection_result)

    @staticmethod
    def _open_official_link(url: str) -> None:
        parsed = QUrl(url)
        if parsed.isValid() and parsed.scheme() == "https":
            QDesktopServices.openUrl(parsed)

    def _toggle_information(self, expanded: bool) -> None:
        self.info_panel.setVisible(expanded)
        self.info_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def _replace_credential(self) -> None:
        value = self.api_key.text()
        if not value:
            self.credential_status.setText("Enter a new API key before replacing the credential.")
            return
        self._api_key_protected = alternative.protect_secret(value)
        self.api_key.clear()
        self.api_key.setPlaceholderText("Saved protected credential")
        self.credential_status.setText("Replacement credential is ready to save.")

    def _remove_credential(self) -> None:
        self._api_key_protected = ""
        self.api_key.clear()
        self.api_key.setPlaceholderText("Enter API key")
        self.aptoide_enabled.setChecked(False)
        self.credential_status.setText("Aptoide credential will be removed when settings are saved.")

    def _current_plaintext_key(self) -> str:
        entered = self.api_key.text()
        if entered:
            return entered
        result = alternative.unprotect_secret(self._api_key_protected)
        return result.value if result.available else ""

    def _test_connection(self) -> None:
        store_name = self.store_name.text().strip().lower()
        api_key = self._current_plaintext_key()
        if not alternative.valid_aptoide_store_name(store_name):
            self.credential_status.setText("Enter the authorized Aptoide store identifier.")
            return
        if not api_key:
            self.credential_status.setText("Enter or restore an available Aptoide API key.")
            return
        self.test_button.setEnabled(False)
        self.credential_status.setText("Testing the authorized Aptoide API connection…")

        def worker() -> None:
            status, message = alternative.AptoideProvider(store_name, api_key).test_connection()
            self.connection_result.emit(status, message)

        threading.Thread(target=worker, daemon=True).start()

    def _on_connection_result(self, _status: str, message: str) -> None:
        self.test_button.setEnabled(True)
        self.credential_status.setText(message)

    def reset_to_defaults(self) -> None:
        self.fdroid_enabled.setChecked(True)
        self.aptoide_enabled.setChecked(False)
        self.store_name.clear()
        self._remove_credential()

    def configuration(self) -> dict[str, dict[str, object]]:
        entered = self.api_key.text()
        protected = alternative.protect_secret(entered) if entered else self._api_key_protected
        return {
            "fdroid_main": {"enabled": self.fdroid_enabled.isChecked()},
            "aptoide": {
                "enabled": self.aptoide_enabled.isChecked(),
                "store_name": self.store_name.text().strip().lower(),
                "api_key_protected": protected,
            },
        }
