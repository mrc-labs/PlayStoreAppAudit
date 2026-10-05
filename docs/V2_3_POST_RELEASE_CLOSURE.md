# v2.3.0 Phase E post-release closure audit

Audit date: **2026-10-05 CEST**. Scope: focused closure PR on `chore/v2.3-closure` for independent Control Tower review. Publication and independent public-byte verification already passed. **Final closure remains pending normal merge, post-merge verification and safe local synchronization.** #225/#232 remain open. This tracked audit is not a generated repository snapshot or handoff export.

## Starting state and immutable release

Before changing anything, `git status --short` was empty; branch was `main`. Local HEAD, fetched `origin/main` and live GitHub main all equalled `8d476dc5507d8249d8cd62c861095ed3e443f0af`. The authorized closure branch was absent locally/remotely and was created only after the read-only consumer/retention checks and authorized maintenance dispatch. No reset, stash, clean, discard or force operation occurred.

Latest stable public [v2.3.0](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v2.3.0) was published at **2026-10-05T12:44:51Z** (14:44:51 CEST). Release ID `403687278`; annotated tag object `ee386624680b8608a98fb13da5f51bdff736d1e9`, peeled target `8d476dc5507d8249d8cd62c861095ed3e443f0af`. GitHub API reports `immutable: false`; project policy still makes source/tag/assets immutable. Publication used local authenticated GitHub CLI, so there is no publication Actions run ID. No tag-triggered rebuild occurred.

[Independent Control Tower ledger](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-5995051051): fresh public download of all eight assets passed canonical names/sizes/SHA-256, ZIP integrity, checksum coverage and byte-for-byte equality against accepted CI assembly. The public checksum verifies seven payloads. This audit preserves that independent acceptance; it does not claim a new eight-asset local download.

### Canonical release lineage

All five runs were queried live: completed/SUCCESS, exact immutable release SHA.

| Gate | Run | Retained evidence |
| --- | --- | --- |
| Quality #680 | [37241775290](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37241775290) | 1790 passing tests, source checks; run/logs retained |
| Windows x64/ARM64 | [37246646085](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37246646085) | Both final candidate artifacts |
| Linux x64/ARM64 | [37246681845](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37246681845) | Both candidates and both compatibility reports |
| macOS Intel/ARM64 | [37246726056](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37246726056) | Accepted attempt 2, upload infrastructure retry; both accepted artifacts |
| Assembly | [37260955813](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37260955813) | Final artifact `11324630974` / `PlayStoreAppAudit-v2.3.0-final-release-assets` |

Assembly artifact compressed size **429,342,726 bytes**; upstream digest `de32d3aa4f7bec62519822446df154200329570b766840e8e2b144ef3327c91c`. Accepted macOS x64 `11321923618` and ARM64 `11320245610` are preserved; no rejected/replaced retry output is promoted.

### Published public asset identity

| Name | Asset ID | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `PlayStoreAppAudit-v2.3.0-linux-arm64.zip` | `612515647` | 82,688,647 | `d989faa60715d789d3b142a9170fcffb01490e721cd7180b3232400c8071d7b2` |
| `PlayStoreAppAudit-v2.3.0-linux-x64.zip` | `612515652` | 85,641,420 | `8fdd2dff09ea7ec54f76ecdd5ca941e98da28d9642c6fb3764dcbbe07cef1282` |
| `PlayStoreAppAudit-v2.3.0-macos-arm64.zip` | `612515651` | 46,431,422 | `3da0976fe496464f805b04ae6ec0a424d0fd937e44a89b123a778044817c0bb3` |
| `PlayStoreAppAudit-v2.3.0-macos-x64.zip` | `612515660` | 52,710,857 | `76681745c6c1b5d727ed2500c15c5cd8e6cbd2e6f31b6d32c280ced008bba5ed` |
| `PlayStoreAppAudit-v2.3.0-third-party-sources.tar.xz` | `612515656` | 73,174,984 | `53331a4c2c158b4cc77f9dbc07b9da8c4ad7dfce99b96d618f8baef36a613546` |
| `PlayStoreAppAudit-v2.3.0-windows-arm64.zip` | `612522708` | 43,603,246 | `e600d202a4fc0ab5e16442a614e18b4fb3ba1a820741636ca4b82c6afa4de9af` |
| `PlayStoreAppAudit-v2.3.0-windows-x64.zip` | `612528263` | 47,129,402 | `546547469503f63ecf82dfb6c0d1c728515f204a435037aa63b0aa1a852488e0` |
| `SHA256SUMS.txt` | `612534595` | 758 | `5e537300cff4ef27a230799596c77e4a7debc8eff24d856ddf43e029151bb7cf` |

