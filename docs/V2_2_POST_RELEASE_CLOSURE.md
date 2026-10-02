# v2.2.0 post-release closure audit

Audit date: **2026-10-02 CEST**. Scope: repository/context housekeeping and development-baseline restoration. Branch: `chore/v2.2-permanent-closure`. This is a reviewable closure PR, not a declaration that the unmerged release cycle is already closed. PR/head/Quality evidence is recorded after the final commit in the PR description and control-tower report to avoid a self-referential commit.

## Verified starting point and immutable release

Before any change the working tree was clean on `main`; local HEAD/main, origin/main and live GitHub main all equalled `21b6646571b7e93044b76fe4d18a04eeec092f18`. Local and remote `v2.2.0` are annotated, object `95a402b25f65bf22db58f831076bca747e2c9103`, peeling to that SHA. Public stable Release `401714084` contains exactly eight uploaded assets; [#212](https://github.com/mrc-labs/PlayStoreAppAudit/issues/212) remains open.

Canonical Quality `36987000922`, Windows `36988301118`, Linux `36988304138`, macOS `36988307201` and assembly `36993205418` were independently queried: all completed/success, attempt 1, exact release SHA. Published release/body and all eight asset IDs/names/byte sizes/digests/update timestamps were compared before/after housekeeping and are unchanged. The independent public re-download acceptance already recorded by the published Release is preserved, not redefined by this audit. Exact public sizes/hashes are in [PROJECT_STATUS.md](PROJECT_STATUS.md#published-v220-release).

## Actions housekeeping

Automatic `36993339377` followed final assembly, before publication. Deliberate [post-publication retention 36998852473](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36998852473) succeeded from canonical main using the still-frozen Python selector. Both saw 36 artifacts and selected no expired run/artifact deletion. The final assembler logs explicitly identify only Windows `36988301118`, Linux `36988304138` and macOS `36988307201` as source consumers. No workflow was in progress/queued when redundant retired candidates were removed.

Deleted only the authorized retired-freeze runs `36970928815`, `36970930873`, `36970933130`, removing eight artifacts. They were completed/success at the retired `80d56fe88a2bd998d3ac79bf0726eabf8ed66dee` freeze and were never public-release inputs. Final runs/artifacts and public assets remain intact. No retention policy/settings/algorithm change was made.

Remaining compressed Actions storage: **28 artifacts / 2,882,645,224 bytes / 2,749.10 MiB / 2.685 GiB**. Nine are canonical v2.2 final package/compatibility/assembler evidence. Nineteen older artifacts remain deliberately under existing grace/failed-run policy or as historical assembler evidence. Four older partial Linux ARM64 packages account for about 872 MiB of duplicate diagnostic data; they must not be mistaken for the accepted candidates. Older small SHA-specific compatibility reports remain visible and are recorded rather than changing normalization/retention logic during closure.

Separate pip caches: **23 / 2,706,260,081 bytes / 2.520 GiB**. Repeated keys are branch-scoped, with older 3.14.7 entries as well as 3.14.8. No cache purge was performed. This is a measured snapshot, not a promise that future CI leaves the count unchanged.

## Actions artifact inventory

| Artifact ID | Source run | Name | Compressed bytes |
| --- | --- | --- | ---: |
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

## Restored development contract

All nine workflows are reviewed and restored to stable `"3.14"` / `check-latest: true`: `quality.yml`, `build-windows-exe.yml`, `build-linux.yml`, `build-macos.yml`, `sign-windows.yml` (three environments), `assemble-release.yml`, `assemble-windows-engineering-release.yml`, `actions-retention.yml`, `ui-style-audit.yml`. All 11 setup steps guard stable major/minor 3.14 immediately before consumers and log the actual full runtime; PowerShell exits remain fail-closed. Duplicate Python/Qt/standard-GIL checks retain their semantics.

`build_windows_standalone.ps1` keeps 64-bit/native machine guards and full runtime logging, now allowing stable 3.14 patches. `prepare_linux_x64_sysroot.sh` resolves the actual full setup-python patch dynamically, requires stable 3.14, downloads the matching official Ubuntu 22.04 x64 distribution and verifies exact equality after installation. Security floors, native architecture, GIL and Qt/Nuitka pins are preserved. `requires-python >=3.14` and source version 2.2.0 are unchanged; no Python 3.15 migration occurred.

Regression tests accept 3.14.7/8/9 stable patches, reject other minors/prereleases, inventory every setup guard, preserve the historical exact 3.14.8 release evidence and require future audited full-patch freeze before SHA selection. The historical final gate's pin inventory/findings remain intact behind an explicit superseded/current-state banner.

## Documentation and live repository page

README/CHANGELOG/STATUS/ROADMAP/HANDOFF now describe published v2.2, its three shipped pillars and Sponsors, six platforms, unsigned Windows/Linux and engineering ad-hoc macOS without Developer ID/notarization. The exact release identity/runs/toolchain/public acceptance are recorded. Preparation/pending-freeze/unmerged-#220 claims were corrected in maintained current context; dedicated historical evidence is labeled, not silently rewritten. The former draft is a small superseded link record without placeholders. RELEASE_NOTES copies the actual live published body, preserving all four sections and the Sponsors footer.

ROADMAP assigns no v2.3 scope. #147/#154/#209 remain deferred. HANDOFF_V2.2 is the current post-release continuation file for the newest-handoff export selector. RELEASE_CLOSURE permanently requires live About/README verification and separate read-only local Docker hygiene. No repository snapshot or export was generated.

Live metadata was safely updated and re-read through authenticated GitHub API:

| Field | Before | After |
| --- | --- | --- |
| Description | Play Store App Audit - Android App Inventory, Store Analysis & Maintenance Toolkit | Store App Audit - Android App Inventory, Store Analysis & Maintenance Toolkit |
| Homepage | empty (`null`) | empty (`null`) |
| Topics | `adb`, `android`, `android-apps`, `apk`, `app-audit`, `app-inventory`, `desktop-app`, `google-play`, `google-play-store`, `pyside6`, `python`, `qt6` | unchanged |

Technical repository slug/executable/package identifiers and historical URLs remain `PlayStoreAppAudit`. No homepage was invented and no topic changed cosmetically.

The live repository homepage returned HTTP 200 and GitHub's server-rendered README was inspected through authenticated API. About already uses the corrected product description; README heading is Store App Audit and Sponsors links are present. `/releases/latest` resolves stable/public v2.2.0. The default-branch rendered README still advertises v2.1 and v2.2 preparation **until this PR merges**; this is an explicit remaining control-tower dependency, not a claim that a branch edit already updated public main. Branch rendered README verification and exact-head Quality must pass before handoff; default-branch homepage recheck follows merge. No connected browser was available; inspection used live HTML and API, not an unverified visual screenshot.

## Read-only local Docker audit

Docker is installed: client **29.8.1**, API **1.56**, Windows/amd64. Contexts: `default` (`npipe:////./pipe/docker_engine`) and selected `desktop-linux` (`npipe:////./pipe/dockerDesktopLinuxEngine`). The selected Linux engine pipe does not exist: daemon is not running/reachable. `docker version`, `docker ps -a`, `docker images`, `docker system df`, `docker volume ls` and `docker builder du` were attempted with access to the local configuration and returned the same daemon-unavailable condition.

Consequently Ubuntu tags (20.04/22.04/24.04), stopped containers, dangling images, Store App Audit packaging resources, volumes/cache and cross-project dependencies **cannot be inventoried yet**. No individual deletion candidate is certified; no image/container/volume/cache was deleted, no daemon was started and no prune was run. When the maintainer has Docker running, repeat those read-only commands and review individual resource ownership with control tower.

Normal local source development/pytest/Qt/CLI smoke does **not** require Docker. Repository CI intentionally retains `ubuntu:22.04` for x64 compatibility sysroot/probe and Ubuntu 22.04 GUI/CLI backward-runtime smoke, separate from Ubuntu 24.04 build hosts. Retired Ubuntu 22.04 hosted build runners do not authorize removing compatibility containers or unrelated local-project resources.

## Local repository hygiene inspection

Initial checkout: clean main at the immutable release SHA. Current work uses the focused closure branch. Exactly one registered worktree exists: this normal checkout; no additional Git worktree was registered. All historical local branches below are already merged into local main **except `v2/local-apk-device-specific`**. That branch has local-only ancestry and must be preserved for review, not treated as a merged deletion candidate. The other historical release/feature branches are review candidates only; `main` must remain permanent and the active closure branch is retained.

Complete local branch inventory at review:

- `chore/v2.2-github-sponsors`
- `chore/v2.2-permanent-closure`
- `docs/final-v2.1-editorial-roadmap`
- `docs/v2.1-post-release-closure`
- `feature/200-personal-device-library`
- `feature/211-headless-cli`
- `feature/v2.2-source-aware-custom-layouts`
- `fix/v199-legal-cffi-evidence`
- `main`
- `post-release/v2.0.0-docs`
- `release/v2.2-entry-freshness`
- `release/v2.2-fix-assembly-contract`
- `v2.1/local-apk-file-ops-core`
- `v2.1/quick-filter-spacing`
- `v2/acceptance-polish-2`
- `v2/acceptance-ux-fixes`
- `v2/canonical-screenshots-help`
- `v2/changes-history-polish`
- `v2/connected-device-play-profile`
- `v2/dark-mode-contrast`
- `v2/data-maintenance-polish`
- `v2/device-specific-productization`
- `v2/device-specific-resolver-core`
- `v2/device-specific-resolver-integration`
- `v2/device-specific-resolver-poc`
- `v2/final-file-about-polish`
- `v2/final-freshness-2.2.0`
- `v2/final-help-polish`
- `v2/final-polish-2.0.0`
- `v2/local-apk-device-specific`
- `v2/local-apk-library-ui`
- `v2/local-apk-source-rework`
- `v2/release-macos-bundle-fix-2.0.0`
- `v2/release-macos-pyaxmlparser-resource-fix-2.0.0`
- `v2/release-posix-fixes-2.0.0`
- `v2/release-prep-2.0.0`
- `v2/release-prep-2.2.0`
- `v2/release-workflow-fixes-2.0.0`
- `v2/source-workflow-containers`

Relevant ignored directories reviewed:

- `build/release-git-v2.1.0`, `build/release-work-v2.1.0-2`, `build/v2.1.0-pytest-temp`: old release working copies/test outputs, subject to review for independent changes before removal.
- `build/v2.2-freshness`, `build/v2.2-release-prep`, `build/v2.2-final-freshness`, `build/v2.2-assembly-contract`: historical diagnostics/source logs/archives/test data and isolated Python tooling. Test temp/app-data subdirectories are disposable after closure review; preserve acceptance evidence and the Python environments until this PR's validation finishes.
- `build/v2.2-closure`: this audit's supporting JSON/HTML/logs/tooling, ignored; review after its durable report and post-merge closure are accepted.
- `artifact/rc3-evidence` through `artifact/rc8-evidence`, `artifact/rc7-source-fix`, `artifact/local-evidence`, `artifact/phase-c`: historical acceptance/instrumentation material; preserve anything not yet archived or used by other work.
- `artifact/pytest_*`, `artifact/sponsors-*-temp-*`, Sponsors smoke/test app-data and cache directories: local test-output cleanup candidates after review.
- `.venv`, `dist/release314env`, ordinary compiler/test caches: potentially still useful development environments, not certified disposable by this audit.

No root-level `release-v*-candidate-*` directory was present. No branch, worktree or local temporary directory was deleted, reset, stashed, cleaned or discarded.

## Validation and closure dependency

Local validation on CPython 3.14.8 x64: **54 focused tests passed; full pytest 1661 passed, 9 skipped**, normal exit. Compileall, canonical Quality Ruff scope (0.16.10), Qt offscreen smoke including status preservation, guarded headless CLI smoke, strict legal preflight with Nuitka 4.2.2, pip check and diff whitespace all passed. Syntax validation passed for nine workflow YAMLs, 17 Python helpers, 12 heredoc/33 inline Python blocks and all workflow/helper Bash/PowerShell. Source application behavior is unchanged. No Windows/Linux/macOS Nuitka build, production signing, tag/Release/asset mutation or #212 closure was performed.

The initial sandbox full-suite run hit three PowerShell WindowsApps process-access errors; the native-access rerun passed without changing/skipping those tests. That run reported one pytest cache-directory collision warning while the focused suite used the same cache; it did not fail any test. The final exact PR-head Quality must pass and is recorded in the PR description/control-tower report. Control tower must merge normally (no squash/rebase/auto-merge), require post-merge Quality, synchronize clean local main with fetch/prune and ff-only pull, verify the actual canonical SHA, recheck the public homepage, and only then export the final repository snapshot/handoff and confirm #212/permanent closure. The future merge SHA is not guessed in this document.
