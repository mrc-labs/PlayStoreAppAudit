from __future__ import annotations

import csv
import queue
import subprocess
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app_icon import ensure_runtime_icon
from playstore_audit_core import AuditConfig
from playstore_audit_multicountry import audit_apps_multicountry
from playstore_audit_user_state import (
    DEFAULT_SETTINGS,
    TECHNICAL_COLUMNS,
    clear_cache,
    compare_with_history,
    load_fresh_cache,
    load_history,
    load_settings,
    save_history,
    save_settings,
    update_cache,
)
import playstore_audit_customtkinter as legacy
import playstore_audit_gui as gui_base


legacy.subprocess = subprocess
gui_base.audit_apps = audit_apps_multicountry

FIXED_WORKERS = 16
SOURCE_PLACEHOLDER = "Choose a CSV / TSV / TXT file, or scan your Android phone"
PROJECT_URL = "https://github.com/mrc-labs/PlayStoreAppAudit"
PRIMARY_COLUMNS = (
    "criticality",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
)
MODEL_COLUMNS = (
    "criticality",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
    "change",
    "play_status",
    "updated_source",
    "play_http_status",
    "app_name",
    "store_url",
    "is_system",
)
COLUMN_LABELS = {
    "criticality": "Status",
    "package_name": "Package Name",
    "play_title": "Play Store Title",
    "play_last_update": "Last update",
    "age_days": "Age (days)",
    "notes": "Notes",
    "change": "Change",
    "play_status": "Play status",
    "updated_source": "Update source",
    "play_http_status": "HTTP status",
    "app_name": "Input name",
    "store_url": "Store URL",
    "is_system": "System app",
}
DEFAULT_WIDTHS = {
    "criticality": 145,
    "package_name": 285,
    "play_title": 245,
    "play_last_update": 110,
    "age_days": 90,
    "notes": 430,
    "change": 105,
    "play_status": 185,
    "updated_source": 170,
    "play_http_status": 90,
    "app_name": 210,
    "store_url": 340,
    "is_system": 90,
}


