# Store App Audit v2.3 release handoff

Updated **2026-10-05 CEST**. Active cycle: [#225](https://github.com/mrc-labs/PlayStoreAppAudit/issues/225), acceptance/release preparation [#232](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232).

## Published history versus current source

Latest published release is **v2.2.0**, immutable at `21b6646571b7e93044b76fe4d18a04eeec092f18`; annotated tag object `95a402b25f65bf22db58f831076bca747e2c9103`, Release ID `401714084`. Its eight assets and published verification remain unchanged. Its complete closure is recorded in `V2_2_POST_RELEASE_CLOSURE.md`; `HANDOFF_V2.2.md` remains historical.

Current source is **2.3.0**, Windows File/Product **2.3.0.0**, **unpublished** on `v2/release-prep-2.3.0`. This branch is not the frozen release SHA. Starting/Phase A accepted baseline is `ba7bf2268603dd75f95c9906299ba4bed036865b`; [accepted evidence](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-5984807882).

All three pillars are integrated: Category/installer state through PR #227/#228, up to three Named Custom Views per independent source family through PR #229, conservative identical-SHA-256 duplicate review through PR #230. Phase A passed. Keep accepted limitations visible: long named views can clip at minimum width with tooltips; synchronous duplicate revalidation can pause UI; portable final check-to-delete race remains; Windows symlink tests depend on privileges.

## Phase B checkpoint and delivered HEAD

Version/exact-runtime code checkpoint: `1060e98a028856e7d700651819e197cc83ea40fc`. The subsequent current-context/evidence commit completes preparation. The final **exact release-prep HEAD**, local/remote equality, clean state and validation are captured in the generated clean `REPOSITORY_SNAPSHOT.md` and final delivery report. Use that full SHA for review/Quality; do not treat the code checkpoint as final HEAD. This avoids embedding a commit's own unknowable hash into itself.

Fresh entry evidence: [V2_3_RELEASE_ENTRY_FRESHNESS.md](V2_3_RELEASE_ENTRY_FRESHNESS.md). Preparation/validation: [V2_3_RELEASE_PREP.md](V2_3_RELEASE_PREP.md). Public wording: [V2_3_RELEASE_BODY_DRAFT.md](V2_3_RELEASE_BODY_DRAFT.md), with canonical four sections and pending final verification.

Local source gate passed: **1781 pytest passed, 9 skipped**, full Quality Ruff, application/nine-helper compilation, PowerShell syntax and standard Qt offscreen smoke. Focused release checks **81 passed**; focused Help/workflow/Tracks A/B/C **117 passed**. Strict source legal preflight and dependency integrity passed. Exact delivered-head gate and remote equality are recorded by the clean external delivery evidence; remote CI and native candidate acceptance remain pending.

Python 3.14.8 is freshly selected, staged exactly in all 11 setup environments/nine workflows and both native helpers with fail-closed full equality. Matched PySide/Shiboken/Qt 6.11.2 and Nuitka 4.2.2 remain current. No direct dependency/Action pin update was needed; clean mypy dependency resolution now uses ast_serialize 0.12.1. Final freshness remains mandatory immediately before final SHA freeze. Post-release closure restores rolling stable Python 3.14 / `check-latest: true`.

## Next authorized phase

Return control for **control-tower release-prep review**. No PR, merge, tag, release, issue closure or final platform build dispatch was performed in Phase B.

Phase C must review this exact delivered branch SHA, run remote exact-head Quality, merge normally and validate exact post-merge main. Repeat the full final freshness gate, resolve/pin any newly required compatible updates, then freeze one exact full main SHA. Build Windows x64/ARM64, Linux x64/ARM64 and macOS Intel/ARM64 from that same SHA. Validate package contents, architecture, version, startup, provenance, all legal/source material, Linux x64 Ubuntu 22.04 backward smoke, all ELF maxima and actual macOS floors. Entry/source checks are not package acceptance.

Phase D assembles exactly eight engineering assets from accepted same-SHA runs, validates them, tags and publishes accepted existing artifacts, then independently re-downloads and verifies size/SHA-256/byte identity. Windows/Linux remain unsigned; macOS uses ad-hoc engineering signing only, without Developer ID or notarization. #154 production trust and #209 updater remain outside v2.3. A tag must never rebuild binaries.

Phase E follows `RELEASE_CLOSURE.md` and `CI_MAINTENANCE.md`: context review, live public repository/About/homepage/topics/README checks, safe retention, separate read-only local Docker audit, restored rolling development Python, validated clean local VS Code synchronization to expected canonical main SHA, then clean snapshot/handoff. Never reset/stash/discard dirty work. Publishing alone is not closure.

## Watches to reopen at final freshness

- Windows ARM64 vendor OpenSSL 3.6 support ends 2026-11-01; recheck current vcpkg port/integration and applicable advisories before a delayed release.
- Xcode 27 does not preserve Intel support; keep supported shared Xcode 26.6 until a concrete successor preserves both architectures and floors.
- Ubuntu-latest 26.04 rollout begins 2026-10-19; release builders are explicitly 24.04. Hosted Ubuntu 22.04 retirement does not retire intentional supported Jammy compatibility containers.
- Qt 6.12 is newer independently, but the public matched Python bindings remain 6.11.2; do not mix libraries. Recheck parent releases and advisories.
- Vendor-owned Azure signing internals are recorded observations; production signing acceptance is absent and remains #154.
