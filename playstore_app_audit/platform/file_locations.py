from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from playstore_app_audit.platform import runtime

logger = logging.getLogger(__name__)


def open_file_location(value: object) -> tuple[bool, str]:
    """Reveal one existing local file using argument-safe platform commands."""

    platform = runtime.platform_key()
    path = Path(str(value or "")).expanduser()
    logger.debug("Local APK reveal requested: platform=%s path=%s", platform, path)
    if not path.is_file():
        logger.warning(
            "Local APK reveal failed: platform=%s reason=missing path=%s", platform, path
        )
        return False, "The local APK file is no longer available at this location."
    path = path.resolve(strict=True)
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
        logger.exception("Local APK reveal failed: platform=%s path=%s", platform, path)
        return False, f"The file location could not be opened: {exc}"
    logger.info("Local APK reveal succeeded: platform=%s path=%s", platform, path)
    return True, ""
