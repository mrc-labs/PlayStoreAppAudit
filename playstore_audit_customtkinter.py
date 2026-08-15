from __future__ import annotations

import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from playstore_audit_core import AuditConfig, audit_apps, load_apps
from playstore_audit_windows import WindowsPlayStoreAuditApp


class CompatCTkButton(ctk.CTkButton):
    def config(self, **kwargs):
        return self.configure(**kwargs)


class CompatProgress(ctk.CTkProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._maximum = 100.0
        self._value = 0.0
        self.set(0)

    def __setitem__(self, key, value):
        if key == "maximum":
            self._maximum = max(float(value), 1.0)
            self.set(min(max(self._value / self._maximum, 0.0), 1.0))
            return
        if key == "value":
            self._value = float(value)
            self.set(min(max(self._value / self._maximum, 0.0), 1.0))
            return
        return super().__setitem__(key, value)

    def __getitem__(self, key):
        if key == "maximum":
            return self._maximum
        if key == "value":
            return self._value
        return super().__getitem__(key)


class CustomTkPlayStoreAuditApp(WindowsPlayStoreAuditApp):
    """CustomTkinter presentation of the same Play Store audit workflow."""

    def __init__(self) -> None:
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.language_var.set("en")
        self.configure(bg="#F4F6F9")

    def _build_ui(self) -> None:
        self.configure(bg="#F4F6F9")

        root = ctk.CTkFrame(self, fg_color="#F4F6F9", corner_radius=0)
        root.pack(fill="both", expand=True, padx=18, pady=16)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(5, weight=1)

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(header, text="Play Store App Audit", font=ctk.CTkFont(size=28, weight="bold"), text_color="#1C2731").pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Check Android packages against Google Play, classify update risk and inspect everything in one table.",
            font=ctk.CTkFont(size=13),
            text_color="#6B7782",
        ).pack(anchor="w", pady=(2, 0))

        top = ctk.CTkFrame(root, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=2)

        source = ctk.CTkFrame(top, fg_color=("#FFFFFF", "#202225"), corner_radius=12, border_width=1, border_color=("#E1E6EB", "#34383D"))
        source.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        source.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(source, text="App source", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 8))

        self.path_entry = ctk.CTkEntry(source, textvariable=self.input_var, state="readonly", height=34, corner_radius=8)
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 8))
        self.choose_button = CompatCTkButton(source, text="Choose file", command=self._choose_input, width=110, height=34, corner_radius=8)
        self.choose_button.grid(row=1, column=1, padx=(0, 8), pady=(0, 8))
        self.scan_button = CompatCTkButton(source, text="Scan phone with ADB", command=self._scan_phone, width=150, height=34, corner_radius=8)
        self.scan_button.grid(row=1, column=2, padx=(0, 16), pady=(0, 8))

        self.skip_source_check = ctk.CTkCheckBox(
            source,
            text="Exclude system apps when loading / scanning",
            variable=self.skip_system_var,
            onvalue=True,
            offvalue=False,
        )
        self.skip_source_check.grid(row=2, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 7))
        ctk.CTkLabel(
            source,
            text="ADB loads third-party apps only. CSV removes apps classified as system at load time.",
            text_color=("#6C7781", "#AAB1B7"),
            font=ctk.CTkFont(size=11),
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=16)
        ctk.CTkLabel(source, textvariable=self.source_var, text_color=("#6C7781", "#AAB1B7"), wraplength=820, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", padx=16, pady=(5, 14))

        settings = ctk.CTkFrame(top, fg_color=("#FFFFFF", "#202225"), corner_radius=12, border_width=1, border_color=("#E1E6EB", "#34383D"))
        settings.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(settings, text="Audit settings", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(14, 8))
        ctk.CTkLabel(settings, text="Country").grid(row=1, column=0, sticky="w", padx=(16, 6))
        self.country_entry = ctk.CTkEntry(settings, textvariable=self.country_var, width=64, height=32)
        self.country_entry.grid(row=1, column=1, sticky="w", padx=(0, 16))
        ctk.CTkLabel(settings, text="Parallel threads").grid(row=1, column=2, sticky="w", padx=(0, 6))
        self.workers_entry = ctk.CTkEntry(settings, textvariable=self.workers_var, width=64, height=32)
        self.workers_entry.grid(row=1, column=3, sticky="w", padx=(0, 16))
        ctk.CTkLabel(
            settings,
            text="Country controls Store availability. Store language is fixed internally to English.",
            text_color=("#6C7781", "#AAB1B7"),
            font=ctk.CTkFont(size=11),
            wraplength=480,
            justify="left",
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=16, pady=(8, 14))

        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        actions.grid_columnconfigure(0, weight=1)
        self.run_button = CompatCTkButton(actions, text="Run Play Store audit", command=self._start_audit, height=40, corner_radius=9, font=ctk.CTkFont(weight="bold"))
        self.run_button.grid(row=0, column=0, sticky="ew")
        self.export_button = CompatCTkButton(actions, text="Export results", command=self._export_results, state="disabled", width=130, height=40, corner_radius=9, fg_color=("#E8EDF2", "#343A40"), text_color=("#28343E", "#F0F2F4"), hover_color=("#DDE4EA", "#41474D"))
        self.export_button.grid(row=0, column=1, padx=(8, 0))
        self.clear_button = CompatCTkButton(actions, text="Clear", command=self._clear_results, width=80, height=40, corner_radius=9, fg_color=("#E8EDF2", "#343A40"), text_color=("#28343E", "#F0F2F4"), hover_color=("#DDE4EA", "#41474D"))
        self.clear_button.grid(row=0, column=2, padx=(8, 0))

        progress_card = ctk.CTkFrame(root, fg_color=("#FFFFFF", "#202225"), corner_radius=12, border_width=1, border_color=("#E1E6EB", "#34383D"))
        progress_card.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        progress_card.grid_columnconfigure(0, weight=1)
        self.progress = CompatProgress(progress_card, height=10, corner_radius=5)
        self.progress.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ctk.CTkLabel(progress_card, textvariable=self.status_var, text_color=("#6C7781", "#AAB1B7"), font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        results = ctk.CTkFrame(root, fg_color=("#FFFFFF", "#202225"), corner_radius=12, border_width=1, border_color=("#E1E6EB", "#34383D"))
        results.grid(row=5, column=0, sticky="nsew", pady=(10, 0))
        results.grid_columnconfigure(0, weight=1)
        results.grid_rowconfigure(3, weight=1)

        toolbar = ctk.CTkFrame(results, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(toolbar, textvariable=self.summary_var, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        self.hide_system_check = ctk.CTkCheckBox(toolbar, text="Hide system apps", variable=self.hide_system_var, command=self._refresh_table)
        self.hide_system_check.grid(row=0, column=1, padx=(16, 12))
        self.filter_entry = ctk.CTkEntry(toolbar, textvariable=self.filter_var, width=280, height=32, placeholder_text="Filter apps…")
        self.filter_entry.grid(row=0, column=2)

        chips = ctk.CTkFrame(results, fg_color="transparent")
        chips.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        self.criticality_buttons = {}
        all_button = CompatCTkButton(chips, text="All", width=58, height=29, corner_radius=7, command=lambda: self._set_criticality_filter(None), fg_color=("#EDF1F4", "#343A40"), text_color=("#26323C", "#F0F2F4"), hover_color=("#E2E8ED", "#41474D"))
        all_button.pack(side="left", padx=(0, 4))
        for key in ("red", "orange", "yellow", "blue", "purple", "green"):
            info = self.CRITICALITY[key]
            button = CompatCTkButton(
                chips,
                text=self.criticality_count_vars[key].get(),
                width=105,
                height=29,
                corner_radius=7,
                command=lambda k=key: self._set_criticality_filter(k),
                fg_color=info["background"],
                text_color=info["foreground"],
                hover_color=info["background"],
                border_width=1,
                border_color=info["background"],
            )
            button.pack(side="left", padx=3)
            self.criticality_buttons[key] = button

        ctk.CTkLabel(
            results,
            text="Removed = no Store listing  •  Stale = >730d  •  Aging = >365–730d  •  Anomaly = unusual Store availability  •  Other = unknown/error  •  Current = ≤365d",
            text_color=("#6C7781", "#AAB1B7"),
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, sticky="w", padx=14, pady=(1, 7))

        table_frame = tk.Frame(results, bg="#FFFFFF", highlightthickness=0)
        table_frame.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 8))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Audit.Treeview", background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#263238", rowheight=29, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Audit.Treeview.Heading", background="#F0F3F6", foreground="#34424E", relief="flat", font=("Segoe UI", 9, "bold"), padding=(7, 7))
        style.map("Audit.Treeview", background=[("selected", "#DDEBF7")], foreground=[("selected", "#18212A")])

        self.tree = ttk.Treeview(table_frame, columns=self.COLUMNS, show="headings", selectmode="browse", style="Audit.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        for column in self.COLUMNS:
            self.tree.heading(column, text=self.COLUMN_LABELS[column], command=lambda c=column: self._sort_results(c))
            anchor = "center" if column in {"play_status", "play_last_update", "age_days", "criticality"} else "w"
            stretch = column in {"app_name", "package_name", "play_title", "notes"}
            self.tree.column(column, width=self.COLUMN_WIDTHS[column], minwidth=80, anchor=anchor, stretch=stretch)
        for key, info in self.CRITICALITY.items():
            self.tree.tag_configure(key, background=info["background"], foreground="#263238", font=("Segoe UI", 9))
        self.tree.bind("<Double-1>", self._open_selected_store_url)

        ctk.CTkLabel(results, text="Tip: click a column header to sort; double-click a row to open Google Play.", text_color=("#6C7781", "#AAB1B7"), font=ctk.CTkFont(size=11)).grid(row=4, column=0, sticky="w", padx=14, pady=(0, 10))

    def _refresh_table(self) -> None:
        super()._refresh_table()
        if hasattr(self, "criticality_buttons"):
            for key, button in self.criticality_buttons.items():
                button.configure(text=self.criticality_count_vars[key].get())

    def _choose_input(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose app list",
            filetypes=[("App lists", "*.csv *.tsv *.txt"), ("CSV", "*.csv"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if not selected:
            return
        try:
            apps = load_apps(selected)
            metadata = self._read_system_metadata_from_file(selected, apps)
        except Exception as exc:
            messagebox.showerror("Invalid app list", str(exc))
            return

        self.file_system_metadata = metadata
        system_packages, method = self._classify_file_system_packages(apps)
        original_count = len(apps)
        skipped = 0
        if self.skip_system_var.get():
            apps = [app for app in apps if app["package_name"] not in system_packages]
            skipped = original_count - len(apps)

        self.file_apps = apps
        self.device_apps_all = []
        self.device_system_packages = set()
        self.source_mode = "file"
        self.input_var.set(selected)
        suffix = f" | {skipped} system excluded during load" if self.skip_system_var.get() else f" | {len(system_packages)} classified as system"
        self.source_var.set(f"File loaded: {len(apps)}/{original_count} packages{suffix} | {method}")
        self.status_var.set("File ready. Run the Play Store audit.")

    def _scan_phone(self) -> None:
        adb = self._find_adb()
        if not adb:
            adb = self._install_platform_tools()
            if not adb:
                return

        self.status_var.set("Checking ADB device connection…")
        self.update_idletasks()
        try:
            devices = subprocess.run([adb, "devices"], check=True, capture_output=True, text=True, timeout=20).stdout.splitlines()
            rows = [line.split() for line in devices[1:] if line.strip()]
            authorised = [parts[0] for parts in rows if len(parts) >= 2 and parts[1] == "device"]
            unauthorised = [parts[0] for parts in rows if len(parts) >= 2 and parts[1] == "unauthorized"]
            offline = [parts[0] for parts in rows if len(parts) >= 2 and parts[1] == "offline"]
            if not authorised:
                if unauthorised:
                    raise RuntimeError("The phone is visible to ADB but is not authorised. Unlock it and accept 'Allow USB debugging?', then scan again.")
                if offline:
                    raise RuntimeError("The phone is visible to ADB but is offline. Reconnect the USB cable, unlock it and try again.")
                raise RuntimeError("ADB is installed, but no Android phone is visible. Check USB debugging, cable/data mode and Windows USB drivers.")

            command = [adb, "shell", "pm", "list", "packages"]
            exclude_system = bool(self.skip_system_var.get())
            if exclude_system:
                command.append("-3")
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
            packages = sorted(self._parse_adb_packages(result.stdout))
            if not packages:
                raise RuntimeError("ADB returned no Android packages.")

            system_packages = set() if exclude_system else self._get_system_packages_from_adb(adb)
            self.device_apps_all = [{"app_name": package, "package_name": package} for package in packages]
            self.device_system_packages = system_packages
            self.file_apps = []
            self.file_system_metadata = {}
            self.source_mode = "device"
            self.input_var.set("")
            if exclude_system:
                self.source_var.set(f"Phone scan: {len(packages)} third-party packages loaded | system apps excluded during ADB scan")
            else:
                user_count = sum(1 for package in packages if package not in system_packages)
                self.source_var.set(f"Phone scan: {len(packages)} total packages | {user_count} third-party | {len(system_packages)} system")
            self.status_var.set("Phone scan ready. Run the Play Store audit.")
        except Exception as exc:
            self.status_var.set("Phone scan failed")
            messagebox.showerror("ADB connection error", str(exc))

    def _start_audit(self) -> None:
        try:
            apps, system_packages, classification_method = self._get_apps_to_audit()
        except Exception as exc:
            messagebox.showerror("No app list", str(exc))
            return
        if not apps:
            messagebox.showerror("Nothing to audit", "No packages are loaded.")
            return
        try:
            workers = max(1, int(self.workers_var.get()))
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Parallel threads must be a number.")
            return

        country = (self.country_var.get().strip() or "it").lower()
        self.current_system_packages = system_packages
        self.criticality_filter = None
        source_label = "Phone" if self.source_mode == "device" else "CSV/TXT"
        self.source_var.set(f"{source_label} source: {len(apps)} packages | {len(system_packages)} classified as system | {classification_method}")
        self.run_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(apps)
        self.status_var.set(f"Starting audit for {len(apps)} packages in Store country '{country}'…")
        self.current_rows = []
        self._refresh_table()
        config = AuditConfig(country=country, language="en", max_workers=workers)
        threading.Thread(target=self._audit_worker, args=(apps, config), daemon=True).start()


def main() -> None:
    app = CustomTkPlayStoreAuditApp()
    app.mainloop()


if __name__ == "__main__":
    main()
