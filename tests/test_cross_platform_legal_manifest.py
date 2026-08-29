import json
from pathlib import Path

import prepare_release_legal_bundle as legal


def test_credential_crypto_dependency_closure_has_legal_material() -> None:
    root = Path(__file__).resolve().parents[1]
    distributions = {
        legal._normalize_dist_name(distribution.metadata["Name"]): distribution
        for distribution in legal._runtime_dependency_closure(root, [])
    }

    for name in ("cryptography", "cffi", "pycparser"):
        assert name in distributions
        assert legal._distribution_license_files(distributions[name])


def test_release_platform_mapping(monkeypatch) -> None:
    cases = {
        "Windows": "windows",
        "Linux": "linux",
        "Darwin": "macos",
    }

    for system, expected in cases.items():
        monkeypatch.setattr(
            legal.platform,
            "system",
            lambda value=system: value,
        )
        assert legal._host_platform_key() == expected


def test_openssl_runtime_detection_is_cross_platform() -> None:
    present = {
        "libssl-3-x64.dll",
        "libcrypto-3-arm64.dll",
        "libssl.so",
        "libssl.so.3",
        "libcrypto.so.3",
        "libssl.3.dylib",
        "libcrypto.3.dylib",
    }

    for name in present:
        assert legal._is_openssl_runtime_name(name)

    assert not legal._is_openssl_runtime_name("ssl.py")
    assert not legal._is_openssl_runtime_name("libsomething.so")


def test_third_party_notice_is_platform_neutral(
    tmp_path: Path,
) -> None:
    legal._write_third_party_notices(
        package_legal_dir=tmp_path,
        qt_version="6.11.1",
        dependencies=[],
        cpython_version="3.13.0",
        cpython_license="licenses/python/LICENSE.txt",
        nuitka_version="4.1.3",
        nuitka_files=["licenses/nuitka/LICENSE.txt"],
        openssl=None,
    )

    text = (
        tmp_path / "THIRD_PARTY_NOTICES.md"
    ).read_text(encoding="utf-8")

    assert "Windows standalone ZIP" not in text
    assert "The standalone package keeps" in text
    assert "one inseparable executable" in text


def test_legal_manifest_policy_is_platform_neutral() -> None:
    root = Path(__file__).resolve().parents[1]

    prepare = (
        root / ".github/scripts/prepare_release_legal_bundle.py"
    ).read_text(encoding="utf-8")

    validator = (
        root / ".github/scripts/validate_release_legal_bundle.py"
    ).read_text(encoding="utf-8")

    assert 'MANIFEST_SCHEMA_VERSION = 3' in prepare
    assert '"platform": "windows"' not in prepare

    assert "final_msvc_revalidation_required" not in prepare
    assert "final_msvc_revalidation_required" not in validator

    assert (
        "final_artifact_revalidation_required"
        in prepare
    )
    assert (
        "final_artifact_revalidation_required"
        in validator
    )

    assert "_bundled_adb_paths(package_dir)" in validator



def test_refresh_runtime_evidence_after_package_mutation(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "package"
    release_dir = tmp_path / "release"
    staged_dir = release_dir / "package-legal"

    package_dir.mkdir()
    staged_dir.mkdir(parents=True)

    executable = package_dir / "PlayStoreAppAudit"
    executable.write_bytes(b"unsigned")

    build_info = package_dir / "BUILD-INFO.txt"
    build_info.write_text(
        "Application version: 1.3.0\n",
        encoding="utf-8",
    )

    licenses = package_dir / "licenses"
    licenses.mkdir()
    (licenses / "ignored.txt").write_text(
        "legal",
        encoding="utf-8",
    )

    manifest_path = staged_dir / "LEGAL-MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": (
                    legal.MANIFEST_SCHEMA_VERSION
                ),
                "package": {
                    "directory_name": "old",
                    "platform": "old",
                    "architecture": "old",
                    "runtime_file_count": 0,
                    "runtime_inventory_sha256": "",
                    "runtime_inventory": [],
                    "build_info": None,
                },
            }
        ),
        encoding="utf-8",
    )

    # Simulate a signing/package mutation after initial
    # legal preparation.
    executable.write_bytes(b"signed-payload")

    legal._refresh_runtime_evidence(
        package_dir,
        release_dir,
    )

    refreshed = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    package = refreshed["package"]
    inventory = legal._runtime_inventory(package_dir)

    assert package["directory_name"] == package_dir.name
    assert package["platform"] == legal._host_platform_key()
    assert package["architecture"] == legal.platform.machine()
    assert package["runtime_file_count"] == len(inventory)
    assert package["runtime_inventory"] == inventory

    assert package["runtime_inventory_sha256"] == (
        legal._canonical_json_sha256(inventory)
    )

    assert package["build_info"]["path"] == "BUILD-INFO.txt"

    assert not any(
        item["path"].startswith("licenses/")
        for item in inventory
    )


def test_refresh_runtime_evidence_cli_is_available() -> None:
    root = Path(__file__).resolve().parents[1]

    script = (
        root
        / ".github/scripts/prepare_release_legal_bundle.py"
    ).read_text(encoding="utf-8")

    assert "--refresh-runtime-evidence" in script
    assert (
        "--nuitka-report is required when preparing"
        in script
    )

def test_cpython_license_prefers_local_release_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    local_license = runtime / "LICENSE.txt"
    local_license.write_text(
        "LOCAL CPYTHON LICENSE\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        legal.sys,
        "base_prefix",
        str(runtime),
    )
    monkeypatch.setattr(
        legal.sys,
        "prefix",
        str(runtime),
    )

    def unexpected_download(url: str) -> str:
        raise AssertionError(
            f"Unexpected network fallback: {url}"
        )

    monkeypatch.setattr(
        legal,
        "_download_text",
        unexpected_download,
    )

    licenses_root = tmp_path / "licenses"

    bundled = legal._copy_cpython_license(
        licenses_root,
    )

    assert bundled == "licenses/cpython/LICENSE.txt"
    assert (
        licenses_root / "cpython" / "LICENSE.txt"
    ).read_text(encoding="utf-8") == (
        "LOCAL CPYTHON LICENSE\n"
    )


def test_cpython_license_falls_back_to_exact_upstream_tag(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    monkeypatch.setattr(
        legal.sys,
        "base_prefix",
        str(runtime),
    )
    monkeypatch.setattr(
        legal.sys,
        "prefix",
        str(runtime),
    )
    monkeypatch.setattr(
        legal.platform,
        "python_version",
        lambda: "3.13.15",
    )

    requested_urls: list[str] = []

    upstream_license = (
        "CPython license\n"
        + "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2\n"
        + ("license text\n" * 100)
    )

    def fake_download(url: str) -> str:
        requested_urls.append(url)
        return upstream_license

    monkeypatch.setattr(
        legal,
        "_download_text",
        fake_download,
    )

    licenses_root = tmp_path / "licenses"

    bundled = legal._copy_cpython_license(
        licenses_root,
    )

    assert requested_urls == [
        "https://raw.githubusercontent.com/python/cpython/"
        "v3.13.15/LICENSE"
    ]
    assert bundled == "licenses/cpython/LICENSE.txt"

    destination = (
        licenses_root / "cpython" / "LICENSE.txt"
    )

    assert destination.read_text(
        encoding="utf-8"
    ) == upstream_license
