# Building Play Store App Audit

Windows, macOS and Linux use the same Python/Qt source tree from the canonical `main` branch. The release-packaging Python baseline is 3.13.

The canonical release engineering rules are also summarized in `AGENTS.md` and `PROJECT_DECISIONS.md`. Current pins, workflow names and backlog live in `PROJECT_STATUS.md`.

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

Python 3.13 is the release-packaging baseline. Python 3.14 is a Quality CI compatibility target. Move the packaging baseline only through a deliberate toolchain change with successful package validation.

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

`.github/workflows/quality.yml` runs the cheap pull-request and `main` validation on Python 3.13 and 3.14. It is the normal pre-release correctness gate; it is not a package release workflow.

## Release toolchain baseline

For v1.3.x release engineering:

- Packaging Python: 3.13
- Quality CI: Python 3.13 and 3.14
- `PySide6-Essentials==6.11.1`
- `Nuitka==4.1.3`
- Qt Widgets
- official JavaScript GitHub Actions at their currently supported majors

Do not change these as incidental cleanup. Toolchain migration requires a dedicated PR and package evidence.

## Local Windows x64 package

`build_windows_exe.bat` is the supported local Windows x64 helper. It:

- requires native x64 Python 3.13 through the Windows Python launcher;
- creates or reuses `.venv` and installs `requirements-dev.txt`;
- runs compileall, pytest, Ruff and Qt source smoke checks;
- derives package and Windows version metadata from `playstore_app_audit.__version__`;
- builds a standalone application directory through Nuitka and packages it as a versioned ZIP;
- verifies x64 PE architecture, required and forbidden runtime contents, and Windows file/product version;
- runs the packaged smoke test and writes a SHA-256 sidecar.

Run it from a normal Command Prompt:

```bat
build_windows_exe.bat
```

The output is placed under `dist/`. Generated icons, deployment configuration and build directories are ignored and must not be committed.

This helper is for local x64 engineering. Production releases use the GitHub Actions release-candidate workflows described below.

## Release-candidate workflows

Heavy package workflows are deliberate manual dispatches. Ordinary pushes and release-tag pushes do not build release packages.

Every production release starts with three package workflow runs, all dispatched from the same exact frozen `main` SHA:

- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`

Windows then has a separate production trust stage:

- `.github/workflows/sign-windows.yml`

Every package/signing workflow verifies the required exact `expected_sha`. Package workflows verify dispatch and checkout identity before expensive build work. The Windows signing workflow additionally verifies that its unsigned source run is a successful `Build Windows - Qt6` run from the same repository and exact SHA.

After release dependencies are installed, every package job runs the deterministic legal-material preflight described below. Nuitka compilation does not begin until that preflight succeeds.

### Windows native package build

`.github/workflows/build-windows-exe.yml` accepts:

- `target`: `x64`, `arm64` or `both`
- `expected_sha`: the exact 40-character commit SHA intended for the build

For a production release, use `target=both`. The x64 job runs on `windows-2025`; ARM64 runs on `windows-11-arm`.

Each selected job validates native Python/PySide6 inputs, PE architecture, Windows version metadata, managed ADB behaviour, source checks, packaged startup, legal material and release provenance. The native package workflow intentionally produces an unsigned intermediate Windows candidate. It is not accepted directly by the production release assembler after Windows production signing is enabled.

### Windows production signing

`.github/workflows/sign-windows.yml` accepts:

- `expected_sha`: the same exact frozen SHA used by the unsigned build
- `build_run_id`: the successful `Build Windows - Qt6` run containing both x64 and ARM64 unsigned artifacts

The workflow has three stages:

1. a cheap Ubuntu preflight verifies the exact SHA, `main` dispatch, unsigned source workflow identity/status/repository and signing configuration;
2. x64 and ARM64 `PlayStoreAppAudit.exe` files are signed on `windows-2025` with Microsoft Artifact Signing Public Trust;
3. each final signed ZIP is re-extracted, signature-checked and smoke-tested on its native Windows architecture, including `windows-11-arm` for ARM64.

The signing action itself is kept on a supported x64 Windows runner. Signing an ARM64 PE does not replace its native build evidence: the workflow rechecks the ARM64 PE machine and runs the final signed application on the native ARM64 runner before the signing workflow can succeed.

Only the owned top-level `PlayStoreAppAudit.exe` is signed. Before signing, the workflow records SHA-256 hashes for every other package file except `BUILD-INFO.txt`; after signing it fails if any non-target file changed. Third-party DLLs are not re-signed merely for consistency.

Production signing uses:

- `azure/login@v3` with GitHub OIDC
- `azure/artifact-signing-action@v2`
- SHA-256 file digest
- RFC3161 timestamping with SHA-256

Required GitHub Secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

Required GitHub repository variables:

- `WINDOWS_ARTIFACT_SIGNING_ENDPOINT`
- `WINDOWS_ARTIFACT_SIGNING_ACCOUNT_NAME`
- `WINDOWS_ARTIFACT_SIGNING_CERTIFICATE_PROFILE_NAME`

The Azure identity must have permission to sign with the configured Artifact Signing account/certificate profile. The configured profile must be a production Public Trust profile appropriate for public Win32 distribution, not a self-signed, Private Trust or test profile.

After Authenticode signing, the workflow requires a valid signature and timestamp, updates `BUILD-INFO.txt`, refreshes runtime legal evidence, reruns the strict public legal validator and standalone validator, creates the final signed ZIP, and verifies the signature again after ZIP roundtrip. A signing workflow run is not a valid Windows release source unless all native post-sign verification jobs also pass.

### Linux

`.github/workflows/build-linux.yml` always builds both release architectures from one manual dispatch:

- x64 on `ubuntu-22.04`
- ARM64 on `ubuntu-24.04-arm`

Its only release input is the required exact `expected_sha`.

Linux packaging uses Nuitka standalone mode, not onefile. The ZIP contains the complete standalone tree so Qt/PySide/Shiboken shared libraries remain individually replaceable. Linux x64 can use the managed Google Platform-Tools archive; Linux ARM64 requires a native compatible ADB.

### macOS

`.github/workflows/build-macos.yml` always builds both release architectures from one manual dispatch:

- Apple Silicon / ARM64 on `macos-15`
- Intel / x64 on `macos-15-intel`

It accepts:

- `expected_sha`: the exact frozen source commit
- `signing_mode`: `engineering` or `production`

`engineering` is the default for deliberate package experiments. It uses an ad-hoc signature and uploads non-canonical artifact names beginning with `PlayStoreAppAudit-engineering-`, so those artifacts cannot match the assembler's production download pattern.

`production` is required for a production release. It fails before dependency installation if the required Apple signing/notary secrets are missing. After the app and public legal material are complete, the workflow signs nested Mach-O code and nested bundles inside-out, signs the top-level app with a Developer ID Application identity, enables hardened runtime and secure timestamping, submits a temporary ZIP to Apple's notary service, requires `Accepted`, staples and validates the ticket, verifies the signature and runs a Gatekeeper assessment. The final release ZIP is created only after those checks and the final strict legal validation have passed.

Required GitHub Secrets for production mode:

- `MACOS_DEVELOPER_ID_APPLICATION_P12_BASE64`
- `MACOS_DEVELOPER_ID_APPLICATION_P12_PASSWORD`
- `MACOS_DEVELOPER_ID_TEAM_ID`
- `MACOS_NOTARY_API_KEY_P8_BASE64`
- `MACOS_NOTARY_KEY_ID`
- `MACOS_NOTARY_ISSUER_ID`

The P12 and App Store Connect API key are materialized only in temporary runner paths. The certificate is imported into a temporary keychain, and the workflow removes the temporary signing/notary material in an `always()` cleanup step.

Separating platform workflows improves failure isolation and selective reruns. It does not make them independent release sources: every production package and signing stage still has to use the same frozen SHA.

## Architecture validation

Do not infer package architecture from a filename or runner label alone:

- Windows uses `.github/scripts/inspect_pe.py` against Python, QtCore, managed ADB and the packaged executable where applicable. Production signing rechecks the signed executable and final ZIP, then repeats verification on the native target runner.
- Linux verifies the ELF machine field and executable mode after archive extraction.
- macOS verifies Mach-O architecture and bundle metadata.

Managed Google ADB and the application package can have different architectures. In particular, a native Windows ARM64 application package does not imply that Google's downloaded `adb.exe` is ARM64.

## Legal/source validation

Release packages include public legal/source-availability material. Internal legal manifests and validation evidence are build inputs and do not belong in the public binary packages.

The consolidated public source archive is:

`PlayStoreAppAudit-vVERSION-third-party-sources.tar.xz`

The release process validates the expected corresponding-source set and checksums. Do not relax legal validation merely to make CI pass.

### Cheap pre-Nuitka preflight

`.github/scripts/preflight_release_legal_material.py` runs after the release Python dependencies are installed and before Qt deployment/Nuitka compilation in the Windows, Linux and macOS package workflows.

It deliberately reuses the source/license resolution functions from `prepare_release_legal_bundle.py` and fails closed when deterministic prerequisites cannot be established. It checks:

- the canonical project version;
- the exact `PySide6-Essentials` project pin and the installed PySide6/Shiboken version match;
- official Qt/PySide source archive names, URLs and SHA-256 provenance metadata for `pyside-setup`, `qtbase`, `qtimageformats` and `qtsvg`;
- the exact certifi source distribution metadata and SHA-256 digest;
- CPython license resolution, including the exact-version upstream fallback used by the strict legal tooling;
- the required Nuitka legal files and the exact release build pin.

The preflight resolves metadata and small legal text only. It does not download the large Qt/PySide source archives, because the final package determines the authoritative source-component set and the full corresponding-source download still belongs to the package-aware legal stage.

Passing the preflight is not release compliance evidence by itself. After packaging, `prepare_release_legal_bundle.py` still detects the actual runtime, downloads the exact required source archives, injects public legal material and creates validation evidence. `validate_release_legal_bundle.py` then performs the strict public package/source validation. The preflight complements these gates and never replaces or weakens them.

For macOS production builds, legal/public files are injected before the production signature. After signing/notarization/stapling, runtime evidence is refreshed against that final app state and the strict public legal validator runs before the release ZIP is created. Do not add or modify app-bundle files after the production signature except through the deliberate notarization/stapling process.

For Windows production builds, the unsigned native package already passed the strict legal gate. Authenticode changes the owned executable bytes and the signing workflow deliberately updates `BUILD-INFO.txt`, so runtime evidence is refreshed and the strict public legal validator runs again before the final signed ZIP is created. The release ZIP and checksum always refer to this final signed state, never the unsigned intermediate ZIP.

## Frozen-SHA production release procedure

A production release uses one exact immutable source revision for all six platform packages.

1. Finish source, version and changelog changes through normal PRs.
2. Merge the final release PR to `main` with a normal merge commit.
3. Require the cheap post-merge Quality run to pass.
4. Record the exact full `main` SHA. This becomes the frozen release SHA.
5. Dispatch `.github/workflows/build-windows-exe.yml` from `main` with `target=both` and `expected_sha=<frozen SHA>`; record its successful unsigned Windows build run ID.
6. Dispatch `.github/workflows/sign-windows.yml` from the same frozen `main` SHA with `expected_sha=<frozen SHA>` and `build_run_id=<successful unsigned Windows build run>`. Require both signing jobs and both native post-sign verification jobs to pass; record this successful signed-Windows run ID.
7. Dispatch `.github/workflows/build-linux.yml` from `main` with `expected_sha=<frozen SHA>`.
8. Dispatch `.github/workflows/build-macos.yml` from `main` with `expected_sha=<frozen SHA>` and `signing_mode=production`.
9. Confirm that all six final release candidates succeeded from that exact SHA:
   - Windows x64 signed and natively verified
   - Windows ARM64 signed and natively verified
   - Linux x64
   - Linux ARM64
   - macOS x64 with production Developer ID/notarization evidence
   - macOS ARM64 with production Developer ID/notarization evidence
10. Dispatch `.github/workflows/assemble-release.yml` from the same frozen `main` SHA with:
    - `expected_sha=<frozen SHA>`
    - `windows_run_id=<successful Sign Windows release candidates run>`
    - `linux_run_id=<successful Linux run>`
    - `macos_run_id=<successful production macOS run>`
11. The assembler verifies each input workflow's identity, event, successful completion, repository and exact head SHA before downloading artifacts. The three run IDs must be distinct. The Windows input cannot accept the unsigned native build workflow, and the canonical macOS artifact pattern cannot match engineering-mode artifact names.
12. The assembler validates the six release candidates, their provenance and legal/source material, then produces the final public asset set.
13. Require the assembler output to contain exactly 8 files and no extra directories:
    - `PlayStoreAppAudit-vVERSION-windows-x64.zip`
    - `PlayStoreAppAudit-vVERSION-windows-arm64.zip`
    - `PlayStoreAppAudit-vVERSION-linux-x64.zip`
    - `PlayStoreAppAudit-vVERSION-linux-arm64.zip`
    - `PlayStoreAppAudit-vVERSION-macos-x64.zip`
    - `PlayStoreAppAudit-vVERSION-macos-arm64.zip`
    - `PlayStoreAppAudit-vVERSION-third-party-sources.tar.xz`
    - `SHA256SUMS.txt`
14. Verify the final asset checksums and perform any deliberate release smoke/manual checks against those exact artifacts.
15. Create the annotated `vMAJOR.MINOR.PATCH` tag on the same frozen SHA only after artifact validation.
16. Create the GitHub Release and upload the already validated eight assets.
17. Do not rebuild because the tag was pushed. The tag identifies the validated source commit; it is not a package-build trigger.
18. Once published, treat the tag, release history and binary assets as immutable.

If source code or release tooling changes after step 4, discard the affected release candidates, freeze the new exact `main` SHA and rebuild all six final candidates. Never mix artifacts from different SHAs.

Documentation-only changes after a published release do not justify rebuilding, retagging or replacing that release's binary assets.

## Version handling

The canonical application version is recorded in both `playstore_app_audit.__version__` and `pyproject.toml`; tests require them to match. Windows file/product version adds a fourth numeric component, so application version `1.3.0` maps to Windows version `1.3.0.0`.

## Packaged smoke tests

Set `PLAYSTORE_APP_AUDIT_SMOKE_TEST=1` when starting a packaged binary in automation. The application creates its Qt event loop, shows the main window briefly and exits deterministically.

A package is not valid merely because the compiler returned success. Verify standalone runtime contents, intended architecture and version, successful startup, legal material and release provenance.

## Signing and distribution

At the immutable v1.3.0 baseline:

- Windows packages are unsigned.
- Linux packages are unsigned.
- macOS bundles have only an ad-hoc CI signature and are not Apple-notarized.

### macOS v1.4 production path

`.github/scripts/sign_macos_app.py` is the canonical app-bundle signing helper. It discovers Mach-O files and nested code bundles, signs them inside-out, signs the top-level app last and then performs strict recursive verification. Production mode adds hardened runtime and secure timestamping. It deliberately does not use `codesign --deep` as the signing strategy.

The production workflow then notarizes with `xcrun notarytool`, requires an accepted result, staples the ticket and validates both the stapled app and the extracted final release app with code-signing and Gatekeeper checks.

Do not treat the implementation as credential-validated until a deliberate `signing_mode=production` workflow run succeeds on both macOS architectures with real Developer ID and App Store Connect notary credentials.

### Windows v1.4 production path

`.github/workflows/sign-windows.yml` is the production Authenticode trust stage. It uses Microsoft Artifact Signing with a configured production Public Trust profile and GitHub OIDC, signs only `PlayStoreAppAudit.exe`, requires SHA-256 plus RFC3161 timestamping, refreshes strict legal evidence after signing, and repeats final package/signature validation after ZIP roundtrip.

The Artifact Signing action runs on a supported x64 Windows hosted runner. ARM64 remains a native package target: after its ARM64 PE is signed, the final ZIP is reverified and smoke-tested on `windows-11-arm` before the signing workflow can succeed.

Do not treat the implementation as production-validated until the Azure Artifact Signing account, identity validation, certificate profile, federated GitHub identity and repository configuration are provisioned and one deliberate signing workflow run succeeds for both architectures. The assembler accepts only that successful signing workflow as its Windows source.
