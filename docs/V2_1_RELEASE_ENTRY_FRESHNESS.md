# v2.1 release-entry component freshness audit

Audit date: 2026-09-22 CEST

Status: **PASS for v2.1 release-phase entry**, subject to exact-head Quality succeeding on the final documentation/cleanup head before merge. This gate does not bump the application version, freeze a release SHA, build the six production targets, tag, or publish v2.1.0.

This is the first of the two mandatory gates defined in `RELEASE_COMPONENT_FRESHNESS.md`. It was entered only after the feature-complete Windows x64 package from accepted `main` SHA `3a76e292bc45e8ff20bad39ffe4e2a5b0c0353b4` passed human packaged acceptance. The complete audit must be repeated immediately before the final v2.1 exact-SHA freeze.

## Direct runtime, development and packaging baseline

| Component | Repository selection before gate | Latest stable verified | Action | Authoritative source |
| --- | --- | --- | --- | --- |
| CPython | 3.14 | 3.14.7 | Current supported release baseline | https://www.python.org/downloads/ |
| PySide6-Essentials / Shiboken6 | 6.11.2 | 6.11.2 | Current | https://pypi.org/project/PySide6-Essentials/ |
| Nuitka | 4.2.1 | 4.2.1 | Current | https://pypi.org/project/Nuitka/ |
| pyaxmlparser | 0.3.31 | 0.3.31 | Current | https://pypi.org/project/pyaxmlparser/ |
| google-play-scraper | 1.2.7 | 1.2.7 | Current | https://pypi.org/project/google-play-scraper/ |
| requests | 2.34.2 | 2.34.2 | Current | https://pypi.org/project/requests/ |
| beautifulsoup4 | 4.15.0 | 4.15.0 | Current | https://pypi.org/project/beautifulsoup4/ |
| cryptography | 50.0.1 | 50.0.1 | Current | https://pypi.org/project/cryptography/ |
| websocket-client | 1.9.2 | 1.9.2 | Current | https://pypi.org/project/websocket-client/ |
| Pillow | 12.3.0 | 12.3.0 | Current | https://pypi.org/project/Pillow/ |
| pytest | 9.1.1 | 9.1.1 | Current | https://pypi.org/project/pytest/ |
| Ruff | 0.16.7 | 0.16.8 | **Updated to 0.16.8** | https://pypi.org/project/ruff/ |
| mypy | 2.3.1 | 2.3.1 | Current | https://pypi.org/project/mypy/ |
| setuptools | 84.0.0 | 84.0.0 | Current build-system pin | https://pypi.org/project/setuptools/ |
| wheel | 0.48.0 | 0.48.0 | Current build-system pin | https://pypi.org/project/wheel/ |
| pip | release jobs upgrade bootstrap pip | 26.2.1 | Current stable verified | https://pypi.org/project/pip/ |
| Android Platform-Tools | upstream `platform-tools-latest-*` endpoint | 37.0.1 | Current managed-download policy retained | https://developer.android.com/tools/releases/platform-tools |

Python 3.15 is not selected at this gate because the repository release contract remains the stable CPython 3.14 line and no stable Python 3.15 release supersedes that selected baseline.

## Clean Python 3.14 release/tooling audit

Quality run #579 / workflow run `35680746516` executed a one-shot fail-closed freshness step on branch head `94d003bd7258ec11c13cb640b7ffd10a4467e054`.

The environment installed the exact direct/dev pins plus `setuptools==84.0.0`, `wheel==0.48.0` and `Nuitka==4.2.1`. The resolved package set was:

- `Pillow 12.3.0`
- `PySide6-Essentials 6.11.2`
- `asn1crypto 1.5.1`
- `ast-serialize 0.11.2`
- `beautifulsoup4 4.15.0`
- `certifi 2026.7.22`
- `cffi 2.1.1`
- `charset-normalizer 3.5.1`
- `click 8.5.0`
- `colorama 0.4.6`
- `cryptography 50.0.1`
- `google-play-scraper 1.2.7`
- `idna 3.20`
- `iniconfig 2.3.0`
- `librt 0.15.0`
- `lxml 6.1.3`
- `mypy 2.3.1`
- `mypy-extensions 1.1.0`
- `Nuitka 4.2.1`
- `packaging 26.3`
- `pathspec 1.1.1`
- `Pillow 12.3.0`
- `pluggy 1.6.0`
- `pyaxmlparser 0.3.31`
- `pycparser 3.0`
- `Pygments 2.21.0`
- `pytest 9.1.1`
- `requests 2.34.2`
- `ruff 0.16.8`
- `setuptools 84.0.0`
- `shiboken6 6.11.2`
- `soupsieve 2.9.2`
- `typing-extensions 4.16.0`
- `urllib3 2.8.0`
- `websocket-client 1.9.2`
- `wheel 0.48.0`

