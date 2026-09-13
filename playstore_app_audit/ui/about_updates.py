"""About dialog with integrated asynchronous update status presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPalette, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from playstore_app_audit import __version__
from playstore_app_audit.resources import ensure_runtime_icon

AUTO_UPDATE_CHECK_LABEL = "Check for updates automatically at startup"


class AboutUpdatesDialog(QDialog):
    """Product About surface that also owns update-check presentation."""

    check_requested = Signal()
    startup_check_changed = Signal(bool)
    release_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._release_url = ""
        self.setObjectName("AboutUpdatesDialog")
        self.setWindowTitle("About Play Store App Audit")
        self.setMinimumWidth(560)
        self.resize(620, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(16)
        icon = QLabel()
        icon.setObjectName("AboutProductIcon")
        pixmap = QPixmap(str(ensure_runtime_icon()))
        if not pixmap.isNull():
            icon.setPixmap(
                pixmap.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        icon.setFixedSize(64, 64)
        header.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        identity = QVBoxLayout()
        identity.setSpacing(3)
        title = QLabel("Play Store App Audit")
        title.setObjectName("AboutTitle")
        title_font = QFont(title.font())
        title_font.setPointSizeF(title_font.pointSizeF() + 5)
        title_font.setBold(True)
        title.setFont(title_font)
        identity.addWidget(title)

        tagline = QLabel("Audit Android apps with Store, device and local-package evidence.")
        tagline.setObjectName("AboutTagline")
        tagline.setWordWrap(True)
        tagline_font = QFont(tagline.font())
        tagline_font.setPointSizeF(tagline_font.pointSizeF() + 1)
        tagline.setFont(tagline_font)
        identity.addWidget(tagline)

        version = QLabel(f"Version {__version__}")
        version.setObjectName("AboutVersion")
        version.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        identity.addWidget(version)
        header.addLayout(identity, 1)
        root.addLayout(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(separator)

        update_card = QFrame()
        update_card.setObjectName("AboutUpdateCard")
        update_card.setFrameShape(QFrame.Shape.StyledPanel)
        update_layout = QVBoxLayout(update_card)
        update_layout.setContentsMargins(16, 14, 16, 14)
        update_layout.setSpacing(9)

        self.update_title = QLabel("Checking for updates…")
        self.update_title.setObjectName("AboutUpdateStatusTitle")
        status_font = QFont(self.update_title.font())
        status_font.setBold(True)
        self.update_title.setFont(status_font)
        update_layout.addWidget(self.update_title)

        self.update_detail = QLabel(
            f"Version {__version__} is installed. Looking for the latest stable release."
        )
        self.update_detail.setObjectName("AboutUpdateStatusDetail")
        self.update_detail.setWordWrap(True)
        self.update_detail.setMinimumHeight(self.update_detail.fontMetrics().lineSpacing() * 2 + 2)
        update_layout.addWidget(self.update_detail)

        action_row = QHBoxLayout()
        self.update_action = QPushButton("Check Again")
        self.update_action.setObjectName("AboutUpdateAction")
        self.update_action.clicked.connect(self._handle_update_action)
        update_action_policy = self.update_action.sizePolicy()
        update_action_policy.setRetainSizeWhenHidden(True)
        self.update_action.setSizePolicy(update_action_policy)
        self.update_action.hide()
        action_row.addWidget(self.update_action)
        action_row.addStretch(1)
        update_layout.addLayout(action_row)

        root.addWidget(update_card)

        self.startup_check = QCheckBox(AUTO_UPDATE_CHECK_LABEL)
        self.startup_check.setObjectName("AboutStartupUpdateCheck")
        self.startup_check.setToolTip(
            "Disable this to stop background update checks when Play Store App Audit starts. "
            "Opening About still checks for updates every time."
        )
        self.startup_check.toggled.connect(self.startup_check_changed)
        root.addWidget(self.startup_check)

        about_text = QLabel(
            "<b>Created by MRC</b><br><br>"
            "Play Store App Audit checks Android package identities against public Google Play "
            "listings and can combine Store, connected-device and local APK evidence.<br><br>"
            "Unofficial utility. Not affiliated with or endorsed by Google."
        )
        about_text.setObjectName("AboutProductInfo")
        about_text.setWordWrap(True)
        root.addWidget(about_text)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        root.addWidget(buttons)

    def set_startup_check_enabled(self, enabled: bool) -> None:
        self.startup_check.blockSignals(True)
        self.startup_check.setChecked(bool(enabled))
        self.startup_check.blockSignals(False)

    def set_checking(self) -> None:
        self._release_url = ""
        self.update_title.setText("Checking for updates…")
        self.update_detail.setText(
            f"Version {__version__} is installed. Looking for the latest stable release."
        )
        self.update_action.hide()

    def set_up_to_date(self) -> None:
        self._release_url = ""
        self.update_title.setText("You're up to date")
        self.update_detail.setText(
            f"You're running Play Store App Audit {__version__}. "
            "This is the latest available version."
        )
        self.update_action.setText("Check Again")
        self.update_action.show()

    def set_update_available(self, tag: str, url: str) -> None:
        self._release_url = url
        self.update_title.setText(f"Update available: {tag}")
        self.update_detail.setText(
            f"You're running version {__version__}. A newer stable release is available."
        )
        self.update_action.setText("View Release")
        self.update_action.show()

    def set_unavailable(self, message: str) -> None:
        self._release_url = ""
        self.update_title.setText("Update check unavailable")
        self.update_detail.setText(message or "The latest release could not be checked right now.")
        self.update_action.setText("Check Again")
        self.update_action.show()

    def _handle_update_action(self) -> None:
        if self._release_url:
            self.release_requested.emit(self._release_url)
        else:
            self.check_requested.emit()
