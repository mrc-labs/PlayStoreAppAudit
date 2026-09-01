from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from playstore_app_audit.devices.adb import run_adb
from playstore_app_audit.services import store_locale


@dataclass(frozen=True, slots=True)
class ScanSession:
    """Immutable context captured by one completed Scan Phone operation."""

    session_id: str
    captured_at: datetime
    source_id: str
    source_kind: Literal["device"]
    device_id: str
    serial_masked: str
    manufacturer: str
    model: str
    android_version: str
    android_api: str
    security_patch: str
    locale: store_locale.StoreLocale | None
    packages: tuple[str, ...]
    system_packages: frozenset[str]
    system_scope: Literal["third_party_only", "all_packages"]
    locale_fallback_attempted: bool

    @property
    def package_count(self) -> int:
        return len(self.packages)

    @property
    def system_package_count(self) -> int:
        return len(self.system_packages)

    @property
    def third_party_package_count(self) -> int:
        return max(0, self.package_count - self.system_package_count)

    @property
    def excludes_system_packages(self) -> bool:
        return self.system_scope == "third_party_only"

    def device_summary(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "serial_masked": self.serial_masked,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "android_version": self.android_version,
            "android_api": self.android_api,
            "security_patch": self.security_patch,
            "total_packages": self.package_count,
            "system_packages": self.system_package_count,
            "third_party_packages": self.third_party_package_count,
            "captured_at": self.captured_at.isoformat(),
        }


def _parse_packages(text: str) -> tuple[str, ...]:
    packages = {
        line.removeprefix("package:").strip()
        for line in str(text or "").splitlines()
        if line.strip().startswith("package:")
    }
    return tuple(sorted(package for package in packages if package))


def _device_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in str(text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def _authorised_serial(devices_output: str) -> str:
    rows = _device_rows(devices_output)
    authorised = [serial for serial, state in rows if state == "device"]
    unauthorised = [serial for serial, state in rows if state == "unauthorized"]
    offline = [serial for serial, state in rows if state == "offline"]
    if len(authorised) == 1:
        return authorised[0]
    if len(authorised) > 1:
        raise RuntimeError(
            "More than one authorised Android device is visible to ADB. Keep only the "
            "phone you want to scan connected, then scan again."
        )
    if unauthorised:
        raise RuntimeError(
            "The phone is visible to ADB but is not authorised. Unlock it and accept "
            "'Allow USB debugging?', then scan again."
        )
    if offline:
        raise RuntimeError(
            "The phone is visible to ADB but is offline. Reconnect the USB cable, "
            "unlock it and try again."
        )
    raise RuntimeError(
        "ADB is installed, but no Android phone is visible. Check USB debugging, "
        "cable/data mode and any operating-system USB permissions or drivers."
    )


def _masked_device_identity(serial: str) -> tuple[str, str]:
    device_id = (
        hashlib.sha256(serial.encode("utf-8", errors="ignore")).hexdigest()[:16]
        if serial
        else "unknown"
    )
    if len(serial) >= 4:
        masked = f"••••{serial[-4:]}"
    elif serial:
        masked = "•" * len(serial)
    else:
        masked = "Unknown"
    return device_id, masked


def device_summary_from_properties(
    properties: dict[str, str],
    serial: str,
    total_packages: int = 0,
    system_packages: int = 0,
    *,
    captured_at: datetime | None = None,
) -> dict[str, object]:
    device_id, serial_masked = _masked_device_identity(serial)
    captured = captured_at or datetime.now(UTC)
    return {
        "device_id": device_id,
        "serial_masked": serial_masked,
        "manufacturer": properties.get("ro.product.manufacturer", ""),
        "model": properties.get("ro.product.model", ""),
        "android_version": properties.get("ro.build.version.release", ""),
        "android_api": properties.get("ro.build.version.sdk", ""),
        "security_patch": properties.get("ro.build.version.security_patch", ""),
        "total_packages": int(total_packages),
        "system_packages": int(system_packages),
        "third_party_packages": max(0, int(total_packages) - int(system_packages)),
        "captured_at": captured.isoformat(),
    }


def collect_scan_session(adb: str, *, exclude_system: bool) -> ScanSession:
    """Collect one atomic, read-only phone source without repeating device context probes."""

    captured_at = datetime.now(UTC)
    devices_output = run_adb(adb, "devices", timeout=20).stdout
    serial = _authorised_serial(devices_output)

    try:
        properties_output = run_adb(adb, "shell", "getprop", timeout=25).stdout
    except Exception as exc:
        raise RuntimeError("ADB could not read the connected phone's device summary.") from exc
    properties = store_locale.parse_getprop_output(properties_output)

    detected_locale = store_locale.locale_from_android_properties(properties)
    fallback_attempted = detected_locale is None
    if detected_locale is None:
        detected_locale = store_locale.detect_android_store_locale_from_properties(adb, properties)

    package_args = ("shell", "pm", "list", "packages", "-3") if exclude_system else (
        "shell",
        "pm",
        "list",
        "packages",
    )
    packages = _parse_packages(run_adb(adb, *package_args, timeout=60).stdout)
    if not packages:
        raise RuntimeError("ADB returned no Android packages.")

    system_packages: frozenset[str]
    if exclude_system:
        system_packages = frozenset()
    else:
        system_output = run_adb(
            adb, "shell", "pm", "list", "packages", "-s", timeout=60
        ).stdout
        system_packages = frozenset(_parse_packages(system_output))

    device_id, serial_masked = _masked_device_identity(serial)
    session_id = uuid4().hex
    return ScanSession(
        session_id=session_id,
        captured_at=captured_at,
        source_id=f"device:{device_id}:{session_id}",
        source_kind="device",
        device_id=device_id,
        serial_masked=serial_masked,
        manufacturer=properties.get("ro.product.manufacturer", ""),
        model=properties.get("ro.product.model", ""),
        android_version=properties.get("ro.build.version.release", ""),
        android_api=properties.get("ro.build.version.sdk", ""),
        security_patch=properties.get("ro.build.version.security_patch", ""),
        locale=detected_locale,
        packages=packages,
        system_packages=system_packages,
        system_scope="third_party_only" if exclude_system else "all_packages",
        locale_fallback_attempted=fallback_attempted,
    )
