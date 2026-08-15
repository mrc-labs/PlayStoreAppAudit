from __future__ import annotations

import subprocess

import customtkinter as ctk

import playstore_audit_customtkinter as legacy


# The legacy presentation module performs the ADB scan in its own override but
# did not import subprocess. Inject it explicitly so the existing logic uses
# the standard-library module instead of failing at runtime.
legacy.subprocess = subprocess

FIXED_WORKERS = 16


class CustomTkPlayStoreAuditBranch(legacy.CustomTkPlayStoreAuditApp):
    """Compact CustomTkinter presentation of the shared audit workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.language_var.set("en")
        self.workers_var.set(FIXED_WORKERS)

        source = self.path_entry.master
        settings = self.country_entry.master
        top = source.master

        # Remove the separate settings card. Store country belongs to the
        # source definition now, while concurrency is fixed internally.
        settings.grid_remove()
        source.grid_configure(columnspan=2, padx=(0, 0))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        self.skip_source_check.configure(text="Exclude system apps from source")
        self.skip_source_check.grid_forget()

        country_group = ctk.CTkFrame(source, fg_color="transparent")
        country_group.grid(row=2, column=0, sticky="w", padx=(16, 8), pady=(0, 7))
        ctk.CTkLabel(country_group, text="Store country").pack(side="left", padx=(0, 7))
        self.country_source_entry = ctk.CTkEntry(
            country_group,
            textvariable=self.country_var,
            width=66,
            height=30,
            corner_radius=7,
        )
        self.country_source_entry.pack(side="left")

        self.skip_source_check.grid(
            row=2,
            column=1,
            columnspan=2,
            sticky="w",
            padx=(4, 16),
            pady=(0, 7),
        )

        # Update the helper line created by the legacy UI.
        for child in source.winfo_children():
            try:
                grid = child.grid_info()
                if int(grid.get("row", -1)) == 3 and isinstance(child, ctk.CTkLabel):
                    child.configure(
                        text=(
                            "Applied during CSV/TXT load or ADB scan. Turn it off to include system apps."
                        )
                    )
            except Exception:
                pass

        # Keep app_name in the underlying Treeview values so legacy selection,
        # export and double-click logic remain intact, but do not display it.
        visible_columns = tuple(
            column for column in self.COLUMNS if column != "app_name"
        )
        self.tree.configure(displaycolumns=visible_columns)
        self.tree.heading(
            "package_name",
            text="Package Name",
            command=lambda: self._sort_results("package_name"),
        )
        self.tree.column("package_name", width=285, minwidth=160, stretch=True)

    def _start_audit(self) -> None:
        # Hidden, fixed concurrency. Store language remains fixed to English.
        self.workers_var.set(FIXED_WORKERS)
        self.language_var.set("en")
        super()._start_audit()


def main() -> None:
    app = CustomTkPlayStoreAuditBranch()
    app.mainloop()


if __name__ == "__main__":
    main()