### Signing, compatibility and toolchain facts

Published application **2.3.0**, Windows File/Product **2.3.0.0**. Exact release Python **3.14.8**, matched PySide/Shiboken/Qt **6.11.2**, Nuitka **4.2.2**, Android Platform-Tools **37.0.1**. Final freshness repeated before exact-main freeze; Phase B entry/preparation remains dated historical evidence, not a substitute for final/native acceptance.

Windows/Linux packages are unsigned. macOS is engineering ad-hoc only, without Developer ID, production signing or notarization. Six-platform architecture/version/startup/provenance/legal/source and same-SHA assembly acceptance passed before publication.

Linux uses Ubuntu 24.04 native build hosts. x64 passed Ubuntu 22.04 ZIP-roundtripped offscreen GUI, xcb GUI and CLI smoke. All-ELF maxima: x64 **GLIBC 2.35 / GLIBCXX 3.4.29**, ARM64 **2.38 / 3.4.32**; ARM64 native acceptance was Ubuntu 24.04. Preserve the supported Jammy x64 target sysroot and official same-patch interpreter, vendor OpenSSL security floors and host compiler provenance.

macOS main-executable deployment settings x64 **10.15** / ARM64 **11.0** are not package-wide floors. Highest bundled metadata is Intel **26.0** (OpenSSL) / ARM64 **15.0** (PySide/Shiboken), unchanged relative to v2.2. Tested hosts were Intel **26.6.1** / ARM64 **26.6.2**, with Xcode 26.6. No older-OS runtime acceptance is claimed.

## Actions housekeeping and retained evidence

Authenticated active GitHub CLI account `Mr-Mauro` had repository access. Full paginated artifact/producer inventory and queued/in-progress/waiting/pending/requested run queries found **no active consumer** before dispatch. Read-only simulation of the existing generational selection selected no canonical artifact; all nine were confirmed present, with Quality/build/assembly runs successful at the release SHA.

Dispatched only the existing unchanged maintenance workflow from frozen `main`:
`gh workflow run actions-retention.yml --repo mrc-labs/PlayStoreAppAudit --ref main`.

[Retention run 37348726683](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37348726683): `workflow_dispatch`, branch `main`, head `8d476dc5507d8249d8cd62c861095ed3e443f0af`, completed **SUCCESS**, job `111893876962`. Logs were inspected: active artifacts 37; successful runs, individual artifacts and expired failure/cancelled selections all empty. No retention deletion occurred. Workflow checkout's ordinary ephemeral-runner directory initialization is not an artifact deletion.

| Snapshot | Active artifacts | Compressed bytes | Separate pip caches | Cache bytes |
| --- | ---: | ---: | ---: | ---: |
| Before | 37 | 4,548,500,908 | 23 | 2,706,260,081 |
| After | 37 | 4,548,500,908 | 23 | 2,706,260,081 |

All nine canonical v2.3 artifacts total **1,665,855,684 bytes** and remain retained. Quality `37241775290` and both macOS attempts' accepted lineage remain available. Release/body, annotated tag/target and public asset identity were rechecked unchanged after retention. The policy/algorithm/default retention settings were preserved; only the development Python selector/guard is changed in this PR. No manual cleanup or cache purge occurred.

### Complete active Actions artifact inventory

