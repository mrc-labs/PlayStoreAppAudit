from __future__ import annotations

import csv
import queue
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from playstore_audit_core import AuditConfig, audit_apps, load_apps, write_results


class PlayStoreAuditApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Play Store App Audit")
        self.geometry("760x470")
        self.minsize(700, 430)
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.country_var = tk.StringVar(value="it")
        self.language_var = tk.StringVar(value="it")
        self.workers_var = tk.IntVar(value=16)
        self.status_var = tk.StringVar(value="Pronto")
        self.progress_queue: queue.Queue = queue.Queue()
        self._build_ui()
        self.after(100, self._process_queue)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Play Store App Audit", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14))
        ttk.Label(frame, text="File CSV/TXT:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.input_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=8)
        ttk.Button(frame, text="Scegli file", command=self._choose_input).grid(row=1, column=3)
        ttk.Button(frame, text="Estrai app dal telefono con ADB", command=self._extract_from_adb).grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 14))
        ttk.Label(frame, text="Cartella output:").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.output_var).grid(row=3, column=1, columnspan=2, sticky="ew", padx=8)
        ttk.Button(frame, text="Scegli cartella", command=self._choose_output).grid(row=3, column=3)
        options = ttk.LabelFrame(frame, text="Impostazioni", padding=10)
        options.grid(row=4, column=0, columnspan=4, sticky="ew", pady=16)
        ttk.Label(options, text="Paese:").grid(row=0, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.country_var, width=8).grid(row=0, column=1, padx=(5, 20))
        ttk.Label(options, text="Lingua:").grid(row=0, column=2, sticky="w")
        ttk.Entry(options, textvariable=self.language_var, width=8).grid(row=0, column=3, padx=(5, 20))
        ttk.Label(options, text="Thread:").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(options, from_=1, to=32, textvariable=self.workers_var, width=7).grid(row=0, column=5, padx=5)
        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(4, 8))
        ttk.Label(frame, textvariable=self.status_var).grid(row=6, column=0, columnspan=4, sticky="w")
        self.run_button = ttk.Button(frame, text="Avvia analisi", command=self._start_audit)
        self.run_button.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(18, 0), ipady=7)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)

    def _choose_input(self) -> None:
        selected = filedialog.askopenfilename(title="Scegli la lista delle app", filetypes=[("File app", "*.csv *.tsv *.txt"), ("CSV", "*.csv"), ("Testo", "*.txt"), ("Tutti i file", "*.*")])
        if selected:
            self.input_var.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Scegli la cartella di output")
        if selected:
            self.output_var.set(selected)

    def _find_adb(self) -> str | None:
        candidates = [shutil.which("adb"), str(Path.cwd() / "adb.exe"), str(Path.cwd() / "platform-tools" / "adb.exe")]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    def _extract_from_adb(self) -> None:
        adb = self._find_adb()
        if not adb:
            messagebox.showerror("ADB non trovato", "Installa Android SDK Platform-Tools oppure copia adb.exe nella cartella dell'app.")
            return
        try:
            devices = subprocess.run([adb, "devices"], check=True, capture_output=True, text=True, timeout=20).stdout.splitlines()
            connected = [line.split()[0] for line in devices[1:] if line.strip() and line.strip().endswith("\tdevice")]
            if not connected:
                raise RuntimeError("Nessun telefono autorizzato. Attiva Debug USB e conferma l'autorizzazione sul telefono.")
            result = subprocess.run([adb, "shell", "pm", "list", "packages", "-3"], check=True, capture_output=True, text=True, timeout=60)
            packages = sorted({line.replace("package:", "", 1).strip() for line in result.stdout.splitlines() if line.strip().startswith("package:")})
            if not packages:
                raise RuntimeError("ADB non ha restituito app di terze parti.")
            output_dir = Path(self.output_var.get() or Path.home() / "Downloads")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"android_packages_{timestamp}.csv"
            with output_file.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=["app_name", "package_name"])
                writer.writeheader()
                for package in packages:
                    writer.writerow({"app_name": "", "package_name": package})
            self.input_var.set(str(output_file))
            messagebox.showinfo("Lista creata", f"Trovate {len(packages)} app.\n\nFile salvato in:\n{output_file}")
        except Exception as exc:
            messagebox.showerror("Errore ADB", str(exc))

    def _start_audit(self) -> None:
        input_path = Path(self.input_var.get().strip())
        output_dir = Path(self.output_var.get().strip())
        if not input_path.exists():
            messagebox.showerror("File mancante", "Scegli un file CSV, TSV o TXT valido.")
            return
        self.run_button.config(state="disabled")
        self.progress["value"] = 0
        self.status_var.set("Lettura del file…")
        threading.Thread(target=self._audit_worker, args=(input_path, output_dir), daemon=True).start()

    def _audit_worker(self, input_path: Path, output_dir: Path) -> None:
        try:
            apps = load_apps(input_path)
            self.progress_queue.put(("total", len(apps)))
            config = AuditConfig(country=(self.country_var.get().strip() or "it").lower(), language=(self.language_var.get().strip() or "it").lower(), max_workers=max(1, int(self.workers_var.get())))
            def progress(done: int, total: int, package_name: str) -> None:
                self.progress_queue.put(("progress", done, total, package_name))
            rows = audit_apps(apps, config, progress)
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = input_path.stem
            complete = output_dir / f"{stem}_playstore_audit_{timestamp}.csv"
            problems = output_dir / f"{stem}_playstore_problems_{timestamp}.csv"
            write_results(rows, complete, problems)
            self.progress_queue.put(("done", str(complete), str(problems)))
        except Exception as exc:
            self.progress_queue.put(("error", str(exc)))

    def _process_queue(self) -> None:
        try:
            while True:
                message = self.progress_queue.get_nowait()
                kind = message[0]
                if kind == "total":
                    self.progress["maximum"] = message[1]
                elif kind == "progress":
                    _, done, total, package_name = message
                    self.progress["value"] = done
                    self.status_var.set(f"Completate {done}/{total}: {package_name}")
                elif kind == "done":
                    _, complete, problems = message
                    self.run_button.config(state="normal")
                    self.status_var.set("Analisi completata")
                    messagebox.showinfo("Completato", f"Output completo:\n{complete}\n\nSolo problemi:\n{problems}")
                elif kind == "error":
                    self.run_button.config(state="normal")
                    self.status_var.set("Errore")
                    messagebox.showerror("Errore", message[1])
        except queue.Empty:
            pass
        self.after(100, self._process_queue)


if __name__ == "__main__":
    PlayStoreAuditApp().mainloop()
