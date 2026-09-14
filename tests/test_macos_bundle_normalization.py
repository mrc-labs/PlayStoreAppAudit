from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import normalize_macos_bundle as bundle
import pytest


def _app_with_certifi(tmp_path: Path) -> tuple[Path, bytes]:
    app = tmp_path / "PlayStoreAppAudit.app"
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    (macos / "certifi").mkdir(parents=True)
    resources.mkdir()
    (macos / "main").write_bytes(bytes.fromhex("cffaedfe") + b"executable")
    original = b"test CA bundle\nkeep these bytes exactly\n"
    (macos / "certifi" / "cacert.pem").write_bytes(original)
    return app, original


def _require_directory_symlink(tmp_path: Path) -> None:
    target = tmp_path / "symlink-target"
    target.mkdir()
    link = tmp_path / "symlink-probe"
    try:
        link.symlink_to("symlink-target", target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks require a privilege unavailable here")
    link.unlink()


def test_certifi_relocation_preserves_bytes_and_runtime_lookup(tmp_path: Path) -> None:
    _require_directory_symlink(tmp_path)
    app, original = _app_with_certifi(tmp_path)

    digest = bundle.normalize_bundle(app)

    link = app / "Contents" / "MacOS" / "certifi"
    resource = app / "Contents" / "Resources" / "certifi" / "cacert.pem"
    assert digest == sha256(original).hexdigest()
    assert resource.is_file() and not resource.is_symlink()
    assert resource.read_bytes() == original
    assert link.is_symlink()
    assert os.readlink(link) == "../Resources/certifi"
    assert (link / "cacert.pem").read_bytes() == original
    assert bundle.normalize_bundle(app) == digest


def test_existing_resource_destination_fails_without_moving_data(tmp_path: Path) -> None:
    app, original = _app_with_certifi(tmp_path)
    destination = app / "Contents" / "Resources" / "certifi"
    destination.mkdir()

    with pytest.raises(RuntimeError, match="destination already exists"):
        bundle.normalize_bundle(app)

    assert (app / "Contents" / "MacOS" / "certifi" / "cacert.pem").read_bytes() == original


def test_inconsistent_existing_resource_state_fails(tmp_path: Path) -> None:
    app, _ = _app_with_certifi(tmp_path)
    source = app / "Contents" / "MacOS" / "certifi"
    source.rename(app / "Contents" / "Resources" / "certifi")

    with pytest.raises(RuntimeError, match="Expected Nuitka certifi data directory"):
        bundle.normalize_bundle(app)


def test_macho_inside_certifi_is_not_moved(tmp_path: Path) -> None:
    app, original = _app_with_certifi(tmp_path)
    code = app / "Contents" / "MacOS" / "certifi" / "unexpected.dylib"
    code.write_bytes(bytes.fromhex("cafebabe") + b"universal code")

    with pytest.raises(RuntimeError, match="Refusing to move Mach-O code"):
        bundle.normalize_bundle(app)

    assert code.is_file()
    assert (code.parent / "cacert.pem").read_bytes() == original
    assert not (app / "Contents" / "Resources" / "certifi").exists()


def test_link_creation_failure_rolls_back_and_uses_relative_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, original = _app_with_certifi(tmp_path)
    link = app / "Contents" / "MacOS" / "certifi"
    requested: list[tuple[Path, str, bool]] = []

    def reject_link(path: Path, target: str, *, target_is_directory: bool) -> None:
        assert (app / "Contents" / "Resources" / "certifi" / "cacert.pem").read_bytes() == original
        requested.append((path, target, target_is_directory))
        raise OSError("symlink unavailable")

    monkeypatch.setattr(Path, "symlink_to", reject_link)

    with pytest.raises(OSError, match="symlink unavailable"):
        bundle.normalize_bundle(app)

    assert requested == [(link, "../Resources/certifi", True)]
    assert (link / "cacert.pem").read_bytes() == original
    assert not (app / "Contents" / "Resources" / "certifi").exists()


def test_non_code_survey_reports_other_macos_resources(tmp_path: Path) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    (macos / "other-package").mkdir()
    (macos / "other-package" / "data.txt").write_text("other resource")

    assert bundle._non_code_macos_files(macos) == [
        "certifi/cacert.pem",
        "other-package/data.txt",
    ]


def test_workflow_normalizes_before_legal_inventory_and_signing() -> None:
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-macos.yml"
    ).read_text(encoding="utf-8")

    normalize = workflow.index('python .github/scripts/normalize_macos_bundle.py --app "$APP"')
    legal = workflow.index('python .github/scripts/prepare_release_legal_bundle.py')
    sign = workflow.index('python .github/scripts/sign_macos_app.py')
    assert normalize < legal < sign
    assert 'test "$(readlink "$CERTIFI_LINK")" = "../Resources/certifi"' in workflow
    assert 'test "$(shasum -a 256 "$CERTIFI_RESOURCE"' in workflow
    assert 'test -L "$RAPP/Contents/MacOS/certifi"' in workflow
    assert 'cmp "$RAPP/Contents/MacOS/certifi/cacert.pem"' in workflow
