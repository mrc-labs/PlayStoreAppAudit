# Building Play Store App Audit

## Shared source

Windows, macOS and Linux use the same Python/Qt source revision. Do not create permanent operating-system branches.

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

`.github/workflows/build-windows-exe.yml` is the normal automatic build. It runs on pushes to the active development branch, tests the application using Qt's offscreen backend, then packages the app with `pyside6-deploy` / Nuitka.

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

The workflow still runs tests against the same source before packaging.

## ADB / Android Platform-Tools

At runtime, if ADB is not already installed, Play Store App Audit downloads the official current Google Platform-Tools archive matching the host OS:

- Windows: `platform-tools-latest-windows.zip`
- macOS: `platform-tools-latest-darwin.zip`
- Linux: `platform-tools-latest-linux.zip`

The platform abstraction also searches typical Android SDK locations and `ANDROID_SDK_ROOT` / `ANDROID_HOME`.

## Signing and distribution

Unsigned CI artifacts are suitable for testing. Public distribution should eventually add:

- Windows code signing and installer/package strategy
- Apple Developer ID signing, hardened runtime and notarisation for macOS
- Linux AppImage/Flatpak/deb packaging only if there is a real distribution need

Signing secrets must be stored in GitHub Actions secrets and must never be committed to the repository.
