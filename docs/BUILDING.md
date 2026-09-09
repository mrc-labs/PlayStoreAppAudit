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
python -c "from PySide6.QtWidgets import QApplication; from playstore_app_audit.ui.main_window import MainWindow; app=QApplication([]); w=MainWindow(); assert w.path_edit.isHidden(); assert w.choose_button.text()=='Choose File'; assert w.scan_button.text()=='Scan Phone'; old='Audit completed • 10 cached • 2 live'; w.status_label.setText(old); w._set_view_preset('Device'); assert w.status_label.text()==old; assert w.country_edit.text(); print('Qt source smoke test OK'); w.close()"
Remove-Item Env:QT_QPA_PLATFORM
```

`.github/workflows/quality.yml` runs the cheap pull-request and `main` validation on Python 3.13 and 3.14. It is the normal pre-release correctness gate; it is not a package release workflow.

## Release toolchain baseline

For the Windows x64 ETB profiles through v1.99 and the preserved future production profile:

- Packaging Python: 3.13
- Quality CI: Python 3.13 and 3.14
- `PySide6-Essentials==6.11.1`
- `Nuitka==4.1.3`
- Qt Widgets
- official JavaScript GitHub Actions at their currently supported majors

Do not change these as incidental cleanup. Toolchain migration requires a dedicated PR and package evidence.

## Release profiles

The project has a lightweight unsigned Windows x64 Engineering Test Build profile for near-term releases and a preserved six-platform signed production profile for a later production milestone.

### v1.4 Windows x64 Engineering Test Build (ETB)

v1.4 is a public Engineering Test Build. It publishes only the Windows x64 standalone package and deliberately does not build Windows ARM64, Linux or macOS or invoke production signing.

The three public assets are exactly:

1. `PlayStoreAppAudit-vVERSION-windows-x64.zip`
2. `PlayStoreAppAudit-vVERSION-third-party-sources.tar.xz`
3. `SHA256SUMS.txt`

The Windows x64 package must come from the exact frozen `main` SHA and remains unsigned. The normal package legal/source gate remains mandatory and the release-wide source archive is assembled from the exact source evidence emitted by that x64 candidate.

The engineering assembler accepts only a successful manual `Build Windows - Qt6` run from the same repository and exact SHA, requires the x64 artifact, and rejects a source run that also emitted the canonical Windows ARM64 artifact. It does not accept a signing run and does not build any other platform or architecture.

### v1.5 Windows x64 Engineering Test Build (ETB)

v1.5.0 remains an unsigned Windows x64-only Engineering Test Build. It follows the same exact-SHA engineering release path as v1.4:

- build Windows x64 only with `.github/workflows/build-windows-exe.yml` using `target=x64`;
- do not build Windows ARM64, Linux or macOS release candidates;
- do not invoke production signing or incur signing spend;
- assemble with `.github/workflows/assemble-windows-engineering-release.yml`;
- publish exactly `PlayStoreAppAudit-v1.5.0-windows-x64.zip`, `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`;
- use release title suffix `(ETB Win x64)` and body heading `## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)`.

### v1.6 Windows x64 Engineering Test Build (ETB)

v1.6.0 is frozen as an unsigned Windows x64-only Engineering Test Build, reusing the exact-SHA profile proven by v1.5.

- canonical version metadata is `1.6.0`;
- build Windows x64 only with `.github/workflows/build-windows-exe.yml` using `target=x64`;
- do not build Windows ARM64, Linux or macOS release candidates;
- do not invoke production Windows signing or macOS signing/notarization;
- assemble with `.github/workflows/assemble-windows-engineering-release.yml`;
- publish exactly `PlayStoreAppAudit-v1.6.0-windows-x64.zip`, `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`;
- use the current release title `Play Store App Audit v1.6.0 (Win x64 Only)` and body heading `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`;
- clearly state that the Windows package is unsigned.

The exact v1.6 release SHA is the `main` merge commit produced by the profile/version freeze once its post-merge Quality gate passes. If source or release tooling changes afterward, discard the candidate SHA and rebuild the required ETB artifacts from the new exact SHA.

