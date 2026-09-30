# v2.2 release-phase entry freshness gate

Audit date: 2026-09-30 CEST.

Status: **BLOCKED.** Stable Qt 6.12.0 was published today but matching stable PySide/Shiboken packages are not available from the maintained release channels. Native OpenSSL/compiler/runner findings below also require resolution. Clean Python dependencies being current does not satisfy the whole-toolchain policy. The final pre-release freshness gate is still pending and must be repeated immediately before any future release SHA freeze.

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
| Qt supplied by PySide | 6.11.2 | **6.12.0**, released 30 Sep | **Blocked:** no matching stable PySide/Shiboken release; do not replace Qt binaries inside 6.11.2 wheels | [Qt announcement](https://www.qt.io/blog/qt-6.12-released), [stable source index](https://download.qt.io/official_releases/qt/6.12/6.12.0/), [Qt for Python release index](https://download.qt.io/official_releases/QtForPython/pyside6/) |
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

The signing Action's current major and v2.0.0 annotated tags both resolve to commit `c7ab2a863ab5f9a846ddb8265964877ef296ee82`. Inspection of its [actual composite action](https://github.com/Azure/artifact-signing-action/blob/c7ab2a863ab5f9a846ddb8265964877ef296ee82/action.yml) found older embedded tooling despite the direct Action itself being the latest release:

| Indirect provider component | Selected by current Action | Latest stable upstream | Action / validation | Authoritative source |
| --- | --- | --- | --- | --- |
| ArtifactSigning PowerShell module | 0.1.8 | 0.1.20 | Provider-path freshness unresolved; module version is internal to vendor Action | [PowerShell Gallery](https://www.powershellgallery.com/packages/ArtifactSigning/0.1.20) |
| Microsoft.Windows.SDK.BuildTools / SignTool package | 10.0.26100.4188 | 10.0.28000.2705 | Provider-path freshness unresolved; no input override exposed by current Action | [NuGet](https://www.nuget.org/packages/Microsoft.Windows.SDK.BuildTools/10.0.28000.2705) |
| Microsoft.ArtifactSigning.Client | 1.0.128 | 1.0.128 | Current by official registry | [NuGet](https://www.nuget.org/packages/Microsoft.ArtifactSigning.Client/1.0.128) |
| SignCLI optional package/cache declaration | 0.9.1-beta.26227.3 | 1.1.5 | Older beta is vendor-internal; not promoted to a stable selection or exercised by this audit | [NuGet](https://www.nuget.org/packages/sign/1.1.5) |
| actions/cache nested in signing Action | pinned v5.0.4 commit | v6.1.0 | Provider-path freshness unresolved; no direct repository cache Action to update | [Release](https://github.com/actions/cache/releases/tag/v6.1.0) |

These provider internals are recorded as additional unresolved maintained-tooling findings, not waived by a “current Action major” claim. A vendor update or deliberately validated integration change is required before declaring that maintained path fresh. Production signing remains out of scope under #154; no signing workflow, credential operation or vendor fork was activated here.

## Clean resolved environment and transitive packages

The official Python install manager extracted CPython **3.14.7 x64** into the ignored `build/v2.2-freshness/python3147` directory, verifying the signed Python download index. A new venv received `requirements-dev.txt` (including runtime requirements), `Nuitka==4.2.2`, `setuptools==84.0.0`, `wheel==0.48.0` and current pip 26.2.1. No global Python installation was changed.

Every installed distribution was independently compared with PyPI JSON release metadata, excluding prerelease/dev/yanked releases. All 36 installed distributions matched the latest stable upstream version. The following are resolver-selected dependencies, not new repository pins; “before” is the repository's unpinned resolver selection.

| Component | Repository before | Resolved = latest stable | Action / evidence | Authoritative source |
| --- | --- | --- | --- | --- |
| asn1crypto | resolver-selected | 1.5.1 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/asn1crypto/json) |
| ast_serialize | resolver-selected | 0.11.2 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/ast_serialize/json) |
| certifi | resolver-selected | 2026.7.22 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/certifi/json) |
| cffi | resolver-selected | 2.1.1 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/cffi/json) |
| charset-normalizer | resolver-selected | 3.5.2 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/charset-normalizer/json) |
| click | resolver-selected | 8.5.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/click/json) |
| colorama | resolver-selected | 0.4.6 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/colorama/json) |
| idna | resolver-selected | 3.20 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/idna/json) |
| iniconfig | resolver-selected | 2.3.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/iniconfig/json) |
| librt | resolver-selected | 0.16.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/librt/json) |
| lxml | resolver-selected | 6.1.3 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/lxml/json) |
| mypy_extensions | resolver-selected | 1.1.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/mypy_extensions/json) |
| packaging | resolver-selected | 26.3 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/packaging/json) |
| pathspec | resolver-selected | 1.1.1 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/pathspec/json) |
| pluggy | resolver-selected | 1.6.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/pluggy/json) |
| pycparser | resolver-selected | 3.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/pycparser/json) |
| Pygments | resolver-selected | 2.21.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/Pygments/json) |
| soupsieve | resolver-selected | 2.10 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/soupsieve/json) |
| typing_extensions | resolver-selected | 4.16.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/typing_extensions/json) |
| urllib3 | resolver-selected | 2.8.0 | Current; clean metadata comparison and pip check | [PyPI](https://pypi.org/pypi/urllib3/json) |

`pip check`: exit 0, `No broken requirements found.`

`pip list --outdated --format=json`: exit 0, exactly `[]`, no stderr. No remaining entries were ignored. `lxml` is an existing transitive dependency of pyaxmlparser; it was not added to the HTTP fallback, which still uses html.parser. `build` and its optional extras are not used and were not installed. Linux-only deployment additionally resolves [PyPI patchelf 0.19.1.0](https://pypi.org/pypi/patchelf/json), packaging [upstream patchelf 0.19.1](https://github.com/NixOS/patchelf/releases/tag/0.19.1); native Linux resolution is still required before a pass.

The clean runtime reports Qt **6.11.2** and cryptography OpenSSL **4.0.3, 29 Sep 2026**. CPython's independently bundled ssl module reports OpenSSL **3.5.7, 9 Jun 2026**; this is the official CPython 3.14.7 payload, not cryptography's OpenSSL. The [OpenSSL release page](https://www.openssl-library.org/source/) already publishes **3.5.9 LTS**, **3.6.5** and **4.0.3**, all dated 29 Sep. Thus CPython's bundled SSL and Vcpkg's 3.6.4 are older even within their respective maintained branches. This additional bundled-component finding is unresolved under the strict whole-toolchain policy; it is not waived because the containing Python release is current. A refreshed official payload or deliberately validated supported build/policy resolution is needed. Bundled libraries must not be replaced ad hoc in official Python/Qt wheels.

PySide's deployment helper was inspected: without `--nuitka-version`, `install_dependencies` removes the generated default Nuitka version constraint when the installed compiler is used. Thus its default.spec mention of 4.1.1 does not downgrade the repository-installed 4.2.2. The shipped Qt/PySide/Shiboken package versions remain paired; no Addons/QML migration is introduced.

## Android Platform-Tools / ADB

[Android's stable release notes](https://developer.android.com/tools/releases/platform-tools) identify **37.0.1**. All three actual latest endpoint ZIPs were downloaded on the audit date; each `platform-tools/source.properties` reports `Pkg.Revision=37.0.1`. Archive members pass the repository's path-containment assumptions and each contains the expected executable. Windows ADB executed successfully: protocol version 1.0.41, build **37.0.1-15733141**. No phone commands were run.

| Repository selection / authoritative download | Latest stable resolved | SHA-256 | Action |
| --- | --- | --- | --- |
| [windows latest endpoint](https://dl.google.com/android/repository/platform-tools-latest-windows.zip) | 37.0.1 | `45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99` | Current; retain latest endpoint |
| [macos latest endpoint](https://dl.google.com/android/repository/platform-tools-latest-darwin.zip) | 37.0.1 | `ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d` | Current; retain latest endpoint |
| [linux latest endpoint](https://dl.google.com/android/repository/platform-tools-latest-linux.zip) | 37.0.1 | `d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1` | Current; retain latest endpoint |

Linux ARM64 deliberately uses a native distro/SDK ADB because the Google Linux archive is x64. That architecture limitation is unchanged. Its distro package is not represented as Google's 37.0.1 managed binary.

## Native toolchain / runner freshness findings

The official [runner inventory](https://github.com/actions/runner-images/tree/14d8569222caf7662f18b6875bf518683db9ff58) was inspected along with all workflow-selected prerequisites. Current maintained runner images are refreshed by GitHub; ordinary apt package revisions are not converted into repository pins. A supported older OS image is not automatically proof of latest-stable compiler/SDK freshness. These findings prevent an unconditional gate pass.

| Component/group | Repository before / selected path | Latest stable upstream or current official inventory | Action / validation | Authoritative source |
| --- | --- | --- | --- | --- |
| Windows x64 runner/compiler | windows-2025, Nuitka `--msvc=latest` | Windows Server 2025; current label inventory selects VS 2026 18.10.12210.168 | No hard-coded compiler version to replace; exact native build evidence required | [Windows current image](https://github.com/actions/runner-images/blob/14d8569222caf7662f18b6875bf518683db9ff58/images/windows/Windows2025-VS2026-Readme.md) |
| Windows ARM64 runner/compiler | windows-11-arm; incorrectly described as preview | Windows 11 ARM64 / VS 2026 GA; label migration scheduled to finish 30 Sep | Updated RUNNER_STATUS to generally available; no production signing activated | [Official migration notice](https://github.com/actions/runner-images/issues/14602), [image](https://github.com/actions/runner-images/blob/14d8569222caf7662f18b6875bf518683db9ff58/images/windows/Windows11-VS2026-Arm64-Readme.md) |
| Vcpkg tool / ports | runner VCPKG_INSTALLATION_ROOT, native static-MD OpenSSL triplet | tool release 2026-09-26; registry release 2026.07.29; current master OpenSSL port 3.6.4#1 | **Blocked for latest OpenSSL**; blindly upgrading Vcpkg cannot provide OpenSSL 4.0.3 | [Tool release](https://github.com/microsoft/vcpkg-tool/releases/tag/2026-09-26), [registry release](https://github.com/microsoft/vcpkg/releases/tag/2026.07.29), [exact port](https://github.com/microsoft/vcpkg/blob/a42757564758c60651ebc616d9b000b7b91249ef/ports/openssl/vcpkg.json) |
| OpenSSL for cryptography | 50.0.1 wheels carried 4.0.2; ARM64 source build uses Vcpkg port | **4.0.3**, stable; 4.1 beta excluded | Updated cryptography wheels carry 4.0.3; **Windows ARM64 source path blocked**, official port remains 3.6.4 | [OpenSSL releases](https://www.openssl-library.org/source/), [cryptography changelog](https://cryptography.io/en/latest/changelog/#v50-0-2) |
| OpenSSL bundled with official CPython | 3.5.7 in current Windows CPython 3.14.7 | 3.5.9 on LTS branch; 4.0.3 overall | **Unresolved vendor payload freshness**; current CPython alone is not proof of current embedded SSL | [OpenSSL releases](https://www.openssl-library.org/source/), [CPython release](https://www.python.org/downloads/release/python-3147/) |
| cryptography wheel coverage | Windows ARM64 and macOS Intel use source installation | 50.0.2 has Windows x64, Linux x64/ARM64 and macOS ARM64 wheels, no Windows ARM64/macOS Intel wheels | Source-built platforms need compiler/OpenSSL/package evidence; wheel success on x64 is insufficient | [Exact PyPI file metadata](https://pypi.org/pypi/cryptography/50.0.2/json) |
| Linux runners | ubuntu-22.04 x64; ubuntu-24.04-arm; ubuntu-24.04 assembly/maintenance/UI audit | GA 26.04 / 26.04-arm also available; selected image revisions 20260920.303.1 / 20260920.129.1 / 20260920.314.1 | **Unresolved latest-image vs binary compatibility baseline**; not silently promoted to current under the strict gate | [Runner inventory](https://github.com/actions/runner-images/tree/14d8569222caf7662f18b6875bf518683db9ff58), [existing compatibility contract](BUILDING.md#linux) |
| Linux native prerequisites | distro gcc/binutils/zip/unzip/Qt display libraries, patchelf via deployment | current selected-distro packages; patchelf 0.19.1.0 | No deliberately pinned apt package revision; changing distro/compiler baseline requires native architecture/ABI/package/legal checks | [Ubuntu x64 image](https://github.com/actions/runner-images/blob/14d8569222caf7662f18b6875bf518683db9ff58/images/ubuntu/Ubuntu2204-Readme.md), [Ubuntu ARM64 image](https://github.com/actions/runner-images/blob/14d8569222caf7662f18b6875bf518683db9ff58/images/ubuntu/Ubuntu2404-Arm64-Readme.md) |
| macOS runner / Xcode / Apple Clang | macos-15 / macos-15-intel; default Xcode 16.4, selectable through 26.3 | stable **Xcode 27** requires macOS 26.6+; 27.1 beta / 27.2 beta excluded; GA macos-26 images default to 26.6 | **Blocked:** newest stable Xcode cannot run on selected macOS 15 host; no validated two-architecture replacement exists in this gate | [Apple requirements](https://developer.apple.com/xcode/system-requirements), [macOS 15 image](https://github.com/actions/runner-images/blob/14d8569222caf7662f18b6875bf518683db9ff58/images/macos/macos-15-Readme.md), [macOS 26 image](https://github.com/actions/runner-images/blob/14d8569222caf7662f18b6875bf518683db9ff58/images/macos/macos-26-Readme.md) |
| Windows signing provider | azure/login v3 + artifact-signing-action v2, SHA-256/RFC3161, PowerShell native verification | current maintained provider Actions above | Source integration current; production credentials/trust untested and remain #154 | [Microsoft integration documentation](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations) |
| Apple signing/notarization tools | codesign, security, xcrun notarytool/stapler, spctl, lipo/otool from OS/Xcode | OS/Xcode supplied; follow native toolchain finding above | Engineering signing only; no production signing/notary invocation or credential claim | [Apple notarization documentation](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) |
| Legal/source and checksum tooling | repository Python helpers, stdlib hashlib/tarfile/zipfile, platform shell tools | selected current Python / runner distributions; no separate pinned release utility | Legal preflight passes for Qt sources, certifi, CPython license and Nuitka; strict package legal validation still required | [Canonical legal preflight](../.github/scripts/preflight_release_legal_material.py), [source preparation](../.github/scripts/prepare_release_legal_bundle.py) |

Apple's [current Xcode 27 release notes](https://developer.apple.com/documentation/xcode-release-notes/xcode-27-release-notes) additionally restrict the host to Apple silicon. That is an explicit incompatibility with the current native Intel build job, not merely an untested version bump. The six-platform contract must be preserved; adopting the latest compiler requires a validated replacement build strategy for the Intel artifact or a deliberate policy resolution. This gate does not silently drop Intel support or adopt a preview runner.

The built-in Device Specific profiles' goopdl v1.2.1 attribution URLs identify the original copied data and license provenance; they are not an installed/executed goopdl dependency or an instruction to replace profiles during a toolchain audit. Nuitka-provided SCons/native dependency inspection are supplied by the current Nuitka release; no separate repository compiler/helper version pin was found.

## Validation and update inventory

- Exact runtime pins changed: `requirements.txt` and `pyproject.toml`, cryptography 50.0.1 to 50.0.2.
- Duplicated runtime assertion changed: `.github/workflows/build-windows-exe.yml`, cryptography 50.0.2 on ARM64.
- Development pin changed: `requirements-dev.txt`, Ruff 0.16.8 to 0.16.9.
- Runner evidence correction: Windows ARM64 status now GA. No Action reference changed.
- Current/future status reconciled in AGENTS, README, PROJECT_STATUS, HANDOFF_V2.2 and ROADMAP. AGENTS labels the unchanged Python 3.14 development baseline as v2.2. Historical v2.1 records remain unchanged. `tests/test_cross_platform_legal_manifest.py` deliberately retains synthetic 50.0.1 fixture metadata; it is not a dependency pin and the fixture tests passed.
- Focused tests: **65 passed** across credential protection, cross-platform legal manifest, release preflight/workflows, freshness contracts and headless CLI.
- Full pytest: **1638 passed, 9 skipped** on Python 3.14.7, with one local pytest cache-write warning. Initial sandbox runs failed on default application-data/temp write permissions; rerunning with isolated application data and temporary directories passed. An intervening unrestricted run was stopped and is not acceptance evidence.
- `compileall -q playstore_app_audit`: PASS.
- Canonical CI Ruff scope, including maintained release helpers: PASS on Ruff 0.16.9.
- Required helper py_compile and handoff PowerShell parser check: PASS.
- Canonical Qt offscreen smoke: PASS, with isolated application data.
- CLI dispatch smoke: PASS through `main.py cli audit --help` with a meta-path guard rejecting PySide6 and UI imports. Focused CLI tests also exercise audit dispatch/output semantics.
- `git diff --check`: PASS.
- Clean dependency and legal preflight evidence as above.
- Hosted exact-implementation-head Quality **#608 / 36771154934** (PR event) and **#609 / 36771199689** (manual exact-branch checkout): SUCCESS on `2fee4e10cb9c67accbab909b042aaf4d0005aac9`, Python 3.14.7, **1647 passed**, Ruff and canonical Qt smoke. The final documentation head must also receive exact-head Quality before handoff.

## Native evidence and final disposition

Windows x64 package validation run **36771203775 / #145** was still running at the user-requested pause on 2026-09-30 at 20:30 UTC, on implementation head `2fee4e10cb9c67accbab909b042aaf4d0005aac9`. Its outcome has not yet been collected. PR #217 remains draft until the blockers are resolved. This is deliberate package evidence, not a release artifact; app version 2.1.0 is intentional.

The gate cannot pass while Qt and the OpenSSL/native platform and latest-runner/compiler questions above remain unresolved. First, adopt a corresponding stable PySide/Shiboken release carrying Qt 6.12.0 when published, or validate an explicitly maintained alternative build; no such stable binding release was available at this audit. A bare Qt binary substitution would invalidate the supported wheel combination and existing source/legal evidence. Required next work also includes a validated latest-stable OpenSSL provisioning path for Windows ARM64, a stable Xcode 27/macOS host path for both supported Mac architectures, and an explicit resolution of newer Linux runner selection versus the maintained binary compatibility baseline. If preserving an older maintained baseline is desired, it requires a deliberate engineering policy decision; this audit does not silently waive the strict invariant. Once resolved, repeat every affected clean-environment, source, native/architecture, package CLI/GUI and legal/source check, then repeat this entry gate.

The **final pre-release freshness gate is still pending**. This entry record cannot substitute for it. No tag, frozen release SHA, GitHub Release, release assembly or public asset mutation is authorized by these results.

## User-requested pause and resumption checkpoint

Work is **paused at the user's request** because of the current Codex credit window. The freshness gate remains **BLOCKED**, not passed. The working branch is `release/v2.2-entry-freshness`; the durable review location is [draft PR #217](https://github.com/mrc-labs/PlayStoreAppAudit/pull/217). This checkpoint records the findings after implementation commit `2fee4e10cb9c67accbab909b042aaf4d0005aac9`. The checkpoint commit itself has not yet received exact-head Quality validation.

The already-dispatched Windows run may finish independently; it has not been cancelled. No other native build was dispatched. Local supporting evidence and the isolated Python 3.14.7 environment remain under the ignored `build/v2.2-freshness/` directory, including `environment.json`, `audit_environment.py`, `adb-evidence.json`, `legal-preflight.json`, `pytest-isolated.log`, `quality-609.log`, upstream snapshots and the v2.1 release/tag fingerprints. These local files are not included in the Git commit; the findings and links are preserved in this document.

Resume by checking the branch, clean working tree and remote state, then collect the result/logs/artifacts of Windows run `36771203775`. Complete the applicable packaged startup, architecture, provenance and legal checks without treating compiler success alone as acceptance. Recheck upstream stable metadata because releases may have changed during the pause. Resolve the Qt, bundled/native OpenSSL, Linux runner, Xcode/Intel and embedded signing-action component findings recorded above, preserving all six platforms and existing authorization limits. Complete affected validation and the evidence review, and obtain successful Quality on the final exact PR head before claiming completion. Keep #212 open and PR #217 draft while blockers remain; do not freeze, tag, publish, assemble or mutate v2.1 assets. The separate final pre-release freshness gate remains pending.
