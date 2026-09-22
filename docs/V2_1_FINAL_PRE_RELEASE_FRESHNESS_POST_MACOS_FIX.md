# v2.1 repeated final pre-release component freshness audit after the macOS fix

Audit date: 2026-09-22 CEST

Status: **ONE-SHOT HOSTED PROOF PASSED; cleanup is complete locally and normal exact-head Quality is pending.** The live audit found one required update: Nuitka 4.2.1 to 4.2.2. The maintained pins and workflows were updated, and Quality #590 / run `35759658599` proved the clean hosted Python 3.14 dependency state. The temporary audit step has now been removed while all permanent Nuitka 4.2.2 changes remain. This record does not freeze a release SHA, tag, publish, or claim production signing/notarization credentials.

This is a new audit under `docs/RELEASE_COMPONENT_FRESHNESS.md`. It does not rewrite or extend the authority of `V2_1_FINAL_PRE_RELEASE_FRESHNESS.md`, whose evidence remains historical and predates the macOS Device Specific resource-packaging correction.

Audit lineage:

- accepted post-macOS-fix `main` audited at `a1505f7763a169668064eadef77f44beb7bd48e0`;
- previous candidate `459d3cf5e6c9290ec1c30e0116fd823d82660c23`: **INVALIDATED, NOT FOR RELEASE**;
- focused local toolchain-update commit: `e4a6361d6036910c597df525f926ca181f76ee54`;
- hosted proof PR head: `d6154352c38d4dae87a23a3d4534b8a372345720`;
- final release SHA: not selected.

## Python, Qt, direct dependencies and release tooling

| Component | Repository selection before repeat | Latest stable verified | Action | Authoritative upstream source |
| --- | --- | --- | --- | --- |
| CPython | stable 3.14 line | 3.14.7 | Current release baseline | https://www.python.org/downloads/ |
| PySide6-Essentials | 6.11.2 | 6.11.2 | Current | https://pypi.org/project/PySide6-Essentials/ |
| Shiboken6 | 6.11.2 through PySide6-Essentials | 6.11.2 | Current | https://pypi.org/project/shiboken6/ |
| Qt | 6.11.2 supplied by PySide6-Essentials | 6.11.2 | Current | https://www.qt.io/blog/qt-6.11.2-released |
| Nuitka | 4.2.1 | 4.2.2 | **Updated to 4.2.2** | https://nuitka.net/doc/download.html |
| pyaxmlparser | 0.3.31 | 0.3.31 | Current | https://pypi.org/project/pyaxmlparser/ |
| google-play-scraper | 1.2.7 | 1.2.7 | Current | https://pypi.org/project/google-play-scraper/ |
| requests | 2.34.2 | 2.34.2 | Current | https://pypi.org/project/requests/ |
| beautifulsoup4 | 4.15.0 | 4.15.0 | Current | https://pypi.org/project/beautifulsoup4/ |
| cryptography | 50.0.1 | 50.0.1 | Current | https://pypi.org/project/cryptography/ |
| websocket-client | 1.9.2 | 1.9.2 | Current | https://pypi.org/project/websocket-client/ |
| Pillow | 12.3.0 | 12.3.0 | Current | https://pypi.org/project/pillow/ |
| pytest | 9.1.1 | 9.1.1 | Current | https://pypi.org/project/pytest/ |
| Ruff | 0.16.8 | 0.16.8 | Current | https://pypi.org/project/ruff/ |
| mypy | 2.3.1 | 2.3.1 | Current | https://pypi.org/project/mypy/ |
| setuptools | 84.0.0 | 84.0.0 | Current build-system pin | https://pypi.org/project/setuptools/ |
| wheel | 0.48.0 | 0.48.0 | Current build-system pin | https://pypi.org/project/wheel/ |
| pip | release jobs upgrade bootstrap pip | 26.2.1 | Current stable | https://pypi.org/project/pip/ |
| Android Platform-Tools / ADB | upstream `platform-tools-latest-*` endpoints | 37.0.1 | Current managed-download policy retained | https://developer.android.com/tools/releases/platform-tools |

Python 3.15 remains a pre-release line on the audit date and is outside the stable Python 3.14 release contract. No pre-release interpreter or package was selected.

## Clean Python 3.14 dependency proof

