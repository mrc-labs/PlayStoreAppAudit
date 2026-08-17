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

### v1.1.0 validation and Actions usage

During local development, run compile/tests/Ruff, the Qt smoke test and the Windows x64 package build locally. Produce and manually test the local x64 executable before committing or pushing; do not dispatch GitHub Actions merely to repeat local checks.

After that manual approval, let the Quality workflow run once through the pull request's normal trigger. Its concurrency group is scoped to the PR, so a newer commit can cancel an older still-running Quality job without cancelling another PR. Do not manually dispatch a duplicate Quality run.

After merge, let the normal `main` push build Windows x64 once and use that exact final-main artifact for release validation. Do not manually dispatch a duplicate Windows run. Windows ARM64 remains an explicit engineering target, while macOS/Linux remain manual-only; none is part of the v1.1.0 release build.

## Windows

`.github/workflows/build-windows-exe.yml` is the normal automatic build. For v1.1.0, relevant pushes to `main` test and package Windows x64 only using Qt's offscreen backend and `pyside6-deploy` / Nuitka.

The manual workflow target defaults to `x64`. It also retains explicit `arm64` and `both` engineering targets without duplicating the build logic:

- Windows x64 runs on the explicit `windows-2025` hosted-runner label and expects `IMAGE_FILE_MACHINE_AMD64` (`0x8664`).
- Windows ARM64 runs on `windows-11-arm` and expects `IMAGE_FILE_MACHINE_ARM64` (`0xAA64`). GitHub currently marks this hosted runner as public preview.

Each selected job installs the matching native Python 3.13 interpreter, requires a native `PySide6-Essentials` wheel and QtCore extension, and inspects the final executable's PE header rather than trusting the runner label or filename. The generated Windows file/product version is derived from the canonical application version and verified after packaging. Selected jobs run compile/tests/Ruff, Qt source smoke checks and the deterministic packaged executable smoke test.

The workflow artifacts are named `PlayStoreAppAudit-vVERSION-windows-x64` and `PlayStoreAppAudit-vVERSION-windows-arm64`. Each contains the matching versioned `.exe`, `.exe.sha256` checksum and `BUILD-INFO-windows-ARCH.txt`. `BUILD-INFO` records source/run provenance and the measured Python, QtCore, managed ADB and packaged executable architectures.

The v1.1.0 prebuilt release contains only the Windows x64 artifact. v1.0.0 remains the last release with the full six-package prebuilt matrix. Source-level Windows ARM64, Linux and macOS support remains in place.

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

- Windows x64 and ARM64: the managed `platform-tools-latest-windows.zip` archive is available. The native ARM64 application package and Google's `adb.exe` are separate architecture concerns.
- macOS: the managed `platform-tools-latest-darwin.zip` archive is available where supported by the application.
- Linux x64: the application supports Google's managed `platform-tools-latest-linux.zip` archive.
- Linux ARM64: Google does not provide the managed Linux archive used by this application. Install a native ADB from the system, distribution or an ARM64-compatible Android SDK instead.

The Windows matrix calls the application's real `install_platform_tools()` path, runs the returned executable with `adb version`, inspects its PE header and records whether execution was native or used Windows x64/x86 emulation. It does not claim that Google's ADB executable is ARM64 unless the measured PE header says so, and the build fails if the managed executable cannot run.

The platform abstraction also searches `PATH`, typical Android SDK locations and `ANDROID_SDK_ROOT` / `ANDROID_HOME`. All ADB operations performed by the application remain read-only.

## Release versioning

The canonical version is recorded in both `playstore_app_audit.__version__` and `pyproject.toml`. A regression test requires them to match.

For a normal release:

1. Update both version values in the same change.
2. Update `CHANGELOG.md`.
3. Merge only after the PR quality workflow is green.
4. For v1.1.0, confirm the one automatic Windows x64 build from the resulting `main` commit and use that exact artifact for release validation.
5. Do not dispatch Windows ARM64, Linux or macOS packaging for v1.1.0 unless a separate engineering investigation explicitly requires it.
6. Tag the validated `main` commit as `vMAJOR.MINOR.PATCH`.

Release tags identify immutable source checkpoints. Feature/fix development continues from `main` on short-lived branches rather than version-specific permanent branches.

## Signing and distribution

The Windows and Linux CI artifacts are unsigned, while the macOS bundle has only an ad-hoc CI signature and is not notarized. These artifacts are suitable for testing. Public distribution should eventually add:

- Windows code signing and installer/package strategy
- Apple Developer ID signing, hardened runtime and notarisation for macOS
- Linux AppImage/Flatpak/deb packaging only if there is a real distribution need

Signing secrets must be stored in GitHub Actions secrets and must never be committed to the repository.
