from __future__ import annotations

import subprocess
import tkinter as tk

import customtkinter as ctk

from app_icon import ensure_runtime_icon
from playstore_audit_multicountry import audit_apps_multicountry
import playstore_audit_customtkinter as legacy
import playstore_audit_gui as gui_base


# The legacy presentation module performs the ADB scan in its own override but
# did not import subprocess. Inject it explicitly so the existing logic uses
# the standard-library module instead of failing at runtime.
legacy.subprocess = subprocess

# Keep the audit engine aligned with the Qt6 branch.
gui_base.audit_apps = audit_apps_multicountry

FIXED_WORKERS = 16
SOURCE_PLACEHOLDER = "Choose a CSV / TSV / TXT file, or scan your Android phone"


class CustomTkPlayStoreAuditBranch(legacy.CustomTkPlayStoreAuditApp):
    """Compact CustomTkinter presentation of the shared audit workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.language_var.set("en")
        self.workers_var.set(FIXED_WORKERS)
        self.geometry("1460x780")
        self.minsize(1080, 610)

        try:
            self._app_icon_image = tk.PhotoImage(file=str(ensure_runtime_icon()))
            self.iconphoto(True, self._app_icon_image)
        except Exception:
            self._app_icon_image = None

        source = self.path_entry.master
        settings = self.country_entry.master
        top = source.master

        # Replace the path field so CustomTkinter's native placeholder works.
        # CTkEntry placeholders do not work together with textvariable.
        old_path = self.path_entry
        old_path.destroy()
        self.path_entry = ctk.CTkEntry(
            source,
            placeholder_text=SOURCE_PLACEHOLDER,
            placeholder_text_color=("#83909B", "#89939C"),
            height=34,
            corner_radius=8,
            takefocus=False,
        )
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 8))
        self.path_entry.bind("<KeyPress>", lambda _event: "break")
        self.path_entry.bind("<<Paste>>", lambda _event: "break")
        self.input_var.trace_add("write", lambda *_: self._sync_path_entry())
        self._sync_path_entry()

        # Remove the standalone settings card. All source controls now share
        # one row: path | Choose file | ADB | country | system-app exclusion.
        settings.grid_remove()
        source.grid_configure(columnspan=2, padx=(0, 0))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)
        source.grid_columnconfigure(0, weight=1)
        for column in range(1, 6):
            source.grid_columnconfigure(column, weight=0)

        self.skip_source_check.configure(text="Exclude system apps from source")
        self.skip_source_check.grid_forget()

        self.country_source_label = ctk.CTkLabel(source, text="Store country")
        self.country_source_label.grid(row=1, column=3, sticky="e", padx=(10, 6), pady=(0, 8))
        self.country_source_entry = ctk.CTkEntry(
            source,
            textvariable=self.country_var,
            width=58,
            height=34,
            corner_radius=8,
        )
        self.country_source_entry.grid(row=1, column=4, sticky="w", padx=(0, 10), pady=(0, 8))

        self.skip_source_check.grid(
            row=1,
            column=5,
            sticky="w",
            padx=(0, 16),
            pady=(0, 8),
        )

        # Remove the extra helper line and keep only the compact source-status
        # line directly below the controls.
        for child in source.winfo_children():
            try:
                grid = child.grid_info()
                row = int(grid.get("row", -1))
                if row == 3 and isinstance(child, ctk.CTkLabel):
                    child.grid_remove()
                elif row == 4 and isinstance(child, ctk.CTkLabel):
                    child.grid_configure(
                        row=2,
                        column=0,
                        columnspan=6,
                        sticky="w",
                        padx=16,
                        pady=(0, 12),
                    )
            except Exception:
                pass

        # Keep app_name in underlying values for export and compatibility, but
        # do not display the redundant Input name column.
        visible_columns = tuple(column for column in self.COLUMNS if column != "app_name")
        self.tree.configure(displaycolumns=visible_columns)
        self.tree.heading(
            "package_name",
            text="Package Name",
            command=lambda: self._sort_results("package_name"),
        )
        self.tree.column("package_name", width=285, minwidth=160, stretch=True)

        self._compact_action_row()

    def _sync_path_entry(self) -> None:
        if not hasattr(self, "path_entry"):
            return
        value = self.input_var.get().strip()
        try:
            self.path_entry.delete(0, "end")
            if value:
                self.path_entry.insert(0, value)
        except Exception:
            pass

    def _compact_action_row(self) -> None:
        """Run | progress+status | Export | Clear on one compact row."""
        actions = self.run_button.master
        root = actions.master
        progress_card = self.progress.master
        results = self.tree.master.master

        self.run_button.grid_forget()
        self.export_button.grid_forget()
        self.clear_button.grid_forget()
        progress_card.destroy()

        for column in range(4):
            actions.grid_columnconfigure(column, weight=0)
        actions.grid_columnconfigure(1, weight=1)

        self.run_button.grid(row=0, column=0, sticky="w")

        progress_group = ctk.CTkFrame(actions, fg_color="transparent")
        progress_group.grid(row=0, column=1, sticky="ew", padx=(10, 10))
        progress_group.grid_columnconfigure(0, weight=1)
        self.progress = legacy.CompatProgress(progress_group, height=10, corner_radius=5)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.inline_status_label = ctk.CTkLabel(
            progress_group,
            textvariable=self.status_var,
            text_color=("#6C7781", "#AAB1B7"),
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.inline_status_label.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.export_button.grid(row=0, column=2, padx=(0, 8))
        self.clear_button.grid(row=0, column=3)

        results.grid_configure(row=3, pady=(10, 0))
        root.grid_rowconfigure(5, weight=0)
        root.grid_rowconfigure(3, weight=1)

    def _classify_criticality(self, row: dict[str, object]) -> None:
        status = str(row.get("play_status") or "").strip()
        if status == "not_found_in_checked_countries":
            key = "red"
        elif status == "available_in_other_country":
            key = "blue"
        elif status == "multi_country_check_inconclusive":
            key = "purple"
        else:
            super()._classify_criticality(row)
            return

        row["criticality_key"] = key
        row["criticality"] = self.CRITICALITY[key]["label"]
        row["criticality_rank"] = self.CRITICALITY[key]["rank"]
        row["age_days"] = ""

    def _start_audit(self) -> None:
        self.workers_var.set(FIXED_WORKERS)
        self.language_var.set("en")
        super()._start_audit()


def main() -> None:
    app = CustomTkPlayStoreAuditBranch()
    app.mainloop()


if __name__ == "__main__":
    main()
