# v2.3.1 maintenance release preparation

Audit date: **2026-10-24 Europe/Rome (CEST)**. Canonical tracker: [#238](https://github.com/mrc-labs/PlayStoreAppAudit/issues/238). Starting main: `58f0d27041b6220442e9c35e470db744c3dfe02c`. Temporary branch: `release/v2.3.1-maintenance`.

This is the active release checklist and complete **entry** component audit required by [the freshness policy](RELEASE_COMPONENT_FRESHNESS.md). It records fresh official upstream queries and local validation, not copied v2.3 acceptance. Categories: **A** directly selected/resolved components; **B** supported parent bundles; **C** vendor-owned internals; **D** supported OS/compiler integrations preserving the accepted matrix/floors.

Source metadata is prepared as **2.3.1 / Windows 2.3.1.0**. Latest published remains **v2.3.0**, immutable source `8d476dc5507d8249d8cd62c861095ed3e443f0af`, tag object `ee386624680b8608a98fb13da5f51bdff736d1e9`, Release ID `403687278`. No new release SHA is frozen, and no v2.3.1 packages have been built or published. Published v2.3.0 binaries are never inputs to the new release.

## Scope and acceptance boundaries

- [x] Clean real checkout verified; origin URL and fetched main match the expected repository/SHA; clean local main fast-forwarded from `dd6d9dc9ff39e330129d3624e4de57d4ab004966`; requested branch did not already exist.
- [x] Complete entry inventory, stable/minor/major comparison, support/deprecation/security review and compatible refresh below.
- [ ] Focused PR reviewed independently and exact-head Quality accepted by Control Tower.
- [ ] Normal merge commit, post-merge Quality and complete second freshness audit.
- [ ] One exact audited Python patch pinned/asserted in all producing/final Quality/signing/assembly setups, then a new main SHA frozen.
- [ ] All six same-SHA packages rebuilt and independently accepted, including actual ABI/deployment floors, GUI/CLI, architecture, provenance and strict package-aware legal/source evidence.
- [ ] Eight-file assembly, explicit tag/publication approval, public re-download/hash/byte acceptance and full [closure](RELEASE_CLOSURE.md).

No application behavior/source adaptation is included; the only application package edit is version metadata. A discovered need for an application fix or compatibility adaptation must be referred to Control Tower for MINOR scope reassessment. No #154 signing activation, #209 updater, product feature or opportunistic refactor. Windows/Linux remain unsigned; macOS engineering/ad-hoc only. No Docker/DDEV/site resources were inspected or cleaned for this preparation.

## Python decision and six-target availability (A/B)

Fresh [Python downloads](https://www.python.org/downloads/), [3.14.9](https://www.python.org/downloads/release/python-3149/) and [3.15.1](https://www.python.org/downloads/release/python-3151/) establish stable **3.15.1** globally and **3.14.9** as the latest supported compatible 3.14 patch, both released October 21. The [lifecycle table](https://devguide.python.org/versions/) retains 3.14 bugfix support/security EOL **2030-10**, versus 3.15 **2031-10**.

**Select 3.14.9 for entry validation; retain rolling stable 3.14 / check-latest during preparation.** [Nuitka's current manual](https://nuitka.net/user-documentation/user-manual.html#python) supports through 3.14, while the [4.3 release](https://nuitka.net/posts/nuitka-release-43.html) explicitly calls 3.15 support experimental. [Current compiler changelog](https://nuitka.net/changelog/Changelog.html) does not promote it to a supported production baseline. PySide 6.12.0 accepts `<3.16,>=3.10` and supplies stable ABI wheels, but that alone cannot approve the full 3.15 compiler stack. This is a concrete support-boundary exception, not avoidance of a newer stable Python or validation cost. No free-threaded/experimental configuration is selected.

The freshly fetched [hosted manifest](https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json) includes stable GIL-enabled **3.14.9** and **3.15.1** for Windows x64/ARM64, macOS x64/ARM64 and Ubuntu 24.04 x64/ARM64. Both also have Ubuntu 22.04 x64 distributions. There is **no manifest propagation blocker**. Official 3.14.9 [Actions release](https://github.com/actions/python-versions/releases/tag/3.14.9-39619022138):

| Target | Official distribution |
| --- | --- |
| Windows x64 | `python-3.14.9-win32-x64.zip` |
| Windows ARM64 | `python-3.14.9-win32-arm64.zip` |
| macOS Intel | `python-3.14.9-darwin-x64.tar.gz` |
| macOS ARM64 | `python-3.14.9-darwin-arm64.tar.gz` |
| Linux x64 / ARM64 | `python-3.14.9-linux-24.04-{x64,arm64}.tar.gz` |
| Ubuntu 22.04 compatibility x64 | `python-3.14.9-linux-22.04-x64.tar.gz` |

The canonical `download_linux_compat_python.py` downloaded the 22.04 x64 archive and verified official release size/digest, observed SHA-256 **`a379ac4453e83c7e5525321ee9d56c92482f1d307a00fd30c3fd44e5d9bea008`**. No custom distribution or patch downgrade. The Windows hosted archive also matched its official size/digest (`c9ab01887dbbbfd99dbd15321e150df5099245498ff649be06e061d637133aa3`); its PSF installer has valid Authenticode. Its runner setup script was **not** executed locally. Local validation instead uses the official Python install manager's signature-verified index and `--target` extraction inside ignored `artifact/`, plus a fresh venv. Existing global Python installations and existing venvs were not updated.

All 11 setup environments/nine workflows retain rolling 3.14 selectors and stable/final guards. The existing architecture/GIL checks and Linux same-patch enforcement remain. **No final patch pins are populated by this entry gate.** Repeat full freshness and exact-patch selection before freeze.

## Complete Python dependency inventory (A, matched Qt B)

The previous column is the starting manifest pin or the last published release-entry resolved version, not a claim about every user's existing environment. Selected/installed and latest stable/latest compatible were compared against fresh non-yanked PyPI release metadata, Python requirements and wheel filenames. Every row links its exact authoritative metadata. A resolved transitive update does not add a new application library. Certifi was already a requests transitive; an explicit matching runtime pin now ensures reused environments receive corrected trust material.

| Component | Category | Previous | Selected/installed | Latest stable / compatible | Decision/source |
| --- | --- | --- | --- | --- | --- |
| asn1crypto | A | 1.5.1 | 1.5.1 | 1.5.1 | current; [PyPI](https://pypi.org/pypi/asn1crypto/1.5.1/json) |
| ast_serialize | A | 0.12.1 | 0.13.1 | 0.13.1 | updated; [PyPI](https://pypi.org/pypi/ast_serialize/0.13.1/json) |
| beautifulsoup4 | A | 4.15.0 | 4.15.0 | 4.15.0 | current; [PyPI](https://pypi.org/pypi/beautifulsoup4/4.15.0/json) |
| certifi | A | 2026.7.22 | 2026.10.23 | 2026.10.23 | updated; [PyPI](https://pypi.org/pypi/certifi/2026.10.23/json) |
| cffi | A | 2.1.1 | 2.1.1 | 2.1.1 | current; [PyPI](https://pypi.org/pypi/cffi/2.1.1/json) |
| charset-normalizer | A | 3.5.2 | 3.5.2 | 3.5.2 | current; [PyPI](https://pypi.org/pypi/charset-normalizer/3.5.2/json) |
| click | A | 8.5.0 | 8.5.0 | 8.5.0 | current; [PyPI](https://pypi.org/pypi/click/8.5.0/json) |
| colorama | A | 0.4.6 | 0.4.6 | 0.4.6 | current; [PyPI](https://pypi.org/pypi/colorama/0.4.6/json) |
| cryptography | A | 50.0.2 | 50.0.2 | 50.0.2 | current; [PyPI](https://pypi.org/pypi/cryptography/50.0.2/json) |
| google-play-scraper | A | 1.2.7 | 1.2.7 | 1.2.7 | current; [PyPI](https://pypi.org/pypi/google-play-scraper/1.2.7/json) |
| idna | A | 3.20 | 3.20 | 3.20 | current; [PyPI](https://pypi.org/pypi/idna/3.20/json) |
| iniconfig | A | 2.3.0 | 2.3.1 | 2.3.1 | updated; [PyPI](https://pypi.org/pypi/iniconfig/2.3.1/json) |
| librt | A | 0.16.0 | 0.16.0 | 0.16.0 | current; [PyPI](https://pypi.org/pypi/librt/0.16.0/json) |
| lxml | A | 6.1.3 | 6.1.3 | 6.1.3 | current; [PyPI](https://pypi.org/pypi/lxml/6.1.3/json) |
| mypy | A | 2.4.0 | 2.4.0 | 2.4.0 | current; [PyPI](https://pypi.org/pypi/mypy/2.4.0/json) |
| mypy_extensions | A | 1.1.0 | 1.1.0 | 1.1.0 | current; [PyPI](https://pypi.org/pypi/mypy_extensions/1.1.0/json) |
| Nuitka | A | 4.2.2 | 4.3.1 | 4.3.1 | updated; [PyPI](https://pypi.org/pypi/Nuitka/4.3.1/json) |
| packaging | A | 26.3 | 26.3 | 26.3 | current; [PyPI](https://pypi.org/pypi/packaging/26.3/json) |
| pathspec | A | 1.1.1 | 1.1.1 | 1.1.1 | current; [PyPI](https://pypi.org/pypi/pathspec/1.1.1/json) |
| pillow | A | 12.3.0 | 13.0.0 | 13.0.0 | updated; [PyPI](https://pypi.org/pypi/pillow/13.0.0/json) |
| pip | A | 26.2.1 | 26.2.2 | 26.2.2 | updated; [PyPI](https://pypi.org/pypi/pip/26.2.2/json) |
| pluggy | A | 1.6.0 | 1.7.0 | 1.7.0 | updated; [PyPI](https://pypi.org/pypi/pluggy/1.7.0/json) |
| pyaxmlparser | A | 0.3.31 | 0.3.31 | 0.3.31 | current; [PyPI](https://pypi.org/pypi/pyaxmlparser/0.3.31/json) |
| pycparser | A | 3.0 | 3.12 | 3.12 | updated; [PyPI](https://pypi.org/pypi/pycparser/3.12/json) |
| Pygments | A | 2.21.0 | 2.21.0 | 2.21.0 | current; [PyPI](https://pypi.org/pypi/Pygments/2.21.0/json) |
| PySide6_Essentials | B matched Qt parent | 6.11.2 | 6.12.0 | 6.12.0 | updated; [PyPI](https://pypi.org/pypi/PySide6_Essentials/6.12.0/json) |
| pytest | A | 9.1.1 | 9.1.1 | 9.1.1 | current; [PyPI](https://pypi.org/pypi/pytest/9.1.1/json) |
| requests | A | 2.34.2 | 2.34.2 | 2.34.2 | current; [PyPI](https://pypi.org/pypi/requests/2.34.2/json) |
| ruff | A | 0.16.10 | 0.17.2 | 0.17.2 | updated; [PyPI](https://pypi.org/pypi/ruff/0.17.2/json) |
| setuptools | A | 84.0.0 | 84.2.1 | 84.2.1 | updated; [PyPI](https://pypi.org/pypi/setuptools/84.2.1/json) |
| shiboken6 | B matched Qt parent | 6.11.2 | 6.12.0 | 6.12.0 | updated; [PyPI](https://pypi.org/pypi/shiboken6/6.12.0/json) |
| soupsieve | A | 2.10 | 3.0.4 | 3.0.4 | updated; [PyPI](https://pypi.org/pypi/soupsieve/3.0.4/json) |
| typing_extensions | A | 4.16.0 | 4.16.0 | 4.16.0 | current; [PyPI](https://pypi.org/pypi/typing_extensions/4.16.0/json) |
| urllib3 | A | 2.8.0 | 2.8.0 | 2.8.0 | current; [PyPI](https://pypi.org/pypi/urllib3/2.8.0/json) |
| websocket-client | A | 1.9.2 | 1.9.2 | 1.9.2 | current; [PyPI](https://pypi.org/pypi/websocket-client/1.9.2/json) |
| wheel | A | 0.48.0 | 0.48.0 | 0.48.0 | current; [PyPI](https://pypi.org/pypi/wheel/0.48.0/json) |

`pip check` passes and the complete installed runtime/dev/build environment returns **[]** from `pip list --outdated --format=json`. Packaging build-system pins are setuptools **84.2.1** / wheel **0.48.0**. Existing unpinned transitive constraints resolve the current versions shown; they were not converted into a new lock system.

Pure Python wheels have no native architecture floor. Fresh filename/Requires-Python inspection for compiled packages covers cp314 and/or compatible abi3 plus these paths:

| Native component | Six-target wheel/support evidence and decision |
| --- | --- |
| PySide6-Essentials/Shiboken/Qt **6.12.0** | cp310-abi3; Windows amd64/ARM64, macOS **14 universal2**, manylinux **2.34 x64 / 2.39 ARM64**. Linux tags match 6.11.2; macOS wheel tag moves 13 to 14, below accepted whole-package metadata maxima Intel 26 / ARM64 15. [Qt 6.12 platform matrix](https://doc.qt.io/qt-6/supported-platforms.html) explicitly retains Ubuntu 22.04 x64, Ubuntu 24.04 both architectures, Windows 10 1809+/11/ARM64 and macOS 14.4+. Final measured binary floors must remain within v2.3 acceptance; metadata checks do not substitute for packaged runtime tests. |
| Pillow **13.0.0** | cp314 Windows amd64/ARM64, macOS 10.15 x64 / 11 ARM64, manylinux 2.27/2.28 x64/ARM64; no accepted floor increase. [13.0 notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html): drops Python 3.10, not this 3.14 baseline; removed APIs are not used by repository tools/application. Pillow remains development-only and excluded from packages. |
| Ruff **0.17.2** | Native py3 wheels for Windows amd64/ARM64, macOS 10.12 x64 / 11 ARM64, manylinux 2.17 x64/ARM64. [Release](https://github.com/astral-sh/ruff/releases/tag/0.17.2); existing rules pass without source fixes or broadened ignores. |
| ast_serialize **0.13.1** | cp39-abi3 wheels on both Windows/macOS/Linux architectures, macOS 10.12 x64 / 11 ARM64, manylinux 2.17. Current resolved mypy dependency. |
| cffi **2.1.1**, charset-normalizer **3.5.2**, lxml **6.1.3**, librt **0.16.0**, mypy **2.4.0** | Exact PyPI file lists were checked for cp314/pure alternatives; current supported native integrations retained. Mypy also publishes a pure Python wheel for hosts without a compiled wheel. No new floor selected. |
| cryptography **50.0.2** | Current stable parent, abi3 wheels for Windows x64, Linux x64/ARM64 and macOS ARM64. **No Windows ARM64 or macOS Intel wheel**: preserve the existing audited native source-build paths, rather than claim six-wheel coverage. [Stable installation docs](https://cryptography.io/en/50.0.2/installation/) and [changelog](https://cryptography.io/en/50.0.2/changelog/) retain the selected OpenSSL integrations; next 51.0.0 is unreleased. All-six native source/package validation remains a final-candidate gate. |

### Deployment/compiler components and announced removals

**Nuitka 4.2.2 -> 4.3.1** (A) is the fresh latest stable compatible release, including the 4.3 maintenance patch; use 4.3.1 in all four consuming workflows, preflight assertions, local batch helper and corresponding tests. Source archive installation/build and exact legal files passed. The supported native compiler matrix remains MSVC, system GCC/Clang and both 64-bit architectures. Standalone mode remains explicit.

[Qt for Python release notes](https://doc.qt.io/qtforpython-6/release_notes/pyside6_release_notes.html) were reviewed for 6.12.0 and 6.11.3: deployment `python_path` was removed; repository configuration does not use it. Removed item-copy constructors, changed QSettings/QDataStream deserialization, opt-in `loadUiType` and deployment shell/extraction fixes require no application adaptation in the source/smoke suite. `pyside6-deploy`'s new standalone default does not change the explicit repository mode.

Use the stable **`--no-install`** deployment option in Linux/macOS init/build steps: validate the already installed audited tooling instead of allowing deployment to modify it. A local init/dry-run verified command generation and unchanged Nuitka 4.3.1 without compiling. The parent default spec still mentions Nuitka 4.1.1 (B observation); the selected installed compiler is explicit/current. Linux deployment checks the **Python distribution** `patchelf`, not just the apt executable; explicitly install **patchelf==0.19.1.0** (A, current stable compatible manylinux wheels on both architectures). This surfaces the existing deployment dependency and makes it reviewable before preflight; apt patchelf remains an OS prerequisite.

[Nuitka 4.3.1 SCons selector](https://github.com/Nuitka/Nuitka/blob/4.3.1/nuitka/build/SconsInterface.py) uses bundled **4.10.1 for Python >=3.7 on all systems**, legacy **4.3.0/3.1.2** paths otherwise. Independent [SCons 4.11.1](https://pypi.org/pypi/SCons/json) is a **B upstream observation**, not an override. Deprecated `__nuitka_binary_dir`/`__nuitka_binary_exe` have no repository use; current `__compiled__` detection remains supported. No migration source fix is needed.

### Embedded library inventory (B)

Parent freshness and applicable security were evaluated at the supported parent boundary; embedded internals are not mechanically replaced with independently newer majors. Local actual Windows runtime inspection plus the [official CPython 3.14.9 Windows SBOM](https://www.python.org/ftp/python/3.14.9/python-3.14.9-amd64.exe.spdx.json) establishes:

| Supported parent | Actual embedded components | Latest-compatible decision |
| --- | --- | --- |
| CPython **3.14.9** | OpenSSL **3.5.9**, Expat **2.9.0** (was 2.8.5), SQLite **3.50.4**, zlib API **1.3.1.zlib-ng**; SBOM zlib-ng **2.2.4**, bzip2 **1.0.8**, xz **5.2.5**, zstd **1.5.7**, libffi **3.4.4**, libmpdec **4.0.0/2.5.1**, Tcl **9.0.4.0**, Tk **9.0.4.1**, macholib **1.0** and HACL* revision `8ba599b2f6c9701b3dc961db895b0856a2210f76` | Current compatible official parent; no standalone replacement. Windows host compiler MSC **19.44**. Other native runtime embedded versions must be logged from their actual packages. |
| ensurepip/pip **26.2.2** | Bundled certifi **2026.10.19**; SBOM vendored cachecontrol 0.14.4, distlib 0.4.2, distro 1.9.0, idna 3.18, msgpack 1.1.2, packaging 26.2, platformdirs 4.10.0, Pygments 2.20.0, pyproject-hooks 1.2.0, requests 2.34.2, resolvelib 1.2.1, rich 14.2.0, tomli 2.4.1, tomli-w 1.2.0, truststore 0.10.4, urllib3 2.7.0; setuptools 70.3.0 in SBOM build tooling | Supported parent with security-remediated CA bundle. Independent runtime certifi **2026.10.23** and build setuptools **84.2.1** are separately selected A components; do not confuse vendored/build SBOM values with installed distributions. |
| cryptography **50.0.2** Windows x64 wheel | OpenSSL **4.0.3** | Current supported parent; independent upstream **4.1.0** (October 23) is newer, but stable cryptography's supported/tested integration list stops at **4.0**. No experimental unlisted source integration adopted. |
| lxml **6.1.3** | libxml2 **2.11.9**, libxslt **1.1.45** | Current security-patched parent; [exact upstream changes](https://github.com/lxml/lxml/blob/lxml-6.1.3/CHANGES.txt). This remains pyaxmlparser's dependency, not Google Play HTTP parsing. |
| Pillow **13.0.0** development wheel | FreeType **2.14.3**, LittleCMS **2.19**, WebP **1.6.0**, AVIF **1.4.2**, RAQM **0.11.0**, FriBidi **1.0.11**, HarfBuzz **14.5.0**, libjpeg-turbo **3.2.0** (JPEG API 8), OpenJPEG **2.5.4**, TIFF **4.7.2**, zlib-ng **2.3.3**, Tk API **9.0** | Latest supported parent, no independent codec replacement; Pillow is not shipped in final runtime. |

## Actions, API, assembly and signing integrations (A/C)

Every external `uses:` in all maintained workflows was inventoried. Major aliases already resolve to the current supported parent, so no cosmetic Action reference change is needed. Actual release/manifests were read afresh; official JavaScript Actions use **Node 24**. The application has no Node dependency or setup-node addition.

| Selected repository reference | Current stable parent | Decision/source |
| --- | --- | --- |
| actions/checkout@v7 | **7.0.1** | Current A; [release](https://github.com/actions/checkout/releases/tag/v7.0.1) |
| actions/setup-python@v7 | **7.1.0** (was 7.0.0) | Alias tracks updated A parent; [release](https://github.com/actions/setup-python/releases/tag/v7.1.0), normal official manifests retained; no mirror input selected |
| actions/upload-artifact@v7 | **7.0.2** (was 7.0.1) | Updated alias parent, retries/artifact client fixes; [release](https://github.com/actions/upload-artifact/releases/tag/v7.0.2) |
| actions/download-artifact@v8 | **8.0.2** (was 8.0.1) | Updated alias parent; [release](https://github.com/actions/download-artifact/releases/tag/v8.0.2) |
| azure/login@v3 | **3.1.0** | Current A parent; [release](https://github.com/Azure/login/releases/tag/v3.1.0) |
| azure/artifact-signing-action@v2 | **2.0.0** | Current A parent; [release](https://github.com/Azure/artifact-signing-action/releases/tag/v2.0.0); not activated |

Fresh [signing action manifest](https://github.com/Azure/artifact-signing-action/blob/v2.0.0/action.yml) C internals: ArtifactSigning module **0.1.8** vs [Gallery 0.1.20](https://www.powershellgallery.com/packages/ArtifactSigning); SDK BuildTools **10.0.26100.4188** vs [NuGet 10.0.28000.2705](https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/index.json); signing client **1.0.128** vs [1.0.146](https://api.nuget.org/v3-flatcontainer/microsoft.artifactsigning.client/index.json); optional Sign CLI **0.9.1-beta.26227.3** vs [stable 1.1.5](https://api.nuget.org/v3-flatcontainer/sign/index.json); nested cache **5.0.4** vs [current 6.1.0](https://github.com/actions/cache/releases/tag/v6.1.0). These are observations inside the current supported vendor parent, not independently selectable repository pins. The optional preview CLI is not a newly adopted path.

Fresh [Azure login lock](https://github.com/Azure/login/blob/v3.1.0/package-lock.json) C observations: actions/core **1.11.1** vs [3.0.1](https://registry.npmjs.org/@actions/core/latest), exec **1.1.1** vs [3.0.0](https://registry.npmjs.org/@actions/exec/latest), io **1.1.2** vs [3.0.2](https://registry.npmjs.org/@actions/io/latest). All five non-development npm lock dependencies were checked at exact versions in OSV below. No applicable advisory or declared unsupported/broken selected parent was identified; no vendor fork/internal override. Reopen when support/advisory/parent facts change. This is not credential-validated production trust acceptance.

The refreshed stable [vcpkg vendor tool manifest](https://github.com/microsoft/vcpkg/blob/2026.10.16/scripts/vcpkg-tools.json) also records C internals: CMake **4.4.3**, Ninja **1.13.2**, Windows Git **2.55.0.windows.5**, NuGet **7.9.0**, 7zip/7zr **26.03**, PowerShell **7.6.6**, Python embedded **3.14.7**, Node **24.21.0**, .NET **10.0.401**, azcopy **10.32.8**, gsutil **5.37**, coscli **1.0.8**, vswhere **3.1.7**. These are optional parent download definitions, not claims that every tool runs in this build. The [OpenSSL Windows recipe](https://github.com/microsoft/vcpkg/blob/2026.10.16/ports/openssl/windows/portfile.cmake) uses native compiler/CMake and Perl (NASM only outside its ARM64 CLANGASM branch); it does not request Python/pip, Node or the cloud tools. In particular, its optional embedded Python is not the selected application/build Python and has no ensurepip/pip bundle: the pip CA incident does not justify modifying unrelated vendor definitions. Actual acquired tools and their provenance must be retained in native candidate logs. Current stable parent is selected; no internal fork.

GitHub REST **2026-03-10** remains [current supported API](https://docs.github.com/en/rest/about-the-rest-api/api-versions); historical 2022-11-28 EOL **2028-03-10** is not the selected repository API. [Artifact size/digest and lineage APIs](https://docs.github.com/en/rest/actions/artifacts) remain supported. Assembly/legal/archive/hash helpers use Python stdlib and unchanged exact-SHA contracts; no separate obsolete archive library/binary is added. Apple `codesign`, `security`, `notarytool`, `stapler`, `spctl`, `lipo`, `otool` and `install_name_tool` remain in the supported Xcode/macOS parent; [altool migration](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool) is already complete. Neither production signing workflow was dispatched.

## Native toolchains, SDKs and compatibility floors (A/B/D)

| Component/current integration | Latest stable / latest compatible supported | Decision, support/deprecation and authoritative evidence |
| --- | --- | --- |
| Windows `windows-2025`, `windows-11-arm`, Quality `windows-latest` | Current supported native labels, VS 2026 **18.10.12224.181**, Windows SDK **10.0.26100.0**, PowerShell **7.6.6**, CMake **4.4.4**, Ninja **1.13.2**, GitHub CLI **2.102.0** in current inventories | D current vendor bundles; [x64 image](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-VS2026-Readme.md) `20261007.264.1`, [ARM64 image](https://github.com/actions/runner-images/blob/main/images/windows/Windows11-VS2026-Arm64-Readme.md) `20261013.183.4`; native MSVC/PE/GIL checks preserved. Log actual build image/tool versions later. |
| Rust source prerequisites **1.99.0** | Stable compatible **1.99.1**, October 15, paired Cargo **0.100.0** | A updated Windows ARM64/macOS Intel selectors/assertions. [Stable manifest](https://static.rust-lang.org/dist/channel-rust-stable.toml) explicitly has native `aarch64-pc-windows-msvc` and `x86_64-apple-darwin`; [release](https://blog.rust-lang.org/2026/10/15/Rust-1.99.1/). No architecture/floor removed. |
| macOS Intel rustup **1.29.1** | Stable compatible **1.29.2** | A updated official native installer and exact SHA-256; freshly downloaded installer matched **`b9610730ddeef52765723847866fd1e3540b2bf7d5ab0c324aa143a5edf25ba0`** from [upstream checksum](https://static.rust-lang.org/rustup/archive/1.29.2/x86_64-apple-darwin/rustup-init.sha256), [stable manifest](https://static.rust-lang.org/rustup/release-stable.toml). No Homebrew Intel bottle assumption. |
| Windows ARM64 vcpkg registry `eb2d3a3...` | Stable registry **2026.10.16**, exact commit **`9eec002df1cd109f8f104cd966a763daf9751489`**; vcpkg-tool **2026-09-26**, OpenSSL **3.6.5#2** | A updated stable registry; B/D port integration kept. [Release](https://github.com/microsoft/vcpkg/releases/tag/2026.10.16) tests arm64-windows-static-md; [port](https://github.com/microsoft/vcpkg/blob/2026.10.16/ports/openssl/vcpkg.json), [tool metadata](https://github.com/microsoft/vcpkg/blob/2026.10.16/scripts/vcpkg-tool-metadata.txt). New registry supports ARM64EC/multi-config wrappers; no hand-written port fork. |
| Windows ARM64 OpenSSL **3.6.5** through vcpkg | Global **4.1.0**; supported selected vendor port **3.6.5#2** | Latest stable registry still supplies 3.6.5. Retain vendor integration, static-MD/native PE checks. **OpenSSL 3.6 EOL 2026-11-01** is an explicit release-delay blocker: if freeze/build/publication crosses EOL without a supported replacement, reopen and stop. No unsupported parent may be waived. |
| macOS Intel independent OpenSSL **4.0.3** | Global **4.1.0**, October 23; latest stable **cryptography-supported integration 4.0.3** | A retained supported alternative: [stable cryptography installation matrix](https://cryptography.io/en/50.0.2/installation/) lists through 4.0, not 4.1. No unlisted/experimental native integration. [OpenSSL release](https://github.com/openssl/openssl/releases/tag/openssl-4.1.0) reviewed; no selected security fix requires 4.1. Existing static source checksum/architecture/deployment flags retained. [4.0 support](https://openssl-library.org/policies/releasestrat/) through **2027-05-14** (3.5 LTS through **2030-04-08**). |
| Linux Ubuntu **24.04.5** x64/ARM64 hosts | Newer GA **26.04**; compatible supported selected **24.04**, standard support through **May 2029** | D retain intended binary floor and current native/sysroot integration, which explicitly checks a 24.04 host. The [26.04 inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2604-Readme.md) has OS 26.04.1, kernel 7.0, GCC through 15.2.0/Clang 22.1.2; Qt 6.12 explicitly supports the selected Ubuntu 22.04/24.04 baseline. 26.04 is not a drop-in replacement for the current 24.04/sysroot contract. [x64 inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md) `20261012.334.1`, [ARM64 inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Arm64-Readme.md) `20261012.149.1`; GCC **13.3.0**, binutils **2.42-4ubuntu2.10**, Bash **5.2.21**, CMake **3.31.6**, Ninja **1.13.2**, distro patchelf **0.18.0-1.1build1**. No compiler/sysroot adaptation hidden in this PATCH. |
| Ubuntu **22.04** x64 sysroot/probe/runtime containers | Supported compatibility floor through **May 2027** | D current intentional container integration; [Ubuntu lifecycle](https://ubuntu.com/about/release-cycle). Hosted 22.04 build runners are already retired from this repository, separate from supported containers. Preserve official same-patch Python, sysroot probe, package-roundtrip and xcb/offscreen/CLI acceptance. No local Docker operation. |
| Linux OpenSSL | Noble **3.0.13-0ubuntu3.16**, Jammy **3.0.2-0ubuntu1.30**, current supported vendor security integrations | D current Ubuntu-backed alternatives to upstream 4.1; [Noble](https://launchpad.net/ubuntu/noble/+source/openssl), [Jammy](https://launchpad.net/ubuntu/jammy/+source/openssl), [USN-8847-1](https://ubuntu.com/security/notices/USN-8847-1). Apt refresh and fail-closed floors retained. Upstream 3.0 EOL does not end distro vendor support. |
| Noble zlib **1:1.3.dfsg-3.1ubuntu2.3** | Current vendor security-fixed revision | D explicitly install/refresh and require the fixed floor in both Linux builders for [USN-8954-1](https://ubuntu.com/security/notices/USN-8954-1), October 22. Jammy applicability is still under upstream/vendor evaluation; see security analysis below. |
| Linux Qt/GUI/native prerequisites | Supported apt packages: EGL/GL, fontconfig, X11/XCB/XKB, dbus/glib/atspi, Xvfb/xauth, binutils, zip/unzip; x64 sysroot libc/kernel headers, libssl/sqlite/uuid/ffi/bz2/lzma/z/crypt | D current maintained Noble/Jammy integrations, refreshed by apt; no independent library-major swaps. Exact candidate dpkg inventories and ABI maxima remain required. The installed package set and SDK/libc provenance are recorded by existing build helpers. |
| macOS **26** Intel/ARM64 + Xcode **26.6** | Global stable Xcode **27.1** (27.2 RC excluded); latest compatible common x64/ARM64 **26.6**, build **17F113**, Apple Clang **21.0.0**, macOS SDK **26.5** | D retain [Apple matrix](https://developer.apple.com/xcode/system-requirements/) common Intel support. [Apple explicitly requires Xcode 26 or earlier on Intel hosts](https://developer.apple.com/documentation/apple-silicon/porting-just-in-time-compilers-to-apple-silicon); the Xcode 27 hosted successor is also still a runner preview. [Xcode 27 security CVE-2026-65393](https://support.apple.com/en-us/149040) concerns IDE user-data permission handling, not this command-line packaging path; no IDE workspace is opened. [Intel image](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-Readme.md) OS **26.6.1**, image `20260824.0517.1`; [ARM64](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md) OS **26.6.2**, image `20261013.0424.1`. Explicit DEVELOPER_DIR isolates the supported Xcode from newer command-line tools. |
| Native download/legal utilities | Current supported runner/vendor curl, tar/ditto, shasum/Get-FileHash, Git/GitHub CLI, PowerShell, platform SDK signing tools | B/D inspect parent inventory; no new standalone utility pin. macOS current inventories expose curl **8.21.0 Intel / 8.7.1 ARM64**, bsdtar **3.5.3**, GNU tar **1.35**, Git **2.55.0 Intel / 2.56.0 ARM64**, CMake **4.4.2 Intel**. These are vendor tools, not code shipped in the app. Use HTTPS, existing pinned hashes/provenance and current supported OS trust. |

**Compatibility acceptance is unchanged:** Linux x64 Ubuntu 22.04 with maximum GLIBC 2.35 / GLIBCXX 3.4.29; ARM64 Ubuntu 24.04 with previous measured maxima 2.38 / 3.4.32. macOS requested compiler deployment settings 10.15/11.0 are not whole-package promises: previous measured metadata maxima Intel 26.0 / ARM64 15.0 and tested hosts 26.6.1/26.6.2 remain the comparison boundary. New candidate checks must measure again and reject an implicit increase; this entry record does not claim that six unbuilt packages passed.

## Android Platform-Tools / ADB (A/D)

Fresh [official notes](https://developer.android.com/tools/releases/platform-tools) and all managed latest archives confirm **37.0.1**, still latest stable compatible. CRC, expected executable/members and source.properties revision passed. No endpoint or application change:

| Official archive | Bytes | SHA-256 | Architecture |
| --- | --- | --- | --- |
| [Windows](https://dl.google.com/android/repository/platform-tools-latest-windows.zip) | 8,044,989 | `45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99` | PE i386 0x14c; retain accepted x64/ARM64 host execution contract, not native ARM64 |
| [Linux](https://dl.google.com/android/repository/platform-tools-latest-linux.zip) | 9,054,187 | `d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1` | ELF x64 (EM_X86_64=62), not a Linux ARM64 archive |
| [macOS](https://dl.google.com/android/repository/platform-tools-latest-darwin.zip) | 16,110,554 | `ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d` | Universal Mach-O, two architectures |

Linux ARM64 retains the native supported Noble [adb 34.0.4-debian](https://packages.ubuntu.com/noble/adb) vendor integration (D). Safe archive/executable validation and read-only device semantics are unchanged. Archives were inspected without installing ADB or connecting to a device.

## Security applicability and deprecation decisions

### Trust material: required remediation applied

[Python's October 21 releases](https://www.python.org/downloads/release/python-3149/) and [PSF security guidance](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576) identify the eMudhra/emSign incident. **pip 26.2.2 embeds certifi 2026.10.19**, removing the affected trust; independent runtime **certifi 2026.10.23** is latest and restores unaffected roots without reinstating compromised trust. [Certifi upstream history](https://github.com/certifi/python-certifi/commits/master/) was freshly read.

The remediation applies separately to build pip's vendored CA bundle, requests/runtime certifi and macOS Python certificates. All dependency-installing workflows and the local Windows helper bootstrap pip using **the exact HTTPS wheel URL plus SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70` published by Python/PSF**, before installing other packages. Bootstrap failure stops execution, including PowerShell and cross-platform UI-audit installs. Runtime certifi is pinned identically in requirements and project metadata. Fresh local 3.14.9 ensurepip already contains corrected pip; the hash-bound bootstrap was also exercised. Reused project venvs must receive the same bootstrap; unrelated local environments were not modified.

Stdlib downloads continue to use OS/CPython certificate verification plus existing hash/metadata/provenance gates. No trusted-host, disabled TLS verification, unverified certificates or manual global CA edits. [CPython #160040](https://github.com/python/cpython/issues/160040) proposes additional SPKI-denylist defense in depth and remains open at audit time; it is an upstream observation, not a released replacement or a reason to claim 3.14.9 has that extra feature. Candidate provisioning must keep OS trust/security updates current.

### Qt and Python package advisories

Fresh exact-version OSV batch queries: **43 queries / zero nonempty results** (38 Python packages including independently inspected SCons/patchelf, plus five non-development Azure/login npm dependencies). [OSV API](https://google.github.io/osv.dev/api/#tag/v1/operation/OSV_QueryBatch); exact PyPI release metadata also returned no listed vulnerabilities. These are dated database observations, not proof of absence. Parent-native advisories were separately inspected.

| Official advisory / date | Applicability and action |
| --- | --- |
| Qt [CVE-2026-95620](https://www.qt.io/blog/security-advisory-cve-2026-95620), Oct 23; [CVE-2026-96432](https://www.qt.io/blog/security-advisory-cve-2026-96432), Oct 21 | QNetworkAccessManager HTTP/2 DoS in <=6.11.2; fixed by selected **6.12.0**. No in-app HTTP/2 workaround/source fix required. |
| Qt [CVE-2026-16762](https://www.qt.io/blog/cve-2026-16762), Oct 23; [CVE-2026-8168](https://www.qt.io/blog/security-advisory-cve-2026-8168), Oct 19 | QXmlStreamReader/QtSvg DoS already fixed in previous 6.11.2 and selected **6.12.0**. QtSvg is used by icon tooling; no claim of non-applicability based only on Qt Widgets. |
| Qt [CVE-2026-101201](https://www.qt.io/blog/security-advisory-cve-2026-101201), Oct 20 | JSON/Qt5 compatibility parsing issue, affected through 6.11.2; selected **6.12.0** outside affected range. |
| Qt [CVE-2026-105923](https://www.qt.io/blog/security-advisory-cve-2026-105923), Oct 21 | Qt Quick VectorImage path not used in this Widgets application; selected 6.12.0 also fixes it. Previous September advisories remain fixed by the newer parent. |
| Pillow [13.0.0 security notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html) | EPS/Ghostscript decompression-bomb bypass GHSA-vx6w-vv9f-6gvg and ImageMorph zero-width write GHSA-58r4-6rv3-gfh8 addressed in selected parent; Pillow is dev-only. No removed Pillow API used. |
| [OpenSSL advisories](https://openssl-library.org/news/vulnerabilities/) / [Ubuntu USN-8847-1](https://ubuntu.com/security/notices/USN-8847-1) | Selected OpenSSL 3.5.9 / 3.6.5 / 4.0.3 and Ubuntu vendor-fixed revisions include applicable September fixes (including CVE-2026-35189/-35191/-42772/-54872/-54873/-54875). New independent 4.1.0 is not substituted into unsupported parent integrations. |
| [USN-8954-1](https://ubuntu.com/security/notices/USN-8954-1), Oct 22 / [CVE-2026-85091](https://ubuntu.com/security/CVE-2026-85091) | Noble zlib fixed package is now explicitly refreshed/asserted. Advisory concerns non-blocking C `gzwrite/gzprintf/gzvprintf` state, not Python's inflate/deflate API; the application uses Python gzip/zlib APIs, not those C write APIs. Jammy vendor status remains **Needs evaluation**, so record an upstream watch rather than label all older zlib/zlib-ng copies vulnerable or fixed. Existing CPython/zlib-ng parent is not manually replaced. Candidate native dependency/provenance and reachable-path review must be repeated if facts change. |

### Explicit migration/watch ledger

- **Required and applied:** current compatible Qt/Pillow/Nuitka/Ruff/setuptools/Rust/rustup/vcpkg refresh, secure pip/runtime certifi, Noble zlib security floor, and stable deployment no-install support. No application source adaptation was needed.
- **Required before freeze:** complete second audit, actual exact Python selection/pins/assertions, post-merge/exact-SHA Quality. No release package/security acceptance inferred from source checks.
- **Release-delay blocker:** OpenSSL 3.6 vendor/source integration EOL **November 1**; reevaluate before that boundary. A supported stable parent/port successor is required if release slips beyond it; any necessary source adaptation goes to Control Tower for scope/version reassessment.
- **Watch:** Python 3.15 production support in Nuitka; cryptography support for OpenSSL 4.1/native missing-wheel paths; CPython #160040; Jammy zlib upstream evaluation.
- **Announced, no current migration:** Qt **6.12 is the last Windows 10 series**; future 6.13 cannot implicitly raise that floor. Pillow IM removal **15.0 / 2028-10-15**, load_djpeg removal **14 / 2027-10-15**, deprecated ImageQt.align8to32: no repository use. SoupSieve 3.0.4 requires Python >=3.11.5 and its 3.0 migration notes were checked; current 3.14/BeautifulSoup integration passes without source edits.
- [Runner #14748](https://github.com/actions/runner-images/issues/14748): ubuntu-latest 26.04 rollout **October 19-November 19**, builders explicitly 24.04; [#14747](https://github.com/actions/runner-images/issues/14747) GA is not floor acceptance.
- [#14254](https://github.com/actions/runner-images/issues/14254): hosted Ubuntu 22.04 unsupported **2027-04-17**, already migrated builders; intentional supported compatibility containers remain. [#13518](https://github.com/actions/runner-images/issues/13518): macOS 14 runners unsupported **2026-11-02**, not selected.
- [#14602](https://github.com/actions/runner-images/issues/14602) / [#14592](https://github.com/actions/runner-images/issues/14592): Windows ARM VS2026 transition already supported by native existing checks. [#14404](https://github.com/actions/runner-images/issues/14404): Xcode 27 preview/Intel removal excludes migration. [#14856](https://github.com/actions/runner-images/issues/14856): macOS default OpenSSL 3 -> 4, existing independent Intel source path remains explicit. Android NDK28 removal/NDK30 addition [#14745](https://github.com/actions/runner-images/issues/14745) and Android CMake change [#14826](https://github.com/actions/runner-images/issues/14826) do not affect this desktop app; no Android APK compilation is performed. MySQL 8.0 removal [#14818](https://github.com/actions/runner-images/issues/14818) is unused.
- Windows legacy Python launcher/traditional installer replacement is announced; the supported install manager accepts existing `py -3.14` selection, so no launcher migration source change is required. Traditional installers remain supported for 3.14/3.15. No unsupported/preview successor is adopted.

## Validation and remaining release gates

The fresh isolated environment and official-source evidence are under ignored `artifact/v2.3.1-maintenance/`; they are working evidence, not release assets. Durable conclusions and authoritative sources are recorded here. No command-carrier or continuation Markdown was created.

- Python **3.14.9** native x64/GIL, matched PySide/Shiboken/Qt **6.12.0**, Nuitka **4.3.1**, certifi **2026.10.23** verified.
- `pip check` **PASS**; complete `pip list --outdated --format=json` **[]**.
- Full pytest **1782 passed / 9 skipped**, all 1791 collected tests, native Windows Python 3.14.9 with a dedicated application-data directory and `--basetemp`. Initial restricted runs encountered denied access to the real profile/default pytest temp tree, plus three stale compiler-pin expectations; the expectations were aligned and the isolated full rerun passed without application changes. The nine skips retain platform/privilege conditions. Exact-head remote Quality remains a separate acceptance gate, recorded in the PR.
- Compileall application plus release helpers **PASS**; repository Quality Ruff scope **PASS** with 0.17.2.
- Actual Windows GUI event-loop **offscreen and native windows plugins PASS**; canonical CI widget smoke **PASS**; source `main.py cli audit --help` **PASS**. App data for smoke/test reruns is isolated, not the user's real data.
- Strict canonical legal/source **preflight PASS** for 2.3.1 / 3.14.9 / Qt 6.12.0 / Nuitka 4.3.1 / certifi 2026.10.23: exact Qt/PySide/certifi source metadata and SHA-256, CPython license and all three required Nuitka legal files resolved. Package-aware strict corresponding-source/archive validation remains required after native builds; preflight intentionally does not download the large Qt source payloads.
- Modified PowerShell helper parses; Bash helpers syntax-check; deployment init/dry-run passes without compiler invocation or dependency mutation. Workflow static/unit tests must pass on final PR head.

**Stop boundary:** return focused PR/exact head and its Quality result to Control Tower. Do not merge, freeze, dispatch final package builds, assemble, tag or publish. After independent review, follow #238, BUILDING.md, RELEASE_NOTES.md and RELEASE_CLOSURE.md. Release notes must retain the four canonical sections and the approved maintenance-only highlights; publication/verification claims require new v2.3.1 evidence.