class CustomTkPlayStoreAuditBranch(legacy.CustomTkPlayStoreAuditApp):
    """CustomTkinter UI aligned functionally with the Qt6 branch."""

    COLUMNS = MODEL_COLUMNS
    COLUMN_LABELS = COLUMN_LABELS
    COLUMN_WIDTHS = DEFAULT_WIDTHS
    EXPORT_FIELDS = list(dict.fromkeys(gui_base.PlayStoreAuditApp.EXPORT_FIELDS + ["change", "cache_hit"]))

    def __init__(self) -> None:
        self.user_settings = load_settings()
        self._audit_session = 0
        self._audit_active = False
        self._audit_paused = False
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (0, 0, "")

        super().__init__()
        self.language_var.set(str(self.user_settings.get("store_language") or "en"))
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
        self.skip_source_check.grid(row=1, column=5, sticky="w", padx=(0, 16), pady=(0, 8))

        for child in source.winfo_children():
            try:
                info = child.grid_info()
                row = int(info.get("row", -1))
                if row == 3 and isinstance(child, ctk.CTkLabel):
                    child.grid_remove()
                elif row == 4 and isinstance(child, ctk.CTkLabel):
                    child.grid_configure(row=2, column=0, columnspan=6, sticky="w", padx=16, pady=(0, 12))
            except Exception:
                pass

        self._compact_action_row()
        self._build_menu()
        self._setup_context_menu()
        self._restore_column_widths()
        self._apply_column_visibility()
        self._set_run_mode("run")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

    def _visible_column_order(self) -> list[str]:
        columns = ["criticality"]
        if self.user_settings.get("compare_previous"):
            columns.append("change")
        columns.extend(PRIMARY_COLUMNS[1:])
        selected = self.user_settings.get("technical_columns", [])
        columns.extend(column for column in TECHNICAL_COLUMNS if column in selected)
        return columns

    def _apply_column_visibility(self) -> None:
        self.tree.configure(displaycolumns=tuple(self._visible_column_order()))
        for column in MODEL_COLUMNS:
            self.tree.heading(column, text=self.COLUMN_LABELS[column], command=lambda c=column: self._sort_results(c))

    def _restore_column_widths(self) -> None:
        widths = self.user_settings.get("ctk_column_widths", {})
        if not isinstance(widths, dict):
            widths = {}
        for column in MODEL_COLUMNS:
            try:
                width = int(widths.get(column, self.COLUMN_WIDTHS[column]))
            except (TypeError, ValueError):
                width = self.COLUMN_WIDTHS[column]
            self.tree.column(column, width=max(70, width))

    def _save_column_widths(self) -> None:
        widths = {}
        for column in MODEL_COLUMNS:
            try:
                widths[column] = int(self.tree.column(column, "width"))
            except Exception:
                pass
        self.user_settings["ctk_column_widths"] = widths
        self.user_settings = save_settings(self.user_settings)

    def _reset_table_layout(self) -> None:
        for column, width in self.COLUMN_WIDTHS.items():
            self.tree.column(column, width=width)
        self.user_settings["ctk_column_widths"] = {}
        self.user_settings = save_settings(self.user_settings)
        self._apply_column_visibility()
        self.status_var.set("Table layout reset to defaults")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Choose app list…", command=self._choose_input)
        file_menu.add_command(label="Scan phone with ADB", command=self._scan_phone)
        file_menu.add_separator()
        file_menu.add_command(label="Export all results…", command=self._export_results)
        file_menu.add_command(label="Export visible results…", command=self._export_visible_results)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        tools = tk.Menu(menubar, tearoff=0)
        tools.add_command(label="Advanced settings…", command=self._show_advanced_settings)
        tools.add_command(label="Clear audit cache", command=self._clear_audit_cache)
        tools.add_command(label="Reset table layout", command=self._reset_table_layout)
        menubar.add_cascade(label="Tools", menu=tools)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About Play Store App Audit", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        tk.Tk.config(self, menu=menubar)
        self._menu_bar = menubar

    def _show_advanced_settings(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Advanced settings")
        window.geometry("620x700")
        window.minsize(560, 620)
        window.transient(self)
        window.grab_set()
        content = ctk.CTkScrollableFrame(window, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(
            content,
            text="⚠ Advanced settings can change accuracy, network behaviour and the amount of technical data shown. Change them only when necessary and if you understand the effect.",
            wraplength=540,
            justify="left",
            text_color="#8A5A18",
            fg_color="#FFF6E5",
            corner_radius=8,
        ).pack(fill="x", pady=(0, 12), ipady=8)

        language_var = tk.StringVar(value=str(self.user_settings.get("store_language") or "en"))
        cache_var = tk.BooleanVar(value=bool(self.user_settings.get("cache_enabled", True)))
        ttl_var = tk.IntVar(value=int(self.user_settings.get("cache_ttl_hours", 72)))
        compare_var = tk.BooleanVar(value=bool(self.user_settings.get("compare_previous", False)))

        store = ctk.CTkFrame(content)
        store.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(store, text="Store and cache", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(store, text="Store language").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(store, textvariable=language_var, width=90).grid(row=1, column=1, sticky="w", padx=12, pady=6)
        ctk.CTkCheckBox(store, text="Use intelligent cache", variable=cache_var).grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=6)
        ctk.CTkLabel(store, text="Healthy-result cache TTL").grid(row=3, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(store, textvariable=ttl_var, width=90).grid(row=3, column=1, sticky="w", padx=12, pady=6)
        ctk.CTkLabel(store, text="hours (default 72)", text_color="#6C7781").grid(row=3, column=1, sticky="w", padx=(110, 12), pady=6)
        ctk.CTkLabel(
            store,
            text="Only normal available apps with a valid update date are cached. Removed, anomaly and error states always run live.",
            wraplength=520,
            justify="left",
            text_color="#6C7781",
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 12))

        history = ctk.CTkFrame(content)
        history.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(history, text="Audit history", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(history, text="Compare with previous audit", variable=compare_var).pack(anchor="w", padx=12, pady=4)
        ctk.CTkLabel(
            history,
            text="Off by default. The first completed audit creates a local baseline; later audits show Change = New / Same / Better / Worse.",
            wraplength=520,
            justify="left",
            text_color="#6C7781",
        ).pack(anchor="w", padx=12, pady=(4, 12))

        technical = ctk.CTkFrame(content)
        technical.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(technical, text="Technical columns", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        technical_vars: dict[str, tk.BooleanVar] = {}
        selected = set(self.user_settings.get("technical_columns", []))
        for key, label in TECHNICAL_COLUMNS.items():
            variable = tk.BooleanVar(value=key in selected)
            technical_vars[key] = variable
            ctk.CTkCheckBox(technical, text=label, variable=variable).pack(anchor="w", padx=12, pady=3)
        ctk.CTkLabel(technical, text="These fields are mainly useful for diagnostics and debugging.", text_color="#6C7781").pack(anchor="w", padx=12, pady=(6, 12))

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))

        def reset_controls() -> None:
            language_var.set(str(DEFAULT_SETTINGS["store_language"]))
            cache_var.set(bool(DEFAULT_SETTINGS["cache_enabled"]))
            ttl_var.set(int(DEFAULT_SETTINGS["cache_ttl_hours"]))
            compare_var.set(bool(DEFAULT_SETTINGS["compare_previous"]))
            for variable in technical_vars.values():
                variable.set(False)

        def save_and_close() -> None:
            try:
                ttl = max(1, min(720, int(ttl_var.get())))
            except Exception:
                messagebox.showerror("Invalid setting", "Cache TTL must be a number between 1 and 720 hours.", parent=window)
                return
            self.user_settings.update(
                {
                    "store_language": (language_var.get().strip() or "en").lower(),
                    "cache_enabled": bool(cache_var.get()),
                    "cache_ttl_hours": ttl,
                    "compare_previous": bool(compare_var.get()),
                    "technical_columns": [key for key, variable in technical_vars.items() if variable.get()],
                }
            )
            self.user_settings = save_settings(self.user_settings)
            self.language_var.set(str(self.user_settings.get("store_language") or "en"))
            self._apply_column_visibility()
            self.status_var.set("Advanced settings saved; audit-related changes apply from the next run")
            window.destroy()

        ctk.CTkButton(buttons, text="Reset to defaults", command=reset_controls, fg_color="#6C7781").pack(side="left")
        ctk.CTkButton(buttons, text="Cancel", command=window.destroy, fg_color="#6C7781").pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", command=save_and_close).pack(side="right")

    def _clear_audit_cache(self) -> None:
        if messagebox.askyesno(
            "Clear audit cache?",
            "Delete locally cached healthy Play Store results? Audit history and settings will not be deleted.",
            parent=self,
        ):
            clear_cache()
            self.status_var.set("Audit cache cleared")

    def _show_about(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("About Play Store App Audit")
        window.geometry("520x330")
        window.resizable(False, False)
        window.transient(self)
        ctk.CTkLabel(window, text="Play Store App Audit", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(window, text="Created by MRC", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20)
        ctk.CTkLabel(window, text="Development assistance: OpenAI ChatGPT", text_color="#6C7781").pack(anchor="w", padx=20, pady=(2, 12))
        ctk.CTkLabel(
            window,
            text="Audit Android packages against public Google Play listings, update dates and regional availability.\n\nUnofficial utility. Not affiliated with or endorsed by Google.",
            wraplength=470,
            justify="left",
        ).pack(anchor="w", padx=20)
        ctk.CTkButton(window, text="MRC on GitHub", command=lambda: webbrowser.open(PROJECT_URL)).pack(anchor="w", padx=20, pady=16)
        ctk.CTkButton(window, text="Close", command=window.destroy, width=90, fg_color="#6C7781").pack(anchor="e", padx=20, pady=(0, 20))

    def _setup_context_menu(self) -> None:
        self.tree.bind("<Button-3>", self._show_row_context_menu, add="+")

    def _show_row_context_menu(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        values = self.tree.item(item, "values")
        if len(values) < 2:
            return
        package_name = str(values[1])
        row = next((entry for entry in self.current_rows if str(entry.get("package_name")) == package_name), None)
        if not row:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Open in Google Play", command=lambda: webbrowser.open(str(row.get("store_url") or "")))
        menu.add_separator()
        menu.add_command(label="Copy package name", command=lambda: self._copy_text(str(row.get("package_name") or "")))
        menu.add_command(label="Copy Play Store title", command=lambda: self._copy_text(str(row.get("play_title") or "")))
        menu.add_command(label="Copy Store URL", command=lambda: self._copy_text(str(row.get("store_url") or "")))
        menu.add_command(label="Copy visible row", command=lambda: self._copy_text("\t".join(str(row.get(column, "") or "") for column in self._visible_column_order())))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    def _export_rows(self, rows: list[dict[str, object]], default_name: str) -> None:
        if not rows:
            messagebox.showinfo("Nothing to export", "There are no rows to export.", parent=self)
            return
        selected = filedialog.asksaveasfilename(
            title="Export audit results",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=default_name,
        )
        if not selected:
            return
        try:
            with open(selected, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.EXPORT_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            messagebox.showinfo("Export complete", f"Results saved to:\n{selected}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _export_results(self) -> None:
        self._export_rows(self.current_rows, "playstore_audit_results.csv")

    def _export_visible_results(self) -> None:
        self._export_rows(self._filtered_rows(), "playstore_audit_visible_results.csv")

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
        text = "Pause" if mode == "pause" else "Resume" if mode == "resume" else "Run Play Store audit"
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
            messagebox.showerror("No app list", str(exc), parent=self)
            return
        if not apps:
            messagebox.showerror("Nothing to audit", "No packages are loaded.", parent=self)
            return

        self.user_settings = load_settings()
        country = (self.country_var.get().strip() or "it").lower()
        language = str(self.user_settings.get("store_language") or "en").lower()
        cache_enabled = bool(self.user_settings.get("cache_enabled", True))
        ttl = int(self.user_settings.get("cache_ttl_hours", 72))
        cached = load_fresh_cache(apps, country, language, ttl) if cache_enabled else {}
        live_apps = [app for app in apps if app["package_name"] not in cached]
        cached_count = len(cached)

        self.current_system_packages = system_packages
        self.criticality_filter = None
        self.workers_var.set(FIXED_WORKERS)
        self.language_var.set(language)
        source_label = "Phone" if self.source_mode == "device" else "CSV/TXT"
        self.source_var.set(
            f"{source_label} source: {len(apps)} packages | {len(system_packages)} classified as system | {classification_method}"
        )
        self.current_rows = []
        self._refresh_table()
        self.export_button.configure(state="disabled")
        self.progress["value"] = cached_count
        self.progress["maximum"] = len(apps)
        cache_text = f" | {cached_count} from cache" if cached_count else ""
        self.status_var.set(f"Starting audit for {len(apps)} packages in Store country '{country}'{cache_text}…")

        self._audit_session += 1
        session = self._audit_session
        self._audit_active = True
        self._audit_paused = False
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (cached_count, len(apps), "")
        self._set_audit_source_controls_enabled(False)
        self._set_run_mode("pause")
        config = AuditConfig(country=country, language=language, max_workers=FIXED_WORKERS)
        threading.Thread(
            target=self._controlled_audit_worker,
            args=(apps, live_apps, cached, config, session, self._audit_pause_event, self._audit_cancel_event, cache_enabled),
            daemon=True,
        ).start()

    def _controlled_audit_worker(
        self,
        all_apps: list[dict[str, str]],
        live_apps: list[dict[str, str]],
        cached: dict[str, dict[str, object]],
        config: AuditConfig,
        session: int,
        pause_event: threading.Event,
        cancel_event: threading.Event,
        cache_enabled: bool,
    ) -> None:
        try:
            cached_count = len(cached)
            total_count = len(all_apps)

            def progress(done: int, _total: int, package_name: str) -> None:
                if cancel_event.is_set() or session != self._audit_session:
                    return
                self.progress_queue.put(("controlled_progress", session, cached_count + done, total_count, package_name))

            live_rows = audit_apps_multicountry(
                live_apps,
                config,
                progress,
                pause_event=pause_event,
                cancel_event=cancel_event,
            ) if live_apps else []
            if cancel_event.is_set() or session != self._audit_session:
                return
            if cache_enabled and live_rows:
                update_cache(live_rows, config.country, config.language)
            by_package = {package: dict(row) for package, row in cached.items()}
            by_package.update({str(row.get("package_name") or ""): row for row in live_rows})
            rows = [by_package[app["package_name"]] for app in all_apps if app["package_name"] in by_package]
            self.progress_queue.put(("controlled_done", session, rows, cached_count, len(live_rows)))
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
                    self.status_var.set(f"Paused | {done}/{total} completed" if self._audit_paused else f"Completed {done}/{total}: {package_name}")
                elif kind == "controlled_done":
                    _, session, rows, cached_count, live_count = message
                    if session != self._audit_session:
                        continue
                    compare_enabled = bool(self.user_settings.get("compare_previous", False))
                    history = load_history() if compare_enabled else {}
                    for row in rows:
                        row["is_system"] = str(row.get("package_name") or "") in self.current_system_packages
                        self._classify_criticality(row)
                        row["change"] = compare_with_history(row, history) if compare_enabled else ""
                    if compare_enabled:
                        save_history(rows)
                    self.current_rows = rows
                    if self.sort_column:
                        self.current_rows.sort(key=lambda row: self._sort_key(row, self.sort_column), reverse=self.sort_reverse)
                    self._audit_active = False
                    self._audit_paused = False
                    self._audit_pause_event.set()
                    self._set_audit_source_controls_enabled(True)
                    self._set_run_mode("run")
                    self.export_button.configure(state="normal" if rows else "disabled")
                    self.progress["value"] = self.progress["maximum"]
                    cache_summary = f" | {cached_count} cached | {live_count} live" if cached_count else f" | {live_count} live"
                    self.status_var.set(f"Audit completed{cache_summary}")
                    self._apply_column_visibility()
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
                    self.export_button.configure(state="normal" if self.current_rows else "disabled")
                    self.status_var.set("Audit failed")
                    messagebox.showerror("Audit error", error, parent=self)
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

    def _on_close(self) -> None:
        self._cancel_active_audit()
        self._save_column_widths()
        self.destroy()


def main() -> None:
    app = CustomTkPlayStoreAuditBranch()
    app.mainloop()


if __name__ == "__main__":
    main()
