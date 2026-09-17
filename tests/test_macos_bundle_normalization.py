from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import normalize_macos_bundle as bundle
import pytest

PUBLIC_XML = b"<resources><public name='test' id='0x1'/></resources>\n"


def _app_with_certifi(tmp_path: Path) -> tuple[Path, bytes]:
    app = tmp_path / "PlayStoreAppAudit.app"
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    (macos / "certifi").mkdir(parents=True)
    resources.mkdir()
    (macos / "main").write_bytes(bytes.fromhex("cffaedfe") + b"executable")
    original = b"test CA bundle\nkeep these bytes exactly\n"
    (macos / "certifi" / "cacert.pem").write_bytes(original)
    public_dir = macos / "pyaxmlparser" / "resources"
    public_dir.mkdir(parents=True)
    (public_dir / "public.xml").write_bytes(PUBLIC_XML)
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


def test_certifi_link_target_is_native_relative_path() -> None:
    target = Path(bundle.CERTIFI_LINK_TARGET)

    assert os.path.join("..", "Resources", "certifi") == bundle.CERTIFI_LINK_TARGET
    assert not target.is_absolute()
    assert target.parts == ("..", "Resources", "certifi")
    assert target.as_posix() == "../Resources/certifi"


def test_pyaxmlparser_link_target_is_native_relative_path() -> None:
    target = Path(bundle.PYAXMLPARSER_LINK_TARGET)

    assert os.path.join("..", "..", "Resources", "pyaxmlparser", "resources") == (
        bundle.PYAXMLPARSER_LINK_TARGET
    )
    assert not target.is_absolute()
    assert target.parts == ("..", "..", "Resources", "pyaxmlparser", "resources")
    assert target.as_posix() == "../../Resources/pyaxmlparser/resources"


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
    assert Path(os.readlink(link)).parts == ("..", "Resources", "certifi")
    assert (link / "cacert.pem").read_bytes() == original
    assert bundle.normalize_bundle(app) == digest


def test_pyaxmlparser_relocation_preserves_bytes_hash_and_runtime_lookup(
    tmp_path: Path,
) -> None:
    _require_directory_symlink(tmp_path)
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    source = macos / "pyaxmlparser" / "resources" / "public.xml"
    original_hash = sha256(source.read_bytes()).hexdigest()

    bundle.normalize_bundle(app)

    link = macos / "pyaxmlparser" / "resources"
    physical = app / "Contents" / "Resources" / "pyaxmlparser" / "resources" / "public.xml"
    assert (macos / "pyaxmlparser").is_dir()
    assert not (macos / "pyaxmlparser").is_symlink()
    assert link.is_symlink()
    assert Path(os.readlink(link)).parts == (
        "..", "..", "Resources", "pyaxmlparser", "resources"
    )
    assert physical.is_file() and not physical.is_symlink()
    assert physical.read_bytes() == (link / "public.xml").read_bytes() == PUBLIC_XML
    assert sha256(physical.read_bytes()).hexdigest() == original_hash
    assert bundle._non_code_macos_files(macos) == []
    bundle.normalize_bundle(app)
    assert physical.read_bytes() == PUBLIC_XML


def test_pyaxmlparser_destination_collision_preserves_source(tmp_path: Path) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    destination = resources / "pyaxmlparser" / "resources"
    destination.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="destination already exists"):
        bundle._normalize_pyaxmlparser(macos, resources)

    assert (macos / "pyaxmlparser" / "resources" / "public.xml").read_bytes() == PUBLIC_XML


def test_pyaxmlparser_macho_is_not_moved(tmp_path: Path) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    code = macos / "pyaxmlparser" / "resources" / "unexpected.dylib"
    code.write_bytes(bytes.fromhex("feedfacf") + b"Mach-O code")

    with pytest.raises(RuntimeError, match="Refusing to move Mach-O code"):
        bundle._normalize_pyaxmlparser(macos, resources)

    assert code.is_file()
    assert not (resources / "pyaxmlparser").exists()


