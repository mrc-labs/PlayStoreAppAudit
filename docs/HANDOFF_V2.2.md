# Store App Audit v2.2.0 — published release / post-release continuation

Last updated: 2026-10-02 CEST. This is the current continuation handoff until a later release-cycle handoff is approved. Historical preparation, diagnostic and retired-freeze records are evidence, not current candidate instructions.

## Immutable published release

v2.2.0 was published on **2026-10-02** as [Store App Audit v2.2.0](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v2.2.0) and is immutable at source SHA `21b6646571b7e93044b76fe4d18a04eeec092f18`. Annotated tag `v2.2.0` has object `95a402b25f65bf22db58f831076bca747e2c9103`; GitHub Release ID is `401714084`.

The release shipped source-aware independent **Custom (Phone / App List)** and **Custom (Local APK)** layouts, the persistent privacy-safe **Personal Device profile library**, and **CLI/headless audit mode**, plus discreet GitHub Sponsors integration. Arbitrary Named Custom Views #147, production signing/notarization #154 and safe update/self-update #209 remain deferred; no v2.3 scope is assigned.

All six packages use exact stable Python **3.14.8**, PySide/Shiboken/Qt **6.11.2** and Nuitka **4.2.2**. Linux x64/ARM64 build hosts are Ubuntu **24.04**; x64 passed Ubuntu **22.04** packaged offscreen/xcb GUI and CLI backward smoke, with all-ELF maxima GLIBC 2.35 / GLIBCXX 3.4.29 (ARM64 2.38 / 3.4.32). macOS uses macOS 26 / Xcode 26.6. Windows/Linux are unsigned; macOS is engineering ad-hoc signed only, without Developer ID signing or notarization.

Canonical evidence, all **attempt 1 / SUCCESS / exact release SHA**:

| Gate | Run |
| --- | --- |
| Quality #637 | [36987000922](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36987000922) |
| Windows #150, x64 + ARM64 | [36988301118](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36988301118) |
| Linux #18, x64 + ARM64 | [36988304138](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36988304138) |
| macOS #15, Intel + Apple Silicon | [36988307201](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36988307201) |
| Assembly #2 | [36993205418](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36993205418) |

Exactly eight public assets were independently re-downloaded: six platform ZIPs, one consolidated third-party source archive and `SHA256SUMS.txt`. Names, byte sizes, SHA-256 and byte-for-byte identity against accepted assembly files passed. The public checksum file verified all seven payloads. Published source, tag and assets must never be rebuilt, retagged or replaced.


