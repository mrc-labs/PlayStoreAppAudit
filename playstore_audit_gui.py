from __future__ import annotations

import csv
import queue
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from playstore_audit_core import AuditConfig, OUTPUT_FIELDS, audit_apps, load_apps


class PlayStoreAuditApp(tk.Tk):
    COLUMNS = (
        "app_name",
        "package_name",
        "play_status",
        "play_last_update",
        "play_title",
        "updated_source",
        "notes",
    )

    COLUMN_LABELS = {
        "app_name": "Input name",
        "package_name": "Package",
        "play_status": "Play status",
        "play_last_update": "Last update",
        "play_title": "Play Store title",
        "updated_source": "Update source",
        "notes": "Notes",
    }

    COLUMN_WIDTHS = {
        "app_name": 170,
        "package_name": 260,
        "play_status": 190,
        "play_last_update": 115,
        "play_title": 210,
        "updated_source": 170,
        "notes": 340,
    }

    SYSTEM_COLUMN_NAMES = {
        "is_system", "issystem", "system", "system_app", "systemapp",
        "is_system_app", "issystemapp", "app_type", "apptype", "type",
    }
    PACKAGE_COLUMN_NAMES = {
        "package", "packageid", "packagename", "package_name",
        "appid", "app_id", "id",
    }
    TRUE_SYSTEM_VALUES = {
        "1", "true", "yes", "y", "system", "system_app", "systemapp",
        "preinstalled", "pre-installed",
    }
    FALSE_SYSTEM_VALUES = {
        "0", "false", "no", "n", "user", "user_app", "userapp",
        "third-party", "third_party", "thirdparty",
    }

    # Offline fallback used only when neither CSV metadata nor an authorised
    # source phone is available. Kept deliberately conservative.
    DEFINITE_SYSTEM_PREFIXES = (
        "com.android.",
        "com.google.android.overlay.",
        "com.google.android.providers.",
        "com.google.android.permissioncontroller",
        "com.google.android.modulemetadata",
        "com.google.android.ext.",
        "com.google.android.networkstack",
        "com.google.android.adservices.api",
        "com.google.android.ondevicepersonalization.services",
    )
    DEFINITE_SYSTEM_PACKAGES = {
        "android",
        "com.google.android.packageinstaller",
        "com.google.android.documentsui",
        "com.google.android.settings.intelligence",
        "com.google.android.cellbroadcastreceiver",
        "com.google.android.cellbroadcastservice",
        "com.google.android.connectivity.resources",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Play Store App Audit")
        self.geometry("1340x790")
        self.minsize(1020, 640)

        self.input_var = tk.StringVar()
        self.source_var = tk.StringVar(value="No app list selected")
        self.country_var = tk.StringVar(value="it")
        self.language_var = tk.StringVar(value="it")
        self.workers_var = tk.IntVar(value=16)
        self.exclude_system_var = tk.BooleanVar(value=True)
        self.filter_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="No results yet")

        self.progress_queue: queue.Queue = queue.Queue()
        self.source_mode: str | None = None
        self.file_apps: list[dict[str, str]] = []
        self.file_system_metadata: dict[str, bool] = {}
        self.device_apps_all: list[dict[str, str]] = []
        self.device_system_packages: set[str] = set()
        self.current_rows: list[dict[str, object]] = []
        self.sort_column: str | None = None
        self.sort_reverse = False

        self._build_ui()
        self.filter_var.trace_add("write", lambda *_: self._refresh_table())
        self.after(100, self._process_queue)

    @staticmethod
    def _normalise_header(value: str) -> str:
        return "".join(
            character
            for character in value.strip().lower().replace(" ", "_").replace("-", "_")
            if character.isalnum() or character == "_"
        )

    @staticmethod
    def _parse_bool(value: str) -> bool | None:
        normalised = value.strip().lower()
        if normalised in PlayStoreAuditApp.TRUE_SYSTEM_VALUES:
            return True
        if normalised in PlayStoreAuditApp.FALSE_SYSTEM_VALUES:
            return False
        return None

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(5, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Play Store App Audit", font=("Segoe UI", 19, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Audit Android packages and inspect results directly in the app").grid(row=1, column=0, sticky="w", pady=(2, 0))

        source_frame = ttk.LabelFrame(root, text="App source", padding=10)
        source_frame.grid(row=1, column=0, sticky="ew")
        source_frame.columnconfigure(1, weight=1)
        ttk.Label(source_frame, text="CSV / TXT:").grid(row=0, column=0, sticky="w")
        ttk.Entry(source_frame, textvariable=self.input_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(source_frame, text="Choose file", command=self._choose_input).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(source_frame, text="Scan phone with ADB", command=self._scan_phone).grid(row=0, column=3)
        ttk.Label(source_frame, textvariable=self.source_var).grid(row=1, column=1, columnspan=3, sticky="w", padx=8, pady=(7, 0))

        options = ttk.LabelFrame(root, text="Audit settings", padding=10)
        options.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(options, text="Country:").grid(row=0, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.country_var, width=7).grid(row=0, column=1, padx=(5, 18))
        ttk.Label(options, text="Language:").grid(row=0, column=2, sticky="w")
        ttk.Entry(options, textvariable=self.language_var, width=7).grid(row=0, column=3, padx=(5, 18))
        ttk.Label(options, text="Parallel threads:").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(options, from_=1, to=32, textvariable=self.workers_var, width=7).grid(row=0, column=5, padx=(5, 22))
        ttk.Checkbutton(
            options,
            text="Exclude system apps (phone scans and CSV files)",
            variable=self.exclude_system_var,
        ).grid(row=0, column=6, sticky="w")
        ttk.Label(
            options,
            text=(
                "For CSV files, detection is exact when the CSV contains a system flag "
                "or an authorised Android phone is connected via ADB."
            ),
        ).grid(row=1, column=0, columnspan=7, sticky="w", pady=(7, 0))

        action_frame = ttk.Frame(root)
        action_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        action_frame.columnconfigure(0, weight=1)
        self.run_button = ttk.Button(action_frame, text="Run Play Store audit", command=self._start_audit)
        self.run_button.grid(row=0, column=0, sticky="ew", ipady=5)
        self.export_button = ttk.Button(action_frame, text="Export results…", command=self._export_results, state="disabled")
        self.export_button.grid(row=0, column=1, padx=(8, 0))
        ttk.Button(action_frame, text="Clear", command=self._clear_results).grid(row=0, column=2, padx=(8, 0))

        progress_frame = ttk.Frame(root)
        progress_frame.grid(row=4, column=0, sticky="ew", pady=(10, 8))
        progress_frame.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_frame, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(4, 0))

        results = ttk.LabelFrame(root, text="Results", padding=8)
        results.grid(row=5, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(results)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        toolbar.columnconfigure(2, weight=1)
        ttk.Label(toolbar, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")
        ttk.Label(toolbar, text="Filter:").grid(row=0, column=1, sticky="e", padx=(20, 5))
        ttk.Entry(toolbar, textvariable=self.filter_var, width=34).grid(row=0, column=2, sticky="e")

        table_frame = ttk.Frame(results)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_frame, columns=self.COLUMNS, show="headings", selectmode="browse")
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        for column in self.COLUMNS:
            self.tree.heading(column, text=self.COLUMN_LABELS[column], command=lambda c=column: self._sort_results(c))
            anchor = "center" if column in {"play_status", "play_last_update"} else "w"
            stretch = column in {"app_name", "package_name", "play_title", "notes"}
            self.tree.column(column, width=self.COLUMN_WIDTHS[column], minwidth=90, anchor=anchor, stretch=stretch)

        self.tree.tag_configure("problem", font=("Segoe UI", 9, "bold"))
        self.tree.bind("<Double-1>", self._open_selected_store_url)
        ttk.Label(results, text="Tip: click a column header to sort; double-click a row to open its Play Store page.").grid(row=2, column=0, sticky="w", pady=(6, 0))

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

        self.file_apps = apps
        self.file_system_metadata = metadata
        self.device_apps_all = []
        self.device_system_packages = set()
        self.source_mode = "file"
        self.input_var.set(selected)
        meta_text = f" | system flag available for {len(metadata)} packages" if metadata else ""
        self.source_var.set(f"File selected: {len(apps)} unique Android packages{meta_text}")
        self.status_var.set("File ready. Run the Play Store audit.")

    def _read_system_metadata_from_file(self, path: str | Path, apps: list[dict[str, str]]) -> dict[str, bool]:
        file_path = Path(path)
        if file_path.suffix.lower() not in {".csv", ".tsv"}:
            return {}
        raw = file_path.read_text(encoding="utf-8-sig", errors="replace")
        if not raw.strip():
            return {}
        try:
            dialect = csv.Sniffer().sniff(raw[:5000], delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","

        reader = csv.DictReader(raw.splitlines(), delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            return {}
        normalised = {self._normalise_header(name): name for name in fieldnames if name is not None}
        package_column = next((original for name, original in normalised.items() if name in self.PACKAGE_COLUMN_NAMES), None)
        system_column = next((original for name, original in normalised.items() if name in self.SYSTEM_COLUMN_NAMES), None)
        if not package_column or not system_column:
            return {}

        valid_packages = {app["package_name"] for app in apps}
        metadata: dict[str, bool] = {}
        for row in reader:
            package_name = (row.get(package_column) or "").strip()
            if package_name not in valid_packages:
                continue
            value = self._parse_bool(row.get(system_column) or "")
            if value is not None:
                metadata[package_name] = value
        return metadata

    def _find_adb(self) -> str | None:
        candidates = [
            shutil.which("adb"),
            str(Path.cwd() / "adb.exe"),
            str(Path.cwd() / "platform-tools" / "adb.exe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    def _get_authorised_adb(self) -> str | None:
        adb = self._find_adb()
        if not adb:
            return None
        try:
            devices = subprocess.run([adb, "devices"], check=True, capture_output=True, text=True, timeout=20).stdout.splitlines()
        except Exception:
            return None
        connected = [line.split()[0] for line in devices[1:] if line.strip() and line.strip().endswith("\tdevice")]
        return adb if connected else None

    @staticmethod
    def _parse_adb_packages(output: str) -> set[str]:
        return {
            line.replace("package:", "", 1).strip()
            for line in output.splitlines()
            if line.strip().startswith("package:")
        }

    def _get_system_packages_from_adb(self, adb: str) -> set[str]:
        result = subprocess.run(
            [adb, "shell", "pm", "list", "packages", "-s"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return self._parse_adb_packages(result.stdout)

    def _scan_phone(self) -> None:
        adb = self._get_authorised_adb()
        if not adb:
            messagebox.showerror(
                "ADB not available",
                "Install Android SDK Platform-Tools, enable USB debugging and authorise the connected phone.",
            )
            return
        self.status_var.set("Scanning connected phone…")
        self.update_idletasks()
        try:
            all_result = subprocess.run(
                [adb, "shell", "pm", "list", "packages"],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            system_packages = self._get_system_packages_from_adb(adb)
            all_packages = sorted(self._parse_adb_packages(all_result.stdout))
            if not all_packages:
                raise RuntimeError("ADB returned no Android packages.")

            self.device_apps_all = [{"app_name": package, "package_name": package} for package in all_packages]
            self.device_system_packages = system_packages
            self.file_apps = []
            self.file_system_metadata = {}
            self.source_mode = "device"
            self.input_var.set("")
            user_count = sum(1 for package in all_packages if package not in system_packages)
            self.source_var.set(
                f"Phone scan: {len(all_packages)} total packages | {user_count} third-party | {len(system_packages)} system"
            )
            self.status_var.set("Phone scan ready. The system-app checkbox can be changed before running.")
        except Exception as exc:
            self.status_var.set("Phone scan failed")
            messagebox.showerror("ADB error", str(exc))

    def _is_definite_system_package(self, package_name: str) -> bool:
        if package_name in self.DEFINITE_SYSTEM_PACKAGES:
            return True
        return any(package_name.startswith(prefix) for prefix in self.DEFINITE_SYSTEM_PREFIXES)

    def _filter_file_apps(self, apps: list[dict[str, str]]) -> tuple[list[dict[str, str]], int, str]:
        if not self.exclude_system_var.get():
            return apps, 0, "system filtering disabled"

        system_packages = {
            package_name
            for package_name, is_system in self.file_system_metadata.items()
            if is_system
        }
        known_user_packages = {
            package_name
            for package_name, is_system in self.file_system_metadata.items()
            if not is_system
        }
        method_parts: list[str] = []
        if self.file_system_metadata:
            method_parts.append("CSV system flag")

        adb = self._get_authorised_adb()
        if adb:
            try:
                system_packages.update(self._get_system_packages_from_adb(adb))
                method_parts.append("ADB exact match")
            except Exception:
                adb = None

        heuristic_count = 0
        if not adb:
            for app in apps:
                package_name = app["package_name"]
                if package_name in system_packages or package_name in known_user_packages:
                    continue
                if self._is_definite_system_package(package_name):
                    system_packages.add(package_name)
                    heuristic_count += 1
            if heuristic_count:
                method_parts.append("conservative package-name fallback")

        filtered = [app for app in apps if app["package_name"] not in system_packages]
        excluded = len(apps) - len(filtered)

        if method_parts:
            method = " + ".join(method_parts)
        else:
            method = (
                "no exact classifier available; connect the source phone via ADB "
                "or add an is_system column for reliable CSV filtering"
            )
        return filtered, excluded, method

    def _get_apps_to_audit(self) -> tuple[list[dict[str, str]], int, str]:
        if self.source_mode == "device" and self.device_apps_all:
            apps = list(self.device_apps_all)
            if self.exclude_system_var.get():
                filtered = [app for app in apps if app["package_name"] not in self.device_system_packages]
                return filtered, len(apps) - len(filtered), "ADB exact system classification"
            return apps, 0, "system filtering disabled"

        if self.source_mode == "file" and self.file_apps:
            return self._filter_file_apps(list(self.file_apps))

        raise ValueError("Choose a CSV/TXT file or scan a connected Android phone first.")

    def _start_audit(self) -> None:
        try:
            apps, excluded_count, filter_method = self._get_apps_to_audit()
        except Exception as exc:
            messagebox.showerror("No app list", str(exc))
            return
        if not apps:
            messagebox.showerror("Nothing to audit", "All packages were excluded by the current system-app filter.")
            return
        try:
            workers = max(1, int(self.workers_var.get()))
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Parallel threads must be a number.")
            return

        if self.source_mode == "file":
            self.source_var.set(
                f"CSV/TXT source: {len(apps)} packages to audit | {excluded_count} system packages excluded | {filter_method}"
            )
        else:
            self.source_var.set(
                f"Phone source: {len(apps)} packages to audit | {excluded_count} system packages excluded"
            )

        self.run_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(apps)
        self.status_var.set(
            f"Starting audit for {len(apps)} packages"
            + (f" ({excluded_count} system apps skipped)…" if excluded_count else "…")
        )
        self.current_rows = []
        self._refresh_table()
        config = AuditConfig(
            country=(self.country_var.get().strip() or "it").lower(),
            language=(self.language_var.get().strip() or "it").lower(),
            max_workers=workers,
        )
        threading.Thread(target=self._audit_worker, args=(apps, config), daemon=True).start()

    def _audit_worker(self, apps: list[dict[str, str]], config: AuditConfig) -> None:
        try:
            def progress(done: int, total: int, package_name: str) -> None:
                self.progress_queue.put(("progress", done, total, package_name))
            rows = audit_apps(apps, config, progress)
            self.progress_queue.put(("done", rows))
        except Exception as exc:
            self.progress_queue.put(("error", str(exc)))

    def _sort_key(self, row: dict[str, object], column: str):
        value = str(row.get(column, "") or "").strip()
        if column == "play_last_update":
            return (1, "") if not value else (0, value)
        return value.casefold()

    def _sort_results(self, column: str) -> None:
        if not self.current_rows:
            return
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.current_rows.sort(key=lambda row: self._sort_key(row, column), reverse=self.sort_reverse)
        self._refresh_headings()
        self._refresh_table()

    def _refresh_headings(self) -> None:
        for column in self.COLUMNS:
            label = self.COLUMN_LABELS[column]
            if column == self.sort_column:
                label += " ▼" if self.sort_reverse else " ▲"
            self.tree.heading(column, text=label, command=lambda c=column: self._sort_results(c))

    def _filtered_rows(self) -> list[dict[str, object]]:
        query = self.filter_var.get().strip().casefold()
        if not query:
            return self.current_rows
        return [
            row for row in self.current_rows
            if query in " ".join(str(row.get(column, "") or "") for column in OUTPUT_FIELDS).casefold()
        ]

    def _refresh_table(self) -> None:
        if not hasattr(self, "tree"):
            return
        selected_package = None
        selection = self.tree.selection()
        if selection:
            values = self.tree.item(selection[0], "values")
            if len(values) > 1:
                selected_package = values[1]
        for item in self.tree.get_children():
            self.tree.delete(item)

        visible_rows = self._filtered_rows()
        for row in visible_rows:
            values = [row.get(column, "") for column in self.COLUMNS]
            tags = ()
            if row.get("play_status") != "available" or not row.get("play_last_update"):
                tags = ("problem",)
            item = self.tree.insert("", "end", values=values, tags=tags)
            if selected_package and row.get("package_name") == selected_package:
                self.tree.selection_set(item)

        if self.current_rows:
            available = sum(1 for row in self.current_rows if row.get("play_status") == "available")
            problems = len(self.current_rows) - available
            suffix = f" | showing {len(visible_rows)}" if len(visible_rows) != len(self.current_rows) else ""
            self.summary_var.set(f"{len(self.current_rows)} apps | {available} available | {problems} need attention{suffix}")
        else:
            self.summary_var.set("No results yet")

    def _open_selected_store_url(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        if len(values) < 2:
            return
        package_name = str(values[1])
        row = next((item for item in self.current_rows if item.get("package_name") == package_name), None)
        if row and row.get("store_url"):
            webbrowser.open(str(row["store_url"]))

    def _export_results(self) -> None:
        if not self.current_rows:
            return
        selected = filedialog.asksaveasfilename(
            title="Export audit results",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="playstore_audit_results.csv",
        )
        if not selected:
            return
        try:
            with open(selected, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
                writer.writeheader()
                writer.writerows(self.current_rows)
            messagebox.showinfo("Export complete", f"Results saved to:\n{selected}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _clear_results(self) -> None:
        self.current_rows = []
        self.sort_column = None
        self.sort_reverse = False
        self.filter_var.set("")
        self.progress["value"] = 0
        self.status_var.set("Ready")
        self.export_button.config(state="disabled")
        self._refresh_headings()
        self._refresh_table()

    def _process_queue(self) -> None:
        try:
            while True:
                message = self.progress_queue.get_nowait()
                kind = message[0]
                if kind == "progress":
                    _, done, total, package_name = message
                    self.progress["value"] = done
                    self.progress["maximum"] = total
                    self.status_var.set(f"Completed {done}/{total}: {package_name}")
                elif kind == "done":
                    _, rows = message
                    self.current_rows = rows
                    if self.sort_column:
                        self.current_rows.sort(
                            key=lambda row: self._sort_key(row, self.sort_column),
                            reverse=self.sort_reverse,
                        )
                    self.run_button.config(state="normal")
                    self.export_button.config(state="normal")
                    self.progress["value"] = self.progress["maximum"]
                    self.status_var.set("Audit completed")
                    self._refresh_table()
                elif kind == "error":
                    self.run_button.config(state="normal")
                    self.export_button.config(state="normal" if self.current_rows else "disabled")
                    self.status_var.set("Audit failed")
                    messagebox.showerror("Audit error", message[1])
        except queue.Empty:
            pass
        self.after(100, self._process_queue)


if __name__ == "__main__":
    PlayStoreAuditApp().mainloop()
