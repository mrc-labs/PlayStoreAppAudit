from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

import playstore_app_audit.ui.theme as theme_ui
from playstore_app_audit.product_identity import DISPLAY_NAME, PREVIOUS_DISPLAY_NAMES


class RichHelpDialog(QDialog):
    """Scrollable native dialog for authored, static user guides."""

    def __init__(self, parent: QWidget | None, title: str, content: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 640)
        self.setMinimumSize(620, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        self.browser = QTextBrowser()
        self.browser.setObjectName("RichHelpBrowser")
        self.browser.setOpenExternalLinks(True)
        self.browser.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.browser.document().setDocumentMargin(22)
        self.browser.document().setDefaultStyleSheet(
            theme_ui.rich_help_stylesheet(
                self.palette()
            )
        )
        # Keep authored guides compatible while the source/docs terminology is
        # migrated gradually. Technical identifiers and URLs are unaffected.
        for previous_name in PREVIOUS_DISPLAY_NAMES:
            content = content.replace(previous_name, DISPLAY_NAME)
        self.browser.setHtml(content)
        layout.addWidget(self.browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def show_rich_help(parent: QWidget, title: str, content: str) -> None:
    RichHelpDialog(parent, title, content).exec()
