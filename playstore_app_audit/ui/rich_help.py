from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget


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
            """
            body { color: #26323d; font-family: 'Segoe UI', sans-serif; font-size: 10.5pt; }
            h1 { color: #18212a; font-size: 19pt; margin: 0 0 12px 0; }
            h2 { color: #26323d; font-size: 13pt; margin: 18px 0 7px 0; }
            h3 { color: #35424e; font-size: 11pt; margin: 14px 0 5px 0; }
            p { margin: 5px 0 9px 0; }
            ol, ul { margin: 5px 0 11px 22px; }
            li { margin-bottom: 6px; }
            pre { background: #f1f4f7; border: 1px solid #d7dee5; padding: 10px; margin: 8px 0 12px 0; white-space: pre-wrap; }
            code { color: #203040; font-family: Consolas, 'Courier New', monospace; font-size: 9.5pt; }
            a { color: #236ea8; text-decoration: underline; }
            .lead { color: #566674; font-size: 11pt; margin-bottom: 12px; }
            .note { background: #eef6fc; border: 1px solid #bdd7ea; color: #294f68; padding: 10px; margin: 10px 0; }
            .warning { background: #fff6e5; border: 1px solid #e9c77d; color: #6b4a16; padding: 10px; margin: 10px 0; }
            """
        )
        self.browser.setHtml(content)
        layout.addWidget(self.browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def show_rich_help(parent: QWidget, title: str, content: str) -> None:
    RichHelpDialog(parent, title, content).exec()
