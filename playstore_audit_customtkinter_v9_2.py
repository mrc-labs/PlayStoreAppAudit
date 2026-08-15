from __future__ import annotations

import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from typing import Any
from tkinter import filedialog, messagebox

from playstore_audit_process import install_hidden_subprocess_windows
install_hidden_subprocess_windows()

import customtkinter as ctk

import playstore_audit_customtkinter_v9 as v9
import playstore_audit_customtkinter_v9_stable as stable
import playstore_audit_user_state as user_state
import playstore_audit_v9_2_features as v92

v9.features.VIEW_PRESETS = v92.VIEW_PRESETS
v9.features.CSV_EXPORT_GUIDE = v92.CSV_EXPORT_GUIDE
v9.features.APP_VERSION = v92.APP_VERSION


class CustomTkPlayStoreAuditV92(stable.CustomTkPlayStoreAuditV9Stable):
    def __init__(self) -> None:
        self._status_filters: set[str] = set()
        settings = user_state.load_settings()
        settings["active_filter_preset"] = "All"
        user_state.save_settings(settings)
        super().__init__()
        self._active_filter_preset = "All"
        self._find_all_filter_button()
        self._sync_status_filter_buttons()
        self._refresh_table()

    # ---------- Views ----------
    def _visible_column_order(self) -> list[str]:
        settings = user_state.load_settings()
        preset = str(settings.get("view_preset") or "Basic")
        compare = bool(settings.get("compare_previous", False))
        health = bool(settings.get("health_score_enabled", False))

        if preset == "Technical":
            columns = list(v9.V9_MODEL_COLUMNS)
            if not compare and "change" in columns:
                columns.remove("change")
        elif preset == "Device":
            columns = ["criticality"]
            if compare:
                columns.append("change")
            columns += [
                "package_name", "play_title", "play_last_update", "age_days",
                "compatibility_status", "installed_version", "version_comparison",
                "installer_source", "app_enabled", "device_change",
            ]
            if health:
                columns.append("health_score")
            columns.append("notes")
        elif preset == "Custom":
            configured = settings.get("custom_view_columns", v92.DEFAULT_CUSTOM_VIEW_COLUMNS)
            columns = [c for c in configured if c in v9.V9_MODEL_COLUMNS] if isinstance(configured, list) else list(v92.DEFAULT_CUSTOM_VIEW_COLUMNS)
            if "criticality" not in columns:
                columns.insert(0, "criticality")
            if "package_name" not in columns:
                columns.insert(1, "package_name")
            if compare and "change" not in columns:
                columns.insert(1, "change")
        else:
            columns = ["criticality"]
            if compare:
                columns.append("change")
            columns += ["package_name", "play_title", "play_last_update", "age_days", "notes"]
        return list(dict.fromkeys(columns))

    # ---------- Multi-status filters ----------
    def _set_criticality_filter(self, key: str | None) -> None:
        if key is None:
            self._status_filters.clear()
        elif key in self._status_filters:
            self._status_filters.remove(key)
        else:
            self._status_filters.add(key)
        self.criticality_filter = None
        self._refresh_table()

    def _filtered_rows(self):
        rows = self._rows_before_criticality_filter()
        if self._status_filters:
            rows = [row for row in rows if str(row.get("criticality_key") or "") in self._status_filters]
        return rows

    def _find_all_filter_button(self) -> None:
        self._all_status_button = None
        try:
            first = next(iter(self.criticality_buttons.values()))
            for child in first.master.winfo_children():
                if isinstance(child, ctk.CTkButton) and str(child.cget("text")) == "All":
                    self._all_status_button = child
                    break
        except Exception:
            self._all_status_button = None

    def _sync_status_filter_buttons(self) -> None:
        if not hasattr(self, "criticality_buttons"):
            return
        if getattr(self, "_all_status_button", None) is None:
            self._find_all_filter_button()
        if self._all_status_button is not None:
            self._all_status_button.configure(
                border_width=2 if not self._status_filters else 0,
                border_color="#657786",
            )
        for key, button in self.criticality_buttons.items():
            info = self.CRITICALITY[key]
            selected = key in self._status_filters
            button.configure(
                border_width=2 if selected else 1,
                border_color=info.get("foreground", "#657786") if selected else info["background"],
            )

    # ---------- Date display + concise summary ----------
    def _refresh_table(self) -> None:
        backups: list[tuple[dict[str, Any], str, Any]] = []
        style = v92.configured_date_format()
        if hasattr(self, "current_rows"):
            for row in self.current_rows:
                for field in v92.DATE_FIELDS:
                    if field in row:
                        backups.append((row, field, row.get(field)))
                        row[field] = v92.format_date_value(row.get(field), style)
        try:
            super()._refresh_table()
        finally:
            for row, field, value in backups:
                row[field] = value

        if hasattr(self, "summary_var") and hasattr(self, "current_rows"):
            try:
                visible = len(self._filtered_rows())
            except Exception:
                visible = len(self.current_rows)
            self.summary_var.set(v92.concise_summary(list(self.current_rows), visible))
        self._sync_status_filter_buttons()

    def _clear_results(self) -> None:
        self._status_filters.clear()
        super()._clear_results()
        self._sync_status_filter_buttons()
        if hasattr(self, "summary_var"):
            self.summary_var.set("No results yet")

    # ---------- Menu ----------
    def _build_menu_v9(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Choose app list…", command=self._choose_input)
        recent = tk.Menu(file_menu, tearoff=0)
        paths = v9.features.get_recent_sources()
        if paths:
            for path in paths:
                recent.add_command(label=Path(path).name, command=lambda p=path: self._load_input_file(p))
        else:
            recent.add_command(label="No recent files", state="disabled")
        file_menu.add_cascade(label="Recent sources", menu=recent)
        file_menu.add_command(label="Scan phone with ADB", command=self._scan_phone)
        file_menu.add_command(label="Export current phone package list as CSV…", command=self._export_phone_packages_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Export all results as CSV…", command=self._export_results)
        file_menu.add_command(label="Export visible results as CSV…", command=self._export_visible_results)
        file_menu.add_command(label="Export HTML report…", command=self._export_html_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        view = tk.Menu(menubar, tearoff=0)
        view_presets = tk.Menu(view, tearoff=0)
        current = str(user_state.load_settings().get("view_preset") or "Basic")
        self._view_menu_var = tk.StringVar(value=current)
        for name in v92.VIEW_PRESETS:
            view_presets.add_radiobutton(
                label=name,
                value=name,
                variable=self._view_menu_var,
                command=lambda n=name: self._set_view_preset(n),
            )
        view.add_cascade(label="View preset", menu=view_presets)
        view.add_separator()
        view.add_command(label="Reset table layout", command=self._reset_table_layout)
        menubar.add_cascade(label="View", menu=view)

        tools = tk.Menu(menubar, tearoff=0)
        tools.add_command(label="Advanced settings…", command=self._show_advanced_settings)
        tools.add_separator()
        tools.add_command(label="Force full refresh (ignore cache)", command=self._force_full_refresh)
        tools.add_command(label="Recheck Removed / Anomaly / Other", command=self._recheck_problematic)
        tools.add_separator()
        tools.add_command(label="Device summary…", command=self._show_device_summary)
        snapshots = tk.Menu(tools, tearoff=0)
        snapshots.add_command(label="Save current device snapshot…", command=self._save_device_snapshot)
        snapshots.add_command(label="Compare current device with snapshot…", command=self._compare_device_snapshot)
        tools.add_cascade(label="Device snapshots", menu=snapshots)
        tools.add_command(label="Device inventory changes…", command=self._show_inventory_changes)
        tools.add_separator()
        tools.add_command(label="Clear audit cache", command=self._clear_audit_cache)
        tools.add_command(label="Clear previous-audit history", command=self._clear_audit_history)
        menubar.add_cascade(label="Tools", menu=tools)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="ADB setup guide…", command=lambda: self._show_text_help("ADB setup guide", v9.features.ADB_SETUP_GUIDE))
        help_menu.add_command(label="How to export package CSV…", command=lambda: self._show_text_help("Export package CSV", v92.CSV_EXPORT_GUIDE))
        help_menu.add_command(label="Health score methodology…", command=lambda: self._show_text_help("Health score methodology", v9.features.HEALTH_SCORE_GUIDE))
        help_menu.add_separator()
        help_menu.add_command(label="Check for updates…", command=self._check_for_updates)
        help_menu.add_command(label="Create diagnostic bundle…", command=self._create_diagnostic_bundle)
        help_menu.add_separator()
        help_menu.add_command(label="About Play Store App Audit", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        tk.Tk.config(self, menu=menubar)
        self._menu_bar = menubar

    # ---------- Advanced settings ----------
    def _show_advanced_settings(self) -> None:
        self.user_settings = user_state.load_settings()
        window = ctk.CTkToplevel(self)
        window.title("Advanced settings")
        window.geometry("780x840")
        window.minsize(690, 690)
        window.transient(self)
        window.grab_set()

        content = ctk.CTkScrollableFrame(window, fg_color="transparent", width=720)
        content.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(
            content,
            text="⚠ Expert settings. These options can change Store interpretation, ADB collection, cache behaviour and the data shown. Change them only when genuinely necessary.",
            wraplength=680,
            justify="left",
            text_color="#8A5A18",
            fg_color="#FFF6E5",
            corner_radius=8,
        ).pack(fill="x", pady=(0, 12), ipady=8)

        s = self.user_settings
        language = tk.StringVar(value=str(s.get("store_language") or "en"))
        fallback = tk.StringVar(value=str(s.get("fallback_countries") or v9.v8.features.DEFAULT_FALLBACK_COUNTRIES))
        date_format = tk.StringVar(value=str(s.get("date_format") or v92.DEFAULT_DATE_FORMAT))
        cache = tk.BooleanVar(value=bool(s.get("cache_enabled", True)))
        ttl = tk.IntVar(value=int(s.get("cache_ttl_hours", 72)))
        collect = tk.BooleanVar(value=bool(s.get("collect_device_metadata", True)))
        permissions = tk.BooleanVar(value=bool(s.get("permissions_audit_enabled", False)))
        inventory = tk.BooleanVar(value=bool(s.get("inventory_history_enabled", True)))
        health = tk.BooleanVar(value=bool(s.get("health_score_enabled", False)))
        compare = tk.BooleanVar(value=bool(s.get("compare_previous", False)))
        portable = tk.BooleanVar(value=v9.features.portable_mode_active())

        store = ctk.CTkFrame(content)
        store.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(store, text="Store, dates and cache", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(store, text="Store language").grid(row=1, column=0, sticky="w", padx=12, pady=5)
        ctk.CTkEntry(store, textvariable=language, width=100).grid(row=1, column=1, sticky="w", padx=12, pady=5)
        ctk.CTkLabel(store, text="Fallback Store countries").grid(row=2, column=0, sticky="w", padx=12, pady=5)
        ctk.CTkEntry(store, textvariable=fallback, width=420).grid(row=2, column=1, sticky="ew", padx=12, pady=5)
        ctk.CTkLabel(store, text="Date display format").grid(row=3, column=0, sticky="w", padx=12, pady=5)
        ctk.CTkOptionMenu(store, values=list(v92.DATE_FORMATS), variable=date_format, width=190).grid(row=3, column=1, sticky="w", padx=12, pady=5)
        ctk.CTkCheckBox(store, text="Use intelligent cache", variable=cache).grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=5)
        ctk.CTkLabel(store, text="Healthy-result cache TTL").grid(row=5, column=0, sticky="w", padx=12, pady=5)
        ctk.CTkEntry(store, textvariable=ttl, width=90).grid(row=5, column=1, sticky="w", padx=12, pady=5)
        store.grid_columnconfigure(1, weight=1)

        device = ctk.CTkFrame(content)
        device.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(device, text="Connected Android device", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(device, text="Collect connected-device metadata", variable=collect).pack(anchor="w", padx=12, pady=3)
        ctk.CTkCheckBox(device, text="Audit sensitive requested permissions (advanced)", variable=permissions).pack(anchor="w", padx=12, pady=3)
        ctk.CTkLabel(
            device,
            text="Checks a curated list of permissions declared/requested by each package (camera, microphone, location, contacts, SMS, phone, media, all-files access, overlays, etc.). It does not decide whether a permission is granted, justified or malicious. The same package dump is already collected for device metadata, so this mainly adds parsing rather than extra per-app ADB calls.",
            wraplength=680,
            justify="left",
            text_color="#6C7781",
        ).pack(anchor="w", padx=12, pady=(3, 7))
        ctk.CTkCheckBox(device, text="Keep per-device inventory history", variable=inventory).pack(anchor="w", padx=12, pady=3)
        ctk.CTkCheckBox(device, text="Enable experimental Health score", variable=health).pack(anchor="w", padx=12, pady=(3, 12))

        history = ctk.CTkFrame(content)
        history.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(history, text="Audit history", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(history, text="Compare with previous Play Store audit", variable=compare).pack(anchor="w", padx=12, pady=(0, 12))

        storage = ctk.CTkFrame(content)
        storage.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(storage, text="Storage", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(storage, text="Portable mode: keep app data next to the EXE", variable=portable).pack(anchor="w", padx=12, pady=3)
        ctk.CTkLabel(storage, text="Changing portable mode migrates local app data and requires a restart. The EXE folder must be writable.", wraplength=680, justify="left", text_color="#6C7781").pack(anchor="w", padx=12, pady=(4, 12))

        custom = ctk.CTkFrame(content)
        custom.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(custom, text="Custom view columns", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))
        configured = set(s.get("custom_view_columns", v92.DEFAULT_CUSTOM_VIEW_COLUMNS))
        custom_vars: dict[str, tk.BooleanVar] = {}
        choices = [c for c in v9.V9_MODEL_COLUMNS if c not in {"criticality", "package_name"}]
        for i, key in enumerate(choices):
            var = tk.BooleanVar(value=key in configured)
            custom_vars[key] = var
            label = v9.v8.v7.COLUMN_LABELS.get(key, key)
            ctk.CTkCheckBox(custom, text=label, variable=var).grid(row=1 + i // 2, column=i % 2, sticky="w", padx=12, pady=2)
        ctk.CTkLabel(custom, text="Status and Package Name are always included. Choose View → View preset → Custom to use this selection.", wraplength=680, justify="left", text_color="#6C7781").grid(row=2 + len(choices) // 2, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 12))
        custom.grid_columnconfigure(0, weight=1)
        custom.grid_columnconfigure(1, weight=1)

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))
        old_portable = v9.features.portable_mode_active()

        def reset_controls() -> None:
            language.set("en")
            fallback.set(v9.v8.features.DEFAULT_FALLBACK_COUNTRIES)
            date_format.set(v92.DEFAULT_DATE_FORMAT)
            cache.set(True)
            ttl.set(72)
            collect.set(True)
            permissions.set(False)
            inventory.set(True)
            health.set(False)
            compare.set(False)
            portable.set(False)
            defaults = set(v92.DEFAULT_CUSTOM_VIEW_COLUMNS)
            for key, var in custom_vars.items():
                var.set(key in defaults)

        def save_and_close() -> None:
            try:
                ttl_value = max(1, min(720, int(ttl.get())))
            except Exception:
                messagebox.showerror("Invalid setting", "Cache TTL must be a number between 1 and 720 hours.", parent=window)
                return
            fallback_text, invalid = v9.v8.features.normalise_country_string(fallback.get())
            previous_fallback = str(self.user_settings.get("fallback_countries") or "")
            custom_columns = ["criticality", "package_name"] + [k for k, var in custom_vars.items() if var.get()]
            self.user_settings.update({
                "store_language": (language.get().strip() or "en").lower(),
                "fallback_countries": fallback_text,
                "date_format": date_format.get(),
                "cache_enabled": bool(cache.get()),
                "cache_ttl_hours": ttl_value,
                "collect_device_metadata": bool(collect.get()),
                "permissions_audit_enabled": bool(permissions.get()),
                "inventory_history_enabled": bool(inventory.get()),
                "health_score_enabled": bool(health.get()),
                "compare_previous": bool(compare.get()),
                "custom_view_columns": list(dict.fromkeys(custom_columns)),
            })
            self.user_settings = user_state.save_settings(self.user_settings)
            if previous_fallback.strip().lower() != fallback_text.strip().lower():
                user_state.clear_cache()
            if bool(portable.get()) != old_portable:
                ok, portable_msg = v9.features.migrate_portable_mode(bool(portable.get()))
                if not ok:
                    messagebox.showwarning("Portable mode", portable_msg, parent=window)
            self._apply_column_visibility()
            self._refresh_table()
            msg = "Advanced settings saved"
            if invalid:
                msg += " | ignored invalid country entries: " + ", ".join(invalid)
            self.status_var.set(msg)
            window.destroy()

        ctk.CTkButton(buttons, text="Reset to defaults", command=reset_controls, fg_color="#6C7781").pack(side="left")
        ctk.CTkButton(buttons, text="Cancel", command=window.destroy, fg_color="#6C7781").pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", command=save_and_close).pack(side="right")

    # ---------- Details / exports ----------
    def _show_details(self, row: dict[str, Any]) -> None:
        super()._show_details(v92.rows_for_output([row])[0])

    def _export_rows(self, rows: list[dict[str, object]], default_name: str) -> None:
        super()._export_rows(v92.rows_for_output([dict(r) for r in rows]), default_name)

    def _export_html_report(self) -> None:
        if not self.current_rows:
            messagebox.showinfo("Nothing to export", "There are no results to export.", parent=self)
            return
        selected = filedialog.asksaveasfilename(
            title="Export HTML report",
            defaultextension=".html",
            initialfile="playstore_audit_report.html",
            filetypes=[("HTML", "*.html")],
        )
        if not selected:
            return
        try:
            v9.features.write_html_report(selected, v92.rows_for_output(list(self.current_rows)), self._device_summary)
            messagebox.showinfo("Export complete", f"HTML report saved to:\n{selected}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _show_about(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("About Play Store App Audit")
        window.geometry("540x330")
        window.resizable(False, False)
        window.transient(self)
        ctk.CTkLabel(window, text="Play Store App Audit", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(window, text="Created by MRC", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20, pady=(0, 12))
        ctk.CTkLabel(window, text="Audit Android packages against public Google Play listings, update dates, regional availability and optional connected-device metadata.\n\nUnofficial utility. Not affiliated with or endorsed by Google.", wraplength=490, justify="left").pack(anchor="w", padx=20)
        ctk.CTkButton(window, text="MRC on GitHub", command=lambda: webbrowser.open(v9.v8.v7.PROJECT_URL)).pack(anchor="w", padx=20, pady=16)
        ctk.CTkButton(window, text="Close", command=window.destroy, width=90, fg_color="#6C7781").pack(anchor="e", padx=20, pady=(0, 20))


def main() -> None:
    app = CustomTkPlayStoreAuditV92()
    app.mainloop()


if __name__ == "__main__":
    main()
