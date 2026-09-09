import json
from pathlib import Path
from types import SimpleNamespace

import prepare_release_legal_bundle as legal
import pytest


def _credential_distributions(monkeypatch) -> None:
    distributions = {
        "cryptography": SimpleNamespace(
            metadata={"Name": "cryptography"},
            version="50.0.1",
            files=[legal.metadata.PackagePath("cryptography/__init__.py")],
            requires=["cffi>=2.0.0"],
        ),
        "cffi": SimpleNamespace(
            metadata={"Name": "cffi"},
            version="2.1.1",
            files=[
                legal.metadata.PackagePath(
                    "_cffi_backend.cp313-win_amd64.pyd"
                ),
                legal.metadata.PackagePath("cffi/__init__.py"),
            ],
            requires=["pycparser"],
        ),
        "pycparser": SimpleNamespace(
            metadata={"Name": "pycparser"},
            version="3.0",
            files=[legal.metadata.PackagePath("pycparser/__init__.py")],
            requires=[],
        ),
    }
    monkeypatch.setattr(
        legal,
        "_project_dependency_names",
        lambda _root: ["cryptography"],
    )
    monkeypatch.setattr(
        legal.metadata,
        "distribution",
        lambda name: distributions[legal._normalize_dist_name(name)],
    )


def _credential_report() -> list[dict[str, str]]:
    return [
        {
            "name": "cryptography.hazmat.primitives.hashes",
            "kind": "CompiledPythonModule",
            "distribution": "cryptography",
        }
    ]


def _dependency_names(
    dependencies: list[legal.RuntimeDependencyEvidence],
) -> set[str]:
    return {
        legal._normalize_dist_name(item.distribution.metadata["Name"])
        for item in dependencies
    }


def test_cffi_is_retained_with_real_runtime_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _credential_distributions(monkeypatch)

    dependencies = legal._runtime_dependency_closure(
        tmp_path,
        ["_cffi_backend.pyd"],
        _credential_report(),
        {
            "cryptography": ("cryptography", "50.0.1"),
            "cffi": ("cffi", "2.1.1"),
        },
    )

    assert _dependency_names(dependencies) == {"cffi", "cryptography"}
    cffi = next(
        item
        for item in dependencies
        if legal._normalize_dist_name(item.distribution.metadata["Name"])
        == "cffi"
    )
    assert cffi.runtime_evidence == ("_cffi_backend.pyd",)


def test_pycparser_metadata_alone_does_not_make_it_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _credential_distributions(monkeypatch)

    dependencies = legal._runtime_dependency_closure(
        tmp_path,
        ["_cffi_backend.pyd"],
        _credential_report(),
        {
            "cryptography": ("cryptography", "50.0.1"),
            "cffi": ("cffi", "2.1.1"),
        },
    )

    assert "pycparser" not in _dependency_names(dependencies)


def test_pycparser_is_retained_with_real_runtime_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _credential_distributions(monkeypatch)

    dependencies = legal._runtime_dependency_closure(
        tmp_path,
        ["_cffi_backend.pyd", "pycparser/__init__.py"],
        _credential_report(),
        {
            "cryptography": ("cryptography", "50.0.1"),
            "cffi": ("cffi", "2.1.1"),
        },
    )

    assert _dependency_names(dependencies) == {
        "cffi",
        "cryptography",
        "pycparser",
    }


def test_direct_dependency_without_runtime_evidence_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _credential_distributions(monkeypatch)

    with pytest.raises(
        RuntimeError,
        match="direct dependency cryptography 50.0.1",
    ):
        legal._runtime_dependency_closure(
            tmp_path,
            ["_cffi_backend.pyd"],
            [],
            {},
        )


def test_unknown_real_nuitka_dependency_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _credential_distributions(monkeypatch)

    report = _credential_report()
    report.append(
        {
            "name": "unknown_runtime",
            "kind": "CompiledPythonModule",
            "distribution": "unknown-distribution",
        }
    )

    with pytest.raises(
        RuntimeError,
        match="undeclared runtime distribution unknown-distribution",
    ):
        legal._runtime_dependency_closure(
            tmp_path,
            ["_cffi_backend.pyd"],
            report,
            {
                "cryptography": ("cryptography", "50.0.1"),
                "cffi": ("cffi", "2.1.1"),
                "unknown-distribution": (
                    "unknown-distribution",
                    "1.0",
                ),
            },
        )


def test_ambiguous_packaged_dependency_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _credential_distributions(monkeypatch)
    original = legal._distribution_top_level_names

    def shared_transitive_top_level(distribution) -> list[str]:
        if distribution.metadata["Name"] in {"cffi", "pycparser"}:
            return ["shared_runtime"]
        return original(distribution)

    monkeypatch.setattr(
        legal,
        "_distribution_top_level_names",
        shared_transitive_top_level,
    )

    with pytest.raises(
        RuntimeError,
        match="Ambiguous packaged runtime evidence",
    ):
        legal._runtime_dependency_closure(
            tmp_path,
            ["shared_runtime/__init__.py"],
            _credential_report(),
            {
                "cryptography": ("cryptography", "50.0.1"),
            },
        )


def test_nuitka_report_preserves_distribution_inventory(
    tmp_path: Path,
) -> None:
    report = tmp_path / "compilation-report.xml"
    report.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<nuitka-compilation-report nuitka_version="4.1.3">
  <module name="_cffi_backend" kind="PythonExtensionModule"
          distribution="cffi" />
  <distributions>
    <distribution name="cffi" version="2.1.1" />
  </distributions>
</nuitka-compilation-report>
""",
        encoding="utf-8",
    )

    version, modules, distributions = (
        legal._load_nuitka_compilation_report(report)
    )

    assert version == "4.1.3"
    assert modules == [
        {
            "name": "_cffi_backend",
            "kind": "PythonExtensionModule",
            "distribution": "cffi",
        }
    ]
    assert distributions == {"cffi": ("cffi", "2.1.1")}



def test_cffi_abi_tagged_extension_has_runtime_evidence() -> None:
    cffi = legal.metadata.distribution("cffi")
    top_level = legal._distribution_top_level_names(cffi)

    assert "_cffi_backend" in top_level
    assert not any(
        name.startswith("_cffi_backend.")
        for name in top_level
    )
    assert legal._runtime_evidence(
        ["_cffi_backend.pyd"],
        top_level,
    ) == ["_cffi_backend.pyd"]


def test_runtime_evidence_still_fails_for_absent_distribution() -> None:
    assert legal._runtime_evidence(
        ["unrelated_module.pyd"],
        ["missing_dependency"],
    ) == []


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
