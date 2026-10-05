# v2.3.0 Phase B release preparation

**Historical Phase B record, superseded for current state.** v2.3.0 is published at `8d476dc5507d8249d8cd62c861095ed3e443f0af`; final freshness, canonical six-platform/assembly acceptance and independent public-byte verification subsequently passed. Phase E restores rolling stable Python 3.14 / `check-latest: true`, preserving exact 3.14.8 release evidence below. [Closure audit](V2_3_POST_RELEASE_CLOSURE.md) records later outcomes and outstanding work. All preparation/pending statements below describe the original audit boundary, not current publication state.

Date: **2026-10-05 CEST**. Tracking: [#225](https://github.com/mrc-labs/PlayStoreAppAudit/issues/225), [#232](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232).

## Source state and scope

- Exact clean starting HEAD: `ba7bf2268603dd75f95c9906299ba4bed036865b`.
- [Phase A acceptance](https://github.com/mrc-labs/PlayStoreAppAudit/issues/232#issuecomment-5984807882) passed on that exact main SHA: all three integrated tracks, native Windows acceptance and the full source gate.
- Work stays on `v2/release-prep-2.3.0`. This review branch is **not a frozen release SHA**.
- Code/toolchain checkpoint: `1060e98a028856e7d700651819e197cc83ea40fc` (`release: prepare v2.3.0 version and exact Python runtime`). Subsequent documentation commit completes Phase B. The exact delivered HEAD is recorded by the clean export and final handoff, avoiding a self-referential commit hash.
- Scope: canonical Play Store Category (#188), up to three Named Custom Views per source family (#147), conservative Local APK Duplicate review/cleanup (#224). #154 and #209 remain deferred.

## Version ownership and historical integrity

Canonical owners are `playstore_app_audit/__init__.py::__version__` and `pyproject.toml::project.version`, both **2.3.0**. `tests/test_version.py` and `tests/test_release_legal_preflight.py` current-version expectations match them. `tests/test_workflows.py` now requires exact Quality 3.14.8/stable checks, and `tests/test_canonical_help_assets.py` requires the historical v2.1 gallery plus current unpublished 2.3/published 2.2 wording and the rendered `{category}` placeholder.

Qt application/About, CLI version, diagnostics, release filenames, BUILD-INFO and packaging helpers derive from canonical version ownership. `.github/scripts/build_windows_standalone.ps1` derives the Windows File/Product value as `$AppVersion.0`, now **2.3.0.0**; no independent version literal was introduced.

Remaining 2.2.0 references are published/historical evidence or deliberately synthetic generic fixtures (`test_final_file_about_polish.py`, `test_release_assembler_workflow.py`). Latest published release remains v2.2.0. Its release SHA, annotated tag, Release ID, assets, sizes, hashes, CI IDs, release-note body, v2.2 changelog entry, `V2_2_*` records and `HANDOFF_V2.2.md` are preserved. Current-facing README, Help, AGENTS, Project Status, Roadmap, Building and duplicate integration context distinguish historical 2.2 integration from current unpublished 2.3 preparation.

## Freshness and exact runtime preparation

The [fresh entry audit](V2_3_RELEASE_ENTRY_FRESHNESS.md) checked primary upstream sources, hosted availability, all directly maintained Actions, the complete fresh Python environment, parent bundles, native prerequisites, vendor support, advisories and announcements.

Python **3.14.8** is freshly confirmed as the latest stable compatible 3.14 patch and hosted for all six targets, including the same-patch Ubuntu 22.04 x64 compatibility distribution. PySide/Shiboken/Qt **6.11.2**, Nuitka **4.2.2** and all direct dependency/Action pins remain current. The clean resolver selects **ast_serialize 0.12.1**, a mypy development dependency; no repository dependency pin or product runtime requirement was added.

All **11 setup environments across nine workflows** stage exact `3.14.8`, disable rolling `check-latest`, and fail closed on full version plus stable release level before use: Quality, Windows, Linux, macOS, both assemblers, Windows signing infrastructure, UI style audit and Actions retention. Windows native helper additionally preserves standard-GIL/64-bit/native-architecture checks. Linux x64 sysroot requires exact 3.14.8, downloads that official Ubuntu 22.04 distribution with upstream digest/size verification, and checks equality after installation.

The entry audit does not itself freeze release pins under the permanent policy. Staging these pins is the separate explicitly authorized Phase B preparation step. Repeat the **entire** final freshness gate immediately before final exact-main-SHA freeze; a newer compatible component then requires update and affected validation. Phase E restores rolling stable `3.14` / `check-latest: true`, updates guards/tests/context, validates and safely synchronizes the local checkout.

## Validation

Fresh isolated Windows x64 environment: Python 3.14.8, PySide6/Qt 6.11.2; user settings and existing venv are untouched.

- Focused version, workflow, asset-layout, assembler, legal/source and Linux ABI checks: **81 passed**.
- Strict release-legal preflight against the fresh environment: **PASS**, reporting project 2.3.0 and the audited toolchain. This is source preflight, not final packaged compliance.
- Focused Help/workflow and Tracks A/B/C regressions: **117 passed**.
- Full pytest after correcting those legitimate Help/workflow expectations: **1781 passed, 9 skipped** (136.98 seconds), with no weakened checks.
- Full Quality Ruff scope (application, tests, main and all nine listed helpers): **PASS**.
- Application compileall, all nine Quality Python helper compilations, PowerShell export-helper parser: **PASS**.
- Standard Qt offscreen smoke, including status preservation on presentation changes: **PASS**.
- Dependency integrity: `pip check` **PASS**, fresh selected `pip list --outdated` **[]**.
- Historical integrity: 11 complete historical/operational files, published v2.2 context blocks, the entire v2.2-and-older changelog suffix, local annotated tag object and peeled release target are unchanged against the starting baseline. Draft headings, all eight expected asset names and new local documentation links passed structural verification.

The completed pre-commit gate is recorded here; the same complete gate is repeated on the delivered clean commit, with exact HEAD/log evidence in the external clean export/final delivery report. Remote exact-head Quality remains a control-tower gate, not a claimed CI result.

## Release work planned at the Phase B checkpoint (historical)

**Phase C:** control-tower review/PR, exact-head Quality, normal merge and post-merge Quality; repeat final freshness, verify exact Python selection and freeze one full main SHA. Build and accept all six same-SHA candidates, with architecture/version/startup/provenance/legal/source and actual binary compatibility evidence. Recheck the ast_serialize development resolution as part of clean platform environment validation.

**Phase D:** same-SHA engineering assembly through `assemble-release.yml`, exactly eight assets; accepted artifact checksums and manual/package checks; annotated tag and publication only after acceptance; independent public re-download, size/hash/byte-identity verification. Windows/Linux stay unsigned, macOS ad-hoc only. No production signing/notarization claim.

**Phase E:** permanent closure in `RELEASE_CLOSURE.md`: reconcile maintained context and live GitHub About/homepage/topics/rendered README; retention policy; read-only local Docker inventory, no ambiguous/shared deletion; restore rolling development Python; clean local VS Code `status`, `fetch --prune`, switch main, `pull --ff-only`, verify expected canonical SHA; generate snapshot/handoff only from clean synchronized state.

Phase B created **no tag, GitHub Release, final platform build dispatch, merge, PR or issue closure**.
