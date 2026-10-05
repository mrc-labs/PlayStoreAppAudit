# Store App Audit v2.3 publication and Phase E handoff

Updated **2026-10-05 CEST**. #225 and #232 remain open for independent Control Tower closure review. This tracked context is not a generated checkout/snapshot export.

## Immutable release versus development

Published **v2.3.0** on **2026-10-05**, immutable at `8d476dc5507d8249d8cd62c861095ed3e443f0af`; annotated tag object `ee386624680b8608a98fb13da5f51bdff736d1e9`, Release ID `403687278`. Exactly eight accepted Windows/Linux/macOS x64/ARM64 ZIP/source/checksum assets are published. Windows/Linux are unsigned; macOS is engineering ad-hoc only, without Developer ID or notarization. [Independent public-byte verification](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-5995051051) passed. Source remains **2.3.0** / Windows **2.3.0.0**. Phase E restores rolling stable Python `3.14` / `check-latest: true` on `chore/v2.3-closure`. Its forthcoming development SHA is separate from the immutable release SHA. Control Tower review, normal merge, post-merge Quality/rendered-main README checks and safe local synchronization remain pending. See [closure audit](V2_3_POST_RELEASE_CLOSURE.md).

Published at 2026-10-05T12:44:51Z. Published toolchain: exact Python **3.14.8**, matched PySide/Shiboken/Qt **6.11.2**, Nuitka **4.2.2**. GitHub reports `immutable: false`; project policy still forbids rebuild/retag/asset replacement.

All three pillars shipped: #188 Category/installer state (PR #227/#228), #147 up to three Named Custom Views per independent source family (PR #229), #224 conservative identical-SHA-256 duplicate review (PR #230). Phase A accepted `ba7bf2268603dd75f95c9906299ba4bed036865b`. Historical Phase B [preparation](V2_3_RELEASE_PREP.md)/[entry freshness](V2_3_RELEASE_ENTRY_FRESHNESS.md) remain preserved. Practical limits: long view names can clip with tooltips; synchronous duplicate revalidation may pause UI; the portable final check-to-delete race remains; Windows symlink tests depend on privileges. Published Help retains preparation-time wording because product code/assets remain unchanged.

## Accepted release evidence

| Gate | Canonical run | Acceptance |
| --- | --- | --- |
| Quality #680 | [37241775290](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37241775290) | SUCCESS, 1790 tests |
| Windows x64/ARM64 | [37246646085](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37246646085) | SUCCESS |
| Linux x64/ARM64 | [37246681845](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37246681845) | SUCCESS, both compatibility reports retained |
| macOS Intel/ARM64 | [37246726056](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37246726056) | SUCCESS, accepted attempt 2 after upload retry |
| Assembly | [37260955813](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37260955813) | SUCCESS, artifact `11324630974` |

All resolve to the exact immutable release SHA. Six-platform package/startup/architecture/version/provenance/legal/source acceptance and independent public-byte verification passed. Linux x64 Ubuntu 22.04 offscreen/xcb GUI and CLI smoke passed; ELF maxima x64 GLIBC 2.35 / GLIBCXX 3.4.29, ARM64 2.38 / 3.4.32. macOS bundled metadata maxima Intel 26.0 / ARM64 15.0 differ from main-executable settings 10.15/11.0; tested hosts 26.6.1/26.6.2 establish no older-OS runtime acceptance. Publication used local authenticated CLI, with no publication Actions run ID or tag-triggered rebuild.

## Phase E and next authorized step

[Closure audit](V2_3_POST_RELEASE_CLOSURE.md) records unchanged retention run `37348726683`, before/after **37 artifacts / 4,548,500,908 bytes**, all nine canonical artifacts, correct live metadata, stale default-main README awaiting merge, preserved local material and unavailable Docker daemon. Development restores stable `3.14` / `check-latest: true` in 11 setup environments/nine workflows plus matching guards/tests/native helpers. Stable/final, GIL, architecture, security and same-resolved-patch checks remain. Dependency pins, product code, source/Windows version and release assets remain unchanged. Every future freeze requires complete freshness and one exact audited full patch again.

The closure PR's exact head and exact-head Quality result belong in the PR/final delivery report, not a self-referential hash in this commit. Stop for **independent Control Tower review**. Do not merge, enable auto-merge or close #225/#232. After normal merge, verify exact post-merge Quality, recheck rendered default-main README/live metadata, repeat Docker resource inspection when its daemon is available, then follow `RELEASE_CLOSURE.md`: clean status, fetch --prune, switch main, pull --ff-only, verify clean canonical HEAD. Never reset/stash/discard unexpected work. Generate a snapshot/handoff only from that synchronized state if requested. Final closure remains pending.

Historical v2.2 release/closure and `HANDOFF_V2.2.md` remain unchanged. #154 production signing/notarization and #209 updater/self-update remain deferred; no next product milestone is assigned here. Dated entry-audit watches remain future rechecks: matched Qt bindings, vendor OpenSSL support, Intel/ARM64 Xcode successor, runner labels and vendor signing integrations. They do not authorize rebuilding published v2.3.
