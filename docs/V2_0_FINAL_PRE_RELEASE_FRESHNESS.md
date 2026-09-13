# v2.0 final pre-release component freshness audit

Audit date: 2026-09-13 CEST

Status: **PASS for the Windows x64 v2.0.0 package-candidate gate.** The selected stable direct/toolchain baseline, clean CPython 3.14.7 dependency audit, maintained GitHub Actions, supported runner labels and release signing/notarization source paths have been rechecked. Exact-head Quality passed on package/runtime/workflow state `c0e119c4811dfc40d188d29e7cb683eee43495d8`. This PASS-closing commit changes only this evidence document and must itself receive exact-head Quality before any package build is started. The final public release SHA is not frozen yet.

This is the second mandatory gate defined in `RELEASE_COMPONENT_FRESHNESS.md`. It is intentionally separate from `V2_0_RELEASE_ENTRY_FRESHNESS.md`. Passing it permits the native Windows x64 v2.0.0 package candidate for human acceptance. It does not permit publication, tagging, or the final six-platform production gate before that Windows acceptance passes.

## Direct runtime, development and packaging baseline

| Component | Repository selection | Latest stable rechecked | Current status | Authoritative source |
| --- | --- | --- | --- | --- |
| CPython | 3.14 | 3.14.7 | Current | https://www.python.org/downloads/ |
| PySide6-Essentials / Shiboken6 | 6.11.2 | 6.11.2 | Current | https://pypi.org/project/PySide6-Essentials/ |
| Nuitka | 4.2.1 | 4.2.1 | Current | https://pypi.org/project/Nuitka/ |
| pyaxmlparser | 0.3.31 | 0.3.31 | Current | https://pypi.org/project/pyaxmlparser/ |
| google-play-scraper | 1.2.7 | 1.2.7 | Current | https://pypi.org/project/google-play-scraper/ |
| requests | 2.34.2 | 2.34.2 | Current | https://pypi.org/project/requests/ |
| beautifulsoup4 | 4.15.0 | 4.15.0 | Current | https://pypi.org/project/beautifulsoup4/ |
| cryptography | 50.0.1 | 50.0.1 | Current | https://pypi.org/project/cryptography/ |
| Pillow | 12.3.0 | 12.3.0 | Current | https://pypi.org/project/Pillow/ |
| pytest | 9.1.1 | 9.1.1 | Current | https://pypi.org/project/pytest/ |
| Ruff | 0.16.7 | 0.16.7 | Current | https://pypi.org/project/ruff/ |
| mypy | 2.3.1 | 2.3.1 | Current | https://pypi.org/project/mypy/ |
| setuptools | 84.0.0 | 84.0.0 | Current | https://pypi.org/project/setuptools/ |
| wheel | 0.48.0 | 0.48.0 | Current | https://pypi.org/project/wheel/ |
| pip | release jobs upgrade bootstrap pip | 26.2.1 | Current stable rechecked | https://pypi.org/project/pip/ |
| Android Platform-Tools | `platform-tools-latest-*` managed endpoint | 37.0.1 | Current; latest endpoint remains the managed policy | https://developer.android.com/tools/releases/platform-tools |

Python 3.15 is not selected because the current v2.0 release contract is CPython 3.14 and the stable Python 3.14 maintenance line is 3.14.7. No pre-release interpreter is adopted by this gate.

## Clean-environment Python release/tooling audit

On 2026-09-13 CEST, a fresh virtual environment outside the repository was created from **CPython 3.14.7**. It received upgraded `pip`, `setuptools==84.0.0`, `wheel==0.48.0`, `Nuitka==4.2.1` and every dependency in `requirements-dev.txt` (including `requirements.txt`). The resolved `python -m pip list` versions were:

| Package | Resolved version | Package | Resolved version |
| --- | --- | --- | --- |
| asn1crypto | 1.5.1 | ast-serialize | 0.11.1 |
| beautifulsoup4 | 4.15.0 | certifi | 2026.7.22 |
| cffi | 2.1.1 | charset-normalizer | 3.5.1 |
| click | 8.5.0 | colorama | 0.4.6 |
| cryptography | 50.0.1 | google-play-scraper | 1.2.7 |
| idna | 3.19 | iniconfig | 2.3.0 |
| librt | 0.15.0 | lxml | 6.1.3 |
| mypy | 2.3.1 | mypy-extensions | 1.1.0 |
| Nuitka | 4.2.1 | packaging | 26.3 |
| pathspec | 1.1.1 | Pillow | 12.3.0 |
| pip | 26.2.1 | pluggy | 1.6.0 |
| pyaxmlparser | 0.3.31 | pycparser | 3.0 |
| Pygments | 2.21.0 | PySide6-Essentials | 6.11.2 |
| pytest | 9.1.1 | requests | 2.34.2 |
| ruff | 0.16.7 | setuptools | 84.0.0 |
| shiboken6 | 6.11.2 | soupsieve | 2.9.2 |
| typing-extensions | 4.16.0 | urllib3 | 2.7.0 |
| wheel | 0.48.0 | | |

