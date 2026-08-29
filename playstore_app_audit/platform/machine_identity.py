from __future__ import annotations

import getpass
import hashlib
import platform
import re
import socket
import subprocess
import uuid
from pathlib import Path


def _windows_machine_guid() -> str:
    try:
        import winreg

        access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            access,
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "MachineGuid")
        return str(value).strip()
    except (OSError, ImportError):
        return ""


def _linux_machine_id() -> str:
    for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return ""


def _macos_platform_uuid() -> str:
    try:
        completed = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', completed.stdout)
    return match.group(1).strip() if match else ""


def _preferred_machine_id() -> tuple[str, str]:
    system = platform.system().casefold()
    if system == "windows":
        value = _windows_machine_guid()
        if value:
            return "windows-machine-guid", value
    elif system == "linux":
        value = _linux_machine_id()
        if value:
            return "linux-machine-id", value
    elif system == "darwin":
        value = _macos_platform_uuid()
        if value:
            return "macos-platform-uuid", value
    fallback = "\0".join((socket.gethostname(), getpass.getuser(), str(uuid.getnode())))
    return "fallback-host-user-node", fallback


def local_machine_identity() -> str:
    """Return a local-only digest suitable for key derivation.

    The preferred OS identifier and the weaker deterministic fallback never
    leave this module in raw form and are never persisted or transmitted.
    """

    source, value = _preferred_machine_id()
    return hashlib.sha256(f"{source}\0{value}".encode()).hexdigest()


def local_user_identity() -> str:
    try:
        return getpass.getuser().strip() or "unknown-user"
    except OSError:
        return "unknown-user"
