from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state

CATEGORY_GOOGLE_PLAY = "google_play"
CATEGORY_ALTERNATIVE_STORE = "alternative_store"
CATEGORY_SIDELOADED = "sideloaded"
CATEGORY_UNKNOWN_PREINSTALLED = "unknown_or_preinstalled"
CATEGORY_OTHER = "other_installer"

INSTALLER_CATEGORIES = frozenset(
    {
        CATEGORY_GOOGLE_PLAY,
        CATEGORY_ALTERNATIVE_STORE,
        CATEGORY_SIDELOADED,
        CATEGORY_UNKNOWN_PREINSTALLED,
        CATEGORY_OTHER,
    }
)

_GOOGLE_PLAY_INSTALLERS = {
    "com.android.vending": "Google Play",
}

_ALTERNATIVE_STORE_INSTALLERS = {
    "com.sec.android.app.samsungapps": "Galaxy Store",
    "com.amazon.venezia": "Amazon Appstore",
    "com.huawei.appmarket": "Huawei AppGallery",
    "com.xiaomi.mipicks": "Xiaomi GetApps",
    "com.xiaomi.market": "Xiaomi App Store",
    "com.oppo.market": "OPPO App Market",
    "com.heytap.market": "HeyTap App Market",
    "com.bbk.appstore": "vivo App Store",
    "com.vivo.appstore": "vivo App Store",
    "org.fdroid.fdroid": "F-Droid",
    "com.aurora.store": "Aurora Store",
    "com.apkpure.aegon": "APKPure",
}

_SIDELOAD_INSTALLERS = {
    "com.android.packageinstaller": "Sideload / package installer",
    "com.google.android.packageinstaller": "Sideload / package installer",
    "com.samsung.android.packageinstaller": "Sideload / package installer",
}

CATEGORY_LABELS = {
    CATEGORY_GOOGLE_PLAY: "Google Play",
    CATEGORY_ALTERNATIVE_STORE: "Alternative store",
    CATEGORY_SIDELOADED: "Sideloaded",
    CATEGORY_UNKNOWN_PREINSTALLED: "Unknown / preinstalled",
    CATEGORY_OTHER: "Other installer",
}

FILTER_PRESETS = (
    "Google Play",
    "Alternative stores",
    "Sideloaded",
    "Unknown / preinstalled",
    "Other installers",
)

_CAPTURE_LOCK = threading.Lock()
_LAST_INSTALLER_MAP: dict[str, str] = {}
_INSTALLED = False


@dataclass(frozen=True, slots=True)
class InstallerSource:
    package: str
    category: str
    label: str


def _normalise_package(value: object) -> str:
    package = str(value or "").strip()
    if package.casefold() in {"", "null", "none", "undefined"}:
        return ""
    return package


def classify_installer_package(value: object) -> InstallerSource:
    """Classify an installer from the exact package reported by PackageManager.

    Unknown package names are deliberately kept as `other_installer` rather than
    guessed from substrings. An empty installer remains observationally ambiguous:
    Android may be reporting a preinstalled app or simply no installer source.
    """
    package = _normalise_package(value)
    if not package:
        return InstallerSource("", CATEGORY_UNKNOWN_PREINSTALLED, "Unknown / preinstalled")
    if package in _GOOGLE_PLAY_INSTALLERS:
        return InstallerSource(
            package,
            CATEGORY_GOOGLE_PLAY,
            f"{_GOOGLE_PLAY_INSTALLERS[package]} ({package})",
        )
    if package in _ALTERNATIVE_STORE_INSTALLERS:
        return InstallerSource(
            package,
            CATEGORY_ALTERNATIVE_STORE,
            f"{_ALTERNATIVE_STORE_INSTALLERS[package]} ({package})",
        )
    if package in _SIDELOAD_INSTALLERS:
        return InstallerSource(
            package,
            CATEGORY_SIDELOADED,
            f"{_SIDELOAD_INSTALLERS[package]} ({package})",
        )
    return InstallerSource(package, CATEGORY_OTHER, package)


def installer_fields(value: object) -> dict[str, str]:
    source = classify_installer_package(value)
    return {
        "installer_source": source.label,
        "installer_package": source.package,
        "installer_category": source.category,
    }


def _legacy_display_category(value: object) -> str:
    """Recognise only exact display formats emitted by pre-v1.7 builds."""
    source = str(value or "").strip()
    if source == "Unknown / preinstalled":
        return CATEGORY_UNKNOWN_PREINSTALLED
    if source == "Sideload / package installer" or source.startswith(
        "Sideload / package installer ("
    ):
        return CATEGORY_SIDELOADED
    if source == "Google Play" or source.startswith("Google Play ("):
        return CATEGORY_GOOGLE_PLAY
    for label in _ALTERNATIVE_STORE_INSTALLERS.values():
        if source == label or source.startswith(f"{label} ("):
            return CATEGORY_ALTERNATIVE_STORE
    return ""


def installer_category(row: dict[str, Any]) -> str:
    """Return the structured category, with exact-format legacy compatibility."""
    category = str(row.get("installer_category") or "").strip()
    if category in INSTALLER_CATEGORIES:
        return category
    package = _normalise_package(row.get("installer_package"))
    if package:
        return classify_installer_package(package).category
    return _legacy_display_category(row.get("installer_source"))