The actual published body, including its Sponsors footer, is recorded in [RELEASE_NOTES.md](RELEASE_NOTES.md#published-v220-release-body). The former [draft](V2_2_RELEASE_BODY_DRAFT.md) is clearly superseded. Full public asset names, sizes and hashes are in [PROJECT_STATUS.md](PROJECT_STATUS.md#published-v220-release).

## Current development baseline and closure state

Source/package version remains **2.2.0** (Windows File/Product **2.2.0.0**). This closure PR restores stable rolling Python `3.14` with `check-latest: true` in all 11 setup environments across nine workflows, with fail-closed stable major/minor guards and full-version logging. The Windows helper keeps its standard-GIL/64-bit/native architecture protections; the Linux x64 helper dynamically selects the official Ubuntu 22.04 distribution of the exact patch resolved by setup-python and verifies equality after installation. `requires-python >=3.14` is unchanged; Python 3.15 is not adopted.

Immediately before every future frozen release SHA, final freshness must replace rolling selectors with one audited exact full Python patch and full-version equality again. The v2.2 release's exact 3.14.8 evidence remains historical and unchanged.

Issue [#212](https://github.com/mrc-labs/PlayStoreAppAudit/issues/212) remains open until control-tower normal merge, successful post-merge Quality, safe local synchronization and final closure confirmation. The closure PR must stay draft without auto-merge; no squash/rebase. Its future merge SHA is not known yet. Immutable release history remains at the release SHA above; post-release `main` will advance only when this focused PR is merged. Do not generate `REPOSITORY_SNAPSHOT.md` or the final handoff export before that merge and clean synchronization.


PySide6-Essentials/Shiboken/Qt 6.11.2, Nuitka 4.2.2, Ruff 0.16.10 and mypy 2.4.0 remain current pins. Rust 1.99.0 remains in native Windows ARM64/macOS Intel cryptography source builds. Do not adopt preview successors, Ubuntu 26.04 or Xcode 27 preview through housekeeping. Required Ubuntu vendor OpenSSL security floors remain fail-closed.

## Shipped product contracts to preserve

- Two independent versioned Custom families persist columns/order/widths. Phone/App List share one family; source applicability and contextual overlays never rewrite either user-owned layout. Valid legacy single-Custom state migrates conservatively once.
- Personal Device persistence is explicit opt-in. Multiple saved profiles work offline, with rename/delete/confirmed refresh and random record/cache-revision IDs; allowlisted safe context excludes raw ADB serials, durable device-correlation hashes, Android/GSF/IMEI/SIM identifiers, account identities, bearer tokens, cookies and check-in IDs. Built-in references and transient capture remain separate. Unknown future-schema bytes and unavailable saved selections survive unrelated settings saves.
- CLI `audit app-list|apk-files|apk-folder|phone` reuses canonical services without Qt/UI imports, does not persist overrides/history, exports canonical JSON/CSV and cancels cooperatively. Packaged invocation uses the existing binary's explicit `cli` dispatch before Qt import.
- Raw public Store evidence remains authoritative; Device Specific evidence is additive. Different installed/store versions do not automatically mean outdated, regional absence does not prove global removal, and `datePublished` is never a latest-update date.

## Engineering and release invariants

- `main` is the only permanent branch; short-lived branches use normal PR merge commits, no squash/rebase.
- Published source/tag/assets are immutable; all future final candidates use one exact frozen SHA after Quality. Tag pushes never rebuild binaries.
- Keep all six architectures, explicit target/provenance guards and strict legal/source acceptance. Production trust requires separately validated credentials/provider eligibility under #154.
- Qt Widgets uses platform/default QStyle; keep Basic compact, technical settings behind Tools, presentation actions from overwriting operational status, and Details Auto/Right/Below/Hidden. Do not introduce QDockWidget or broad structural/UI rewrites.
- ADB remains read-only for installed applications. Stop/Cancel is cooperative; never force thread termination. Keep Store parsing/persistence/device/OS work outside UI code and avoid runtime monkey-patching.
- Maintenance Score remains a heuristic with internal compatibility key `health_score`; a full identifier migration is separate unassigned work.
- Normal changes use source Quality; expensive Nuitka builds need an actual package-evidence reason. This closure performs no package build.

## Deferred work

#147 arbitrary Named Custom Views, #154 production signing/notarization and #209 safe update/self-update remain outside v2.2. Duplicate APK management, custom integrations, Windows Explorer integration, richer dashboards and watchlists/background monitoring remain deferred or rejected as documented in [ROADMAP.md](ROADMAP.md). No arbitrary v2.3 milestone is assigned and source version is not bumped just to resume development.

## Actions and local hygiene

See [the closure audit](V2_2_POST_RELEASE_CLOSURE.md) and [CI maintenance snapshot](CI_MAINTENANCE.md#v220-closure-snapshot) for retained final artifacts, older diagnostics, measured Actions storage and reviewed local branches/directories. Three retired-freeze runs were safely removed; canonical final runs and all public release assets remain unchanged. Live GitHub About uses Store App Audit; homepage is empty and topics are unchanged.

Docker CLI is installed but Docker Desktop's Linux daemon is stopped. Inventory commands cannot enumerate images/containers/volumes/cache; no cleanup candidate can yet be certified and nothing was deleted or pruned. Docker is not needed for normal local source development. Intentional CI `ubuntu:22.04` sysroot/probe/backward smoke remains required despite Ubuntu 24.04 build hosts.

## Continuation instructions

1. Review the focused draft closure PR and its exact-head passing Quality. Control tower alone merges normally and confirms #212 closure; no auto-merge.
2. After merge, require post-merge Quality. Run `git status --short` before synchronization; if dirty, stop without reset/stash/discard.
3. From a clean checkout, `git fetch --prune origin`, switch to `main`, and `git pull --ff-only origin main`. Verify clean HEAD equals the actual canonical post-release merge/documentation SHA and verify the unchanged v2.2 tag.
4. Verify live GitHub About and rendered README against the merged published-v2.2 context. When Docker is running, repeat the read-only inventory and let control tower review individual cleanup candidates; review merged local branches/ignored working directories separately.
5. Only then run `scripts/export_chat_handoff.ps1` to generate `REPOSITORY_SNAPSHOT.md` and the final continuation export. Do not describe publication alone or this unmerged PR as permanent closure.
