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

The final artifact is `PlayStoreAppAudit.exe`.

## macOS and Linux

`.github/workflows/build-macos-linux.yml` has **only** `workflow_dispatch`. It consumes no runner resources on ordinary pushes.

To build one of these platforms in GitHub:

1. Open the repository on GitHub.
2. Open **Actions**.
3. Select **Build macOS / Linux - Qt6 (manual)**.
4. Choose **Run workflow**.
5. Select `linux`, `macos` or `both`.
6. When the run completes, download the artifact from that workflow run.

The workflow runs compile/tests/Ruff/Qt offscreen smoke checks against the same source before packaging, then verifies that the generated artifact is non-trivial instead of trusting the deployment command alone.

### Linux runner prerequisites

The GitHub Ubuntu runner needs a small Qt/EGL/XCB runtime set before importing Qt offscreen:

```bash
sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0
```

These are CI/build-host dependencies, not additional Python runtime packages in the application.

### macOS packaging note

The application does not use Qt Virtual Keyboard. The macOS Nuitka build therefore excludes the `platforminputcontexts` plugin. With PySide6 6.11.1 on the current GitHub ARM64 macOS runner, including that unused plugin can make Nuitka follow a missing `QtVirtualKeyboardQml.framework` reference. Excluding it keeps the app bundle limited to the Qt functionality the application actually uses.

The workflow also checks for a real executable under `Contents/MacOS` and requires the app/archive to exceed a minimal plausible size. This guards against a deployment wrapper reporting success after an internal compiler/plugin failure.

## ADB / Android Platform-Tools

At runtime, if ADB is not already installed, Play Store App Audit downloads the official current Google Platform-Tools archive matching the host OS:

- Windows: `platform-tools-latest-windows.zip`
- macOS: `platform-tools-latest-darwin.zip`
- Linux: `platform-tools-latest-linux.zip`

The platform abstraction also searches typical Android SDK locations and `ANDROID_SDK_ROOT` / `ANDROID_HOME`.

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

Unsigned CI artifacts are suitable for testing. Public distribution should eventually add:

- Windows code signing and installer/package strategy
- Apple Developer ID signing, hardened runtime and notarisation for macOS
- Linux AppImage/Flatpak/deb packaging only if there is a real distribution need

Signing secrets must be stored in GitHub Actions secrets and must never be committed to the repository.
