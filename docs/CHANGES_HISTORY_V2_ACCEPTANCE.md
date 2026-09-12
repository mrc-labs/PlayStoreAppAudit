# v2 Changes & History acceptance

This document locks the owner acceptance contract for issue #145 and the post-#144 v2 UX simplification pass.

## Product goal

Play Store App Audit has three distinct longitudinal features:

1. previous Play Store audit comparison;
2. per-device inventory comparison;
3. explicit Device Snapshots.

They remain separate backends, but the ordinary UI must present them as one optional advanced capability instead of several overlapping menu trees.

## Master feature gate

Add one persisted Advanced setting:

`changes_history_enabled`

User-facing label:

**Enable Changes & History features**

Fresh-install default: **Off**.

When Off:
- the final `Tools > Changes & History…` action does not exist in the menu;
- no previous-Store-audit comparison is performed or promoted;
- no per-device inventory-history comparison is performed or promoted;
- no history-derived row annotations are shown;
- explicit Device Snapshot files and all retained history files are preserved;
- Data Maintenance may still clear retained Previous Audit History or Device Inventory History explicitly;
- Store cache, alternative-store cache, icon cache, Maintenance Score, Local APK, exports and source behavior are unchanged.

When On:
- show one `Tools > Changes & History…` action;
- child tracking settings control automatic Store and device history independently;
- manual Device Snapshot actions are available through that dialog without another tracking checkbox.

Disabling the master gate must never delete history or snapshots.

## Existing compatibility settings

Keep the established backend keys unless a narrow compatibility wrapper is clearly safer:

- `compare_previous` -> user-facing **Track Store changes between audits**;
- `inventory_history_enabled` -> user-facing **Track changes between phone audits**.

Both child controls are disabled in Advanced Settings while the master gate is Off.

The master gate is authoritative at runtime. A legacy child key being true must not bypass a disabled master gate.

## Migration

When `changes_history_enabled` is absent, resolve it once from evidence of intentional/real use.

Enable the master gate if any of these are true:
- `compare_previous` is true;
- meaningful Previous Audit History exists;
- any per-device inventory baseline exists;
- any explicit Device Snapshot exists.

Otherwise migrate to Off.

Do **not** enable the master gate merely because legacy `inventory_history_enabled` is true: that setting historically defaulted to true and is not proof of intentional use.

Persist the resolved master value so migration is one-time and later user choices remain authoritative.

Migration must not delete or rewrite history/snapshot contents.

## Advanced Settings

Add one compact **Changes & History** section containing:

- `Enable Changes & History features`
- `Track Store changes between audits`
- `Track changes between phone audits`

Child controls visually and functionally depend on the master checkbox.

Recommended explanatory copy:

`Optional longitudinal analysis. Keep this off for the simplest workflow. Enabling it adds one Changes & History entry under Tools.`

Store child copy should explain that the first successful comparable audit establishes a baseline.

Device child copy should explain that comparisons are for the same phone/device association and cover installed-app inventory changes.

Settings apply through the existing Advanced Settings save/apply flow. The final menu must reflect the new master value immediately after settings are accepted, without requiring application restart.

## Tools menu

Remove the current final user-facing history tree/actions:

- `Device History`
- `Device Snapshots…` submenu
- `Device Inventory Changes…`

When the master feature is enabled, replace them with exactly one top-level action:

`Changes & History…`

When the master feature is disabled, that action must be absent, not merely disabled.

Do not move `Data Maintenance…` into this feature. Data deletion remains separate.

## Changes & History dialog

Use one small native Qt dialog with three clearly separated sections.

### Store changes

Purpose text: compare current Google Play evidence with the previous successful comparable audit.

Expose:
- current tracking state (`On` / `Off` or equivalent concise presentation);
- `Review Store Changes…` when current change evidence exists.

If tracking is enabled but no previous baseline/change evidence exists, explain that a successful audit establishes the baseline and do not show a misleading empty report as if changes had been checked.

Reuse the existing canonical Store-change overview/review path.

### Device changes

Purpose text: compare the current phone inventory with the previous completed audit of the same device.

Expose:
- current tracking state;
- `Review Device Changes…` when current device comparison data exists.

Explain that automatic device history can report installed/removed apps, version changes, installer changes and enabled-state changes.

Reuse the existing canonical Device Inventory Changes path and device-association/privacy rules.

### Device Snapshots

Purpose text: manual point-in-time snapshots chosen by the user, separate from automatic history.

Expose:
- `Save Current Snapshot…`
- `Compare with Snapshot…`

These actions are enabled only when their existing source/result prerequisites are satisfied.

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
8. disabling master hides/removes `Tools > Changes & History…` without deleting data;
9. enabling master makes the action appear immediately after settings apply;
10. child checkboxes are disabled while master Off;
11. final Tools menu has no old Device History tree;
12. dialog has Store changes, Device changes and Device Snapshots sections;
13. Store review uses existing canonical change evidence and is unavailable/clear when no baseline exists;
14. Device review uses existing comparison aggregate and respects source/device prerequisites;
15. snapshot actions retain existing prerequisites and persistence semantics;
16. master Off prevents Store history comparison/promotion;
17. master Off prevents device inventory comparison/promotion;
18. master On + child Off skips only that child subsystem;
19. master On + child On preserves successful-audit promotion semantics;
20. stopped/failed/abandoned audits still do not promote;
21. Data Maintenance behavior from #144 is unchanged.

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