### v1.7-v1.99 Windows x64 Engineering Test Builds (ETB)

v1.7.0, v1.8.0 and v1.9.0 are published and immutable as unsigned Windows x64 ETBs. v1.99 deliberately reuses the same exact-SHA x64-only release profile unless a later explicit release decision changes it.

- Build with `.github/workflows/build-windows-exe.yml` using `target=x64` only.
- Do not invoke production Windows signing or build Windows ARM64/Linux/macOS release candidates.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- Publish exactly the Windows x64 ZIP, consolidated third-party source archive and `SHA256SUMS.txt`.
- Current/future ETB GitHub Release titles use `(Win x64 Only)`; the body heading continues to say `Engineering Test Build - Windows x64 Only`.
- v1.7.0 frozen release SHA is `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.
- v1.8.0 frozen release SHA is `ac328f0dffddb6b70fa7600f1291377376bc05d4`.
- v1.9.0 frozen release SHA is `6c117009525f40434e9db714dadf1dd01b79f9ab`.
- v1.99 requires a real packaged Windows x64 user-acceptance candidate before the separate final exact-SHA release freeze.

### v2.0-or-later full production release

Production trust validation and the full six-platform release are not planned before v2.0. The production workflows remain intact so the architecture can be activated later without being part of the Windows x64-only v1.6-v1.99 release cost.

The future production profile consists of:

- Windows x64/ARM64 native package build followed by publicly trusted signing and native post-sign verification;
- Linux x64/ARM64 standalone packages;
- macOS x64/ARM64 Developer ID signing, hardened runtime, notarization and stapling;
- the six-candidate assembler with exactly eight final public assets.

Production signing is implemented in source but is not considered credential-validated until deliberate real signing runs succeed.

## GitHub Actions retention

Artifact-producing workflows use repository-default retention as their hard safety ceiling. `.github/workflows/actions-retention.yml` applies the generational cleanup policy documented in `CI_MAINTENANCE.md`.

The newest successful equivalent generation remains current. The previous generation receives a 7-day grace period after its successor completes. Older successful generations are removed, and failed/cancelled runs are removed after the 7-day threshold.

This housekeeping never alters GitHub Release assets, tags or source commits.

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

The packaged output is placed under `artifact/windows-x64-local`; temporary environment/build output remains under ignored local directories. Generated icons, deployment configuration and all local package/build output must not be committed.

This helper is for local x64 engineering. Public release artifacts use the GitHub Actions exact-SHA workflows described below.

## Release-candidate workflows

Heavy package workflows are deliberate manual dispatches. Ordinary pushes and release-tag pushes do not build release packages.

Available package workflows are:

- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`

Future production Windows trust uses:

- `.github/workflows/sign-windows.yml`

Assembly is profile-specific:

- `.github/workflows/assemble-windows-engineering-release.yml` for Windows x64 ETB releases including the Windows x64 ETB profiles through v1.99;
- `.github/workflows/assemble-release.yml` for the future v2.0-or-later six-platform production release.

Every package/signing/assembly workflow verifies the required exact `expected_sha`. Package workflows verify dispatch and checkout identity before expensive build work. The Windows signing workflow additionally verifies that its unsigned source run is a successful `Build Windows - Qt6` run from the same repository and exact SHA.

After release dependencies are installed, every package job runs the deterministic legal-material preflight described below. Nuitka compilation does not begin until that preflight succeeds.

### Windows native package build

`.github/workflows/build-windows-exe.yml` accepts:

- `target`: `x64`, `arm64` or `both`
- `expected_sha`: the exact 40-character commit SHA intended for the build

For Windows x64 ETB releases through v1.99, use `target=x64`. The x64 job runs on `windows-2025`. Do not select `arm64` or `both` for those ETB releases.

For the future six-platform production profile, use `target=both`; ARM64 runs on `windows-11-arm`.

Each selected job validates native Python/PySide6 inputs, PE architecture, Windows version metadata, managed ADB behaviour, source checks, packaged startup, legal material and release provenance.

