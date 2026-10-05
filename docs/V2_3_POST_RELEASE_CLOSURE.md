# v2.3.0 Phase E post-release closure audit

Initial audit: **2026-10-05 CEST**, PR #234 (`chore/v2.3-closure`). Follow-up: **2026-10-06 CEST**, `docs/v2.3-final-closure` from canonical main `19e2f14644000f9fbc11f1f7052fb16438692257`. PR #234 review/normal merge/post-merge checks and the initial safe local synchronization are complete; the new focused documentation PR still requires independent review, normal merge, post-merge checks and final local synchronization. #225/#232 stay open; final signoff belongs in their ledgers. This is tracked context, not a generated snapshot, handoff export or command Markdown.

## Accepted PR #234 and safe local synchronization

[Control Tower ledger](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-6005262111) independently accepted the reviewed PR #234 head `e7f41a235df9ea09cc2e304de970a1207a1b9898`, its normal merge to `19e2f14644000f9fbc11f1f7052fb16438692257`, and both parents: immutable frozen main `8d476dc5507d8249d8cd62c861095ed3e443f0af` plus the exact reviewed head. Merge timestamp `2026-10-05T23:16:14Z` is **2026-10-06 01:16:14 CEST**. Post-merge [Quality #682 / 37387525994](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37387525994) completed SUCCESS at exact canonical main with **1791 tests**, Ruff, compilation, PowerShell and Qt smoke. Rolling stable Python development restoration is merged; no product/version/dependency changes.

Before any synchronization on 2026-10-06 the real VS Code checkout was clean. Fetch with prune, switch main and fast-forward-only pull completed without discarding local work. Local HEAD, fetched origin/main and fresh GitHub main all matched `19e2f14644000f9fbc11f1f7052fb16438692257`, with a clean working tree. The local annotated v2.3.0 target remained `8d476dc5507d8249d8cd62c861095ed3e443f0af`. Live API/HTML checks corroborated the merged PR, Quality, rendered-main README (v2.3 latest/published features/unsigned-ad-hoc state/Sponsors/four screenshots), unchanged About/homepage/topics and latest published release/tag identity. The newer development main is not the immutable release source.

Only after the successful Docker inventory below was `docs/v2.3-final-closure` created from that clean synchronized main. Local and remote branch were absent before creation; no existing work was recreated. At follow-up inventory there are **45 local branches**, one registered worktree and one unmerged existing branch (`v2/local-apk-device-specific`), all preserved. The new final-documentation PR's review, merge, exact post-merge checks and resulting local synchronization are **pending**. No issue closure or generated handoff is performed; signoff remains in #225/#232.

## Completed Docker inventory (2026-10-06 CEST)

The installed Docker Desktop was initially stopped; it was started normally with explicit user authorization. No installation, configuration change, container/image/volume/cache deletion or prune occurred. Desktop **4.93.0 (240920)**, client/server Engine **29.8.1**, selected `desktop-linux` context, Linux amd64 server. All eight requested read-only inventory commands (version, info, all containers, digest-bearing images, volumes, detailed storage, builders and build-cache usage) completed successfully. Raw outputs and selected ownership/mount metadata are retained in an external temporary audit directory; no secret/environment values or extra tracked log/command file were added.

### Containers and ownership

**4 stopped containers, 0 running/paused**. Names, compose/DDEV labels and mounts identify the separate `shop-wp` WordPress project and shared DDEV router/SSH services.

| Container | Image | State / exit code |
| --- | --- | --- |
| `ddev-shop-wp-web` | `ddev/ddev-webserver:v1.25.4-shop-wp-built` | exited / 143 |
| `ddev-shop-wp-db` | `ddev/ddev-dbserver-mariadb-10.11:v1.25.4-shop-wp-built` | exited / 0 |
| `ddev-router` | `ddev/ddev-traefik-router:v1.25.4` | exited / 143 |
| `ddev-ssh-agent` | `ddev/ddev-ssh-agent:v1.25.4` | exited / 2 |

All four are preserved. Stopped state and nonzero historical exit codes are inventory facts, not evidence that another project's resources are disposable. No container was started/stopped/recreated by the inventory.

### Images, Ubuntu tags and dangling images

**9 unique image IDs / 10 repository-tag rows**; `ddev/ddev-webserver:latest` and `:v1.25.4` point to the same image. All named images are DDEV integrations; no `ubuntu:20.04`, `ubuntu:22.04`, `ubuntu:24.04` or other Ubuntu repository tag appears. No image named for Store App Audit or `psaa-remediation` appears. Dangling-image query returned **zero**.

