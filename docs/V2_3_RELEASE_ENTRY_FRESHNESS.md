# v2.3 release-entry component freshness

**Historical Phase B record, superseded for current state.** v2.3.0 is published at `8d476dc5507d8249d8cd62c861095ed3e443f0af`; final freshness, canonical six-platform/assembly acceptance and independent public-byte verification subsequently passed. Normally merged PR #234 restored rolling stable Python 3.14 / `check-latest: true` at post-release PR #234 baseline `19e2f14644000f9fbc11f1f7052fb16438692257`, with Quality #682 SUCCESS. Exact 3.14.8 release evidence below is preserved. [Closure audit](V2_3_POST_RELEASE_CLOSURE.md) records later outcomes and outstanding work. All preparation/pending statements below describe the original audit boundary, not current publication state.

Audit date: **2026-10-05 CEST** (primary queries began `2026-10-04T22:00:49Z`, already October 5 locally). This is a fresh entry audit, not copied v2.2 approval. Scope follows [the permanent ownership policy](RELEASE_COMPONENT_FRESHNESS.md): **A** directly controlled, **B** supported parent bundle, **C** vendor internals, **D** supported OS/compiler baseline preserving six targets and compatibility floors.

**Entry conclusion: PASS for Phase B source preparation.** No newer stable compatible direct pin or Action major requires a repository update. One independently resolved mypy development dependency, ast_serialize, advances to 0.12.1 in the clean environment. No final package, signing, legal-compliance or frozen-SHA acceptance is implied. Final complete freshness and all six native candidate validations remain mandatory in Phase C.

## CPython and exact runtime staging (A)

