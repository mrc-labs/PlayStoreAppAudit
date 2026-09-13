# v2.0 final pre-release component freshness audit

Audit date: 2026-09-13 CEST

Status: **IN PROGRESS.** The authoritative upstream recheck of the selected stable direct/toolchain baseline is current. The gate is not PASS and no exact release SHA may be frozen until the clean Python 3.14 release environment is re-resolved, the transitive/outdated check is completed, exact-head Quality is green after all release-preparation edits, and the remaining runner/signing release paths are confirmed.

This is the second mandatory gate defined in `RELEASE_COMPONENT_FRESHNESS.md`. It is intentionally separate from `V2_0_RELEASE_ENTRY_FRESHNESS.md` and must describe the exact dependency/workflow state immediately before the v2.0 production SHA is frozen.

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

Python 3.15 is not selected because the current v2.0 release contract is CPython 3.14 and the stable Python download line remains 3.14.7 for that series. No pre-release interpreter is adopted by this gate.

## Transitive release/tooling baseline to re-resolve

The release-entry gate resolved the following versions on a clean Python 3.14.7 environment. Authoritative PyPI rechecks performed during this final gate have not identified a newer stable release for the listed baseline, but the clean final release environment still must be re-resolved and checked before this document can become PASS:

- `lxml 6.1.3`
- `click 8.5.0`
- `asn1crypto 1.5.1`
- `charset-normalizer 3.5.1`
- `idna 3.19`
- `urllib3 2.7.0`
- `certifi 2026.7.22`
- `soupsieve 2.9.2`
- `typing-extensions 4.16.0`
- `cffi 2.1.1`
- `shiboken6 6.11.2`
- `colorama 0.4.6`
- `iniconfig 2.3.0`
- `packaging 26.3`
- `pluggy 1.6.0`
- `Pygments 2.21.0`
- `mypy-extensions 1.1.0`
- `pathspec 1.1.1`
- `librt 0.15.0`
- `ast-serialize 0.11.1`
- `pycparser 3.0`

Required before PASS: install the exact release dependency set in a clean Python 3.14 environment, record the resolved versions, run `python -m pip list --outdated`, investigate every release/runtime/tooling-path result, and confirm no newer stable package remains unapplied.

## GitHub Actions and provider actions

| Action | Repository reference | Latest stable rechecked | Status |
| --- | --- | --- | --- |
| `actions/checkout` | `@v7` | v7.0.1 | Current maintained major |
| `actions/setup-python` | `@v7` | v7.0.0 | Current maintained major |
| `actions/upload-artifact` | `@v7` | v7.0.1 | Current maintained major |
| `actions/download-artifact` | `@v8` | v8.0.1 | Current maintained major |
| `azure/login` | `@v3` | v3.1.0 | Current maintained major |
| `azure/artifact-signing-action` | `@v2` | v2.0.0 | Current maintained major |

The repository intentionally tracks maintained action majors under the established workflow policy. The final exact-SHA review must still confirm that every maintained workflow uses the expected major and that no additional release action/tool has been introduced since this audit was written.

## Runner, platform and signing scope

The final gate retains the release-entry interpretation: runner labels are compatibility/build targets, not dependencies that are automatically replaced merely because a newer OS image exists.

Before PASS and exact-SHA freeze:

- confirm the maintained Windows x64 and Windows ARM64 runner labels remain supported and appropriate for the binary compatibility contract;
- confirm the Linux x64/ARM64 runner/container prerequisites still satisfy the standalone-package contract;
- confirm the macOS x64/ARM64 runner selections, Developer ID signing, hardened runtime, notarization, stapling and Gatekeeper validation paths are still valid;
- confirm the Microsoft Artifact Signing Public Trust workflow source remains current;
- do not claim Windows production signing or Apple signing/notarization until actual final production runs validate credentials/provider eligibility.

## Validation state

Completed before this final gate:

- PR #150 and all final v2 product/UX changes merged to `main`.
- Post-merge Quality passed on `main` at `d2a00f8e7f1ca3d2bbe7c9e69b312f911f98e61d`.
- The release-preparation branch moved canonical application/package metadata to `2.0.0`.
- The earlier Python 3.14 migration package demonstrated the toolchain on native Windows x64, but that `1.99.0` artifact is migration evidence only and is not a v2.0 release candidate.

Still required before PASS:

1. finalize release-preparation documentation/changelog without changing product behavior;
2. complete the clean Python 3.14 transitive/outdated inspection;
3. confirm every maintained release workflow/action/runner/signing path against the final branch state;
4. obtain exact-head Quality green on the final release-preparation head;
5. update this document to **PASS**, recording the exact branch head that is eligible to become the Windows x64 v2.0.0 package candidate.

A successful final freshness PASS permits the Windows x64 candidate build. It does not itself publish or tag v2.0.0, and it does not permit the final six-platform production gate until Windows x64 packaged human acceptance has passed.
