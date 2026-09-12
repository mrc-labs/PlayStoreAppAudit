# v2 Changes & History acceptance

This document locks the owner acceptance contract for issue #145 and the post-#144 v2 UX simplification pass.

## Product goal

Play Store App Audit has three distinct longitudinal features:

1. previous Play Store audit comparison;
2. per-device inventory comparison;
3. explicit Device Snapshots.

They remain separate backends, but the ordinary UI must present them as one optional advanced capability instead of several overlapping menu trees.

## Master feature gate

Keep one persisted automatic-tracking master setting:

`changes_history_enabled`

User-facing label:

**Enable automatic change tracking**

Fresh-install default: **Off**.

When Off:
- the final `Tools > Changes & History…` action remains visible as the canonical configuration, review and snapshot surface;
- no previous-Store-audit comparison is performed or promoted;
- no per-device inventory-history comparison is performed or promoted;
- no history-derived row annotations are shown;
- explicit Device Snapshot files and all retained history files are preserved;
- manual Device Snapshot actions remain available when their normal current-device/result prerequisites are met;
- Data Maintenance may still clear retained Previous Audit History or Device Inventory History explicitly;
- Store cache, alternative-store cache, icon cache, Maintenance Score, Local APK, exports and source behavior are unchanged.

When On:
- child tracking settings control automatic Store and device history independently;
- manual Device Snapshot actions remain independent from automatic tracking.

Disabling the master gate must never delete history or snapshots.

## Existing compatibility settings

Keep the established backend keys unless a narrow compatibility wrapper is clearly safer:

- `compare_previous` -> user-facing **Track Play Store listing changes**;
- `inventory_history_enabled` -> user-facing **Track device app inventory changes**.

The master and both child controls live only in the Changes & History dialog. Both child controls remain visible but disabled while the master gate is Off, without changing their stored values.

The master gate is authoritative at runtime. A legacy child key being true must not bypass a disabled master gate.

## Migration

When `changes_history_enabled` is absent, resolve it once from evidence of intentional/real use.

Enable the master gate if any of these are true:
- `compare_previous` is true;
- meaningful Previous Audit History exists;
- any per-device inventory baseline exists;
- any safely discoverable Device Snapshot exists in app-owned canonical data.

Otherwise migrate to Off.

Do **not** enable the master gate merely because legacy `inventory_history_enabled` is true: that setting historically defaulted to true and is not proof of intentional use.

Persist the resolved master value so migration is one-time and later user choices remain authoritative.

Migration must not delete or rewrite history/snapshot contents.

Legacy snapshots saved to arbitrary user-selected filesystem locations were not registered by the application and are not discoverable for migration. Do not scan the user's filesystem to find them.

## Advanced Settings

Advanced Settings contains no Changes & History page, master setting or Store/device child setting. There is no duplicate or hidden configuration path outside the Changes & History dialog.

## Tools menu

Remove the current final user-facing history tree/actions:

- `Device History`
- `Device Snapshots…` submenu
- `Device Inventory Changes…`

Replace them with exactly one always-visible top-level action:

`Changes & History…`

The action remains available whether automatic tracking is On or Off so users can discover and configure the feature and use manual snapshots.

Do not move `Data Maintenance…` into this feature. Data deletion remains separate.

## Changes & History dialog

Use one small native Qt dialog as the canonical configuration and review surface. At the top expose:

- `Enable automatic change tracking` for `changes_history_enabled`;
- native Apply/Save semantics that persist through the normal settings service without deleting retained data.

The Store and device child checkboxes remain visible in their corresponding sections. They are disabled while automatic tracking is Off and enabled independently when it is On. Their stored values survive master Off/On toggles.

### Play Store listing changes

Purpose text: compare current Google Play evidence with the previous successful comparable audit.

Expose:
- `Track Play Store listing changes` for `compare_previous`;
- `Detect availability, Store version and update-status changes between audits. Shown in the Play Store Listing Change column.` directly below the checkbox;
- `Review Play Store Changes…` when current change evidence exists.

If tracking is enabled but no previous baseline/change evidence exists, explain that a successful audit establishes the baseline and do not show a misleading empty report as if changes had been checked.

Reuse the existing canonical Store-change overview/review path.

### Device app inventory changes

Purpose text: compare the current phone inventory with the previous completed audit of the same device.

Expose:
- `Track device app inventory changes` for `inventory_history_enabled`;
- `Detect installed, removed, version, installer and enabled-state changes between scans of the same phone. Shown in the Device App Inventory Change column for phone audit results.` directly below the checkbox;
- `Review Device Changes…` when current device comparison data exists.

Explain that automatic device history can report installed/removed apps, version changes, installer changes and enabled-state changes.

Reuse the existing canonical Device Inventory Changes path and device-association/privacy rules.

## Result-table columns

Keep the persisted row/export identifiers `change` and `device_change`. Their canonical user-facing names are **Play Store Listing Change** and **Device App Inventory Change**, with intentional multiline table headers.

Built-in column presets apply both history gates symmetrically:

- show Play Store Listing Change only when `store_history_enabled(settings)` is true (and never for Local APK sources);
- show Device App Inventory Change only when `device_inventory_history_enabled(settings)` is true and the active source is a device;
- in Basic device results, place Store Status, Play Store Listing Change and Device App Inventory Change before Package Name;
- Source Details and Technical follow the same gates and source applicability;
- Custom remains user-controlled: it retains the user's saved visibility/order/width configuration and does not automatically add a history column that is absent from that saved column set. A saved history-column choice is hidden while inapplicable and returns when its gate/source becomes applicable again.

