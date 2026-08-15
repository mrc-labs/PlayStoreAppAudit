# Play Store App Audit - Qt6 branch

This branch contains the **PySide6 / Qt 6** GUI.

The audit engine and Play Store logic remain shared with the CustomTkinter variant. The two branches intentionally differ mainly in presentation/widget technology.

## App source

The source card contains:

- `Choose file`
- `Scan phone with ADB`
- `Store country`
- `Exclude system apps from source`

`Store country` is detected from the Windows Region and remains editable.

Store language is **not exposed in the UI** and is fixed internally to `en`.

Audit concurrency is **fixed internally to 16 parallel workers** and is no longer exposed as a user setting.

When `Exclude system apps from source` is enabled:

- **ADB** loads third-party packages only using `adb shell pm list packages -3`;
- **CSV/TSV** removes packages classified as system while the file is loaded, using an explicit system flag when available, an exact ADB comparison when possible, or the conservative package-name fallback.

When it is disabled, all packages are loaded. `Hide system apps` remains available as a result-table display filter.

## Results

The interactive table shows `Package Name` as the canonical package identifier. `Input name` is retained internally/exported when available but is hidden from the on-screen table because it is usually redundant.

The Qt table supports:

- native sorting;
- draggable/reorderable columns;
- `Age (days)` numeric sorting;
- instant text filtering;
- clickable criticality counters;
- pastel row colouring;
- `Hide system apps` as a visual filter;
- double-click to open the Google Play listing;
- optional CSV export.

Criticality remains:

- red: Removed;
- orange: Stale, >730 days;
- yellow: Aging, >365 and <=730 days;
- blue: Store anomaly;
- purple: Other / unknown / error;
- green: Current, <=365 days.

## ADB

If ADB is missing, the app can download the current Windows Platform-Tools package directly from Google's official endpoint and install it under `%LOCALAPPDATA%\PlayStoreAppAudit\platform-tools`.

## Build

GitHub Actions builds:

`PlayStoreAppAudit-Qt6.exe`

Artifact name:

`PlayStoreAppAudit-Windows-Qt6`

Local entry point:

`playstore_audit_qt_compact.py`
