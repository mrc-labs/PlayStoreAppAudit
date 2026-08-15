# Play Store App Audit - Qt6 branch

This branch contains the **PySide6 / Qt 6** GUI.

The audit engine and Play Store logic remain aligned with the CustomTkinter variant. The two branches intentionally differ mainly in presentation/widget technology.

## App source

The source card keeps the main controls on one horizontal row:

`source field | Choose file | Scan phone with ADB | Store country | Exclude system apps from source`

A compact source-status line appears directly underneath.

`Store country` is detected from the Windows Region and remains editable because Google Play availability can differ by country/region.

Store language is **not exposed in the UI** and is fixed internally to `en`.

Audit concurrency is **fixed internally to 16 parallel workers** and is no longer exposed as a user setting.

When `Exclude system apps from source` is enabled:

- **ADB** loads third-party packages only using `adb shell pm list packages -3`;
- **CSV/TSV** removes packages classified as system while the file is loaded, using an explicit system flag when available, an exact ADB comparison when possible, or the conservative package-name fallback.

When it is disabled, all packages are loaded. `Hide system apps` remains available as a result-table display filter.

## Multi-country availability check

The normal audit checks the selected Store country first. If the package is reported unavailable there, the app automatically checks representative alternate Play Store markets: US, UK, Germany, France, Italy, Switzerland, Spain, Canada, Australia and Japan.

- found in another checked country -> **blue Store anomaly** and a note identifying the selected/unavailable country and the country where it was found;
- not found in any checked market -> **red Removed**, with the checked markets recorded in Notes;
- alternate checks contain request/HTTP errors and no listing is found -> **purple Other**, with an inconclusive multi-country note.

The additional requests run only for packages unavailable in the selected market.

## Compact audit controls

The audit action area is intentionally kept on one horizontal row:

`Run Play Store audit | progress + status | Export results | Clear`

This removes the old standalone progress card and gives more vertical space to the results table.

## Results

The interactive table shows `Package Name` as the canonical package identifier. `Input name` is retained internally/exported when available but is hidden from the on-screen table because it is usually redundant.

The Qt table supports native sorting, draggable/reorderable columns, numeric `Age (days)` sorting, instant text filtering, clickable criticality counters, pastel row colouring, `Hide system apps`, double-click to open Google Play and optional CSV export.

Criticality:

- red: Removed;
- orange: Stale, >730 days;
- yellow: Aging, >365 and <=730 days;
- blue: Store anomaly;
- purple: Other / unknown / error;
- green: Current, <=365 days.

## ADB

If ADB is missing, the app can download the current Windows Platform-Tools package directly from Google's official endpoint and install it under `%LOCALAPPDATA%\PlayStoreAppAudit\platform-tools`.

## Build

GitHub Actions builds `PlayStoreAppAudit-Qt6.exe` as artifact `PlayStoreAppAudit-Windows-Qt6`.

Local entry point: `playstore_audit_qt_compact.py`.