For Windows x64 ETB releases, the successful unsigned x64 run is the direct source of `.github/workflows/assemble-windows-engineering-release.yml`. For the future production profile, the x64+ARM64 native build is only an intermediate and must pass through `.github/workflows/sign-windows.yml` before the full production assembler can accept it.

### Windows production signing, v2.0 or later

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

Required GitHub Secrets when this production profile is activated:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

Required GitHub repository variables:

- `WINDOWS_ARTIFACT_SIGNING_ENDPOINT`
- `WINDOWS_ARTIFACT_SIGNING_ACCOUNT_NAME`
- `WINDOWS_ARTIFACT_SIGNING_CERTIFICATE_PROFILE_NAME`

The Azure identity must have permission to sign with the configured Artifact Signing account/certificate profile. The configured profile must be a production Public Trust profile appropriate for public Win32 distribution, not a self-signed, Private Trust or test profile.

After Authenticode signing, the workflow requires a valid signature and timestamp, updates `BUILD-INFO.txt`, refreshes runtime legal evidence, reruns the strict public legal validator and standalone validator, creates the final signed ZIP, and verifies the signature again after ZIP roundtrip. A signing workflow run is not a valid Windows production release source unless all native post-sign verification jobs also pass.

### Linux

`.github/workflows/build-linux.yml` always builds both release architectures from one manual dispatch:

- x64 on `ubuntu-22.04`
- ARM64 on `ubuntu-24.04-arm`

Its only release input is the required exact `expected_sha`.

Linux packaging uses Nuitka standalone mode, not onefile. The ZIP contains the complete standalone tree so Qt/PySide/Shiboken shared libraries remain individually replaceable. Linux x64 can use the managed Google Platform-Tools archive; Linux ARM64 requires a native compatible ADB.

Linux is not built for Windows x64 ETB releases such as v1.4, v1.5 or v1.6.0. It remains part of the future v2.0-or-later production profile.

### macOS

`.github/workflows/build-macos.yml` always builds both release architectures from one manual dispatch:

- Apple Silicon / ARM64 on `macos-15`
- Intel / x64 on `macos-15-intel`

It accepts:

- `expected_sha`: the exact frozen source commit
- `signing_mode`: `engineering` or `production`

`engineering` uses an ad-hoc signature and uploads non-canonical artifact names beginning with `PlayStoreAppAudit-engineering-`.

`production` fails before dependency installation if the required Apple signing/notary secrets are missing. After the app and public legal material are complete, the workflow signs nested Mach-O code and nested bundles inside-out, signs the top-level app with a Developer ID Application identity, enables hardened runtime and secure timestamping, submits a temporary ZIP to Apple's notary service, requires `Accepted`, staples and validates the ticket, verifies the signature and runs a Gatekeeper assessment. The final release ZIP is created only after those checks and the final strict legal validation have passed.

Required GitHub Secrets when production macOS signing is activated:

- `MACOS_DEVELOPER_ID_APPLICATION_P12_BASE64`
- `MACOS_DEVELOPER_ID_APPLICATION_P12_PASSWORD`
- `MACOS_DEVELOPER_ID_TEAM_ID`
- `MACOS_NOTARY_API_KEY_P8_BASE64`
- `MACOS_NOTARY_KEY_ID`
- `MACOS_NOTARY_ISSUER_ID`

The P12 and App Store Connect API key are materialized only in temporary runner paths. The certificate is imported into a temporary keychain, and the workflow removes the temporary signing/notary material in an `always()` cleanup step.

macOS is not built for the frozen v1.6.0 Windows x64 ETB profile. Production macOS signing/notarization is deferred to the v2.0-or-later production milestone.

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

For unsigned Windows x64 engineering releases through v1.99, the native x64 package is the final binary state, so the strict legal evidence produced by the Windows package workflow is the evidence consumed by the engineering assembler.

For macOS production builds, legal/public files are injected before the production signature. After signing/notarization/stapling, runtime evidence is refreshed against that final app state and the strict public legal validator runs before the release ZIP is created. Do not add or modify app-bundle files after the production signature except through the deliberate notarization/stapling process.

