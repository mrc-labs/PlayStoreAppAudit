# v2.2 release-phase entry freshness gate

Audit date: 2026-09-30 CEST.

Status: **IN PROGRESS — not passed.** This record is being completed with clean-environment, source Quality and affected native/package evidence. The final pre-release freshness gate is still pending and must be repeated immediately before any future release SHA freeze.

## Scope and starting state

Local `main`, local `origin/main` and live remote `refs/heads/main` were verified as `e204d68e2d969f7d0a30ca166243020fc115ae44` before editing. The tree was clean. Work uses `release/v2.2-entry-freshness` and one focused PR. Issue #212 remains open; its third coordination comment confirms all three pillars complete through PRs #214, #215 and #216, with baseline Quality #607 / run `36754783824` passing.

Application version remains **2.1.0**. These are entry-gate checks and development package evidence, not a release freeze, release assembly or publication. Published v2.1 source/tag/assets remain immutable. Production signing remains separate issue #154.

## Direct dependencies and build tools

Each row was checked on the audit date. PyPI release metadata was checked for stable, non-yanked releases; prereleases are excluded.

| Component | Repository before | Latest stable upstream | Action | Authoritative source |
| --- | --- | --- | --- | --- |
| CPython | stable 3.14 line; local interpreter 3.14.6 | 3.14.7 | Current repository baseline; isolated local 3.14.7 extraction for validation; 3.15 remains prerelease | [Python releases](https://www.python.org/downloads/) |
| pyaxmlparser | 0.3.31 | 0.3.31 | Current | [PyPI](https://pypi.org/pypi/pyaxmlparser/json) |
| google-play-scraper | 1.2.7 | 1.2.7 | Current | [PyPI](https://pypi.org/pypi/google-play-scraper/json) |
| requests | 2.34.2 | 2.34.2 | Current | [PyPI](https://pypi.org/pypi/requests/json) |
| beautifulsoup4 | 4.15.0 | 4.15.0 | Current | [PyPI](https://pypi.org/pypi/beautifulsoup4/json) |
| cryptography | 50.0.1 | 50.0.2 | Updated runtime pins and Windows ARM64 assertion; native validation pending | [PyPI](https://pypi.org/pypi/cryptography/json), [changelog](https://cryptography.io/en/latest/changelog/#v50-0-2) |
| PySide6-Essentials / Shiboken6 | 6.11.2 / 6.11.2 | 6.11.2 / 6.11.2 | Current; Qt runtime version verified in clean environment | [PySide](https://pypi.org/pypi/PySide6-Essentials/json), [Shiboken](https://pypi.org/pypi/shiboken6/json) |
| websocket-client | 1.9.2 | 1.9.2 | Current | [PyPI](https://pypi.org/pypi/websocket-client/json) |
| Pillow | 12.3.0 | 12.3.0 | Current | [PyPI](https://pypi.org/pypi/Pillow/json) |
| pytest | 9.1.1 | 9.1.1 | Current | [PyPI](https://pypi.org/pypi/pytest/json) |
| Ruff | 0.16.8 | 0.16.9 | Updated requirements-dev.txt | [PyPI](https://pypi.org/pypi/ruff/json) |
| mypy | 2.3.1 | 2.3.1 | Current | [PyPI](https://pypi.org/pypi/mypy/json) |
| Nuitka | 4.2.2 | 4.2.2 | Current in all workflows/helpers | [PyPI](https://pypi.org/pypi/Nuitka/json) |
| pyside6-deploy | supplied by PySide 6.11.2 | supplied by PySide 6.11.2 | Current; deployment mechanism remains Nuitka standalone | [Qt deployment documentation](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) |
| pip | upgraded at workflow install | 26.2.1 | Current clean resolution | [PyPI](https://pypi.org/pypi/pip/json) |
| setuptools | 84.0.0 | 84.0.0 | Current build-system pin | [PyPI](https://pypi.org/pypi/setuptools/json) |
| wheel | 0.48.0 | 0.48.0 | Current build-system pin | [PyPI](https://pypi.org/pypi/wheel/json) |
| build | not used by maintained workflows | 1.6.1 | Audited; not added to dependency graph | [PyPI](https://pypi.org/pypi/build/json) |

## External Actions

All nine maintained workflows were inspected: Quality, Windows/Linux/macOS builds, Windows signing, both assemblers, retention and UI style audit. There are exactly six external Action identities; no independent cache/release-publishing Action is used. Maintained major refs consume the current minor/patch automatically.

| Action | Repository before | Latest stable | Action | Authoritative source |
| --- | --- | --- | --- | --- |
| actions/checkout | v7 | v7.0.1 | Current | [Release](https://github.com/actions/checkout/releases/tag/v7.0.1) |
| actions/setup-python | v7 | v7.0.0 | Current | [Release](https://github.com/actions/setup-python/releases/tag/v7.0.0) |
| actions/upload-artifact | v7 | v7.0.1 | Current | [Release](https://github.com/actions/upload-artifact/releases/tag/v7.0.1) |
| actions/download-artifact | v8 | v8.0.1 | Current | [Release](https://github.com/actions/download-artifact/releases/tag/v8.0.1) |
| azure/login | v3 | v3.1.0 | Current; production signing not activated | [Release](https://github.com/Azure/login/releases/tag/v3.1.0) |
| azure/artifact-signing-action | v2 | v2.0.0 | Current; production signing not activated | [Release](https://github.com/Azure/artifact-signing-action/releases/tag/v2.0.0) |

## Remaining evidence

Clean resolution, Platform-Tools latest endpoints, runner/compiler/vendor tooling, legal/source checks, source tests and affected native/package results are being recorded before a final gate decision. No pending item is treated as a pass.
