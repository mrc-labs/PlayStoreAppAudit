from pathlib import Path

import prepare_release_legal_bundle as legal


def test_runtime_legal_root_for_flat_package(
    tmp_path: Path,
) -> None:
    package = tmp_path / "PlayStoreAppAudit"
    package.mkdir()

    assert legal._runtime_legal_root(package) == package


def test_runtime_legal_root_for_macos_app(
    tmp_path: Path,
) -> None:
    app = tmp_path / "PlayStoreAppAudit.app"
    resources = app / "Contents" / "Resources"
    resources.mkdir(parents=True)

    assert legal._runtime_legal_root(app) == resources


def test_macos_legal_payload_is_in_resources_and_not_inventory(
    tmp_path: Path,
) -> None:
    app = tmp_path / "PlayStoreAppAudit.app"
    executable = app / "Contents" / "MacOS" / "PlayStoreAppAudit"
    resources = app / "Contents" / "Resources"

    executable.parent.mkdir(parents=True)
    resources.mkdir(parents=True)

    executable.write_bytes(b"runtime")

    staged = tmp_path / "package-legal"
    staged.mkdir()

    (staged / "LICENSE").write_text(
        "project license",
        encoding="utf-8",
    )
    (staged / "THIRD_PARTY_NOTICES.md").write_text(
        "notices",
        encoding="utf-8",
    )
    (staged / "SOURCE-AVAILABILITY.md").write_text(
        "sources",
        encoding="utf-8",
    )

    licenses = staged / "licenses"
    licenses.mkdir()
    (licenses / "example.txt").write_text(
        "third-party license",
        encoding="utf-8",
    )

    legal._copy_package_legal_into_runtime(
        staged,
        app,
    )

    assert (resources / "LICENSE").is_file()
    assert (resources / "THIRD_PARTY_NOTICES.md").is_file()
    assert (resources / "SOURCE-AVAILABILITY.md").is_file()
    assert (resources / "licenses" / "example.txt").is_file()

    assert not (app / "LICENSE").exists()
    assert not (app / "licenses").exists()

    inventory = legal._runtime_inventory(app)
    paths = {
        item["path"]
        for item in inventory
    }

    assert "Contents/MacOS/PlayStoreAppAudit" in paths

    assert not any(
        path.startswith("Contents/Resources/licenses/")
        for path in paths
    )
    assert "Contents/Resources/LICENSE" not in paths
    assert (
        "Contents/Resources/THIRD_PARTY_NOTICES.md"
        not in paths
    )
    assert (
        "Contents/Resources/SOURCE-AVAILABILITY.md"
        not in paths
    )
