from pathlib import Path

import pytest
import validate_release_legal_bundle as validator


def _legal_trees(tmp_path: Path) -> tuple[Path, Path]:
    package = tmp_path / "package"
    staging = tmp_path / "package-legal"

    package.mkdir()
    staging.mkdir()

    for name in validator.REQUIRED_PACKAGE_FILES:
        content = f"{name}\n".encode()
        (package / name).write_bytes(content)
        (staging / name).write_bytes(content)

    (package / "licenses").mkdir()
    (staging / "licenses").mkdir()

    (staging / "LEGAL-MANIFEST.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    return package, staging


def test_staging_only_legal_manifest_is_accepted(
    tmp_path: Path,
) -> None:
    package, staging = _legal_trees(tmp_path)

    validator._validate_required_files(
        package,
        staging,
    )


def test_packaged_legal_manifest_is_rejected(
    tmp_path: Path,
) -> None:
    package, staging = _legal_trees(tmp_path)

    (package / "LEGAL-MANIFEST.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        validator.ValidationError,
        match="must not ship",
    ):
        validator._validate_required_files(
            package,
            staging,
        )