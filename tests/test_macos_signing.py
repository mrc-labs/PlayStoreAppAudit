from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import sign_macos_app as signing


def test_sort_inside_out_prefers_deeper_paths() -> None:
    paths = [
        Path("App.app/Contents/MacOS/app"),
        Path("App.app/Contents/Frameworks/QtCore.framework/Versions/A/QtCore"),
        Path("App.app/Contents/Frameworks/QtCore.framework"),
    ]

    ordered = signing._sort_inside_out(paths)

    assert ordered[0].name == "QtCore"
    assert ordered[-1].name == "app"


def test_production_codesign_uses_runtime_timestamp_and_keychain() -> None:
    command = signing._codesign_command(
        Path("App.app"),
        identity="ABCDEF",
        keychain=Path("release.keychain-db"),
        production=True,
    )

    assert command[:4] == [
        "codesign",
        "--force",
        "--sign",
        "ABCDEF",
    ]
    assert "--deep" not in command
    assert command[4:6] == ["--keychain", "release.keychain-db"]
    assert command[6:9] == ["--options", "runtime", "--timestamp"]
    assert command[-1] == "App.app"


def test_engineering_codesign_is_adhoc_without_runtime_timestamp() -> None:
    command = signing._codesign_command(
        Path("App.app"),
        identity="-",
        keychain=None,
        production=False,
    )

    assert command == [
        "codesign",
        "--force",
        "--sign",
        "-",
        "App.app",
    ]


def test_sign_app_signs_files_then_bundles_then_top_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "PlayStoreAppAudit.app"
    app.mkdir()
    binary = app / "Contents" / "MacOS" / "PlayStoreAppAudit"
    framework = app / "Contents" / "Frameworks" / "QtCore.framework"
    binary.parent.mkdir(parents=True)
    framework.mkdir(parents=True)
    binary.write_bytes(b"binary")

    monkeypatch.setattr(
        signing,
        "discover_macho_files",
        lambda _app: [binary],
    )
    monkeypatch.setattr(
        signing,
        "discover_nested_bundles",
        lambda _app: [framework],
    )

    commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        check: bool,
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(signing.subprocess, "run", fake_run)

    signing.sign_app(
        app,
        identity="ABCDEF",
        keychain=Path("release.keychain-db"),
        production=True,
    )

    assert commands[0][-1] == str(binary)
    assert commands[1][-1] == str(framework)
    assert commands[2][-1] == str(app.resolve())
    assert commands[3][:4] == [
        "codesign",
        "--verify",
        "--deep",
        "--strict",
    ]


def test_production_signing_requires_explicit_keychain(tmp_path: Path) -> None:
    app = tmp_path / "PlayStoreAppAudit.app"
    app.mkdir()

    with pytest.raises(RuntimeError, match="explicit keychain"):
        signing.sign_app(
            app,
            identity="ABCDEF",
            production=True,
        )
