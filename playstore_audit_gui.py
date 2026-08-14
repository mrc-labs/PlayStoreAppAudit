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
        "updated_source": 160,
        "notes": 330,
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Play Store App Audit")
        self.geometry("1320x760")
        self.minsize(1000, 620)

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
        self.device_apps: list[dict[str, str]] = []
        self.current_rows: list[dict[str, object]] = []
        self.source_mode: str | None = None
        self.sort_column: str | None = None
        self.sort_reverse = False

        self._build_ui()
        self.filter_var.trace_add("write", lambda *_: self._refresh_table())
        self.after(100, self._process_queue)

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
        ttk.Checkbutton(options, text="Exclude system apps when scanning phone", variable=self.exclude_system_var).grid(row=0, column=6, sticky="w")

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
        self.device_apps = []
        self.source_mode = "file"
        self.input_var.set(selected)
        try:
            count = len(load_apps(selected))
            self.source_var.set(f"File selected: {count} unique Android packages")
        except Exception:
            self.source_var.set("File selected")

    def _find_adb(self) -> str | None:
        candidates = [shutil.which("adb"), str(Path.cwd() / "adb.exe"), str(Path.cwd() / "platform-tools" / "adb.exe")]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    def _scan_phone(self) -> None:
        adb = self._find_adb()
        if not adb:
            messagebox.showerror("ADB not found", "Install Android SDK Platform-Tools or put adb.exe / the platform-tools folder next to the application.")
            return
        self.status_var.set("Scanning connected phone…")
        self.update_idletasks()
        try:
            devices = subprocess.run([adb, "devices"], check=True, capture_output=True, text=True, timeout=20).stdout.splitlines()
            connected = [line.split()[0] for line in devices[1:] if line.strip() and line.strip().endswith("\tdevice")]
            if not connected:
                raise RuntimeError("No authorised Android phone found. Enable USB debugging and accept the computer authorisation on the phone.")
            command = [adb, "shell", "pm", "list", "packages"]
            if self.exclude_system_var.get():
                command.append("-3")
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
            packages = sorted({line.replace("package:", "", 1).strip() for line in result.stdout.splitlines() if line.strip().startswith("package:")})
            if not packages:
                raise RuntimeError("ADB returned no Android packages.")
            self.device_apps = [{"app_name": package, "package_name": package} for package in packages]
            self.source_mode = "device"
            self.input_var.set("")
            scope = "third-party apps only" if self.exclude_system_var.get() else "third-party + system apps"
            self.source_var.set(f"Phone scan: {len(packages)} packages ({scope})")
            self.status_var.set("Phone scan ready. Run the Play Store audit.")
        except Exception as exc:
            self.status_var.set("Phone scan failed")
            messagebox.showerror("ADB error", str(exc))

    def _get_apps_to_audit(self) -> list[dict[str, str]]:
        if self.source_mode == "device" and self.device_apps:
            return list(self.device_apps)
        if self.source_mode == "file":
            input_value = self.input_var.get().strip()
            if input_value:
                return load_apps(input_value)
        raise ValueError("Choose a CSV/TXT file or scan a connected Android phone first.")

    def _start_audit(self) -> None:
        try:
            apps = self._get_apps_to_audit()
        except Exception as exc:
            messagebox.showerror("No app list", str(exc))
            return
        try:
            workers = max(1, int(self.workers_var.get()))
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Parallel threads must be a number.")
            return
        self.run_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(apps)
        self.status_var.set(f"Starting audit for {len(apps)} packages…")
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
        package_name = self.tree.set(selection[0], "package_name")
        row = next((item for item in self.current_rows if str(item.get("package_name", "")) == package_name), None)
        if row and row.get("store_url"):
            webbrowser.open(str(row["store_url"]))

    def _export_results(self) -> None:
        if not self.current_rows:
            messagebox.showinfo("Nothing to export", "Run an audit first.")
            return
        destination = filedialog.asksaveasfilename(
            title="Export audit results",
            defaultextension=".csv",
            initialfile="playstore_audit_results.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not destination:
            return
        try:
            with open(destination, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
                writer.writeheader()
                writer.writerows(self.current_rows)
            messagebox.showinfo("Export complete", f"Saved {len(self.current_rows)} rows to:\n{destination}")
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
                    self.progress["maximum"] = total
                    self.progress["value"] = done
                    self.status_var.set(f"Completed {done}/{total}: {package_name}")
                elif kind == "done":
                    _, rows = message
                    self.current_rows = list(rows)
                    self.sort_column = "app_name"
                    self.sort_reverse = False
                    self.current_rows.sort(key=lambda row: self._sort_key(row, "app_name"))
                    self._refresh_headings()
                    self._refresh_table()
                    self.run_button.config(state="normal")
                    self.export_button.config(state="normal")
                    self.status_var.set(f"Audit complete: {len(self.current_rows)} packages")
                elif kind == "error":
                    self.run_button.config(state="normal")
                    self.status_var.set("Audit failed")
                    messagebox.showerror("Audit error", message[1])
        except queue.Empty:
            pass
        self.after(100, self._process_queue)


if __name__ == "__main__":
    PlayStoreAuditApp().mainloop()
