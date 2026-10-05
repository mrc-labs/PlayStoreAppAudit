# Store App Audit v2.3 publication and Phase E handoff

Updated **2026-10-06 CEST**. #225 and #232 remain open for independent Control Tower closure review. This tracked context is not a generated checkout/snapshot export.

## Immutable release versus development

Published **v2.3.0** remains immutable at `8d476dc5507d8249d8cd62c861095ed3e443f0af`; annotated tag object `ee386624680b8608a98fb13da5f51bdff736d1e9`, Release ID `403687278`. Source stays **2.3.0** / Windows **2.3.0.0**; Windows/Linux are unsigned and macOS is engineering ad-hoc only, without Developer ID or notarization. PR [#234](https://github.com/mrc-labs/PlayStoreAppAudit/pull/234) merged normally to post-release `main` **`19e2f14644000f9fbc11f1f7052fb16438692257`**, restoring rolling stable Python `3.14` / `check-latest: true`. Quality [#682 / 37387525994](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/37387525994) passed there with **1791 tests**. [Control Tower ledger](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-6005262111) confirms the public README/metadata and unchanged release identity. The real local checkout was safely synchronized clean to that main on **2026-10-06 CEST**; read-only Docker inventory then succeeded with shared DDEV resources preserved. The focused `docs/v2.3-final-closure` follow-up still requires independent review, normal merge, post-merge checks and the final clean local synchronization. #225/#232 remain open; final signoff belongs in their ledgers. See [closure audit](V2_3_POST_RELEASE_CLOSURE.md).

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

[Closure audit](V2_3_POST_RELEASE_CLOSURE.md) preserves the 2026-10-05 retention snapshot (`37348726683`, 37 artifacts / 4,548,500,908 bytes, nine canonical artifacts). PR #234 completed the rolling Python restoration and public README reconciliation; post-merge Quality #682 passed. Local checkout synchronized clean to `19e2f14644000f9fbc11f1f7052fb16438692257`. Docker Desktop was started normally and all eight read-only inventory commands succeeded: four stopped DDEV containers, nine images, five volumes, 78 shared cache records / 1.152 GB; no Ubuntu tags or dangling images. All resources, unmerged `v2/local-apk-device-specific`, environments and release staging are preserved. Stable/final, GIL, architecture, security and same-resolved-patch checks remain unchanged; future freezes still require one exact audited full Python patch.

PR #234 is already reviewed and normally merged, with exact post-merge Quality/public README/identity PASS in the [Control Tower ledger](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-6005262111). The new `docs/v2.3-final-closure` PR is a focused documentation follow-up from `19e2f14644000f9fbc11f1f7052fb16438692257`. Its exact head, local consistency checks and Quality result belong in the PR/delivery report. Stop for independent review; do not merge, enable auto-merge or close #225/#232. After its approved normal merge, verify the resulting canonical main/post-merge Quality/public context, then safely synchronize the clean real checkout and verify exact HEAD under `RELEASE_CLOSURE.md`. Do not reset/stash/discard unexpected work. No handoff/export or generated command Markdown is authorized in this task. Final signoff remains in the issue ledgers; this follow-up does not predeclare its review, merge or final synchronization complete.

Historical v2.2 release/closure and `HANDOFF_V2.2.md` remain unchanged. #154 production signing/notarization and #209 updater/self-update remain deferred; no next product milestone is assigned here. Dated entry-audit watches remain future rechecks: matched Qt bindings, vendor OpenSSL support, Intel/ARM64 Xcode successor, runner labels and vendor signing integrations. They do not authorize rebuilding published v2.3.
