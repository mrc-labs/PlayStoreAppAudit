from __future__ import annotations

import subprocess
from pathlib import Path

from playstore_app_audit.platform import runtime


def open_file_location(value: object) -> tuple[bool, str]:
    """Reveal one existing local file using argument-safe platform commands."""

    path = Path(str(value or "")).expanduser()
    if not path.is_file():
        return False, "The local APK file is no longer available at this location."
    path = path.resolve(strict=True)
    try:
        if runtime.platform_key() == "windows":
            subprocess.Popen(["explorer.exe", f"/select,{path}"], close_fds=True)
        elif runtime.platform_key() == "macos":
            subprocess.Popen(["open", "-R", str(path)], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", str(path.parent)], close_fds=True)
    except OSError as exc:
        return False, f"The file location could not be opened: {exc}"
    return True, ""
