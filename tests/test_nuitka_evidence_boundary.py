from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import validate_release_legal_bundle as validator


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, dict]:
    release_dir = tmp_path / "legal-release"
    package_dir = tmp_path / "package"

    evidence_dir = release_dir / "validation-evidence"
    evidence_dir.mkdir(parents=True)
    package_dir.mkdir()

    report_sha = "a" * 64

    evidence = {
        "schema_version": 2,
        "source": "Nuitka compilation report",
        "nuitka_version": "2.7.0",
        "source_report_sha256": report_sha,
        "module_count": 2,
        "modules": [
            {
                "name": "example",
                "kind": "CompiledPythonModule",
                "distribution": "example-dist",
            },
            {
                "name": "example.helper",
                "kind": "CompiledPythonModule",
                "distribution": "example-dist",
            },
        ],
        "distribution_count": 1,
        "distributions": [
            {
                "name": "example-dist",
                "version": "1.2.3",
            }
        ],
    }

    evidence_path = (
        evidence_dir
        / "NUITKA-COMPILATION-EVIDENCE.json"
    )

    evidence_path.write_text(
        json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "toolchain": {
            "nuitka": {
                "version": "2.7.0",
                "compilation_report_sha256": report_sha,
                "sanitized_evidence_file": (
                    "validation-evidence/"
                    "NUITKA-COMPILATION-EVIDENCE.json"
                ),
                "sanitized_evidence_sha256": _sha(
                    evidence_path
                ),
            }
        }
    }

    return release_dir, package_dir, manifest


def test_staged_nuitka_evidence_is_accepted(
    tmp_path: Path,
) -> None:
    release_dir, package_dir, manifest = _fixture(
        tmp_path
    )

    modules, distributions = validator._validate_nuitka_build_evidence(
        release_dir,
        package_dir,
        manifest,
    )

    assert modules == {
        "example": "example-dist",
        "example.helper": "example-dist",
    }
    assert distributions == {"example-dist": "1.2.3"}


def test_packaged_nuitka_evidence_is_rejected(
    tmp_path: Path,
) -> None:
    release_dir, package_dir, manifest = _fixture(
        tmp_path
    )

    packaged = (
        package_dir
        / "licenses"
        / "build-evidence"
        / "NUITKA-COMPILATION-EVIDENCE.json"
    )
    packaged.parent.mkdir(parents=True)
    packaged.write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        validator.ValidationError,
        match="validation-only and must not ship",
    ):
        validator._validate_nuitka_build_evidence(
            release_dir,
            package_dir,
            manifest,
        )


def test_compiled_distribution_missing_from_legal_inventory_fails_closed(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()

    with pytest.raises(
        validator.ValidationError,
        match="absent from legal inventory",
    ):
        validator._validate_dependency_evidence(
            package_dir,
            {"runtime_dependencies": []},
            {"example": "example-dist"},
            {"example-dist": "1.2.3"},
        )
