#!/usr/bin/env python3
"""Prepare legal material and corresponding-source assets for a Windows standalone release.

This script is intentionally project-specific. Run it with the same Python environment used
for the release build so dependency metadata and toolchain versions match the packaged runtime.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import http.client
import importlib.metadata as metadata
import json
import platform
import re
import shutil
import ssl
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import certifi
from legal_payload_store import store_canonical_legal_payload
from release_asset_layout import build_third_party_source_bundle

APP_NAME = "Play Store App Audit"
PROJECT_REPOSITORY = "https://github.com/mrc-labs/PlayStoreAppAudit"
PROJECT_LICENSE = "GPL-3.0-only"
MANIFEST_SCHEMA_VERSION = 3
RELEASE_PLATFORMS = {"windows", "linux", "macos"}


def _host_platform_key() -> str:
    system = platform.system().casefold()

    mapping = {
        "windows": "windows",
        "linux": "linux",
        "darwin": "macos",
    }

    try:
        return mapping[system]
    except KeyError as exc:
        raise RuntimeError(
            f"Unsupported release host platform: {platform.system()}"
        ) from exc


def _is_openssl_runtime_name(name: str) -> bool:
    name_cf = name.casefold()

    return (
        (
            name_cf.startswith(("libssl-", "libcrypto-"))
            and name_cf.endswith(".dll")
        )
        or name_cf.startswith(("libssl.so", "libcrypto.so"))
        or (
            name_cf.startswith(("libssl.", "libcrypto."))
            and name_cf.endswith(".dylib")
        )
    )

LEGAL_ROOT_FILES = {
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "SOURCE-AVAILABILITY.md",
    "LEGAL-MANIFEST.json",
}
LEGAL_ROOT_DIRS = {"licenses"}
LICENSE_FILE_RE = re.compile(r"^(?:licen[cs]e|copying|notice|authors?)(?:[._-].*)?$", re.IGNORECASE)
REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SHA256_PAGE_RE = re.compile(
    r"\bSHA\s*[-_ ]?\s*256(?:\s+Hash)?\b.{0,1024}?\b([0-9a-fA-F]{64})\b",
    re.DOTALL | re.IGNORECASE,
)
OPENSSL_VERSION_RE = re.compile(r"OpenSSL\s+([0-9]+\.[0-9]+\.[0-9]+)")

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


@dataclass(frozen=True)
class SourceAssetSpec:
    component: str
    filename: str
    url: str
    sha256: str
    provenance_url: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _posix(path: Path) -> str:
    return path.as_posix()


def _safe_relpath(path: Path, root: Path) -> str:
    return _posix(path.resolve().relative_to(root.resolve()))


def _open_url_with_retry(
    request: urllib.request.Request,
    *,
    timeout: int,
):
    retryable_statuses = {429, 500, 502, 503, 504}
    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        try:
            return urllib.request.urlopen(
                request,
                context=_SSL_CONTEXT,
                timeout=timeout,
            )
        except urllib.error.HTTPError as exc:
            if exc.code not in retryable_statuses or attempt == max_attempts:
                raise RuntimeError(
                    f"HTTP {exc.code} while fetching {request.full_url}"
                ) from exc

            retry_after = None
            if exc.headers is not None:
                retry_after = exc.headers.get("Retry-After")

            try:
                delay = float(retry_after) if retry_after is not None else None
            except ValueError:
                delay = None

            if delay is None:
                delay = min(2 ** (attempt - 1), 8)

            delay = max(0.0, min(delay, 30.0))

            print(
                f"HTTP {exc.code} while fetching {request.full_url}; "
                f"retrying after {delay:g}s "
                f"(attempt {attempt + 1}/{max_attempts})",
                file=sys.stderr,
            )
            time.sleep(delay)

        except urllib.error.URLError as exc:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Network error while fetching {request.full_url}: "
                    f"{exc.reason}"
                ) from exc

            delay = min(2 ** (attempt - 1), 8)

            print(
                f"Network error while fetching {request.full_url}; "
                f"retrying after {delay:g}s "
                f"(attempt {attempt + 1}/{max_attempts})",
                file=sys.stderr,
            )
            time.sleep(delay)

    raise RuntimeError(
        f"Unable to fetch URL after retries: {request.full_url}"
    )


_TEXT_DOWNLOAD_CACHE: dict[str, str] = {}


def _download_text(url: str) -> str:
    cached = _TEXT_DOWNLOAD_CACHE.get(url)
    if cached is not None:
        return cached

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PlayStoreAppAudit-release-tooling/1"},
    )
    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        try:
            with _open_url_with_retry(
                request,
                timeout=60,
            ) as response:
                text = response.read().decode("utf-8")
        except (
            OSError,
            http.client.IncompleteRead,
        ) as exc:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Network read error while fetching {url} "
                    f"after {max_attempts} attempts: {exc}"
                ) from exc

            delay = min(2 ** (attempt - 1), 8)

            print(
                f"Network read error while fetching {url}: {exc}; "
                f"retrying after {delay:g}s "
                f"(attempt {attempt + 1}/{max_attempts})",
                file=sys.stderr,
            )
            time.sleep(delay)
            continue

        _TEXT_DOWNLOAD_CACHE[url] = text
        return text

    raise RuntimeError(
        f"Unable to read URL after retries: {url}"
    )


def _download_file(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    if (
        destination.exists()
        and _sha256(destination) == expected_sha256
    ):
        print(
            f"Reusing verified source asset {destination.name}",
            file=sys.stderr,
        )
        return

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PlayStoreAppAudit-release-tooling/1"},
    )
    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        temp_path: Path | None = None
        read_error: BaseException | None = None

        try:
            print(
                f"Downloading source asset {destination.name} "
                f"from {url} "
                f"(attempt {attempt}/{max_attempts})",
                file=sys.stderr,
            )

            with _open_url_with_retry(
                request,
                timeout=120,
            ) as response, tempfile.NamedTemporaryFile(
                delete=False,
                dir=destination.parent,
                suffix=".download",
            ) as tmp:
                temp_path = Path(tmp.name)

                while True:
                    try:
                        chunk = response.read(1024 * 1024)
                    except (
                        OSError,
                        http.client.IncompleteRead,
                    ) as exc:
                        read_error = exc
                        break

                    if not chunk:
                        break

                    tmp.write(chunk)

            if read_error is not None:
                if attempt == max_attempts:
                    raise RuntimeError(
                        f"Network read error while downloading "
                        f"{destination.name} from {url} after "
                        f"{max_attempts} attempts: {read_error}"
                    ) from read_error

                delay = min(2 ** (attempt - 1), 8)

                print(
                    f"Network read error while downloading "
                    f"{destination.name} from {url}: {read_error}; "
                    f"discarding partial file and retrying after "
                    f"{delay:g}s "
                    f"(attempt {attempt + 1}/{max_attempts})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue

            if temp_path is None:
                raise RuntimeError(
                    f"No temporary download was created for "
                    f"{destination.name}"
                )

            actual = _sha256(temp_path)

            if actual != expected_sha256:
                raise RuntimeError(
                    f"SHA-256 mismatch for {destination.name}: "
                    f"expected {expected_sha256}, got {actual}"
                )

            temp_path.replace(destination)

            print(
                f"Verified source asset {destination.name}",
                file=sys.stderr,
            )
            return
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    raise RuntimeError(
        f"Unable to download source asset after retries: {url}"
    )


def _normalise_hash_type(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _extract_metalink_sha256(text: str) -> str | None:
    root = ET.fromstring(text)

    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1].casefold()
        if local_name != "hash":
            continue

        hash_type = _normalise_hash_type(
            element.attrib.get("type", "")
        )
        if hash_type != "sha256":
            continue

        for candidate in (
            element.text or "",
            element.attrib.get("value", ""),
            element.attrib.get("hash", ""),
        ):
            value = candidate.strip()
            if SHA256_HEX_RE.fullmatch(value):
                return value.lower()

    return None


def _extract_page_sha256(text: str) -> str | None:
    match = SHA256_PAGE_RE.search(text)
    if match is None:
        return None
    return match.group(1).lower()


def _qt_official_sha256(base_url: str) -> tuple[str, str]:
    errors: list[str] = []

    for suffix in (".meta4", ".metalink"):
        metalink_url = f"{base_url}{suffix}"
        try:
            metalink_text = _download_text(metalink_url)
            digest = _extract_metalink_sha256(metalink_text)

            if digest is not None:
                return digest, metalink_url

            errors.append(
                f"{metalink_url}: SHA-256 hash element not found"
            )
        except (
            ET.ParseError,
            OSError,
            RuntimeError,
            UnicodeDecodeError,
        ) as exc:
            errors.append(f"{metalink_url}: {exc}")

    mirrorlist_url = f"{base_url}.mirrorlist"
    try:
        mirror_page = _download_text(mirrorlist_url)
        digest = _extract_page_sha256(mirror_page)

        if digest is not None:
            return digest, mirrorlist_url

        errors.append(f"{mirrorlist_url}: SHA-256 hash not found")
    except (
        OSError,
        RuntimeError,
        UnicodeDecodeError,
    ) as exc:
        errors.append(f"{mirrorlist_url}: {exc}")

    raise RuntimeError(
        "Unable to obtain official Qt SHA-256 metadata:\n  "
        + "\n  ".join(errors)
    )


def _qt_source_spec(component: str, qt_version: str) -> SourceAssetSpec:
    major_minor = ".".join(qt_version.split(".")[:2])

    if component == "pyside-setup":
        filename = f"pyside-setup-everywhere-src-{qt_version}.tar.xz"
        base_url = (
            "https://download.qt.io/official_releases/QtForPython/pyside6/"
            f"PySide6-{qt_version}-src/{filename}"
        )
    else:
        filename = f"{component}-everywhere-src-{qt_version}.tar.xz"
        base_url = (
            f"https://download.qt.io/official_releases/qt/"
            f"{major_minor}/{qt_version}/submodules/{filename}"
        )

    sha256, provenance_url = _qt_official_sha256(base_url)

    return SourceAssetSpec(
        component,
        filename,
        base_url,
        sha256,
        provenance_url,
    )


def _certifi_source_spec(certifi_version: str) -> SourceAssetSpec:
    api_url = f"https://pypi.org/pypi/certifi/{certifi_version}/json"
    payload = json.loads(_download_text(api_url))
    candidates = [item for item in payload.get("urls", []) if item.get("packagetype") == "sdist"]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected exactly one certifi sdist for {certifi_version}, found {len(candidates)}")
    item = candidates[0]
    return SourceAssetSpec(
        component="certifi",
        filename=item["filename"],
        url=item["url"],
        sha256=item["digests"]["sha256"].lower(),
        provenance_url=api_url,
    )


def _read_project_version(repo_root: Path) -> str:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    init_path = repo_root / "playstore_app_audit" / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    package_version: str | None = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            package_version = node.value.value
            break
    if package_version is None:
        raise RuntimeError(f"Unable to read canonical __version__ from {init_path}")
    if package_version != version:
        raise RuntimeError(f"Version mismatch: pyproject={version}, package={package_version}")
    return version


def _project_dependency_names(repo_root: Path) -> list[str]:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    names: list[str] = []
    for requirement in pyproject["project"].get("dependencies", []):
        match = REQUIREMENT_NAME_RE.match(requirement)
        if match:
            names.append(match.group(1))
    return names


def _normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _runtime_dependency_closure(
    repo_root: Path,
    _package_files: Iterable[str],
) -> list[metadata.Distribution]:
    """Return the installed dependency closure declared by the project.

    Runtime inclusion is validated separately because Nuitka may compile
    pure-Python distributions into the executable without leaving package
    files in the standalone directory.
    """

    direct_names = _project_dependency_names(repo_root)
    direct_keys = {_normalize_dist_name(name) for name in direct_names}
    queue = deque(direct_names)
    seen: set[str] = set()
    result: list[metadata.Distribution] = []

    while queue:
        requested = queue.popleft()
        key = _normalize_dist_name(requested)

        if key in seen:
            continue

        seen.add(key)

        try:
            dist = metadata.distribution(requested)
        except metadata.PackageNotFoundError as exc:
            if key in direct_keys:
                raise RuntimeError(
                    f"Required runtime distribution is not installed: {requested}"
                ) from exc
            continue

        result.append(dist)

        for requirement in dist.requires or []:
            if "extra ==" in requirement.lower() or "extra==" in requirement.lower():
                continue

            match = REQUIREMENT_NAME_RE.match(requirement)

            if match:
                queue.append(match.group(1))

    return sorted(
        result,
        key=lambda dist: _normalize_dist_name(dist.metadata["Name"]),
    )


def _distribution_license_files(dist: metadata.Distribution) -> list[metadata.PackagePath]:
    result: list[metadata.PackagePath] = []
    for entry in dist.files or []:
        name = PurePosixPath(str(entry)).name
        if LICENSE_FILE_RE.match(name):
            result.append(entry)
    return sorted(result, key=str)


def _distribution_top_level_names(dist: metadata.Distribution) -> list[str]:
    top_level: set[str] = set()
    for entry in dist.files or []:
        parts = PurePosixPath(str(entry)).parts
        if not parts or ".dist-info" in parts[0] or ".egg-info" in parts[0]:
            continue
        first = parts[0]
        if first.startswith("."):
            continue
        if first.endswith((".py", ".pyd")):
            first = first.rsplit(".", 1)[0]
        if first and first != "__pycache__":
            top_level.add(first)
    return sorted(top_level, key=str.casefold)


def _runtime_legal_root(package_dir: Path) -> Path:
    if (
        package_dir.name.casefold().endswith(".app")
        and (package_dir / "Contents").is_dir()
    ):
        return package_dir / "Contents" / "Resources"

    return package_dir


def _runtime_inventory(
    package_dir: Path,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    legal_root = _runtime_legal_root(package_dir)

    for path in sorted(
        (
            item
            for item in package_dir.rglob("*")
            if item.is_file()
        ),
        key=lambda item: str(item).casefold(),
    ):
        skip_as_legal = False

        try:
            legal_rel = path.relative_to(legal_root)
        except ValueError:
            legal_rel = None

        if legal_rel is not None and legal_rel.parts:
            legal_rel_posix = legal_rel.as_posix()
            first = legal_rel.parts[0]

            if (
                legal_rel_posix in LEGAL_ROOT_FILES
                or first in LEGAL_ROOT_DIRS
            ):
                skip_as_legal = True

        if skip_as_legal:
            continue

        rel = _safe_relpath(path, package_dir)

        entries.append(
            {
                "path": rel,
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )

    return entries


def _runtime_evidence(package_files: Iterable[str], top_level_names: Iterable[str]) -> list[str]:
    files = list(package_files)
    evidence: list[str] = []
    for name in top_level_names:
        name_cf = name.casefold()
        for rel in files:
            path = PurePosixPath(rel)
            parts = [part.casefold() for part in path.parts]
            stem = path.name.casefold().split(".", 1)[0]
            if name_cf in parts or stem == name_cf:
                evidence.append(rel)
                break
    return sorted(set(evidence), key=str.casefold)


def _shared_library_matches(name: str, stem: str) -> bool:
    name_cf = name.casefold()
    stem_cf = stem.casefold()

    return (
        name_cf == f"{stem_cf}.dll"
        or name_cf == f"lib{stem_cf}.dylib"
        or name_cf == f"lib{stem_cf}.so"
        or name_cf.startswith(f"lib{stem_cf}.so.")
    )


def _bundled_adb_paths(package_dir: Path) -> list[str]:
    return sorted(
        (
            _safe_relpath(path, package_dir)
            for path in package_dir.rglob("*")
            if path.is_file()
            and path.name.casefold()
            in {
                "adb",
                "adb.exe",
                "adbwinapi.dll",
                "adbwinusbapi.dll",
            }
        ),
        key=str.casefold,
    )


def _forbidden_matches(package_dir: Path) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []

    for path in package_dir.rglob("*"):
        if not path.is_file():
            continue

        rel = _safe_relpath(path, package_dir)
        rel_cf = rel.casefold()
        name_cf = path.name.casefold()
        reason: str | None = None

        if (
            name_cf == "qpdf.dll"
            or name_cf == "libqpdf.dylib"
            or name_cf == "libqpdf.so"
            or name_cf.startswith("libqpdf.so.")
        ):
            reason = "qpdf image-format plugin is intentionally excluded"
        elif "virtualkeyboard" in rel_cf.replace("-", "").replace("_", ""):
            reason = "Qt Virtual Keyboard runtime is intentionally excluded"
        elif "/qtquick/virtualkeyboard/" in f"/{rel_cf.strip('/')}/":
            reason = "Qt Quick Virtual Keyboard QML is intentionally excluded"

        if reason:
            matches.append(
                {
                    "path": rel,
                    "reason": reason,
                }
            )

    return matches


def _detect_qt_components(package_dir: Path) -> list[str]:
    rel_paths = {
        _safe_relpath(path, package_dir).casefold()
        for path in package_dir.rglob("*")
        if path.is_file()
    }
    basenames = {
        PurePosixPath(path).name
        for path in rel_paths
    }

    components: list[str] = []

    qtbase_detected = (
        any(
            _shared_library_matches(name, "qt6core")
            for name in basenames
        )
        or any(
            "/qtcore.framework/" in f"/{rel}/"
            for rel in rel_paths
        )
        or any(
            "pyside6" in rel
            for rel in rel_paths
        )
    )

    if qtbase_detected:
        components.append("qtbase")

    qtsvg_detected = (
        any(
            _shared_library_matches(name, stem)
            for name in basenames
            for stem in ("qt6svg", "qsvg", "qsvgicon")
        )
        or any(
            "/qtsvg.framework/" in f"/{rel}/"
            for rel in rel_paths
        )
    )

    if qtsvg_detected:
        components.append("qtsvg")

    imageformat_stems = (
        "qicns",
        "qtga",
        "qtiff",
        "qwbmp",
        "qwebp",
    )

    if any(
        _shared_library_matches(name, stem)
        for name in basenames
        for stem in imageformat_stems
    ):
        components.append("qtimageformats")

    if any(
        "pyside6" in rel or "shiboken6" in rel
        for rel in rel_paths
    ):
        components.append("pyside-setup")

    return components


def _tar_members(archive: Path) -> list[tarfile.TarInfo]:
    with tarfile.open(archive, mode="r:xz") as handle:
        return [member for member in handle.getmembers() if member.isfile()]


def _strip_archive_root(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    return PurePosixPath(*path.parts[1:]) if len(path.parts) > 1 else path


def _extract_tar_member(archive: Path, member_name: str, destination: Path) -> None:
    with tarfile.open(archive, mode="r:xz") as handle:
        member = handle.getmember(member_name)
        source = handle.extractfile(member)
        if source is None:
            raise RuntimeError(f"Cannot extract {member_name} from {archive.name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            shutil.copyfileobj(source, output)



def _read_tar_member_bytes(
    archive: Path,
    member_name: str,
) -> bytes:
    with tarfile.open(archive, mode="r:xz") as handle:
        member = handle.getmember(member_name)
        source = handle.extractfile(member)

        if source is None:
            raise RuntimeError(
                f"Cannot read {member_name} from {archive.name}"
            )

        return source.read()


def _normalize_qt_archive_candidate(
    candidate: PurePosixPath,
) -> PurePosixPath | None:
    """Normalize a relative Qt archive path without allowing archive-root escape."""

    if candidate.is_absolute():
        return None

    normalized_parts: list[str] = []

    for part in candidate.parts:
        if part in {"", "."}:
            continue

        if part == "..":
            if not normalized_parts:
                return None
            normalized_parts.pop()
            continue

        normalized_parts.append(part)

    if not normalized_parts:
        return None

    return PurePosixPath(*normalized_parts)


def _resolve_qt_license_reference(
    attribution_rel: PurePosixPath,
    reference: str,
    members_by_rel: dict[str, str],
) -> tuple[PurePosixPath, str]:
    reference = reference.strip()

    if not reference:
        raise RuntimeError("Empty Qt attribution license reference")

    if "\\" in reference:
        raise RuntimeError(
            f"Unsafe/non-POSIX Qt attribution license reference: {reference!r}"
        )

    reference_path = PurePosixPath(reference)

    if reference_path.is_absolute():
        raise RuntimeError(
            f"Unsafe absolute Qt attribution license reference: {reference!r}"
        )

    # Qt attribution files may legitimately use ../LICENSE-style references.
    # Resolve them relative to the attribution file first, but accept the result
    # only when lexical normalization remains inside the source-archive root.
    raw_candidates = [
        attribution_rel.parent / reference_path,
        reference_path,
    ]

    for raw_candidate in raw_candidates:
        candidate = _normalize_qt_archive_candidate(raw_candidate)

        if candidate is None:
            continue

        normalized = candidate.as_posix()

        if normalized in members_by_rel:
            return candidate, members_by_rel[normalized]

    # Some Qt metadata historically names a license file without giving its
    # complete archive-relative location. Preserve the previous conservative
    # fallback only when the basename is unique across the source archive.
    basename = reference_path.name.casefold()

    basename_matches = [
        (PurePosixPath(rel), member_name)
        for rel, member_name in members_by_rel.items()
        if PurePosixPath(rel).name.casefold() == basename
    ]

    if len(basename_matches) == 1:
        return basename_matches[0]

    if not basename_matches:
        raise RuntimeError(
            f"Qt attribution references missing license file "
            f"{reference!r}: {attribution_rel}"
        )

    raise RuntimeError(
        f"Qt attribution license reference is ambiguous by basename "
        f"{reference!r}: "
        f"{[rel.as_posix() for rel, _ in basename_matches]}"
    )


def _extract_qt_legal_material(
    component: str,
    archive: Path,
    licenses_root: Path,
) -> tuple[
    list[str],
    list[dict[str, Any]],
    list[str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    license_files: list[str] = []
    license_mappings: list[dict[str, Any]] = []
    attribution_sources: list[str] = []
    attribution_records: list[dict[str, Any]] = []
    attribution_license_mappings: list[dict[str, Any]] = []
    members = _tar_members(archive)
    members_by_rel = {
        _strip_archive_root(member.name).as_posix(): member.name
        for member in members
    }

    stable_pyside_community_licenses = {
        "LGPL-3.0-only.txt",
        "GPL-2.0-only.txt",
        "GPL-3.0-only.txt",
        "Qt-GPL-exception-1.0.txt",
    }

    bundled_by_archive_rel: dict[str, str] = {}

    for member in members:
        rel = _strip_archive_root(member.name)

        if "LICENSES" not in rel.parts:
            continue

        licenses_index = rel.parts.index("LICENSES")
        tail = PurePosixPath(*rel.parts[licenses_index + 1 :])

        preserve_stable_path = (
            component == "pyside-setup"
            and tail.as_posix() in stable_pyside_community_licenses
        )

        if preserve_stable_path:
            destination = licenses_root / "qt" / component / tail
            _extract_tar_member(
                archive,
                member.name,
                destination,
            )
            bundled_rel = _safe_relpath(
                destination,
                licenses_root.parent,
            )
            digest = _sha256(destination)
        else:
            payload = _read_tar_member_bytes(
                archive,
                member.name,
            )
            bundled_rel, digest = store_canonical_legal_payload(
                licenses_root,
                payload,
            )

        license_files.append(bundled_rel)
        bundled_by_archive_rel[rel.as_posix()] = bundled_rel

        license_mappings.append(
            {
                "source_member": (
                    f"{component}/{rel.as_posix()}"
                ),
                "bundled_file": bundled_rel,
                "sha256": digest,
            }
        )

    for member in members:
        if PurePosixPath(member.name).name != "qt_attribution.json":
            continue
        rel = _strip_archive_root(member.name)
        attribution_source = f"{component}/{rel.as_posix()}"
        attribution_sources.append(attribution_source)

        try:
            # Qt upstream attribution metadata can contain literal
            # control characters inside strings.
            data = json.loads(
                _read_tar_member_bytes(
                    archive,
                    member.name,
                ).decode("utf-8"),
                strict=False,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid Qt attribution JSON: {component}/{rel}") from exc
        records = data if isinstance(data, list) else [data]
        if not records or not all(isinstance(record, dict) for record in records):
            raise RuntimeError(f"Unexpected Qt attribution structure: {component}/{rel}")

        for record_index, record in enumerate(records):
            if not any(key in record for key in ("Name", "Id", "Description")):
                raise RuntimeError(f"Qt attribution lacks identity fields: {component}/{rel}")
            if not any(key in record for key in ("License", "LicenseId", "LicenseFile", "LicenseFiles")):
                raise RuntimeError(f"Qt attribution lacks license fields: {component}/{rel}")

            referenced = record.get("LicenseFile") or record.get("LicenseFiles")
            references = [referenced] if isinstance(referenced, str) else list(referenced or [])
            bundled_for_record: list[str] = []
            for reference in references:
                if not isinstance(reference, str) or not reference.strip():
                    raise RuntimeError(f"Invalid LicenseFile entry in {component}/{rel}")
                source_rel, member_name = _resolve_qt_license_reference(
                    rel, reference, members_by_rel
                )
                source_key = source_rel.as_posix()
                bundled_rel = bundled_by_archive_rel.get(source_key)
                if bundled_rel is None:
                    payload = _read_tar_member_bytes(
                        archive,
                        member_name,
                    )
                    bundled_rel, _ = store_canonical_legal_payload(
                        licenses_root,
                        payload,
                    )
                    bundled_by_archive_rel[source_key] = bundled_rel
                bundled_for_record.append(bundled_rel)
                attribution_license_mappings.append(
                    {
                        "attribution_source": attribution_source,
                        "record_index": record_index,
                        "reference": reference,
                        "source_member": f"{component}/{source_rel.as_posix()}",
                        "bundled_file": bundled_rel,
                    }
                )

            attribution_records.append(
                {
                    "component": component,
                    "source": attribution_source,
                    "record_index": record_index,
                    "data": record,
                    "bundled_license_files": sorted(
                        set(bundled_for_record), key=str.casefold
                    ),
                }
            )

    return (
        sorted(set(license_files), key=str.casefold),
        sorted(
            license_mappings,
            key=lambda item: item["source_member"].casefold(),
        ),
        sorted(set(attribution_sources), key=str.casefold),
        attribution_records,
        sorted(
            attribution_license_mappings,
            key=lambda item: (
                item["attribution_source"].casefold(),
                item["record_index"],
                item["reference"].casefold(),
            ),
        ),
    )

def _render_qt_attributions(records: list[dict[str, Any]]) -> str:
    lines = [
        "Qt third-party attributions",
        "===========================",
        "",
        "This file is generated from qt_attribution.json metadata contained in the exact",
        "Qt/PySide source archives staged for this release. Parsed attribution records and",
        "source provenance are retained in release validation evidence; original metadata remains",
        "available in the exact upstream source archives.",
        "",
    ]
    field_order = [
        "Name",
        "Id",
        "Description",
        "Homepage",
        "Version",
        "QtUsage",
        "License",
        "LicenseId",
        "LicenseFile",
        "LicenseFiles",
        "Copyright",
    ]
    for index, item in enumerate(records, start=1):
        data = item["data"]
        title = data.get("Name") or data.get("Id") or data.get("Description") or f"Attribution {index}"
        lines.extend([f"[{index}] {title}", f"Source metadata: {item['source']}"])
        for key in field_order:
            if key not in data:
                continue
            value = data[key]
            if isinstance(value, (dict, list)):
                rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                rendered = str(value).strip()
            if rendered:
                lines.append(f"{key}: {rendered}")
        for bundled_file in item.get("bundled_license_files", []):
            lines.append(f"Bundled license file: {bundled_file}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"



def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _load_nuitka_compilation_report(
    report_path: Path,
) -> tuple[str, list[dict[str, str]]]:
    try:
        root = ET.parse(report_path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise RuntimeError(
            f"Unable to parse Nuitka compilation report: {report_path}: {exc}"
        ) from exc

    if _xml_local_name(root.tag) != "nuitka-compilation-report":
        raise RuntimeError(
            f"Unexpected Nuitka report root element: {root.tag}"
        )

    nuitka_version = root.attrib.get("nuitka_version", "").strip()
    if not nuitka_version:
        raise RuntimeError("Nuitka compilation report has no nuitka_version")

    modules_by_name: dict[str, dict[str, str]] = {}

    for element in root.iter():
        if _xml_local_name(element.tag) != "module":
            continue

        name = element.attrib.get("name", "").strip()
        if not name:
            continue

        kind = element.attrib.get("kind", "").strip()

        existing = modules_by_name.get(name)
        if existing is not None and existing.get("kind") != kind:
            raise RuntimeError(
                f"Nuitka report contains conflicting module entries for {name}"
            )

        modules_by_name[name] = {
            "name": name,
            "kind": kind,
        }

    modules = [
        modules_by_name[name]
        for name in sorted(modules_by_name, key=str.casefold)
    ]

    if not modules:
        raise RuntimeError(
            "Nuitka compilation report contains no compiled/included module records"
        )

    return nuitka_version, modules


def _compiled_module_evidence(
    report_modules: list[dict[str, str]],
    top_level_names: list[str],
) -> list[str]:
    result: set[str] = set()

    for item in report_modules:
        module_name = item["name"]

        for top_level in top_level_names:
            if (
                module_name == top_level
                or module_name.startswith(top_level + ".")
            ):
                result.add(module_name)
                break

    return sorted(result, key=str.casefold)


def _write_nuitka_build_evidence(
    release_dir: Path,
    report_path: Path,
    nuitka_version: str,
    report_modules: list[dict[str, str]],
) -> tuple[str, str]:
    destination = (
        release_dir
        / "validation-evidence"
        / "NUITKA-COMPILATION-EVIDENCE.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)

    evidence = {
        "schema_version": 1,
        "source": "Nuitka compilation report",
        "nuitka_version": nuitka_version,
        "source_report_sha256": _sha256(report_path),
        "module_count": len(report_modules),
        "modules": report_modules,
    }

    destination.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return (
        _safe_relpath(destination, release_dir),
        _sha256(destination),
    )

def _copy_distribution_legal_files(
    dist: metadata.Distribution,
    licenses_root: Path,
) -> tuple[list[str], list[str]]:
    dist_name = dist.metadata["Name"]
    version = dist.version
    target_root = licenses_root / "python-packages" / f"{dist_name}-{version}"
    copied: list[str] = []
    source_entries: list[str] = []
    for entry in _distribution_license_files(dist):
        source = Path(dist.locate_file(entry))
        if not source.is_file():
            continue
        destination = target_root / PurePosixPath(str(entry)).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(_safe_relpath(destination, licenses_root.parent))
        source_entries.append(str(entry))
    return sorted(copied), sorted(source_entries)


def _copy_cpython_license(licenses_root: Path) -> str:
    roots = list(
        dict.fromkeys(
            (
                Path(sys.base_prefix),
                Path(sys.prefix),
            )
        )
    )
    candidates = [
        root / filename
        for root in roots
        for filename in ("LICENSE.txt", "LICENSE")
    ]

    source = next(
        (path for path in candidates if path.is_file()),
        None,
    )

    destination = licenses_root / "cpython" / "LICENSE.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if source is not None:
        shutil.copy2(source, destination)
    else:
        python_version = platform.python_version()
        license_url = (
            "https://raw.githubusercontent.com/python/cpython/"
            f"v{python_version}/LICENSE"
        )

        license_text = _download_text(license_url)

        if (
            len(license_text) < 1000
            or "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2"
            not in license_text
        ):
            raise RuntimeError(
                "Unexpected CPython license payload from "
                f"{license_url}"
            )

        destination.write_text(
            license_text,
            encoding="utf-8",
            newline="\n",
        )

    return _safe_relpath(
        destination,
        licenses_root.parent,
    )


def _copy_nuitka_legal_files(licenses_root: Path) -> tuple[str, list[str]]:
    try:
        dist = metadata.distribution("Nuitka")
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError("Nuitka is not installed in the release environment") from exc

    required = {"license-runtime.txt", "license.txt", "notice.txt"}
    found: dict[str, Path] = {}
    for entry in dist.files or []:
        name = PurePosixPath(str(entry)).name.casefold()
        if name in required:
            source = Path(dist.locate_file(entry))
            if source.is_file():
                found[name] = source
    missing = required - found.keys()
    if missing:
        raise RuntimeError(f"Nuitka legal files missing from installed distribution: {sorted(missing)}")

    copied: list[str] = []
    for key in sorted(required):
        source = found[key]
        destination = licenses_root / "nuitka" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(_safe_relpath(destination, licenses_root.parent))
    return dist.version, copied


def _copy_openssl_license(
    licenses_root: Path,
    openssl_version: str,
) -> tuple[str, str]:
    version_match = OPENSSL_VERSION_RE.search(openssl_version)

    if not version_match:
        raise RuntimeError(
            f"Unable to parse OpenSSL version: {openssl_version}"
        )

    numeric_version = version_match.group(1)
    version_parts = tuple(
        int(part)
        for part in numeric_version.split(".")
    )

    if version_parts < (3, 0):
        raise RuntimeError(
            f"Unsupported OpenSSL license mapping for version "
            f"{numeric_version}: release tooling currently expects "
            f"OpenSSL 3.0 or later"
        )

    url = (
        "https://www.openssl-library.org/source/license/"
        "apache-license-2.0.txt"
    )

    license_text = _download_text(url)

    if (
        "Apache License" not in license_text
        or "Version 2.0" not in license_text
        or "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION"
        not in license_text
    ):
        raise RuntimeError(
            f"Unexpected OpenSSL Apache-2.0 license content from {url}"
        )

    destination = licenses_root / "openssl" / "LICENSE.txt"
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    destination.write_text(
        license_text,
        encoding="utf-8",
        newline="\n",
    )

    return (
        _safe_relpath(
            destination,
            licenses_root.parent,
        ),
        url,
    )


def _write_source_availability(
    package_legal_dir: Path,
    version: str,
    release_tag: str,
    source_bundle: dict[str, Any],
) -> None:
    release_url = f"{PROJECT_REPOSITORY}/releases/tag/{release_tag}"

    lines = [
        "# Third-party corresponding source availability",
        "",
        f"This notice applies to {APP_NAME} v{version} binary releases.",
        "",
        "Required corresponding source for redistributed LGPL/MPL third-party",
        "components is provided in one release-wide archive:",
        "",
        f"- `{source_bundle['filename']}`",
        "",
        "Verify the final release-wide archive checksum using `SHA256SUMS.txt`",
        "attached to the same GitHub Release.",
        "",
        f"Release location: {release_url}",
        "",
        "The bundle contains its own README, internal SHA256SUMS.txt and the",
        "exact unmodified upstream source archives under sources/.",
        "",
        f"The GPL-covered {APP_NAME} source corresponding to the application",
        f"binary must also be available from the exact `{release_tag}` tag.",
        "",
    ]

    (package_legal_dir / "SOURCE-AVAILABILITY.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )


def _write_third_party_notices(
    package_legal_dir: Path,
    qt_version: str,
    dependencies: list[dict[str, Any]],
    cpython_version: str,
    cpython_license: str,
    nuitka_version: str,
    nuitka_files: list[str],
    openssl: dict[str, Any] | None,
) -> None:
    lines = [
        "# Third-party notices",
        "",
        f"{APP_NAME} includes or is distributed with third-party software. {APP_NAME} itself is",
        "distributed under GPL-3.0-only in the community edition; that project license does not",
        "replace or restrict third-party licenses.",
        "",
        "## Qt / PySide6 / Shiboken6",
        "",
        f"- Runtime/source version: {qt_version}.",
        "- Distribution basis for shipped LGPL-capable Qt/PySide/Shiboken components: GNU LGPL v3.",
        "- Community license texts are under `licenses/qt/pyside-setup/`, including",
        "  `LGPL-3.0-only.txt`, `GPL-2.0-only.txt`, `GPL-3.0-only.txt`, and the Qt GPL exception.",
        "- `LicenseRef-Qt-Commercial.txt`, if present in the upstream source archive, documents an",
        "  alternative upstream licensing option and is not the license basis used for this package.",
        "- Qt Virtual Keyboard is intentionally excluded.",
        "- Qt community license texts and canonical third-party legal payloads are under",
        "  `licenses/qt/` and `licenses/qt-third-party/`.",
        "- A human-readable attribution rendering is in `licenses/QT-ATTRIBUTIONS.txt`.",
        "",
        "### LGPL library replacement",
        "",
        "The standalone package keeps Qt/PySide/Shiboken runtime libraries, extension modules",
        "and plugins as separate files rather than embedding them into one inseparable executable.",
        "A recipient may replace a compatible LGPL-covered shared runtime library or plugin by",
        "substituting the corresponding file in the extracted package layout while preserving the",
        "ABI compatibility required by the application.",
        "",
        "## CPython",
        "",
        f"- CPython {cpython_version} - Python Software Foundation licensing.",
        f"- License: `{cpython_license}`.",
        "",
        "## Python runtime distributions",
        "",
    ]
    for item in dependencies:
        if _normalize_dist_name(item["name"]) in {"pyside6-essentials", "shiboken6"}:
            license_summary = "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"
            license_paths = [
                "licenses/qt/pyside-setup/LGPL-3.0-only.txt",
                "licenses/qt/pyside-setup/GPL-2.0-only.txt",
                "licenses/qt/pyside-setup/GPL-3.0-only.txt",
                "licenses/qt/pyside-setup/Qt-GPL-exception-1.0.txt",
            ]
        else:
            license_summary = item["license"] or "See bundled license files"
            license_paths = item["license_files"]
        rendered_paths = ", ".join(f"`{path}`" for path in license_paths) or "metadata only"
        lines.append(
            f"- **{item['name']} {item['version']}** - {license_summary} - license/notice files: "
            f"{rendered_paths}"
        )

    lines.extend(
        [
            "",
            "## Nuitka-generated runtime",
            "",
            f"- Nuitka {nuitka_version} is the build tool.",
            "- Nuitka itself is AGPLv3; its runtime exception permits generated target code to be",
            "  conveyed under other terms.",
            "- Bundled Nuitka legal files: " + ", ".join(f"`{path}`" for path in nuitka_files) + ".",
        ]
    )
    if openssl is not None:
        lines.extend(
            [
                "",
                "## OpenSSL",
                "",
                f"- {openssl['version']}.",
                "- OpenSSL 3.x is licensed under Apache License 2.0.",
                f"- License: `{openssl['license_file']}`.",
                "- Packaged files: " + ", ".join(f"`{path}`" for path in openssl["runtime_files"]) + ".",
            ]
        )
    lines.extend(
        [
            "",
            "## Google Android Platform-Tools / ADB",
            "",
            "Android Platform-Tools are not bundled in this release. When managed ADB setup is",
            "requested, the application downloads Google's Platform-Tools archive directly.",
            "Google and Android are not affiliated with or endorsers of Play Store App Audit.",
            "",
            "## Trademarks",
            "",
            "All third-party product names and trademarks remain the property of their respective",
            "owners. Their mention is descriptive only.",
            "",
        ]
    )
    (package_legal_dir / "THIRD_PARTY_NOTICES.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def _write_sha256s(source_assets_dir: Path, assets: list[dict[str, Any]]) -> None:
    lines = [f"{item['sha256']}  {item['filename']}" for item in assets]
    (source_assets_dir / "SHA256SUMS.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def _copy_package_legal_into_runtime(package_legal_dir: Path, package_dir: Path) -> None:
    staging_only = {"LEGAL-MANIFEST.json"}
    runtime_legal_root = _runtime_legal_root(package_dir)
    runtime_legal_root.mkdir(parents=True, exist_ok=True)

    for item in package_legal_dir.iterdir():
        if item.name in staging_only:
            continue

        destination = runtime_legal_root / item.name
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def _refresh_runtime_evidence(
    package_dir: Path,
    release_dir: Path,
) -> None:
    manifest_path = (
        release_dir
        / "package-legal"
        / "LEGAL-MANIFEST.json"
    )

    if not package_dir.is_dir():
        raise RuntimeError(
            f"Package directory does not exist: {package_dir}"
        )

    if not manifest_path.is_file():
        raise RuntimeError(
            f"Staged legal manifest does not exist: {manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError(
            "Cannot refresh runtime evidence for an incompatible "
            "legal manifest schema"
        )

    package = manifest.get("package")

    if not isinstance(package, dict):
        raise RuntimeError(
            "Legal manifest package object is missing"
        )

    runtime_inventory = _runtime_inventory(package_dir)

    build_info = next(
        (
            item
            for item in runtime_inventory
            if PurePosixPath(
                item["path"]
            ).name.casefold() == "build-info.txt"
        ),
        None,
    )

    package.update(
        {
            "directory_name": package_dir.name,
            "platform": _host_platform_key(),
            "architecture": platform.machine(),
            "runtime_file_count": len(runtime_inventory),
            "runtime_inventory_sha256": (
                _canonical_json_sha256(runtime_inventory)
            ),
            "runtime_inventory": runtime_inventory,
            "build_info": build_info,
        }
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--release-tag")
    parser.add_argument("--nuitka-report", type=Path)
    parser.add_argument(
        "--inject",
        action="store_true",
        help="Copy generated package legal files into package-dir",
    )
    parser.add_argument(
        "--refresh-runtime-evidence",
        action="store_true",
        help=(
            "Refresh only runtime inventory evidence after a "
            "package mutation such as macOS signing"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = (
        args.repo_root
        or Path(__file__).resolve().parents[2]
    ).resolve()
    package_dir = args.package_dir.resolve()
    release_dir = args.release_dir.resolve()

    if args.refresh_runtime_evidence:
        if args.inject:
            raise RuntimeError(
                "--refresh-runtime-evidence cannot be combined "
                "with --inject"
            )

        _refresh_runtime_evidence(
            package_dir,
            release_dir,
        )

        print(
            "Refreshed runtime evidence for "
            f"{package_dir}"
        )
        return 0

    legal_preparation_started = time.perf_counter()

    if args.nuitka_report is None:
        raise RuntimeError(
            "--nuitka-report is required when preparing "
            "legal release material"
        )

    nuitka_report = args.nuitka_report.resolve()
    package_legal_dir = release_dir / "package-legal"
    source_assets_dir = release_dir / "source-assets"
    licenses_root = package_legal_dir / "licenses"

    if not nuitka_report.is_file():
        raise RuntimeError(
            f"Nuitka compilation report does not exist: {nuitka_report}"
        )

    report_nuitka_version, report_modules = (
        _load_nuitka_compilation_report(nuitka_report)
    )

    if not package_dir.is_dir():
        raise RuntimeError(f"Package directory does not exist: {package_dir}")
    if _forbidden_matches(package_dir):
        formatted = "\n".join(f"  {item['path']}: {item['reason']}" for item in _forbidden_matches(package_dir))
        raise RuntimeError(f"Forbidden runtime components detected:\n{formatted}")
    if _bundled_adb_paths(package_dir):
        raise RuntimeError(
            "ADB is bundled, but public release policy requires "
            "managed ADB to stay external"
        )

    version = _read_project_version(repo_root)
    release_tag = args.release_tag or f"v{version}"
    expected_tag = f"v{version}"
    if release_tag != expected_tag:
        raise RuntimeError(f"Release tag must match canonical version: expected {expected_tag}, got {release_tag}")

    runtime_inventory_started = time.perf_counter()
    runtime_inventory = _runtime_inventory(package_dir)
    print(
        "Legal timing: runtime inventory "
        f"{time.perf_counter() - runtime_inventory_started:.2f}s",
        file=sys.stderr,
    )
    runtime_paths = [item["path"] for item in runtime_inventory]
    runtime_inventory_sha256 = _canonical_json_sha256(runtime_inventory)
    qt_components = _detect_qt_components(package_dir)
    if "qtbase" not in qt_components or "pyside-setup" not in qt_components:
        raise RuntimeError(f"Expected Qt/PySide runtime was not detected: {qt_components}")

    pyside_version = metadata.version("PySide6_Essentials")
    shiboken_version = metadata.version("shiboken6")
    if pyside_version != shiboken_version:
        raise RuntimeError(
            f"PySide6_Essentials/shiboken6 version mismatch: {pyside_version} vs {shiboken_version}"
        )

    if package_legal_dir.exists():
        shutil.rmtree(package_legal_dir)
    package_legal_dir.mkdir(parents=True, exist_ok=True)
    source_assets_dir.mkdir(parents=True, exist_ok=True)
    licenses_root.mkdir(parents=True)

    shutil.copy2(repo_root / "LICENSE", package_legal_dir / "LICENSE")

    source_metadata_started = time.perf_counter()
    source_specs = [
        _qt_source_spec(component, pyside_version)
        for component in qt_components
    ]
    certifi_version = metadata.version("certifi")
    source_specs.append(_certifi_source_spec(certifi_version))
    print(
        "Legal timing: source provenance metadata "
        f"{time.perf_counter() - source_metadata_started:.2f}s",
        file=sys.stderr,
    )
    expected_source_names = {spec.filename for spec in source_specs}
    for stale in source_assets_dir.iterdir():
        if stale.is_file() and stale.name != "SHA256SUMS.txt" and stale.name not in expected_source_names:
            stale.unlink()

    source_assets: list[dict[str, Any]] = []
    qt_license_files: list[str] = []
    qt_license_mappings: list[dict[str, Any]] = []
    qt_attribution_sources: list[str] = []
    qt_attribution_records: list[dict[str, Any]] = []
    qt_attribution_license_mappings: list[dict[str, Any]] = []
    qt_source_components: list[dict[str, Any]] = []

    for spec in source_specs:
        destination = source_assets_dir / spec.filename
        source_started = time.perf_counter()
        _download_file(spec.url, destination, spec.sha256)
        print(
            f"Legal timing: source asset {spec.filename} "
            f"{time.perf_counter() - source_started:.2f}s",
            file=sys.stderr,
        )
        entry: dict[str, Any] = {
            "component": spec.component,
            "filename": spec.filename,
            "sha256": spec.sha256,
            "size": destination.stat().st_size,
            "download_url": spec.url,
            "provenance_url": spec.provenance_url,
        }
        source_assets.append(entry)
        if spec.component == "certifi":
            continue
        extraction_started = time.perf_counter()
        (
            licenses,
            license_mappings,
            attributions,
            records,
            attribution_license_mappings,
        ) = _extract_qt_legal_material(
            spec.component,
            destination,
            licenses_root,
        )
        print(
            f"Legal timing: Qt extraction {spec.component} "
            f"{time.perf_counter() - extraction_started:.2f}s",
            file=sys.stderr,
        )

        qt_license_files.extend(licenses)
        qt_license_mappings.extend(license_mappings)
        qt_attribution_sources.extend(attributions)
        qt_attribution_records.extend(records)
        qt_attribution_license_mappings.extend(
            attribution_license_mappings
        )
        qt_source_components.append(
            {
                "component": spec.component,
                "source_asset": spec.filename,
                "license_files_extracted": len(licenses),
                "attribution_sources_found": len(attributions),
            }
        )

    qt_human_path = licenses_root / "QT-ATTRIBUTIONS.txt"
    qt_human_path.write_text(
        _render_qt_attributions(qt_attribution_records), encoding="utf-8", newline="\n"
    )

    dependencies: list[dict[str, Any]] = []
    for dist in _runtime_dependency_closure(repo_root, runtime_paths):
        copied_files, metadata_files = _copy_distribution_legal_files(
            dist,
            licenses_root,
        )

        normalized_name = _normalize_dist_name(dist.metadata["Name"])
        is_qt_python = normalized_name in {
            "pyside6-essentials",
            "shiboken6",
        }

        community_files = [
            "licenses/qt/pyside-setup/LGPL-3.0-only.txt",
            "licenses/qt/pyside-setup/GPL-2.0-only.txt",
            "licenses/qt/pyside-setup/GPL-3.0-only.txt",
            "licenses/qt/pyside-setup/Qt-GPL-exception-1.0.txt",
        ]

        if is_qt_python:
            missing_community_files = [
                rel
                for rel in community_files
                if not (package_legal_dir / PurePosixPath(rel)).is_file()
            ]

            if missing_community_files:
                raise RuntimeError(
                    f"Required Qt/PySide community license files are missing "
                    f"for {dist.metadata['Name']} {dist.version}: "
                    f"{missing_community_files}"
                )

        elif not copied_files:
            raise RuntimeError(
                f"No license/notice files found for packaged dependency "
                f"{dist.metadata['Name']} {dist.version}"
            )

        top_level = _distribution_top_level_names(dist)
        evidence = _runtime_evidence(runtime_paths, top_level)
        compiled_evidence = _compiled_module_evidence(
            report_modules,
            top_level,
        )

        if not evidence and not compiled_evidence:
            raise RuntimeError(
                f"No file-backed or Nuitka-compiled runtime evidence found for "
                f"dependency {dist.metadata['Name']} {dist.version}"
            )
        dependencies.append(
            {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "license": (
                    "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"
                    if is_qt_python
                    else dist.metadata.get("License-Expression") or dist.metadata.get("License") or ""
                ),
                "distribution_license_basis": "LGPL-3.0-only" if is_qt_python else None,
                "license_files": community_files if is_qt_python else copied_files,
                "upstream_metadata_license_files": copied_files if is_qt_python else [],
                "metadata_license_entries": metadata_files,
                "top_level_names": top_level,
                "runtime_evidence": evidence,
                "nuitka_compiled_modules": compiled_evidence,
            }
        )

    cpython_license = _copy_cpython_license(licenses_root)
    nuitka_version, nuitka_files = _copy_nuitka_legal_files(licenses_root)

    if report_nuitka_version != nuitka_version:
        raise RuntimeError(
            "Nuitka report/version mismatch: "
            f"report={report_nuitka_version}, installed={nuitka_version}"
        )

    build_evidence_rel, build_evidence_sha256 = (
        _write_nuitka_build_evidence(
            release_dir,
            nuitka_report,
            report_nuitka_version,
            report_modules,
        )
    )

    openssl_runtime_files = sorted(
        {
            item["path"]
            for item in runtime_inventory
            if _is_openssl_runtime_name(
                PurePosixPath(item["path"]).name
            )
        },
        key=str.casefold,
    )
    openssl: dict[str, Any] | None = None
    if openssl_runtime_files:
        openssl_license, openssl_source = _copy_openssl_license(licenses_root, ssl.OPENSSL_VERSION)
        openssl = {
            "version": ssl.OPENSSL_VERSION,
            "runtime_files": openssl_runtime_files,
            "license_file": openssl_license,
            "license_source": openssl_source,
        }

    _write_sha256s(source_assets_dir, source_assets)

    source_bundle_started = time.perf_counter()
    source_bundle = build_third_party_source_bundle(
        source_assets_dir,
        release_dir,
        version,
        source_assets,
    )
    print(
        "Legal timing: source bundle assembly "
        f"{time.perf_counter() - source_bundle_started:.2f}s",
        file=sys.stderr,
    )

    _write_source_availability(
        package_legal_dir,
        version,
        release_tag,
        {
            "filename": source_bundle.name,
            "sha256": _sha256(source_bundle),
            "size": source_bundle.stat().st_size,
        },
    )

    _write_third_party_notices(
        package_legal_dir=package_legal_dir,
        qt_version=pyside_version,
        dependencies=dependencies,
        cpython_version=platform.python_version(),
        cpython_license=cpython_license,
        nuitka_version=nuitka_version,
        nuitka_files=nuitka_files,
        openssl=openssl,
    )

    build_info = next(
        (item for item in runtime_inventory if PurePosixPath(item["path"]).name.casefold() == "build-info.txt"),
        None,
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "application": {
            "name": APP_NAME,
            "version": version,
            "project_license": PROJECT_LICENSE,
            "release_tag": release_tag,
            "repository": PROJECT_REPOSITORY,
        },
        "package": {
            "directory_name": package_dir.name,
            "platform": _host_platform_key(),
            "architecture": platform.machine(),
            "runtime_file_count": len(runtime_inventory),
            "runtime_inventory_sha256": runtime_inventory_sha256,
            "runtime_inventory": runtime_inventory,
            "build_info": build_info,
        },
        "toolchain": {
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "architecture": platform.architecture()[0],
            },
            "nuitka": {
                "version": nuitka_version,
                "compilation_report_sha256": _sha256(nuitka_report),
                "sanitized_evidence_file": build_evidence_rel,
                "sanitized_evidence_sha256": build_evidence_sha256,
            },
            "openssl": openssl,
        },
        "runtime_dependencies": dependencies,
        "qt": {
            "version": pyside_version,
            "distribution_basis": "LGPL-3.0-only",
            "detected_components": qt_components,
            "source_components": qt_source_components,
            "community_license_files": sorted(
                path
                for path in qt_license_files
                if PurePosixPath(path).name
                in {
                    "LGPL-3.0-only.txt",
                    "GPL-2.0-only.txt",
                    "GPL-3.0-only.txt",
                    "Qt-GPL-exception-1.0.txt",
                }
            ),
            "all_extracted_license_files": sorted(
                set(qt_license_files),
                key=str.casefold,
            ),
            "license_mappings": sorted(
                qt_license_mappings,
                key=lambda item: item["source_member"].casefold(),
            ),
            "attribution_sources": sorted(
                set(qt_attribution_sources),
                key=str.casefold,
            ),
            "attribution_records": qt_attribution_records,
            "attribution_record_count": len(qt_attribution_records),
            "attribution_license_mappings": qt_attribution_license_mappings,
            "attribution_license_files": sorted(
                {item["bundled_file"] for item in qt_attribution_license_mappings},
                key=str.casefold,
            ),
            "human_readable_attributions": "licenses/QT-ATTRIBUTIONS.txt",
        },
        "source_bundle": {
            "filename": source_bundle.name,
            "sha256": _sha256(source_bundle),
            "size": source_bundle.stat().st_size,
        },
        "source_assets": source_assets,
        "policy": {
            "forbidden_runtime_matches": [],
            "adb_bundled": False,
            "final_artifact_revalidation_required": True,
            "project_source_tag_must_exist_before_publication": True,
        },
    }
    (package_legal_dir / "LEGAL-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    if args.inject:
        _copy_package_legal_into_runtime(package_legal_dir, package_dir)

    print(f"Prepared permanent legal release staging for {APP_NAME} v{version}")
    print(f"Package legal staging: {package_legal_dir}")
    print(f"Source release assets: {source_assets_dir}")
    print(f"Runtime payload files fingerprinted: {len(runtime_inventory)}")
    print(f"Qt attribution records rendered: {len(qt_attribution_records)}")
    print(
        "Legal timing: total preparation "
        f"{time.perf_counter() - legal_preparation_started:.2f}s",
        file=sys.stderr,
    )
    print("Final MSVC main artifact still requires a fresh legal/runtime validation before publication.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
