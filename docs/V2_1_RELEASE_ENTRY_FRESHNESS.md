# v2.1 release-entry component freshness audit

Audit date: 2026-09-22 CEST

Status: **VALIDATION IN PROGRESS**. The upstream audit and clean CPython 3.14 dependency audit are complete. One repository-owned development pin was updated from Ruff 0.16.7 to 0.16.8, and the Windows ARM64 runner-status metadata was refreshed from the obsolete public-preview description to generally available while retaining the supported `windows-11-arm` label. Source Quality is green. The gate remains open until the affected native Windows ARM64 package path succeeds from the final branch head and the resulting evidence is recorded here.

This is the first of the two mandatory v2.1 freshness gates defined in `RELEASE_COMPONENT_FRESHNESS.md`. It occurs after the combined feature-complete Windows x64 packaged acceptance and before the deliberate `2.1.0` version/release-preparation sequence. It does not freeze a release SHA and does not authorize tagging or publication.

## Direct runtime, development and packaging baseline

| Component | Repository selection | Latest stable verified | Status / action | Authoritative source |
| --- | --- | --- | --- | --- |
| CPython | 3.14 | 3.14.7 | Current | https://www.python.org/downloads/release/python-3147/ |
| PySide6-Essentials / Shiboken6 | 6.11.2 | 6.11.2 | Current | https://pypi.org/project/PySide6-Essentials/ |
| Nuitka | 4.2.1 | 4.2.1 | Current | https://pypi.org/project/Nuitka/ |
| pyaxmlparser | 0.3.31 | 0.3.31 | Current | https://pypi.org/project/pyaxmlparser/ |
| google-play-scraper | 1.2.7 | 1.2.7 | Current | https://pypi.org/project/google-play-scraper/ |
| requests | 2.34.2 | 2.34.2 | Current | https://pypi.org/project/requests/ |
| beautifulsoup4 | 4.15.0 | 4.15.0 | Current | https://pypi.org/project/beautifulsoup4/ |
| cryptography | 50.0.1 | 50.0.1 | Current | https://pypi.org/project/cryptography/ |
| PySide6-Essentials | 6.11.2 | 6.11.2 | Current | https://pypi.org/project/PySide6-Essentials/ |
| websocket-client | 1.9.2 | 1.9.2 | Current | https://pypi.org/project/websocket-client/ |
| Pillow | 12.3.0 | 12.3.0 | Current | https://pypi.org/project/Pillow/ |
| pytest | 9.1.1 | 9.1.1 | Current | https://pypi.org/project/pytest/ |
| Ruff | 0.16.8 | 0.16.8 | **Updated from 0.16.7** | https://pypi.org/project/ruff/0.16.8/ |
| mypy | 2.3.1 | 2.3.1 | Current | https://pypi.org/project/mypy/ |
| setuptools | 84.0.0 | 84.0.0 | Current | https://pypi.org/project/setuptools/ |
| wheel | 0.48.0 | 0.48.0 | Current | https://pypi.org/project/wheel/ |
| pip | release jobs upgrade bootstrap pip | 26.2.1 | Current stable | https://pypi.org/project/pip/ |
| Android Platform-Tools | `platform-tools-latest-*` managed endpoint | 37.0.1 | Current | https://developer.android.com/tools/releases/platform-tools |

Python 3.15 pre-release builds are not selected. The project policy excludes release candidates, betas, alphas, nightlies and development snapshots from the stable freshness baseline unless an explicit engineering decision changes that rule.

## Clean-environment Python audit

PR #202 Quality run `35674723949`, job `106578713093`, resolved the v2.1 dependency set on CPython 3.14 after the Ruff update.

Resolved release/test-path packages:

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
- `packaging 26.3`
- `pathspec 1.1.1`
- `Pillow 12.3.0`
- `pluggy 1.6.0`
- `pyaxmlparser 0.3.31`
- `pycparser 3.0`
- `Pygments 2.21.0`
- `PySide6-Essentials 6.11.2`
- `pytest 9.1.1`
- `requests 2.34.2`
- `ruff 0.16.8`
- `shiboken6 6.11.2`
- `soupsieve 2.9.2`
- `typing-extensions 4.16.0`
- `urllib3 2.8.0`
- `websocket-client 1.9.2`

