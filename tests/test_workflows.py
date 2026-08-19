from __future__ import annotations

from pathlib import Path


def test_windows_release_build_is_manual_and_sha_guarded() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-windows-exe.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow

    assert "default: x64" in workflow
    assert "- arm64" in workflow
    assert "- both" in workflow

    assert "expected_sha:" in workflow
    assert "required: true" in workflow
    assert "EXPECTED_SHA: ${{ inputs.expected_sha }}" in workflow
    assert "DISPATCH_SHA: ${{ github.sha }}" in workflow
    assert "ref: ${{ github.sha }}" in workflow

    assert "github.event_name == 'push'" not in workflow
    assert "'0x8664'" in workflow


def test_quality_runs_on_pull_requests_and_relevant_main_pushes() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/quality.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert workflow.count("branches: [main]") == 2
    assert '".github/workflows/*.yml"' in workflow
    assert "github.event.pull_request.number || github.ref" in workflow
    assert "cancel-in-progress: true" in workflow

    assert 'python-version:' in workflow
    assert '- "3.13"' in workflow
    assert '- "3.14"' in workflow
    assert "python-version: ${{ matrix.python-version }}" in workflow
    assert "EXPECTED_PYTHON: ${{ matrix.python-version }}" in workflow


def test_desktop_release_build_is_manual_and_sha_guarded() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-macos-linux.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow

    assert "expected_sha:" in workflow
    assert "required: true" in workflow

    assert workflow.count(
        "EXPECTED_SHA: ${{ inputs.expected_sha }}"
    ) == 2
    assert workflow.count(
        "DISPATCH_SHA: ${{ github.sha }}"
    ) == 2
    assert workflow.count(
        "ref: ${{ github.sha }}"
    ) == 2
    assert workflow.count(
        "Verify requested build commit"
    ) == 2

    assert "STOP before expensive build work." in workflow


def test_linux_release_keeps_shared_runtime_replaceable() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-macos-linux.yml"
    ).read_text(encoding="utf-8")

    linux = workflow.split("  build-macos:", 1)[0]

    assert "p['nuitka']['mode']='standalone'" in linux
    assert "p['nuitka']['mode']='onefile'" not in linux

    assert "STANDALONE_DIR=" in linux
    assert 'cp -a "$STANDALONE_DIR/." "$PACKAGE_DIR/"' in linux

    assert "libQt6Core.so*" in linux
    assert "libpyside6*.so*" in linux
    assert "libshiboken6*.so*" in linux

    assert 'ROUNDTRIP_DIR="roundtrip/$PACKAGE_NAME"' in linux
    assert 'ROUNDTRIP_BIN="$ROUNDTRIP_DIR/PlayStoreAppAudit"' in linux

    assert "unzip" in linux
    assert "zip" in linux


def test_desktop_release_pins_nuitka_and_emits_report() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-macos-linux.yml"
    ).read_text(encoding="utf-8")

    assert workflow.count(
        'pip install -r requirements-dev.txt "Nuitka==4.1.3"'
    ) == 2

    assert workflow.count(
        "--report=compilation-report.xml"
    ) == 2

    assert workflow.count(
        "test -s compilation-report.xml"
    ) == 2



def test_linux_release_runs_legal_gate_before_zip() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-macos-linux.yml"
    ).read_text(encoding="utf-8")

    linux = workflow.split("  build-macos:", 1)[0]

    assert linux.count(
        "prepare_release_legal_bundle.py"
    ) == 1
    assert linux.count(
        "validate_release_legal_bundle.py"
    ) == 1

    assert (
        '--nuitka-report "$PWD/compilation-report.xml"'
        in linux
    )
    assert "--inject" in linux
    assert "--public" in linux

    assert (
        'LEGAL_RELEASE_DIR="$PWD/artifact/'
        'legal-release-v${APP_VERSION}"'
        in linux
    )

    prepare = linux.index(
        "prepare_release_legal_bundle.py"
    )
    validate = linux.index(
        "validate_release_legal_bundle.py"
    )
    archive = linux.index(
        'ARCHIVE="$PWD/artifact/$PACKAGE_NAME.zip"'
    )
    roundtrip = linux.index(
        'test -f "$ROUNDTRIP_DIR/LICENSE"'
    )

    assert prepare < validate < archive < roundtrip

    assert 'test -f "$PACKAGE_DIR/LICENSE"' in linux
    assert (
        'test ! -e "$PACKAGE_DIR/LEGAL-MANIFEST.json"'
        in linux
    )
    assert 'test -f "$ROUNDTRIP_DIR/LICENSE"' in linux
    assert (
        'test ! -e "$ROUNDTRIP_DIR/LEGAL-MANIFEST.json"'
        in linux
    )



def test_macos_release_signs_then_refreshes_and_validates() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-macos-linux.yml"
    ).read_text(encoding="utf-8")

    macos = workflow.split("  build-macos:", 1)[1]

    assert macos.count(
        "prepare_release_legal_bundle.py"
    ) == 2
    assert macos.count(
        "validate_release_legal_bundle.py"
    ) == 1

    assert macos.count("--inject") == 1
    assert macos.count(
        "--refresh-runtime-evidence"
    ) == 1
    assert macos.count("--public") == 1

    assert (
        '--package-dir "$APP"'
        in macos
    )
    assert (
        '--nuitka-report "$PWD/compilation-report.xml"'
        in macos
    )

    prepare = macos.index(
        "prepare_release_legal_bundle.py"
    )
    codesign = macos.index(
        'codesign --force --deep --sign - "$APP"'
    )
    refresh = macos.index(
        "--refresh-runtime-evidence"
    )
    validate = macos.index(
        "validate_release_legal_bundle.py"
    )
    archive = macos.index(
        'ZIP="artifact/PlayStoreAppAudit-v'
        '${APP_VERSION}-macos-${PACKAGE_ARCH}.zip"'
    )

    assert (
        prepare
        < codesign
        < refresh
        < validate
        < archive
    )

    assert (
        'test -f "$APP/Contents/Resources/LICENSE"'
        in macos
    )
    assert (
        'test ! -e "$APP/Contents/Resources/'
        'LEGAL-MANIFEST.json"'
        in macos
    )

    assert (
        'test -f "$RAPP/Contents/Resources/LICENSE"'
        in macos
    )
    assert (
        'test ! -e "$RAPP/Contents/Resources/'
        'LEGAL-MANIFEST.json"'
        in macos
    )

    assert "BUILD-INFO-${PACKAGE_ARCH}.txt" not in macos
def test_desktop_release_prunes_forbidden_qt_plugins_before_legal_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-macos-linux.yml"
    ).read_text(encoding="utf-8")

    linux, macos = workflow.split("  build-macos:", 1)

    linux_qpdf = (
        'find "$STANDALONE_DIR" -type f '
        "-name 'libqpdf.so*' -print -delete"
    )
    macos_qpdf = (
        'find "$APP" -type f '
        "-name 'libqpdf*.dylib' -print -delete"
    )

    assert (
        "--noinclude-qt-plugins=platforminputcontexts"
        in linux
    )
    assert linux_qpdf in linux
    assert macos_qpdf in macos

    assert (
        linux.index(linux_qpdf)
        < linux.index("prepare_release_legal_bundle.py")
    )
    assert (
        macos.index(macos_qpdf)
        < macos.index("prepare_release_legal_bundle.py")
    )
