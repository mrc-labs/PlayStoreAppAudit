from __future__ import annotations

from pathlib import Path

import preflight_release_legal_material as preflight
import prepare_release_legal_bundle as legal
import pytest

ROOT = Path(__file__).resolve().parents[1]
DIGEST = "0123456789abcdef" * 4


def _source_spec(component: str, version: str) -> legal.SourceAssetSpec:
    if component == "certifi":
        filename = f"certifi-{version}.tar.gz"
    else:
        filename = f"{component}-everywhere-src-{version}.tar.xz"

    return legal.SourceAssetSpec(
        component=component,
        filename=filename,
        url=f"https://example.invalid/{filename}",
        sha256=DIGEST,
        provenance_url=f"https://example.invalid/{filename}.meta4",
    )


def _fake_cpython_license(licenses_root: Path) -> str:
    destination = licenses_root / "cpython" / "LICENSE.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "Python Software Foundation license\n" + ("legal text\n" * 200),
        encoding="utf-8",
    )
    return "licenses/cpython/LICENSE.txt"


def test_preflight_resolves_deterministic_legal_prerequisites(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions = {
        "PySide6-Essentials": "6.11.1",
        "shiboken6": "6.11.1",
        "certifi": "2026.8.3",
    }

    monkeypatch.setattr(
        preflight.metadata,
        "version",
        lambda name: versions[name],
    )
    monkeypatch.setattr(
        legal,
        "_qt_source_spec",
        lambda component, version: _source_spec(component, version),
    )
    monkeypatch.setattr(
        legal,
        "_certifi_source_spec",
        lambda version: _source_spec("certifi", version),
    )
    monkeypatch.setattr(
        legal,
        "_copy_cpython_license",
        _fake_cpython_license,
    )
    monkeypatch.setattr(
        legal,
        "_copy_nuitka_legal_files",
        lambda _root: (
            "4.1.3",
            [
                "licenses/nuitka/LICENSE-runtime.txt",
                "licenses/nuitka/LICENSE.txt",
                "licenses/nuitka/NOTICE.txt",
            ],
        ),
    )

    result = preflight.run_preflight(
        ROOT,
        expected_nuitka_version="4.1.3",
    )

    assert result["project_version"] == "1.7.0"
    assert result["pyside6_essentials_version"] == "6.11.1"
    assert result["shiboken6_version"] == "6.11.1"
    assert result["nuitka_version"] == "4.1.3"
    assert result["cpython_license"] == "resolved"

    components = {
        item["component"]
        for item in result["source_assets"]
    }
    assert components == {
        "pyside-setup",
        "qtbase",
        "qtimageformats",
        "qtsvg",
        "certifi",
    }


def test_preflight_rejects_pyside_shiboken_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions = {
        "PySide6-Essentials": "6.11.1",
        "shiboken6": "6.11.0",
    }
    monkeypatch.setattr(
        preflight.metadata,
        "version",
        lambda name: versions[name],
    )

    with pytest.raises(
        RuntimeError,
        match="PySide6-Essentials/shiboken6 version mismatch",
    ):
        preflight.run_preflight(
            ROOT,
            expected_nuitka_version="4.1.3",
        )


def test_preflight_rejects_wrong_nuitka_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions = {
        "PySide6-Essentials": "6.11.1",
        "shiboken6": "6.11.1",
        "certifi": "2026.8.3",
    }

    monkeypatch.setattr(
        preflight.metadata,
        "version",
        lambda name: versions[name],
    )
    monkeypatch.setattr(
        legal,
        "_qt_source_spec",
        lambda component, version: _source_spec(component, version),
    )
    monkeypatch.setattr(
        legal,
        "_certifi_source_spec",
        lambda version: _source_spec("certifi", version),
    )
    monkeypatch.setattr(
        legal,
        "_copy_cpython_license",
        _fake_cpython_license,
    )
    monkeypatch.setattr(
        legal,
        "_copy_nuitka_legal_files",
        lambda _root: (
            "4.1.2",
            ["one", "two", "three"],
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Installed Nuitka version does not match",
    ):
        preflight.run_preflight(
            ROOT,
            expected_nuitka_version="4.1.3",
        )


def test_exact_pyside_pin_is_required(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example"
dependencies = ["PySide6-Essentials>=6.11"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="exactly one exact PySide6-Essentials==VERSION",
    ):
        preflight._read_exact_pyside_pin(tmp_path)