| Repository | Tag | Image ID prefix |
| --- | --- | --- |
| `ddev/ddev-webserver` | `v1.25.4-shop-wp-built` | `2de2d93f1e95` |
| `ddev/ddev-dbserver-mariadb-10.11` | `v1.25.4-shop-wp-built` | `1d4b0772ca47` |
| `ddev/ddev-webserver` | `latest` | `5dfc489f8a4b` |
| `ddev/ddev-webserver` | `v1.25.4` | `5dfc489f8a4b` |
| `ddev/ddev-dbserver-mariadb-10.11` | `v1.25.4` | `b24bb87bc518` |
| `ddev/ddev-dbserver-mariadb-11.8` | `v1.25.4` | `869af6679e68` |
| `ddev/ddev-xhgui` | `v1.25.4` | `70946481646f` |
| `ddev/ddev-traefik-router` | `v1.25.4` | `004aab66ba2b` |
| `ddev/ddev-ssh-agent` | `v1.25.4` | `054f98a2f3d2` |
| `ddev/ddev-utilities` | `latest` | `97822ff9a064` |

Images without attached containers (base DDEV web/DB images, MariaDB 11.8, xhgui, utilities) may support other/future project runs; no deletion eligibility is inferred from their container count. Preserve them pending an explicit owner-reviewed cleanup. This local absence of Ubuntu images does not change intentional CI Ubuntu 22.04 x64 sysroot/probe/backward-smoke requirements.

### Volumes and cache

**5 local volumes**, all retained:

| Volume | Ownership / disposition |
| --- | --- |
| `ddev-global-cache` | shared DDEV cache / SSH service; preserve |
| `ddev-shop-wp-snapshots` | shop-wp project; preserve |
| `ddev-ssh-agent_dot_ssh` | shared DDEV cache / SSH service; preserve |
| `ddev-ssh-agent_socket_dir` | shared DDEV cache / SSH service; preserve |
| `shop-wp-mariadb` | shop-wp project; preserve |

Detailed storage reports `ddev-global-cache` **663.5 MB**, `shop-wp-mariadb` **185.7 MB**; snapshot/SSH volumes show **0 B** at inspection. The snapshot volume has zero container links but its project label identifies `shop-wp`; it is preserved. Global cache has three links and SSH socket volume two links; shared use is concrete.

Both `default` and selected `desktop-linux` builder entries are running, using the Docker driver and BuildKit **v0.33.0**. Cache usage shows **78 records / 1.152 GB**, **Shared 1.152 GB / Private 0 B**. `buildx du` labels **1.152 GB reclaimable**, while `docker system df` reports **0 B cache reclaimable**; the reports differ for these shared records, so preserve both observations without inferring additive guaranteed cleanup savings. Cache ownership is shared/ambiguous and all records remain intact.

| Docker storage category | Total | Active | Reported size | Reported reclaimable |
| --- | ---: | ---: | ---: | ---: |
| Images | 9 | 4 | 4.216GB | 876MB (20%) |
| Containers | 4 | 0 | 137.9MB | 137.9MB (100%) |
| Local Volumes | 5 | 4 | 849.2MB | 0B (0%) |
| Build Cache | 78 | 0 | 1.152GB | 0B |

Do not sum shared image/cache figures as exclusive disk allocation. Docker reports stopped-container writable layers and some images as reclaimable; the project labels/mounts and shared cache make them resources to preserve, not authorized cleanup targets. No application release staging, environment, unmerged branch or shared resource was deleted. The previous daemon-unavailable limitation below is now resolved by this completed read-only inventory.

## Historical starting state and immutable release (PR #234)


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

### Complete Actions artifact inventory at the 2026-10-05 retention snapshot

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

### Manual review candidates at the 2026-10-05 snapshot, preserved

Older partial/failure/cancelled runs `36847001212`, `36913179503`, `36921057381`, `36922785071`, `36927646143` and `36947574138` remain subject to the existing seven-day expiry; they do not replace successful generations. The unchanged workflow found none expired at dispatch.

