# v2 Data Maintenance acceptance

This document locks the owner acceptance contract for the post-#142 Data Maintenance polish tracked by issue #143.

## Scope

This pass makes destructive local-data actions understandable and keeps per-run refresh behavior clearly separate from deletion.

It does not change Store evidence semantics, Maintenance Score, cache TTLs, audit lifecycle, source handling, packaging, signing, release assets, or the application version.

## Tools > Data Maintenance…

Replace the current `Tools > Data Maintenance` submenu with one action:

`Data Maintenance…`

Opening it shows one small native Qt dialog with two visually separate sections: **Cached data** and **History**.

The top-level Data Maintenance action and destructive controls are available only while the application is idle. Do not allow a cache/history clear to race an active audit, finalization, source scan, icon download generation, or export.

### Cached data

Expose these three independent rows, each with a short explanation and an individual **Clear…** action.

1. **Store Results Cache**
   - Healthy reusable Google Play audit results only.
   - Default healthy-result TTL remains 24 hours.
   - Clearing it does not clear current results, settings, previous-audit history, device inventory history, Device Snapshots, icon cache, or alternative-store cache.

2. **App Icon Cache**
   - Downloaded Store artwork only.
   - Clear both persistent disk state and the active loader's relevant in-memory state consistently.
   - Retire queued/stale icon work so an old disk/network completion cannot repopulate the just-cleared cache.
   - Clearing it must not change audit evidence, Store status, relationship status, Maintenance Score, current result rows, settings, or histories.
   - Existing icon loading remains bounded and asynchronous after the clear.

3. **Alternative Store Cache**
   - F-Droid/Aptoide provider-result evidence cache only.
   - Clearing it does not clear Google Play results, app icons, current results, settings, or histories.

Also provide **Clear All Caches…** inside the Cached data section.

`Clear All Caches…` clears exactly:
- Store Results Cache;
- App Icon Cache;
- Alternative Store Cache.

It must never clear:
- Previous Audit History;
- Device Inventory History;
- Device Snapshots;
- settings;
- current results;
- source selection;
- saved Smart Queries or view configuration.

### History

Expose these two independent rows with their existing destructive semantics and explicit confirmation.

4. **Previous Audit History**
   - The baseline used for previous-audit comparisons.
   - Clearing it does not clear caches, settings, current results, Device Inventory History, or Device Snapshots.

5. **Device Inventory History**
   - Per-device baseline used by Device Inventory Changes.
   - Explicit Device Snapshots are a separate user-created feature and must remain untouched.
   - Clearing it does not clear caches, settings, current results, or Previous Audit History.

There is no `Clear All Data` action and no action that combines cache deletion with history deletion.

## Confirmation and result copy

Every destructive action requires a confirmation dialog with **No/Cancel as the safe default**.

Confirmation copy must say what will be deleted and name the important data that will not be deleted. Avoid vague wording such as `Clear local data?`.

After a successful clear, show a concise operational-status message identifying exactly what was cleared. Failure must be surfaced rather than reported as success.

Suggested intent-level copy:

- Store Results Cache: `Delete cached healthy Google Play results? Current results, history and settings will not be deleted.`
- App Icon Cache: `Delete downloaded app icons from memory and disk? Audit evidence, scores, history and settings will not be changed.`
- Alternative Store Cache: `Delete cached F-Droid/Aptoide lookup results? Google Play results, history and settings will not be deleted.`
- Clear All Caches: `Delete Store results, app icons and alternative-store caches? History, Device Snapshots, settings and current results will not be deleted.`
- Previous Audit History: preserve the existing meaning that the next successful comparison run creates a new baseline.
- Device Inventory History: explicitly say Device Snapshots will not be deleted.

Exact prose may be polished during implementation, but the scope statements above are mandatory.

## Audit refresh action

Keep the refresh action under **Audit**, not Data Maintenance.

Rename the current `Force Full Refresh` action to:

`Run with Fresh Store Results`

Tooltip/help text:

`Ignore cached Google Play and alternative-store results for this run. No cache files are deleted; app icons may still come from the icon cache.`

Semantics remain exactly the post-#142 behavior:
- bypass reusable healthy Google Play result cache for that run;
- force eligible alternative-distribution checks live for that run;
- do not delete either result cache before the run;
- do not delete or bypass the App Icon Cache;
- completed live Store/provider evidence may reconcile/update its exact result-cache entries normally;
- transient/inconclusive live Store evidence does not destroy an older healthy Store result;
- stopped/failed runs do not globally clear unrelated cache state.

The action remains an execution command, not a maintenance command.

## Implementation boundaries

Prefer explicit service-level clear primitives for each persistent cache rather than UI code manipulating files directly.

The App Icon clear path must coordinate with `AppIconLoader`; deleting the icon directory alone is insufficient because the loader has bounded RAM state, pending work, a disk worker queue and active network replies.

Do not clear current table rows as a side effect. A user may clear caches while looking at completed results; those rows remain the evidence from the completed run until the next audit or explicit `Clear Results`.

Do not change the existing 45-day Store-cache storage pruning introduced before this polish.

Do not change alternative-provider TTLs or begin caching new Store-status classes.

## Required regression coverage

Cover at minimum:

1. Individual Store Results Cache clear touches only that cache.
2. Individual App Icon Cache clear retires in-memory/pending generation state and persistent disk state without changing audit rows/evidence.
3. Individual Alternative Store Cache clear touches only provider cache state.
4. `Clear All Caches…` clears exactly the three caches and preserves settings, current results, Previous Audit History, Device Inventory History and Device Snapshots.
5. Previous Audit History clear preserves both caches and Device Inventory/Device Snapshots.
6. Device Inventory History clear preserves Device Snapshots and other stores.
7. Confirmation dialogs default safely to No/Cancel and accurately describe scope.
8. Data Maintenance destructive actions are disabled/not executable while an audit or other incompatible operation is active.
9. `Run with Fresh Store Results` bypasses Google Play and alternative-provider result caches without deleting them.
10. The same refresh still allows App Icon Cache reuse.
11. Post-#142 exact-key Store cache reconciliation, 24-hour default TTL, non-sliding `fetched_at`, and 45-day storage pruning remain unchanged.

## Explicitly out of scope

Do not mix this PR with:
- `.aab` support;
- app version bump;
- `health_score` -> `maintenance_score` internal compatibility migration;
- Help feedback link;
- ETB/history wording cleanup;
- parser/container work;
- Nuitka/packaging;
- signing;
- release assets/tags;
- non-Windows release work.
