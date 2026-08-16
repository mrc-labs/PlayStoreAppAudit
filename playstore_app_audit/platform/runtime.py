from __future__ import annotations

import ctypes
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

APP_DIR_NAME = "PlayStoreAppAudit"
PLATFORM_TOOLS_PAGE = "https://developer.android.com/tools/releases/platform-tools"
PLATFORM_TOOLS_URLS = {
    "windows": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "macos": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
    "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
}


def platform_key() -> str:
    name = platform.system().lower()
    if name == "windows":
        return "windows"
    if name == "darwin":
        return "macos"
    return "linux"


def platform_label() -> str:
    return {"windows": "Windows", "macos": "macOS", "linux": "Linux"}[platform_key()]


def adb_executable_name() -> str:
    return "adb.exe" if platform_key() == "windows" else "adb"


def platform_tools_url() -> str:
    return PLATFORM_TOOLS_URLS[platform_key()]


def app_data_dir() -> Path:
    key = platform_key()
    if key == "windows":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    elif key == "macos":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    target = base / APP_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def managed_platform_tools_dir() -> Path:
    return app_data_dir() / "platform-tools"


def _country_from_locale_string(value: str) -> str | None:
    text = str(value or "").strip()
    match = re.search(r"(?:_|-)([A-Za-z]{2})(?:[.@]|$)", text)
    if match:
        return match.group(1).lower()
    return None


def detect_store_country() -> str:
    """Return the best available ISO alpha-2 region for the current desktop OS."""
    if platform_key() == "windows":
        try:
            buffer = ctypes.create_unicode_buffer(16)
            get_geo_name = ctypes.windll.kernel32.GetUserDefaultGeoName
            result = get_geo_name(buffer, len(buffer))
            value = buffer.value.strip()
            if result and len(value) == 2 and value.isalpha():
                return value.lower()
        except Exception:
            pass

    for env_name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        country = _country_from_locale_string(os.environ.get(env_name, ""))
        if country:
            return country

    try:
        language, _encoding = locale.getlocale()
        country = _country_from_locale_string(language or "")
        if country:
            return country
    except Exception:
        pass
    return "us"


def hidden_subprocess_kwargs() -> dict[str, Any]:
    """Hide spawned console windows on Windows; no-op elsewhere."""
    if platform_key() != "windows":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def adb_candidates() -> list[Path]:
    name = adb_executable_name()
    candidates: list[Path] = []
    on_path = shutil.which("adb")
    if on_path:
        candidates.append(Path(on_path))
    candidates += [
        Path.cwd() / name,
        Path.cwd() / "platform-tools" / name,
        managed_platform_tools_dir() / name,
    ]

    key = platform_key()
    if key == "windows":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Android" / "Sdk" / "platform-tools" / name)
    elif key == "macos":
        candidates.append(Path.home() / "Library" / "Android" / "sdk" / "platform-tools" / name)
    else:
        candidates += [
            Path.home() / "Android" / "Sdk" / "platform-tools" / name,
            Path.home() / "Android" / "sdk" / "platform-tools" / name,
        ]

    for env_name in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value) / "platform-tools" / name)

    seen: set[str] = set()
    result: list[Path] = []
    for candidate in candidates:
        key_value = str(candidate.expanduser().resolve(strict=False))
        if key_value not in seen:
            seen.add(key_value)
            result.append(Path(key_value))
    return result


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()
