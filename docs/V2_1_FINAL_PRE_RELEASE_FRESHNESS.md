# v2.1 final pre-release component freshness audit

Audit date: 2026-09-22 CEST

Status: **PASS for the mandatory final pre-release freshness gate**, subject to exact-head Quality succeeding after this evidence record and removal of the temporary audit step. This document does not itself freeze a release SHA, tag, publish, or claim production signing/notarization credentials.

This is the second mandatory audit defined by `docs/RELEASE_COMPONENT_FRESHNESS.md`. It was performed only after the v2.1 release-preparation version/docs work was complete and Quality #584 passed on release-prep head `fda09cbe27dc98aebaafb2c673bb518fdc613fa3`.

## Python, direct dependencies and release tooling

Current stable selections were rechecked against authoritative upstream release state and then independently challenged by a clean Python 3.14 CI environment.

| Component | Repository selection / resolved baseline | Latest stable verified | Result |
| --- | --- | --- | --- |
| CPython | 3.14 release line; CI resolved 3.14.7 | 3.14.7 | Current |
| PySide6-Essentials / Shiboken6 | 6.11.2 | 6.11.2 | Current |
| Nuitka | 4.2.1 | 4.2.1 | Current |
| pyaxmlparser | 0.3.31 | 0.3.31 | Current |
| google-play-scraper | 1.2.7 | 1.2.7 | Current |
| requests | 2.34.2 | 2.34.2 | Current |
| beautifulsoup4 | 4.15.0 | 4.15.0 | Current |
| cryptography | 50.0.1 | 50.0.1 | Current |
| websocket-client | 1.9.2 | 1.9.2 | Current |
| Pillow | 12.3.0 | 12.3.0 | Current |
| pytest | 9.1.1 | 9.1.1 | Current |
| Ruff | 0.16.8 | 0.16.8 | Current |
| mypy | 2.3.1 | 2.3.1 | Current |
| setuptools | 84.0.0 | 84.0.0 | Current build-system pin |
| wheel | 0.48.0 | 0.48.0 | Current build-system pin |
| pip | release jobs upgrade bootstrap pip; CI resolved 26.2.1 | 26.2.1 | Current |
| Android Platform-Tools | managed upstream latest endpoint | 37.0.1 | Current |

Authoritative sources:
- https://www.python.org/downloads/
- https://pypi.org/
- https://developer.android.com/tools/releases/platform-tools

### Fail-closed clean-environment proof

Quality #585 / workflow run `35700725588` executed the temporary final-pre-freeze audit step on exact head `126602cfe8ef7d05139ed8005940047a1062088d`.

The job:
- installed the complete direct/runtime/dev set from `requirements-dev.txt`;
- installed the exact release-tooling pins `setuptools==84.0.0`, `wheel==0.48.0` and `Nuitka==4.2.1`;
- ran `python -m pip check`;
- emitted the installed inventory;
- required `python -m pip list --outdated --format=json` to be empty.

Observed evidence:
- CPython: 3.14.7 x64;
- `pip`: 26.2.1;
- `setuptools`: 84.0.0;
- `wheel`: 0.48.0;
- `Nuitka`: 4.2.1;
- `certifi`: 2026.7.22;
- `ast-serialize`: 0.11.2;
- `idna`: 3.20;
- `urllib3`: 2.8.0;
- `pip check`: `No broken requirements found.`;
- `OUTDATED_JSON=[]`;
- explicit marker: `FINAL_PRE_FREEZE_PYTHON_FRESHNESS=PASS`.

The same run completed the normal Quality gate with **1586 passed**, Ruff PASS and Qt offscreen smoke PASS.

## GitHub Actions

Repository workflow references were re-enumerated. The maintained action majors remain:

| Action | Repository reference | Latest stable verified | Result |
| --- | --- | --- | --- |
| `actions/checkout` | `@v7` | v7.0.1 | Current maintained major |
| `actions/setup-python` | `@v7` | v7.0.0 | Current maintained major |
| `actions/upload-artifact` | `@v7` | v7.0.1 | Current maintained major |
| `actions/download-artifact` | `@v8` | v8.0.1 | Current maintained major |
| `azure/login` | `@v3` | v3.1.0 | Current maintained major |
| `azure/artifact-signing-action` | `@v2` | v2.0.0 | Current maintained major |

The project intentionally follows maintained majors for these Actions, so patch/minor maintenance within each selected major remains upstream-managed without repository churn.

Authoritative sources:
- https://github.com/actions/checkout/releases
- https://github.com/actions/setup-python/releases
- https://github.com/actions/upload-artifact/releases
- https://github.com/actions/download-artifact/releases
- https://github.com/Azure/login/releases
- https://github.com/Azure/artifact-signing-action/releases

## Runner images and architecture prerequisites

Current workflow runner selections were re-enumerated from the repository and checked against GitHub's supported hosted-runner labels:

- Windows x64: `windows-2025`
- Windows ARM64: `windows-11-arm`
- Linux x64: `ubuntu-22.04` (deliberately retained for binary compatibility)
- Linux ARM64: `ubuntu-24.04-arm`
- macOS ARM64: `macos-15`
- macOS x64: `macos-15-intel`
- assembly/maintenance: `ubuntu-24.04`
- Quality: `windows-latest`

GitHub currently lists all of those labels as supported hosted-runner labels. Moving Linux x64 merely because a newer Ubuntu label exists would narrow compatibility rather than constitute a freshness improvement, so the deliberate `ubuntu-22.04` baseline remains unchanged.

Authoritative source:
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners

## Platform-Tools / managed ADB

Android's current Platform-Tools release remains 37.0.1. The repository's managed ADB path continues to use the upstream latest download endpoint; the already accepted feature-complete Windows x64 package exercised that managed path successfully. No pin or source change is required.

Authoritative source:
- https://developer.android.com/tools/releases/platform-tools

## Signing and notarization source paths

Windows production-signing source configuration remains:
- GitHub OIDC via `azure/login@v3`;
- Microsoft Artifact Signing via `azure/artifact-signing-action@v2`;
- exact-SHA/source-run provenance checks before signing.

macOS production source configuration remains:
- Developer ID Application signing;
- hardened runtime and secure timestamp;
- `xcrun notarytool`;
- stapling;
- Gatekeeper verification before artifact upload.

This gate verifies source/configuration freshness only. It does **not** claim that production credentials/provider configuration are available. Actual trust status must be taken only from the final release runs. If production signing/notarization cannot run successfully, release documentation must state the real unsigned/ad-hoc status rather than imply stronger trust.

## Gate result and freeze rule

**PASS for the second mandatory v2.1 freshness gate.**

The temporary Quality step existed only to capture one-shot fail-closed evidence and is removed in the same evidence/cleanup phase. Exact-head Quality must now pass with normal `.github/workflows/quality.yml` restored.

Only after that final Quality is green may PR #204 be made ready and merged normally with expected-head protection. Post-merge Quality on `main` must also be green. The exact release SHA can be frozen only from that accepted `main`.

Any source/dependency/tooling change after this gate invalidates the candidate SHA and requires the affected freshness/validation gates to be repeated. Published v2.0.0 remains immutable and issue #200 remains outside v2.1 scope.
