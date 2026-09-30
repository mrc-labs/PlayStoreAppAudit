"""App List system flags and conservative package classification."""

from __future__ import annotations

import csv
from pathlib import Path

SYSTEM_COLUMN_NAMES = frozenset({
    "is_system", "issystem", "system", "system_app", "systemapp",
    "is_system_app", "issystemapp", "app_type", "apptype", "type",
})
PACKAGE_COLUMN_NAMES = frozenset({
    "package", "packageid", "packagename", "package_name", "appid", "app_id", "id",
})
TRUE_SYSTEM_VALUES = frozenset({
    "1", "true", "yes", "y", "system", "system_app", "systemapp", "preinstalled", "pre-installed",
})
FALSE_SYSTEM_VALUES = frozenset({
    "0", "false", "no", "n", "user", "user_app", "userapp", "third-party", "third_party", "thirdparty",
})
DEFINITE_SYSTEM_PREFIXES = (
    "com.android.", "com.google.android.overlay.", "com.google.android.providers.",
    "com.google.android.permissioncontroller", "com.google.android.modulemetadata",
    "com.google.android.ext.", "com.google.android.networkstack",
    "com.google.android.adservices.api",
    "com.google.android.ondevicepersonalization.services",
)
DEFINITE_SYSTEM_PACKAGES = frozenset({
    "android", "com.google.android.packageinstaller", "com.google.android.documentsui",
    "com.google.android.settings.intelligence", "com.google.android.cellbroadcastreceiver",
    "com.google.android.cellbroadcastservice", "com.google.android.connectivity.resources",
})


def normalise_header(value: str) -> str:
    return "".join(
        character for character in value.strip().lower().replace(" ", "_").replace("-", "_")
        if character.isalnum() or character == "_"
    )


def parse_bool(value: str) -> bool | None:
    normalised = value.strip().lower()
    if normalised in TRUE_SYSTEM_VALUES:
        return True
    if normalised in FALSE_SYSTEM_VALUES:
        return False
    return None


def is_definite_system_package(package_name: str) -> bool:
    return package_name in DEFINITE_SYSTEM_PACKAGES or any(
        package_name.startswith(prefix) for prefix in DEFINITE_SYSTEM_PREFIXES
    )


def read_system_metadata(path: str | Path, apps: list[dict[str, str]]) -> dict[str, bool]:
    file_path = Path(path)
    if file_path.suffix.lower() not in {".csv", ".tsv"}:
        return {}
    raw = file_path.read_text(encoding="utf-8-sig", errors="replace")
    if not raw.strip():
        return {}
    try:
        delimiter = csv.Sniffer().sniff(raw[:5000], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","
    reader = csv.DictReader(raw.splitlines(), delimiter=delimiter)
    normalised = {
        normalise_header(name): name for name in reader.fieldnames or () if name is not None
    }
    package_column = next(
        (original for name, original in normalised.items() if name in PACKAGE_COLUMN_NAMES), None
    )
    system_column = next(
        (original for name, original in normalised.items() if name in SYSTEM_COLUMN_NAMES), None
    )
    if not package_column or not system_column:
        return {}
    valid_packages = {app["package_name"] for app in apps}
    metadata: dict[str, bool] = {}
    for row in reader:
        package_name = (row.get(package_column) or "").strip()
        if package_name not in valid_packages:
            continue
        value = parse_bool(row.get(system_column) or "")
        if value is not None:
            metadata[package_name] = value
    return metadata


def classify_packages(
    apps: list[dict[str, str]], metadata: dict[str, bool],
    *, exact_system: set[str] | None = None,
) -> set[str]:
    system = {package for package, is_system in metadata.items() if is_system}
    known_user = {package for package, is_system in metadata.items() if not is_system}
    if exact_system is not None:
        system.update(exact_system)
    else:
        for app in apps:
            package = app["package_name"]
            if package not in system and package not in known_user and is_definite_system_package(package):
                system.add(package)
    return system.intersection(app["package_name"] for app in apps)
