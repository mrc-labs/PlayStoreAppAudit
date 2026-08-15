from __future__ import annotations

import ctypes
import locale
import os
import shutil
import subprocess
import tempfile
import urllib.request
import webbrowser
import zipfile
from pathlib import Path
from tkinter import messagebox

from playstore_audit_gui import PlayStoreAuditApp


class WindowsPlayStoreAuditApp(PlayStoreAuditApp):
    """Windows-specific shell around the main GUI.

    Adds:
    - Store country defaulted from the Windows geographic region.
    - English as the default Store language.
    - Better ADB discovery.
    - Optional one-click Platform-Tools download directly from Google.
    """

    PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    PLATFORM_TOOLS_PAGE = "https://developer.android.com/tools/releases/platform-tools"
    SDK_LICENSE_PAGE = "https://developer.android.com/studio/terms"

    def __init__(self) -> None:
        super().__init__()
        self.language_var.set("en")
        self.country_var.set(self._detect_windows_country())

    @staticmethod
    def _detect_windows_country() -> str:
        """Return the user's Windows geographic region as ISO 3166-1 alpha-2.

        Windows GetUserDefaultGeoName reads the Region setting rather than the
        UI/display language, which is exactly what we want for Play Store market.
        """
        if os.name == "nt":
            try:
                buffer = ctypes.create_unicode_buffer(16)
                get_geo_name = ctypes.windll.kernel32.GetUserDefaultGeoName
                result = get_geo_name(buffer, len(buffer))
                value = buffer.value.strip()
                if result and len(value) == 2 and value.isalpha():
                    return value.lower()
            except Exception:
                pass

        # Conservative fallback for non-Windows/dev runs.
        try:
            locale_name = locale.getlocale()[0] or ""
            if "_" in locale_name:
                region = locale_name.rsplit("_", 1)[-1]
                if len(region) == 2 and region.isalpha():
                    return region.lower()
        except Exception:
            pass
        return "it"

    @staticmethod
    def _managed_platform_tools_dir() -> Path:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "PlayStoreAppAudit" / "platform-tools"

    def _find_adb(self) -> str | None:
        candidates: list[str | None] = []

        # Existing discovery from the base application first.
        base_adb = super()._find_adb()
        candidates.append(base_adb)

        # ADB managed by this app.
        candidates.append(str(self._managed_platform_tools_dir() / "adb.exe"))

        # Standard Android Studio SDK location.
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(str(Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe"))

        # Common SDK environment variables.
        for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
            value = os.environ.get(variable)
            if value:
                candidates.append(str(Path(value) / "platform-tools" / "adb.exe"))

        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            normalised = str(Path(candidate))
            if normalised in seen:
                continue
            seen.add(normalised)
            if Path(normalised).is_file():
                return normalised
        return None

    def _install_platform_tools(self) -> str | None:
        choice = messagebox.askyesnocancel(
            "Install Android Platform-Tools",
            "ADB is not installed on this PC.\n\n"
            "Yes: download the latest Windows Platform-Tools directly from Google "
            "and install them only for PlayStoreAppAudit.\n\n"
            "No: open Google's official Platform-Tools page so you can install them manually.\n\n"
            "By choosing Yes and using the SDK tools, you confirm that you have reviewed "
            "and accept Google's Android SDK License Agreement.",
        )

        if choice is None:
            return None
        if choice is False:
            webbrowser.open(self.PLATFORM_TOOLS_PAGE)
            return None

        target = self._managed_platform_tools_dir()
        self.status_var.set("Downloading latest Android Platform-Tools from Google…")
        self.update_idletasks()

        try:
            with tempfile.TemporaryDirectory(prefix="playstore_audit_adb_") as temp_dir:
                temp_root = Path(temp_dir)
                archive_path = temp_root / "platform-tools.zip"
                request = urllib.request.Request(
                    self.PLATFORM_TOOLS_URL,
                    headers={"User-Agent": "PlayStoreAppAudit/1.0"},
                )
                with urllib.request.urlopen(request, timeout=90) as response, archive_path.open("wb") as output:
                    shutil.copyfileobj(response, output)

                extract_root = temp_root / "extract"
                extract_root.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(archive_path, "r") as archive:
                    # The archive is downloaded from Google's official fixed endpoint.
                    archive.extractall(extract_root)

                extracted_tools = extract_root / "platform-tools"
                extracted_adb = extracted_tools / "adb.exe"
                if not extracted_adb.is_file():
                    raise RuntimeError("Google Platform-Tools archive did not contain adb.exe.")

                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(extracted_tools, target)

            adb = target / "adb.exe"
            version = subprocess.run(
                [str(adb), "version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            ).stdout.strip().splitlines()
            version_text = version[0] if version else "ADB installed"
            self.status_var.set("ADB installed. Connect/authorise the phone and scan again.")
            messagebox.showinfo(
                "ADB installed",
                f"{version_text}\n\nInstalled in:\n{target}\n\n"
                "If your phone is connected, keep it unlocked and accept the USB debugging RSA prompt if it appears.",
            )
            return str(adb)
        except Exception as exc:
            self.status_var.set("ADB installation failed")
            messagebox.showerror(
                "ADB installation failed",
                f"Could not download/install Platform-Tools automatically.\n\n{exc}\n\n"
                "The official Google download page will now open.",
            )
            webbrowser.open(self.PLATFORM_TOOLS_PAGE)
            return None

    def _scan_phone(self) -> None:
        adb = self._find_adb()
        if not adb:
            adb = self._install_platform_tools()
            if not adb:
                return

        self.status_var.set("Checking ADB device connection…")
        self.update_idletasks()

        try:
            devices_output = subprocess.run(
                [adb, "devices"],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            ).stdout.splitlines()

            device_rows = []
            for line in devices_output[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    device_rows.append((parts[0], parts[1]))

            authorised = [serial for serial, state in device_rows if state == "device"]
            unauthorised = [serial for serial, state in device_rows if state == "unauthorized"]
            offline = [serial for serial, state in device_rows if state == "offline"]

            if not authorised:
                if unauthorised:
                    raise RuntimeError(
                        "The phone is visible to ADB but is not authorised.\n\n"
                        "Unlock the phone and accept the 'Allow USB debugging?' RSA prompt, "
                        "then click Scan phone with ADB again."
                    )
                if offline:
                    raise RuntimeError(
                        "The phone is visible to ADB but is offline. Disconnect/reconnect the USB cable, "
                        "unlock the phone, and try again."
                    )
                raise RuntimeError(
                    "ADB is installed, but no Android phone is visible.\n\n"
                    "Check that USB debugging is enabled, use a data-capable USB cable, "
                    "select a USB data/file-transfer mode if needed, and install the phone manufacturer's USB driver if Windows requires it."
                )

            self.status_var.set("Scanning connected phone…")
            self.update_idletasks()

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
                f"Phone scan: {len(all_packages)} total packages | "
                f"{user_count} third-party | {len(system_packages)} system"
            )
            self.status_var.set("Phone scan ready. Run the Play Store audit.")
        except Exception as exc:
            self.status_var.set("Phone scan failed")
            messagebox.showerror("ADB connection error", str(exc))


if __name__ == "__main__":
    WindowsPlayStoreAuditApp().mainloop()
