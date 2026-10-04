# Session-local duplicate APK review

Track C implements the locked [issue #224 contract](https://github.com/mrc-labs/PlayStoreAppAudit/issues/224#issuecomment-5981962164) on `feature/v2.3-duplicate-apk-management`, based on `19884ab557b145d52fb18455c8e5bf2988b39dfe`. Source version remains 2.2.0. This is development work awaiting control-tower review and exact-SHA CI, not a published release claim.

## Review and identity

`File > Local APK(s) > Review Duplicates…` follows Mass Rename and precedes the separator for Remove All Outdated/Unknown. It is enabled only for an idle active Local APK source with useful current-row findings. Availability performs no file hashing.

The review has two tabs:

- **Exact Duplicates:** at least two distinct canonical, platform-normalized physical paths in the active candidates with the same valid 64-hex `local_apk_sha256`. Package ID and version do not participate in exact identity. SHA hex case is normalized. Repeated or conflicting evidence for one physical path cannot create extra copies. Rows are never collapsed.
- **Variants / Versions:** read-only Same Version Variant findings require one package and an exact stored local version tuple with different valid hashes. Multiple Versions reports distinct local version tuples for one package. The tuple preserves version code, long version code and version name exactly where available; wholly missing/invalid version evidence is not guessed. Store version, age and ordering do not authorize cleanup.

Each physical file has its own path, filename, package/app context and local version. Full hashes and paths are available in cell tooltips. Selection defaults to none. Selecting every member of any affected group disables removal. The variants tab has no checkboxes and disables the global removal button.

The removal button accepts a review plan, followed by a separate permanent-deletion confirmation defaulting to No. Cancel, close and declining confirmation perform no mutation.

## Service and execution

`services/local_apk_duplicates.py` is Qt-independent. Frozen dataclasses separate discovery, preview evidence, selected paths, keeper paths, the cleanup plan and deterministic per-file results. The dialog snapshots metadata before selection; subsequent selection changes do not refresh stale evidence. Selection uses the frozen displayed paths so resolving a changed path cannot silently select a different copy.

Execution validates plan structure and distinct paths again. Before the first mutation in a group, every selected file and every preview keeper must still resolve to the frozen physical path, exist as a supported package file, retain preview device/inode/size/mtime evidence and pass SHA-256 recomputation from current bytes. SHA-256 is mandatory even when metadata matches. A stale group is blocked before any selected copy is removed. Independent safe groups can continue.

Before each individual removal, keeper files and the selected file are hashed again. A final path/metadata check catches ordinary changes while another member was being hashed. The service calls only `local_apk_file_ops.remove_local_package_file()` for deletion. A deletion failure stops further removals in that group; independent groups remain eligible. Results distinguish removed, blocked/stale and failed.

The cleanup service never selects keeper paths for deletion. It requires all preview keepers to remain valid, which is deliberately more conservative than accepting a substitute. The ordinary single-file Remove action remains separate and can explicitly remove a final file.

MainWindow shares `_sync_local_apk_removed_paths()` with Mass Remove and uses `_sync_local_apk_file_mutation_views()`. Only successful physical deletions remove rows/candidates; failed and unrelated rows remain, with source label, model, selection, details and action availability refreshed without another Store audit.

## Practical limits and validation

External writers cannot be transactionally locked through the existing portable path-based deletion primitive. Rehashing and final metadata checks minimize the check-to-delete interval; concurrent external replacement or deletion in that final interval remains an operating-system race. Review and cleanup should run while the package files are stable. No watcher, background cleanup policy or persistent library state is introduced.

Execution is synchronous like the existing mass-file mutation workflows. Large files or many selected copies can pause the UI while current bytes are repeatedly verified. There is no automatic removal, historical-version policy, Store-based duplicate policy, version bump, dependency/toolchain change, updater or signing work.

Focused service/UI tests cover identity, source membership, missing evidence, empty/all/N-1 selections, cancellation, path retargeting, replaced/changed/missing selected and keeper files, current-byte mismatches, changes during hashing, independent partial execution, canonical helper failures and physical-row reconciliation. Existing Local APK mutation and transient same-SHA/distinct-path tests are retained. Native Windows Qt dialog rendering is checked at 1100x600 and the 780x420 minimum; both tabs remain available with tooltips for long evidence.

Local validation on 2026-10-04, using existing Python 3.14.8 / PySide6 6.11.2:

- Focused duplicate service/UI tests: **56 passed**.
- Existing Mass Rename, Mass Remove, physical file operations and transient Local APK tests: **117 passed, 2 skipped**.
- Full pytest: **1780 passed, 9 skipped**. Tests use isolated repository-local app data, a fresh repository-local pytest temporary directory and no pytest cache. The complete final run executes outside the sandbox to allow the installed Windows PowerShell application alias; no tests or dependencies were disabled or changed for environment limitations.
- Duplicate UI tests with the native Windows Qt plugin: **15 passed**, plus visual inspection of native renders for both tabs.
- Quality Ruff scope, application compileall, all nine Quality Python helper compilations, PowerShell handoff-helper syntax and the standard Qt offscreen smoke: **passed**.

Exact-SHA GitHub CI gating and control-tower review remain pending; no release, tag, merge, issue closure or PR is performed by this implementation task.
