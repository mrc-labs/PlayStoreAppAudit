from __future__ import annotations

import csv
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from typing import Any
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from app_icon import ensure_runtime_icon
from playstore_audit_core import load_apps
import playstore_audit_customtkinter_v8 as v8
import playstore_audit_user_state as user_state
import playstore_audit_v9_features as features


V9_EXTRA_COLUMNS = (
    "compatibility_status",
    "target_sdk",
    "min_sdk",
    "first_install_time",
    "last_local_update",
    "app_enabled",
    "sensitive_permissions_count",
    "sensitive_permissions",
    "device_change",
    "health_score",
)
V9_MODEL_COLUMNS = tuple(dict.fromkeys(tuple(v8.V8_MODEL_COLUMNS) + V9_EXTRA_COLUMNS))
v8.V8_MODEL_COLUMNS = V9_MODEL_COLUMNS
v8.v7.MODEL_COLUMNS = V9_MODEL_COLUMNS
v8.v7.COLUMN_LABELS.update(features.V9_TECHNICAL_COLUMNS)
v8.v7.DEFAULT_WIDTHS.update(
    {
        "compatibility_status": 150,
        "target_sdk": 90,
        "min_sdk": 80,
        "first_install_time": 155,
        "last_local_update": 155,
        "app_enabled": 100,
        "sensitive_permissions_count": 105,
        "sensitive_permissions": 360,
        "device_change": 155,
        "health_score": 90,
    }
)
v8.v7.CustomTkPlayStoreAuditBranch.COLUMNS = V9_MODEL_COLUMNS
v8.v7.CustomTkPlayStoreAuditBranch.COLUMN_LABELS = v8.v7.COLUMN_LABELS
v8.v7.CustomTkPlayStoreAuditBranch.COLUMN_WIDTHS = v8.v7.DEFAULT_WIDTHS
v8.CustomTkPlayStoreAuditV8.COLUMNS = V9_MODEL_COLUMNS
v8.CustomTkPlayStoreAuditV8.COLUMN_LABELS = v8.v7.COLUMN_LABELS
v8.CustomTkPlayStoreAuditV8.COLUMN_WIDTHS = v8.v7.DEFAULT_WIDTHS
v8.CustomTkPlayStoreAuditV8.EXPORT_FIELDS = list(
    dict.fromkeys(list(v8.CustomTkPlayStoreAuditV8.EXPORT_FIELDS) + list(V9_EXTRA_COLUMNS))
)
v8.features.collect_device_metadata = features.collect_device_metadata_v9
v8.features.enrich_rows_with_device_metadata = features.enrich_rows_with_device_metadata_v9