Applying dialog settings must refresh the existing table presentation immediately through the canonical column-visibility path, without rebuilding the model or resetting saved widths/order.

The production phone-source transition sets the canonical `device` source and reapplies column visibility: built-in presets restore their source defaults, while Custom preserves its saved order and widths. Completed phone-audit presentation retains that source and reapplies column visibility during result finalization.

Customize View checkbox selections are authoritative when Save is clicked. Persist the exact normalized selection plus mandatory columns together with the existing live visual order, usable widths and compatibility header state; do not recapture presentation-time visible columns after applying runtime gates. Cancel and window close discard unsaved edits. The dialog opens from its actual column-content size, bounded by the current screen's available geometry, and retains an as-needed vertical scrollbar for smaller displays.

The dialog footer is one permanent native layout containing the initially hidden saved-status label, stretch and Apply/Close button box. Showing `Settings saved.` after a successful Apply must not add a vertical row or change the dialog's required height.

### Device Snapshots

Purpose text: manual point-in-time snapshots chosen by the user, separate from automatic history.

Expose:
- `Save Current Snapshot…`
- `Compare with Snapshot…`

These actions are enabled only when their existing source/result prerequisites are satisfied, regardless of the automatic-tracking master or child settings.

Explicit snapshots remain user-created data and are never automatically overwritten or deleted by automatic history maintenance.

## Lifecycle and promotion

The master feature gate must participate in runtime lifecycle checks, not only UI visibility.

Master Off:
- skip previous-audit history comparison and promotion;
- skip device-inventory history comparison and promotion;
- do not retain stale history-derived annotations in newly installed results.

Master On:
- Store history only runs/promotes when `compare_previous` is enabled;
- device inventory history only runs/promotes when `inventory_history_enabled` is enabled;
- completed successful eligible audits retain existing promotion behavior;
- stopped, failed and abandoned audits do not promote either automatic baseline;
- Local APK source remains excluded from phone/history promotion exactly as before;
- Device Snapshots remain manual and independent.

Do not change privacy rules or device identity association.

## Data Maintenance

PR #144 semantics stay locked.

`Tools > Data Maintenance…` may still show and clear:
- Previous Audit History;
- Device Inventory History.

This remains useful even if the master feature is currently Off because retained data may exist from earlier use.

Clearing Device Inventory History must continue to preserve Device Snapshots.

## Required regression coverage

Cover at minimum:

1. fresh settings resolve `changes_history_enabled == False`;
2. old settings with only legacy default `inventory_history_enabled=True` resolve master Off;
3. explicit `compare_previous=True` resolves master On;
4. meaningful previous-audit history resolves master On;
5. an inventory baseline resolves master On;
6. a Device Snapshot resolves master On;
7. migration persists once and later explicit Off remains Off even while old data remains;
8. `Tools > Changes & History…` exists with master Off and On;
9. final Tools menu has no old Device History tree;
10. Advanced Settings exposes none of the three Changes & History controls;
11. the Changes & History dialog exposes the master and both child controls;
12. child checkboxes are disabled while master Off and enabled while master On;
13. stored child values survive master Off/On toggles and dialog changes persist;
14. dialog has Play Store listing changes, Device app inventory changes and Device Snapshots sections with the canonical checkbox labels and descriptions;
15. Store review uses existing canonical change evidence and distinguishes no current comparable baseline from a completed comparison with no meaningful changes;
16. Device review uses existing comparison aggregate and respects source/device prerequisites;
17. snapshot actions retain existing prerequisites and remain usable with master Off;
18. snapshot save/load comparison round-trips and Device Inventory History clearing preserves snapshot files;
19. master Off prevents Store history comparison/promotion;
20. master Off prevents device inventory comparison/promotion;
21. master On + child Off skips only that child subsystem;
22. master On + child On preserves successful-audit promotion semantics;
23. stopped/failed/abandoned audits still do not promote;
24. Data Maintenance behavior from #144 is unchanged.
25. Apply immediately updates Play Store Listing Change visibility for master Off/On and Store-child Off/On transitions;
26. Apply immediately updates Device App Inventory Change visibility for master Off/On and device-child Off/On transitions;
27. Basic, Source Details and Technical apply both canonical history gates and device-source applicability;
28. Custom history-column choices remain stored across feature-gate and source changes;
29. schema, Customize View, Smart Query and HTML report labels use the canonical column names;
30. both canonical table headers wrap intentionally and satisfy their bounded width policies.
31. a real completed phone-scan transition resolves to the canonical device source and applies device-history visibility across every built-in preset;
32. completed phone-audit result presentation retains the canonical device source and visibility;
33. Custom does not add a device-history column absent from the saved Custom column set;
34. the saved-status label and native Apply/Close button box share one permanent footer layout before and after Apply.
35. Customize View Save retains a selected but currently inapplicable history column and exposes it after a real phone-source transition;
36. saving an applicable history column survives reopen and restart, while explicit removal also survives reopen and restart;
37. Customize View Cancel and window close discard checkbox edits;
38. a real Changes & History Apply path exposes the device-history column for Basic, Source Details and Technical phone results;
39. Customize View sizing fits content when screen geometry permits and clamps to preserve as-needed scrolling on small displays.

## Out of scope

Do not mix this pass with:
- version bump;
- `.aab` support;
- internal `health_score` -> `maintenance_score` migration;
- Help feedback link;
- ETB/history documentation cleanup beyond wording needed for this feature;
- packaging/Nuitka;
- signing;
- release assets/tags;
- non-Windows release work.