A new virtual environment under the retained release-work area was created from CPython 3.14.6 x64 because that is the locally installed 3.14 interpreter. The repository requires the stable 3.14 line, and the one-shot hosted Quality proof independently resolved the current 3.14.7 patch release as recorded below.

The environment installed every dependency in `requirements-dev.txt` plus the exact release-tooling pins `setuptools==84.0.0`, `wheel==0.48.0` and `Nuitka==4.2.2`. PySide6, Shiboken and Qt each reported 6.11.2.

Resolved inventory:

| Package | Version | Package | Version |
| --- | --- | --- | --- |
| asn1crypto | 1.5.1 | ast-serialize | 0.11.2 |
| beautifulsoup4 | 4.15.0 | certifi | 2026.7.22 |
| cffi | 2.1.1 | charset-normalizer | 3.5.1 |
| click | 8.5.0 | colorama | 0.4.6 |
| cryptography | 50.0.1 | google-play-scraper | 1.2.7 |
| idna | 3.20 | iniconfig | 2.3.0 |
| librt | 0.15.0 | lxml | 6.1.3 |
| mypy | 2.3.1 | mypy-extensions | 1.1.0 |
| Nuitka | 4.2.2 | packaging | 26.3 |
| pathspec | 1.1.1 | Pillow | 12.3.0 |
| pip | 26.2.1 | pluggy | 1.6.0 |
| pyaxmlparser | 0.3.31 | pycparser | 3.0 |
| Pygments | 2.21.0 | PySide6-Essentials | 6.11.2 |
| pytest | 9.1.1 | requests | 2.34.2 |
| Ruff | 0.16.8 | setuptools | 84.0.0 |
| Shiboken6 | 6.11.2 | soupsieve | 2.9.2 |
| typing-extensions | 4.16.0 | urllib3 | 2.8.0 |
| websocket-client | 1.9.2 | wheel | 0.48.0 |

Observed local proof after the Nuitka update:

- `python -m pip check`: `No broken requirements found.`
- `python -m pip list --outdated --format=json --no-cache-dir`: exactly `[]`
- full source test suite: `1582 passed, 9 skipped`
- compileall and maintained helper compilation: PASS
- Ruff: PASS
- Qt offscreen smoke: PASS

The first fail-closed query before the update returned Nuitka 4.2.1 with latest version 4.2.2. That result triggered the update; it was not waived.

### Hosted one-shot proof

GitHub Quality #590 / workflow run `35759658599` completed successfully for PR head `d6154352c38d4dae87a23a3d4534b8a372345720`. Because this was a `pull_request` workflow, `actions/checkout` tested GitHub's synthetic merge ref at `03ebbbf866d815c5bc9a77f4e6f7d0c550af52e2`, which merged that PR head into base `a1505f7763a169668064eadef77f44beb7bd48e0`. The checkout SHA was therefore the synthetic merge SHA, not the PR head SHA.

Hosted evidence:

- CPython: 3.14.7
- Nuitka: 4.2.2
- `python -m pip check`: `No broken requirements found.`
- `OUTDATED_JSON=[]`
- `POST_MACOS_FIX_PYTHON_FRESHNESS=PASS`
- pytest: `1591 passed`
- Ruff: PASS
- Qt offscreen smoke: PASS

The one-shot hosted proof therefore passed. The temporary audit step has been removed from the normal Quality workflow in the following local cleanup commit; normal exact-head Quality on that cleanup commit is still required.

## GitHub Actions

Repository workflows were re-enumerated from the exact audited source. The maintained references and live latest stable releases are:

| Action | Repository reference | Latest stable verified | Result |
| --- | --- | --- | --- |
| `actions/checkout` | `@v7` | v7.0.1 | Current maintained major |
| `actions/setup-python` | `@v7` | v7.0.0 | Current maintained major |
| `actions/upload-artifact` | `@v7` | v7.0.1 | Current maintained major |
| `actions/download-artifact` | `@v8` | v8.0.1 | Current maintained major |
| `azure/login` | `@v3` | v3.1.0 | Current maintained major |
| `azure/artifact-signing-action` | `@v2` | v2.0.0 | Current maintained major |

Authoritative sources:

- https://github.com/actions/checkout/releases
- https://github.com/actions/setup-python/releases
- https://github.com/actions/upload-artifact/releases
- https://github.com/actions/download-artifact/releases
- https://github.com/Azure/login/releases
- https://github.com/Azure/artifact-signing-action/releases

