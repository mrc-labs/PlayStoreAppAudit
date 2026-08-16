from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "playstore_app_audit/services/device_insights.py"
TEST = ROOT / "tests/test_adb_bulk_metadata.py"

text = SERVICE.read_text(encoding="utf-8")

helper_marker = "\n\ndef compatibility_label(target_sdk: object, device_sdk: object) -> str:\n"
helpers = r'''

def _extract_bulk_package_blocks(text: str, wanted: set[str] | None = None) -> dict[str, str]:
    """Extract package sections from one ``dumpsys package`` response.

    Android's own CTS utilities parse the Packages section from the same bulk
    command. Keep this deliberately defensive: if the section shape is not
    recognised the caller simply falls back to per-package dumpsys calls.
    """
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    section_match = re.search(r"(?m)^[ \t]*Packages:[ \t]*$", normalized)
    if not section_match:
        return {}
    tail = normalized[section_match.end() :].lstrip("\n")
    section = re.split(r"\n[ \t]*\n", tail, maxsplit=1)[0]
    header = re.compile(r"(?m)^[ \t]{2}Package \[([^\]]+)\][^\n]*$")
    matches = list(header.finditer(section))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        package = match.group(1).strip()
        if wanted is not None and package not in wanted:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        blocks[package] = section[match.start() : end].rstrip()
    return blocks


def _metadata_is_usable(info: dict[str, str]) -> bool:
    return any(
        str(info.get(key) or "").strip()
        for key in (
            "installed_version_code",
            "installed_version",
            "target_sdk",
            "first_install_time",
            "last_local_update",
        )
    )
'''
if helper_marker not in text:
    raise RuntimeError("Could not find helper insertion point")
text = text.replace(helper_marker, helpers + helper_marker, 1)

pattern = re.compile(
    r'''    metadata: dict\[str, dict\[str, str\]\] = \{\}\n\n'''
    r'''    def read_one\(package: str\) -> tuple\[str, dict\[str, str\]\]:\n'''
    r'''.*?'''
    r'''    return metadata\n''',
    re.DOTALL,
)
replacement = r'''    metadata: dict[str, dict[str, str]] = {}

    # Fast path: one PackageManager dump for the entire inventory. This avoids
    # starting hundreds of separate adb/dumpsys processes on larger phones.
    # Any package whose block is missing or does not contain usable metadata is
    # handled by the proven per-package fallback below.
    try:
        cancelled = cancel_event is not None and cancel_event.is_set()
        if not cancelled:
            bulk_dump = _run(adb, ["shell", "dumpsys", "package"], 60)
            blocks = _extract_bulk_package_blocks(bulk_dump, set(packages))
            for package, dump in blocks.items():
                info = _parse_package_dump(dump, package in disabled, device_sdk, include_permissions)
                if not _metadata_is_usable(info):
                    continue
                info["installer_source"] = v8._friendly_installer(installer_map.get(package, ""))
                metadata[package] = info
    except Exception:
        # Bulk dumps differ across Android/OEM versions. Falling back is a
        # correctness feature, not an error condition.
        pass

    remaining = [package for package in packages if package not in metadata]
    if cancel_event is not None and cancel_event.is_set():
        return metadata

    def read_one(package: str) -> tuple[str, dict[str, str]]:
        if cancel_event is not None and cancel_event.is_set():
            return package, {}
        try:
            dump = _run(adb, ["shell", "dumpsys", "package", package], 30)
            info = _parse_package_dump(dump, package in disabled, device_sdk, include_permissions)
        except Exception:
            info = {
                "installed_version": "",
                "installed_version_code": "",
                "target_sdk": "",
                "min_sdk": "",
                "first_install_time": "",
                "last_local_update": "",
                "app_enabled": "Unknown",
                "compatibility_status": "Unknown",
                "sensitive_permissions_count": "" if not include_permissions else "0",
                "sensitive_permissions": "",
            }
        info["installer_source"] = v8._friendly_installer(installer_map.get(package, ""))
        return package, info

    if not remaining:
        return metadata

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 8))) as executor:
        futures = {executor.submit(read_one, package): package for package in remaining}
        for future in as_completed(futures):
            if cancel_event is not None and cancel_event.is_set():
                for pending in futures:
                    pending.cancel()
                break
            package, info = future.result()
            metadata[package] = info
    return metadata
'''
updated, count = pattern.subn(lambda _match: replacement, text, count=1)
if count != 1:
    raise RuntimeError(f"Expected one metadata collector block, found {count}")
SERVICE.write_text(updated, encoding="utf-8")