`python -m pip check` returned `No broken requirements found.`

The complete `python -m pip list --outdated --format=json` result was:

```json
[]
```

Compared with the v2.0 historical audit, the unconstrained transitive resolver has already moved `ast-serialize` to 0.11.2, `idna` to 3.20 and `urllib3` to 2.8.0. Those are transitive dependencies rather than repository-owned direct pins; the clean environment resolved their current stable releases without source changes.

## GitHub Actions and provider actions

All maintained workflow action references were rechecked against their upstream release streams:

| Action | Repository reference | Latest stable verified | Status |
| --- | --- | --- | --- |
| `actions/checkout` | `@v7` | v7.0.1 | Current maintained major |
| `actions/setup-python` | `@v7` | v7.0.0 | Current maintained major |
| `actions/upload-artifact` | `@v7` | v7.0.1 | Current maintained major |
| `actions/download-artifact` | `@v8` | v8.0.1 | Current maintained major |
| `azure/login` | `@v3` | v3.1.0 | Current maintained major |
| `azure/artifact-signing-action` | `@v2` | v2.0.0 | Current maintained major |

The repository deliberately tracks supported action majors rather than patch tags. No maintained action requires a major-version migration at this gate.

## Runners, platform prerequisites and signing paths

GitHub's current hosted-runner reference lists the repository's maintained labels as supported standard runners.

- Windows x64 remains `windows-2025`.
- Windows ARM64 remains `windows-11-arm`. It is a supported standard ARM64 runner, not a public-preview runner. GitHub began migrating the `windows-11-arm` alias to the Visual Studio 2026 image on 2026-09-21, with rollout scheduled through 2026-09-30. The workflow metadata was corrected to `generally available`; the runner label was deliberately not changed.
- Linux x64 remains `ubuntu-22.04`. Newer Ubuntu images exist, but this is a deliberate supported binary-compatibility baseline rather than a stale tool pin; moving the build image can narrow the glibc compatibility contract.
- Linux ARM64 remains `ubuntu-24.04-arm`, a supported standard ARM64 label and the current architecture-specific release baseline.
- macOS ARM64 remains `macos-15`; Intel/x64 remains `macos-15-intel`. Both remain supported standard labels. A newer OS image is not substituted merely for freshness when it would change the release compatibility target.
- Quality continues to use the maintained `windows-latest` alias.

Windows production-signing source configuration remains `azure/login@v3` plus `azure/artifact-signing-action@v2` with GitHub OIDC. macOS production mode continues to use Developer ID Application signing, hardened runtime, `xcrun notarytool`, stapling and Gatekeeper validation. Fresh source configuration does not prove credentials, provider eligibility, signing or notarization; only real final production runs can provide that evidence.

## Validation evidence

Completed:

- Combined feature-complete Windows x64 packaged acceptance from `main` SHA `3a76e292bc45e8ff20bad39ffe4e2a5b0c0353b4`, workflow run `35655658931`, passed human acceptance before release-phase entry.
- That accepted package is product-acceptance evidence only. It is not a v2.1 release artifact and cannot be reused after the release toolchain changes.
- Ruff was updated to 0.16.8 on the focused freshness branch.
- The Windows ARM64 runner-status metadata was corrected without changing its supported runner label.
- PR #202 Quality run `35674723949` passed on the freshness-update head with **1586 tests**, Ruff 0.16.8, Qt offscreen smoke, `pip check`, and `pip list --outdated=[]`.
- The temporary branch-only dependency-snapshot Quality step used to collect the clean-environment evidence was removed after the evidence was captured.

Still required before this gate can become PASS:

1. exact-head Quality on the final evidence/test branch state;
2. affected native Windows ARM64 package validation from that same final branch head, exercising the refreshed `windows-11-arm` path and the updated Ruff lint gate;
3. record the successful run and package evidence here, then require final no-change Quality if the evidence-closing commit changes only documentation/tests.

## Gate result

**PENDING** until the affected native Windows ARM64 package validation above succeeds and this record is closed to PASS.

The final pre-release freshness gate remains mandatory after the deliberate v2.1 release-preparation changes and immediately before the exact release SHA is frozen. This entry record must not be copied forward as proof that components remain current at freeze time.
