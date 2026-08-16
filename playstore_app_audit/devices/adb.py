from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from playstore_app_audit import __version__
from playstore_app_audit.platform.runtime import (
    adb_candidates,
    adb_executable_name,
    hidden_subprocess_kwargs,
    managed_platform_tools_dir,
    managed_platform_tools_download_supported,
    managed_platform_tools_unavailable_message,
    platform_tools_url,
)


def run_adb(adb: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [adb, *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        **hidden_subprocess_kwargs(),
    )


def find_adb() -> str | None:
    """Return the first ADB candidate that can actually execute on this host."""
    for candidate in adb_candidates():
        if not candidate.is_file():
            continue
        try:
            run_adb(str(candidate), "version", timeout=10)
        except (OSError, subprocess.SubprocessError):
            # Important on Linux ARM64: an old managed x86-64 Platform-Tools
            # download may still exist from an earlier build. Ignore unusable
            # binaries and continue looking for a native distro/SDK ADB.
            continue
        return str(candidate)
    return None


def is_authorised(adb: str) -> bool:
    try:
        lines = run_adb(adb, "devices", timeout=20).stdout.splitlines()
    except Exception:
        return False
    return any(len(line.split()) >= 2 and line.split()[1] == "device" for line in lines[1:])


def install_platform_tools() -> tuple[str, str]:
    """Download the current official Google Platform-Tools archive for this OS."""
    if not managed_platform_tools_download_supported():
        raise RuntimeError(managed_platform_tools_unavailable_message())

    target = managed_platform_tools_dir()
    executable = adb_executable_name()

    with tempfile.TemporaryDirectory(prefix="playstore_audit_adb_") as temp_dir:
        temp_root = Path(temp_dir)
        archive_path = temp_root / "platform-tools.zip"
        request = urllib.request.Request(
            platform_tools_url(),
            headers={"User-Agent": f"PlayStoreAppAudit/{__version__}"},
        )
        with urllib.request.urlopen(request, timeout=90) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)

        extract_root = temp_root / "extract"
        extract_root.mkdir(parents=True, exist_ok=True)
        root_resolved = extract_root.resolve()
        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.infolist():
                destination = (extract_root / member.filename).resolve()
                if destination != root_resolved and root_resolved not in destination.parents:
                    raise RuntimeError("Unsafe path in Platform-Tools archive.")
            archive.extractall(extract_root)

        extracted = extract_root / "platform-tools"
        extracted_adb = extracted / executable
        if not extracted_adb.is_file():
            raise RuntimeError(f"Google Platform-Tools archive did not contain {executable}.")

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(extracted, target)

    adb = target / executable
    if executable != "adb.exe":
        adb.chmod(adb.stat().st_mode | 0o111)
    version_lines = run_adb(str(adb), "version", timeout=20).stdout.strip().splitlines()
    version_text = version_lines[0] if version_lines else "ADB installed"
    return str(adb), version_text
