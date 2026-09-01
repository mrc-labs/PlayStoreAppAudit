from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from playstore_app_audit.devices.adb import run_adb
from playstore_app_audit.services import installer_source, store_locale


@dataclass(frozen=True, slots=True)
class CompactPackageMetadata:
    """Small immutable PackageManager snapshot captured during Scan Phone.

    ``None`` means that PackageManager did not make the field available. An
    empty installer package is distinct: the aggregate response explicitly
    reported no installer, which keeps the existing Unknown / preinstalled
    classification without pretending that collection succeeded when it did
    not.
    """

    package_name: str
    installed_version_code: str | None
    installer_package: str | None
    installer_source: str | None
    installer_category: str | None
    is_enabled: bool | None
    is_system: bool

    @property
    def app_enabled(self) -> str:
        if self.is_enabled is None:
            return "Unknown"
        return "Enabled" if self.is_enabled else "Disabled"


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
    package_metadata: tuple[CompactPackageMetadata, ...]
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

    def metadata_by_package(self) -> dict[str, CompactPackageMetadata]:
        return {item.package_name: item for item in self.package_metadata}

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


def _parse_compact_package_rows(text: str) -> dict[str, tuple[str | None, str | None]]:
    """Return package -> (versionCode, installer package) from aggregate output."""

    parsed: dict[str, tuple[str | None, str | None]] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        package_match = re.match(r"^package:(\S+)(.*)$", line)
        if not package_match:
            continue
        package = package_match.group(1).strip()
        if not package:
            continue
        suffix = package_match.group(2)
        version_match = re.search(r"(?:^|\s)versionCode(?::|=)(\d+)(?:\s|$)", suffix)
        installer_match = re.search(r"(?:^|\s)installer=(\S+)(?:\s|$)", suffix)
        parsed[package] = (
            version_match.group(1) if version_match else None,
            installer_match.group(1) if installer_match else None,
        )
    return parsed


def _parse_packages(text: str) -> tuple[str, ...]:
    return tuple(sorted(_parse_compact_package_rows(text)))


def _collect_compact_package_rows(
    adb: str, *, exclude_system: bool
) -> dict[str, tuple[str | None, str | None]]:
    """Enumerate packages once with compact fields and low-cost aggregate fallbacks."""

    base_args = ("shell", "pm", "list", "packages")
    if exclude_system:
        base_args += ("-3",)

    # Supported Android releases return one line per package containing both
    # `versionCode:<number>` and `installer=<package-or-null>`. This replaces
    # the old plain enumeration; it is not an additional package-list call.
    try:
        preferred = run_adb(
            adb, *base_args, "-i", "--show-versioncode", timeout=60
        ).stdout
        parsed = _parse_compact_package_rows(preferred)
        if parsed:
            return parsed
    except Exception:
        pass

    # Some older PackageManager builds support installer output but not
    # --show-versioncode. Preserve that safe subset without per-package work.
    try:
        installer_only = run_adb(adb, *base_args, "-i", timeout=60).stdout
        parsed = _parse_compact_package_rows(installer_only)
        if parsed:
            return parsed
    except Exception:
        pass

    # Final compatibility path is the exact Phase A aggregate enumeration.
    plain = run_adb(adb, *base_args, timeout=60).stdout
    return _parse_compact_package_rows(plain)


def _disabled_packages(
    adb: str, *, exclude_system: bool
) -> frozenset[str] | None:
    args = ("shell", "pm", "list", "packages")
    if exclude_system:
        args += ("-3",)
    try:
        output = run_adb(adb, *args, "-d", timeout=45).stdout
    except Exception:
        return None
    return frozenset(_parse_packages(output))


def _compact_metadata(
    package_rows: dict[str, tuple[str | None, str | None]],
    system_packages: frozenset[str],
    disabled_packages: frozenset[str] | None,
) -> tuple[CompactPackageMetadata, ...]:
    items: list[CompactPackageMetadata] = []
    for package in sorted(package_rows):
        version_code, raw_installer = package_rows[package]
        if raw_installer is None:
            friendly = None
            category = None
        else:
            classified = installer_source.classify_installer_package(raw_installer)
            raw_installer = classified.package
            friendly = classified.label
            category = classified.category
        items.append(
            CompactPackageMetadata(
                package_name=package,
                installed_version_code=version_code,
                installer_package=raw_installer,
                installer_source=friendly,
                installer_category=category,
                is_enabled=(
                    None if disabled_packages is None else package not in disabled_packages
                ),
                is_system=package in system_packages,
            )
        )
    return tuple(items)


def enrich_rows_with_compact_metadata(
    rows: list[dict[str, object]], session: ScanSession | None
) -> None:
    """Overlay T1 compact fields without fabricating rich package metadata."""

    if session is None:
        return
    by_package = session.metadata_by_package()
    for row in rows:
        package = str(row.get("package_name") or "")
        compact = by_package.get(package)
        if compact is None:
            continue
        if compact.installed_version_code is not None:
            row["installed_version_code"] = compact.installed_version_code
        if compact.installer_package is not None:
            row["installer_package"] = compact.installer_package
            row["installer_source"] = compact.installer_source or ""
            row["installer_category"] = compact.installer_category or ""
        if compact.is_enabled is not None:
            row["app_enabled"] = compact.app_enabled
        elif not row.get("app_enabled"):
            row["app_enabled"] = "Unknown"
        row["is_system"] = compact.is_system


def inventory_rows(session: ScanSession) -> list[dict[str, object]]:
    """Build the coherent T1-only inventory representation for baseline work."""

    return [
        {
            "package_name": item.package_name,
            "installed_version": "",
            "installed_version_code": item.installed_version_code or "",
            "installer_package": item.installer_package or "",
            "installer_source": item.installer_source or "",
            "installer_category": item.installer_category or "",
            "app_enabled": item.app_enabled if item.is_enabled is not None else "Unknown",
            "is_system": item.is_system,
            "play_title": "",
        }
        for item in session.package_metadata
    ]


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


def authorised_device_matches(adb: str, expected_device_id: str) -> bool:
    """Return whether the one authorised phone is the session's hashed device."""

    try:
        devices_output = run_adb(adb, "devices", timeout=20).stdout
        serial = _authorised_serial(devices_output)
    except Exception:
        return False
    device_id, _masked = _masked_device_identity(serial)
    return bool(expected_device_id) and device_id == expected_device_id


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

    package_rows = _collect_compact_package_rows(adb, exclude_system=exclude_system)
    packages = tuple(sorted(package_rows))
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

    disabled_packages = _disabled_packages(adb, exclude_system=exclude_system)
    package_metadata = _compact_metadata(
        package_rows, system_packages, disabled_packages
    )

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
        package_metadata=package_metadata,
        system_packages=system_packages,
        system_scope="third_party_only" if exclude_system else "all_packages",
        locale_fallback_attempted=fallback_attempted,
    )
