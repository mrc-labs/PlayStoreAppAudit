from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from playstore_app_audit import __version__
from playstore_app_audit.resources import ensure_runtime_icon
from playstore_app_audit.services import debug_logging
from playstore_app_audit.services.app_icon_metadata import install_app_icon_metadata_capture
from playstore_app_audit.services.performance_diagnostics import install_performance_diagnostics
from playstore_app_audit.services.play_store import install_play_store_service
from playstore_app_audit.services.scraper_transport import install_scraper_transport_timeout
from playstore_app_audit.ui.main_window import MainWindow
from playstore_app_audit.ui.update_check import install_update_check_controller

SMOKE_TEST_ENV = "PLAYSTORE_APP_AUDIT_SMOKE_TEST"


def consume_debug_argument(arguments: list[str]) -> tuple[list[str], bool]:
    debug = "--debug" in arguments[1:]
    return ([item for item in arguments if item != "--debug"] if debug else list(arguments), debug)


def main() -> int:
    qt_arguments, debug = consume_debug_argument(sys.argv)
    sys.argv = qt_arguments
    if debug:
        debug_path = debug_logging.start_debug_logging()
        logging.getLogger("playstore_app_audit").info("Debug log: %s", debug_path)
        if sys.stdout is not None:
            print(f"Debug log: {debug_path}", flush=True)
    else:
        debug_logging.configure_parser_logging(debug=False)
    install_scraper_transport_timeout()
    install_play_store_service()
    install_performance_diagnostics()
    install_app_icon_metadata_capture()

    smoke_test = os.environ.get(SMOKE_TEST_ENV, "").strip().lower() in {"1", "true", "yes"}

    app = QApplication(sys.argv)
    app.setApplicationName("Play Store App Audit")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = MainWindow()
    install_update_check_controller(window, schedule_startup=not smoke_test)
    window.show()

    if smoke_test:
        # CI uses this to prove that a packaged binary can create the real main
        # window, enter Qt's event loop and exit cleanly. Startup update checks
        # are intentionally skipped so this deterministic smoke does not depend
        # on external network availability.
        QTimer.singleShot(750, app.quit)

    exit_code = app.exec()
    if smoke_test:
        print("Play Store App Audit packaged smoke test completed", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
