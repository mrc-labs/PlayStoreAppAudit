# Building Play Store App Audit

## Shared source

Windows, macOS and Linux use the same Python/Qt source revision from the canonical `main` branch. Do not create permanent operating-system branches.

## Local development

Use Python 3.13 for the current release/deployment toolchain and install:

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

The source should remain compatible with Python 3.14. Move the release baseline to 3.14 once the stable Nuitka/deployment toolchain no longer treats it as experimental.

Quality checks:

```bash
python -m compileall -q playstore_app_audit
python -m pytest
ruff check playstore_app_audit tests main.py
```

Run from source:

```bash
python main.py
```

## Windows

`.github/workflows/build-windows-exe.yml` is the normal automatic build. It runs on relevant pushes to `main`, tests the application using Qt's offscreen backend, then packages the app with `pyside6-deploy` / Nuitka.

The x64 artifact is named `PlayStoreAppAudit-vVERSION-windows-x64`. It contains the versioned `.exe`, its SHA-256 checksum and `BUILD-INFO-windows-x64.txt`. CI also starts the packaged executable with Qt's deterministic offscreen backend before uploading it.

## macOS and Linux

`.github/workflows/build-macos-linux.yml` has **only** `workflow_dispatch`. It consumes no runner resources on ordinary pushes.

To build one of these platforms in GitHub:

1. Open the repository on GitHub.
2. Open **Actions**.
3. Select **Build macOS / Linux - Qt6 (manual)**.
4. Choose **Run workflow**.
5. Select `linux`, `macos` or `both`.
6. When the run completes, download the artifact from that workflow run.

The workflow runs compile/tests/Ruff/Qt offscreen smoke checks against the same source before packaging, then verifies that the generated artifact is non-trivial instead of trusting the deployment command alone. Package names include the project version and architecture:

- Linux: `PlayStoreAppAudit-vVERSION-linux-x64.tar.gz` or `PlayStoreAppAudit-vVERSION-linux-arm64.tar.gz`
- macOS: `PlayStoreAppAudit-vVERSION-macOS-x64.zip` or `PlayStoreAppAudit-vVERSION-macOS-arm64.zip`

Each package has an SHA-256 checksum and source/build provenance in `BUILD-INFO`. Linux keeps the executable and `BUILD-INFO.txt` together inside the tar archive so the executable mode survives GitHub artifact handling. The macOS app carries the same information under `Contents/Resources`, with an additional copy beside the ZIP in the workflow artifact.

### Linux runner prerequisites

The GitHub Ubuntu runner needs a small Qt/EGL/XCB runtime set before importing Qt offscreen:

```bash
sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0
```

These are CI/build-host dependencies, not additional Python runtime packages in the application.

The packaging job additionally installs Xvfb and Qt's XCB support libraries. After extracting the tar archive, it checks the executable bit and exact ELF machine architecture, then starts that extracted binary through Xvfb using the native XCB plugin. This complements rather than replaces the deterministic offscreen smoke test.

### macOS packaging note

The application does not use Qt Virtual Keyboard. The macOS Nuitka build therefore excludes the `platforminputcontexts` plugin. With PySide6 6.11.1 on the current GitHub ARM64 macOS runner, including that unused plugin can make Nuitka follow a missing `QtVirtualKeyboardQml.framework` reference. Excluding it keeps the app bundle limited to the Qt functionality the application actually uses.

The ARM64 build uses the deterministic `macos-15` Apple Silicon runner label and the Intel/x64 build uses `macos-15-intel`; they remain separate thin packages. The workflow resolves the main executable from `CFBundleExecutable`, requires the exact expected `lipo` architecture, and sets both `CFBundleShortVersionString` and `CFBundleVersion` before the final ad-hoc signing step. It verifies the plist values, signature and architecture again after ZIP extraction, then repeats the deterministic offscreen startup against the extracted app.

The runner version is the build host, not a minimum-supported-macOS declaration. `BUILD-INFO` records the build-host macOS version and the main executable's actual `LC_BUILD_VERSION` `minos` value. The workflow does not claim macOS 13 compatibility; a broader compatibility claim requires deliberately configured and verified deployment targeting.

## ADB / Android Platform-Tools

At runtime, managed Platform-Tools support depends on the host OS and architecture:

- Windows: the managed `platform-tools-latest-windows.zip` archive is available where supported by the application.
- macOS: the managed `platform-tools-latest-darwin.zip` archive is available where supported by the application.
- Linux x64: the application supports Google's managed `platform-tools-latest-linux.zip` archive.
- Linux ARM64: Google does not provide the managed Linux archive used by this application. Install a native ADB from the system, distribution or an ARM64-compatible Android SDK instead.

The platform abstraction also searches `PATH`, typical Android SDK locations and `ANDROID_SDK_ROOT` / `ANDROID_HOME`. All ADB operations performed by the application remain read-only.

## Release versioning

The canonical version is recorded in both `playstore_app_audit.__version__` and `pyproject.toml`. A regression test requires them to match.

For a normal release:

1. Update both version values in the same change.
2. Update `CHANGELOG.md`.
3. Merge only after the PR quality workflow is green.
4. Confirm the automatic Windows build from the resulting `main` commit.
5. Validate Linux and macOS from the same source revision when the release affects packaging/platform code.
6. Tag the validated `main` commit as `vMAJOR.MINOR.PATCH`.

Release tags identify immutable source checkpoints. Feature/fix development continues from `main` on short-lived branches rather than version-specific permanent branches.

## Signing and distribution

The Windows and Linux CI artifacts are unsigned, while the macOS bundle has only an ad-hoc CI signature and is not notarized. These artifacts are suitable for testing. Public distribution should eventually add:

- Windows code signing and installer/package strategy
- Apple Developer ID signing, hardened runtime and notarisation for macOS
- Linux AppImage/Flatpak/deb packaging only if there is a real distribution need

Signing secrets must be stored in GitHub Actions secrets and must never be committed to the repository.
