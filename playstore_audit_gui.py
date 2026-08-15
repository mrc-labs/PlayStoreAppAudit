from __future__ import annotations

import csv
import queue
import re
import shutil
import subprocess
import threading
import webbrowser
from datetime import date, datetime
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
        "age_days",
        "play_title",
        "updated_source",
        "notes",
        "criticality",
    )

    COLUMN_LABELS = {
        "app_name": "Input name",
        "package_name": "Package",
        "play_status": "Play status",
        "play_last_update": "Last update",
        "age_days": "Age (days)",
        "play_title": "Play Store title",
        "updated_source": "Update source",
        "notes": "Notes",
        "criticality": "Criticality",
    }

    COLUMN_WIDTHS = {
        "app_name": 160,
        "package_name": 235,
        "play_status": 175,
        "play_last_update": 105,
        "age_days": 90,
        "play_title": 190,
        "updated_source": 150,
        "notes": 260,
        "criticality": 145,
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

    MONTHS = {
        "jan": 1, "january": 1, "gen": 1, "gennaio": 1,
        "feb": 2, "february": 2, "febbraio": 2,
        "mar": 3, "march": 3, "marzo": 3,
        "apr": 4, "april": 4, "aprile": 4,
        "may": 5, "maggio": 5, "mag": 5,
        "jun": 6, "june": 6, "giu": 6, "giugno": 6,
        "jul": 7, "july": 7, "lug": 7, "luglio": 7,
        "aug": 8, "august": 8, "ago": 8, "agosto": 8,
        "sep": 9, "sept": 9, "september": 9, "set": 9, "settembre": 9,
        "oct": 10, "october": 10, "ott": 10, "ottobre": 10,
        "nov": 11, "november": 11, "novembre": 11,
        "dec": 12, "december": 12, "dic": 12, "dicembre": 12,
    }

    CRITICALITY = {
        "red": {"label": "🔴 Removed", "short": "🔴 Removed", "rank": 0, "background": "#FDF0F0", "foreground": "#6F3232"},
        "orange": {"label": "🟠 Stale", "short": "🟠 Stale", "rank": 1, "background": "#FFF4E8", "foreground": "#71491F"},
        "yellow": {"label": "🟡 Aging", "short": "🟡 Aging", "rank": 2, "background": "#FFFBE8", "foreground": "#65591E"},
        "blue": {"label": "🔵 Store anomaly", "short": "🔵 Anomaly", "rank": 3, "background": "#EEF6FC", "foreground": "#315A75"},
        "purple": {"label": "🟣 Other", "short": "🟣 Other", "rank": 4, "background": "#F7F0FA", "foreground": "#65446F"},
        "green": {"label": "🟢 Current", "short": "🟢 Current", "rank": 5, "background": "#F0F8F1", "foreground": "#35613B"},
    }

    EXPORT_FIELDS = list(OUTPUT_FIELDS) + ["is_system", "criticality", "age_days"]

    def __init__(self) -> None:
        super().__init__()
        self.title("Play Store App Audit")
        self.geometry("1460x850")
        self.minsize(1080, 670)

        self.input_var = tk.StringVar()
        self.source_var = tk.StringVar(value="No app list selected")
        self.country_var = tk.StringVar(value="it")
        self.language_var = tk.StringVar(value="it")
        self.workers_var = tk.IntVar(value=16)
        self.hide_system_var = tk.BooleanVar(value=True)
        self.filter_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="No results yet")

        self.progress_queue: queue.Queue = queue.Queue()
        self.source_mode: str | None = None
        self.file_apps: list[dict[str, str]] = []
        self.file_system_metadata: dict[str, bool] = {}
        self.device_apps_all: list[dict[str, str]] = []
        self.device_system_packages: set[str] = set()
        self.current_system_packages: set[str] = set()
        self.current_rows: list[dict[str, object]] = []
        self.sort_column: str | None = None
        self.sort_reverse = False
        self.criticality_filter: str | None = None
        self.criticality_count_vars = {
            key: tk.StringVar(value=f"{info['short']} 0")
            for key, info in self.CRITICALITY.items()
        }

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
        ttk.Spinbox(options, from_=1, to=32, textvariable=self.workers_var, width=7).grid(row=0, column=5, padx=(5, 18))
        ttk.Label(options, text="System apps are audited too, then can be hidden or shown instantly in the results.").grid(row=0, column=6, sticky="w", padx=(8, 0))

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
        results.rowconfigure(3, weight=1)

        toolbar = ttk.Frame(results)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        toolbar.columnconfigure(3, weight=1)
        ttk.Label(toolbar, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(toolbar, text="Hide system apps", variable=self.hide_system_var, command=self._refresh_table).grid(row=0, column=1, padx=(20, 16), sticky="w")
        ttk.Label(toolbar, text="Filter:").grid(row=0, column=2, sticky="e", padx=(0, 5))
        ttk.Entry(toolbar, textvariable=self.filter_var, width=34).grid(row=0, column=3, sticky="e")

        legend = ttk.Frame(results)
        legend.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        ttk.Button(legend, text="All", width=7, command=lambda: self._set_criticality_filter(None)).pack(side="left", padx=(0, 5))
        for key in ("red", "orange", "yellow", "blue", "purple", "green"):
            info = self.CRITICALITY[key]
            tk.Button(
                legend,
                textvariable=self.criticality_count_vars[key],
                command=lambda k=key: self._set_criticality_filter(k),
                relief="flat",
                bd=1,
                padx=8,
                pady=3,
                background=info["background"],
                foreground=info["foreground"],
                activebackground=info["background"],
                activeforeground=info["foreground"],
                font=("Segoe UI", 9),
                cursor="hand2",
            ).pack(side="left", padx=3)

        ttk.Label(
            results,
            text=(
                "Click a colour counter to filter. Removed = not on Store | Aging = >365–730d | "
                "Stale = >730d | Current = ≤365d | Store anomaly = unusual Store availability | Other = unknown/error"
            ),
        ).grid(row=2, column=0, sticky="w", pady=(0, 7))

        table_frame = ttk.Frame(results)
        table_frame.grid(row=3, column=0, sticky="nsew")
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
            anchor = "center" if column in {"play_status", "play_last_update", "age_days", "criticality"} else "w"
            stretch = column in {"app_name", "package_name", "play_title", "notes"}
            self.tree.column(column, width=self.COLUMN_WIDTHS[column], minwidth=80, anchor=anchor, stretch=stretch)

        for key, info in self.CRITICALITY.items():
            self.tree.tag_configure(key, background=info["background"], foreground=info["foreground"], font=("Segoe UI", 9))

        self.tree.bind("<Double-1>", self._open_selected_store_url)
        ttk.Label(results, text="Tip: click any column header to sort; double-click a row to open its Play Store page.").grid(row=4, column=0, sticky="w", pady=(6, 0))

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
        candidates = [shutil.which("adb"), str(Path.cwd() / "adb.exe"), str(Path.cwd() / "platform-tools" / "adb.exe")]
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
        result = subprocess.run([adb, "shell", "pm", "list", "packages", "-s"], check=True, capture_output=True, text=True, timeout=60)
        return self._parse_adb_packages(result.stdout)

    def _scan_phone(self) -> None:
        adb = self._get_authorised_adb()
        if not adb:
            messagebox.showerror("ADB not available", "Install Android SDK Platform-Tools, enable USB debugging and authorise the connected phone.")
            return
        self.status_var.set("Scanning connected phone…")
        self.update_idletasks()
        try:
            all_result = subprocess.run([adb, "shell", "pm", "list", "packages"], check=True, capture_output=True, text=True, timeout=60)
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
            self.source_var.set(f"Phone scan: {len(all_packages)} total packages | {user_count} third-party | {len(system_packages)} system")
            self.status_var.set("Phone scan ready. All packages will be audited; system apps can be hidden in the results table.")
        except Exception as exc:
            self.status_var.set("Phone scan failed")
            messagebox.showerror("ADB error", str(exc))

    def _is_definite_system_package(self, package_name: str) -> bool:
        if package_name in self.DEFINITE_SYSTEM_PACKAGES:
            return True
        return any(package_name.startswith(prefix) for prefix in self.DEFINITE_SYSTEM_PREFIXES)

    def _classify_file_system_packages(self, apps: list[dict[str, str]]) -> tuple[set[str], str]:
        system_packages = {package_name for package_name, is_system in self.file_system_metadata.items() if is_system}
        known_user_packages = {package_name for package_name, is_system in self.file_system_metadata.items() if not is_system}
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

        method = " + ".join(method_parts) if method_parts else "no exact classifier available; connect the source phone via ADB or add an is_system column"
        valid_packages = {app["package_name"] for app in apps}
        return system_packages.intersection(valid_packages), method

    def _get_apps_to_audit(self) -> tuple[list[dict[str, str]], set[str], str]:
        if self.source_mode == "device" and self.device_apps_all:
            return list(self.device_apps_all), set(self.device_system_packages), "ADB exact system classification"
        if self.source_mode == "file" and self.file_apps:
            system_packages, method = self._classify_file_system_packages(self.file_apps)
            return list(self.file_apps), system_packages, method
        raise ValueError("Choose a CSV/TXT file or scan a connected Android phone first.")

    def _start_audit(self) -> None:
        try:
            apps, system_packages, classification_method = self._get_apps_to_audit()
        except Exception as exc:
            messagebox.showerror("No app list", str(exc))
            return
        try:
            workers = max(1, int(self.workers_var.get()))
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Parallel threads must be a number.")
            return

        self.current_system_packages = system_packages
        self.criticality_filter = None
        self.source_var.set(
            f"{('Phone' if self.source_mode == 'device' else 'CSV/TXT')} source: {len(apps)} packages | "
            f"{len(system_packages)} classified as system | {classification_method}"
        )
        self.run_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(apps)
        self.status_var.set(f"Starting audit for all {len(apps)} packages…")
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

    def _parse_update_date(self, value: object) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            pass

        match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÀ-ÿ.]+)\s+(\d{4})", text)
        if match:
            day, month_name, year = match.groups()
            month = self.MONTHS.get(month_name.lower().rstrip("."))
            if month:
                try:
                    return date(int(year), month, int(day))
                except ValueError:
                    return None

        match = re.fullmatch(r"([A-Za-zÀ-ÿ.]+)\s+(\d{1,2}),?\s+(\d{4})", text)
        if match:
            month_name, day, year = match.groups()
            month = self.MONTHS.get(month_name.lower().rstrip("."))
            if month:
                try:
                    return date(int(year), month, int(day))
                except ValueError:
                    return None
        return None

    def _classify_criticality(self, row: dict[str, object]) -> None:
        status = str(row.get("play_status") or "").strip()
        update_date = self._parse_update_date(row.get("play_last_update"))
        age_days: int | None = None

        if status == "not_found_or_unavailable":
            key = "red"
        elif status == "available_in_fallback_locale_only":
            key = "blue"
        elif status != "available":
            key = "purple"
        elif update_date is None:
            key = "purple"
        else:
            age_days = (date.today() - update_date).days
            if age_days < 0:
                key = "purple"
            elif age_days <= 365:
                key = "green"
            elif age_days <= 730:
                key = "yellow"
            else:
                key = "orange"

        row["criticality_key"] = key
        row["criticality"] = self.CRITICALITY[key]["label"]
        row["criticality_rank"] = self.CRITICALITY[key]["rank"]
        row["age_days"] = "" if age_days is None else age_days

    def _sort_key(self, row: dict[str, object], column: str):
        if column == "criticality":
            return int(row.get("criticality_rank", 99))
        if column == "age_days":
            value = row.get("age_days", "")
            try:
                return int(value)
            except (TypeError, ValueError):
                return -1
        if column == "play_last_update":
            parsed = self._parse_update_date(row.get(column))
            return parsed.toordinal() if parsed else -1
        value = str(row.get(column, "") or "").strip()
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

    def _set_criticality_filter(self, key: str | None) -> None:
        if key is not None and self.criticality_filter == key:
            self.criticality_filter = None
        else:
            self.criticality_filter = key
        self._refresh_table()

    def _rows_before_criticality_filter(self) -> list[dict[str, object]]:
        rows = self.current_rows
        if self.hide_system_var.get():
            rows = [row for row in rows if not row.get("is_system")]

        query = self.filter_var.get().strip().casefold()
        if query:
            search_fields = list(OUTPUT_FIELDS) + ["criticality", "is_system", "age_days"]
            rows = [
                row for row in rows
                if query in " ".join(str(row.get(column, "") or "") for column in search_fields).casefold()
            ]
        return rows

    def _filtered_rows(self) -> list[dict[str, object]]:
        rows = self._rows_before_criticality_filter()
        if self.criticality_filter:
            rows = [row for row in rows if row.get("criticality_key") == self.criticality_filter]
        return rows

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

        count_rows = self._rows_before_criticality_filter()
        counts = {
            key: sum(1 for row in count_rows if row.get("criticality_key") == key)
            for key in self.CRITICALITY
        }
        for key, variable in self.criticality_count_vars.items():
            variable.set(f"{self.CRITICALITY[key]['short']} {counts[key]}")

        visible_rows = self._filtered_rows()
        for row in visible_rows:
            values = [row.get(column, "") for column in self.COLUMNS]
            tag = str(row.get("criticality_key") or "purple")
            item = self.tree.insert("", "end", values=values, tags=(tag,))
            if selected_package and row.get("package_name") == selected_package:
                self.tree.selection_set(item)

        if self.current_rows:
            hidden_system = sum(1 for row in self.current_rows if row.get("is_system")) if self.hide_system_var.get() else 0
            summary = f"showing {len(visible_rows)}/{len(self.current_rows)}"
            if hidden_system:
                summary += f" | {hidden_system} system hidden"
            if self.criticality_filter:
                summary += f" | filter: {self.CRITICALITY[self.criticality_filter]['label']}"
            self.summary_var.set(summary)
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
                writer = csv.DictWriter(handle, fieldnames=self.EXPORT_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.current_rows)
            messagebox.showinfo("Export complete", f"Results saved to:\n{selected}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _clear_results(self) -> None:
        self.current_rows = []
        self.current_system_packages = set()
        self.sort_column = None
        self.sort_reverse = False
        self.criticality_filter = None
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
                    for row in rows:
                        row["is_system"] = str(row.get("package_name") or "") in self.current_system_packages
                        self._classify_criticality(row)
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