[Python downloads](https://www.python.org/downloads/), the [3.14.8 release](https://www.python.org/downloads/release/python-3148/) and [release changelog](https://docs.python.org/release/3.14.8/whatsnew/changelog.html) freshly establish **3.14.8**, released 2026-09-30 as an expedited security/maintenance release, as current stable 3.14. It includes SSLContext, archive handling and other fixes plus bundled OpenSSL 3.5.9/Expat 2.8.5 updates. The [lifecycle table](https://devguide.python.org/versions/) lists 3.14 in bugfix support through its October 2030 security EOL. Python 3.15 remains outside the approved baseline; no separate migration or six-target evidence exists.

The freshly downloaded [actions/python-versions manifest](https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json) lists stable 3.14.8 for Windows x64/ARM64, macOS x64/ARM64 and Ubuntu 24.04 x64/ARM64. It also exposes the **same patch** for Ubuntu 22.04 x64. The [official release](https://github.com/actions/python-versions/releases/tag/3.14.8-36806082737) asset for that compatibility distribution was downloaded and verified by the canonical `download_linux_compat_python.py` helper against upstream size/digest; SHA-256 `3b6ca0860f3e23ca51901c78b7c945253ef35b9938dbc6529a5fea2183342363`. No custom distribution or patch downgrade was used. Local fresh Python reports `3.14.8`, release level `final`.

**Decision: freshly select 3.14.8, current/no runtime upgrade.** Separate authorized Phase B work stages ordinary YAML exact literals in all **11 setup environments across nine workflows**: `quality.yml`, `build-windows-exe.yml`, `build-linux.yml`, `build-macos.yml`, `assemble-release.yml`, `assemble-windows-engineering-release.yml`, `sign-windows.yml`, `ui-style-audit.yml`, `actions-retention.yml`. Every setup has immediate stable/full-equality checks before its consumer, rolling `check-latest` removed, and existing post-setup equality strengthened. Windows standalone and Linux x64 compatibility helpers require the same exact patch, retaining GIL/architecture/security checks. Tests reject older/newer patches, other minor versions and prereleases. Entry audit alone does not freeze pins or a SHA: repeat final freshness before the exact main freeze. Phase E restores rolling stable 3.14 / `check-latest: true` with matched guard/test/context updates.

## Complete Python environment (A, with matched Qt parent B)

Installed afresh in an isolated temporary venv from `requirements-dev.txt`, plus maintained Nuitka/setuptools/wheel build tooling. All selected versions were compared with non-yanked stable PyPI metadata, including release dates, Python constraints and wheel files. `pip check` passed; `pip list --outdated --format=json` returned **[]**. The full per-component inventory and primary metadata links follow below. No runtime/dev manifest pin changed.

ast_serialize **0.12.1**, released 2026-10-03, replaces the previously locally resolved 0.12.0; it is an independently resolved mypy dependency, not a newly added application dependency. Current cp39-abi3 wheels cover both Windows architectures, both macOS architectures and manylinux 2.17 x64/ARM64, compatible with Python 3.14 and existing floors. Fresh Windows install/source validation uses 0.12.1; clean other-platform resolution/package checks remain Phase C evidence.

## Qt/PySide/Shiboken and deployment parents (B)

[Public Qt for Python index](https://download.qt.io/official_releases/QtForPython/pyside6/) and PyPI metadata still select matched **PySide6-Essentials 6.11.2 / Shiboken6 6.11.2 / Qt 6.11.2**. Actual fresh `qVersion()` and both bindings agree. Python constraint is `>=3.10,<3.15`, cp310-abi3. Wheel paths: Windows amd64/ARM64, macOS 13 universal2, manylinux 2.34 x64 and 2.39 ARM64. The nominal wheel tag is distinct from measured package requirements; historical v2.2 all-ELF maxima are not new v2.3 acceptance. Actual ABI and macOS deployment floors must be measured again on candidates.

Independent [Qt 6.12.0](https://download.qt.io/official_releases/qt/6.12/6.12.0/) exists but public matched stable bindings remain 6.11.2. **Current supported parent/no action; future binding-release watch.** Do not swap independently newer Qt binaries into these wheels.

[pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) is shipped by the selected binding parent and uses explicit maintained **Nuitka 4.2.2**, current stable. Existing standalone/native paths remain. Nuitka's [SCons selector](https://github.com/Nuitka/Nuitka/blob/4.2.2/nuitka/build/SconsInterface.py) bundles Windows Python-3.14 SCons **4.10.1**, Unix **3.1.2** and legacy Windows **4.3.0** paths. Independent SCons **4.11.1** is an upstream observation, not the selected integration. Do not override the supported compiler parent solely for version arithmetic.

Observed fresh Windows parent bundles:

| Parent | Actual embedded versions | Decision |
| --- | --- | --- |
| CPython 3.14.8 | OpenSSL 3.5.9; Expat 2.8.5; SQLite 3.50.4; zlib 1.3.1.zlib-ng | Current official runtime bundle; no independent replacement |
| cryptography 50.0.2 wheel | OpenSSL 4.0.3 | Current supported parent; separate native source integrations below |
| lxml 6.1.3 wheel | libxml2 2.11.9; libxslt 1.1.45 | Supported security-patched parent; [upstream changes](https://github.com/lxml/lxml/blob/lxml-6.1.3/CHANGES.txt), no independent swap |
| Pillow 12.3.0 | FreeType 2.14.3, LittleCMS 2.19, WebP 1.6.0, AVIF 1.4.2, RAQM 0.10.5, FriBidi 1.0.11, HarfBuzz 14.2.1, libjpeg-turbo 3.1.4.1, JPEG2000 2.5.4, TIFF 4.7.1, zlib-ng 2.3.3, Tk 9.0 | Current supported parent; runtime feature inventory recorded, no independent swap |

`lxml` remains pyaxmlparser's declared APK-parser dependency; Google Play HTTP parsing continues to use BeautifulSoup with `html.parser`. No new dependency was added.

## Direct Actions (A) and vendor internals (C)

Every maintained workflow `uses:` reference was inventoried; no other external Action was found. Latest stable releases and actual action manifests were freshly read:

| Direct selected Action | Current stable upstream | Runtime/decision and primary evidence |
| --- | --- | --- |
| actions/checkout@v7 | 7.0.1 | Node 24; current major, [release](https://github.com/actions/checkout/releases/tag/v7.0.1) |
| actions/setup-python@v7 | 7.0.0 | Node 24; current major, [release](https://github.com/actions/setup-python/releases/tag/v7.0.0) |
| actions/upload-artifact@v7 | 7.0.1 | Node 24; current major, [release](https://github.com/actions/upload-artifact/releases/tag/v7.0.1) |
| actions/download-artifact@v8 | 8.0.1 | Node 24; current major, [release](https://github.com/actions/download-artifact/releases/tag/v8.0.1) |
| Azure/login@v3 | 3.1.0 | Node 24; current major, [release](https://github.com/Azure/login/releases/tag/v3.1.0) |
| Azure/artifact-signing-action@v2 | 2.0.0 | Composite; current stable parent, [release](https://github.com/Azure/artifact-signing-action/releases/tag/v2.0.0) |

**No Action pin change.** No application Node dependency/setup-node is introduced.

Actual [signing parent manifest](https://github.com/Azure/artifact-signing-action/blob/v2.0.0/action.yml) and [login lock](https://github.com/Azure/login/blob/v3.1.0/package-lock.json) expose vendor-owned observations: ArtifactSigning module **0.1.8** versus [Gallery 0.1.20](https://www.powershellgallery.com/packages/ArtifactSigning); SDK BuildTools **10.0.26100.4188** versus NuGet **10.0.28000.2705**; signing client **1.0.128**, current; optional Sign CLI **0.9.1-beta.26227.3** versus stable **1.1.5**; nested cache **v5.0.4** versus current **v6.1.0**; login core **1.11.1** versus **3.0.1**, exec **1.1.1** versus **3.0.0**, io **1.1.2** versus **3.0.2**. NuGet/npm latest metadata was independently queried, links in the source ledger below.

**Supported latest vendor parent/upstream observations, no fork or unsafe internal override.** Repository configuration does not expose those implementation pins. No demonstrated applicable advisory, unsupported parent or broken integration was found in the checked sources. Reopen on parent/support/advisory changes; this is not production trust acceptance. #154 remains deferred and no signing workflow was run.

## Native build and OS prerequisites (A/B/D)

| Selected integration | Fresh stable/support evidence | Decision |
| --- | --- | --- |
| Windows release `windows-2025`, `windows-11-arm`; Quality `windows-latest` | [Runner labels](https://github.com/actions/runner-images/blob/main/README.md) and architecture inventories: supported GA VS 2026 **18.10.12217.157**, PowerShell **7.6.6**; native ARM64 path retained | Current supported OS/compiler bundles (D); log actual runner revisions at build time, preserve native MSVC/64-bit/GIL checks |
| Windows ARM64 Rust source cryptography | Stable **Rust 1.99.0** (2026-10-01), paired Cargo **0.100.0**, [stable manifest](https://static.rust-lang.org/dist/channel-rust-stable.toml); explicit native aarch64 host | Current independent toolchain (A); no update |
| Windows ARM64 vcpkg OpenSSL | Registry `eb2d3a3279fd019cb7733072d86900d0ad2a1aef`, current [tool release](https://github.com/microsoft/vcpkg-tool/releases/latest) **2026-09-26**; selected/current [OpenSSL port](https://github.com/microsoft/vcpkg/blob/master/ports/openssl/vcpkg.json) **3.6.5** | Current maintained integration; no update. OpenSSL 3.6 support ends **2026-11-01**, explicit release-delay watch |
| Linux hosts Ubuntu **24.04** both architectures | Fresh inventories: OS **24.04.5**, x64 image `20260927.320.1`, ARM64 `20260927.135.1`; selected GCC **13.3.0**, binutils **2.42-4ubuntu2.10**, distro patchelf integration | Current supported native hosts (D), support through May 2029; no implicit floor change |
| Linux x64 Ubuntu **22.04** sysroot/probe/backward smoke | [Ubuntu lifecycle](https://ubuntu.com/about/release-cycle), supported through May 2027; official same-patch Python distribution verified | Intentional compatibility environment, not a hosted 22.04 build runner. Preserve sysroot, compiler probe, all-ELF GLIBC/GLIBCXX inspection and actual packaged GUI/CLI backward smoke |
| Linux OpenSSL vendor security integration | [Jammy 3.0.2-0ubuntu1.30](https://launchpad.net/ubuntu/jammy/+source/openssl), [Noble 3.0.13-0ubuntu3.16](https://launchpad.net/ubuntu/noble/+source/openssl), [USN-8847-1](https://ubuntu.com/security/notices/USN-8847-1), 2026-09-29 | Current Ubuntu-maintained security packages (D). Existing workflows already refresh apt and enforce these floors; runner inventory can lag at Noble .15. Upstream OpenSSL 3.0 EOL does not end Ubuntu vendor support; do not substitute an independent major |
| Linux patchelf | Distro Noble **0.18.0-1.1build1** vendor helper; independent upstream/PyPI **0.19.1 / 0.19.1.0** | Supported OS helper (D), not a selected independent Python package; no global override |
| macOS `macos-26`/`macos-26-intel`, explicit Xcode **26.6** | [Intel inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-Readme.md), [ARM64 inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md): Xcode build **17F113**, Clang **21.0.0**; OS Intel **26.6.1**/ARM64 **26.6.2** | Current common supported host/compiler (D). [Apple Xcode 27](https://developer.apple.com/xcode/system-requirements/) does not preserve Intel; runner preview does not authorize adoption or a floor increase |
| macOS Intel source cryptography | No current Intel wheel in cryptography 50.0.2; stable Rust **1.99.0**, [rustup **1.29.1**](https://static.rust-lang.org/rustup/release-stable.toml), official Intel installer checksum matches `259e2b84274434085163fe8d556510571772cda2aa6d87ca6aa664f57bc644e3` | Current A/native supported path. No Homebrew Intel bottle assumption. ARM64 retains native wheel |
| macOS Intel static OpenSSL **4.0.3** | [Official checksum](https://github.com/openssl/openssl/releases/download/openssl-4.0.3/openssl-4.0.3.tar.gz.sha256) matches `325b5c806167c13b40b1ffeadfe0248197c00eccc4cf123ec1e28d2d2fd216d9`; [support policy](https://openssl-library.org/policies/releasestrat/) supports 4.0 through **2027-05-14** (3.5 LTS through 2030-04-08) | Current independently provisioned compatible release (A), static source build retains architecture and deployment flags |
| Apple codesign/security/notarytool/stapler/spctl | Supplied by selected supported Xcode/macOS parent; [notarytool migration](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool) uses the supported successor to retired altool | Supported tooling parent (B/D), no migration required; engineering ad-hoc only, no Developer ID/notarization acceptance |

Existing deployment targets x64 10.15/ARM64 11.0 are requested compile settings, not proof every bundled binary runs there. Matched Qt wheel metadata and real Mach-O floors must remain distinct; Phase C measures actual final package requirements. No six-target requirement or compatibility floor was changed. Unchanged v2.2 native path evidence supports maintaining integrations, not acceptance of unbuilt v2.3 packages.

## Android Platform-Tools (A/D)

[Official release notes](https://developer.android.com/tools/releases/platform-tools) and fresh downloads confirm stable **37.0.1** on all three managed latest endpoints. All archives passed CRC integrity, expected member/executable and `source.properties` revision checks:

| Endpoint | Bytes | SHA-256 | Executable architecture |
| --- | --- | --- | --- |
| [Windows](https://dl.google.com/android/repository/platform-tools-latest-windows.zip) | 8,044,989 | `45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99` | Official PE i386 (`0x14c`), existing supported x64/ARM64 host execution contract, not claimed native ARM64 |
| [Linux](https://dl.google.com/android/repository/platform-tools-latest-linux.zip) | 9,054,187 | `d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1` | ELF x64 (`EM_X86_64=62`); no Google Linux ARM64 archive claim |
| [macOS](https://dl.google.com/android/repository/platform-tools-latest-darwin.zip) | 16,110,554 | `ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d` | Universal fat binary, two architectures |

**Current/no endpoint change.** Platform-specific executable names, safe archive extraction and native Linux ARM64 distro fallback remain behind device/platform boundaries. Noble's native ARM64 [adb **34.0.4-debian**](https://packages.ubuntu.com/noble/adb) is the maintained vendor integration (D), not a downloadable Google ARM64 binary. No connected-device mutation or ADB installation/uninstallation was performed.

## Release/legal/API infrastructure

[GitHub REST versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions) confirms selected **2026-03-10**, current. Historical 2022-11-28 has EOL 2028-03-10 and is not the selected contract. [Artifact API](https://docs.github.com/en/rest/actions/artifacts) continues to support the repository's size/digest/provenance checks. All maintained REST headers were inventoried; no stale selected version. **Current/no API migration.**

Legal/source preparation remains canonical preflight plus strict bundle preparation, per-platform validation and same-SHA consolidation through `assemble-release.yml`; archive/checksum helpers use maintained Python stdlib, no independent obsolete binary added. Fresh strict preflight passed on project **2.3.0**, Python **3.14.8**, PySide/Qt **6.11.2**, Nuitka **4.2.2**, including source metadata/digest checks. Focused legal/source/assembler/layout/provenance tests passed. Do not weaken legal verification or claim final legal package acceptance before Phase C/D. Expected set remains six ZIPs + one consolidated third-party `tar.xz` + one SHA256SUMS file.

## Security, announcements and explicit watches

Checked fresh exact-version PyPI advisories with [OSV batch API](https://google.github.io/osv.dev/api/#tag/v1/operation/OSV_QueryBatch): **37 queries, zero nonempty results**. This includes selected runtime/dev/build tools and inspected patchelf. Azure/login's five non-development npm lock dependencies were also queried at their exact resolved versions: **5 queries, zero nonempty results**. These are dated database observations, not proof of absence of vulnerabilities. Parent security sources were checked separately.

Qt [CVE-2026-76151](https://www.qt.io/blog/security-advisory-cve-2026-76151), [CVE-2026-19248](https://www.qt.io/blog/security-advisory-cve-2026-19248), [CVE-2026-78253](https://www.qt.io/blog/security-advisory-cve-2026-78253), [CVE-2026-79616](https://www.qt.io/blog/security-advisory-cve-2026-79616) are fixed by selected 6.11.2; the Qt Quick case is outside this Qt Widgets application. [OpenSSL advisories](https://openssl-library.org/news/vulnerabilities/), cryptography/lxml release notes and Ubuntu USN evidence were evaluated at their actual parent/vendor boundaries. No actionable unresolved finding was identified in checked sources; reopen on new facts.

Fresh [runner announcements](https://github.com/actions/runner-images/issues?q=is%3Aissue+is%3Aopen+label%3AAnnouncement) were read, including bodies:

- [#14748](https://github.com/actions/runner-images/issues/14748): ubuntu-latest 26.04 rollout October 19 to November 19; **future migration watch**, release builders explicitly 24.04.
- [#14747](https://github.com/actions/runner-images/issues/14747): Ubuntu 26.04 GA; does not authorize implicit package floor changes. Supported 24.04 retains current intended matrix/floors.
- [#14254](https://github.com/actions/runner-images/issues/14254): hosted Ubuntu 22.04 deprecated September 17, unsupported April 17, 2027. Required hosted builders already migrated to 24.04; supported intentional 22.04 containers remain.
- [#14602](https://github.com/actions/runner-images/issues/14602), [#14592](https://github.com/actions/runner-images/issues/14592): supported Windows/ARM64 VS2026 paths are already selected; no migration remains.
- [#14404](https://github.com/actions/runner-images/issues/14404): Xcode 27 preview, Apple Silicon-only successor; **future watch**, retain common supported 26.6.
- [#13518](https://github.com/actions/runner-images/issues/13518): macOS 14 retirement November 2; unselected (release 26, audit 15), **non-actionable observation**.
- #14826 Android CMake, #14818 MySQL and #14745 Android NDK concern unused paths; **non-actionable observations**. #14835 is a placeholder without concrete supported change/date; no invented migration or blocker.

No newly announced applicable deprecation demands a Phase B code migration. Future watches: public matched Qt bindings, OpenSSL 3.6 support deadline, compatible Intel/ARM64 Xcode successor, runner label changes and current vendor signing parents/internals. Repeat the full audit at final freshness and record actual native embedded versions during builds.

## Validation and limits

Focused release gate: **81 passed**, including exact runtime rejection checks and historical v2.2 preservation. Focused Help/workflow/Tracks A/B/C: **117 passed**. Full local source gate: **1781 passed, 9 skipped**, full Ruff, compilation, PowerShell parser and standard Qt offscreen smoke passed; [release preparation](V2_3_RELEASE_PREP.md) records the validation boundary. Fresh install and dependency integrity pass; no outdated selected Python distributions. Final exact-head remote Quality, native packages, production trust and publication remain pending. No final platform builds were dispatched.

The following generated inventory/source ledger records the queried versions and primary sources for every freshness decision; it is durable evidence, not an additional version configuration system.


## Per-distribution clean inventory

All 36 installed distributions are stable/non-yanked. Direct pins and independent resolver components are category A; matched Qt wheels retain their category B parent boundary. Pure Python and unchanged native parent selections retain the approved six-target integration; candidate-native validation remains pending, as explained above.

| Component | Ownership | Fresh selected | Latest stable | Decision and primary metadata |
| --- | --- | --- | --- | --- |
| asn1crypto | A resolved transitive | 1.5.1 | 1.5.1 | Current/no action; [PyPI](https://pypi.org/pypi/asn1crypto/json) |
| ast_serialize | A resolved transitive | 0.12.1 | 0.12.1 | Updated clean resolution; compatible six-target wheels; [PyPI](https://pypi.org/pypi/ast_serialize/json) |
| beautifulsoup4 | A direct/build | 4.15.0 | 4.15.0 | Current/no action; [PyPI](https://pypi.org/pypi/beautifulsoup4/json) |
| certifi | A resolved transitive | 2026.7.22 | 2026.7.22 | Current/no action; [PyPI](https://pypi.org/pypi/certifi/json) |
| cffi | A resolved transitive | 2.1.1 | 2.1.1 | Current/no action; [PyPI](https://pypi.org/pypi/cffi/json) |
| charset-normalizer | A resolved transitive | 3.5.2 | 3.5.2 | Current/no action; [PyPI](https://pypi.org/pypi/charset-normalizer/json) |
| click | A resolved transitive | 8.5.0 | 8.5.0 | Current/no action; [PyPI](https://pypi.org/pypi/click/json) |
| colorama | A resolved transitive | 0.4.6 | 0.4.6 | Current/no action; [PyPI](https://pypi.org/pypi/colorama/json) |
| cryptography | A direct/build | 50.0.2 | 50.0.2 | Current/no action; [PyPI](https://pypi.org/pypi/cryptography/json) |
| google-play-scraper | A direct/build | 1.2.7 | 1.2.7 | Current/no action; [PyPI](https://pypi.org/pypi/google-play-scraper/json) |
| idna | A resolved transitive | 3.20 | 3.20 | Current/no action; [PyPI](https://pypi.org/pypi/idna/json) |
| iniconfig | A resolved transitive | 2.3.0 | 2.3.0 | Current/no action; [PyPI](https://pypi.org/pypi/iniconfig/json) |
| librt | A resolved transitive | 0.16.0 | 0.16.0 | Current/no action; [PyPI](https://pypi.org/pypi/librt/json) |
| lxml | A resolved transitive | 6.1.3 | 6.1.3 | Current/no action; [PyPI](https://pypi.org/pypi/lxml/json) |
| mypy | A direct/build | 2.4.0 | 2.4.0 | Current/no action; [PyPI](https://pypi.org/pypi/mypy/json) |
| mypy_extensions | A resolved transitive | 1.1.0 | 1.1.0 | Current/no action; [PyPI](https://pypi.org/pypi/mypy_extensions/json) |
| Nuitka | A direct/build | 4.2.2 | 4.2.2 | Current/no action; [PyPI](https://pypi.org/pypi/Nuitka/json) |
| packaging | A resolved transitive | 26.3 | 26.3 | Current/no action; [PyPI](https://pypi.org/pypi/packaging/json) |
| pathspec | A resolved transitive | 1.1.1 | 1.1.1 | Current/no action; [PyPI](https://pypi.org/pypi/pathspec/json) |
| pillow | A direct/build | 12.3.0 | 12.3.0 | Current/no action; [PyPI](https://pypi.org/pypi/pillow/json) |
| pip | A direct/build | 26.2.1 | 26.2.1 | Current/no action; [PyPI](https://pypi.org/pypi/pip/json) |
| pluggy | A resolved transitive | 1.6.0 | 1.6.0 | Current/no action; [PyPI](https://pypi.org/pypi/pluggy/json) |
| pyaxmlparser | A direct/build | 0.3.31 | 0.3.31 | Current/no action; [PyPI](https://pypi.org/pypi/pyaxmlparser/json) |
| pycparser | A resolved transitive | 3.0 | 3.0 | Current/no action; [PyPI](https://pypi.org/pypi/pycparser/json) |
| Pygments | A resolved transitive | 2.21.0 | 2.21.0 | Current/no action; [PyPI](https://pypi.org/pypi/Pygments/json) |
| PySide6_Essentials | B matched Qt parent | 6.11.2 | 6.11.2 | Current/no action; matched parent; [PyPI](https://pypi.org/pypi/PySide6_Essentials/json) |
| pytest | A direct/build | 9.1.1 | 9.1.1 | Current/no action; [PyPI](https://pypi.org/pypi/pytest/json) |
| requests | A direct/build | 2.34.2 | 2.34.2 | Current/no action; [PyPI](https://pypi.org/pypi/requests/json) |
| ruff | A direct/build | 0.16.10 | 0.16.10 | Current/no action; [PyPI](https://pypi.org/pypi/ruff/json) |
| setuptools | A direct/build | 84.0.0 | 84.0.0 | Current/no action; [PyPI](https://pypi.org/pypi/setuptools/json) |
| shiboken6 | B matched Qt parent | 6.11.2 | 6.11.2 | Current/no action; matched parent; [PyPI](https://pypi.org/pypi/shiboken6/json) |
| soupsieve | A resolved transitive | 2.10 | 2.10 | Current/no action; [PyPI](https://pypi.org/pypi/soupsieve/json) |
| typing_extensions | A resolved transitive | 4.16.0 | 4.16.0 | Current/no action; [PyPI](https://pypi.org/pypi/typing_extensions/json) |
| urllib3 | A resolved transitive | 2.8.0 | 2.8.0 | Current/no action; [PyPI](https://pypi.org/pypi/urllib3/json) |
| websocket-client | A direct/build | 1.9.2 | 1.9.2 | Current/no action; [PyPI](https://pypi.org/pypi/websocket-client/json) |
| wheel | A direct/build | 0.48.0 | 0.48.0 | Current/no action; [PyPI](https://pypi.org/pypi/wheel/json) |

Additional independently inspected packages, not installed overrides: [SCons 4.11.1](https://pypi.org/pypi/SCons/json), [patchelf 0.19.1.0](https://pypi.org/pypi/patchelf/json). The supported selected integrations are described above.

## Fresh primary-source ledger

These sources were fetched afresh (HTTP 200), not inferred from the old release record. Releases/manifests/inventories must be queried again at the final gate.

- [python-downloads](https://www.python.org/downloads/)
- [python-release](https://www.python.org/downloads/release/python-3148/)
- [python-lifecycle](https://devguide.python.org/versions/)
- [python-changelog](https://docs.python.org/release/3.14.8/whatsnew/changelog.html)
- [qt-index](https://download.qt.io/official_releases/QtForPython/pyside6/)
- [qt612](https://download.qt.io/official_releases/qt/6.12/6.12.0/)
- [qt-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)
- [openssl-support](https://openssl-library.org/policies/releasestrat/)
- [openssl-advisories](https://openssl-library.org/news/vulnerabilities/)
- [cryptography-changelog](https://cryptography.io/en/latest/changelog/)
- [lxml-changelog](https://raw.githubusercontent.com/lxml/lxml/lxml-6.1.3/CHANGES.txt)
- [nuitka-scons](https://raw.githubusercontent.com/Nuitka/Nuitka/4.2.2/nuitka/build/SconsInterface.py)
- [rust-stable](https://static.rust-lang.org/dist/channel-rust-stable.toml)
- [rustup-stable](https://static.rust-lang.org/rustup/release-stable.toml)
- [rust-macos-targets](https://doc.rust-lang.org/rustc/platform-support/apple-darwin.html)
- [rustup-intel-sha](https://static.rust-lang.org/rustup/archive/1.29.1/x86_64-apple-darwin/rustup-init.sha256)
- [vcpkg-port-current](https://raw.githubusercontent.com/microsoft/vcpkg/master/ports/openssl/vcpkg.json)
- [vcpkg-port-selected](https://raw.githubusercontent.com/microsoft/vcpkg/eb2d3a3279fd019cb7733072d86900d0ad2a1aef/ports/openssl/vcpkg.json)
- [runner-labels](https://raw.githubusercontent.com/actions/runner-images/main/README.md)
- [windows-x64-image](https://raw.githubusercontent.com/actions/runner-images/main/images/windows/Windows2025-VS2026-Readme.md)
- [windows-arm-image](https://raw.githubusercontent.com/actions/runner-images/main/images/windows/Windows11-VS2026-Arm64-Readme.md)
- [linux-x64-image](https://raw.githubusercontent.com/actions/runner-images/main/images/ubuntu/Ubuntu2404-Readme.md)
- [linux-arm-image](https://raw.githubusercontent.com/actions/runner-images/main/images/ubuntu/Ubuntu2404-Arm64-Readme.md)
- [macos-intel-image](https://raw.githubusercontent.com/actions/runner-images/main/images/macos/macos-26-Readme.md)
- [macos-arm-image](https://raw.githubusercontent.com/actions/runner-images/main/images/macos/macos-26-arm64-Readme.md)
- [apple-xcode-requirements](https://developer.apple.com/xcode/system-requirements/)
- [apple-notary-migration](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool)
- [ubuntu-lifecycle](https://ubuntu.com/about/release-cycle)
- [ubuntu-usn](https://ubuntu.com/security/notices/USN-8847-1)
- [ubuntu-jammy-openssl](https://launchpad.net/ubuntu/jammy/+source/openssl)
- [ubuntu-noble-openssl](https://launchpad.net/ubuntu/noble/+source/openssl)
- [ubuntu-adb](https://packages.ubuntu.com/noble/adb)
- [android-platform-tools](https://developer.android.com/tools/releases/platform-tools)
- [github-api-versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
- [github-artifacts-api](https://docs.github.com/en/rest/actions/artifacts)
- [azure-signing-integration](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations)
- [azure-signing-module](https://www.powershellgallery.com/packages/ArtifactSigning)
- [nuget-sdk](https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/index.json)
- [nuget-client](https://api.nuget.org/v3-flatcontainer/microsoft.artifactsigning.client/index.json)
- [nuget-sign](https://api.nuget.org/v3-flatcontainer/sign/index.json)
- [npm-core](https://registry.npmjs.org/@actions/core/latest)
- [npm-exec](https://registry.npmjs.org/@actions/exec/latest)
- [npm-io](https://registry.npmjs.org/@actions/io/latest)
- [actions-checkout-latest](https://api.github.com/repos/actions/checkout/releases/latest)
- [actions-checkout-source](https://raw.githubusercontent.com/actions/checkout/v7/action.yml)
- [actions-setup-python-latest](https://api.github.com/repos/actions/setup-python/releases/latest)
- [actions-setup-python-source](https://raw.githubusercontent.com/actions/setup-python/v7/action.yml)
- [actions-upload-artifact-latest](https://api.github.com/repos/actions/upload-artifact/releases/latest)
- [actions-upload-artifact-source](https://raw.githubusercontent.com/actions/upload-artifact/v7/action.yml)
- [actions-download-artifact-latest](https://api.github.com/repos/actions/download-artifact/releases/latest)
- [actions-download-artifact-source](https://raw.githubusercontent.com/actions/download-artifact/v8/action.yml)
- [Azure-login-latest](https://api.github.com/repos/Azure/login/releases/latest)
- [Azure-login-source](https://raw.githubusercontent.com/Azure/login/v3/action.yml)
- [Azure-artifact-signing-action-latest](https://api.github.com/repos/Azure/artifact-signing-action/releases/latest)
- [Azure-artifact-signing-action-source](https://raw.githubusercontent.com/Azure/artifact-signing-action/v2/action.yml)
- [azure-login-lock](https://raw.githubusercontent.com/Azure/login/v3/package-lock.json)
- [vcpkg-tool-latest](https://api.github.com/repos/microsoft/vcpkg-tool/releases/latest)