| Artifact ID | Source run | Name | Compressed bytes |
| --- | --- | --- | ---: |
| `11324630974` | `37260955813` | `PlayStoreAppAudit-v2.3.0-final-release-assets` | 429,342,726 |
| `11321923618` | `37246726056` | `PlayStoreAppAudit-engineering-v2.3.0-macos-x64` | 199,172,941 |
| `11320245610` | `37246726056` | `PlayStoreAppAudit-engineering-v2.3.0-macos-arm64` | 192,894,552 |
| `11319967230` | `37246646085` | `PlayStoreAppAudit-v2.3.0-windows-arm64` | 190,105,896 |
| `11319633622` | `37246646085` | `PlayStoreAppAudit-v2.3.0-windows-x64` | 193,676,529 |
| `11319508548` | `37246681845` | `PlayStoreAppAudit-v2.3.0-linux-arm64` | 228,821,209 |
| `11319418692` | `37246681845` | `linux-compatibility-arm64-8d476dc5507d8249d8cd62c861095ed3e443f0af` | 9,492 |
| `11319418654` | `37246681845` | `linux-compatibility-x64-8d476dc5507d8249d8cd62c861095ed3e443f0af` | 21,002 |
| `11319229443` | `37246681845` | `PlayStoreAppAudit-v2.3.0-linux-x64` | 231,811,337 |
| `11220587477` | `36993205418` | `PlayStoreAppAudit-v2.2.0-final-release-assets` | 428,356,170 |
| `11220510677` | `36988301118` | `PlayStoreAppAudit-v2.2.0-windows-arm64` | 189,989,702 |
| `11219924280` | `36988307201` | `PlayStoreAppAudit-engineering-v2.2.0-macos-x64` | 199,003,581 |
| `11219603540` | `36988307201` | `PlayStoreAppAudit-engineering-v2.2.0-macos-arm64` | 192,740,971 |
| `11219182402` | `36988304138` | `PlayStoreAppAudit-v2.2.0-linux-x64` | 231,592,653 |
| `11219062492` | `36988301118` | `PlayStoreAppAudit-v2.2.0-windows-x64` | 193,543,987 |
| `11218992743` | `36988304138` | `linux-compatibility-x64-21b6646571b7e93044b76fe4d18a04eeec092f18` | 21,011 |
| `11218912152` | `36988304138` | `PlayStoreAppAudit-v2.2.0-linux-arm64` | 228,624,835 |
| `11218807357` | `36988304138` | `linux-compatibility-arm64-21b6646571b7e93044b76fe4d18a04eeec092f18` | 9,489 |
| `11203466670` | `36947969720` | `linux-compatibility-arm64-fe8ec98edc60ffb0baf47f9c634038e6a7cab38c` | 9,490 |
| `11203362036` | `36947969720` | `linux-compatibility-x64-fe8ec98edc60ffb0baf47f9c634038e6a7cab38c` | 21,002 |
| `11202562050` | `36947574138` | `linux-compatibility-x64-0b70546c8e49a048730c52d9b0b4b70171749a47` | 3,184 |
| `11198251292` | `36930784495` | `linux-compatibility-arm64-fbc19d0de4774b6ab83aff6ed709b965bcd9c47a` | 9,488 |
| `11196528912` | `36930784495` | `linux-compatibility-x64-fbc19d0de4774b6ab83aff6ed709b965bcd9c47a` | 20,994 |
| `11195068414` | `36927646143` | `linux-compatibility-arm64-9d6387bf3a19fc3f815f0d903e902622b5882850` | 9,489 |
| `11194818501` | `36927646143` | `PlayStoreAppAudit-v2.2.0-linux-arm64` | 228,624,302 |
| `11194769451` | `36927646143` | `linux-compatibility-x64-9d6387bf3a19fc3f815f0d903e902622b5882850` | 20,320 |
| `11194096391` | `36922785071` | `linux-compatibility-x64-a09bff955f38890bd357230962e9af0df14d48ef` | 19,660 |
| `11193940503` | `36922785071` | `linux-compatibility-arm64-a09bff955f38890bd357230962e9af0df14d48ef` | 9,488 |
| `11193755747` | `36922785071` | `PlayStoreAppAudit-v2.2.0-linux-arm64` | 228,624,148 |
| `11192718227` | `36921057381` | `PlayStoreAppAudit-v2.2.0-linux-arm64` | 228,624,203 |
| `11192258482` | `36921057381` | `linux-compatibility-arm64-6c7b73f4d888e0eb88e5d879acb592d91f68cf0f` | 9,490 |
| `11192121880` | `36921057381` | `linux-compatibility-x64-6c7b73f4d888e0eb88e5d879acb592d91f68cf0f` | 3,169 |
| `11190195078` | `36913179503` | `linux-compatibility-x64-7d1dc297dc15c6ac12863fc2180422cfae2244dd` | 16,565 |
| `11188638900` | `36913179503` | `PlayStoreAppAudit-v2.2.0-linux-arm64` | 228,624,290 |
| `11188578906` | `36913179503` | `linux-compatibility-arm64-7d1dc297dc15c6ac12863fc2180422cfae2244dd` | 9,488 |
| `11154989241` | `36847001212` | `PlayStoreAppAudit-engineering-v2.1.0-macos-arm64` | 192,739,336 |
| `10123756577` | `34401780853` | `PlayStoreAppAudit-v1.99.0-windows-x64-engineering-release-assets` | 111,364,719 |

