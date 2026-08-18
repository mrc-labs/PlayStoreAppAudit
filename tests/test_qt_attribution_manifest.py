from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import validate_release_legal_bundle as validator


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, dict]:
    package = tmp_path / "package"

    payload = b"third-party attribution license\n"
    digest = _sha(payload)

    bundled_rel = f"licenses/qt-third-party/{digest}"
    bundled_path = package / bundled_rel
    bundled_path.parent.mkdir(parents=True, exist_ok=True)
    bundled_path.write_bytes(payload)

    source = "qtbase/src/3rdparty/example/qt_attribution.json"
    source_member = "qtbase/src/3rdparty/example/LICENSE.txt"

    human_rel = "licenses/QT-ATTRIBUTIONS.txt"
    human_path = package / human_rel
    human_path.parent.mkdir(parents=True, exist_ok=True)
    human_path.write_text(
        "\n".join(
            [
                "Qt third-party attributions",
                "",
                "[1] Example component",
                f"Source metadata: {source}",
                "Name: Example component",
                "LicenseFile: LICENSE.txt",
                f"Bundled license file: {bundled_rel}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    manifest = {
        "qt": {
            "attribution_sources": [source],
            "attribution_records": [
                {
                    "component": "qtbase",
                    "source": source,
                    "record_index": 0,
                    "data": {
                        "Name": "Example component",
                        "LicenseFile": "LICENSE.txt",
                    },
                    "bundled_license_files": [bundled_rel],
                }
            ],
            "attribution_record_count": 1,
            "attribution_license_mappings": [
                {
                    "attribution_source": source,
                    "record_index": 0,
                    "reference": "LICENSE.txt",
                    "source_member": source_member,
                    "bundled_file": bundled_rel,
                }
            ],
            "attribution_license_files": [bundled_rel],
            "human_readable_attributions": human_rel,
        }
    }

    return package, manifest


def test_manifest_based_qt_attributions_are_valid(
    tmp_path: Path,
) -> None:
    package, manifest = _fixture(tmp_path)

    validator._validate_qt_attributions(
        package,
        manifest,
    )


def test_missing_qt_attribution_mapping_is_rejected(
    tmp_path: Path,
) -> None:
    package, manifest = _fixture(tmp_path)

    manifest["qt"]["attribution_license_mappings"] = []
    manifest["qt"]["attribution_license_files"] = []

    with pytest.raises(
        validator.ValidationError,
        match="referenced license is not mapped",
    ):
        validator._validate_qt_attributions(
            package,
            manifest,
        )