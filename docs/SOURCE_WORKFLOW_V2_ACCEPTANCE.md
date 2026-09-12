# v2 Source Workflow Acceptance

This branch follows the merged Windows acceptance work in PR #141.

## User-facing goals

- Local package source accepts standalone `.apk` plus installable archive containers `.apks`, `.apkm`, and `.xapk`. `.aab` remains out of scope.
- Local package selection is presented as one source control with clear `File(s)…` and `Folder…` choices.
- Establishing a valid source starts the first audit automatically. The Run action remains available for an explicit rerun / force-refresh workflow.
- Source-side evidence should become visible progressively instead of leaving the results table empty during long parsing / Store lookup work. Fields that are not authoritative yet must be shown as pending/empty and must not be exported as final evidence while the audit is still running.
- Healthy Store cache TTL defaults to 24 hours.
- Legacy saved `72` from the previous default migrates once to 24 hours; a later deliberate user choice of 72 hours must be preserved.
- Reading a healthy cache hit must never refresh `fetched_at` or otherwise turn the TTL into a sliding window.

## Container safety and identity

- Treat `.apks`, `.apkm`, and `.xapk` as ZIP-like containers, never as plain APK files.
- Inspect archives defensively: reject traversal/absolute paths and suspicious archives; enforce bounded entry count, extracted size, and compression ratio.
- Use temporary extraction only and clean it on success, failure, cancellation, and window close.
- Select the base APK / relevant manifest evidence deterministically. Do not pretend every split is an independent app.
- Preserve one result row per physical selected container/location.
- Store lookup remains package-deduplicated.
- Local path, hashes, archive contents, split names, and other local evidence remain local-only. Only package identity may be used for Store lookup.
- Existing standalone `.apk` behavior must remain unchanged.

## Lifecycle

- Source selection, parsing, Store lookup, Pause/Resume/Stop, cancellation, and finalization must preserve the existing cooperative lifecycle. No `QThread.terminate` or equivalent hard termination.
- Progressive rows are provisional UI state only. Stopped/failed/abandoned audits must keep the existing rules around cache/history/Device Inventory promotion.
- Do not enable final export while provisional rows are still incomplete.

## Scope exclusions

Do not include the application version bump, `health_score` to `maintenance_score` internal migration, Help feedback link, ETB cleanup, Nuitka/packaging, or non-Windows release work in this PR.