### Manual review candidates, preserved

Older partial/failure/cancelled runs `36847001212`, `36913179503`, `36921057381`, `36922785071`, `36927646143` and `36947574138` remain subject to the existing seven-day expiry; they do not replace successful generations. The unchanged workflow found none expired at dispatch.

Small historical SHA-specific Linux reports from `36930784495` and `36947969720` have distinct normalized artifact profiles; their continuing diagnostic value/consumers require manual review. Historical v1.99 assembler evidence `34401780853` and canonical v2.2 lineage are preserved. Previous successful generations have the existing seven-day grace relative to the new generation. These are inventory observations, not authorization to delete historical evidence. Older branch-scoped Python pip caches are also preserved; the policy is not changed to force storage savings.

## Live GitHub repository-page reconciliation

Live authenticated metadata before/after is unchanged:

- Description: `Store App Audit - Android App Inventory, Store Analysis & Maintenance Toolkit`.
- Homepage: empty (`null`); no canonical external website is invented.
- Topics: `adb`, `android`, `android-apps`, `apk`, `app-audit`, `app-inventory`, `desktop-app`, `google-play`, `google-play-store`, `pyside6`, `python`, `qt6`.
- Product identity/technical slug remain Store App Audit / PlayStoreAppAudit.
- Latest Release API confirms non-draft, non-prerelease v2.3.0 / ID `403687278`.
- Live repository and latest v2.3 Release HTML plus rendered-main README were inspected, including four canonical screenshots. README still calls v2.2 latest and v2.3 unpublished because closure is not yet merged. This PR corrects current-facing README wording; **public main must be rechecked after merge**. Latest release discovery is confirmed by the authenticated API, separately from stale README prose.
- Sponsors repository link/badge, `.github/FUNDING.yml` and live [mrc-labs Sponsors page](https://github.com/sponsors/mrc-labs) remain correct; no metadata/account edits.
- The published body is copied verbatim into `RELEASE_NOTES.md`; its publication-time future public-verification sentence is preserved, with the subsequent independent PASS ledger recorded outside the body. No live body edit.

## Local Docker and repository hygiene

Docker CLI **29.8.1**, Windows/amd64, context `desktop-linux` is installed. The daemon is unavailable: named pipe `dockerDesktopLinuxEngine` cannot be found; default builder also cannot reach `docker_engine`. Read-only version, containers, images, volumes, system storage and buildx inventories were attempted; they could not enumerate daemon resources. **This is a limitation, not a completed or empty Docker audit.** Repeat when the daemon is available. No daemon start, prune, image/container/volume/cache deletion or inferred cleanup occurred. Intentional CI `ubuntu:22.04` compatibility containers remain required and unchanged.

One registered worktree exists: the user's VS Code checkout. 44 local branches were inspected; 43 are contained in starting `main` (including main and the newly created closure branch before edits). Unmerged local branches: `v2/local-apk-device-specific`. All branches are preserved; remote-tracking divergence/gone markers are not deletion authorization.

| Existing temporary branch | Inspection |
| --- | --- |
| `chore/v2.2-github-sponsors` | merged into starting main |
| `chore/v2.2-permanent-closure` | merged into starting main |
| `docs/final-v2.1-editorial-roadmap` | merged into starting main |
| `docs/v2.1-post-release-closure` | merged into starting main |
| `docs/v2.2-final-closure-confirmation` | merged into starting main |
| `feature/200-personal-device-library` | merged into starting main |
| `feature/211-headless-cli` | merged into starting main |
| `feature/v2.2-source-aware-custom-layouts` | merged into starting main |
| `feature/v2.3-duplicate-apk-management` | merged into starting main |
| `feature/v2.3-named-custom-views` | merged into starting main |
| `fix/v199-legal-cffi-evidence` | merged into starting main |
| `post-release/v2.0.0-docs` | merged into starting main |
| `release/v2.2-entry-freshness` | merged into starting main |
| `release/v2.2-fix-assembly-contract` | merged into starting main |
| `v2.1/local-apk-file-ops-core` | merged into starting main |
| `v2.1/quick-filter-spacing` | merged into starting main |
| `v2/acceptance-polish-2` | merged into starting main |
| `v2/acceptance-ux-fixes` | merged into starting main |
| `v2/canonical-screenshots-help` | merged into starting main |
| `v2/changes-history-polish` | merged into starting main |
| `v2/connected-device-play-profile` | merged into starting main |
| `v2/dark-mode-contrast` | merged into starting main |
| `v2/data-maintenance-polish` | merged into starting main |
| `v2/device-specific-productization` | merged into starting main |
| `v2/device-specific-resolver-core` | merged into starting main |
| `v2/device-specific-resolver-integration` | merged into starting main |
| `v2/device-specific-resolver-poc` | merged into starting main |
| `v2/final-file-about-polish` | merged into starting main |
| `v2/final-freshness-2.2.0` | merged into starting main |
| `v2/final-help-polish` | merged into starting main |
| `v2/final-polish-2.0.0` | merged into starting main |
| `v2/local-apk-device-specific` | unmerged: preserve; inspect ownership |
| `v2/local-apk-library-ui` | merged into starting main |
| `v2/local-apk-source-rework` | merged into starting main |
| `v2/release-macos-bundle-fix-2.0.0` | merged into starting main |
| `v2/release-macos-pyaxmlparser-resource-fix-2.0.0` | merged into starting main |
| `v2/release-posix-fixes-2.0.0` | merged into starting main |
| `v2/release-prep-2.0.0` | merged into starting main |
| `v2/release-prep-2.2.0` | merged into starting main |
| `v2/release-prep-2.3.0` | merged into starting main |
| `v2/release-workflow-fixes-2.0.0` | merged into starting main |
| `v2/source-workflow-containers` | merged into starting main |

Ignored material includes `artifact/`, `build/`, `dist/`, test/cache directories, `.venv/` and `.venv-py313-old/`. Old Python 3.13 environment, merged branches, stale test outputs and old preparation directories are possible manual cleanup candidates; ownership/reuse must be confirmed. Some historical pytest directories deny enumeration, so readable-byte totals below are partial where errors exist; nothing was forced or removed. No top-level `release-v*-candidate-*` directory was found.

| Local tree | Readable files | Readable bytes | Enumeration errors |
| --- | ---: | ---: | ---: |
| `artifact` | 7,371 | 46,536,945 | 18 |
| `build` | 54,440 | 4,235,694,999 | 30 |
| `dist` | 9,691 | 399,706,422 | 0 |

Existing `build/` children: `release-git-v2.1.0`, `release-work-v2.1.0-2`, `v2.1.0-pytest-temp`, `v2.2-assembly-contract`, `v2.2-closure`, `v2.2-final-context`, `v2.2-final-freshness`, `v2.2-freshness`, `v2.2-release-prep`. Existing `dist/release314env` and all `artifact/` RC/history/audit material are preserved.

Publication/acceptance staging is preserved: temporary `psaa-v230-publish-c26d872ea760438f89550ff1a0051f03` (accepted assets/body/verification), `psaa-v23-phase-d-3hpe335o` (candidate/CI assembly acceptance), `psaa-v23-phase-b-7ec2c03c54c940b99426996896e72299` (active isolated validation venv/evidence), and `psaa-v23-final-tests-c5755e676c074b40b5f082c36b74ad30`. New closure logs/PR text live outside the checkout in `psaa-v23-closure-n6mqzcj_`. Free C: disk at inspection: **131,205,672,960 bytes**; Docker storage cannot be measured while its daemon is unavailable. No shared/ambiguous resource or publication staging was deleted.

## Development restoration and context review

Restored rolling stable `3.14` / `check-latest: true` in all **11 setup environments across nine workflows**: Quality, Windows, Linux, macOS, both assemblers, Windows signing infrastructure (three setups), UI style audit and retention. Immediate guards reject other minor versions/prereleases and log the actual full version. Windows preserves standard-GIL/64-bit/native-architecture checks; Linux compatibility downloads the identical resolved full patch, rejects missing/unstable/unofficial distributions and retains release-asset size/digest plus post-install equality and security/ABI checks. The downloader already accepted stable full 3.14 patches; its documentation and tests now explicitly cover rolling resolution without changing download trust rules.

Exact 3.14.8 release/Phase B evidence remains historical. The permanent twice-per-release freshness policy and future exact-patch/full-equality freeze remain mandatory. No application/product code, canonical version, Windows version derivation, dependency pins, product scope, new library, signing policy or retention algorithm changed. #154/#209 remain deferred. Frozen Help's preparation wording is recorded as a historical limitation rather than changing immutable product code or released bytes.

Reviewed the required maintained context: AGENTS, README, CHANGELOG, PROJECT_DECISIONS, PROJECT_STATUS, ROADMAP, BUILDING, RELEASE_NOTES, CI_MAINTENANCE, HANDOFF_V2.3 and RELEASE_CLOSURE, plus RELEASE_COMPONENT_FRESHNESS, LOCAL_APK_DUPLICATES and v2.3 preparation/freshness/body records. Changed current facts and preserved historical v2.2-and-earlier notes. RELEASE_CLOSURE and RELEASE_COMPONENT_FRESHNESS procedures remain unchanged. No generated snapshot/export was created; next product milestone remains unassigned.

## Validation

Focused policy/helper/workflow tests: **56 passed**. PowerShell parser for Windows standalone and export helpers: **PASS**; Bash syntax-only parse of the Linux sysroot helper: **PASS**. Full source gate on exact stable local Python **3.14.8**: **1782 passed, 9 skipped** (Windows directory-link privilege limitations); full Quality Ruff scope, application compileall, nine Python helper compilations, CI source Qt offscreen smoke and `pip check` all **PASS**. Product tree, main entry point, version metadata and dependency pins match the release baseline. Local validation logs/settings/caches remain outside the checkout. Exact PR head and exact-head remote Quality are supplied in the PR/final delivery report rather than embedding a self-referential hash here.

## Closure checklist

Completed for review: initial clean exact-main gate; published identity and independent PASS ledger; consumer/artifact inventory; unchanged retention SUCCESS and before/after storage; preserved canonical release artifacts/logs; metadata/Sponsors inspection; local Git/material read-only inventory; rolling Python restoration and matched checks; maintained context reconciliation; focused and full local Quality/source gates.

Pending: independent Control Tower review and normal merge; exact post-merge Quality; live rendered-main README/metadata recheck; actual Docker resource inventory when daemon is available; clean local status/fetch --prune/switch main/pull --ff-only and exact canonical SHA verification; generated handoff only after synchronization if requested; final closure confirmation and explicit authorized issue handling. No merge/auto-merge, issue closure, production signing, assembly/build dispatch, tag, publication, asset replacement or unrelated feature work occurred in Phase E. **Do not call the cycle closed yet.**
