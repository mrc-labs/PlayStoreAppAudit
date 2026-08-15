from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app_icon import ensure_runtime_icon
from playstore_app_audit import __version__
from playstore_app_audit.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Play Store App Audit")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
