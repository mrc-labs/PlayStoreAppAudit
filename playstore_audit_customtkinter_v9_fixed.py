from __future__ import annotations

import webbrowser

from playstore_audit_process import install_hidden_subprocess_windows

# Prevent adb.exe / cmd-style console windows from flashing during scans and
# per-package metadata collection in a PyInstaller --windowed build.
install_hidden_subprocess_windows()

import customtkinter as ctk

import playstore_audit_customtkinter_v9 as v9


class CustomTkPlayStoreAuditV9Fixed(v9.CustomTkPlayStoreAuditV9):
    def _show_about(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("About Play Store App Audit")
        window.geometry("540x330")
        window.resizable(False, False)
        window.transient(self)

        ctk.CTkLabel(
            window,
            text="Play Store App Audit",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            window,
            text="Created by MRC",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(0, 12))
        ctk.CTkLabel(
            window,
            text=(
                "Audit Android packages against public Google Play listings, update dates, "
                "regional availability and optional connected-device metadata.\n\n"
                "Unofficial utility. Not affiliated with or endorsed by Google."
            ),
            wraplength=490,
            justify="left",
        ).pack(anchor="w", padx=20)
        ctk.CTkButton(
            window,
            text="MRC on GitHub",
            command=lambda: webbrowser.open(v9.v8.v7.PROJECT_URL),
        ).pack(anchor="w", padx=20, pady=16)
        ctk.CTkButton(
            window,
            text="Close",
            command=window.destroy,
            width=90,
            fg_color="#6C7781",
        ).pack(anchor="e", padx=20, pady=(0, 20))


def main() -> None:
    app = CustomTkPlayStoreAuditV9Fixed()
    app.mainloop()


if __name__ == "__main__":
    main()