`python -m pip check` returned `No broken requirements found.` The complete `python -m pip list --outdated --format=json` result was `[]`; no installed release-path component was reported outdated.

## GitHub Actions and provider actions

| Action | Repository reference | Latest stable rechecked | Status |
| --- | --- | --- | --- |
| `actions/checkout` | `@v7` | v7.0.1 | Current maintained major |
| `actions/setup-python` | `@v7` | v7.0.0 | Current maintained major |
| `actions/upload-artifact` | `@v7` | v7.0.1 | Current maintained major |
| `actions/download-artifact` | `@v8` | v8.0.1 | Current maintained major |
| `azure/login` | `@v3` | v3.1.0 | Current maintained major |
| `azure/artifact-signing-action` | `@v2` | v2.0.0 | Current maintained major |

The final branch-state review confirmed that maintained workflows use the expected action majors and no additional release action/tool was introduced after the entry audit.

## Runner, platform and signing scope

The maintained runner labels were rechecked against GitHub's current hosted-runner reference and release notices:

- Windows x64: `windows-2025` remains a supported standard x64 label and currently resolves to the Visual Studio 2026 image family used by exact-head Quality.
- Windows ARM64: `windows-11-arm` remains a supported standard ARM64 label. GitHub has announced a gradual move of that alias to the generally available Visual Studio 2026 image beginning 2026-09-21; the label itself remains supported. The production build must record the actual runner image used.
- Linux x64: `ubuntu-22.04` remains a supported x64 label retained deliberately for binary compatibility.
- Linux ARM64: `ubuntu-24.04-arm` remains a supported standard ARM64 label.
- macOS ARM64: `macos-15` remains a supported Apple Silicon label.
- macOS x64: `macos-15-intel` remains the supported Intel label for the required x86_64 package. GitHub currently plans Intel runner support through the macOS 15 image lifetime; the final build must record the actual runner image used.

The release source paths were also reconfirmed:

- Windows production signing uses GitHub OIDC through `azure/login@v3` and Microsoft Artifact Signing through `azure/artifact-signing-action@v2`, with exact-SHA/source-run provenance checks before signing.
- macOS production mode requires Developer ID Application credentials, hardened runtime and secure timestamp, followed by `xcrun notarytool`, stapling and Gatekeeper verification before artifact upload.
- Linux packaging retains architecture-specific native build/ELF validation and intentionally does not provide managed ADB on Linux ARM64.

These source paths being current does **not** claim that Microsoft signing-provider eligibility, Windows signing credentials, Apple Developer ID credentials or notarization credentials have succeeded. Actual final production runs remain the required credential/provider proof.

## Validation state

Completed for this gate:

- PR #150 and all final v2 product/UX changes merged to `main`.
- Post-merge Quality passed on `main` at `d2a00f8e7f1ca3d2bbe7c9e69b312f911f98e61d`.
- The release-preparation branch moved canonical application/package metadata to `2.0.0`.
- Release-preparation documentation and changelog reflect the v2.0 source and selected release sequence without product-behavior changes.
- Clean CPython 3.14.7 dependency audit passed `pip check` and returned `[]` from `pip list --outdated --format=json`.
- CPython 3.14.7 and Android Platform-Tools 37.0.1 were rechecked as the current selected stable baseline.
- Maintained GitHub Action majors and their latest stable releases were rechecked.
- Windows, Linux and macOS x64/ARM64 runner labels and release-path source configuration were reviewed against the final branch state.
- Exact-head Quality run #431 (`34731549542`) passed against package/runtime/workflow state `c0e119c4811dfc40d188d29e7cb683eee43495d8` on CPython 3.14.7 and PySide6 6.11.2 with 1142 tests, Ruff and Qt offscreen smoke.

The commit that closes this document is documentation-only and does not change application, dependency, workflow, legal, signing or package inputs. Exact-head Quality on that closure head remains a mandatory no-change confirmation before the Windows x64 candidate is built.

## Gate result

**PASS**, subject only to exact-head Quality succeeding on this documentation-only closure commit before build dispatch. Once that no-change confirmation is green, the branch head may be used for the native Windows x64 v2.0.0 package candidate.

This PASS does not freeze the final public release SHA. It does not publish or tag v2.0.0. It does not permit the final six-platform production gate until the Windows x64 package has passed human acceptance.
