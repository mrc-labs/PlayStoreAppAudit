from __future__ import annotations

import ctypes
import os


def enable_windows_per_monitor_dpi() -> None:
    if os.name != "nt":
        return
    try:
        # Must happen before Tk creates the first HWND.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> None:
    enable_windows_per_monitor_dpi()
    from playstore_audit_customtkinter import main as run_app
    run_app()


if __name__ == "__main__":
    main()
