from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Any
from tkinter import filedialog, messagebox

import customtkinter as ctk

import playstore_audit_customtkinter_v9_2 as v92ui
import playstore_audit_v9_3_features as v93


v92ui.v92.APP_VERSION = v93.APP_VERSION
v92ui.v9.features.APP_VERSION = v93.APP_VERSION


class CustomTkPlayStoreAuditV93(v92ui.CustomTkPlayStoreAuditV92):
    def __init__(self) -> None:
        super().__init__()
        self._rebuild_source_area()
        self._setup_export_button_menu()
        self._rebuild_file_menu()
        self._refresh_table()

    # ---------- Source UX ----------
    def _rebuild_source_area(self) -> None:
        source = self.path_entry.master

        # Remove the old single-row source controls and the old status label.
        self.path_entry.grid_forget()
        self.choose_button.grid_forget()
        self.scan_button.grid_forget()
        self.country_source_label.grid_forget()
        self.country_source_entry.grid_forget()
        self.skip_source_check.grid_forget()
        for child in source.winfo_children():
            try:
                info = child.grid_info()
                if int(info.get("row", -1)) == 2 and isinstance(child, ctk.CTkLabel):
                    child.grid_remove()
            except Exception:
                pass

        for column in range(6):
            source.grid_columnconfigure(column, weight=0)
        source.grid_columnconfigure(0, weight=1)

        option_font = ctk.CTkFont(size=13, weight="bold")
        muted = ("#6C7781", "#AAB1B7")

        ctk.CTkLabel(
            source,
            text="Choose a CSV / TSV / TXT file",
            font=option_font,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=(16, 12), pady=(2, 5))
        self.choose_button.configure(text="Choose file", width=130)
        self.choose_button.grid(row=1, column=1, sticky="e", padx=(0, 16), pady=(2, 5))

        ctk.CTkLabel(
            source,
            text="or",
            text_color=muted,
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, columnspan=2, pady=1)

        ctk.CTkLabel(
            source,
            text="Scan your Android phone with ADB",
            font=option_font,
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=(16, 12), pady=(5, 7))
        self.scan_button.configure(text="Scan phone", width=130)
        self.scan_button.grid(row=3, column=1, sticky="e", padx=(0, 16), pady=(5, 7))

        options = ctk.CTkFrame(source, fg_color="transparent")
        options.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=(2, 5))
        self.country_source_label.configure(text="Store country")
        self.country_source_label.pack(side="left")
        self.country_source_entry.configure(width=58)
        self.country_source_entry.pack(side="left", padx=(6, 14))
        self.skip_source_check.pack(side="left")

        self._v93_source_status = ctk.CTkLabel(
            source,
            textvariable=self.source_var,
            text_color=muted,
            wraplength=1000,
            justify="left",
            anchor="w",
        )
        self._v93_source_status.grid(row=5, column=0, columnspan=2, sticky="ew", padx=16, pady=(2, 14))

    def _load_input_file(self, path: str) -> None:
        super()._load_input_file(path)
        if self.source_mode == "file":
            text = self.source_var.get()
            if text.startswith("File selected: "):
                text = text[len("File selected: "):]
            self.source_var.set(f"{Path(path).name}  •  {text}")

    # ---------- Export UX ----------
    def _setup_export_button_menu(self) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Export all results as CSV…", command=self._export_results)
        menu.add_command(label="Export visible results as CSV…", command=self._export_visible_results)
        menu.add_separator()
        menu.add_command(label="Export all results as HTML…", command=self._export_html_report)
        menu.add_command(label="Export visible results as HTML…", command=self._export_visible_html_report)
        self._export_results_menu = menu
        self.export_button.configure(text="Export results ▾", command=self._show_export_results_menu)

    def _show_export_results_menu(self) -> None:
        if str(self.export_button.cget("state")) == "disabled":
            return
        try:
            self._export_results_menu.tk_popup(
                self.export_button.winfo_rootx(),
                self.export_button.winfo_rooty() + self.export_button.winfo_height(),
            )
        finally:
            self._export_results_menu.grab_release()

    def _export_visible_html_report(self) -> None:
        self._export_html_rows(
            [dict(row) for row in self._filtered_rows()],
            "playstore_audit_visible_report.html",
            "Export visible results as HTML",
        )

    def _export_html_rows(self, rows: list[dict[str, Any]], default_name: str, title: str) -> None:
        if not rows:
            messagebox.showinfo("Nothing to export", "There are no results to export.", parent=self)
            return
        selected = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".html",
            initialfile=default_name,
            filetypes=[("HTML", "*.html")],
        )
        if not selected:
            return
        try:
            formatted = v92ui.v92.rows_for_output(rows)
            v92ui.v9.features.write_html_report(selected, formatted, self._device_summary)
            messagebox.showinfo("Export complete", f"HTML report saved to:\n{selected}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _rebuild_file_menu(self) -> None:
        try:
            menu_name = self._menu_bar.entrycget(0, "menu")
            file_menu = self.nametowidget(menu_name)
        except Exception:
            return
        file_menu.delete(0, "end")
        file_menu.add_command(label="Choose app list…", command=self._choose_input)
        recent = tk.Menu(file_menu, tearoff=0)
        paths = v92ui.v9.features.get_recent_sources()
        if paths:
            for path in paths:
                recent.add_command(label=Path(path).name, command=lambda p=path: self._load_input_file(p))
        else:
            recent.add_command(label="No recent files", state="disabled")
        file_menu.add_cascade(label="Recent sources", menu=recent)
        self._v93_recent_menu = recent
        file_menu.add_command(label="Scan phone with ADB", command=self._scan_phone)
        file_menu.add_command(label="Export current phone package list as CSV…", command=self._export_phone_packages_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Export all results as CSV…", command=self._export_results)
        file_menu.add_command(label="Export visible results as CSV…", command=self._export_visible_results)
        file_menu.add_command(label="Export all results as HTML…", command=self._export_html_report)
        file_menu.add_command(label="Export visible results as HTML…", command=self._export_visible_html_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

    # ---------- Concise summary ----------
    def _refresh_table(self) -> None:
        super()._refresh_table()
        if hasattr(self, "summary_var"):
            try:
                visible = len(self._filtered_rows())
            except Exception:
                visible = len(self.current_rows)
            self.summary_var.set(
                v93.concise_summary(
                    list(self.current_rows),
                    visible,
                    getattr(self, "_last_inventory_changes", None),
                )
            )


def main() -> None:
    app = CustomTkPlayStoreAuditV93()
    app.mainloop()


if __name__ == "__main__":
    main()
