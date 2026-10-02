# v2.2.0 final pre-release component freshness gate

> **Historical preparation/freshness evidence, superseded by published v2.2.0.** PR #220 is merged. The release was published on 2026-10-02 at `21b6646571b7e93044b76fe4d18a04eeec092f18` with exact Python 3.14.8. Statements below about pending freeze/publication or open PRs describe the gate-time checkpoint, not current state. Development restores rolling stable 3.14 through the closure PR. See [Project Status](PROJECT_STATUS.md), [published release notes](RELEASE_NOTES.md#published-v220-release-body) and [closure audit](V2_2_POST_RELEASE_CLOSURE.md).

Audit started **2026-10-02 CEST**, from exact main
`486ef062548cab2dee5960c38f02dbfbca226640` (PR #219 merge).
Before editing, the clean local checkout was synchronized by fast-forward;
local main, origin/main and live remote main all matched that SHA.
Starting Quality #628 / [36938816496](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36938816496)
was independently confirmed successful at that exact SHA. Work uses the new
`v2/final-freshness-2.2.0` branch, not the stale prep branch.

**Gate status: PASSED.** Complete upstream, source and affected native validation
is recorded below. Final documentation-head Quality's exact SHA/run/result is
recorded in [draft PR #220](https://github.com/mrc-labs/PlayStoreAppAudit/pull/220)
after this commit; handoff requires its success. The PR remains open/unmerged,
without auto-merge, for control-tower review and a normal merge commit.
No release source SHA is frozen. Diagnostic packages cannot become final candidates.
The entry and preparation records remain historical evidence and are not substituted
for this new upstream audit. Issue #212 remains open; #147/#154/#209 are outside scope.

## Exact Python selection and checks

Python.org and the live official setup-python manifest independently select
**3.14.8**, the latest stable compatible 3.14 patch. Python 3.15 is still listed
as pre-release; no baseline migration is authorized. The 3.14.8 manifest has
standard Windows x64/ARM64, macOS x64/ARM64 and Ubuntu 24.04 x64/ARM64 builds,
plus the required same-patch Ubuntu 22.04 x64 archive. The compatibility helper
re-downloaded that official archive and checked release asset digest/size:
`python-3.14.8-linux-22.04-x64.tar.gz`, SHA-256
`3b6ca0860f3e23ca51901c78b7c945253ef35b9938dbc6529a5fea2183342363`.
Sources: [Python downloads](https://www.python.org/downloads/),
[3.14.8 release](https://www.python.org/downloads/release/python-3148/),
[manifest](https://github.com/actions/python-versions/blob/main/versions-manifest.json),
[official build](https://github.com/actions/python-versions/releases/tag/3.14.8-36806082737).

All **11 setup environments across nine workflows** now use full literals
(Quality's literal matrix entry is `3.14.8`). Every setup step is followed,
before its first Python consumer, by `platform.python_version()` equality to
`3.14.8`; PowerShell explicitly throws on nonzero exit and Bash uses
`set -euo pipefail`. Rolling `check-latest` was removed. Existing duplicated
build/Quality assertions were updated to full equality too.

| Location | Pinned environments / checks |
| --- | --- |
| `.github/workflows/quality.yml` | Literal matrix entry, immediate patch check and post-install Python/Qt check |
| `.github/workflows/build-windows-exe.yml` | Native x64/ARM64, immediate check, standard-GIL/architecture and post-install Python/Qt checks |
| `.github/workflows/build-linux.yml` | Both native 24.04 targets, immediate/pre-provisioning and post-install checks |
| `.github/workflows/build-macos.yml` | Both native macOS 26 targets, immediate and post-install checks |
| `.github/workflows/sign-windows.yml` | Ubuntu preflight, Windows signing environment and native verification environment (three setup steps); production signing is not dispatched |
| `.github/workflows/assemble-release.yml` | Production assembler environment; not dispatched |
| `.github/workflows/assemble-windows-engineering-release.yml` | Historical-profile engineering assembler environment; not dispatched |
| `.github/workflows/actions-retention.yml` | Maintenance environment, aligned for the release window |
| `.github/workflows/ui-style-audit.yml` | Manual audit environment, aligned for the release window |
| `.github/scripts/build_windows_standalone.ps1` | Full patch equality and existing 64-bit check |
| `.github/scripts/prepare_linux_x64_sysroot.sh` | Require resolved patch 3.14.8 before download, then verify the installed compatibility distribution equals it |

The generic official-distribution selector continues to accept a stable full
3.14 patch, but the release caller requires 3.14.8 and rejects another patch.
The controlled local assembly environment must also use and assert 3.14.8.
Regression coverage exercises the guard with 3.14.8, 3.14.7 and 3.14.9,
requiring success only for the selected patch, and inventories every setup step.

This is the deliberately small YAML-literal mechanism required by policy.
After v2.2 permanent closure, a focused development change must restore rolling
`3.14`/`check-latest: true` and the corresponding development assertions/tests
in these nine workflows and the two native helpers. Preserve the immutable
release source and this record. `requires-python >=3.14`, mypy's minor-language
target and the developer launcher stay language/development settings; they are
not final release runtime selectors. No new toolchain configuration system exists.

## Component inventory and ownership

The complete clean Python package inventory and OS/vendor/deprecation inventory
are recorded below. Categories A/B/C/D follow
[RELEASE_COMPONENT_FRESHNESS.md](RELEASE_COMPONENT_FRESHNESS.md) exactly.
Freshness does not assert that a component is free of vulnerabilities.

Required controlled updates identified by fresh queries:

- Ruff **0.16.9 → 0.16.10** and mypy **2.3.1 → 2.4.0**, in `requirements-dev.txt`.
- Rust **1.98.1 → 1.99.0**, paired Cargo, in macOS Intel and Windows ARM64
  source-built cryptography paths. rustup 1.29.1 and OpenSSL selections remain current.
  Native Rust target and actual version checks are required; Intel's verified
  official rustup installer and deployment target are retained.
- Linux Noble OpenSSL runner inventory **3.0.13-0ubuntu3.15 → at least
  3.0.13-0ubuntu3.16**, by explicitly installing current `libssl3t64`/`openssl`
  vendor packages before dependency/package work and rejecting a version below
  the security floor. The Jammy sysroot rejects `libssl3` below
  **3.0.2-0ubuntu1.30**. These are security floors, not stale apt revision pins:
  apt still resolves the current supported vendor packages. Required fixes and
  applicability come from [USN-8847-1](https://ubuntu.com/security/notices/USN-8847-1).
  First Linux final-gate diagnostic #14 / `36947359456` at `41a1b594...` was
  deliberately cancelled when this required update was discovered; it is not
  acceptance evidence. Repeat both architectures from the corrected checkpoint.
  Corrected Linux #15 / `36947574138` at `0b70546c...` installed the required
  Noble `.16` packages and passed the Jammy sysroot security floor, but the
  new host `openssl version` inspection selected Jammy libraries through the
  intentional compatibility `LD_LIBRARY_PATH` and failed for missing
  `OPENSSL_3.0.9`. The inspection now explicitly removes that variable for
  this host-tool command only; compatibility Python and the package retain
  their intended target libraries. No update, security or package check is
  suppressed. The superseded run is cancelled and both architectures repeated.

Stable Rust retains the required native targets and deployment compatibility:
[stable channel manifest](https://static.rust-lang.org/dist/channel-rust-stable.toml),
[macOS target support](https://doc.rust-lang.org/rustc/platform-support/apple-darwin.html),
[target matrix](https://doc.rust-lang.org/rustc/platform-support.html).
The macOS x86 target is tier 2; the required package diagnostic must validate it.

### Clean Python environment (new final-gate resolution)

Upstream snapshots queried **2026-10-02T00:30:01.121363+00:00**; all metadata queries were
repeated for this gate. A new venv was created with the official locally isolated
CPython 3.14.8; no global installation was changed. Canonical requirements-dev
(including runtime), Nuitka 4.2.2, setuptools 84.0.0, wheel 0.48.0 and current
pip were installed. Stable/non-yanked release metadata was independently compared
for all **36 installed distributions**. Final `pip check` exit 0, no broken
requirements; `pip list --outdated --format=json` exit 0, stdout exactly **`[]`**,
stderr empty. The first clean resolution found Ruff/mypy outdated; both were
updated and the complete check repeated. No package was silently excluded.
`lxml` is pyaxmlparser's transitive dependency, not the Store HTTP parser.

| Component | Previous → selected | Latest stable | Category | Action / validation | Authoritative source |
| --- | --- | --- | --- | --- | --- |
| CPython | Rolling 3.14 → exact 3.14.8 | 3.14.8 in supported baseline | A | Full-patch pins/checks; manifest six-target coverage and verified same-patch Jammy archive; actual local/native versions recorded below | [Python](https://www.python.org/downloads/release/python-3148/), [manifest](https://github.com/actions/python-versions/blob/main/versions-manifest.json) |
| asn1crypto | resolver-selected → 1.5.1 | 1.5.1 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/asn1crypto/json) |
| ast_serialize | resolver-selected → 0.11.2 | 0.11.2 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/ast_serialize/json) |
| beautifulsoup4 | 4.15.0 → 4.15.0 | 4.15.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/beautifulsoup4/json) |
| certifi | resolver-selected → 2026.7.22 | 2026.7.22 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/certifi/json) |
| cffi | resolver-selected → 2.1.1 | 2.1.1 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/cffi/json) |
| charset-normalizer | resolver-selected → 3.5.2 | 3.5.2 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/charset-normalizer/json) |
| click | resolver-selected → 8.5.0 | 8.5.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/click/json) |
| colorama | resolver-selected → 0.4.6 | 0.4.6 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/colorama/json) |
| cryptography | 50.0.2 → 50.0.2 | 50.0.2 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/cryptography/json) |
| google-play-scraper | 1.2.7 → 1.2.7 | 1.2.7 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/google-play-scraper/json) |
| idna | resolver-selected → 3.20 | 3.20 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/idna/json) |
| iniconfig | resolver-selected → 2.3.0 | 2.3.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/iniconfig/json) |
| librt | resolver-selected → 0.16.0 | 0.16.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/librt/json) |
| lxml | resolver-selected → 6.1.3 | 6.1.3 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/lxml/json) |
| mypy | 2.3.1 → 2.4.0 | 2.4.0 | A | Updated; full source Quality/native dependency install | [PyPI](https://pypi.org/pypi/mypy/json) |
| mypy_extensions | resolver-selected → 1.1.0 | 1.1.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/mypy_extensions/json) |
| Nuitka | 4.2.2 → 4.2.2 | 4.2.2 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/Nuitka/json) |
| packaging | resolver-selected → 26.3 | 26.3 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/packaging/json) |
| pathspec | resolver-selected → 1.1.1 | 1.1.1 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/pathspec/json) |
| pillow | 12.3.0 → 12.3.0 | 12.3.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/pillow/json) |
| pip | 26.2.1 → 26.2.1 | 26.2.1 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/pip/json) |
| pluggy | resolver-selected → 1.6.0 | 1.6.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/pluggy/json) |
| pyaxmlparser | 0.3.31 → 0.3.31 | 0.3.31 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/pyaxmlparser/json) |
| pycparser | resolver-selected → 3.0 | 3.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/pycparser/json) |
| Pygments | resolver-selected → 2.21.0 | 2.21.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/Pygments/json) |
| PySide6_Essentials | 6.11.2 → 6.11.2 | 6.11.2 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/PySide6_Essentials/json) |
| pytest | 9.1.1 → 9.1.1 | 9.1.1 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/pytest/json) |
| requests | 2.34.2 → 2.34.2 | 2.34.2 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/requests/json) |
| ruff | 0.16.9 → 0.16.10 | 0.16.10 | A | Updated; full source Quality/native dependency install | [PyPI](https://pypi.org/pypi/ruff/json) |
| setuptools | 84.0.0 → 84.0.0 | 84.0.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/setuptools/json) |
| shiboken6 | resolver-selected → 6.11.2 | 6.11.2 | B (matched parent) | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/shiboken6/json) |
| soupsieve | resolver-selected → 2.10 | 2.10 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/soupsieve/json) |
| typing_extensions | resolver-selected → 4.16.0 | 4.16.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/typing_extensions/json) |
| urllib3 | resolver-selected → 2.8.0 | 2.8.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/urllib3/json) |
| websocket-client | 1.9.2 → 1.9.2 | 1.9.2 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/websocket-client/json) |
| wheel | 0.48.0 → 0.48.0 | 0.48.0 | A | Current; clean resolution, stable metadata and pip check | [PyPI](https://pypi.org/pypi/wheel/json) |

No additional maintained direct Python dependency appears in pyproject/runtime/dev
or workflow build installs. `build` is not used and is not added. The existing
developer Python launcher/language metadata is not a frozen release selector.

### Bundle and native-toolchain boundaries

| Component / control boundary | Previous / selected | Latest stable / compatible boundary | Category | Support/security/action and validation | Authoritative source |
| --- | --- | --- | --- | --- | --- |
| Qt supplied by PySide / pyside6-deploy | 6.11.2, unchanged matched PySide/Shiboken | Public bindings remain 6.11.2; independent Qt 6.12.0 exists | B | Supported matched parent retained, no Qt swap. QtNetwork/XML advisories fixed by 6.11.2; native GUI/legal/ABI checks remain mandatory. Watch next public matched bindings | [PySide metadata](https://pypi.org/pypi/PySide6-Essentials/json), [binding index](https://download.qt.io/official_releases/QtForPython/pyside6/), [Qt 6.12](https://download.qt.io/official_releases/qt/6.12/6.12.0/), [deployment](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) |
| Official CPython bundled OpenSSL | Actual local 3.5.9 | Supported 3.14.8 parent; maintained 3.5.9 LTS patch | B | September advisories fixed by selected patch; independent 4.0.3 does not require binary substitution. Native provenance records platform-specific actual integrations | [Python bundle](https://www.python.org/downloads/release/python-3148/), [OpenSSL advisories](https://openssl-library.org/news/vulnerabilities-3.5/), [support](https://openssl-library.org/policies/releasestrat/) |
| CPython embedded Expat/zlib/SQLite | Local expat 2.8.5; zlib 1.3.1.zlib-ng; SQLite 3.50.4 | Current official CPython parent distribution | B | Record embedded versions; no independent binary substitution. Evaluate parent advisories rather than version arithmetic; no applicable required action identified in checked sources | [CPython changelog](https://docs.python.org/release/3.14.8/whatsnew/changelog.html), [CPython bundle](https://www.python.org/downloads/release/python-3148/) |
| lxml embedded libxml2/libxslt | Windows actual 2.11.9 / 1.1.45 | Latest supported lxml 6.1.3 parent; platform wheels differ | B | Upstream explicitly maintains security-patched Windows libxml2. Selected lxml fixes external parameter entity parsing; current wheel's libxslt includes security fixes. Retain vendor parent/legal evidence; no independent swap | [exact parent changelog](https://github.com/lxml/lxml/blob/lxml-6.1.3/CHANGES.txt), [PyPI](https://pypi.org/pypi/lxml/json) |
| cryptography embedded OpenSSL wheel | 50.0.2 / local OpenSSL 4.0.3 | Current parent / current embedded security patch | B | Supported native wheels retained where available; separately controlled source integrations below remain A. September 4.0 advisories fixed | [cryptography changelog](https://cryptography.io/en/latest/changelog/), [OpenSSL advisories](https://openssl-library.org/news/vulnerabilities/) |
| Pillow embedded development codecs | Pillow 12.3.0: FreeType 2.14.3, LittleCMS 2.19, WebP 1.6.0, AVIF 1.4.2, libjpeg-turbo 3.1.4.1, JPEG2000 2.5.4, TIFF 4.7.1, zlib-ng 2.3.3 | Current supported Pillow parent | B | Developer/test imaging tool; no new runtime dependency. Parent current and OSV version query empty; no codec swap | [Pillow releases](https://pillow.readthedocs.io/en/stable/releasenotes/), [PyPI](https://pypi.org/pypi/Pillow/json) |
| Nuitka supplied SCons/deployment inspection | Parent selector: Windows Python 3.14 uses SCons 4.10.1; Unix uses supplied 3.1.2; Windows legacy fallback 4.3.0 | Nuitka 4.2.2 current stable supported parent; independent SCons 4.11.1 | B | Actual installed parent selector inspected; the independent version is an upstream observation, with no repository SCons override. Native builds exercise the supplied compiler/inspection helpers and preserve compilation evidence | [Nuitka](https://nuitka.net/changelog/Changelog.html), [parent selector](https://github.com/Nuitka/Nuitka/blob/4.2.2/nuitka/build/SconsInterface.py), [SCons metadata](https://pypi.org/pypi/SCons/json) |
| Linux deployment patchelf | Deployment resolver 0.19.1.0 / upstream executable 0.19.1; Noble normalization helper 0.18.0-1.1build1 | PyPI 0.19.1.0 current; supported Noble vendor package current | A deployment / D normalization | Independent metadata re-query at 2026-10-02T01:21:38+00:00; both native deployments resolved 0.19.1.0. No update required; vendor helper and deployment patching exercised before GUI/CLI/legal/roundtrip acceptance | [PyPI](https://pypi.org/pypi/patchelf/json), [upstream release](https://github.com/NixOS/patchelf/releases/tag/0.19.1), [Noble package](https://packages.ubuntu.com/noble/patchelf) |
| Rust / Cargo for Windows ARM64 and macOS Intel source builds | Rust 1.98.1 → 1.99.0; paired Cargo | Stable 1.99.0, channel date 2026-10-01 | A | Required update applied in both source paths; native version/architecture and package/legal verification required. Intel tier 2 remains distributed, minimum target compatible | [stable manifest](https://static.rust-lang.org/dist/channel-rust-stable.toml), [targets](https://doc.rust-lang.org/rustc/platform-support.html), [macOS](https://doc.rust-lang.org/rustc/platform-support/apple-darwin.html) |
| rustup Intel official installer / Windows runner tool | 1.29.1, unchanged | 1.29.1 | A / D | Intel installer SHA-256 still verified; no Homebrew Intel source-build detour. Windows runtime selects audited Rust explicitly | [stable manifest](https://static.rust-lang.org/rustup/release-stable.toml), [Intel installer checksum](https://static.rust-lang.org/rustup/archive/1.29.1/x86_64-apple-darwin/rustup-init.sha256) |
| Windows ARM64 Vcpkg registry/tool/OpenSSL source path | Audited registry eb2d3a3279fd019cb7733072d86900d0ad2a1aef; tool 2026-09-26; OpenSSL 3.6.5 | Tool 2026-09-26; current supported official port 3.6.5 | A within supported vendor port | Selected tool metadata/current port independently rechecked. Static native ARM64 source build, PE and backend-version checks retained. OpenSSL 3.6 EOL 2026-11-01 is a required reopen point if release slips; no supported newer official port exists in current registry | [registry port](https://github.com/microsoft/vcpkg/blob/eb2d3a3279fd019cb7733072d86900d0ad2a1aef/ports/openssl/vcpkg.json), [current port](https://github.com/microsoft/vcpkg/blob/master/ports/openssl/vcpkg.json), [tool](https://github.com/microsoft/vcpkg-tool/releases/tag/2026-09-26), [support](https://openssl-library.org/policies/releasestrat/) |
| macOS Intel static OpenSSL source path | 4.0.3, unchanged | 4.0.3 | A | Verified official archive SHA-256 and deployment target retained; supported to 2027-05-14. cryptography backend/extension architecture validated after Rust update | [official release](https://github.com/openssl/openssl/releases/tag/openssl-4.0.3), [support](https://openssl-library.org/policies/releasestrat/) |
| Windows x64 / ARM64 hosts and MSVC | windows-2025 / windows-11-arm | Supported GA hosts; VS 2026 migrations cover selected labels | D | Current inventory VS 18.10.12210.168; MSVC actual compiler/package evidence required. No label rollback; SDK/CMake/Perl/NASM supplied by supported image/vendor Vcpkg build. Newer unrelated tools are not independent shipping requirements | [runner labels](https://github.com/actions/runner-images/blob/main/README.md), [x64 inventory](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-VS2026-Readme.md), [ARM64 inventory](https://github.com/actions/runner-images/blob/main/images/windows/Windows11-VS2026-Arm64-Readme.md), [VS servicing](https://learn.microsoft.com/en-us/visualstudio/productinfo/vs-servicing) |
| macOS ARM64 / Intel hosts, Xcode/Clang/SDK | macos-26 / macos-26-intel; Xcode 26.6 | Current common supported native matrix; Xcode 27 is Apple-silicon-only and hosted preview | D | Retain both architectures and deployment metadata; no preview/floor change. Current image revisions 20260907.0351.1 ARM64 (macOS 26.6.2) / 20260824.0517.1 Intel (macOS 26.6.1), selected Xcode build 17F113; native evidence records actual image/compiler | [Intel inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-Readme.md), [ARM64 inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md), [Apple requirements](https://developer.apple.com/xcode/system-requirements/), [Xcode 27](https://developer.apple.com/documentation/xcode-release-notes/xcode-27-release-notes) |
| Linux x64 / ARM64 build hosts and compiler | ubuntu-24.04 / ubuntu-24.04-arm | Current supported 24.04 LTS matrix; GA 26.04 would change OS/compiler/library floor | D | Retain deliberate supported target floor; no deprecated hosted Ubuntu 22 runner. Latest selected-distro apt prerequisites, GCC/binutils/patchelf/ZIP/Xvfb/display libraries; actual compiler/ELF/native smoke evidence required | [runner labels](https://github.com/actions/runner-images/blob/main/README.md), [x64 inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md), [ARM64 inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Arm64-Readme.md), [Ubuntu lifecycle](https://ubuntu.com/about/release-cycle) |
| Linux x64 compatibility Python/sysroot/runtime | Official same-patch Python 3.14.8 / current Jammy target packages, native 24.04 compiler | Current supported Jammy vendor integration, standard maintenance to May 2027 | A Python / D OS | Official archive hash/size verified; no downgrade/custom distro. No target libc shipped; all-ELF needs + actual 22.04 offscreen/xcb/CLI acceptance required. Native compiler probe preserved | [official Python build](https://github.com/actions/python-versions/releases/tag/3.14.8-36806082737), [Ubuntu lifecycle](https://ubuntu.com/about/release-cycle), [GCC sysroot](https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html) |
| Linux vendor OpenSSL target/native integrations | Jammy 3.0.2-0ubuntu1.30; Noble runner .15 → current apt, security floor 3.0.13-0ubuntu3.16 | Current supported vendor patches; independent OpenSSL 3.0 upstream support ended | D | Noble explicitly refreshed; both vendor security floors fail closed. Source runtime/Qt crypto normalization/legal evidence retained. Ubuntu support to May 2027/May 2029, no claim of upstream 3.0 support | [USN-8847-1](https://ubuntu.com/security/notices/USN-8847-1), [Jammy](https://launchpad.net/ubuntu/jammy/+source/openssl), [Noble](https://launchpad.net/ubuntu/noble/+source/openssl) |
| Native Linux ARM64 ADB | Noble adb: actual 1.0.41 / 34.0.4-debian in Linux #16; managed Google archive is not ARM64 | Supported selected-distro integration | D | Native distro executable/architecture/version check passed; no phone mutations or unsupported x64 download substituted | [Ubuntu adb](https://packages.ubuntu.com/noble/adb), [official endpoints](https://developer.android.com/tools/releases/platform-tools) |
| Native signing/notarization | Azure latest parent Actions; Apple codesign/security/notarytool/stapler/spctl | Supported providers and selected OS/Xcode tools | C / D | Correct signing-account-name input; current notarytool path replaces retired altool. Production credentials/trust unvalidated under #154 and not activated | [Microsoft integration](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations), [Apple TN3147](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool) |
| Legal/source, archives/checksums/provenance | Repository helpers + selected Python stdlib/shell + current vendor tools | Current supported parents, no third-party publisher Action | A repository contract / B/D runtime | Strict legal preflight and native post-build legal/source checks; exact SHA, version/architecture, runtime hashes, source checksums and ZIP roundtrip retained; release assemblers not dispatched | [BUILDING](BUILDING.md), [legal preflight](../.github/scripts/preflight_release_legal_material.py), [release assets](../.github/scripts/assemble_release_assets.py) |
| Manual UI audit / maintenance / assemblers | macos-15 / ubuntu-24.04 / windows-latest; Python 3.14.8 | Current supported labels; no selected-label retirement found | D / A Python | Full setup pins/guards applied even outside build jobs; no unrelated installed-image tool migration | [runner inventory](https://github.com/actions/runner-images/blob/main/README.md) |

### Direct Actions and vendor internals

Every maintained workflow was searched; there are exactly six directly used
external Action identities. All five JavaScript parents declare **node24**;
Azure signing is composite. Major references already select latest stable
patches, so no repository major change or setup-node dependency is needed.

| Action | Selected major / latest stable | Category | Action / evidence |
| --- | --- | --- | --- |
| actions/checkout | v7 / 7.0.1 | A | Current [release](https://github.com/actions/checkout/releases/tag/v7.0.1), [runtime](https://github.com/actions/checkout/blob/v7/action.yml) |
| actions/setup-python | v7 / 7.0.0 | A | Current [release](https://github.com/actions/setup-python/releases/tag/v7.0.0), [runtime](https://github.com/actions/setup-python/blob/v7/action.yml) |
| actions/upload-artifact | v7 / 7.0.1 | A | Current [release](https://github.com/actions/upload-artifact/releases/tag/v7.0.1), [runtime](https://github.com/actions/upload-artifact/blob/v7/action.yml) |
| actions/download-artifact | v8 / 8.0.1 | A | Current [release](https://github.com/actions/download-artifact/releases/tag/v8.0.1), [runtime](https://github.com/actions/download-artifact/blob/v8/action.yml) |
| Azure/login | v3 / 3.1.0 | A parent / C internals | Current [release](https://github.com/Azure/login/releases/tag/v3.1.0), [runtime](https://github.com/Azure/login/blob/v3/action.yml); not dispatched |
| Azure/artifact-signing-action | v2 / 2.0.0 | A parent / C internals | Current [release](https://github.com/Azure/artifact-signing-action/releases/tag/v2.0.0), [composite](https://github.com/Azure/artifact-signing-action/blob/v2/action.yml); not dispatched |

Rechecked non-overridable signing internals: ArtifactSigning module 0.1.8
versus current 0.1.20; SDK BuildTools 10.0.26100.4188 versus 10.0.28000.2705;
ArtifactSigning.Client 1.0.128 current; optional SignCLI beta declaration
0.9.1-beta.26227.3 versus stable 1.1.5; nested actions/cache v5.0.4 versus
v6.1.0. These remain **C observations**: latest supported parent has not
changed, no safe repository input override or applicable trust/support failure
was identified, and this gate does not fork vendor internals or activate signing.
Reopen for a newer supported parent, exposed safe override or actionable advisory.
Sources: [actual composite](https://github.com/Azure/artifact-signing-action/blob/v2/action.yml),
[module gallery](https://www.powershellgallery.com/packages/ArtifactSigning),
[SDK NuGet](https://www.nuget.org/packages/Microsoft.Windows.SDK.BuildTools),
[client NuGet](https://www.nuget.org/packages/Microsoft.ArtifactSigning.Client),
[SignCLI NuGet](https://www.nuget.org/packages/sign),
[cache parent](https://github.com/actions/cache/releases/tag/v6.1.0).

Azure/login v3.1.0's actual lockfile retains `@actions/core` 1.11.1,
`@actions/exec` 1.1.1 and `@actions/io` 1.1.2 versus current npm 3.0.1,
3.0.0 and 3.0.2. These are also **C observations**, not repository-selected
dependencies: no exposed override or newer stable parent exists. Its five
production npm lockfile entries were version-queried against OSV with no findings.
Sources: [actual vendor lockfile](https://github.com/Azure/login/blob/v3.1.0/package-lock.json),
[core registry](https://registry.npmjs.org/@actions/core),
[exec registry](https://registry.npmjs.org/@actions/exec),
[io registry](https://registry.npmjs.org/@actions/io). No vendor fork or production
login was performed.

### Android endpoints: new downloads

All three official latest endpoints returned valid ZIPs, safe member paths,
`platform-tools/source.properties` revision **37.0.1** and the expected
platform executable. Windows `adb version` exited normally, reporting
**1.0.41 / 37.0.1-15733141**. Linux/macOS archives were inspected without
executing foreign binaries. No phone operation was run.

| Platform | Current archive SHA-256 | Official endpoint |
| --- | --- | --- |
| windows | `45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99` | [latest archive](https://dl.google.com/android/repository/platform-tools-latest-windows.zip) |
| macos | `ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d` | [latest archive](https://dl.google.com/android/repository/platform-tools-latest-darwin.zip) |
| linux | `d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1` | [latest archive](https://dl.google.com/android/repository/platform-tools-latest-linux.zip) |

Direct managed tool is A, unchanged current 37.0.1; official
[release notes/endpoints](https://developer.android.com/tools/releases/platform-tools)
remain supported. Linux ARM64 retains the separate maintained vendor integration.

### Deprecation-forward and security/support disposition

| Finding | Classification / action | Authoritative evidence |
| --- | --- | --- |
| Ubuntu 22 hosted images: deprecation 2026-09-17; retirement 2027-04-17 | Required migration already implemented in prep: both build hosts 24.04. Jammy sysroot/container is a distinct supported distro integration; no deprecated hosted runner restored | [announcement #14254](https://github.com/actions/runner-images/issues/14254), [Ubuntu lifecycle](https://ubuntu.com/about/release-cycle) |
| ubuntu-latest migration 2026-10-19 through 2026-11-19 to GA 26.04 | Watch only: repository uses explicit 24.04 for Linux/assembly/maintenance; no implicit floor increase | [announcement #14748](https://github.com/actions/runner-images/issues/14748) |
| Windows latest/2025 → VS 2026 (June 2026); windows-11-arm → VS 2026 (September 2026) | Current migrated labels retained; actual runner/MSVC validation below. No retired VS-2022 image restoration | [#14017](https://github.com/actions/runner-images/issues/14017), [#14602](https://github.com/actions/runner-images/issues/14602), [GA #14592](https://github.com/actions/runner-images/issues/14592) |
| Xcode 27 | Upstream stable Apple release, but hosted xcode-27 still preview and Apple-silicon-only; incompatible with Intel matrix. Retain supported common Xcode 26.6, no preview adoption | [hosted preview #14404](https://github.com/actions/runner-images/issues/14404), [runner inventory](https://github.com/actions/runner-images/blob/main/README.md), [Apple release notes](https://developer.apple.com/documentation/xcode-release-notes/xcode-27-release-notes) |
| macOS 14 retirement / older simulator/Xcode removals | Outside selected macOS 26 release and macOS 15 manual audit; no affected selected-path retirement found | [retirement #13518](https://github.com/actions/runner-images/issues/13518), [selected images](https://github.com/actions/runner-images/blob/main/README.md) |
| Python lifecycle | 3.14 currently in bugfix phase, with security lifecycle ending October 2030; 3.15 remains prerelease; Python 3.10 EOL irrelevant to selected path. Full patch selected before release SHA freeze | [lifecycle](https://devguide.python.org/versions/), [downloads](https://www.python.org/downloads/) |
| PySide/Qt | Matched 6.11.2 current public stable bindings; Qt 6.12 pending matched bindings is a watch. Checked QtNetwork CVE-2026-76151 and XML CVE-2026-19248 are fixed at selected version | [network advisory](https://www.qt.io/blog/security-advisory-cve-2026-76151), [XML advisory](https://www.qt.io/blog/security-advisory-cve-2026-19248), [bindings](https://pypi.org/pypi/PySide6-Essentials/json) |
| Nuitka/pip/setuptools/wheel; Actions Node runtime | Current stable selected parents; no selected-path announced removal requiring a replacement found. Direct JavaScript Actions use Node24 | [Nuitka changes](https://nuitka.net/changelog/Changelog.html), [pip changes](https://pip.pypa.io/en/stable/news/), [setuptools changes](https://setuptools.pypa.io/en/latest/history.html), [wheel](https://pypi.org/pypi/wheel/json), Action sources above |
| OpenSSL September advisories | Python's 3.5.9, cryptography/Intel 4.0.3 and Vcpkg 3.6.5 contain upstream fixes. Ubuntu vendor Jammy .30/Noble .16 required; Noble provisioning updated and both floors fail closed. No generic security guarantee | [OpenSSL timeline/advisories](https://openssl-library.org/news/timeline/), [USN-8847-1](https://ubuntu.com/security/notices/USN-8847-1) |
| OpenSSL support boundaries | Upstream 3.0 EOL is not vendor Ubuntu EOL; maintained distro support remains. Windows port 3.6.5 support ends 2026-11-01: explicit future reopen deadline; latest supported official port is unchanged and independent private OpenSSL 4 port is not a supported vendor successor | [OpenSSL support](https://openssl-library.org/policies/releasestrat/), [Ubuntu lifecycle](https://ubuntu.com/about/release-cycle), [current official port](https://github.com/microsoft/vcpkg/blob/master/ports/openssl/vcpkg.json) |
| Azure signing naming/API; Apple notarization | Repository already uses signing-account-name and maintained parent Actions; notarytool already replaces retired altool. No production trust claim or operation | [current vendor Action](https://github.com/Azure/artifact-signing-action/blob/v2/action.yml), [Apple migration](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool) |
| GitHub REST/artifact APIs | Selected 2026-03-10 current supported version; older 2022-11-28 support ends 2028-03-10. Artifact digest/size/exact-source verification maintained; no selected API retirement found | [version policy](https://docs.github.com/en/rest/about-the-rest-api/api-versions), [artifact APIs](https://docs.github.com/en/rest/actions/artifacts) |
| Android endpoints | Official latest ZIP endpoints current; version/hash/executable/paths verified anew; no endpoint migration required | [official downloads/release notes](https://developer.android.com/tools/releases/platform-tools) |
| Remaining announcement scan | Android SDK CMake and MySQL changes, Podman rollback, obsolete partner-image ownership, older unrelated tooling are not used by these release paths; no unnecessary libraries or tools added | [runner announcements](https://github.com/actions/runner-images/issues?q=is%3Aissue+label%3AAnnouncement), [current ownership](https://github.com/actions/runner-images/blob/main/README.md) |

The final environment's **36 exact PyPI versions** were queried against OSV's
version API; all responses had no vulnerabilities. This is supplementary
database evidence, not proof of absence, and does not replace upstream bundled
library/vendor security assessment. No applicable unresolved required advisory
action was found after the Linux vendor update; affected native validation
passed. Sources: [OSV API](https://google.github.io/osv.dev/api/),
producer advisories/changelogs above. lxml 6.1.3 includes its September external
parameter entity parsing fix; no libxml binary substitution is made.

All checked release paths preserve six targets, intended tested compatibility
floors, strict legal/source acceptance and SHA provenance. The historical
Windows ARM64 Qt trace/wrapper anomaly and prep ARM64 post-pytest exit 139 remain
observations, not claimed fixes; any recurrence must be investigated before PASS.

## Validation checkpoint

Clean local CPython **3.14.8 x64**, isolated environment/application data:

- Focused freshness/pinning/workflow/version/legal/ELF/retention checks: **42 passed**.
- Full pytest: **1653 passed, 9 skipped**, no warnings, normal exit (after final Linux inspection correction).
- Compileall and canonical Quality Ruff scope on Ruff 0.16.10: PASS.
- Canonical Qt offscreen smoke, including status preservation: PASS.
- Guarded `main.py cli audit --help`, rejecting Qt/UI imports: PASS.
- Strict legal preflight with Nuitka 4.2.2 and source/license metadata: PASS.
- All nine workflow YAMLs, 17 Python helpers, 12 embedded Python blocks,
  all embedded workflow Bash/PowerShell, sysroot/smoke Bash and PowerShell helper syntax: PASS.
- `git diff --check`: PASS.

Affected native acceptance is recorded below. Final documentation-head Quality
is recorded in PR #220 after the last commit, before handoff, avoiding a
self-referential documentation commit. Every later release-producing build
still requires the future frozen main SHA and its post-merge Quality.
Local supporting snapshots/logs/archives are in ignored
`build/v2.2-final-freshness/`; durable conclusions belong in this document.
No tag, release, public asset, final assembly or production signing/notarization
operation is performed by this gate.

## Affected native diagnostic evidence

[Linux #16 / 36947969720](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36947969720),
exact SHA **`fe8ec98edc60ffb0baf47f9c634038e6a7cab38c`**, completed **SUCCESS**
on both native Ubuntu 24.04 targets after the security refresh and inspection correction.
Actual Python **3.14.8**, PySide/Shiboken/Qt **6.11.2**, Nuitka **4.2.2**.
Source pytest on each architecture: **1659 passed, 3 skipped**, normal exit;
the prep ARM64 post-pytest exit 139 did not recur and no suppression was added.
Both native trees passed GUI/CLI smoke, all-ELF architecture/version-needs
inspection, strict legal/source acceptance and ZIP roundtrip. x64 additionally
passed actual Ubuntu 22.04 offscreen GUI, Xvfb/xcb GUI and packaged CLI audit help.

| Architecture | Complete ELF inventory / ABI maxima | Independently verified package SHA-256 |
| --- | --- | --- |
| x64 | 134 ELFs; GLIBC 2.35 / GLIBCXX 3.4.29 | `5dd34eb67b5989e57becab0ed3a292baf4c8e6a0ed228508afb449ec5177d5f2` |
| ARM64 | 134 ELFs; GLIBC 2.38 / GLIBCXX 3.4.32 | `be09ac751f565c2b47fadf896ba323512c9f3f7bfd224a49c6642ccf3e018315` |

Independent downloaded-artifact checks matched every ELF architecture/hash,
all **143 runtime-manifest size/hash entries** and **five source-asset checksums**
per package. BUILD-INFO and legal manifests match application 2.2.0 and the exact
diagnostic SHA, full Python patch and Qt/Nuitka versions. x64 host compiler:
**GCC 13.3.0-6ubuntu2~24.04.1**; host images **20260927.320.1** x64 and
**20260927.135.1** ARM64, both Ubuntu **24.04.5**. The x64 target library pair
is Jammy **3.0.2-0ubuntu1.30**; both host/vendor runtimes installed Noble
**3.0.13-0ubuntu3.16**. The compatibility probe and final package each executed
in the supported 22.04 user-space runtime. The container shares the 24.04 host
kernel; this evidence does not establish every older-kernel, GPU or optional
device-integration path.

### Windows ARM64 and macOS Intel

[Windows #148 / 36947353761](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36947353761)
and [macOS #13 / 36947356678](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36947356678)
both completed **SUCCESS**, exact SHA
**`41a1b59461be95443f4b30d8bce1410ab2571487`**. Actual Python **3.14.8**,
PySide/Shiboken/Qt **6.11.2**, Nuitka **4.2.2**, native Rust/Cargo **1.99.0**.
The later two implementation commits affect Linux security provisioning/host
inspection and their regression coverage only; the validated Windows/macOS
workflow, native helper, application and dependency state is unchanged.

| Target | Native evidence | Independent downloaded-artifact acceptance |
| --- | --- | --- |
| Windows ARM64 | `windows-11-vs2026-arm64` image 20260924.168.1; native MSVC toolset 14.51.36231, Nuitka backend 14.5; Vcpkg tool 2026-09-26 and audited registry; native cryptography 50.0.2 source extension with OpenSSL 3.6.5; **1661 tests passed**, no skips; source and packaged GUI/CLI, including real CLI process wait/capture, and strict public legal/source validation passed | Exact BUILD-INFO/application 2.2.0 / Windows File/Product 2.2.0.0 / full Python / Qt / Nuitka; **80 runtime size/hash entries**, **71 ARM64 PE headers**, **five source assets** verified. ZIP SHA-256 `7bb2af66fb0d3602da01c3ad38ab2b534a1df06e1570d024056ba6a2d56efdad` |
| macOS Intel | macOS 26.6.1 / image 20260824.0517.1; Xcode 26.6 build 17F113, Apple Clang 21.0.0 (clang-2100.1.1.101); native cryptography 50.0.2 source extension / static OpenSSL 4.0.3; **1658 passed, 3 skipped**; source/package GUI/CLI, strict legal/source, ad-hoc signature and ZIP-roundtrip verification passed | Exact BUILD-INFO/application 2.2.0 / full Python / Qt / Nuitka; **111 runtime size/hash entries**, **97 x86_64 Mach-O headers**, **five source assets** verified. ZIP SHA-256 `1925f65ba1165d6a7878628f8405290bf243de7a72578c97fd29634d045e75ed` |

Windows remains unsigned. macOS uses **engineering ad-hoc signing only**;
production Developer ID credentials, notarization and Gatekeeper-production
trust are not activated or claimed. Intel main-executable deployment metadata
remains **10.15**; this is not independent old-macOS acceptance of all bundled
libraries. CPython's separately bundled OpenSSL is **3.5.9** on both targets,
distinct from the statically linked cryptography backends above. Windows ARM64's
historical Qt trace/wrapper observation did not prevent the real source/package
smokes here; no general fix or suppressed test is claimed.

All affected diagnostics passed without a recurring unexplained process crash.
The Linux #14/#15 cancellations/failure and corrected #16 acceptance remain
explicit above; no unsuccessful run substitutes for successful validation.
Unchanged Windows x64/macOS ARM64 native paths retain entry-gate evidence;
fresh manifest/pinning/guard/static checks cover them now, and they must receive
new full final candidates after freeze. This gate deliberately does not build
the complete six-target final candidate set.

These are diagnostic acceptance artifacts, not final candidates. Later final
packages must all be rebuilt from one future frozen main merge SHA after normal
PR merge and successful post-merge Quality. No immutable release/tag/source/
binary/checksum asset was altered, and no final release-run/hash placeholder was
filled. No tag, GitHub Release, public assets, final eight-file assembly,
production signing/notarization or issue #212 closure occurred.