The repository deliberately follows maintained majors for these Actions, so current patch/minor maintenance within each major is supplied by the upstream major reference.

## Runner images and architecture prerequisites

The selected labels remain supported GA labels in GitHub's current hosted-runner tables:

- Windows x64: `windows-2025`
- Windows ARM64: `windows-11-arm`
- Linux x64: `ubuntu-22.04`
- Linux ARM64: `ubuntu-24.04-arm`
- macOS x64: `macos-15-intel`
- macOS ARM64: `macos-15`
- assembly and maintenance: `ubuntu-24.04`
- normal Quality: `windows-latest`, currently mapped by GitHub to Windows Server 2025

Authoritative sources:

- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://github.com/actions/runner-images
- https://doc.qt.io/qt-6/supported-platforms.html

Newer Ubuntu 26.04 and macOS 26 labels are available, but they are alternative build environments rather than in-place updates to the selected GA labels. They are deliberately not adopted immediately before freeze: Linux x64 retains Ubuntu 22.04 for the established binary-compatibility floor; Linux ARM64 retains the already validated Ubuntu 24.04 Qt reference environment; macOS retains the already validated macOS 15 Intel/ARM64 pair to avoid introducing an unvalidated SDK/compiler change. Qt 6.11 continues to support the selected environments and macOS 13 or later. Windows retains the established Windows 2025/MSVC 2022-compatible release path rather than switching to the distinct VS 2026 image variants. Every selected label remains supported and will receive exact-target package validation.

## Android Platform-Tools / managed ADB

Android's current stable Platform-Tools release remains 37.0.1. The application still downloads Google's `platform-tools-latest-windows.zip`, `platform-tools-latest-linux.zip` and `platform-tools-latest-darwin.zip` endpoints where the architecture policy allows managed ADB. The final platform builds must exercise and record the real resolved ADB version. Managed ADB remains read-only regarding installed Android applications.

Authoritative source: https://developer.android.com/tools/releases/platform-tools

## Signing, notarization and release utilities

Windows production signing source configuration remains GitHub OIDC through `azure/login@v3` and Microsoft Artifact Signing through `azure/artifact-signing-action@v2`, with exact-SHA/source-run provenance checks. Those are the current maintained action majors.

macOS production source configuration remains Developer ID Application signing with hardened runtime and secure timestamp, followed by `xcrun notarytool`, stapling and Gatekeeper verification. `codesign`, `notarytool`, `stapler`, `spctl`, `lipo`, Xcode/Clang, MSVC, PowerShell, tar/zip and architecture inspection are runner/OS-supplied release utilities rather than repository-pinned downloadable components. The selected current GA runner images and Qt-supported compiler environments remain the maintained source for those tools.

Authoritative sources:

- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://github.com/Azure/login/releases
- https://github.com/Azure/artifact-signing-action/releases
- https://github.com/actions/runner-images

This audit verifies source configuration and current upstream support. It does **not** prove that production credentials exist. Until real final workflows prove otherwise, Windows and Linux are unsigned, macOS is engineering/ad-hoc signed, and Developer ID, notarization, stapling and production Gatekeeper trust remain unproven.

## Gate closure requirements

The one-shot hosted proof has passed, but the repeated gate cannot be marked fully complete until all of the following complete:

1. **COMPLETE:** push the focused update branch without changing its tested contents;
2. **COMPLETE:** run Quality with the temporary one-shot audit on hosted Python 3.14 and require `pip check` clean plus `OUTDATED_JSON=[]`;
3. **COMPLETE:** record the run number, run ID, PR head SHA, synthetic merge checkout SHA, resolved CPython patch version and result here;
4. **COMPLETE LOCALLY:** remove the temporary audit step while keeping the permanent Nuitka 4.2.2 pins;
5. **PENDING:** run normal exact-head Quality after cleanup;
6. merge through a normal merge commit with expected-head protection;
7. require post-merge normal Quality on the new `main`;
8. repeat the live final freshness check from that new `main` and confirm no newer stable component appeared.

Only after those requirements pass may a new exact v2.1.0 candidate SHA be frozen. No artifact from invalidated SHA `459d3cf5e6c9290ec1c30e0116fd823d82660c23` may be reused, and no public tag or release may be created during this sequence.
