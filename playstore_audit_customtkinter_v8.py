from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from tkinter import messagebox

import customtkinter as ctk

from app_icon import ensure_runtime_icon
import playstore_audit_customtkinter_branch as v7
import playstore_audit_user_state as user_state
import playstore_audit_v8_features as features


V8_EXTRA_COLUMNS = (
    "play_version",
    "installed_version",
    "version_comparison",
    "installer_source",
)
V8_MODEL_COLUMNS = tuple(dict.fromkeys(tuple(v7.MODEL_COLUMNS) + V8_EXTRA_COLUMNS))
v7.MODEL_COLUMNS = V8_MODEL_COLUMNS
v7.COLUMN_LABELS.update(
    {
        "play_version": "Play Store version",
        "installed_version": "Installed version",
        "version_comparison": "Installed vs Store",
        "installer_source": "Installer source",
    }
)
v7.DEFAULT_WIDTHS.update(
    {
        "play_version": 150,
        "installed_version": 150,
        "version_comparison": 140,
        "installer_source": 230,
    }
)
v7.CustomTkPlayStoreAuditBranch.COLUMNS = V8_MODEL_COLUMNS
v7.CustomTkPlayStoreAuditBranch.COLUMN_LABELS = v7.COLUMN_LABELS
v7.CustomTkPlayStoreAuditBranch.COLUMN_WIDTHS = v7.DEFAULT_WIDTHS
v7.CustomTkPlayStoreAuditBranch.EXPORT_FIELDS = list(
    dict.fromkeys(
        list(v7.CustomTkPlayStoreAuditBranch.EXPORT_FIELDS)
        + [
            "play_version",
            "installed_version",
            "installed_version_code",
            "version_comparison",
            "installer_source",
        ]
    )
)
v7.audit_apps_multicountry = features.audit_apps_v8
v7.save_history = features.save_history_merged

_ORIGINAL_LOAD_FRESH_CACHE = v7.load_fresh_cache
_BYPASS_CACHE_ONCE = False


def _load_fresh_cache_proxy(*args, **kwargs):
    if _BYPASS_CACHE_ONCE:
        return {}
    return _ORIGINAL_LOAD_FRESH_CACHE(*args, **kwargs)


v7.load_fresh_cache = _load_fresh_cache_proxy


