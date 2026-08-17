# Building Play Store App Audit

Windows, macOS and Linux use the same Python/Qt source tree from the canonical `main` branch. The release-build Python baseline is 3.13.

## Local development environment

Create a virtual environment and install the development dependencies:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on macOS/Linux, then run:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

The source should remain compatible with newer stable CPython releases. Move the release baseline to Python 3.14 only when the stable deployment/compiler toolchain supports it without an experimental warning.

## Run from source

```bash
python main.py
```

The package entry points are equivalent:

```bash
python -m playstore_app_audit
playstore-app-audit
```

## Quality and source smoke checks

Run the standard quality commands before packaging:

```bash
python -m compileall playstore_app_audit
python -m pytest
ruff check playstore_app_audit tests main.py
```

Run the Qt widget smoke check with the offscreen platform plugin. In PowerShell:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -c "from PySide6.QtWidgets import QApplication; from playstore_app_audit.ui.main_window import MainWindow; app=QApplication([]); w=MainWindow(); assert w.path_edit.isHidden(); assert w.choose_button.text()=='Choose file'; assert w.scan_button.text()=='Scan phone'; old='Audit completed • 10 cached • 2 live'; w.status_label.setText(old); w._set_view_preset('Device'); assert w.status_label.text()==old; assert w.country_edit.text(); print('Qt source smoke test OK'); w.close()"
Remove-Item Env:QT_QPA_PLATFORM
```

## Local Windows x64 package

`build_windows_exe.bat` is the supported local Windows x64 build helper. It:

- requires native x64 Python 3.13 through the Windows Python launcher;
- creates or reuses `.venv` and installs `requirements-dev.txt`;
- runs compileall, pytest, Ruff and the Qt source smoke checks;
- derives package and Windows version metadata from `playstore_app_audit.__version__`;
- builds a standalone application directory through Nuitka and packages it as a versioned ZIP;
- verifies the x64 PE architecture, required and forbidden runtime contents, and `MAJOR.MINOR.PATCH.0` Windows version;
- runs the packaged smoke test and writes a SHA-256 sidecar.

Run it from a normal Command Prompt:

```bat
build_windows_exe.bat
```

The versioned output is placed under `dist/`. Generated icons, deployment configuration and build directories are ignored and must not be committed.

The helper intentionally builds x64 only. Use the GitHub workflow's explicit ARM64 engineering target when a native Windows ARM64 package must be validated.

## GitHub Actions build policy

`.github/workflows/build-windows-exe.yml` is the normal automatic package workflow:

- a relevant push to `main` builds Windows x64 only;
- a manual dispatch defaults to x64;
- manual `arm64` and `both` inputs remain available for engineering validation.

The x64 job uses `windows-2025` and expects `IMAGE_FILE_MACHINE_AMD64`. The ARM64 job uses `windows-11-arm` and expects `IMAGE_FILE_MACHINE_ARM64`; the hosted ARM64 runner is currently a preview service and is not part of the normal release path.

Each selected job validates native Python and PySide6 inputs, the generated PE architecture, Windows file/product version, standalone runtime contents, source startup and packaged startup. The uploaded artifacts are a versioned standalone ZIP and its SHA-256 sidecar; build provenance is recorded inside the package.

`.github/workflows/quality.yml` runs compile, tests, Ruff and Qt offscreen smoke checks for pull requests to `main`. Do not manually dispatch a duplicate Quality run when the pull-request trigger already covers the change.

## macOS and Linux packaging

`.github/workflows/build-macos-linux.yml` runs only through manual dispatch. Choose `linux`, `macos` or `both`; no macOS or Linux package job runs on an ordinary push.

Linux runner prerequisites include:

```bash
sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0
```

The packaging job also uses Xvfb and the Qt XCB runtime for extracted-artifact startup validation. Linux x64 can use the managed Google Platform-Tools archive. Linux ARM64 needs a native ADB from the distribution or an ARM64-compatible Android SDK.

The macOS build excludes the unused `platforminputcontexts` / Qt Virtual Keyboard plugin, validates the thin Mach-O architecture and bundle version, applies an ad-hoc signature and repeats startup validation after archive extraction. The runner OS version alone is not a minimum-supported-macOS guarantee.

## Architecture validation

Do not infer package architecture from a filename or runner label alone:

- Windows uses `.github/scripts/inspect_pe.py` against Python, QtCore, managed ADB and the packaged executable where applicable.
- Linux verifies the ELF machine field and executable mode after archive extraction.
- macOS verifies the Mach-O architecture reported by `lipo` and reads deployment metadata from the built executable.

Managed Google ADB and the application package can have different architectures. In particular, a native Windows ARM64 application package does not imply that Google's downloaded `adb.exe` is ARM64.

## Version handling

The canonical application version is recorded in both `playstore_app_audit.__version__` and `pyproject.toml`; tests require them to match. Windows file/product version adds a fourth numeric component, so application version `1.2.0` becomes Windows version `1.2.0.0`.

For a release:

1. Update both canonical version values in the same change.
2. Add an unreleased changelog section and finalize its date only when the release is ready.
3. Complete local compile, tests, Ruff, Qt smoke and Windows x64 packaging.
4. Have the user manually test the local Windows x64 standalone package, including `PlayStoreAppAudit.exe` together with its bundled runtime files.
5. Open one pull request and let its normal Quality run complete.
6. Merge to `main` and let the one automatic final-main Windows x64 build complete.
7. Validate and publish the artifact from that exact final-main run.
8. Tag the validated commit as `vMAJOR.MINOR.PATCH` and create the release.

Do not dispatch duplicate Actions runs without a concrete reason. Windows ARM64 and macOS/Linux packages remain optional manual engineering outputs rather than part of the normal release sequence.

## Packaged smoke tests

Set `PLAYSTORE_APP_AUDIT_SMOKE_TEST=1` when starting a packaged binary in automation. The application creates its Qt event loop, shows the main window briefly and exits deterministically. A package is not considered valid merely because the compiler returned success: verify the standalone runtime contents, the intended architecture and version, and successful completion of this smoke test.

## Signing and distribution

Windows and Linux artifacts are currently unsigned. The macOS bundle receives only an ad-hoc CI signature and is not Apple-notarized. Windows users can therefore encounter SmartScreen or reputation warnings.

Production signing and notarization are future distribution work. Signing credentials must be stored outside the repository in the appropriate secret store.