def test_pyaxmlparser_rejects_unexpected_symlink(tmp_path: Path) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    data = macos / "pyaxmlparser" / "resources"
    (data / "nested").mkdir()
    link = data / "unexpected-link"
    try:
        link.symlink_to("nested", target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks require a privilege unavailable here")

    with pytest.raises(RuntimeError, match="contains a symlink"):
        bundle._normalize_pyaxmlparser(macos, resources)

    assert not (resources / "pyaxmlparser").exists()


def test_pyaxmlparser_rejects_non_regular_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    payload = macos / "pyaxmlparser" / "resources" / "unexpected.bin"
    payload.write_bytes(b"data")
    original_is_file = Path.is_file

    def fake_is_file(path: Path) -> bool:
        if path == payload:
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", fake_is_file)

    with pytest.raises(RuntimeError, match="contains a non-regular file"):
        bundle._normalize_pyaxmlparser(macos, resources)

    assert not (resources / "pyaxmlparser").exists()


def test_pyaxmlparser_link_creation_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    link = macos / "pyaxmlparser" / "resources"
    requested: list[tuple[Path, str, bool]] = []

    def reject_link(path: Path, target: str, *, target_is_directory: bool) -> None:
        assert (resources / "pyaxmlparser" / "resources" / "public.xml").read_bytes() == PUBLIC_XML
        requested.append((path, target, target_is_directory))
        raise OSError("symlink unavailable")

    monkeypatch.setattr(Path, "symlink_to", reject_link)

    with pytest.raises(OSError, match="symlink unavailable"):
        bundle._normalize_pyaxmlparser(macos, resources)

    assert requested == [(link, bundle.PYAXMLPARSER_LINK_TARGET, True)]
    assert (link / "public.xml").read_bytes() == PUBLIC_XML
    assert not (resources / "pyaxmlparser").exists()


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

    assert requested == [(link, bundle.CERTIFI_LINK_TARGET, True)]
    assert (link / "cacert.pem").read_bytes() == original
    assert not (app / "Contents" / "Resources" / "certifi").exists()


def test_help_images_relocate_to_resources_idempotently(
    tmp_path: Path,
) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    source = macos / "help-images"
    source.mkdir()

    expected: dict[str, bytes] = {}

    for index, filename in enumerate(
        bundle.HELP_IMAGE_NAMES,
        start=1,
    ):
        payload = (
            f"synthetic help image {index}: {filename}\n"
        ).encode()
        expected[filename] = payload
        (source / filename).write_bytes(payload)

    bundle._normalize_help_images(
        macos,
        resources,
    )

    destination = resources / "help-images"

    assert not source.exists()
    assert destination.is_dir()

    for filename, payload in expected.items():
        assert (
            destination / filename
        ).read_bytes() == payload

    bundle._normalize_help_images(
        macos,
        resources,
    )

    assert destination.is_dir()


def test_non_code_survey_reports_other_macos_resources(tmp_path: Path) -> None:
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    (macos / "other-package").mkdir()
    (macos / "other-package" / "data.txt").write_text("other resource")

    assert bundle._non_code_macos_files(macos) == [
        "certifi/cacert.pem",
        "other-package/data.txt",
        "pyaxmlparser/resources/public.xml",
    ]


def test_unknown_payload_still_fails_final_survey(tmp_path: Path) -> None:
    _require_directory_symlink(tmp_path)
    app, _ = _app_with_certifi(tmp_path)
    macos = app / "Contents" / "MacOS"
    unknown = macos / "other-package" / "data.txt"
    unknown.parent.mkdir()
    unknown.write_text("other resource")

    with pytest.raises(RuntimeError, match="other-package/data.txt"):
        bundle.normalize_bundle(app)

    assert bundle._non_code_macos_files(macos) == ["other-package/data.txt"]


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
    assert 'PYAXMLPARSER_BEFORE="$(shasum -a 256 "$APP/Contents/MacOS/pyaxmlparser/resources/public.xml"' in workflow
    assert 'test "$(readlink "$PYAXMLPARSER_LINK")" = "../../Resources/pyaxmlparser/resources"' in workflow
    assert 'cmp "$PYAXMLPARSER_LINK/public.xml" "$PYAXMLPARSER_RESOURCE"' in workflow
    assert 'test "$(readlink "$RAPP/Contents/MacOS/pyaxmlparser/resources")" = "../../Resources/pyaxmlparser/resources"' in workflow
    assert 'cmp "$RAPP/Contents/MacOS/pyaxmlparser/resources/public.xml"' in workflow