class CustomTkPlayStoreAuditV9(v8.CustomTkPlayStoreAuditV8, TkinterDnD.DnDWrapper):
    COLUMNS = V9_MODEL_COLUMNS
    COLUMN_LABELS = v8.v7.COLUMN_LABELS
    COLUMN_WIDTHS = v8.v7.DEFAULT_WIDTHS
    EXPORT_FIELDS = v8.CustomTkPlayStoreAuditV8.EXPORT_FIELDS

    def __init__(self) -> None:
        self._device_summary: dict[str, Any] = {}
        self._last_inventory_changes: dict[str, Any] = {}
        self._inventory_processed_session = -1
        self._active_filter_preset = "All"
        super().__init__()

        # Native Windows Explorer drag-and-drop for CustomTkinter through tkDnD.
        try:
            self.TkdndVersion = TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_file_drop)
        except Exception as exc:
            features.log_event(f"CustomTkinter drag/drop unavailable: {exc}")

        self._active_filter_preset = str(user_state.load_settings().get("active_filter_preset") or "All")
        self._build_menu_v9()
        self._apply_column_visibility()
        self._refresh_table()
        features.log_event("CustomTkinter v9 started")

    # ---------- Views / filtering ----------
    def _visible_column_order(self) -> list[str]:
        self.user_settings = user_state.load_settings()
        preset = str(self.user_settings.get("view_preset") or "Basic")
        compare = bool(self.user_settings.get("compare_previous", False))
        health = bool(self.user_settings.get("health_score_enabled", False))
        if preset == "Technical":
            columns = list(V9_MODEL_COLUMNS)
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
        else:
            columns = ["criticality"]
            if compare:
                columns.append("change")
            columns.extend(v8.v7.PRIMARY_COLUMNS[1:])
        selected = self.user_settings.get("technical_columns", [])
        if isinstance(selected, list):
            columns.extend(c for c in selected if c in V9_MODEL_COLUMNS)
        return list(dict.fromkeys(c for c in columns if c in V9_MODEL_COLUMNS))

    def _filtered_rows(self):
        rows = super()._filtered_rows()
        return [row for row in rows if features.row_matches_filter(row, self._active_filter_preset)]

    def _classify_criticality(self, row: dict[str, object]) -> None:
        super()._classify_criticality(row)
        features.apply_health_score(row)

    def _set_view_preset(self, name: str) -> None:
        if name not in features.VIEW_PRESETS:
            return
        settings = user_state.load_settings()
        settings["view_preset"] = name
        self.user_settings = user_state.save_settings(settings)
        self._apply_column_visibility()
        self._refresh_table()
        self.status_var.set(f"View preset: {name}")

    def _apply_filter_preset(self, name: str) -> None:
        self._active_filter_preset = name if name in features.BUILTIN_FILTERS else "All"
        settings = user_state.load_settings()
        settings["active_filter_preset"] = self._active_filter_preset
        user_state.save_settings(settings)
        self._build_menu_v9()
        self._refresh_table()
        self.status_var.set(f"Filter preset: {self._active_filter_preset}")

    # ---------- Menus ----------
    def _build_menu_v9(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Choose app list…", command=self._choose_input)
        recent = tk.Menu(file_menu, tearoff=0)
        paths = features.get_recent_sources()
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
        current_view = str(user_state.load_settings().get("view_preset") or "Basic")
        for name in features.VIEW_PRESETS:
            view_presets.add_radiobutton(label=name, value=name, variable=tk.StringVar(value=current_view), command=lambda n=name: self._set_view_preset(n))
        view.add_cascade(label="View preset", menu=view_presets)
        filters = tk.Menu(view, tearoff=0)
        for name in features.BUILTIN_FILTERS:
            prefix = "✓ " if name == self._active_filter_preset else ""
            filters.add_command(label=prefix + name, command=lambda n=name: self._apply_filter_preset(n))
        saved = features.get_saved_filters()
        if saved:
            filters.add_separator()
            for name in sorted(saved):
                filters.add_command(label=f"★ {name}", command=lambda n=name: self._apply_saved_filter(n))
        view.add_cascade(label="Filter preset", menu=filters)
        view.add_command(label="Save current filter as preset…", command=self._save_current_filter)
        view.add_command(label="Manage saved filter presets…", command=self._manage_saved_filters)
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
        help_menu.add_command(label="ADB setup guide…", command=lambda: self._show_text_help("ADB setup guide", features.ADB_SETUP_GUIDE))
        help_menu.add_command(label="How to export package CSV…", command=lambda: self._show_text_help("Export package CSV", features.CSV_EXPORT_GUIDE))
        help_menu.add_command(label="Health score methodology…", command=lambda: self._show_text_help("Health score methodology", features.HEALTH_SCORE_GUIDE))
        help_menu.add_separator()
        help_menu.add_command(label="Check for updates…", command=self._check_for_updates)
        help_menu.add_command(label="Create diagnostic bundle…", command=self._create_diagnostic_bundle)
        help_menu.add_separator()
        help_menu.add_command(label="About Play Store App Audit", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        tk.Tk.config(self, menu=menubar)
        self._menu_bar = menubar

    # ---------- Loading / drag-drop / recent ----------
    def _load_input_file(self, path: str) -> None:
        try:
            apps = load_apps(path)
            metadata = self._read_system_metadata_from_file(path, apps)
        except Exception as exc:
            messagebox.showerror("Invalid app list", str(exc), parent=self)
            return
        self._cancel_active_audit()
        self.file_apps = apps
        self.file_system_metadata = metadata
        self.device_apps_all = []
        self.device_system_packages = set()
        self._device_summary = {}
        self._last_inventory_changes = {}
        self.source_mode = "file"
        self.input_var.set(path)
        meta = f" | system flag available for {len(metadata)} packages" if metadata else ""
        self.source_var.set(f"File selected: {len(apps)} unique Android packages{meta}")
        self.status_var.set("File ready. Run the Play Store audit.")
        features.add_recent_source(path)
        self._build_menu_v9()
        features.log_event(f"Loaded file source: {Path(path).name} ({len(apps)} packages)")

    def _choose_input(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose app list",
            filetypes=[("App lists", "*.csv *.tsv *.txt"), ("CSV", "*.csv"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if selected:
            self._load_input_file(selected)

    def _on_file_drop(self, event):
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        valid = [p for p in paths if Path(p).suffix.lower() in {".csv", ".tsv", ".txt"} and Path(p).is_file()]
        if len(valid) == 1:
            self._load_input_file(valid[0])
        elif valid:
            messagebox.showinfo("Drag & drop", "Drop one app-list file at a time.", parent=self)
        return getattr(event, "action", None)

    # ---------- Device helpers ----------
    def _ensure_device_summary(self) -> None:
        if self.source_mode != "device":
            return
        adb = self._get_authorised_adb()
        if not adb:
            return
        try:
            self._device_summary = features.collect_device_summary(adb, len(self.device_apps_all), len(self.device_system_packages))
        except Exception as exc:
            features.log_event(f"Device summary failed: {exc}")

    def _start_audit(self) -> None:
        if not self._audit_active:
            self._ensure_device_summary()
        super()._start_audit()

    def _export_phone_packages_csv(self) -> None:
        if not self.device_apps_all:
            messagebox.showinfo("No phone scan", "Scan a phone with ADB first.", parent=self)
            return
        selected = filedialog.asksaveasfilename(title="Export phone package list", defaultextension=".csv", initialfile="android_packages.csv", filetypes=[("CSV", "*.csv")])
        if not selected:
            return
        with open(selected, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["package_name", "is_system"])
            writer.writeheader()
            for app in self.device_apps_all:
                package = app["package_name"]
                writer.writerow({"package_name": package, "is_system": package in self.device_system_packages})
        messagebox.showinfo("Export complete", f"Package list saved to:\n{selected}", parent=self)

    def _show_device_summary(self) -> None:
        self._ensure_device_summary()
        if not self._device_summary:
            messagebox.showinfo("No device summary", "Scan a phone with ADB first.", parent=self)
            return
        d = self._device_summary
        messagebox.showinfo(
            "Device summary",
            f"Device: {d.get('manufacturer','')} {d.get('model','')}\nSerial: {d.get('serial_masked','Unknown')}\nAndroid: {d.get('android_version','?')} (API {d.get('android_api','?')})\nSecurity patch: {d.get('security_patch','?')}\nPackages: {d.get('total_packages',0)} total | {d.get('third_party_packages',0)} third-party | {d.get('system_packages',0)} system",
            parent=self,
        )

    def _save_device_snapshot(self) -> None:
        if not self.current_rows or self.source_mode != "device":
            messagebox.showinfo("No device audit", "Run an ADB-based audit first.", parent=self)
            return
        self._ensure_device_summary()
        default = f"{self._device_summary.get('model','android')}_snapshot.psaa.json".replace(" ", "_")
        selected = filedialog.asksaveasfilename(title="Save device snapshot", defaultextension=".psaa.json", initialfile=default, filetypes=[("PSAA snapshot", "*.psaa.json"), ("JSON", "*.json")])
        if selected:
            features.save_snapshot(selected, self.current_rows, self._device_summary)
            messagebox.showinfo("Snapshot saved", f"Saved to:\n{selected}", parent=self)

    def _compare_device_snapshot(self) -> None:
        if not self.current_rows or self.source_mode != "device":
            messagebox.showinfo("No current device", "Run an ADB-based audit for the current phone first.", parent=self)
            return
        selected = filedialog.askopenfilename(title="Choose device snapshot", filetypes=[("PSAA snapshot", "*.psaa.json *.json"), ("JSON", "*.json")])
        if not selected:
            return
        try:
            comparison = features.compare_snapshots(self.current_rows, self._device_summary, features.load_snapshot(selected))
        except Exception as exc:
            messagebox.showerror("Snapshot error", str(exc), parent=self)
            return
        lines = [
            f"Only in saved snapshot: {len(comparison['only_snapshot'])}",
            f"Only on current device: {len(comparison['only_current'])}",
            f"Version differences: {len(comparison['version_differences'])}",
            f"Installer differences: {len(comparison['installer_differences'])}",
            f"Enabled-state differences: {len(comparison['state_differences'])}",
            "",
        ]
        for label, key in (("Only in snapshot", "only_snapshot"), ("Only current", "only_current"), ("Version differences", "version_differences"), ("Installer differences", "installer_differences"), ("State differences", "state_differences")):
            values = comparison[key]
            if values:
                lines.append(label + ":")
                lines.extend(f"  {p}" for p in values[:100])
                if len(values) > 100:
                    lines.append(f"  … {len(values)-100} more")
                lines.append("")
        self._show_text_help("Device comparison", "\n".join(lines))

    def _show_inventory_changes(self) -> None:
        if not self._last_inventory_changes:
            messagebox.showinfo("No inventory comparison", "Run at least two ADB audits on the same device with inventory history enabled.", parent=self)
            return
        data = self._last_inventory_changes
        c = data.get("counts", {})
        lines = [
            f"New on device: {c.get('new',0)}",
            f"Removed from device: {c.get('removed',0)}",
            f"Version changed: {c.get('version',0)}",
            f"Installer changed: {c.get('installer',0)}",
            f"Enabled state changed: {c.get('state',0)}",
        ]
        removed = data.get("removed", [])
        if removed:
            lines += ["", "Removed packages:"] + [f"  {x}" for x in removed[:150]]
        self._show_text_help("Device inventory changes", "\n".join(lines))

    # ---------- Inventory post-processing ----------
    def _refresh_table(self) -> None:
        if (
            hasattr(self, "_audit_session")
            and not getattr(self, "_audit_active", False)
            and self.source_mode == "device"
            and self.current_rows
            and self._inventory_processed_session != self._audit_session
        ):
            for row in self.current_rows:
                features.apply_health_score(row)
            if bool(user_state.load_settings().get("inventory_history_enabled", True)) and self._device_summary:
                self._last_inventory_changes = features.annotate_inventory_changes_and_save(self.current_rows, self._device_summary)
            self._inventory_processed_session = self._audit_session
        super()._refresh_table()

    # ---------- Saved filters ----------
    def _save_current_filter(self) -> None:
        dialog = ctk.CTkInputDialog(text="Preset name", title="Save filter preset")
        name = (dialog.get_input() or "").strip()
        if not name:
            return
        features.save_filter(name, self.filter_var.get(), self.criticality_filter, self.hide_system_var.get(), self._active_filter_preset)
        self._build_menu_v9()
        self.status_var.set(f"Saved filter preset: {name}")

    def _apply_saved_filter(self, name: str) -> None:
        data = features.get_saved_filters().get(name)
        if not isinstance(data, dict):
            return
        self.filter_var.set(str(data.get("query") or ""))
        self.hide_system_var.set(bool(data.get("hide_system", True)))
        self.criticality_filter = str(data.get("criticality") or "") or None
        self._active_filter_preset = str(data.get("preset") or "All")
        self._refresh_table()
        self._build_menu_v9()
        self.status_var.set(f"Applied saved filter: {name}")

    def _manage_saved_filters(self) -> None:
        saved = features.get_saved_filters()
        if not saved:
            messagebox.showinfo("Saved filters", "No custom filter presets have been saved yet.", parent=self)
            return
        window = ctk.CTkToplevel(self)
        window.title("Manage saved filter presets")
        window.geometry("460x420")
        window.transient(self)
        frame = ctk.CTkScrollableFrame(window)
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        for name in sorted(saved):
            row = ctk.CTkFrame(frame)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left", fill="x", expand=True, padx=10, pady=8)
            ctk.CTkButton(row, text="Delete", width=75, fg_color="#8A4F4F", command=lambda n=name, w=window: self._delete_filter_and_close(n, w)).pack(side="right", padx=8, pady=6)

    def _delete_filter_and_close(self, name: str, window) -> None:
        features.delete_filter(name)
        window.destroy()
        self._build_menu_v9()

    # ---------- Advanced settings ----------
    def _show_advanced_settings(self) -> None:
        self.user_settings = user_state.load_settings()
        window = ctk.CTkToplevel(self)
        window.title("Advanced settings")
        window.geometry("720x820")
        window.minsize(620, 680)
        window.transient(self)
        window.grab_set()
        content = ctk.CTkScrollableFrame(window, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(content, text="⚠ Expert settings. These options can change network load, Store interpretation, ADB collection and technical data shown. Change them only when genuinely necessary.", wraplength=620, justify="left", text_color="#8A5A18", fg_color="#FFF6E5", corner_radius=8).pack(fill="x", pady=(0, 12), ipady=8)

        s = self.user_settings
        language = tk.StringVar(value=str(s.get("store_language") or "en"))
        fallback = tk.StringVar(value=str(s.get("fallback_countries") or v8.features.DEFAULT_FALLBACK_COUNTRIES))
        cache = tk.BooleanVar(value=bool(s.get("cache_enabled", True)))
        ttl = tk.IntVar(value=int(s.get("cache_ttl_hours", 72)))
        collect = tk.BooleanVar(value=bool(s.get("collect_device_metadata", True)))
        permissions = tk.BooleanVar(value=bool(s.get("permissions_audit_enabled", False)))
        inventory = tk.BooleanVar(value=bool(s.get("inventory_history_enabled", True)))
        health = tk.BooleanVar(value=bool(s.get("health_score_enabled", False)))
        compare = tk.BooleanVar(value=bool(s.get("compare_previous", False)))
        portable = tk.BooleanVar(value=features.portable_mode_active())

        store = ctk.CTkFrame(content)
        store.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(store, text="Store and cache", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(store, text="Store language").grid(row=1, column=0, sticky="w", padx=12, pady=5)
        ctk.CTkEntry(store, textvariable=language, width=100).grid(row=1, column=1, sticky="w", padx=12, pady=5)
        ctk.CTkLabel(store, text="Fallback Store countries").grid(row=2, column=0, sticky="w", padx=12, pady=5)
        ctk.CTkEntry(store, textvariable=fallback, width=390).grid(row=2, column=1, sticky="ew", padx=12, pady=5)
        ctk.CTkCheckBox(store, text="Use intelligent cache", variable=cache).grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=5)
        ctk.CTkLabel(store, text="Healthy-result cache TTL").grid(row=4, column=0, sticky="w", padx=12, pady=5)
        ctk.CTkEntry(store, textvariable=ttl, width=90).grid(row=4, column=1, sticky="w", padx=12, pady=5)
        store.grid_columnconfigure(1, weight=1)

        device = ctk.CTkFrame(content)
        device.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(device, text="Connected Android device", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(device, text="Collect installed version, installer, Target/Min SDK and local install/update metadata", variable=collect).pack(anchor="w", padx=12, pady=3)
        ctk.CTkCheckBox(device, text="Audit sensitive requested permissions (advanced, slower)", variable=permissions).pack(anchor="w", padx=12, pady=3)
        ctk.CTkCheckBox(device, text="Keep per-device inventory history", variable=inventory).pack(anchor="w", padx=12, pady=3)
        ctk.CTkCheckBox(device, text="Enable experimental Health score", variable=health).pack(anchor="w", padx=12, pady=3)
        ctk.CTkLabel(device, text="Permission audit is OFF by default. Health score is a maintenance heuristic, not a security rating.", wraplength=620, justify="left", text_color="#6C7781").pack(anchor="w", padx=12, pady=(4, 12))

        history = ctk.CTkFrame(content)
        history.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(history, text="Audit history", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(history, text="Compare with previous Play Store audit", variable=compare).pack(anchor="w", padx=12, pady=(0, 12))

        storage = ctk.CTkFrame(content)
        storage.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(storage, text="Storage", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkCheckBox(storage, text="Portable mode: keep settings/cache/history next to the EXE", variable=portable).pack(anchor="w", padx=12, pady=3)
        ctk.CTkLabel(storage, text="Changing portable mode migrates local app data and requires a restart. The EXE folder must be writable.", wraplength=620, justify="left", text_color="#6C7781").pack(anchor="w", padx=12, pady=(4, 12))

        technical = ctk.CTkFrame(content)
        technical.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(technical, text="Technical columns", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 8))
        selected = set(s.get("technical_columns", []))
        technical_vars: dict[str, tk.BooleanVar] = {}
        for key, label in user_state.TECHNICAL_COLUMNS.items():
            var = tk.BooleanVar(value=key in selected)
            technical_vars[key] = var
            ctk.CTkCheckBox(technical, text=label, variable=var).pack(anchor="w", padx=12, pady=2)
        ctk.CTkLabel(technical, text="View → Device/Technical offers quicker presets; these checkboxes are for manual expert customization.", wraplength=620, justify="left", text_color="#6C7781").pack(anchor="w", padx=12, pady=(5, 12))

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))
        old_portable = features.portable_mode_active()

        def reset_controls() -> None:
            language.set("en")
            fallback.set(v8.features.DEFAULT_FALLBACK_COUNTRIES)
            cache.set(True); ttl.set(72); collect.set(True); permissions.set(False); inventory.set(True); health.set(False); compare.set(False); portable.set(False)
            for var in technical_vars.values():
                var.set(False)

        def save_and_close() -> None:
            try:
                ttl_value = max(1, min(720, int(ttl.get())))
            except Exception:
                messagebox.showerror("Invalid setting", "Cache TTL must be a number between 1 and 720 hours.", parent=window)
                return
            fallback_text, invalid = v8.features.normalise_country_string(fallback.get())
            previous_fallback = str(self.user_settings.get("fallback_countries") or "")
            self.user_settings.update({
                "store_language": (language.get().strip() or "en").lower(),
                "fallback_countries": fallback_text,
                "cache_enabled": bool(cache.get()), "cache_ttl_hours": ttl_value,
                "collect_device_metadata": bool(collect.get()),
                "permissions_audit_enabled": bool(permissions.get()),
                "inventory_history_enabled": bool(inventory.get()),
                "health_score_enabled": bool(health.get()),
                "compare_previous": bool(compare.get()),
                "technical_columns": [k for k, var in technical_vars.items() if var.get()],
            })
            self.user_settings = user_state.save_settings(self.user_settings)
            if previous_fallback.strip().lower() != fallback_text.strip().lower():
                user_state.clear_cache()
            msg = "Advanced settings saved"
            if invalid:
                msg += " | ignored invalid country entries: " + ", ".join(invalid)
            if bool(portable.get()) != old_portable:
                ok, portable_msg = features.migrate_portable_mode(bool(portable.get()))
                if not ok:
                    messagebox.showwarning("Portable mode", portable_msg, parent=window)
                else:
                    msg += " | restart required for portable mode"
            self._apply_column_visibility(); self._refresh_table(); self.status_var.set(msg); window.destroy()

        ctk.CTkButton(buttons, text="Reset to defaults", command=reset_controls, fg_color="#6C7781").pack(side="left")
        ctk.CTkButton(buttons, text="Cancel", command=window.destroy, fg_color="#6C7781").pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Save", command=save_and_close).pack(side="right")

    # ---------- Details/context ----------
    def _show_details(self, row: dict[str, Any]) -> None:
        window = ctk.CTkToplevel(self)
        window.title("App details")
        window.geometry("760x720")
        window.transient(self)
        content = ctk.CTkScrollableFrame(window, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(content, text=str(row.get("play_title") or row.get("package_name") or "App"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 10))
        fields = [
            ("Status","criticality"),("Health score","health_score"),("Change","change"),("Package Name","package_name"),("Play Store Title","play_title"),("Last update","play_last_update"),("Age (days)","age_days"),("Play Store version","play_version"),("Installed version","installed_version"),("Installed vs Store","version_comparison"),("Installer source","installer_source"),("Android compatibility","compatibility_status"),("Target SDK","target_sdk"),("Min SDK","min_sdk"),("First installed","first_install_time"),("Last local update","last_local_update"),("Enabled state","app_enabled"),("Device inventory change","device_change"),("Sensitive permissions","sensitive_permissions"),("Play status","play_status"),("Update source","updated_source"),("HTTP status","play_http_status"),("System app","is_system"),("Notes","notes")
        ]
        for label, key in fields:
            value = str(row.get(key, "") or "")
            if not value and key not in {"notes","change"}:
                continue
            box = ctk.CTkFrame(content); box.pack(fill="x", pady=3)
            ctk.CTkLabel(box, text=label, width=165, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10,8), pady=7)
            ctk.CTkLabel(box, text=value, anchor="w", justify="left", wraplength=520).pack(side="left", fill="x", expand=True, padx=(0,10), pady=7)
        actions = ctk.CTkFrame(window, fg_color="transparent"); actions.pack(fill="x", padx=16, pady=(0,16))
        ctk.CTkButton(actions, text="Open in Google Play", command=lambda: webbrowser.open(str(row.get("store_url") or "")), state="normal" if row.get("store_url") else "disabled").pack(side="left")
        ctk.CTkButton(actions, text="Open App Info on phone", command=lambda: self._open_app_info(str(row.get("package_name") or "")), state="normal" if self.source_mode=="device" else "disabled").pack(side="left", padx=8)
        ctk.CTkButton(actions, text="Close", command=window.destroy, fg_color="#6C7781").pack(side="right")

    def _show_row_context_menu(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        values = self.tree.item(item, "values")
        visible = self._visible_column_order()
        try:
            package_index = visible.index("package_name")
            package_name = str(values[package_index])
        except Exception:
            return
        row = next((r for r in self.current_rows if str(r.get("package_name")) == package_name), None)
        if not row:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="App details…", command=lambda: self._show_details(row))
        menu.add_command(label="Force recheck this app", command=lambda: self._start_subset_refresh([package_name], "App recheck"))
        menu.add_command(label="Open in Google Play", command=lambda: webbrowser.open(str(row.get("store_url") or "")))
        menu.add_command(label="Open App Info on phone", command=lambda: self._open_app_info(package_name), state="normal" if self.source_mode=="device" else "disabled")
        menu.add_separator()
        menu.add_command(label="Copy package name", command=lambda: self._copy_text(package_name))
        menu.add_command(label="Copy Play Store title", command=lambda: self._copy_text(str(row.get("play_title") or "")))
        menu.add_command(label="Copy Store URL", command=lambda: self._copy_text(str(row.get("store_url") or "")))
        menu.add_command(label="Copy visible row", command=lambda: self._copy_text("\t".join(str(row.get(c,"") or "") for c in visible)))
        menu.tk_popup(event.x_root, event.y_root)

    def _open_app_info(self, package_name: str) -> None:
        adb = self._get_authorised_adb()
        if not adb:
            messagebox.showwarning("ADB unavailable", "No authorised Android device is currently connected.", parent=self)
            return
        try:
            features.open_app_info_on_device(adb, package_name)
        except Exception as exc:
            messagebox.showerror("Could not open App Info", str(exc), parent=self)

    # ---------- Reports/help/update/diagnostics ----------
    def _export_html_report(self) -> None:
        if not self.current_rows:
            messagebox.showinfo("No results", "Run an audit first.", parent=self)
            return
        selected = filedialog.asksaveasfilename(title="Export HTML report", defaultextension=".html", initialfile="playstore_audit_report.html", filetypes=[("HTML", "*.html")])
        if selected:
            features.write_html_report(selected, self.current_rows, self._device_summary)
            messagebox.showinfo("Report created", f"HTML report saved to:\n{selected}", parent=self)

    def _show_text_help(self, title: str, text: str) -> None:
        window = ctk.CTkToplevel(self)
        window.title(title)
        window.geometry("760x600")
        window.transient(self)
        box = ctk.CTkTextbox(window, wrap="word")
        box.pack(fill="both", expand=True, padx=14, pady=14)
        box.insert("1.0", text)
        box.configure(state="disabled")
        ctk.CTkButton(window, text="Close", command=window.destroy, width=90, fg_color="#6C7781").pack(anchor="e", padx=14, pady=(0,14))

    def _check_for_updates(self) -> None:
        result = features.check_for_updates()
        if result.get("status") != "ok":
            messagebox.showinfo("Update check", str(result.get("message") or "Update check unavailable."), parent=self)
            return
        if result.get("newer"):
            if messagebox.askyesno("Update available", f"Version {result.get('tag')} is available. Open the release page?", parent=self):
                webbrowser.open(str(result.get("url") or features.LATEST_RELEASE_PAGE))
        else:
            messagebox.showinfo("Up to date", f"You are running Play Store App Audit {features.APP_VERSION}.", parent=self)

    def _create_diagnostic_bundle(self) -> None:
        selected = filedialog.asksaveasfilename(title="Create diagnostic bundle", defaultextension=".zip", initialfile="PlayStoreAppAudit-diagnostics.zip", filetypes=[("ZIP", "*.zip")])
        if selected:
            features.create_diagnostic_bundle(selected, self.current_rows, self._device_summary)
            messagebox.showinfo("Diagnostic bundle created", "The bundle excludes recent file paths, saved filters and the package inventory itself.", parent=self)

    def _show_about(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("About Play Store App Audit")
        window.geometry("540x360")
        window.resizable(False, False)
        window.transient(self)
        ctk.CTkLabel(window, text=f"Play Store App Audit {features.APP_VERSION}", font=ctk.CTkFont(size=23, weight="bold")).pack(anchor="w", padx=20, pady=(20,8))
        ctk.CTkLabel(window, text="Created by MRC", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20)
        ctk.CTkLabel(window, text="Development assistance: OpenAI ChatGPT", text_color="#6C7781").pack(anchor="w", padx=20, pady=(2,12))
        ctk.CTkLabel(window, text="Android/Google Play audit and connected-device maintenance utility.\n\nUnofficial utility. Not affiliated with or endorsed by Google.", wraplength=490, justify="left").pack(anchor="w", padx=20)
        ctk.CTkButton(window, text="MRC on GitHub", command=lambda: webbrowser.open("https://github.com/mrc-labs/PlayStoreAppAudit")).pack(anchor="w", padx=20, pady=16)
        ctk.CTkButton(window, text="Close", command=window.destroy, width=90, fg_color="#6C7781").pack(anchor="e", padx=20, pady=(0,20))


def main() -> None:
    app = CustomTkPlayStoreAuditV9()
    app.mainloop()


if __name__ == "__main__":
    main()
