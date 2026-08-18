from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import validate_release_legal_bundle as validator


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, dict, Path]:
    package = tmp_path / "package"

    community = {
        "LGPL-3.0-only.txt": b"lgpl\n",
        "GPL-2.0-only.txt": b"gpl2\n",
        "GPL-3.0-only.txt": b"gpl3\n",
        "Qt-GPL-exception-1.0.txt": b"exception\n",
    }

    mappings = []

    for name, data in community.items():
        path = package / "licenses" / "qt" / "pyside-setup" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

        mappings.append(
            {
                "source_member": f"pyside-setup/LICENSES/{name}",
                "bundled_file": path.relative_to(package).as_posix(),
                "sha256": _sha(data),
            }
        )

    canonical_data = b"third-party-license\n"
    canonical_sha = _sha(canonical_data)
    canonical = (
        package
        / "licenses"
        / "qt-third-party"
        / canonical_sha
    )
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes(canonical_data)

    mappings.append(
        {
            "source_member": "qtbase/src/example/LICENSE.txt",
            "bundled_file": canonical.relative_to(package).as_posix(),
            "sha256": canonical_sha,
        }
    )

    required = sorted(
        validator.REQUIRED_QT_COMMUNITY_LICENSES
    )

    manifest = {
        "qt": {
            "distribution_basis": "LGPL-3.0-only",
            "community_license_files": required,
            "license_mappings": mappings,
            "all_extracted_license_files": sorted(
                {item["bundled_file"] for item in mappings},
                key=str.casefold,
            ),
            "attribution_license_mappings": [],
        },
        "runtime_dependencies": [
            {
                "name": "PySide6_Essentials",
                "distribution_license_basis": "LGPL-3.0-only",
                "license_files": required,
            },
            {
                "name": "shiboken6",
                "distribution_license_basis": "LGPL-3.0-only",
                "license_files": required,
            },
        ],
    }

    (package / "THIRD_PARTY_NOTICES.md").write_text(
        "\n".join(
            [
                "Distribution basis: LGPL-3.0-only",
                "LGPL library replacement instructions",
                "Commercial Qt is not the license basis used for this package",
            ]
        ),
        encoding="utf-8",
    )

    return package, manifest, canonical


def test_qt_canonical_license_mapping_is_valid(
    tmp_path: Path,
) -> None:
    package, manifest, _ = _fixture(tmp_path)

    validator._validate_qt_license_mapping(
        package,
        manifest,
    )


def test_qt_canonical_license_tampering_is_rejected(
    tmp_path: Path,
) -> None:
    package, manifest, canonical = _fixture(tmp_path)

    canonical.write_bytes(b"tampered\n")

    with pytest.raises(
        validator.ValidationError,
        match="SHA-256 mismatch",
    ):
        validator._validate_qt_license_mapping(
            package,
            manifest,
        )