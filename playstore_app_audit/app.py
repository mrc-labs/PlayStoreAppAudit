from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from playstore_app_audit import __version__
from playstore_app_audit.resources import ensure_runtime_icon
from playstore_app_audit.services.performance_diagnostics import install_performance_diagnostics
from playstore_app_audit.services.store_path_diagnostics import install_store_path_diagnostics
from playstore_app_audit.ui.main_window import MainWindow

SMOKE_TEST_ENV = "PLAYSTORE_APP_AUDIT_SMOKE_TEST"


def main() -> int:
    install_performance_diagnostics()
    install_store_path_diagnostics()

    app = QApplication(sys.argv)
    app.setApplicationName("Play Store App Audit")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = MainWindow()
    window.show()

    smoke_test = os.environ.get(SMOKE_TEST_ENV, "").strip().lower() in {"1", "true", "yes"}
    if smoke_test:
        # CI uses this to prove that a packaged binary can create the real main
        # window, enter Qt's event loop and exit cleanly. Normal launches never
        # set this environment variable, so user-facing behaviour is unchanged.
        QTimer.singleShot(750, app.quit)

    exit_code = app.exec()
    if smoke_test:
        print("Play Store App Audit packaged smoke test completed", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