TEST.write_text(
    r'''from __future__ import annotations

import playstore_app_audit.services.device_insights as insights


BULK_DUMP = """Packages:
  Package [com.example.one] (abc123):
    versionCode=101 minSdk=26 targetSdk=35
    versionName=1.0.1
    firstInstallTime=2026-01-01 10:00:00
    lastUpdateTime=2026-08-01 11:00:00
    requested permissions:
      android.permission.CAMERA
  Package [com.example.two] (def456):
    versionCode=202 minSdk=24 targetSdk=32
    versionName=2.0.2
    firstInstallTime=2025-01-01 10:00:00
    lastUpdateTime=2026-07-01 11:00:00

Queries:
  system apps query data
"""


def test_extract_bulk_package_blocks_is_scoped_to_packages_section() -> None:
    blocks = insights._extract_bulk_package_blocks(BULK_DUMP, {"com.example.one", "com.example.two"})
    assert set(blocks) == {"com.example.one", "com.example.two"}
    assert "versionCode=101" in blocks["com.example.one"]
    assert "Queries:" not in blocks["com.example.two"]


def test_bulk_metadata_avoids_per_package_dumpsys(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(insights.user_state, "load_settings", lambda: {"permissions_audit_enabled": True})

    def fake_run(adb: str, args: list[str], timeout: int = 30) -> str:
        calls.append(tuple(args))
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args == ["shell", "pm", "list", "packages", "-d"]:
            return "package:com.example.two\n"
        if args == ["shell", "pm", "list", "packages", "-i"]:
            return (
                "package:com.example.one installer=com.android.vending\n"
                "package:com.example.two installer=com.android.vending\n"
            )
        if args == ["shell", "dumpsys", "package"]:
            return BULK_DUMP
        raise AssertionError(f"Unexpected adb call: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)
    result = insights.collect_device_metadata_v9(
        "adb", ["com.example.one", "com.example.two"], max_workers=2
    )

    assert result["com.example.one"]["installed_version"] == "1.0.1"
    assert result["com.example.one"]["sensitive_permissions_count"] == "1"
    assert result["com.example.one"]["installer_source"].startswith("Google Play")
    assert result["com.example.two"]["app_enabled"] == "Disabled"
    assert result["com.example.two"]["compatibility_status"] == "Aging target"
    assert not [call for call in calls if len(call) == 4 and call[:3] == ("shell", "dumpsys", "package")]


def test_partial_bulk_dump_falls_back_only_for_missing_package(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    one_only = BULK_DUMP.replace(
        "  Package [com.example.two] (def456):\n"
        "    versionCode=202 minSdk=24 targetSdk=32\n"
        "    versionName=2.0.2\n"
        "    firstInstallTime=2025-01-01 10:00:00\n"
        "    lastUpdateTime=2026-07-01 11:00:00\n",
        "",
    )
    monkeypatch.setattr(insights.user_state, "load_settings", lambda: {"permissions_audit_enabled": False})

    def fake_run(adb: str, args: list[str], timeout: int = 30) -> str:
        calls.append(tuple(args))
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args == ["shell", "pm", "list", "packages", "-d"]:
            return ""
        if args == ["shell", "pm", "list", "packages", "-i"]:
            return ""
        if args == ["shell", "dumpsys", "package"]:
            return one_only
        if args == ["shell", "dumpsys", "package", "com.example.two"]:
            return "versionCode=303 minSdk=24 targetSdk=34\nversionName=3.0.3\n"
        if args == ["shell", "dumpsys", "package", "com.example.one"]:
            raise AssertionError("Bulk-covered package should not be queried again")
        raise AssertionError(f"Unexpected adb call: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)
    result = insights.collect_device_metadata_v9(
        "adb", ["com.example.one", "com.example.two"], max_workers=2
    )

    assert result["com.example.one"]["installed_version_code"] == "101"
    assert result["com.example.two"]["installed_version"] == "3.0.3"
    specific = [call for call in calls if len(call) == 4 and call[:3] == ("shell", "dumpsys", "package")]
    assert specific == [("shell", "dumpsys", "package", "com.example.two")]


def test_bulk_failure_preserves_per_package_fallback(monkeypatch) -> None:
    monkeypatch.setattr(insights.user_state, "load_settings", lambda: {"permissions_audit_enabled": False})
    per_package: list[str] = []

    def fake_run(adb: str, args: list[str], timeout: int = 30) -> str:
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args in (
            ["shell", "pm", "list", "packages", "-d"],
            ["shell", "pm", "list", "packages", "-i"],
        ):
            return ""
        if args == ["shell", "dumpsys", "package"]:
            raise RuntimeError("OEM bulk dump unavailable")
        if len(args) == 4 and args[:3] == ["shell", "dumpsys", "package"]:
            per_package.append(args[3])
            return f"versionCode=1 minSdk=23 targetSdk=35\nversionName={args[3]}\n"
        raise AssertionError(f"Unexpected adb call: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)
    result = insights.collect_device_metadata_v9("adb", ["pkg.one", "pkg.two"], max_workers=2)
    assert set(result) == {"pkg.one", "pkg.two"}
    assert set(per_package) == {"pkg.one", "pkg.two"}
''',
    encoding="utf-8",
)

print("ADB bulk metadata optimisation prepared.")