`python -m pip check` returned `No broken requirements found.`

The complete `python -m pip list --outdated --format=json` result was exactly:

```json
[]
```

Since the v2.0 audit, the unpinned resolver-selected transitives `ast-serialize`, `idna` and `urllib3` advanced to 0.11.2, 3.20 and 2.8.0 respectively. The accepted Windows package and this clean audit both resolved those maintained current versions automatically; no repository pin is needed for them.

## GitHub Actions and provider actions

All maintained workflows were reviewed. The repository uses only the following maintained action majors:

| Action | Repository reference | Latest stable verified | Status |
| --- | --- | --- | --- |
| `actions/checkout` | `@v7` | v7.0.1 | Current maintained major |
| `actions/setup-python` | `@v7` | v7.0.0 | Current maintained major |
| `actions/upload-artifact` | `@v7` | v7.0.1 | Current maintained major |
| `actions/download-artifact` | `@v8` | v8.0.1 | Current maintained major |
| `azure/login` | `@v3` | v3.1.0 | Current maintained major |
| `azure/artifact-signing-action` | `@v2` | v2.0.0 | Current maintained major |

The established repository policy tracks the supported maintained major for these Actions, so current patch/minor maintenance is consumed through the major reference.

## Runner, Platform-Tools and signing/notary scope

The maintained runner labels were rechecked as supported and remain deliberate compatibility/architecture selections:

- Windows x64: `windows-2025`
- Windows ARM64: `windows-11-arm`
- Linux x64: `ubuntu-22.04`, deliberately retained for binary compatibility rather than automatically narrowing the package contract to a newer distro image
- Linux ARM64: `ubuntu-24.04-arm`
- macOS ARM64: `macos-15`
- macOS x64: `macos-15-intel`
- assembly/maintenance jobs: `ubuntu-24.04`
- normal Quality: `windows-latest`

The accepted Windows x64 package run `35655658931` independently exercised the managed Platform-Tools path and ran ADB 37.0.1 successfully from the upstream latest endpoint.

Windows production signing source configuration remains GitHub OIDC via `azure/login@v3` plus Microsoft Artifact Signing via `azure/artifact-signing-action@v2`. macOS production source configuration remains Developer ID Application signing with hardened runtime and secure timestamp, followed by `xcrun notarytool`, stapling and Gatekeeper verification.

This source/configuration freshness review does not claim production credential availability. Final production signing/notarization trust is established only by the real release runs if the required credentials/provider configuration are available.

## Validation completed

On the freshness-audit head `94d003bd7258ec11c13cb640b7ffd10a4467e054`:

- Ruff was updated from 0.16.7 to 0.16.8.
- clean dependency resolution completed on Python 3.14;
- `pip check` passed;
- `pip list --outdated --format=json` returned `[]`;
- 1586 tests passed;
- Ruff passed with the new 0.16.8 pin;
- Qt offscreen smoke passed;
- Quality run #579 / `35680746516` completed successfully.

The temporary continuous freshness check added only to capture this one-shot evidence is removed before merge so ordinary development Quality does not become a continuous dependency-freshness policy. The permanent two-gate policy remains `RELEASE_COMPONENT_FRESHNESS.md`.

## Gate result and next sequence

**PASS for v2.1 release-phase entry**, provided exact-head Quality is green on the final focused PR head after this evidence record and temporary-audit cleanup.

After that PR is merged normally and post-merge Quality is green, the deliberate v2.1 release-preparation sequence may begin:

1. branch from the accepted/fresh `main`;
2. bump both canonical version locations from 2.0.0 to 2.1.0;
3. update changelog and v2.1 release notes/current project context;
4. run full Quality and affected validation;
5. repeat the complete freshness audit immediately before the exact release SHA is frozen.

The v2.0.0 tag/assets remain immutable and issue #200 remains outside v2.1 scope.
