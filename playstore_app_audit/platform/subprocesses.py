from __future__ import annotations

import os
import subprocess
from typing import Any

_INSTALLED = False
_ORIGINAL_POPEN = subprocess.Popen


def install_hidden_subprocess_windows() -> None:
    """Prevent console utilities such as adb.exe from flashing terminal windows.

    The desktop application is built with PyInstaller --windowed. On Windows,
    launching a console-subsystem executable without CREATE_NO_WINDOW can still
    create a short-lived console window. This installs an idempotent Popen
    subclass so subprocess.run/check_output/check_call and direct Popen calls
    inherit hidden-window defaults unless a caller explicitly supplied its own
    startup/creation flags.
    """
    global _INSTALLED
    if _INSTALLED or os.name != "nt":
        return

    original = _ORIGINAL_POPEN

    class HiddenWindowPopen(original):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            creationflags = int(kwargs.get("creationflags", 0) or 0)
            create_no_window = int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
            kwargs["creationflags"] = creationflags | create_no_window

            if kwargs.get("startupinfo") is None and hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
                startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
                kwargs["startupinfo"] = startupinfo

            super().__init__(*args, **kwargs)

    subprocess.Popen = HiddenWindowPopen  # type: ignore[assignment]
    _INSTALLED = True
