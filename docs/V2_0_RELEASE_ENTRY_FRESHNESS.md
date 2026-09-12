# v2.0 release-entry component freshness audit

Audit date: 2026-09-13 CEST

Status: **PASS for release-phase entry**, subject to completion of the Python 3.14 native package validation on the candidate branch. This record is not the final pre-release freshness gate and does not freeze a release SHA.

This is the first of the two mandatory freshness gates defined in `RELEASE_COMPONENT_FRESHNESS.md`. The complete audit must be repeated immediately before the final v2.0 exact-SHA freeze. Any newer stable component available at that later gate must be adopted and the affected validation repeated before release publication can continue.

## Stable baseline selected for v2.0

| Component | Repository selection | Latest stable verified | Status / action | Authoritative source |
| --- | --- | --- | --- | --- |
| CPython | 3.14 | 3.14.7 | Updated baseline from 3.13 to stable 3.14; 3.15.0rc2 is a pre-release and is excluded | https://www.python.org/downloads/ |
| PySide6-Essentials / Shiboken6 | 6.11.2 | 6.11.2 | Updated | https://pypi.org/project/PySide6-Essentials/ |
| Nuitka | 4.2.1 | 4.2.1 | Updated | https://pypi.org/project/Nuitka/ |
| pyaxmlparser | 0.3.31 | 0.3.31 | Current | https://pypi.org/project/pyaxmlparser/ |
| google-play-scraper | 1.2.7 | 1.2.7 | Current | https://pypi.org/project/google-play-scraper/ |
| requests | 2.34.2 | 2.34.2 | Updated and exactly pinned | https://pypi.org/project/requests/ |
| beautifulsoup4 | 4.15.0 | 4.15.0 | Updated and exactly pinned | https://pypi.org/project/beautifulsoup4/ |
| cryptography | 50.0.1 | 50.0.1 | Current | https://pypi.org/project/cryptography/ |
| Pillow | 12.3.0 | 12.3.0 | Updated and exactly pinned | https://pypi.org/project/Pillow/ |
| pytest | 9.1.1 | 9.1.1 | Updated and exactly pinned | https://pypi.org/project/pytest/ |
| Ruff | 0.16.7 | 0.16.7 | Updated and exactly pinned | https://pypi.org/project/ruff/ |
| mypy | 2.3.1 | 2.3.1 | Updated and exactly pinned | https://pypi.org/project/mypy/ |
| setuptools | 84.0.0 | 84.0.0 | Updated and build-system pinned | https://pypi.org/project/setuptools/ |
| wheel | 0.48.0 | 0.48.0 | Updated and build-system pinned | https://pypi.org/project/wheel/ |
| pip | runner/bootstrap current | 26.2.1 | Latest stable verified; release jobs deliberately upgrade pip before dependency installation | https://pypi.org/project/pip/ |
| Android Platform-Tools | upstream latest endpoint | 37.0.1 | Current managed-download policy retained; verify `platform-tools-latest-*` endpoint again at final gate | https://developer.android.com/tools/releases/platform-tools |

Python 3.15 is not adopted at this gate because the latest published 3.15 build is still a release candidate rather than a stable release. The stable v2.0 baseline is therefore CPython 3.14.7.

## Transitive Python release/tooling packages

A clean Python 3.14.7 CI dependency resolution on the v2.0 toolchain branch installed the following release-path transitive versions. Each was checked against its stable PyPI release at this entry gate and no newer stable version was identified:

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

These packages are not all project-owned direct pins. The final freshness gate must inspect the clean release environment again so that a changed dependency resolver or newly published stable transitive release cannot pass unnoticed.

## GitHub Actions and release-provider actions

The maintained workflow majors were checked against the latest stable upstream releases available at the entry gate:

| Action | Repository reference | Latest stable verified | Status |
| --- | --- | --- | --- |
| `actions/checkout` | `@v7` | v7.0.1 | Current maintained major |
| `actions/setup-python` | `@v7` | v7.0.0 | Current maintained major |
| `actions/upload-artifact` | `@v7` | v7.0.1 | Current maintained major |
| `actions/download-artifact` | `@v8` | v8.0.1 | Current maintained major |
| `azure/login` | `@v3` | v3.1.0 | Current maintained major |
| `azure/artifact-signing-action` | `@v2` | v2.0.0 | Current maintained major |

The repository intentionally tracks the supported action major where that is the established workflow policy. Patch/minor maintenance within that major is therefore supplied by the maintained major reference. The final gate must recheck both the supported major and upstream release status.

## Runner, platform and signing scope

Runner labels are compatibility/build targets rather than application dependency versions. They must remain supported by the provider and appropriate for the intended binary compatibility. A newer OS image is not substituted automatically when doing so would narrow compatibility or change the release contract.

At this gate:

- Windows x64 remains on the maintained `windows-2025` runner and Windows ARM64 on `windows-11-arm` for native architecture evidence.
- Linux runner selection remains architecture/compatibility driven; the standalone package contract and replaceable Qt/PySide/Shiboken libraries remain unchanged.
- macOS runner selection remains architecture driven and the production path still requires Developer ID Application signing, hardened runtime, notarization, stapling and Gatekeeper verification.
- Microsoft Artifact Signing Public Trust remains the implemented Windows production-signing path. Source configuration being current does not claim that credentials/provider eligibility have been validated. A real production signing run is still required before release.
- Apple production signing/notarization source support being current does not claim that credentials have been validated. A real production run on both architectures is still required before release.

## Validation completed at this gate

The migration branch has already established the following source evidence:

- GitHub Actions installs and runs CPython 3.14.7 successfully.
- The selected direct and development dependency set resolves on Python 3.14.
- PySide6-Essentials/Shiboken6 6.11.2 import successfully on the Python 3.14 Quality runner.
- The Quality workflow, release workflows, local Windows helper and standalone builder have been migrated from the old Python 3.13 baseline to Python 3.14.
- The release legal preflight expectations and Qt baseline regressions have been migrated to PySide6 6.11.2 / Nuitka 4.2.1.

Still required before the toolchain migration PR can leave draft status:

1. exact-head Quality must pass after the final migrated regression expectations;
2. a real native Windows x64 standalone package must validate on Python 3.14 with the new toolchain;
3. any failure caused by the migration must be corrected and the affected gate repeated.

## Final pre-release gate reminder

This document is deliberately an entry-gate snapshot. It must not be copied forward as proof that components are still current at release time. Immediately before the final v2.0 exact-SHA freeze, repeat the full audit from authoritative upstream sources, record a new final-gate result, update every newly superseded stable component, invalidate stale release candidates, and repeat all affected validation before freezing the production SHA.
