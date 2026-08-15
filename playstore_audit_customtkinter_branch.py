from __future__ import annotations

import queue
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app_icon import ensure_runtime_icon
from playstore_audit_core import AuditConfig
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

    COLUMNS = (
        "criticality",
        "package_name",
        "play_title",
        "play_last_update",
        "age_days",
        "notes",
    )
    COLUMN_LABELS = {
        "criticality": "Status",
        "package_name": "Package Name",
        "play_title": "Play Store Title",
        "play_last_update": "Last update",
        "age_days": "Age (days)",
        "notes": "Notes",
    }
    COLUMN_WIDTHS = {
        "criticality": 145,
        "package_name": 285,
        "play_title": 245,
        "play_last_update": 110,
        "age_days": 90,
        "notes": 430,
    }

    def __init__(self) -> None:
        self._audit_session = 0
        self._audit_active = False
        self._audit_paused = False
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (0, 0, "")

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

        self.tree.heading(
            "criticality",
            text="Status",
            command=lambda: self._sort_results("criticality"),
        )
        for column in self.COLUMNS:
            self.tree.column(column, width=self.COLUMN_WIDTHS[column])

        self._compact_action_row()
        self._set_run_mode("run")

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
        """Run/Pause | progress+status | Export | Clear on one compact row."""
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

    def _set_run_mode(self, mode: str) -> None:
        if mode == "pause":
            text = "Pause"
        elif mode == "resume":
            text = "Resume"
        else:
            text = "Run Play Store audit"
        self.run_button.configure(text=text, state="normal")

    def _set_audit_source_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.choose_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.skip_source_check.configure(state=state)
        self.country_source_entry.configure(state=state)

    def _toggle_pause(self) -> None:
        if not self._audit_active:
            return
        done, total, _package = self._last_progress
        if self._audit_paused:
            self._audit_pause_event.set()
            self._audit_paused = False
            self._set_run_mode("pause")
            self.status_var.set(f"Resumed | {done}/{total} completed")
        else:
            self._audit_pause_event.clear()
            self._audit_paused = True
            self._set_run_mode("resume")
            self.status_var.set(f"Paused | {done}/{total} completed")

    def _start_audit(self) -> None:
        if self._audit_active:
            self._toggle_pause()
            return

        try:
            apps, system_packages, classification_method = self._get_apps_to_audit()
        except Exception as exc:
            messagebox.showerror("No app list", str(exc))
            return
        if not apps:
            messagebox.showerror("Nothing to audit", "No packages are loaded.")
            return

        country = (self.country_var.get().strip() or "it").lower()
        self.current_system_packages = system_packages
        self.criticality_filter = None
        self.workers_var.set(FIXED_WORKERS)
        self.language_var.set("en")

        source_label = "Phone" if self.source_mode == "device" else "CSV/TXT"
        self.source_var.set(
            f"{source_label} source: {len(apps)} packages | "
            f"{len(system_packages)} classified as system | {classification_method}"
        )

        self.current_rows = []
        self._refresh_table()
        self.export_button.configure(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(apps)
        self.status_var.set(
            f"Starting audit for {len(apps)} packages in Store country '{country}'…"
        )

        self._audit_session += 1
        session = self._audit_session
        self._audit_active = True
        self._audit_paused = False
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (0, len(apps), "")
        self._set_audit_source_controls_enabled(False)
        self._set_run_mode("pause")

        config = AuditConfig(country=country, language="en", max_workers=FIXED_WORKERS)
        threading.Thread(
            target=self._controlled_audit_worker,
            args=(apps, config, session, self._audit_pause_event, self._audit_cancel_event),
            daemon=True,
        ).start()

    def _controlled_audit_worker(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        session: int,
        pause_event: threading.Event,
        cancel_event: threading.Event,
    ) -> None:
        try:
            def progress(done: int, total: int, package_name: str) -> None:
                if cancel_event.is_set() or session != self._audit_session:
                    return
                self.progress_queue.put(("controlled_progress", session, done, total, package_name))

            rows = audit_apps_multicountry(
                apps,
                config,
                progress,
                pause_event=pause_event,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set() or session != self._audit_session:
                return
            self.progress_queue.put(("controlled_done", session, rows))
        except Exception as exc:
            if not cancel_event.is_set() and session == self._audit_session:
                self.progress_queue.put(("controlled_error", session, str(exc)))

    def _process_queue(self) -> None:
        try:
            while True:
                message = self.progress_queue.get_nowait()
                kind = message[0]

                if kind == "controlled_progress":
                    _, session, done, total, package_name = message
                    if session != self._audit_session or not self._audit_active:
                        continue
                    self._last_progress = (done, total, package_name)
                    self.progress["value"] = done
                    self.progress["maximum"] = total
                    if self._audit_paused:
                        self.status_var.set(f"Paused | {done}/{total} completed")
                    else:
                        self.status_var.set(f"Completed {done}/{total}: {package_name}")

                elif kind == "controlled_done":
                    _, session, rows = message
                    if session != self._audit_session:
                        continue
                    for row in rows:
                        row["is_system"] = str(row.get("package_name") or "") in self.current_system_packages
                        self._classify_criticality(row)
                    self.current_rows = rows
                    if self.sort_column:
                        self.current_rows.sort(
                            key=lambda row: self._sort_key(row, self.sort_column),
                            reverse=self.sort_reverse,
                        )
                    self._audit_active = False
                    self._audit_paused = False
                    self._audit_pause_event.set()
                    self._set_audit_source_controls_enabled(True)
                    self._set_run_mode("run")
                    self.export_button.configure(state="normal")
                    self.progress["value"] = self.progress["maximum"]
                    self.status_var.set("Audit completed")
                    self._refresh_table()

                elif kind == "controlled_error":
                    _, session, error = message
                    if session != self._audit_session:
                        continue
                    self._audit_active = False
                    self._audit_paused = False
                    self._audit_pause_event.set()
                    self._set_audit_source_controls_enabled(True)
                    self._set_run_mode("run")
                    self.export_button.configure(
                        state="normal" if self.current_rows else "disabled"
                    )
                    self.status_var.set("Audit failed")
                    messagebox.showerror("Audit error", error)

        except queue.Empty:
            pass
        self.after(100, self._process_queue)

    def _cancel_active_audit(self) -> None:
        if not self._audit_active:
            self._set_run_mode("run")
            return
        self._audit_cancel_event.set()
        self._audit_pause_event.set()
        self._audit_session += 1
        self._audit_active = False
        self._audit_paused = False
        self._set_audit_source_controls_enabled(True)
        self._set_run_mode("run")

    def _clear_results(self) -> None:
        self._cancel_active_audit()
        gui_base.PlayStoreAuditApp._clear_results(self)
        self._set_run_mode("run")


def main() -> None:
    app = CustomTkPlayStoreAuditBranch()
    app.mainloop()


if __name__ == "__main__":
    main()
