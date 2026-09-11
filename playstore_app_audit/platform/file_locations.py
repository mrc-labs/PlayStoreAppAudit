from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from playstore_app_audit.platform import runtime

logger = logging.getLogger(__name__)


def open_file_location(value: object) -> tuple[bool, str]:
    """Reveal one existing local file using argument-safe platform commands."""

    path = Path(str(value or "")).expanduser()
    if not path.is_file():
        logger.warning("Local APK reveal skipped because file is missing: path=%s", path)
        return False, "The local APK file is no longer available at this location."
    path = path.resolve(strict=True)
    platform = runtime.platform_key()
    logger.info("Revealing Local APK in file manager: platform=%s path=%s", platform, path)
    try:
        if platform == "windows":
            # Explorer expects /select, as the switch and the quoted path as the
            # following argument. Keeping the path separate also avoids shell
            # parsing for spaces and other valid filename characters.
            subprocess.Popen(["explorer.exe", "/select,", str(path)], close_fds=True)
        elif platform == "macos":
            subprocess.Popen(["open", "-R", str(path)], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", str(path.parent)], close_fds=True)
    except OSError as exc:
        logger.exception("Could not reveal Local APK path=%s", path)
        return False, f"The file location could not be opened: {exc}"
    return True, ""
