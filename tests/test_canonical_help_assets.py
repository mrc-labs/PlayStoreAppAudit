from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from types import ModuleType

import pytest

from playstore_app_audit import help_texts
from playstore_app_audit import resources as resource_ui
from playstore_app_audit.app import (
    _validate_canonical_help_images_for_smoke,
)

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "images"


def _validator_module() -> ModuleType:
    path = (
        ROOT
        / ".github"
        / "scripts"
        / "validate_canonical_help_resources.py"
    )

    spec = importlib.util.spec_from_file_location(
        "validate_canonical_help_resources",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )
    spec.loader.exec_module(module)

    return module


def _repo_text(relative: str) -> str:
    return (
        ROOT / relative
    ).read_text(
        encoding="utf-8"
    )


def _copy_canonical_set(
    destination: Path,
    *,
    skip: str | None = None,
) -> None:
    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    for filename in (
        resource_ui.CANONICAL_HELP_IMAGE_NAMES
    ):
        if filename == skip:
            continue

        shutil.copy2(
            CANONICAL / filename,
            destination / filename,
        )


def test_source_help_resolver_returns_committed_canonical_images() -> None:
    for filename, dimensions in (
        resource_ui
        .CANONICAL_HELP_IMAGE_DIMENSIONS
        .items()
    ):
        path = (
            resource_ui
            .canonical_help_image_path(
                filename
            )
        )

        assert path == (
            CANONICAL / filename
        ).resolve()

        assert path.is_file()
        assert path.stat().st_size > 8_000
        assert dimensions[0] > 0
        assert dimensions[1] > 0

        uri = (
            resource_ui
            .canonical_help_image_uri(
                filename
            )
        )

        assert uri.startswith("file:")
        assert filename in uri


def test_overview_html_reuses_exact_canonical_gallery() -> None:
    content = (
        help_texts
        .store_app_audit_overview_html()
    )

    assert content.count("<img ") == 4
    assert 'width="700"' not in content
    assert "What can Store App Audit help you answer?" in content
    assert "Not Found" in content
    assert "v2.0.0" in content
    assert "v2.1" in content

    for filename in (
        resource_ui.CANONICAL_HELP_IMAGE_NAMES
    ):
        assert filename in content


def test_readme_reuses_exact_canonical_gallery() -> None:
    readme = _repo_text(
        "README.md"
    )

    assert (
        "tools/generate_canonical_screenshots.py"
        in readme
    )
    assert (
        "fully synthetic fictional apps"
        in readme
    )

    for filename in (
        resource_ui.CANONICAL_HELP_IMAGE_NAMES
    ):
        relative = f"docs/images/{filename}"
        assert relative in readme


def test_packaged_help_validator_accepts_exact_canonical_bytes(
    tmp_path: Path,
) -> None:
    validator = _validator_module()
    package = tmp_path / "package"
    images = package / "help-images"

    _copy_canonical_set(images)

    found = validator.validate_help_resources(
        package,
        canonical_dir=CANONICAL,
    )

    assert set(found) == set(
        validator.EXPECTED_HELP_IMAGES
    )
    assert all(
        paths
        for paths in found.values()
    )


def test_packaged_help_validator_rejects_missing_image(
    tmp_path: Path,
) -> None:
    validator = _validator_module()
    package = tmp_path / "package"
    images = package / "help-images"
    missing = next(
        iter(
            resource_ui
            .CANONICAL_HELP_IMAGE_NAMES
        )
    )

    _copy_canonical_set(
        images,
        skip=missing,
    )

    with pytest.raises(
        RuntimeError,
        match="missing canonical Help image",
    ):
        validator.validate_help_resources(
            package,
            canonical_dir=CANONICAL,
        )


def test_packaged_help_validator_rejects_modified_bytes(
    tmp_path: Path,
) -> None:
    validator = _validator_module()
    package = tmp_path / "package"
    images = package / "help-images"

    _copy_canonical_set(images)

    filename = next(
        iter(
            resource_ui
            .CANONICAL_HELP_IMAGE_NAMES
        )
    )

    target = images / filename
    target.write_bytes(
        target.read_bytes()
        + b"modified"
    )

    with pytest.raises(
        RuntimeError,
        match="differs from canonical source",
    ):
        validator.validate_help_resources(
            package,
            canonical_dir=CANONICAL,
        )


def test_all_nuitka_packagers_include_canonical_help_images() -> None:
    option = (
        "--include-data-dir="
        "docs/images=help-images"
    )

    for relative in (
        ".github/scripts/build_windows_standalone.ps1",
        ".github/workflows/build-linux.yml",
        ".github/workflows/build-macos.yml",
    ):
        assert option in _repo_text(
            relative
        )


def test_all_packagers_validate_raw_and_roundtrip_help_resources() -> None:
    validator = (
        "validate_canonical_help_resources.py"
    )

    windows = _repo_text(
        ".github/scripts/build_windows_standalone.ps1"
    )

    assert validator in windows
    assert (
        "& $Python $ValidateCanonicalHelpResources `\n"
        "    $DistDir.FullName `"
        in windows
    )
    assert (
        "& $Python $ValidateCanonicalHelpResources `\n"
        "    $PackageDir `"
        in windows
    )

    linux = _repo_text(
        ".github/workflows/build-linux.yml"
    )

    assert linux.count(validator) == 2
    assert (
        f'{validator} "$STANDALONE_DIR"'
        in linux
    )
    assert (
        f'{validator} "$ROUNDTRIP_DIR"'
        in linux
    )

    macos = _repo_text(
        ".github/workflows/build-macos.yml"
    )

    assert macos.count(validator) == 2
    assert (
        f'{validator} "$APP"'
        in macos
    )
    assert (
        f'{validator} "$RAPP"'
        in macos
    )


def test_packaged_smoke_resolves_every_help_image() -> None:
    _validate_canonical_help_images_for_smoke()
