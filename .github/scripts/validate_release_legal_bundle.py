#!/usr/bin/env python3
"""Validate Play Store App Audit legal-release material against a standalone package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from prepare_release_legal_bundle import (
    LEGAL_ROOT_DIRS,
    LEGAL_ROOT_FILES,
    MANIFEST_SCHEMA_VERSION,
    _canonical_json_sha256,
    _forbidden_matches,
    _normalize_dist_name,
    _runtime_inventory,
    _sha256,
)

ABSOLUTE_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
ABSOLUTE_USER_PATH_RE = re.compile(r"(?:^|[\\/])(?:Users|home)[\\/]", re.IGNORECASE)
REQUIRED_PACKAGE_FILES = {
    "LICENSE",
    "COMMERCIAL-LICENSING.md",
    "LICENSING.md",
    "THIRD_PARTY_NOTICES.md",
    "SOURCE-AVAILABILITY.md",
    "LEGAL-MANIFEST.json",
}
REQUIRED_QT_COMMUNITY_LICENSES = {
    "licenses/qt/pyside-setup/LGPL-3.0-only.txt",
    "licenses/qt/pyside-setup/GPL-2.0-only.txt",
    "licenses/qt/pyside-setup/GPL-3.0-only.txt",
    "licenses/qt/pyside-setup/Qt-GPL-exception-1.0.txt",
}
QT_PYTHON_DISTS = {"pyside6-essentials", "shiboken6"}


class ValidationError(RuntimeError):
    pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument(
        "--public",
        action="store_true",
        help="Require complete corresponding-source staging suitable for a public release candidate.",
    )
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Unable to parse JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"Expected JSON object in {path}")
    return value


def _walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if isinstance(value, str):
        result.append((path, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            result.extend(_walk_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(_walk_strings(item, f"{path}[{index}]"))
    return result


def _validate_portable_manifest(manifest: dict[str, Any]) -> None:
    for json_path, value in _walk_strings(manifest):
        if ABSOLUTE_WINDOWS_PATH_RE.match(value) or ABSOLUTE_USER_PATH_RE.search(value):
            raise ValidationError(f"Manifest contains an absolute/local user path at {json_path}: {value}")
        if "\\" in value and not value.startswith("https://"):
            raise ValidationError(f"Manifest path/value is not portable POSIX-style text at {json_path}: {value}")


def _validate_required_files(package_dir: Path, package_legal_dir: Path) -> None:
    for name in sorted(REQUIRED_PACKAGE_FILES):
        package_path = package_dir / name
        staged_path = package_legal_dir / name
        _require(package_path.is_file(), f"Package legal file missing: {name}")
        _require(staged_path.is_file(), f"Staged package legal file missing: {name}")
        _require(
            package_path.read_bytes() == staged_path.read_bytes(),
            f"Package/staged legal file mismatch: {name}",
        )
    _require((package_dir / "licenses").is_dir(), "Package licenses/ directory is missing")
    _require((package_legal_dir / "licenses").is_dir(), "Staged licenses/ directory is missing")


def _validate_markdown_paths(package_dir: Path) -> None:
    for name in ("LICENSING.md", "THIRD_PARTY_NOTICES.md", "SOURCE-AVAILABILITY.md"):
        text = (package_dir / name).read_text(encoding="utf-8")
        _require("](../" not in text and "](..\\" not in text, f"Broken parent-relative link found in {name}")
        _require("SOURCE-OFFER.md" not in text, f"Obsolete SOURCE-OFFER.md reference found in {name}")


def _validate_runtime_inventory(package_dir: Path, manifest: dict[str, Any]) -> None:
    package = manifest.get("package")
    _require(isinstance(package, dict), "Manifest package object is missing")
    recorded = package.get("runtime_inventory")
    _require(isinstance(recorded, list), "Manifest runtime_inventory is missing")
    current = _runtime_inventory(package_dir)
    _require(recorded == current, "Runtime payload inventory differs from LEGAL-MANIFEST.json")
    _require(
        package.get("runtime_file_count") == len(current),
        "runtime_file_count does not match runtime_inventory",
    )
    expected_digest = _canonical_json_sha256(current)
    _require(
        package.get("runtime_inventory_sha256") == expected_digest,
        "runtime_inventory_sha256 does not match the canonical runtime inventory",
    )
    _require(
        package.get("directory_name") == package_dir.name,
        "Manifest package directory_name does not match the package directory",
    )


def _validate_forbidden_runtime(package_dir: Path, manifest: dict[str, Any]) -> None:
    matches = _forbidden_matches(package_dir)
    _require(not matches, f"Forbidden runtime components detected: {matches}")
    adb_files = [
        path
        for path in package_dir.rglob("*")
        if path.is_file() and path.name.casefold() in {"adb.exe", "adbwinapi.dll", "adbwinusbapi.dll"}
    ]
    _require(not adb_files, f"Android Platform-Tools files are unexpectedly bundled: {adb_files}")
    policy = manifest.get("policy")
    _require(isinstance(policy, dict), "Manifest policy object is missing")
    _require(policy.get("forbidden_runtime_matches") == [], "Manifest must record no forbidden runtime matches")
    _require(policy.get("adb_bundled") is False, "Manifest must record adb_bundled=false")
    _require(
        policy.get("final_msvc_revalidation_required") is True,
        "Manifest must preserve final MSVC revalidation requirement",
    )


def _validate_qt_license_mapping(package_dir: Path, manifest: dict[str, Any]) -> None:
    for rel in sorted(REQUIRED_QT_COMMUNITY_LICENSES):
        _require((package_dir / PurePosixPath(rel)).is_file(), f"Required Qt community license missing: {rel}")

    qt = manifest.get("qt")
    _require(isinstance(qt, dict), "Manifest qt object is missing")
    _require(qt.get("distribution_basis") == "LGPL-3.0-only", "Qt distribution basis must be LGPL-3.0-only")
    declared = set(qt.get("community_license_files") or [])
    _require(
        REQUIRED_QT_COMMUNITY_LICENSES.issubset(declared),
        "Qt community_license_files does not explicitly map LGPL/GPL community license texts",
    )

    dependencies = manifest.get("runtime_dependencies")
    _require(isinstance(dependencies, list), "Manifest runtime_dependencies is missing")
    qt_python_seen: set[str] = set()
    for item in dependencies:
        _require(isinstance(item, dict), "runtime_dependencies contains a non-object entry")
        normalized = _normalize_dist_name(str(item.get("name", "")))
        if normalized not in QT_PYTHON_DISTS:
            continue
        qt_python_seen.add(normalized)
        _require(
            item.get("distribution_license_basis") == "LGPL-3.0-only",
            f"{item.get('name')} must explicitly use LGPL-3.0-only as distribution basis",
        )
        license_files = set(item.get("license_files") or [])
        _require(
            REQUIRED_QT_COMMUNITY_LICENSES.issubset(license_files),
            f"{item.get('name')} must map to the community LGPL/GPL license texts",
        )
        _require(
            all("LicenseRef-Qt-Commercial" not in path for path in license_files),
            f"{item.get('name')} presents the commercial reference as a distribution license",
        )
    _require(qt_python_seen == QT_PYTHON_DISTS, "PySide6_Essentials and shiboken6 must both be inventoried")

    notices = (package_dir / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    _require("Distribution basis" in notices, "Third-party notices must state the Qt distribution basis")
    _require("LGPL library replacement" in notices, "Third-party notices must include LGPL replacement instructions")
    _require(
        "is not the license basis used for this package" in notices,
        "Commercial Qt reference must be clearly distinguished from the community distribution basis",
    )


def _iter_attribution_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise ValidationError("Qt attribution JSON must contain an object or a list of objects")


def _validate_qt_attributions(package_dir: Path, manifest: dict[str, Any]) -> None:
    qt = manifest["qt"]
    attribution_paths = qt.get("attribution_files")
    _require(isinstance(attribution_paths, list) and attribution_paths, "Qt attribution_files must be non-empty")

    mappings = qt.get("attribution_license_mappings")
    _require(isinstance(mappings, list), "Qt attribution_license_mappings must be a list")
    mapping_index: dict[tuple[str, int, str], dict[str, Any]] = {}
    for mapping in mappings:
        _require(isinstance(mapping, dict), "Qt attribution license mapping must be an object")
        key = (
            str(mapping.get("attribution_file", "")),
            int(mapping.get("record_index", -1)),
            str(mapping.get("reference", "")),
        )
        _require(
            all(key_part != "" for key_part in (key[0], key[2])) and key[1] >= 0,
            f"Malformed Qt attribution license mapping: {mapping}",
        )
        _require(key not in mapping_index, f"Duplicate Qt attribution license mapping: {key}")
        bundled_rel = mapping.get("bundled_file")
        _require(isinstance(bundled_rel, str), f"Qt attribution mapping lacks bundled_file: {mapping}")
        _require(
            (package_dir / PurePosixPath(bundled_rel)).is_file(),
            f"Qt attribution referenced license was not bundled: {bundled_rel}",
        )
        source_member = mapping.get("source_member")
        _require(
            isinstance(source_member, str) and "/" in source_member,
            f"Qt attribution mapping lacks source provenance: {mapping}",
        )
        mapping_index[key] = mapping

    total_records = 0
    expected_mapping_keys: set[tuple[str, int, str]] = set()
    for rel in attribution_paths:
        path = package_dir / PurePosixPath(rel)
        _require(path.is_file(), f"Qt attribution file missing: {rel}")
        # Qt upstream attribution metadata can contain literal control characters inside strings.
        data = json.loads(path.read_text(encoding="utf-8"), strict=False)
        records = _iter_attribution_objects(data)
        for record_index, record in enumerate(records):
            _require(
                any(key in record for key in ("Name", "Id", "Description")),
                f"Qt attribution lacks identity fields: {rel}",
            )
            _require(
                any(key in record for key in ("License", "LicenseId", "LicenseFile", "LicenseFiles")),
                f"Qt attribution lacks license fields: {rel}",
            )
            referenced = record.get("LicenseFile") or record.get("LicenseFiles")
            references = [referenced] if isinstance(referenced, str) else list(referenced or [])
            for reference in references:
                _require(
                    isinstance(reference, str) and reference.strip(),
                    f"Invalid Qt attribution license reference in {rel}",
                )
                key = (rel, record_index, reference)
                expected_mapping_keys.add(key)
                _require(
                    key in mapping_index,
                    f"Qt attribution referenced license is not mapped into the bundle: {key}",
                )
        total_records += len(records)

    _require(
        set(mapping_index) == expected_mapping_keys,
        "Qt attribution license mappings contain stale or missing entries",
    )
    _require(
        total_records == qt.get("attribution_record_count"),
        "Qt attribution_record_count does not match parsed raw attribution metadata",
    )

    declared_license_files = qt.get("attribution_license_files")
    _require(
        isinstance(declared_license_files, list),
        "Qt attribution_license_files must be a list",
    )
    mapped_license_files = sorted(
        {str(mapping["bundled_file"]) for mapping in mappings},
        key=str.casefold,
    )
    _require(
        declared_license_files == mapped_license_files,
        "Qt attribution_license_files does not match attribution license mappings",
    )

    human_rel = qt.get("human_readable_attributions")
    _require(isinstance(human_rel, str), "Qt human_readable_attributions path is missing")
    human_path = package_dir / PurePosixPath(human_rel)
    _require(human_path.is_file(), f"Human-readable Qt attribution output missing: {human_rel}")
    human_text = human_path.read_text(encoding="utf-8")
    _require(
        human_text.count("Source metadata:") == total_records,
        "Human-readable Qt attribution output does not cover every parsed attribution record",
    )
    for bundled_rel in mapped_license_files:
        _require(
            bundled_rel in human_text,
            f"Human-readable Qt attribution output omits bundled license path: {bundled_rel}",
        )

def _validate_nuitka_build_evidence(
    package_dir: Path,
    manifest: dict[str, Any],
) -> set[str]:
    nuitka = manifest.get("toolchain", {}).get("nuitka")
    _require(isinstance(nuitka, dict), "Manifest Nuitka metadata is missing")

    evidence_rel = nuitka.get("sanitized_evidence_file")
    _require(
        isinstance(evidence_rel, str) and evidence_rel,
        "Nuitka sanitized evidence path is missing",
    )

    evidence_path = package_dir / PurePosixPath(evidence_rel)
    _require(
        evidence_path.is_file(),
        f"Nuitka sanitized build evidence is missing: {evidence_rel}",
    )

    expected_sha = nuitka.get("sanitized_evidence_sha256")
    _require(
        isinstance(expected_sha, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None,
        "Invalid Nuitka sanitized evidence SHA-256",
    )
    _require(
        _sha256(evidence_path) == expected_sha,
        "Nuitka sanitized evidence SHA-256 mismatch",
    )

    evidence = _read_json(evidence_path)
    _validate_portable_manifest(evidence)

    _require(
        evidence.get("schema_version") == 1,
        "Unsupported Nuitka build-evidence schema",
    )
    _require(
        evidence.get("source") == "Nuitka compilation report",
        "Unexpected Nuitka build-evidence source",
    )
    _require(
        evidence.get("nuitka_version") == nuitka.get("version"),
        "Nuitka build-evidence version mismatch",
    )
    _require(
        evidence.get("source_report_sha256")
        == nuitka.get("compilation_report_sha256"),
        "Nuitka compilation report SHA-256 provenance mismatch",
    )

    modules = evidence.get("modules")
    _require(
        isinstance(modules, list) and modules,
        "Nuitka build evidence contains no modules",
    )
    _require(
        evidence.get("module_count") == len(modules),
        "Nuitka build-evidence module_count mismatch",
    )

    module_names: set[str] = set()

    for item in modules:
        _require(
            isinstance(item, dict),
            "Nuitka build evidence contains a non-object module",
        )

        name = item.get("name")
        kind = item.get("kind")

        _require(
            isinstance(name, str) and name,
            "Nuitka build evidence contains an invalid module name",
        )
        _require(
            isinstance(kind, str),
            f"Nuitka build evidence contains invalid kind for {name}",
        )
        _require(
            "\\" not in name
            and "/" not in name
            and ":" not in name,
            f"Nuitka build evidence contains path-like module name: {name}",
        )
        _require(
            name not in module_names,
            f"Duplicate Nuitka build-evidence module: {name}",
        )

        module_names.add(name)

    return module_names


def _validate_dependency_evidence(
    package_dir: Path,
    manifest: dict[str, Any],
    compiled_modules: set[str],
) -> None:
    existing = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file()
    }

    for item in manifest["runtime_dependencies"]:
        name = item.get("name")

        file_evidence = item.get("runtime_evidence")
        compiled_evidence = item.get("nuitka_compiled_modules")

        _require(
            isinstance(file_evidence, list),
            f"Invalid file-backed runtime evidence for dependency {name}",
        )
        _require(
            isinstance(compiled_evidence, list),
            f"Invalid Nuitka compiled evidence for dependency {name}",
        )
        _require(
            file_evidence or compiled_evidence,
            f"No runtime evidence for dependency {name}",
        )

        for rel in file_evidence:
            _require(
                rel in existing,
                f"Runtime evidence path for {name} is missing: {rel}",
            )

        top_levels = item.get("top_level_names")
        _require(
            isinstance(top_levels, list) and top_levels,
            f"Missing top-level package names for dependency {name}",
        )

        for module_name in compiled_evidence:
            _require(
                module_name in compiled_modules,
                f"Nuitka compiled-module evidence for {name} is absent "
                f"from sanitized build evidence: {module_name}",
            )

            _require(
                any(
                    module_name == top
                    or module_name.startswith(top + ".")
                    for top in top_levels
                ),
                f"Nuitka module {module_name} does not belong to "
                f"dependency {name}",
            )

        for rel in item.get("license_files") or []:
            _require(
                (package_dir / PurePosixPath(rel)).is_file(),
                f"Dependency license file missing: {rel}",
            )


def _validate_openssl(package_dir: Path, manifest: dict[str, Any]) -> None:
    runtime_openssl = sorted(
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file()
        and path.name.casefold().startswith(("libssl-", "libcrypto-"))
        and path.suffix.casefold() == ".dll"
    )
    openssl = manifest.get("toolchain", {}).get("openssl")
    if runtime_openssl:
        _require(isinstance(openssl, dict), "OpenSSL DLLs are packaged but manifest OpenSSL metadata is missing")
        _require(
            sorted(openssl.get("runtime_files") or []) == runtime_openssl,
            "OpenSSL manifest runtime_files do not match packaged DLLs",
        )
        license_rel = openssl.get("license_file")
        _require(isinstance(license_rel, str), "OpenSSL license path is missing")
        _require((package_dir / PurePosixPath(license_rel)).is_file(), f"OpenSSL license missing: {license_rel}")
    else:
        _require(openssl is None, "Manifest declares OpenSSL although no OpenSSL DLLs are packaged")


def _parse_sha256s(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        _require(len(parts) == 2, f"Malformed SHA256SUMS line: {line}")
        digest, filename = parts[0].lower(), parts[1].strip().lstrip("*")
        _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"Invalid SHA-256 in SHA256SUMS: {line}")
        _require(filename not in result, f"Duplicate SHA256SUMS entry: {filename}")
        result[filename] = digest
    return result


def _validate_source_assets(release_dir: Path, package_dir: Path, manifest: dict[str, Any], public: bool) -> None:
    source_assets_dir = release_dir / "source-assets"
    if not public:
        return
    _require(source_assets_dir.is_dir(), "Public validation requires release-dir/source-assets")
    sums_path = source_assets_dir / "SHA256SUMS.txt"
    _require(sums_path.is_file(), "Public validation requires source-assets/SHA256SUMS.txt")
    sums = _parse_sha256s(sums_path)
    declared = manifest.get("source_assets")
    _require(isinstance(declared, list) and declared, "Manifest source_assets must be non-empty")
    declared_names = {item["filename"] for item in declared}
    _require(set(sums) == declared_names, "SHA256SUMS entries do not exactly match manifest source assets")

    for item in declared:
        filename = item["filename"]
        path = source_assets_dir / filename
        _require(path.is_file(), f"Required corresponding-source asset missing: {filename}")
        actual = _sha256(path)
        _require(actual == item["sha256"], f"Source asset SHA-256 mismatch: {filename}")
        _require(sums[filename] == item["sha256"], f"SHA256SUMS mismatch: {filename}")
        _require(path.stat().st_size == item["size"], f"Source asset size mismatch: {filename}")
        _require(str(item.get("download_url", "")).startswith("https://"), f"Missing HTTPS provenance: {filename}")
        _require(str(item.get("provenance_url", "")).startswith("https://"), f"Missing provenance URL: {filename}")

    certifi_assets = [item for item in declared if item.get("component") == "certifi"]
    _require(len(certifi_assets) == 1, "Exactly one certifi source asset is required")
    certifi_asset = certifi_assets[0]
    _require(certifi_asset["filename"].endswith(".tar.gz"), "certifi must use the official PyPI source distribution")
    _require(
        "pypi.org/pypi/certifi/" in certifi_asset["provenance_url"],
        "certifi provenance must be the PyPI release JSON",
    )

    availability = (package_dir / "SOURCE-AVAILABILITY.md").read_text(encoding="utf-8")
    for item in declared:
        _require(item["filename"] in availability, f"SOURCE-AVAILABILITY.md omits {item['filename']}")
        _require(item["sha256"] in availability, f"SOURCE-AVAILABILITY.md omits SHA-256 for {item['filename']}")

    actual_files = {
        path.name
        for path in source_assets_dir.iterdir()
        if path.is_file() and path.name != "SHA256SUMS.txt"
    }
    _require(actual_files == declared_names, "source-assets contains unlisted or missing release assets")


def _validate_staged_tree(package_dir: Path, package_legal_dir: Path) -> None:
    package_legal_files = {
        path.relative_to(package_legal_dir).as_posix(): _sha256(path)
        for path in package_legal_dir.rglob("*")
        if path.is_file()
    }
    for rel, digest in package_legal_files.items():
        package_path = package_dir / PurePosixPath(rel)
        _require(package_path.is_file(), f"Generated package legal file was not injected: {rel}")
        _require(_sha256(package_path) == digest, f"Injected package legal file differs from staging: {rel}")


def _validate_legal_scope(package_dir: Path) -> None:
    for path in package_dir.iterdir():
        if path.name in LEGAL_ROOT_FILES or path.name in LEGAL_ROOT_DIRS:
            continue
    review_artifacts = [
        path
        for path in package_dir.rglob("*")
        if path.is_file() and path.name.casefold() == "legal-bundle-review.txt"
    ]
    _require(not review_artifacts, "LEGAL-BUNDLE-REVIEW.txt is an engineering review artifact and must not ship")


def main() -> int:
    args = _parse_args()
    package_dir = args.package_dir.resolve()
    release_dir = args.release_dir.resolve()
    package_legal_dir = release_dir / "package-legal"

    _require(package_dir.is_dir(), f"Package directory does not exist: {package_dir}")
    _require(package_legal_dir.is_dir(), f"Package legal staging does not exist: {package_legal_dir}")
    _validate_required_files(package_dir, package_legal_dir)
    _validate_staged_tree(package_dir, package_legal_dir)

    manifest_path = package_dir / "LEGAL-MANIFEST.json"
    manifest = _read_json(manifest_path)
    staged_manifest = _read_json(package_legal_dir / "LEGAL-MANIFEST.json")
    _require(manifest == staged_manifest, "Injected/staged LEGAL-MANIFEST.json objects differ")
    _require(manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION, "Unsupported legal manifest schema")
    _validate_portable_manifest(manifest)
    _validate_markdown_paths(package_dir)
    _validate_runtime_inventory(package_dir, manifest)
    _validate_forbidden_runtime(package_dir, manifest)
    _validate_qt_license_mapping(package_dir, manifest)
    _validate_qt_attributions(package_dir, manifest)
    compiled_modules = _validate_nuitka_build_evidence(
        package_dir,
        manifest,
    )
    _validate_dependency_evidence(
        package_dir,
        manifest,
        compiled_modules,
    )
    _validate_openssl(package_dir, manifest)
    _validate_source_assets(release_dir, package_dir, manifest, args.public)
    _validate_legal_scope(package_dir)

    if args.public:
        private_marker = package_dir / "PRIVATE-TEST-BUILD.txt"
        _require(
            not private_marker.exists(),
            "Public validation must reject PRIVATE-TEST-BUILD.txt",
        )

    application = manifest.get("application", {})
    expected_tag = f"v{application.get('version')}"
    _require(application.get("release_tag") == expected_tag, "Release tag must match canonical app version")
    policy = manifest["policy"]
    _require(
        policy.get("project_source_tag_must_exist_before_publication") is True,
        "Manifest must preserve project-source tag publication gate",
    )

    mode = "PUBLIC/STRICT" if args.public else "PACKAGE"
    print(f"Legal release validation PASS [{mode}]")
    print(f"Package: {package_dir.name}")
    print(f"Runtime payload files: {manifest['package']['runtime_file_count']}")
    print(f"Runtime inventory SHA-256: {manifest['package']['runtime_inventory_sha256']}")
    print(f"Qt attribution records: {manifest['qt']['attribution_record_count']}")
    if args.public:
        print(f"Corresponding-source assets: {len(manifest['source_assets'])}")
    print("Final public compliance still requires validation of the exact final-main MSVC artifact.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