def _remember_installer_map(mapping: dict[str, str]) -> None:
    global _LAST_INSTALLER_MAP
    with _CAPTURE_LOCK:
        _LAST_INSTALLER_MAP = dict(mapping)


def _clear_installer_map() -> None:
    _remember_installer_map({})


def _installer_map_snapshot() -> dict[str, str]:
    with _CAPTURE_LOCK:
        return dict(_LAST_INSTALLER_MAP)


def _enrich_metadata(
    metadata: dict[str, dict[str, str]],
    packages: list[str],
    installer_map: dict[str, str],
) -> dict[str, dict[str, str]]:
    for package in packages:
        info = metadata.get(package)
        if info is None:
            continue
        info.update(installer_fields(installer_map.get(package, "")))
    return metadata


def _extend_builtin_filters() -> None:
    existing = tuple(device_insights.BUILTIN_FILTERS)
    if all(name in existing for name in FILTER_PRESETS):
        return
    anchor = existing.index("Version mismatch") if "Version mismatch" in existing else len(existing)
    prefix = [name for name in existing[:anchor] if name not in FILTER_PRESETS]
    suffix = [name for name in existing[anchor:] if name not in FILTER_PRESETS]
    device_insights.BUILTIN_FILTERS = tuple(prefix + list(FILTER_PRESETS) + suffix)


def _install_filter_policy() -> None:
    original = device_insights.row_matches_filter

    def structured_row_matches_filter(row: dict[str, Any], preset: str) -> bool:
        category = installer_category(row)
        if preset == "Google Play":
            return category == CATEGORY_GOOGLE_PLAY
        if preset == "Alternative stores":
            return category == CATEGORY_ALTERNATIVE_STORE
        if preset == "Sideloaded":
            return category == CATEGORY_SIDELOADED
        if preset == "Unknown / preinstalled":
            return category == CATEGORY_UNKNOWN_PREINSTALLED
        if preset == "Other installers":
            return category == CATEGORY_OTHER
        return original(row, preset)

    device_insights.row_matches_filter = structured_row_matches_filter


def _install_installer_map_capture() -> None:
    original = device_metadata._parse_installer_map

    def capturing_parser(output: str) -> dict[str, str]:
        mapping = original(output)
        _remember_installer_map(mapping)
        return mapping

    device_metadata._parse_installer_map = capturing_parser


def _install_collectors() -> None:
    original_legacy = device_metadata.collect_device_metadata
    original_v9 = device_insights.collect_device_metadata_v9

    def collect_legacy(
        adb: str,
        packages: list[str],
        cancel_event: threading.Event | None = None,
        max_workers: int = 6,
    ) -> dict[str, dict[str, str]]:
        _clear_installer_map()
        result = original_legacy(adb, packages, cancel_event, max_workers)
        return _enrich_metadata(result, packages, _installer_map_snapshot())

    def collect_v9(
        adb: str,
        packages: list[str],
        cancel_event=None,
        max_workers: int = 6,
    ) -> dict[str, dict[str, str]]:
        _clear_installer_map()
        result = original_v9(adb, packages, cancel_event, max_workers)
        return _enrich_metadata(result, packages, _installer_map_snapshot())

    device_metadata.collect_device_metadata = collect_legacy
    device_insights.collect_device_metadata_v9 = collect_v9


def _copy_structured_installer_fields(
    rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]
) -> None:
    for row in rows:
        package = str(row.get("package_name") or "")
        info = metadata.get(package, {})
        for key in ("installer_source", "installer_package", "installer_category"):
            row[key] = info.get(key, "")


def _install_row_enrichment() -> None:
    original_legacy = device_metadata.enrich_rows_with_device_metadata
    original_v9 = device_insights.enrich_rows_with_device_metadata_v9

    def enrich_legacy(
        rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]
    ) -> None:
        original_legacy(rows, metadata)
        _copy_structured_installer_fields(rows, metadata)

    def enrich_v9(
        rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]
    ) -> None:
        original_v9(rows, metadata)
        _copy_structured_installer_fields(rows, metadata)

    device_metadata.enrich_rows_with_device_metadata = enrich_legacy
    device_insights.enrich_rows_with_device_metadata_v9 = enrich_v9


def _install_snapshot_fidelity() -> None:
    original = device_insights.make_device_snapshot

    def make_snapshot(
        rows: list[dict[str, Any]], device_summary: dict[str, Any]
    ) -> dict[str, Any]:
        snapshot = original(rows, device_summary)
        current = {str(row.get("package_name") or ""): row for row in rows}
        apps = snapshot.get("apps")
        if isinstance(apps, list):
            for item in apps:
                if not isinstance(item, dict):
                    continue
                row = current.get(str(item.get("package_name") or ""), {})
                item["installer_package"] = row.get("installer_package", "")
                item["installer_category"] = row.get("installer_category", "")
        return snapshot

    device_insights.make_device_snapshot = make_snapshot


def install_installer_source_extensions() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    _extend_builtin_filters()
    state.TECHNICAL_COLUMNS.setdefault("installer_category", "Installer category")
    state.TECHNICAL_COLUMNS.setdefault("installer_package", "Installer package")

    _install_filter_policy()
    _install_installer_map_capture()
    _install_collectors()
    _install_row_enrichment()
    _install_snapshot_fidelity()

    # Keep the existing friendly-label API stable for callers and tests while
    # making it use the same exact-package classification table.
    device_metadata._friendly_installer = lambda package: classify_installer_package(package).label
    _INSTALLED = True
