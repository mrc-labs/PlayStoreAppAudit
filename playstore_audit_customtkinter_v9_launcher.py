from __future__ import annotations

from playstore_audit_customtkinter_launcher import enable_windows_per_monitor_dpi


def main() -> None:
    enable_windows_per_monitor_dpi()
    from playstore_audit_customtkinter_v9_fixed import main as run_app
    run_app()


if __name__ == "__main__":
    main()
