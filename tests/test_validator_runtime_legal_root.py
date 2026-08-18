from pathlib import Path

import validate_release_legal_bundle as validator


def _write_legal_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    (root / "LICENSE").write_text(
        "license",
        encoding="utf-8",
    )
    (root / "THIRD_PARTY_NOTICES.md").write_text(
        "notices",
        encoding="utf-8",
    )
    (root / "SOURCE-AVAILABILITY.md").write_text(
        "sources",
        encoding="utf-8",
    )

    licenses = root / "licenses"
    licenses.mkdir()
    (licenses / "example.txt").write_text(
        "third-party",
        encoding="utf-8",
    )


def test_validator_reads_macos_legal_files_from_resources(
    tmp_path: Path,
) -> None:
    app = tmp_path / "PlayStoreAppAudit.app"
    resources = app / "Contents" / "Resources"
    executable = app / "Contents" / "MacOS" / "PlayStoreAppAudit"

    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"runtime")

    staged = tmp_path / "package-legal"
    _write_legal_tree(staged)

    (staged / "LEGAL-MANIFEST.json").write_text(
        "{}",
        encoding="utf-8",
    )

    _write_legal_tree(resources)

    validator._validate_required_files(
        app,
        staged,
    )
    validator._validate_markdown_paths(app)
    validator._validate_staged_tree(
        app,
        staged,
    )

    assert not (app / "LICENSE").exists()
    assert not (app / "licenses").exists()


def test_validator_legal_path_is_flat_for_normal_package(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()

    assert validator._runtime_legal_path(
        package,
        "licenses/example.txt",
    ) == package / "licenses" / "example.txt"


def test_validator_legal_path_is_resources_for_macos(
    tmp_path: Path,
) -> None:
    app = tmp_path / "PlayStoreAppAudit.app"
    resources = app / "Contents" / "Resources"
    resources.mkdir(parents=True)

    assert validator._runtime_legal_path(
        app,
        "licenses/example.txt",
    ) == resources / "licenses" / "example.txt"