class CustomTkPlayStoreAuditV8(v7.CustomTkPlayStoreAuditBranch):
    COLUMNS = V8_MODEL_COLUMNS
    COLUMN_LABELS = v7.COLUMN_LABELS
    COLUMN_WIDTHS = v7.DEFAULT_WIDTHS
    EXPORT_FIELDS = v7.CustomTkPlayStoreAuditBranch.EXPORT_FIELDS

    def __init__(self) -> None:
        self._force_refresh_next = False
        self._apps_override: list[dict[str, str]] | None = None
        self._merge_base_rows: list[dict[str, Any]] | None = None
        self._subset_label = ""
        self._pending_device_metadata: dict[str, dict[str, str]] = {}
        super().__init__()
        self._build_menu_v8()
        self._apply_column_visibility()
        self._refresh_table()

    # ---------- Menus ----------
    def _build_menu_v8(self) -> None:
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
        tools.add_separator()
        tools.add_command(label="Force full refresh (ignore cache)", command=self._force_full_refresh)
        tools.add_command(label="Recheck Removed / Anomaly / Other", command=self._recheck_problematic)
        tools.add_separator()
        tools.add_command(label="Clear audit cache", command=self._clear_audit_cache)
        tools.add_command(label="Clear previous-audit history", command=self._clear_audit_history)
        tools.add_command(label="Reset table layout", command=self._reset_table_layout)
        menubar.add_cascade(label="Tools", menu=tools)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About Play Store App Audit", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        tk.Tk.config(self, menu=menubar)
        self._menu_bar = menubar

    def _clear_audit_history(self) -> None:
        if messagebox.askyesno(
            "Clear previous-audit history?",
            "Delete the local comparison baseline? The cache, settings and current results will not be deleted.",
            parent=self,
        ):
            features.clear_history()
            self.status_var.set("Previous-audit history cleared; the next comparison run will create a new baseline")

    # ---------- Advanced settings ----------
    def _show_advanced_settings(self) -> None:
        self.user_settings = user_state.load_settings()
        window = ctk.CTkToplevel(self)
        window.title("Advanced settings")
        window.geometry("660x780")
        window.minsize(590, 660)
        window.transient(self)
        window.grab_set()

        content = ctk.CTkScrollableFrame(window, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(
            content,
            text=(
                "⚠ Expert settings. These options can change network load, Store interpretation and the technical data shown. "
                "Change them only when genuinely necessary. Reset to defaults if you are unsure."
            ),
            wraplength=570,
            justify="left",
            text_color="#8A5A18",
            fg_color="#FFF6E5",
            corner_radius=8,
        ).pack(fill="x", pady=(0, 12), ipady=8)

        language_var = tk.StringVar(value=str(self.user_settings.get("store_language") or "en"))
        fallback_var = tk.StringVar(
            value=str(self.user_settings.get("fallback_countries") or features.DEFAULT_FALLBACK_COUNTRIES)
        )
        cache_var = tk.BooleanVar(value=bool(self.user_settings.get("cache_enabled", True)))
        ttl_var = tk.IntVar(value=int(self.user_settings.get("cache_ttl_hours", 72)))
        device_var = tk.BooleanVar(value=bool(self.user_settings.get("collect_device_metadata", True)))
        compare_var = tk.BooleanVar(value=bool(self.user_settings.get("compare_previous", False)))

        store = ctk.CTkFrame(content)
        store.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(store, text="Store, fallback markets and cache", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(store, text="Store language").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(store, textvariable=language_var, width=100).grid(row=1, column=1, sticky="w", padx=12, pady=6)
        ctk.CTkLabel(store, text="Fallback Store countries").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(store, textvariable=fallback_var, width=380).grid(row=2, column=1, sticky="ew", padx=12, pady=6)
        ctk.CTkLabel(
            store,
            text="Comma/space separated 2-letter codes, e.g. us, gb, de, fr, it, ch. They stay hidden from the normal UI and are used only when the selected Store country is unavailable or inconclusive.",
            wraplength=560,
            justify="left",
            text_color="#6C7781",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 8))
        ctk.CTkCheckBox(store, text="Use intelligent cache", variable=cache_var).grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=6)
        ctk.CTkLabel(store, text="Healthy-result cache TTL").grid(row=5, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(store, textvariable=ttl_var, width=90).grid(row=5, column=1, sticky="w", padx=12, pady=6)
        ctk.CTkLabel(store, text="hours (default 72)", text_color="#6C7781").grid(row=5, column=1, sticky="w", padx=(110, 12), pady=6)
        ctk.CTkLabel(
            store,
            text="Only healthy available listings with a valid update date are cached. Removed, anomaly and error states always run live.",
            wraplength=560,
            justify="left",
            text_color="#6C7781",
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 12))
        store.grid_columnconfigure(1, weight=1)

        device = ctk.CTkFrame(content)
        device.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(device, text="Connected Android device", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(
            device,
            text="Collect installed version and installer source during ADB audits",
            variable=device_var,
        ).pack(anchor="w", padx=12, pady=4)
        ctk.CTkLabel(
            device,
            text="Enabled by default. Version comparison reports Match / Different / Device-specific / Unknown; it does not assume that a different version is necessarily outdated.",
            wraplength=560,
            justify="left",
            text_color="#6C7781",
        ).pack(anchor="w", padx=12, pady=(4, 12))

        history = ctk.CTkFrame(content)
        history.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(history, text="Audit history", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(history, text="Compare with previous audit", variable=compare_var).pack(anchor="w", padx=12, pady=4)
        ctk.CTkLabel(
            history,
            text="Off by default. The first completed audit creates a local baseline; later audits can show New / Same / Better / Worse.",
            wraplength=560,
            justify="left",
            text_color="#6C7781",
        ).pack(anchor="w", padx=12, pady=(4, 12))

        technical = ctk.CTkFrame(content)
        technical.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(technical, text="Technical columns", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        technical_vars: dict[str, tk.BooleanVar] = {}
        selected = set(self.user_settings.get("technical_columns", []))
        for key, label in user_state.TECHNICAL_COLUMNS.items():
            variable = tk.BooleanVar(value=key in selected)
            technical_vars[key] = variable
            ctk.CTkCheckBox(technical, text=label, variable=variable).pack(anchor="w", padx=12, pady=3)
        ctk.CTkLabel(
            technical,
            text="These fields are mainly useful for diagnostics and expert inspection.",
            text_color="#6C7781",
        ).pack(anchor="w", padx=12, pady=(6, 12))

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))

        def reset_controls() -> None:
            language_var.set("en")
            fallback_var.set(features.DEFAULT_FALLBACK_COUNTRIES)
            cache_var.set(True)
            ttl_var.set(72)
            device_var.set(True)
            compare_var.set(False)
            for variable in technical_vars.values():
                variable.set(False)

        def save_and_close() -> None:
            try:
                ttl = max(1, min(720, int(ttl_var.get())))
            except Exception:
                messagebox.showerror(
                    "Invalid setting",
                    "Cache TTL must be a number between 1 and 720 hours.",
                    parent=window,
                )
                return
            fallback_text, invalid = features.normalise_country_string(fallback_var.get())
            previous_fallback = str(self.user_settings.get("fallback_countries") or "")
            self.user_settings.update(
                {
                    "store_language": (language_var.get().strip() or "en").lower(),
                    "fallback_countries": fallback_text,
                    "cache_enabled": bool(cache_var.get()),
                    "cache_ttl_hours": ttl,
                    "collect_device_metadata": bool(device_var.get()),
                    "compare_previous": bool(compare_var.get()),
                    "technical_columns": [
                        key for key, variable in technical_vars.items() if variable.get()
                    ],
                }
            )
            self.user_settings = user_state.save_settings(self.user_settings)
            if previous_fallback.strip().lower() != fallback_text.strip().lower():
                user_state.clear_cache()
            self.language_var.set(str(self.user_settings.get("store_language") or "en"))
            self._apply_column_visibility()
            status = "Advanced settings saved; audit-related changes apply from the next run"
            if invalid:
                status += " | ignored invalid country entries: " + ", ".join(invalid)
            self.status_var.set(status)
            window.destroy()

        ctk.CTkButton(
            buttons,
            text="Reset to defaults",
            command=reset_controls,
            fg_color="#6C7781",
        ).pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Cancel",
            command=window.destroy,
            fg_color="#6C7781",
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", command=save_and_close).pack(side="right")

    # ---------- Column visibility / dashboard ----------
    def _visible_column_order(self) -> list[str]:
        columns = ["criticality"]
        if self.user_settings.get("compare_previous"):
            columns.append("change")
        columns.extend(v7.PRIMARY_COLUMNS[1:])
        selected = self.user_settings.get("technical_columns", [])
        columns.extend(
            column for column in user_state.TECHNICAL_COLUMNS if column in selected and column in V8_MODEL_COLUMNS
        )
        return columns

    def _refresh_table(self) -> None:
        super()._refresh_table()
        if self.current_rows:
            try:
                visible_count = len(self._filtered_rows())
            except Exception:
                visible_count = len(self.current_rows)
            rows = self._rows_before_criticality_filter()
            self.summary_var.set(features.dashboard_summary(rows, visible_count))

    # ---------- Details / context menu ----------
    def _show_details(self, row: dict[str, Any]) -> None:
        window = ctk.CTkToplevel(self)
        window.title("App details")
        window.geometry("720x680")
        window.minsize(620, 520)
        window.transient(self)
        content = ctk.CTkScrollableFrame(window, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(
            content,
            text=str(row.get("play_title") or row.get("package_name") or "App"),
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", pady=(0, 10))
        fields = [
            ("Status", "criticality"),
            ("Change", "change"),
            ("Package Name", "package_name"),
            ("Play Store Title", "play_title"),
            ("Last update", "play_last_update"),
            ("Age (days)", "age_days"),
            ("Play Store version", "play_version"),
            ("Installed version", "installed_version"),
            ("Installed vs Store", "version_comparison"),
            ("Installer source", "installer_source"),
            ("Play status", "play_status"),
            ("Update source", "updated_source"),
            ("HTTP status", "play_http_status"),
            ("System app", "is_system"),
            ("Notes", "notes"),
        ]
        for label, key in fields:
            value = str(row.get(key, "") or "")
            if not value and key not in {"notes", "change"}:
                continue
            box = ctk.CTkFrame(content)
            box.pack(fill="x", pady=3)
            ctk.CTkLabel(box, text=label, width=150, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 8), pady=7)
            ctk.CTkLabel(box, text=value, anchor="w", justify="left", wraplength=500).pack(side="left", fill="x", expand=True, padx=(0, 10), pady=7)

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(
            buttons,
            text="Open in Google Play",
            command=lambda: webbrowser.open(str(row.get("store_url") or "")),
            state="normal" if row.get("store_url") else "disabled",
        ).pack(side="left")
        ctk.CTkButton(buttons, text="Close", command=window.destroy, fg_color="#6C7781").pack(side="right")

    def _show_row_context_menu(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        values = self.tree.item(item, "values")
        if len(values) < 2:
            return
        package_name = str(values[1])
        row = next(
            (entry for entry in self.current_rows if str(entry.get("package_name")) == package_name),
            None,
        )
        if not row:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="App details…", command=lambda: self._show_details(row))
        menu.add_command(
            label="Force recheck this app",
            command=lambda: self._start_subset_refresh([package_name], "App recheck"),
        )
        menu.add_command(
            label="Open in Google Play",
            command=lambda: webbrowser.open(str(row.get("store_url") or "")),
        )
        menu.add_separator()
        menu.add_command(
            label="Copy package name",
            command=lambda: self._copy_text(str(row.get("package_name") or "")),
        )
        menu.add_command(
            label="Copy Play Store title",
            command=lambda: self._copy_text(str(row.get("play_title") or "")),
        )
        menu.add_command(
            label="Copy Store URL",
            command=lambda: self._copy_text(str(row.get("store_url") or "")),
        )
        menu.add_command(
            label="Copy visible row",
            command=lambda: self._copy_text(
                "\t".join(
                    str(row.get(column, "") or "")
                    for column in self._visible_column_order()
                )
            ),
        )
        menu.tk_popup(event.x_root, event.y_root)

    # ---------- Rechecks ----------
    def _force_full_refresh(self) -> None:
        if self._audit_active:
            messagebox.showinfo(
                "Audit running",
                "Pause/resume or wait for the current audit to finish first.",
                parent=self,
            )
            return
        self._force_refresh_next = True
        self._merge_base_rows = None
        self._subset_label = "Full refresh"
        self._start_audit()

    def _recheck_problematic(self) -> None:
        packages = [
            str(row.get("package_name") or "")
            for row in self.current_rows
            if features.is_problematic(row)
        ]
        if not packages:
            messagebox.showinfo(
                "No problematic apps",
                "There are no Removed, Store anomaly or Other results to recheck.",
                parent=self,
            )
            return
        self._start_subset_refresh(packages, "Problematic-app recheck")

    def _start_subset_refresh(self, packages: list[str], label: str) -> None:
        if self._audit_active:
            messagebox.showinfo(
                "Audit running",
                "Wait for the current audit to finish before starting a targeted recheck.",
                parent=self,
            )
            return
        wanted = {package for package in packages if package}
        source_rows = [
            row for row in self.current_rows if str(row.get("package_name") or "") in wanted
        ]
        if not source_rows:
            messagebox.showinfo(
                "Nothing to recheck",
                "No matching app is present in the current results.",
                parent=self,
            )
            return
        self._merge_base_rows = [dict(row) for row in self.current_rows]
        self._subset_label = label
        self._apps_override = [
            {
                "app_name": str(row.get("app_name") or row.get("play_title") or row.get("package_name") or ""),
                "package_name": str(row.get("package_name") or ""),
            }
            for row in source_rows
        ]
        self._force_refresh_next = True
        self._start_audit()
        if self._audit_active and self._merge_base_rows is not None:
            self.current_rows = [dict(row) for row in self._merge_base_rows]
            self._refresh_table()

    def _get_apps_to_audit(self):
        if self._apps_override is not None:
            system = {
                str(row.get("package_name") or "")
                for row in (self._merge_base_rows or self.current_rows)
                if row.get("is_system")
            }
            return list(self._apps_override), system, "targeted manual recheck"
        return super()._get_apps_to_audit()

    def _start_audit(self) -> None:
        global _BYPASS_CACHE_ONCE
        if self._audit_active:
            super()._start_audit()
            return
        settings = user_state.load_settings()
        selected_country = (self.country_var.get().strip() or "").lower()
        features.set_fallback_countries(
            settings.get("fallback_countries", features.DEFAULT_FALLBACK_COUNTRIES),
            selected_country,
        )
        _BYPASS_CACHE_ONCE = bool(self._force_refresh_next)
        try:
            super()._start_audit()
        finally:
            _BYPASS_CACHE_ONCE = False
            self._force_refresh_next = False
            self._apps_override = None

    # ---------- Worker / ADB metadata ----------
    def _controlled_audit_worker(
        self,
        all_apps,
        live_apps,
        cached,
        config,
        session,
        pause_event,
        cancel_event,
        cache_enabled,
    ) -> None:
        metadata_executor: ThreadPoolExecutor | None = None
        metadata_future = None
        try:
            settings = user_state.load_settings()
            if self.source_mode == "device" and settings.get("collect_device_metadata", True):
                adb = self._get_authorised_adb()
                if adb:
                    metadata_executor = ThreadPoolExecutor(max_workers=1)
                    metadata_future = metadata_executor.submit(
                        features.collect_device_metadata,
                        adb,
                        [app["package_name"] for app in all_apps],
                        cancel_event,
                    )

            cached_count = len(cached)
            total_count = len(all_apps)

            def progress(done: int, _total: int, package_name: str) -> None:
                if cancel_event.is_set() or session != self._audit_session:
                    return
                self.progress_queue.put(
                    ("controlled_progress", session, cached_count + done, total_count, package_name)
                )

            live_rows = (
                features.audit_apps_v8(
                    live_apps,
                    config,
                    progress,
                    pause_event=pause_event,
                    cancel_event=cancel_event,
                )
                if live_apps
                else []
            )
            if cancel_event.is_set() or session != self._audit_session:
                return
            if cache_enabled and live_rows:
                v7.update_cache(live_rows, config.country, config.language)
            by_package = {package: dict(row) for package, row in cached.items()}
            by_package.update(
                {str(row.get("package_name") or ""): row for row in live_rows}
            )
            rows = [
                by_package[app["package_name"]]
                for app in all_apps
                if app["package_name"] in by_package
            ]
            metadata = metadata_future.result() if metadata_future is not None else {}
            features.enrich_rows_with_device_metadata(rows, metadata)
            self._pending_device_metadata = metadata
            self.progress_queue.put(
                ("v8_done", session, rows, cached_count, len(live_rows))
            )
        except Exception as exc:
            if not cancel_event.is_set() and session == self._audit_session:
                self.progress_queue.put(("controlled_error", session, str(exc)))
        finally:
            if metadata_executor is not None:
                metadata_executor.shutdown(wait=False, cancel_futures=True)

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
                    self.status_var.set(
                        f"Paused | {done}/{total} completed"
                        if self._audit_paused
                        else f"Completed {done}/{total}: {package_name}"
                    )

                elif kind == "v8_done":
                    _, session, rows, cached_count, live_count = message
                    if session != self._audit_session:
                        continue
                    compare_enabled = bool(self.user_settings.get("compare_previous", False))
                    history = user_state.load_history() if compare_enabled else {}
                    for row in rows:
                        row["is_system"] = (
                            str(row.get("package_name") or "") in self.current_system_packages
                        )
                        self._classify_criticality(row)
                        row["change"] = (
                            user_state.compare_with_history(row, history)
                            if compare_enabled
                            else ""
                        )

                    if self._merge_base_rows is not None:
                        old_rows = self._merge_base_rows
                        label = self._subset_label or "Recheck"
                        replacements = {
                            str(row.get("package_name") or ""): row for row in rows
                        }
                        merged = [
                            replacements.get(str(row.get("package_name") or ""), old)
                            for old in old_rows
                        ]
                        self._merge_base_rows = None
                        self._subset_label = ""
                        if compare_enabled:
                            features.save_history_merged(merged)
                        self.current_rows = merged
                        status_text = f"{label} completed | {len(rows)} app(s) refreshed live"
                    else:
                        if compare_enabled:
                            features.save_history_merged(rows)
                        self.current_rows = rows
                        cache_summary = (
                            f" | {cached_count} cached | {live_count} live"
                            if cached_count
                            else f" | {live_count} live"
                        )
                        status_text = f"Audit completed{cache_summary}"

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
                    self.export_button.configure(
                        state="normal" if self.current_rows else "disabled"
                    )
                    self.progress["value"] = self.progress["maximum"]
                    self.status_var.set(status_text)
                    self._apply_column_visibility()
                    self._refresh_table()

                elif kind == "controlled_error":
                    _, session, error = message
                    if session != self._audit_session:
                        continue
                    if self._merge_base_rows is not None:
                        self.current_rows = self._merge_base_rows
                        self._merge_base_rows = None
                        self._subset_label = ""
                    self._audit_active = False
                    self._audit_paused = False
                    self._audit_pause_event.set()
                    self._set_audit_source_controls_enabled(True)
                    self._set_run_mode("run")
                    self.export_button.configure(
                        state="normal" if self.current_rows else "disabled"
                    )
                    self.status_var.set("Audit failed")
                    self._refresh_table()
                    messagebox.showerror("Audit error", error, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._process_queue)


def main() -> None:
    app = CustomTkPlayStoreAuditV8()
    app.mainloop()


if __name__ == "__main__":
    main()