For Windows production builds, Authenticode changes the owned executable bytes and the signing workflow deliberately updates `BUILD-INFO.txt`, so runtime evidence is refreshed and the strict public legal validator runs again before the final signed ZIP is created.

## Frozen-SHA Windows x64 Engineering Test Build procedure

This procedure applies to the Windows x64 ETB release line through v1.99.

1. Finish source, version and changelog changes through normal PRs.
2. Merge the final release change to `main` with a normal merge commit.
3. Require the cheap post-merge Quality run to pass.
4. Record the exact full `main` SHA. This becomes the frozen release SHA.
5. Dispatch `.github/workflows/build-windows-exe.yml` from `main` with `target=x64` and `expected_sha=<frozen SHA>`.
6. Require the native Windows x64 job to succeed from that exact SHA. Do not dispatch Windows ARM64, Windows signing, Linux or macOS for this ETB profile.
7. Record the successful `Build Windows - Qt6` run ID.
8. Dispatch `.github/workflows/assemble-windows-engineering-release.yml` from the same frozen `main` SHA with:
   - `expected_sha=<frozen SHA>`
   - `windows_run_id=<successful x64-only Build Windows - Qt6 run>`
9. The engineering assembler verifies workflow identity, manual-dispatch status, success, repository and exact head SHA, requires the x64 artifact and rejects the canonical ARM64 artifact.
10. Require exactly three final files and no extra directories:
    - `PlayStoreAppAudit-vVERSION-windows-x64.zip`
    - `PlayStoreAppAudit-vVERSION-third-party-sources.tar.xz`
    - `SHA256SUMS.txt`
11. Verify the final checksums and deliberate manual smoke checks against those exact artifacts.
12. Create the annotated `vMAJOR.MINOR.PATCH` tag on the same frozen SHA only after artifact validation.
13. Create the GitHub Release and upload the already validated three assets. Current and future ETBs use title suffix `(Win x64 Only)`; the release-body heading identifies `Engineering Test Build - Windows x64 Only`; clearly state that the package is unsigned. Preserve older published release titles unchanged.
14. Do not rebuild because the tag was pushed.
15. Once published, treat the tag, release history and binary assets as immutable.

If source code or release tooling changes after step 4, discard the candidate, freeze the new exact `main` SHA and rebuild the Windows x64 candidate. Never mix artifacts from different SHAs.

### v1.99 mandatory user-acceptance candidate

v1.99 adds one deliberate packaged acceptance gate before the normal final procedure above:

1. Reach a feature-complete source candidate through normal reviewed PRs and Quality.
2. Freeze an RC candidate SHA and build a real Windows x64 packaged candidate with the exact-SHA Windows workflow.
3. Provide that package for thorough user acceptance testing; do not create a public RC tag.
4. Record real-use corrections and merge focused corrective PRs when required.
5. If source or release tooling changes, discard the RC as a final candidate. Never publish its package from the changed source line.
6. Only after user acceptance, freeze a new final exact `main` SHA, require final Quality, and run the canonical Windows x64 build and engineering assembler from that SHA.

The authorized RC build is additional evidence; it does not replace the final exact-SHA build after corrections. If acceptance requires no source or release-tooling changes, the later release review may determine whether the accepted SHA can also be the final frozen SHA, but all normal exact-SHA, Quality, build, assembly and publication gates still apply.

### v1.6.0 filename/title specialization

For the frozen v1.6.0 Windows x64 ETB profile, the generic procedure above specializes to:

- version: `1.6.0`;
- tag: `v1.6.0`;
- package: `PlayStoreAppAudit-v1.6.0-windows-x64.zip`;
- source archive: `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`;
- current release title: `Play Store App Audit v1.6.0 (Win x64 Only)`;
- body heading: `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`.

## Frozen-SHA future full production procedure

The future v2.0-or-later production profile uses one exact immutable source revision for all six platform packages.