Small historical SHA-specific Linux reports from `36930784495` and `36947969720` have distinct normalized artifact profiles; their continuing diagnostic value/consumers require manual review. Historical v1.99 assembler evidence `34401780853` and canonical v2.2 lineage are preserved. Previous successful generations have the existing seven-day grace relative to the new generation. These are inventory observations, not authorization to delete historical evidence. Older branch-scoped Python pip caches are also preserved; the policy is not changed to force storage savings.

## Live GitHub repository-page reconciliation

Live authenticated metadata before/after is unchanged:

- Description: `Store App Audit - Android App Inventory, Store Analysis & Maintenance Toolkit`.
- Homepage: empty (`null`); no canonical external website is invented.
- Topics: `adb`, `android`, `android-apps`, `apk`, `app-audit`, `app-inventory`, `desktop-app`, `google-play`, `google-play-store`, `pyside6`, `python`, `qt6`.
- Product identity/technical slug remain Store App Audit / PlayStoreAppAudit.
- Latest Release API confirms non-draft, non-prerelease v2.3.0 / ID `403687278`.
- Initial 2026-10-05 HTML inspection found stale v2.2/preparation README prose before PR #234 merged. After merge, [Control Tower ledger](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-6005262111) and the 2026-10-06 local authenticated rendered-README check confirm correct v2.3 latest/published wording, distribution state, Sponsors and all four screenshot references at `19e2f14644000f9fbc11f1f7052fb16438692257`. The final documentation PR must still receive its own post-merge public-context check.
- Sponsors repository link/badge, `.github/FUNDING.yml` and live [mrc-labs Sponsors page](https://github.com/sponsors/mrc-labs) remain correct; no metadata/account edits.
- The published body is copied verbatim into `RELEASE_NOTES.md`; its publication-time future public-verification sentence is preserved, with the subsequent independent PASS ledger recorded outside the body. No live body edit.

## Local Docker and repository hygiene

At the **initial 2026-10-05** audit Docker CLI **29.8.1** was installed but the daemon pipes were unavailable; Docker resource enumeration was genuinely pending then and no daemon start occurred in that task. The **completed 2026-10-06 inventory above supersedes that limitation** after the separately authorized normal Desktop start. Both audits preserved all resources and required CI Ubuntu 22.04 containers.

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

## Historical PR #234 validation

Focused policy/helper/workflow tests: **56 passed**. PowerShell parser for Windows standalone and export helpers: **PASS**; Bash syntax-only parse of the Linux sysroot helper: **PASS**. Full source gate on exact stable local Python **3.14.8**: **1782 passed, 9 skipped** (Windows directory-link privilege limitations); full Quality Ruff scope, application compileall, nine Python helper compilations, CI source Qt offscreen smoke and `pip check` all **PASS**. Product tree, main entry point, version metadata and dependency pins match the release baseline. Local validation logs/settings/caches remain outside the checkout. Exact PR head and exact-head remote Quality are supplied in the PR/final delivery report rather than embedding a self-referential hash here.

## Final documentation follow-up validation

This follow-up is Markdown-only. Local diff/path/whitespace and main-versus-release/pending-status coherence checks passed, with no product/version/dependency/workflow/helper changes. All **66 local Markdown target/anchor checks** passed; existing focused context/policy/version tests reported **25 passed**. The exact follow-up head and its remote Quality result are supplied in the PR/delivery report. No source/package rebuild or generated export is required or performed. Quality #682 above belongs to already merged PR #234; the new documentation PR's own Quality result remains separate and is recorded in its reviewable delivery evidence.

## Closure checklist

Completed: immutable publication and independent public-byte acceptance; initial PR #234 review/normal merge to `19e2f14644000f9fbc11f1f7052fb16438692257`; exact post-merge Quality #682/public README/metadata checks; preserved retention snapshot and canonical release evidence; clean real local synchronization to that main; complete read-only Docker/container/image/volume/cache/storage and local Git inventories with all shared/ambiguous resources and staging preserved; rolling Python restoration; maintained context reconciliation for the focused documentation follow-up.

Pending: independent review and normal merge of the **new** `docs/v2.3-final-closure` documentation PR; its exact post-merge Quality and public-context recheck; final safe clean local synchronization to the resulting canonical main; ledger signoff and any separately authorized issue handling by Control Tower. No handoff/export or generated command Markdown is authorized now. No merge/auto-merge, issue closure, production signing, assembly/build dispatch, rebuild, tag, publication, asset replacement, local pruning/deletion or unrelated feature work was performed in this follow-up. **Do not call the whole cycle closed yet.**