1. Finish source, version and changelog changes through normal PRs.
2. Merge the final release PR to `main` with a normal merge commit.
3. Require the cheap post-merge Quality run to pass.
4. Record the exact full `main` SHA.
5. Dispatch `.github/workflows/build-windows-exe.yml` with `target=both` and the frozen SHA.
6. Dispatch `.github/workflows/sign-windows.yml` with the same SHA and successful unsigned Windows run ID. Require both signing and native post-sign verification paths to succeed.
7. Dispatch `.github/workflows/build-linux.yml` with the same SHA.
8. Dispatch `.github/workflows/build-macos.yml` with the same SHA and `signing_mode=production`.
9. Confirm all six final release candidates succeeded from that exact SHA.
10. Dispatch `.github/workflows/assemble-release.yml` with the successful signed-Windows, Linux and production-macOS run IDs from that SHA.
11. Require the assembler output to contain exactly eight files: six platform ZIPs, one consolidated third-party source archive and `SHA256SUMS.txt`.
12. Verify checksums and deliberate release smoke/manual checks against those exact artifacts.
13. Create the annotated version tag on the same frozen SHA only after artifact validation.
14. Create the GitHub Release and upload the already validated eight assets.
15. Do not rebuild because the tag was pushed.
16. Once published, treat the tag, release history and binary assets as immutable.

If source code or release tooling changes after the SHA is frozen, freeze a new exact `main` SHA and rebuild every artifact required by the selected release profile.

Documentation-only changes after a published release do not justify rebuilding, retagging or replacing that release's binary assets.

## Version handling

The canonical application version is recorded in both `playstore_app_audit.__version__` and `pyproject.toml`; tests require them to match. Windows file/product version adds a fourth numeric component, so application version `1.9.0` maps to Windows version `1.9.0.0`.

v1.7.0, v1.8.0 and v1.9.0 version metadata are part of their immutable published release profiles. Current source is now frozen at `1.99.0` for the v1.99 Windows x64 release-candidate cycle.

## Packaged smoke tests

Set `PLAYSTORE_APP_AUDIT_SMOKE_TEST=1` when starting a packaged binary in automation. The application creates its Qt event loop, shows the main window briefly and exits deterministically.

A package is not valid merely because the compiler returned success. Verify standalone runtime contents, intended architecture and version, successful startup, legal material and release provenance.

## Signing and distribution

At the immutable v1.3.0 baseline, Windows and Linux packages are unsigned and macOS bundles have only an ad-hoc CI signature.

The Windows x64 ETB release line through v1.99 deliberately remains unsigned. Production trust validation is deferred until v2.0 or later.

### macOS production path, v2.0 or later

`.github/scripts/sign_macos_app.py` is the canonical app-bundle signing helper. It discovers Mach-O files and nested code bundles, signs them inside-out, signs the top-level app last and then performs strict recursive verification. Production mode adds hardened runtime and secure timestamping. It deliberately does not use `codesign --deep` as the signing strategy.

The production workflow then notarizes with `xcrun notarytool`, requires an accepted result, staples the ticket and validates both the stapled app and the extracted final release app with code-signing and Gatekeeper checks.

Do not treat the implementation as credential-validated until a deliberate `signing_mode=production` workflow run succeeds on both macOS architectures with real Developer ID and App Store Connect notary credentials.

### Windows production path, v2.0 or later

`.github/workflows/sign-windows.yml` is the production Authenticode trust stage. It uses Microsoft Artifact Signing with a configured production Public Trust profile and GitHub OIDC, signs only `PlayStoreAppAudit.exe`, requires SHA-256 plus RFC3161 timestamping, refreshes strict legal evidence after signing, and repeats final package/signature validation after ZIP roundtrip.

The Artifact Signing action runs on a supported x64 Windows hosted runner. ARM64 remains a native package target: after its ARM64 PE is signed, the final ZIP is reverified and smoke-tested on `windows-11-arm` before the signing workflow can succeed.

Do not treat the implementation as production-validated until the Azure Artifact Signing account, identity validation, certificate profile, federated GitHub identity and repository configuration are provisioned and one deliberate signing workflow run succeeds for both architectures. The full production assembler accepts only that successful signing workflow as its Windows source.
